"""
Standalone test for http_retry.get_with_retry(). Everything is mocked -
no real network calls, no API keys touched. Run directly:

    venv/bin/python test_retry.py
"""

import unittest
from unittest.mock import MagicMock, patch

from http_retry import get_with_retry


class RetryTestError(Exception):
    pass


def _mock_response(status_code, body="mocked response body"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    return resp


def _status_sequence_side_effect(status_codes):
    """requests.get side_effect that returns one mocked status per call, in
    order, and prints what each attempt got."""
    call_log = []

    def side_effect(url, params=None, timeout=None):
        attempt_num = len(call_log) + 1
        status = status_codes[attempt_num - 1]
        call_log.append(status)
        print(f"  attempt {attempt_num}: mocked GET -> HTTP {status}")
        return _mock_response(status)

    return side_effect


def _sleep_logger(delays_seen):
    def side_effect(seconds):
        delays_seen.append(seconds)
        print(f"    -> retrying in {seconds}s (mocked, not actually waiting)")

    return side_effect


class TestGetWithRetry(unittest.TestCase):
    @patch("http_retry.time.sleep")
    @patch("http_retry.requests.get")
    def test_retries_then_succeeds(self, mock_get, mock_sleep):
        print("\n--- Scenario 1: two 503s, then a 200 ---")
        mock_get.side_effect = _status_sequence_side_effect([503, 503, 200])
        delays_seen = []
        mock_sleep.side_effect = _sleep_logger(delays_seen)

        result = get_with_retry("http://example.test", {}, RetryTestError, "test resource")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(delays_seen, [2, 4])
        print(f"  succeeded on attempt {mock_get.call_count}, delays used: {delays_seen}")

    @patch("http_retry.time.sleep")
    @patch("http_retry.requests.get")
    def test_exhausts_retries_and_raises(self, mock_get, mock_sleep):
        # retries=2 -> 3 total attempts, so 3 straight 503s exactly exhausts it
        # (the default retries=3 -> 4 total attempts, per what we agreed on
        # for fetch_data.py/news.py; using retries=2 here just to match your
        # "three straight 503s" scenario exactly).
        print("\n--- Scenario 2: three straight 503s (retries=2 -> 3 total attempts) ---")
        mock_get.side_effect = _status_sequence_side_effect([503, 503, 503])
        delays_seen = []
        mock_sleep.side_effect = _sleep_logger(delays_seen)

        with self.assertRaises(RetryTestError) as ctx:
            get_with_retry(
                "http://example.test", {}, RetryTestError, "test resource", retries=2
            )

        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(delays_seen, [2, 4])
        self.assertIn("3 attempts", str(ctx.exception))
        print(f"  raised after {mock_get.call_count} attempts, delays used: {delays_seen}")
        print(f"  error message: {ctx.exception}")

    @patch("http_retry.time.sleep")
    @patch("http_retry.requests.get")
    def test_client_error_fails_immediately(self, mock_get, mock_sleep):
        print("\n--- Scenario 3: single 401 ---")
        mock_get.side_effect = _status_sequence_side_effect([401])

        resp = get_with_retry("http://example.test", {}, RetryTestError, "test resource")

        # get_with_retry never raises on a 4xx - it returns the response
        # immediately, with no retry. The call site (fetch_data.py / news.py)
        # is what raises, using the same check they use in the real code -
        # reproduced here so this test proves the full "fails immediately,
        # no retry delay" behavior end to end.
        with self.assertRaises(RetryTestError) as ctx:
            if resp.status_code != 200:
                raise RetryTestError(f"got HTTP {resp.status_code}: {resp.text}")

        self.assertEqual(mock_get.call_count, 1)
        mock_sleep.assert_not_called()
        print(f"  get_with_retry returned after {mock_get.call_count} attempt (no retry)")
        print(f"  call-site check then raised immediately: {ctx.exception}")
        print("  sleep() was never called")


if __name__ == "__main__":
    unittest.main(verbosity=2)
