#!/usr/bin/env python3
"""
Build jacovanderlaan.com book-reference pages from the folder-per-book markdown
under BOOKS_ROOT -> books/<slug>.html, and inject a library grid into
references.html (or books.html if present).

Sibling of build_articles.py (ADR-068 references-layer). Same conventions:
folder-per-unit source of truth, YAML frontmatter, the shared md->html renderer
and page chrome are imported from build_articles so the two builders never drift.

A book page is a *reference*, not an article: no full book contents (copyright),
just Jaco's curated take — why it's in the collection, what he did with it, the
citable ideas, related concepts/writing, and an (optional) affiliate link with
disclosure.

Source of truth = W:/data/books/<slug>/<slug>.md (the data-site route of ADR-068).
Only books whose status is in PUBLISH_STATUS (default: pilot) publish, so the 159
scaffolds stay private until their personal "what I did with it" pass is written.
Override with JVDL_BOOK_STATUS="pilot,ready" or JVDL_BOOKS="slug1,slug2".

Usage:
    python build_books.py
    JVDL_BOOKS_ROOT="W:/..." python build_books.py        # override source
    JVDL_BOOK_STATUS="pilot,ready" python build_books.py   # widen publish gate
"""
from __future__ import annotations

import os
import re
import html
import json
import shutil
from pathlib import Path

# Reuse the article builder's battle-tested helpers + chrome so the two never drift.
import build_articles as A
from build_articles import (
    split_frontmatter,
    md_to_html,
    strip_private_sections,
    NAV,
    BASE_URL,
    OG_DEFAULT,
    _norm_reflist,
    _load_concept_map,
    autolink_concepts,
)

HERE = Path(__file__).parent
BOOKS_ROOT = Path(os.environ.get("JVDL_BOOKS_ROOT", "W:/data/books"))
OUT = HERE / "books"             # books/<slug>.html
ASSETS = HERE / "assets"

# Books notes carry a private working section; never publish it.
PRIVATE_SECTIONS = {"notes", "actions", "comments", "briefs"}

# Publish gate: only these statuses go live. Pilot = the flagship books with a
# full hand/AI-written body; scaffolds stay private.
PUBLISH_STATUS = {
    s.strip().lower()
    for s in os.environ.get("JVDL_BOOK_STATUS", "pilot,ready").split(",")
    if s.strip()
}
# Optional explicit allow-list (folder names). If set, it wins over the status gate.
_ALLOW = [s.strip() for s in os.environ.get("JVDL_BOOKS", "").split(",") if s.strip()]

CONCEPTS_PAGE = "../concepts.html"

# Private author notes live inline as HTML comments (<!-- TODO: Jaco … -->).
# Strip them before rendering so they never reach the published page.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_html_comments(body: str) -> str:
    body = _HTML_COMMENT.sub("", body)
    # collapse blank lines left behind, keep single separators
    return re.sub(r"\n{3,}", "\n\n", body)


def strip_placeholder_sections(body: str) -> str:
    """Drop any ## section whose body is only a scaffold placeholder.

    Scaffold notes carry stub sections — a lone italic "_To write…_" line, or the
    "Get the book" affiliate stub before any real affiliate link exists. Those must
    never reach a published page. A section is dropped if, after its heading, the
    only non-blank content is italic placeholder text (starts with "_" / "_To write"
    / "_Affiliate link"). Sections with real prose, bullets, or a blockquote stay.
    """
    parts = re.split(r"(?m)^(## .+)$", body)
    # parts = [pre, head1, body1, head2, body2, ...]
    out = [parts[0]]
    for i in range(1, len(parts), 2):
        head, sec = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        lines = [l for l in sec.strip().split("\n") if l.strip()]
        is_placeholder = bool(lines) and all(
            l.strip().startswith("_") for l in lines
        )
        empty = not lines
        if is_placeholder or empty:
            continue  # drop heading + its stub body
        out.append(head + sec.rstrip() + "\n")
    joined = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", joined).strip() + "\n"


def _fm_str(meta: dict, key: str, default: str = "") -> str:
    return str(meta.get(key, default)).strip().strip("'\"")


def discover_books() -> list[str]:
    """Slugs to build: the allow-list if given, else every folder whose note's
    status is in PUBLISH_STATUS."""
    if _ALLOW:
        return _ALLOW
    slugs = []
    if not BOOKS_ROOT.is_dir():
        print(f"  ! books root not found: {BOOKS_ROOT}")
        return slugs
    for folder in sorted(BOOKS_ROOT.iterdir()):
        if not folder.is_dir():
            continue
        note = folder / f"{folder.name}.md"
        if not note.exists():
            continue
        meta, _ = split_frontmatter(note.read_text(encoding="utf-8"))
        status = _fm_str(meta, "status").lower()
        if status in PUBLISH_STATUS:
            slugs.append(folder.name)
    return slugs


def _authors(meta: dict) -> str:
    a = meta.get("authors")
    if isinstance(a, list):
        return ", ".join(str(x).strip().strip("'\"") for x in a)
    return _fm_str(meta, "authors") or _fm_str(meta, "author")


def _meta_line(meta: dict) -> str:
    """The '<authors> · <year> · <cluster>' eyebrow, from frontmatter."""
    bits = [_authors(meta)]
    y = _fm_str(meta, "year")
    if y:
        bits.append(y)
    cl = _fm_str(meta, "cluster")
    if cl:
        bits.append(cl.replace("-", " "))
    return " · ".join(b for b in bits if b)


def copy_cover(folder: Path, slug: str) -> str:
    """Copy a cover image into assets/ as book-<slug>.<ext>; return filename or ''."""
    for name in ("cover.jpg", "cover.jpeg", "cover.png"):
        src = folder / name
        if src.is_file():
            ASSETS.mkdir(exist_ok=True)
            ext = src.suffix.lower()
            dest_name = f"book-{slug}{ext}"
            shutil.copy2(src, ASSETS / dest_name)
            return dest_name
    return ""


def build_stars(rating) -> str:
    try:
        r = int(rating)
    except (TypeError, ValueError):
        return ""
    r = max(0, min(5, r))
    return "★" * r + "☆" * (5 - r)


def build_related(meta: dict, book_titles: dict, concept_names: dict) -> str:
    """Related concepts + related writing + related books, from frontmatter."""
    rc = _norm_reflist(meta.get("related_concepts"))
    ra = _norm_reflist(meta.get("related_articles"))
    blocks = []
    if rc:
        lis = []
        for c in rc:
            key = str(c).strip()
            bare = key[len("concept-"):] if key.startswith("concept-") else key
            label = concept_names.get(bare) or bare.replace("-", " ").title()
            lis.append(f'<li><a href="{CONCEPTS_PAGE}#{html.escape(bare, quote=True)}">{html.escape(label)}</a></li>')
        blocks.append(f"<h3>Related concepts</h3><ul>{''.join(lis)}</ul>")
    if ra:
        lis = []
        for a in ra:
            if isinstance(a, dict) and a.get("url"):
                lis.append(f'<li><a href="{html.escape(a["url"], quote=True)}">{html.escape(a.get("title") or a["url"])}</a></li>')
            else:
                aslug = str(a).strip()
                # articles live one dir up under articles/, books stay in books/
                if aslug in book_titles:
                    lis.append(f'<li><a href="{html.escape(aslug, quote=True)}.html">{html.escape(book_titles[aslug])}</a></li>')
                else:
                    lis.append(f'<li><a href="../articles/{html.escape(aslug, quote=True)}.html">{html.escape(aslug.replace("-", " ").title())}</a></li>')
        if lis:
            blocks.append(f"<h3>Related writing</h3><ul>{''.join(lis)}</ul>")
    if not blocks:
        return ""
    return f'<aside class="article-related"><h2>Related</h2>{"".join(blocks)}</aside>'


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Books — Jaco van der Laan</title>
  <meta name="description" content="{meta_desc}">
  <meta name="author" content="Jaco van der Laan">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="book">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../css/style.css">
  <link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">
  <link rel="icon" type="image/png" sizes="32x32" href="../assets/favicon-32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="../assets/favicon-16.png">
  <link rel="apple-touch-icon" sizes="180x180" href="../assets/favicon-180.png">
  <script type="application/ld+json">
{json_ld}
  </script>
  <style>
    .article-body {{ max-width: 720px; margin: 0 auto; }}
    .article-body h2 {{ margin-top: 40px; }}
    .article-body p, .article-body li {{ font-size: 18px; line-height: 1.7; color: var(--ink-soft); }}
    .article-body blockquote {{ border-left: 4px solid var(--accent); margin: 24px 0; padding: 4px 0 4px 20px; color: var(--ink); font-style: italic; }}
    .book-hero {{ display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap; }}
    .book-hero img {{ width: 180px; max-width: 40vw; border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,.18); }}
    .book-rating {{ color: var(--accent); letter-spacing: 2px; font-size: 20px; }}
    .article-meta {{ max-width: 720px; margin: 0 auto 8px; color: var(--ink-faint); font-size: 15px; }}
    .book-disclosure {{ font-size: 14px; color: var(--ink-faint); }}
  </style>
</head>
<body>
  <header class="site">
    <div class="wrap">
      <a class="brand" href="../index.html">Jaco van der&nbsp;Laan</a>
      <input type="checkbox" id="navtoggle" class="nav-toggle" aria-hidden="true">
      <label for="navtoggle" class="nav-burger" aria-label="Menu"><span></span><span></span><span></span></label>
{nav}
    </div>
  </header>

  <section class="hero">
    <div class="wrap">
      <p class="eyebrow"><a href="../references.html" style="color:inherit;">References &amp; sources</a> · Books</p>
      <div class="book-hero">
        {cover}
        <div>
          <h1 style="max-width:680px;">{title}</h1>
          <p class="lead">{meta_line}</p>
          {rating}
        </div>
      </div>
    </div>
  </section>

  <section class="tight">
    <div class="wrap">
      <div class="article-body">
{body}
      </div>
    </div>
  </section>

  <section class="band-dark cta-block">
    <div class="wrap">
      <h2>Structure beats magic.</h2>
      <p class="lead" style="margin:0 auto 28px;">These are the sources behind the method. Want it built into how your team works?</p>
      <a class="btn btn-primary" href="../contact.html">Start a conversation</a>
      &nbsp; <a class="btn btn-ghost" href="../references.html">All references →</a>
    </div>
  </section>

  <footer class="site">
    <div class="wrap">
      <div>© 2026 Jaco van der Laan · Consilium Information Systems B.V.</div>
      <div>
        <a href="../approach.html">Approach</a>
        <a href="../references.html">References</a>
        <a href="../about.html">About</a>
        <a href="../articles.html">Articles</a>
        <a href="../contact.html">Contact</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def build_jsonld_book(title, authors, meta_desc, canonical, image, year, isbn):
    data = {
        "@context": "https://schema.org", "@type": "Book",
        "name": title, "description": meta_desc, "image": image, "url": canonical,
    }
    if authors:
        data["author"] = [{"@type": "Person", "name": a.strip()} for a in authors.split(",") if a.strip()]
    if year:
        data["datePublished"] = str(year)
    if isbn:
        data["isbn"] = isbn
    # The page is Jaco's review of the book.
    data["review"] = {
        "@type": "Review",
        "author": {"@type": "Person", "name": "Jaco van der Laan", "url": BASE_URL},
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def _book_titles(slugs: list[str]) -> dict:
    titles = {}
    for slug in slugs:
        src = BOOKS_ROOT / slug / f"{slug}.md"
        if src.exists():
            meta, _ = split_frontmatter(src.read_text(encoding="utf-8"))
            titles[slug] = _fm_str(meta, "title") or slug
    return titles


# Privacy gate: the book source lives on W: and is scanned by the pipeline's
# check_book_privacy.py before we publish anything public. A leak (employer name,
# biographical vendor tool, own-corpus figure, decision-record id, personal name)
# in a published section aborts the build. Override with JVDL_SKIP_PRIVACY=1.
PRIVACY_CHECK = "W:/systems/code/scripts/books/check_book_privacy.py"


def privacy_gate(site: str) -> None:
    if os.environ.get("JVDL_SKIP_PRIVACY") == "1":
        print("  (privacy gate skipped via JVDL_SKIP_PRIVACY=1)")
        return
    import importlib.util
    if not Path(PRIVACY_CHECK).is_file():
        print(f"  ! privacy check not found ({PRIVACY_CHECK}) — proceeding WITHOUT gate")
        return
    spec = importlib.util.spec_from_file_location("check_book_privacy", PRIVACY_CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = mod.ROOTS.get(site)
    files = [str(f) for f in Path(root).glob("*/*.md")
             if f.name not in ("notes.md", "books.md")] if root and Path(root).is_dir() else []
    total = 0
    for f in sorted(files):
        hits = mod.scan_note(f)
        if hits:
            total += len(hits)
            print(f"  PRIVACY LEAK in {os.path.basename(os.path.dirname(f))}:")
            for label, match, line in hits:
                print(f"    [{label}] {match!r}  … {line[:100]}")
    if total:
        raise SystemExit(
            f"\nBUILD ABORTED: {total} private detail(s) in published book sections. "
            f"Generalize them, or set JVDL_SKIP_PRIVACY=1 to override.")
    print(f"  privacy gate OK ({len(files)} book pages clean)")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    slugs = discover_books()
    if not slugs:
        print("  (no books to publish — check status gate / allow-list)")
        return
    # Site of this builder = 'data' (jvdl). Gate before writing any HTML.
    privacy_gate("data")
    book_titles = _book_titles(slugs)
    concept_map, concept_names = _load_concept_map()
    cards = []
    for slug in slugs:
        folder = BOOKS_ROOT / slug
        src = folder / f"{slug}.md"
        if not src.exists():
            print(f"  ! missing folder-note: {src}")
            continue
        meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
        body = strip_private_sections(body)
        body = strip_html_comments(body)
        body = strip_placeholder_sections(body)
        body = autolink_concepts(body, concept_map, slug)
        title = _fm_str(meta, "title") or slug
        authors = _authors(meta)
        meta_line = _meta_line(meta)
        year = _fm_str(meta, "year")
        isbn = _fm_str(meta, "isbn")
        cluster = _fm_str(meta, "cluster")
        curated = _fm_str(meta, "curated_score")
        meta_desc = f"{title} by {authors} — why it's in Jaco van der Laan's curated data-architecture library, and what he built with it."[:300]
        canonical = f"{BASE_URL}/books/{slug}.html"
        cover_file = copy_cover(folder, slug)
        og_image = f"{BASE_URL}/assets/{cover_file}" if cover_file else OG_DEFAULT
        cover_html = (
            f'<img src="../assets/{cover_file}" alt="{html.escape(title, quote=True)} cover">'
            if cover_file else ""
        )
        stars = build_stars(meta.get("my_rating"))
        rating_html = f'<p class="book-rating" title="My rating">{stars}</p>' if stars else ""
        json_ld = build_jsonld_book(title, authors, meta_desc, canonical, og_image, year, isbn)
        rendered = md_to_html(body) + build_related(meta, book_titles, concept_names)
        # Subtle AI-attribution footer, only when the page carries a Highlights section.
        if re.search(r"(?m)^## Highlights\b", body):
            rendered += ('<p class="ai-note"><em>Highlights on this page are '
                         'generated with the help of AI.</em></p>')
        (OUT / f"{slug}.html").write_text(PAGE.format(
            title=html.escape(title, quote=True),
            meta_desc=html.escape(meta_desc, quote=True),
            meta_line=html.escape(meta_line, quote=True),
            cover=cover_html, rating=rating_html,
            canonical=canonical, og_image=og_image, json_ld=json_ld,
            nav=NAV, body=rendered,
        ), encoding="utf-8")
        print(f"  + books/{slug}.html  ({'cover' if cover_file else 'no cover'})")
        cards.append({
            "slug": slug, "title": title, "authors": authors, "year": year,
            "cluster": cluster, "curated": curated, "stars": stars,
        })

    inject_library(cards)


def inject_library(cards: list) -> None:
    """Inject the book grid into references.html (or books.html) between markers.

    Add these two lines where the grid should render:
        <!-- SITE-BOOKS:START -->
        <!-- SITE-BOOKS:END -->
    """
    for name in ("books.html", "references.html"):
        idx = HERE / name
        if not idx.exists():
            continue
        txt = idx.read_text(encoding="utf-8")
        start = "<!-- SITE-BOOKS:START"
        end = "<!-- SITE-BOOKS:END -->"
        i, j = txt.find(start), txt.find(end)
        if i == -1 or j == -1 or j < i:
            print(f"  ! {name}: SITE-BOOKS markers not found — book grid NOT injected (add the two marker comments)")
            continue
        # richest first, then by year desc, then title
        def sort_key(c):
            try:
                cur = int(c["curated"])
            except (TypeError, ValueError):
                cur = 0
            try:
                yr = int(c["year"])
            except (TypeError, ValueError):
                yr = 0
            return (-cur, -yr, c["title"].lower())
        rows = []
        for c in sorted(cards, key=sort_key):
            meta_bits = " · ".join(b for b in [c["authors"], str(c["year"]) if c["year"] else "", c["cluster"].replace("-", " ")] if b)
            stars = f'<span class="book-rating">{c["stars"]}</span> ' if c["stars"] else ""
            rows.append(
                f'        <div class="card">\n'
                f'          <h3><a href="books/{c["slug"]}.html" style="color:inherit;text-decoration:none;">{html.escape(c["title"])}</a></h3>\n'
                f'          <p class="muted">{stars}{html.escape(meta_bits)}</p>\n'
                f'          <p><a href="books/{c["slug"]}.html">Why it&rsquo;s in my library →</a></p>\n'
                f'        </div>'
            )
        start_line_end = txt.find("-->", i) + len("-->")
        block = txt[i:start_line_end] + "\n" + "\n".join(rows) + "\n      " + end
        new = txt[:i] + block + txt[j + len(end):]
        if new != txt:
            idx.write_text(new, encoding="utf-8")
            print(f"  + {name} (injected {len(cards)} book cards)")
        else:
            print(f"  = {name} (cards already current)")
        return
    print("  ! no references.html / books.html to inject into")


if __name__ == "__main__":
    main()
