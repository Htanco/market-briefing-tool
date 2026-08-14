import html
import re

from config import BRIEFINGS_DIR, PROJECT_ROOT

DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_BRIEFINGS_DIR = DOCS_DIR / "briefings"

DATE_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.md$")

PAGE_STYLE = """
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 700px; margin: 3rem auto; padding: 0 1.5rem; color: #1a1a1a; }
    h1 { font-size: 1.4rem; }
    a { color: #0645ad; }
    ul { list-style: none; padding: 0; }
    li { padding: 0.3rem 0; }
    p { line-height: 1.6; }
"""


def _text_to_html_paragraphs(text):
    paragraphs = re.split(r"\n\s*\n", text.strip())
    html_paragraphs = []
    for para in paragraphs:
        escaped = html.escape(para.strip()).replace("\n", "<br>\n")
        html_paragraphs.append(f"<p>{escaped}</p>")
    return "\n".join(html_paragraphs)


def _briefing_page_html(date_str, body_text):
    body_html = _text_to_html_paragraphs(body_text)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Oil Briefing — {date_str}</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<p><a href="../index.html">&larr; Back to archive</a></p>
<h1>Oil Briefing — {date_str}</h1>
{body_html}
</body>
</html>
"""


def _index_html(dated_entries):
    items = "\n".join(
        f'  <li><a href="briefings/{html_name}">{date_str}</a></li>'
        for date_str, html_name in dated_entries
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Oil Market Briefing Archive</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<h1>Oil Market Briefing Archive</h1>
<ul>
{items}
</ul>
</body>
</html>
"""


def build_index():
    DOCS_BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

    dated_entries = []
    for md_path in BRIEFINGS_DIR.glob("*.md"):
        match = DATE_RE.search(md_path.name)
        if not match:
            continue
        date_str = match.group(1)
        html_name = md_path.stem + ".html"

        body_text = md_path.read_text()
        (DOCS_BRIEFINGS_DIR / html_name).write_text(_briefing_page_html(date_str, body_text))

        dated_entries.append((date_str, html_name))

    dated_entries.sort(key=lambda entry: entry[0], reverse=True)

    (DOCS_DIR / "index.html").write_text(_index_html(dated_entries))

    return dated_entries


if __name__ == "__main__":
    entries = build_index()
    print(f"Built docs/index.html with {len(entries)} briefing(s).")
