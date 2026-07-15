#!/usr/bin/env python3
"""
Build jacovanderlaan.com concepts.html from the MDDE concept folder-notes
(W:/data/rules/mdde-concepts/<slug>/<slug>.md) — the source of truth.

Until now concepts.html was hand-maintained and drifted from the vault (the vault
had more concepts than the page). This generator regenerates the concept cards from
the folder-notes so the two can never diverge: add a folder-note, rerun, done.

It rewrites ONLY the concept container (the category headings + cards between
`<div class="wrap" style="max-width:920px;">` and its matching `</div>` before the
CTA). The page head, nav, hero, CTA and footer are preserved verbatim.

Each note contributes one card:
    <div class="concept" id="<slug>">
      <div class="c-name">Title</div>
      <div class="c-tag">one-line description</div>
      <p class="c-def">the body prose</p>
    </div>
grouped under <h2 class="cat-title">Category</h2> + <div class="concept-grid">, in the
fixed CATEGORY_ORDER. [[concept-slug|Label]] wikilinks in the body become in-page
<a href="#slug"> anchors.

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
    up to the 'Where it lives' / back-link footer. Wikilinks -> in-page anchors."""
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


def inline(s: str) -> str:
    """Render the subset of markdown used in concept bodies -> HTML."""
    # [[concept-slug|Label]] or [[concept-slug]] -> in-page anchor
    def _wiki(m):
        target = m.group(1)
        label = m.group(2) if m.group(2) else target
        slug = target[len("concept-"):] if target.startswith("concept-") else target
        return f'<a href="#{html.escape(slug, quote=True)}">{html.escape(label)}</a>'
    s = re.sub(r"\[\[(concept-[a-z0-9-]+)(?:\|([^\]]+))?\]\]", _wiki, s)
    # escape everything else, then re-open the anchors we just built
    # (do bold/italic before escaping is messy; instead escape, then apply markup)
    # Simplify: we already inserted <a> tags; protect them.
    parts = re.split(r"(<a href=\"#[^\"]+\">[^<]*</a>)", s)
    for i, p in enumerate(parts):
        if p.startswith("<a href="):
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", p)
        parts[i] = p
    return "".join(parts)


def load_concepts() -> dict:
    """category -> list of (slug, name, tag, def_html), in filesystem order."""
    by_cat: dict[str, list] = {}
    for folder in sorted(SRC.iterdir()):
        if not folder.is_dir():
            continue
        note = folder / f"{folder.name}.md"
        if not note.exists():
            continue
        meta, body = split_frontmatter(note.read_text(encoding="utf-8"))
        md = meta.get("metadata", {}) if isinstance(meta.get("metadata"), dict) else {}
        cat = str(md.get("category", "")).strip() or "Method"
        name = str(meta.get("name", folder.name))
        name = name[len("concept-"):] if name.startswith("concept-") else name
        # display title = the H1
        m = re.search(r"(?m)^#\s+(.+)$", body)
        title = m.group(1).strip() if m else folder.name.replace("-", " ").title()
        tag = str(meta.get("description", "")).strip()
        def_html = inline(extract_def(body))
        by_cat.setdefault(cat, []).append((folder.name, title, tag, def_html))
    return by_cat


def render_cards(by_cat: dict) -> str:
    blocks = []
    seen = set()
    order = CATEGORY_ORDER + [c for c in by_cat if c not in CATEGORY_ORDER]
    for cat in order:
        items = by_cat.get(cat)
        if not items:
            continue
        seen.add(cat)
        cards = []
        for slug, title, tag, def_html in items:
            cards.append(
                f'        <div class="concept" id="{html.escape(slug, quote=True)}">'
                f'<div class="c-name">{html.escape(title)}</div>'
                f'<div class="c-tag">{html.escape(tag)}</div>'
                f'<p class="c-def">{def_html}</p></div>'
            )
        blocks.append(
            f'      <h2 class="cat-title">{html.escape(cat)}</h2>\n'
            f'      <div class="concept-grid">\n' + "\n".join(cards) + "\n      </div>"
        )
    return "\n".join(blocks)


def main() -> None:
    by_cat = load_concepts()
    total = sum(len(v) for v in by_cat.values())
    cards_html = render_cards(by_cat)

    page = PAGE.read_text(encoding="utf-8")
    # Replace the inside of the concept container. Anchor on the opening wrap div
    # (max-width:920px) and the '</div>\n  </section>' that closes it before the CTA.
    open_marker = '<div class="wrap" style="max-width:920px;">'
    i = page.find(open_marker)
    if i == -1:
        raise SystemExit("concepts.html: concept container opening marker not found")
    start = i + len(open_marker)
    # the container closes at the FIRST '\n    </div>\n  </section>' after start
    close_marker = "\n    </div>\n  </section>"
    j = page.find(close_marker, start)
    if j == -1:
        raise SystemExit("concepts.html: concept container closing marker not found")
    new_page = page[:start] + "\n" + cards_html + "\n    " + page[j + 1:]
    PAGE.write_text(new_page, encoding="utf-8")
    print(f"  concepts.html regenerated: {total} concepts in "
          f"{len([c for c in CATEGORY_ORDER if by_cat.get(c)])} categories")


if __name__ == "__main__":
    main()
