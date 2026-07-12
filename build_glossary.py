#!/usr/bin/env python3
"""Build the MDDE glossary page (jacovanderlaan.com) -> glossary/index.html.

Source of truth = TWO vault markdown files, merged in order:
    D:/vault/system/glossary/glossary-mdde.md    (MDDE-only terms + intro)
    D:/vault/system/glossary/glossary-shared.md  (terms shared with SBM)

Companion to the SBM glossary builder in C:/Repos/structurebeatsmagic. The
glossary was split by brand (2026-07-12): SBM-only, MDDE-only, shared. The MDDE
site renders mdde + shared; SBM renders sbm + shared. Edit a shared term once in
glossary-shared.md and both sites pick it up.

This site (jacovanderlaan-site) is the STATIC PRECURSOR to the WordPress MDDE
site. This builder emits the staged static page; a WordPress-page feed is a
later step. Parser/renderer mirror the SBM build_glossary.py; chrome (nav, css,
footer) is this site's — the nav is read from build_articles.py so it never
drifts from the rest of the site.

Usage:
    python build_glossary.py
"""
from __future__ import annotations

import os
import re
import html
from pathlib import Path
from dataclasses import dataclass, field

HERE = Path(__file__).parent
GLOSSARY_DIR = Path(os.environ.get("MDDE_GLOSSARY_DIR", "D:/vault/system/glossary"))
SRC_MDDE = GLOSSARY_DIR / "glossary-mdde.md"      # MDDE-only terms (+ intro)
SRC_SHARED = GLOSSARY_DIR / "glossary-shared.md"  # terms shared with SBM
OUT = HERE / "glossary"
# MDDE concept pages live on concepts.html (a single hand-written page), not
# per-slug files. So we can't link [[concept-x]] to a detail page here — render
# concept references as plain text (the SBM site owns per-concept detail pages).
CONCEPT_SLUGS: set[str] = set()


def split_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


@dataclass
class Term:
    name: str
    definition_md: str


@dataclass
class Group:
    title: str
    terms: list = field(default_factory=list)


def parse_glossary(src: Path) -> tuple[str, list[Group]]:
    """Return (intro_md, [Group]). Groups = '## ' sections; terms = '- **X** — ...'
    bullets. Intro = everything between H1 and the first '## ' (minus blockquote/rule)."""
    body = split_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
    lines = body.split("\n")
    groups: list[Group] = []
    intro_lines: list[str] = []
    cur: Group | None = None
    seen_h2 = False
    term_re = re.compile(r"^\s*-\s+\*\*(.+?)\*\*\s+[—-]\s+(.+)$")
    for ln in lines:
        st = ln.rstrip()
        if st.startswith("# ") and not seen_h2:
            continue
        if st.startswith("## "):
            seen_h2 = True
            if st[3:].strip().lower() == "cross-references":
                cur = None
                continue
            cur = Group(title=st[3:].strip())
            groups.append(cur)
            continue
        if cur is not None:
            m = term_re.match(st)
            if m:
                cur.terms.append(Term(name=m.group(1).strip(),
                                      definition_md=m.group(2).strip()))
        elif not seen_h2:
            if st.startswith(">") or st == "---":
                continue
            intro_lines.append(st)
    groups = [g for g in groups if g.terms]
    intro = "\n".join(intro_lines).strip()
    return intro, groups


def merge_groups(groups: list[Group]) -> list[Group]:
    """Fold groups that share a title into one (case-insensitive), preserving
    first-seen order. Lets a brand file and the shared file both use e.g.
    'Data & modelling' without rendering two identical section headers."""
    out: list[Group] = []
    by_key: dict[str, Group] = {}
    for g in groups:
        key = g.title.strip().lower()
        if key in by_key:
            by_key[key].terms.extend(g.terms)
        else:
            ng = Group(title=g.title, terms=list(g.terms))
            by_key[key] = ng
            out.append(ng)
    return out


def esc(x: str) -> str:
    return html.escape(x or "", quote=False)


def render_inline(md: str) -> str:
    """Render a definition's inline markdown. Concept wikilinks -> plain label text
    (MDDE has no per-concept detail pages), **bold**, *italic*, `code`."""
    def _wikilink(m: "re.Match") -> str:
        target = m.group(1).strip()
        label = (m.group(2) or "").strip()
        if target.startswith("concept-"):
            slug = target[len("concept-"):]
            return esc(label or slug.replace("-", " ").title())
        return esc(label or target)

    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wikilink, md)
    # concept labels are already escaped; escape the rest, then restore inline md
    s = html.escape(s, quote=False).replace("&amp;lt;", "&lt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def load_nav() -> str:
    """Read the NAV block from build_articles.py so the glossary nav never drifts
    from the rest of the site."""
    src = (HERE / "build_articles.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'NAV = """(.*?)"""', src, re.S)
    return m.group(1) if m else '      <nav class="main"><a href="../index.html">Home</a></nav>'


NAV = load_nav()

STYLE = """<style>
    .gl-hero { max-width:820px; margin:0 auto; padding:48px 0 8px; text-align:center; }
    .gl-eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:13px; font-weight:700; color:var(--accent); }
    .gl-hero h1 { font-size:52px; margin:.2em 0 .3em; letter-spacing:-.02em; }
    .gl-intro { max-width:720px; margin:0 auto; color:var(--ink-soft); font-size:18px; line-height:1.65; }
    .gl-intro code { background:var(--surface); padding:1px 6px; border-radius:5px; font-size:.9em; }
    .gl-wrap { max-width:820px; margin:0 auto; padding:24px 0 64px; }
    .gl-group { margin-top:2.4rem; }
    .gl-group h2 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:var(--accent); margin:0 0 .9rem; }
    .gl-list { display:grid; gap:14px; }
    .gl-term { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px 20px; }
    .gl-term .t { font-size:18px; font-weight:800; color:var(--ink); margin-bottom:5px; }
    .gl-term .d { font-size:16px; color:var(--ink-soft); margin:0; line-height:1.6; }
    .gl-term .d code { background:var(--bg); padding:1px 5px; border-radius:4px; font-size:.88em; }
    .gl-note { margin-top:2.4rem; font-size:15px; color:var(--ink-faint); border-top:1px solid var(--line); padding-top:1rem; }
</style>"""


def render(intro: str, groups: list[Group]) -> str:
    body: list[str] = []
    for g in groups:
        body.append('<div class="gl-group">')
        body.append(f'<h2>{esc(g.title)}</h2>')
        body.append('<div class="gl-list">')
        for t in g.terms:
            body.append(
                '<div class="gl-term">'
                f'<div class="t">{esc(t.name)}</div>'
                f'<p class="d">{render_inline(t.definition_md)}</p>'
                '</div>'
            )
        body.append('</div></div>')
    groups_html = "\n".join(body)
    intro_html = render_inline(intro.replace("\n", " ")) if intro else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Glossary — Jaco van der Laan</title>
  <meta name="description" content="The non-concept vocabulary of Model-Driven Data Engineering — field terms and distinctions defined and linked. A volatile layer under the concept library.">
  <meta name="author" content="Jaco van der Laan">
  <link rel="canonical" href="https://jacovanderlaan.com/glossary/">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Glossary — Jaco van der Laan">
  <meta property="og:description" content="The vocabulary of Model-Driven Data Engineering, defined and linked.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../css/style.css">
  <link rel="icon" type="image/svg+xml" href="../assets/favicon.svg">
{STYLE}
</head>
<body>

  <header class="site">
    <div class="wrap">
      <a class="brand" href="../index.html">Jaco van der&nbsp;Laan</a>
      <input type="checkbox" id="navtoggle" class="nav-toggle" aria-hidden="true">
      <label for="navtoggle" class="nav-burger" aria-label="Menu"><span></span><span></span><span></span></label>
{NAV}
    </div>
  </header>

  <main>
    <div class="gl-hero">
      <div class="gl-eyebrow">The vocabulary, defined</div>
      <h1>Glossary</h1>
      <p class="gl-intro">{intro_html}</p>
    </div>
    <div class="gl-wrap">
{groups_html}
      <p class="gl-note">A volatile, promotable layer: a term that keeps recurring or earns its own article gets promoted to a <a href="../concepts.html">concept</a>. The coined concepts live in <a href="../concepts.html">concepts &amp; vocabulary</a>.</p>
    </div>
  </main>

  <footer class="site">
    <div class="wrap">
      <div>© 2026 Jaco van der Laan · Consilium Information Systems B.V.</div>
      <div>
        <a href="../approach.html">Approach</a>
        <a href="../services.html">Services</a>
        <a href="../about.html">About</a>
        <a href="../articles.html">Articles</a>
        <a href="../contact.html">Contact</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def main() -> None:
    for src in (SRC_MDDE, SRC_SHARED):
        if not src.exists():
            raise SystemExit(f"Glossary source not found: {src}")
    intro, groups = parse_glossary(SRC_MDDE)
    _, shared_groups = parse_glossary(SRC_SHARED)
    groups = merge_groups(groups + shared_groups)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(render(intro, groups), encoding="utf-8")
    n = sum(len(g.terms) for g in groups)
    print(f"  glossary/index.html ({n} terms in {len(groups)} groups: mdde + shared) -> {OUT}")


if __name__ == "__main__":
    main()
