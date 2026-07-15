#!/usr/bin/env python3
"""
Build jacovanderlaan.com B2B/MDDE article pages from markdown -> articles/*.html
+ inject an "On this site" list into articles.html.

Mirror of the SBM builder (structurebeatsmagic/build_articles.py), adapted to the
jacovanderlaan.com brand: this site's css/style.css, the dropdown nav, the jvdl
favicon/OG card, and canonical_home = jacovanderlaan.com. This is the B2B / MDDE
lane per ADR-062 (two canonical-homes, routed by audience).

Source of truth = folder-per-article markdown under ARTICLES_ROOT. Only slugs in
ARTICLES publish, so unrelated drafts stay private.

Usage:
    python build_articles.py
    JVDL_ARTICLES_ROOT="W:/..." python build_articles.py   # override source
"""
from __future__ import annotations

import os
import re
import html
import json
import shutil
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

HERE = Path(__file__).parent
# B2B/MDDE article source home (folder-per-article: <slug>/<slug>.md + assets/).
ARTICLES_ROOT = Path(os.environ.get(
    "JVDL_ARTICLES_ROOT",
    "W:/data/products/mdde/articles",
))
OUT = HERE / "articles"          # articles/<slug>.html
ASSETS = HERE / "assets"

PRIVATE_SECTIONS = {"notes", "actions", "comments", "briefs"}

# Explicit allow-list of article slugs (folder names). Only these publish.
ARTICLES = [
    "the-missing-system",
    "stop-driving-by-the-rear-view-mirror",
]

# ⚠️ Canonical base = where these pages ACTUALLY live.
# jacovanderlaan.com is the live WordPress site (nginx/SiteGround, 35.214.139.114)
# — NOT this static site. Pointing the canonical at jacovanderlaan.com/articles/...
# yields a 404 (verified 2026-07-15), which is worse than no canonical at all.
# So we canonicalise to the github.io URL where these pages are really served,
# until the hosting decision is made (WordPress publish vs DNS cutover) — see
# action_move-b2b-articles-to-jacovanderlaan. Override via JVDL_BASE_URL once the
# domain question is settled.
BASE_URL = os.environ.get(
    "JVDL_BASE_URL",
    "https://jacovanderlaan.github.io/jacovanderlaan-site",
).rstrip("/")
OG_DEFAULT = f"{BASE_URL}/assets/structurebeatsmagic/sbm-og-card.png"

# The shared nav block (dropdown menu) — kept identical to the site's pages.
NAV = """      <nav class="main">
        <span class="navgroup">
          <button class="navtop" type="button">Approach</button>
          <span class="navmenu">
            <a href="../approach.html">The approach</a>
            <a href="../principles.html">Principles &amp; manifesto</a>
            <a href="../concepts.html">Concepts &amp; vocabulary</a>
            <a href="../mdde.html">MDDE</a>
          </span>
        </span>
        <span class="navgroup">
          <button class="navtop" type="button">Services</button>
          <span class="navmenu">
            <a href="../services.html">Services</a>
            <a href="../work.html">Work &amp; case studies</a>
          </span>
        </span>
        <span class="navgroup">
          <button class="navtop" type="button">Expertise</button>
          <span class="navmenu">
            <a href="../expertise.html">Overview</a>
            <a href="../expertise-sql-migration.html">SQL parsing &amp; migration</a>
            <a href="../expertise-data-vault.html">Data Vault</a>
            <a href="../expertise-data-modeling.html">Data modeling</a>
            <a href="../expertise-diagram-generation.html">Diagram generation</a>
            <a href="../expertise-modeling-tools.html">Modeling tools</a>
            <a href="../expertise-engineering.html">Engineering &amp; architecture</a>
          </span>
        </span>
        <a href="../articles.html">Articles</a>
        <span class="navgroup">
          <button class="navtop" type="button">About</button>
          <span class="navmenu">
            <a href="../about.html">About</a>
            <a href="../references.html">References</a>
            <a href="../ideas.html">Ideas</a>
          </span>
        </span>
        <a class="nav-cta" href="../contact.html">Get in touch</a>
      </nav>"""


def split_frontmatter(text: str):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            meta = {}
            if yaml:
                try:
                    meta = yaml.safe_load(fm_raw) or {}
                except Exception:
                    meta = {}
            return meta, body
    return {}, text


def strip_private_sections(body: str) -> str:
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("## "):
            name = st[3:].strip().rstrip(":").lower()
            if name in PRIVATE_SECTIONS:
                return "\n".join(lines[:i]).rstrip() + "\n"
    return body


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out, para, bullets, quote = [], [], [], []

    def flush_bullets():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    def flush_quote():
        if quote:
            paras = [[]]
            for q in quote:
                if q == "":
                    if paras[-1]:
                        paras.append([])
                else:
                    paras[-1].append(q)
            body = "".join(f"<p>{inline(' '.join(p).strip())}</p>" for p in paras if p)
            out.append(f"<blockquote>{body}</blockquote>")
            quote.clear()

    def flush():
        flush_bullets()
        flush_quote()
        if para:
            joined = " ".join(para).strip()
            if joined:
                out.append(f"<p>{inline(joined)}</p>")
            para.clear()

    def inline(s: str) -> str:
        spans = []
        def _stash(m):
            spans.append(html.escape(m.group(1), quote=False))
            return f"\x00{len(spans) - 1}\x00"
        s = re.sub(r"`([^`]+)`", _stash, s)
        s = html.escape(s, quote=False)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{spans[int(m.group(1))]}</code>", s)
        return s

    first_h1_skipped = lede_checked = in_code = False
    code = []
    for ln in lines:
        st = ln.strip()
        if st.startswith("```"):
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
                code.clear(); in_code = False
            else:
                flush(); lede_checked = True; in_code = True
            continue
        if in_code:
            code.append(ln); continue
        if not st:
            flush(); continue
        if st.startswith("# ") and not first_h1_skipped:
            first_h1_skipped = True; continue
        if (first_h1_skipped and not lede_checked and not out and not para
                and st.startswith("*") and st.endswith("*") and not st.startswith("**")):
            lede_checked = True; continue
        lede_checked = True
        if st == "---":
            flush(); out.append("<hr/>"); continue
        if st.startswith("[[figure:") and st.endswith("]]"):
            flush()
            inner = st[len("[[figure:"):-2].strip()
            fn, _, cap = inner.partition("|")
            fn, cap = fn.strip(), cap.strip()
            cap_html = f"<figcaption>{inline(cap)}</figcaption>" if cap else ""
            out.append(f'<figure class="graphic"><img src="../assets/{fn}" '
                       f'alt="{cap or fn}" loading="lazy"/>{cap_html}</figure>')
            continue
        if st.startswith("### "):
            flush(); out.append(f"<h3>{inline(st[4:])}</h3>"); continue
        if st.startswith("## "):
            flush(); out.append(f"<h2>{inline(st[3:])}</h2>"); continue
        if st.startswith("# "):
            flush(); out.append(f"<h2>{inline(st[2:])}</h2>"); continue
        if st == ">" or st.startswith("> "):
            if para: flush()
            flush_bullets()
            quote.append("" if st == ">" else st[2:].strip())
            continue
        flush_quote()
        if st.startswith("- ") or (st.startswith("* ") and not st.startswith("**")):
            if para: flush()
            bullets.append(st[2:].strip()); continue
        flush_bullets()
        para.append(st)
    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code), quote=False)}</code></pre>")
    flush()
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Jaco van der Laan</title>
  <meta name="description" content="{subtitle}">
  <meta name="author" content="Jaco van der Laan">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{subtitle}">
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
    .article-body pre {{ background: #0f172a; color: #e2e8f0; padding: 18px; border-radius: 12px; overflow-x: auto; font-size: 14px; }}
    .article-meta {{ max-width: 720px; margin: 0 auto 8px; color: var(--ink-faint); font-size: 15px; }}
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
      <p class="eyebrow">{face}</p>
      <h1 style="max-width:820px;">{title}</h1>
      <p class="lead">{subtitle}</p>
      <p class="article-meta">By Jaco van der Laan{date}</p>
      {hero}
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
      <h2>Want this built into how your team works?</h2>
      <p class="lead" style="margin:0 auto 28px;">Structure + Data + AI + Rules → Intelligence. Let's talk about your platform.</p>
      <a class="btn btn-primary" href="../contact.html">Start a conversation</a>
      &nbsp; <a class="btn btn-ghost" href="../articles.html">More writing →</a>
    </div>
  </section>

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


def face_label(meta: dict) -> str:
    f = str(meta.get("face", "")).lower()
    if "enterprise" in f or "b2b" in f or "architect" in f or "data leader" in f:
        return "For data leaders &amp; architects"
    return "MDDE · Model-Driven Data Engineering"


def build_jsonld(title, subtitle, canonical, image, created):
    data = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": title, "description": subtitle, "image": image,
        "author": {"@type": "Person", "name": "Jaco van der Laan",
                   "url": BASE_URL,
                   "sameAs": [BASE_URL, "https://www.linkedin.com/in/jacovanderlaan",
                              "https://medium.com/@jacovanderlaan"]},
        "publisher": {"@type": "Person", "name": "Jaco van der Laan", "url": BASE_URL},
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical}, "url": canonical,
    }
    if created:
        data["datePublished"] = created; data["dateModified"] = created
    return json.dumps(data, indent=2, ensure_ascii=False)


def copy_assets(folder: Path) -> int:
    src = folder / "assets"
    if not src.is_dir():
        return 0
    ASSETS.mkdir(exist_ok=True)
    n = 0
    for f in sorted(src.iterdir()):
        if f.is_file():
            shutil.copy2(f, ASSETS / f.name); n += 1
    return n


# --- Concept linking (ported from the SBM builder; MDDE variant) --------------
# MDDE has ONE concepts page (concepts.html) with per-concept anchor ids, so
# links are ../concepts.html#<slug> rather than a per-concept page. Auto-links
# the first mention of each concept name (+ curated synonyms) in an article body,
# and renders a Related section from related_concepts / related_articles.
CONCEPTS_PAGE = "../concepts.html"

CONCEPT_SYNONYMS = {
    "the-missing-system": ["missing system"],
    "the-rear-view-mirror-problem": ["rear-view mirror", "rear view mirror"],
    "the-validation-loop": ["flag, don't guess", "flag don't guess", "validation loop"],
    "model-driven-data-quality": ["data quality", "plausibility check", "plausibility checks"],
    "deterministic-sql-generation": ["deterministic sql"],
    "business-friendly-metadata": ["business-friendly metadata"],
}


def _norm_reflist(v) -> list:
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def _load_concept_map() -> tuple:
    """(list of (name, slug, pattern), dict slug->name) from MDDE concepts.html.

    Reads the per-concept anchor ids (id="<slug>") + their c-name. Includes
    curated synonyms (case-insensitive). Empty if concepts.html isn't built.
    """
    idx = HERE / "concepts.html"
    if not idx.exists():
        return [], {}
    txt = idx.read_text(encoding="utf-8")
    pairs = re.findall(r'id="([a-z0-9-]+)"[^>]*>\s*<div class="c-name">([^<]+)</div>', txt)
    names = {}
    for slug, raw in pairs:
        names.setdefault(slug, html.unescape(raw).strip())
    valid = set(names)
    syn = [(slug, phrase) for slug, ph in CONCEPT_SYNONYMS.items() if slug in valid for phrase in ph]
    out = []
    for is_syn, (slug, raw) in ([(False, p) for p in pairs] + [(True, p) for p in syn]):
        name = html.unescape(raw).strip()
        if len(name) < 3:
            continue
        flags = re.IGNORECASE if is_syn else 0
        out.append((name, slug, re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", flags)))
    out.sort(key=lambda t: len(t[0]), reverse=True)
    return out, names


def autolink_concepts(body: str, concept_map: list, self_slug: str) -> str:
    if not concept_map:
        return body
    linked, out_lines, in_code = set(), [], False
    for ln in body.split("\n"):
        st = ln.strip()
        if st.startswith("```"):
            in_code = not in_code
            out_lines.append(ln); continue
        if in_code or st.startswith(("#", ">", "[[figure:")):
            out_lines.append(ln); continue
        stash = []
        def _hold(m):
            stash.append(m.group(0)); return f"\x00{len(stash)-1}\x00"
        safe = re.sub(r"\[[^\]]+\]\([^)]+\)|`[^`]+`", _hold, ln)
        for name, slug, pat in concept_map:
            if slug in linked or slug == self_slug:
                continue
            m = pat.search(safe)
            if not m:
                continue
            safe = safe[:m.start()] + f"[{m.group(0)}]({CONCEPTS_PAGE}#{slug})" + safe[m.end():]
            linked.add(slug)
        safe = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], safe)
        out_lines.append(safe)
    return "\n".join(out_lines)


def build_related_section(meta: dict, article_titles: dict, concept_names: dict) -> str:
    rc = _norm_reflist(meta.get("related_concepts"))
    ra = _norm_reflist(meta.get("related_articles"))
    if not rc and not ra:
        return ""
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
                if aslug in article_titles:
                    lis.append(f'<li><a href="{html.escape(aslug, quote=True)}.html">{html.escape(article_titles[aslug])}</a></li>')
        if lis:
            blocks.append(f"<h3>Related writing</h3><ul>{''.join(lis)}</ul>")
    if not blocks:
        return ""
    return f'<aside class="article-related"><h2>Related</h2>{"".join(blocks)}</aside>'


def _article_titles() -> dict:
    titles = {}
    for slug in ARTICLES:
        src = ARTICLES_ROOT / slug / f"{slug}.md"
        if src.exists():
            meta, _ = split_frontmatter(src.read_text(encoding="utf-8"))
            titles[slug] = str(meta.get("title", slug)).strip().strip('"')
    return titles


def main() -> None:
    OUT.mkdir(exist_ok=True)
    article_titles = _article_titles()
    concept_map, concept_names = _load_concept_map()
    cards = []
    for slug in ARTICLES:
        folder = ARTICLES_ROOT / slug
        src = folder / f"{slug}.md"
        if not src.exists():
            print(f"  ! missing folder-note: {src}")
            continue
        copied = copy_assets(folder)
        meta, body = split_frontmatter(src.read_text(encoding="utf-8"))
        body = strip_private_sections(body)
        body = autolink_concepts(body, concept_map, slug)
        title = str(meta.get("title", slug)).strip().strip('"')
        subtitle = str(meta.get("subtitle", "")).strip().strip('"')
        created = str(meta.get("created", "")).strip().strip("'\"")
        date = f" · {created}" if created else ""
        canonical = f"{BASE_URL}/articles/{slug}.html"
        hi = str(meta.get("hero_image", "")).strip().strip("'\"")
        og_image = f"{BASE_URL}/assets/{hi}" if hi else OG_DEFAULT
        hero = ""
        if hi:
            cap = str(meta.get("hero_caption", "")).strip().strip("'\"")
            cap_html = f"<figcaption>{html.escape(cap)}</figcaption>" if cap else ""
            hero = (f'<figure class="graphic" style="margin-top:32px;">'
                    f'<img src="../assets/{hi}" alt="{html.escape(title, quote=True)}">{cap_html}</figure>')
        json_ld = build_jsonld(title, subtitle, canonical, og_image, created)
        (OUT / f"{slug}.html").write_text(PAGE.format(
            title=html.escape(title, quote=True),
            subtitle=html.escape(subtitle, quote=True),
            face=face_label(meta), date=date, hero=hero,
            canonical=canonical, og_image=og_image, json_ld=json_ld,
            nav=NAV, body=md_to_html(body) + build_related_section(meta, article_titles, concept_names),
        ), encoding="utf-8")
        print(f"  + articles/{slug}.html  ({copied} assets)")
        cards.append((created, title, subtitle, f"articles/{slug}.html"))

    inject_articles_list(cards)


def inject_articles_list(cards: list) -> None:
    """Inject the on-site article cards into articles.html between markers."""
    idx = HERE / "articles.html"
    if not idx.exists():
        return
    txt = idx.read_text(encoding="utf-8")
    start = "<!-- SITE-ARTICLES:START"
    end = "<!-- SITE-ARTICLES:END -->"
    i, j = txt.find(start), txt.find(end)
    if i == -1 or j == -1 or j < i:
        print("  ! articles.html: SITE-ARTICLES markers not found — on-site list NOT updated")
        return
    cards.sort(reverse=True)
    rows = []
    for _d, title, subtitle, href in cards:
        rows.append(
            f'        <div class="card">\n'
            f'          <h3><a href="{href}" style="color:inherit;text-decoration:none;">{html.escape(title)}</a></h3>\n'
            f'          <p class="muted">{html.escape(subtitle)}</p>\n'
            f'          <p><a href="{href}">Read the full article →</a></p>\n'
            f'        </div>'
        )
    start_line_end = txt.find("-->", i) + len("-->")
    block = txt[i:start_line_end] + "\n" + "\n".join(rows) + "\n      " + end
    new = txt[:i] + block + txt[j + len(end):]
    if new != txt:
        idx.write_text(new, encoding="utf-8")
        print(f"  + articles.html (injected {len(cards)} on-site cards)")
    else:
        print("  = articles.html (cards already current)")


if __name__ == "__main__":
    main()
