import time

import requests


def get_with_retry(url, params, error_cls, resource_label, timeout=15, retries=3, base_delay=2):
    """GET url with params, retrying transient failures with exponential backoff.

    Retries on network-level failures and 5xx responses only (base_delay,
    base_delay*2, base_delay*4, ... between attempts). A 2xx or 4xx response
    is returned immediately without retrying — a 4xx means the request itself
    is wrong (bad key, bad params) and retrying won't change that.

    Raises error_cls if every attempt fails, with the attempt count and the
    last failure reason in the message.
    """
    total_attempts = retries + 1
    last_error_detail = None

    for attempt in range(1, total_attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_error_detail = f"network error: {exc}"
        else:
            if response.status_code < 500:
                return response
            last_error_detail = f"HTTP {response.status_code}: {response.text[:300]}"

        if attempt < total_attempts:
            time.sleep(base_delay * (2 ** (attempt - 1)))

    raise error_cls(
        f"{resource_label} failed after {total_attempts} attempts "
        f"(retrying network errors and 5xx responses only): {last_error_detail}"
    )
