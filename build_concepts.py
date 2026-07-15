#!/usr/bin/env python3
"""
Build jacovanderlaan.com concept pages from the MDDE concept folder-notes
(W:/data/rules/mdde-concepts/<slug>/<slug>.md) — the source of truth.

Per ADR-084 (concept/glossary/library surface symmetry): MDDE now mirrors SBM's
per-concept model — one detail page per concept plus a grouped index — instead of
a single anchored page. Each concept gets its own URL: shareable, linkable from
articles, indexable for SEO. Same folder-per-concept source, same MDDE chrome.

Outputs:
    concepts.html            — the index: grouped short cards, each LINKING to its
                               detail page (was: inline anchors; now: real links).
    concepts/<slug>.html     — one detail page per concept: title, category,
                               full definition, related-concept links.

The index rewrites ONLY the concept container (between the wrap div and the CTA);
page head, nav, hero, CTA, footer are preserved verbatim. Detail pages are fully
generated from the same head/nav/footer, re-prefixed for the concepts/ subdir.

Usage:
    python build_concepts.py
    JVDL_MDDE_CONCEPTS="W:/..." python build_concepts.py   # override source
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
SRC = Path(os.environ.get("JVDL_MDDE_CONCEPTS", "W:/data/rules/mdde-concepts"))
PAGE = HERE / "concepts.html"
OUT = HERE / "concepts"          # concepts/<slug>.html detail pages

# Fixed category order (mirrors the hand-authored page + the vault README TOC).
CATEGORY_ORDER = [
    "Umbrella thesis",
    "Signature principle",
    "Business-Friendly family",
    "Architecture",
    "SQL & generation",
    "Metadata OS",
    "Lineage & governance",
    "Architecture (anti-pattern)",
    "Temporal patterns",
    "Delivery & method",
    "AI & innovation",
    "AI & innovation (anti-pattern)",
    "Method",
]


def split_frontmatter(text: str):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            meta = {}
            if yaml:
                try:
                    meta = yaml.safe_load(fm) or {}
                except Exception:
                    meta = {}
            return meta, body
    return {}, text


def extract_def(body: str) -> str:
    """The concept definition = the prose paragraph(s) after the '**Category:**' line,
    up to the 'Where it lives' / back-link footer. Wikilinks handled by caller."""
    lines = body.split("\n")
    out, started = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("# ") or s.startswith(">") or s.startswith("**Category:**"):
            started = True
            continue
        if not started:
            continue
        if s.startswith("**Where it lives:**") or s.startswith("← Back") or s.startswith("## "):
            break
        out.append(s)
    prose = " ".join(x for x in out if x).strip()
    return prose


# Slugs that actually have a detail page (populated during load). A wikilink to a
# known concept becomes a real link; to an unknown one, plain text.
_KNOWN_SLUGS: set[str] = set()


def inline(s: str, *, in_detail: bool) -> str:
    """Render the subset of markdown used in concept bodies -> HTML.

    Wikilinks [[concept-slug|Label]] become links to the concept's detail page.
    From the index (in_detail=False) the path is concepts/<slug>.html; from a
    detail page (in_detail=True) it is <slug>.html (same dir)."""
    def _wiki(m):
        target = m.group(1)
        label = m.group(2) if m.group(2) else target
        slug = target[len("concept-"):] if target.startswith("concept-") else target
        disp = html.escape(label)
        if slug in _KNOWN_SLUGS:
            href = f"{slug}.html" if in_detail else f"concepts/{slug}.html"
            return f'<a href="{html.escape(href, quote=True)}">{disp}</a>'
        return disp  # unknown target -> plain text (never link to a missing page)
    s = re.sub(r"\[\[(concept-[a-z0-9-]+)(?:\|([^\]]+))?\]\]", _wiki, s)
    parts = re.split(r"(<a href=\"[^\"]+\">[^<]*</a>)", s)
    for i, p in enumerate(parts):
        if p.startswith("<a href="):
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", p)
        parts[i] = p
    return "".join(parts)


def load_concepts() -> dict:
    """category -> list of dicts {slug,title,tag,def_raw}, in filesystem order.
    Populates _KNOWN_SLUGS so wikilinks only point at pages that exist."""
    by_cat: dict[str, list] = {}
    rows = []
    for folder in sorted(SRC.iterdir()):
        if not folder.is_dir():
            continue
        note = folder / f"{folder.name}.md"
        if not note.exists():
            continue
        _KNOWN_SLUGS.add(folder.name)
        meta, body = split_frontmatter(note.read_text(encoding="utf-8"))
        md = meta.get("metadata", {}) if isinstance(meta.get("metadata"), dict) else {}
        cat = str(md.get("category", "")).strip() or "Method"
        m = re.search(r"(?m)^#\s+(.+)$", body)
        title = m.group(1).strip() if m else folder.name.replace("-", " ").title()
        tag = str(meta.get("description", "")).strip()
        rows.append((cat, {"slug": folder.name, "title": title, "tag": tag,
                           "def_raw": extract_def(body)}))
    for cat, row in rows:
        by_cat.setdefault(cat, []).append(row)
    return by_cat


def render_cards(by_cat: dict) -> str:
    """Index cards — each links to its detail page."""
    blocks = []
    order = CATEGORY_ORDER + [c for c in by_cat if c not in CATEGORY_ORDER]
    for cat in order:
        items = by_cat.get(cat)
        if not items:
            continue
        cards = []
        for c in items:
            href = f"concepts/{html.escape(c['slug'], quote=True)}.html"
            cards.append(
                f'        <a class="concept" href="{href}">'
                f'<div class="c-name">{html.escape(c["title"])}</div>'
                f'<div class="c-tag">{html.escape(c["tag"])}</div>'
                f'<p class="c-def">{inline(c["def_raw"], in_detail=False)}</p></a>'
            )
        blocks.append(
            f'      <h2 class="cat-title">{html.escape(cat)}</h2>\n'
            f'      <div class="concept-grid">\n' + "\n".join(cards) + "\n      </div>"
        )
    return "\n".join(blocks)


# --- detail-page chrome: reuse the index page's <head> + <header> + <footer>, ---
# --- but re-prefix relative asset/nav links with ../ for the concepts/ subdir. ---

def _reprefix(fragment: str) -> str:
    """Rewrite root-relative links (href/src="foo.html", "css/…", "assets/…") to
    ../ so they resolve from concepts/<slug>.html."""
    def fix(m):
        attr, val = m.group(1), m.group(2)
        if val.startswith(("http", "#", "//", "mailto:", "../")):
            return m.group(0)
        return f'{attr}="../{val}"'
    return re.sub(r'(href|src)="([^"]+)"', fix, fragment)


def _page_shell():
    """Extract (head_html, header_html, footer_html) from the index page, once."""
    page = PAGE.read_text(encoding="utf-8")
    head = re.search(r"<head>.*?</head>", page, re.S).group(0)
    header = re.search(r'<header class="site">.*?</header>', page, re.S).group(0)
    fm = re.search(r"<footer.*?</footer>", page, re.S)
    footer = fm.group(0) if fm else ""
    return head, header, footer


def render_detail(c: dict, cat: str, head: str, header: str, footer: str) -> str:
    title = html.escape(c["title"])
    tag = html.escape(c["tag"])
    body_html = inline(c["def_raw"], in_detail=True)
    # detail-specific <head>: reprefix assets, swap title/description/og:url
    d_head = _reprefix(head)
    d_head = re.sub(r"<title>.*?</title>",
                    f"<title>{title} — Concepts — Jaco van der Laan</title>", d_head, flags=re.S)
    d_head = re.sub(r'(<meta name="description" content=")[^"]*(">)',
                    lambda m: m.group(1) + tag + m.group(2), d_head)
    d_head = re.sub(r'(<meta property="og:url" content=")[^"]*(">)',
                    lambda m: m.group(1) + f"https://www.jacovanderlaan.com/concepts/{c['slug']}.html" + m.group(2), d_head)
    d_header = _reprefix(header)
    d_footer = _reprefix(footer)
    detail_style = (
        "<style>\n"
        "  .c-detail { max-width:760px; }\n"
        "  .c-detail .eyebrow { color:var(--accent); }\n"
        "  .c-detail .c-cat { font-size:14px; font-weight:600; color:var(--accent);"
        " text-transform:uppercase; letter-spacing:1px; margin-bottom:10px; }\n"
        "  .c-detail h1 { margin-bottom:14px; }\n"
        "  .c-detail .c-body { font-size:17px; line-height:1.7; color:var(--ink-soft); }\n"
        "  .c-back { display:inline-block; margin-top:2.4rem; font-weight:600;"
        " color:var(--accent); text-decoration:none; }\n"
        "  .c-back:hover { text-decoration:underline; }\n"
        "</style>"
    )
    d_head = d_head.replace("</head>", detail_style + "\n</head>")
    return f"""<!doctype html>
<html lang="en">
{d_head}
<body>
{d_header}

  <section class="hero">
    <div class="wrap c-detail">
      <p class="c-cat">{html.escape(cat)}</p>
      <h1>{title}</h1>
      <p class="lead">{tag}</p>
    </div>
  </section>

  <section class="tight">
    <div class="wrap c-detail">
      <p class="c-body">{body_html}</p>
      <a class="c-back" href="../concepts.html">← All concepts &amp; vocabulary</a>
    </div>
  </section>

{d_footer}
</body>
</html>
"""


def write_index(by_cat: dict) -> int:
    cards_html = render_cards(by_cat)
    page = PAGE.read_text(encoding="utf-8")
    open_marker = '<div class="wrap" style="max-width:920px;">'
    i = page.find(open_marker)
    if i == -1:
        raise SystemExit("concepts.html: concept container opening marker not found")
    start = i + len(open_marker)
    # Idempotent close: the concept container is closed by the LAST </div> that
    # precedes the container's closing </section>. Anchor on the *next* </section>
    # after `start` (the concept section), then step back to the </div> just before
    # it. This survives re-runs (no dependence on exact whitespace we ourselves emit).
    sec = page.find("</section>", start)
    if sec == -1:
        raise SystemExit("concepts.html: concept container closing </section> not found")
    close_div = page.rfind("</div>", start, sec)
    if close_div == -1:
        raise SystemExit("concepts.html: concept container closing </div> not found")
    # Rebuild: opening wrap div + generated cards + the wrap's own closing </div>
    # + the rest (the </section> and everything after) verbatim.
    new_page = page[:start] + "\n" + cards_html + "\n    </div>\n  " + page[sec:]
    PAGE.write_text(new_page, encoding="utf-8")
    return sum(len(v) for v in by_cat.values())


def main() -> None:
    by_cat = load_concepts()
    total = write_index(by_cat)
    OUT.mkdir(exist_ok=True)
    head, header, footer = _page_shell()
    n = 0
    for cat, items in by_cat.items():
        for c in items:
            (OUT / f"{c['slug']}.html").write_text(
                render_detail(c, cat, head, header, footer), encoding="utf-8")
            n += 1
    cats = len([c for c in CATEGORY_ORDER if by_cat.get(c)])
    print(f"  concepts.html index regenerated: {total} concepts in {cats} categories")
    print(f"  concepts/<slug>.html: {n} detail pages -> {OUT}")


if __name__ == "__main__":
    main()
