import html
import re

from config import BRIEFINGS_DIR, COMMODITIES, PROJECT_ROOT, get_commodity_config

DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_BRIEFINGS_DIR = DOCS_DIR / "briefings"

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")

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


def _briefing_page_html(commodity, date_str, body_text):
    display_name = get_commodity_config(commodity)["display_name"]
    body_html = _text_to_html_paragraphs(body_text)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(display_name)} Briefing — {date_str}</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<p><a href="../../index.html">&larr; Back to archive</a></p>
<h1>{html.escape(display_name)} Briefing — {date_str}</h1>
{body_html}
</body>
</html>
"""


def _index_html(sections):
    section_blocks = []
    for commodity, display_name, dated_entries in sections:
        if dated_entries:
            items = "\n".join(
                f'    <li><a href="briefings/{commodity}/{date_str}.html">{date_str}</a></li>'
                for date_str, _ in dated_entries
            )
        else:
            items = "    <li>No briefings yet.</li>"
        section_blocks.append(f"""  <section>
  <h2>{html.escape(display_name)}</h2>
  <ul>
{items}
  </ul>
  </section>""")

    sections_html = "\n".join(section_blocks)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Commodity Market Briefing Archive</title>
<style>{PAGE_STYLE}</style>
</head>
<body>
<h1>Commodity Market Briefing Archive</h1>
{sections_html}
</body>
</html>
"""


def build_index():
    DOCS_BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

    sections = []
    for commodity in COMMODITIES:
        display_name = get_commodity_config(commodity)["display_name"]
        commodity_briefings_src_dir = BRIEFINGS_DIR / commodity
        commodity_docs_dir = DOCS_BRIEFINGS_DIR / commodity
        commodity_docs_dir.mkdir(parents=True, exist_ok=True)

        dated_entries = []
        if commodity_briefings_src_dir.exists():
            for md_path in commodity_briefings_src_dir.glob("*.md"):
                match = DATE_RE.match(md_path.name)
                if not match:
                    continue
                date_str = match.group(1)
                html_name = f"{date_str}.html"

                body_text = md_path.read_text()
                (commodity_docs_dir / html_name).write_text(
                    _briefing_page_html(commodity, date_str, body_text)
                )

                dated_entries.append((date_str, html_name))

        dated_entries.sort(key=lambda entry: entry[0], reverse=True)
        sections.append((commodity, display_name, dated_entries))

    (DOCS_DIR / "index.html").write_text(_index_html(sections))

    return sections


if __name__ == "__main__":
    sections = build_index()
    total = sum(len(entries) for _, _, entries in sections)
    for commodity, display_name, entries in sections:
        print(f"  {display_name}: {len(entries)} briefing(s)")
    print(f"Built docs/index.html with {total} briefing(s) across {len(sections)} commodities.")
