# jacovanderlaan.com — static site (light-premium)

Positioning-aligned rebuild. Plain HTML + one shared CSS — no build step, no framework, no dependencies. Fast, portable, host anywhere.

Blueprint: `D:/vault/personal/career/2-active/positioning/2026-06-23_website-blueprint-v2.md`

## Pages
- `index.html` — Home: the thesis in one screen + readiness filter + CTA ✅
- `approach.html` — the formula, the validation loop, proof in the life ✅
- `services.html` — value-framed engagements, no day-rate ✅
- `work.html` — proof / case studies *(to scaffold)*
- `writing.html` — curated index linking out to Medium/Substack/LinkedIn *(to scaffold)*
- `contact.html` — qualifying form (the readiness filter) *(to scaffold)*

## View locally
Just open `index.html` in a browser — no server needed. Or serve it:
```
cd /c/Repos/jacovanderlaan-site
python -m http.server 8080   # then open http://localhost:8080
```

## Deploy
Drag the folder to **Netlify** (netlify.com/drop) or push to a GitHub repo and enable **GitHub Pages**. Point the `jacovanderlaan.com` DNS at the host. No server, no maintenance.

## Edit
- Copy lives directly in the `.html` files (one `<section>` per block).
- All styling is in `css/style.css` — change `:root` variables to retheme.
- Infographics (SVG) are in `D:/vault/personal/learning/claude-usage/infographics/assets/2026-06-23_*.svg` — copy into `assets/` to embed.

## Brand
Light-premium: off-white bg, deep navy text, one royal-blue accent, gold for the payoff. Restraint = senior. Voice per `D:/vault/personal/career/preferences/ai-context/`.
