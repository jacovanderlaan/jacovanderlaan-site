# WordPress-sync status — jacovanderlaan.com

> **Doel:** in één blik zien wat de live WordPress-site (jacovanderlaan.com, Annemarie's beheer) mist t.o.v. deze GitHub Pages-bron. Bron-van-waarheid = deze repo; WP = afgeleide. Zie plan `plan_website-sync-wordpress-strategie` + runbook `outbound-naar-annemarie` (ADR-063).
>
> **Kolommen:** _Pages-wijziging_ = laatste git-datum. _Doorgegeven_ = via welke outbound-zending (vNN) + datum. _WP-status_ = up-to-date / behind / **new** (bestaat nog niet op WP). _Actie_ = wat Annemarie moet doen.
>
> ⚠️ **Nog te bevestigen door Jaco/Annemarie:** de "Doorgegeven"- en "WP-status"-kolcommen zijn een eerste inschatting op basis van git — vul de echte WP-stand in.

## Sync-tabel (7 jul 2026)

| Pagina | Pages-wijziging | Doorgegeven | WP-status | Actie |
|---|---|---|---|---|
| **concepts.html** | 2026-07-04 | ❓ | **NEW** | Nieuwe named-concept-vocabulary-pagina (60+ concepten) — toevoegen aan WP |
| **expertise.html** | 2026-07-02 | ❓ | **NEW/behind** | Expertise-hub met "Deep dives" + dropdown — toevoegen/bijwerken |
| **expertise-data-modeling.html** | 2026-07-02 | ❓ | **NEW** | 6 expertise-subpagina's (30-jun) — nog niet op WP → toevoegen |
| **expertise-data-vault.html** | 2026-07-02 | ❓ | **NEW** | idem |
| **expertise-sql-migration.html** | 2026-07-02 | ❓ | **NEW** | idem |
| **expertise-diagram-generation.html** | 2026-07-02 | ❓ | **NEW** | idem |
| **expertise-modeling-tools.html** | 2026-07-02 | ❓ | **NEW** | idem |
| **expertise-engineering.html** | 2026-07-02 | ❓ | **NEW** | idem |
| **work.html** | 2026-07-07 | ❓ | **behind** | ⚠️ MDDE-meetup-framing correctie (overgedragen aan community) + ABN afgesloten — WP heeft mogelijk nog oude tekst |
| **about.html** | 2026-07-04 | ❓ | **behind** | ⚠️ MDDE-meetup-claim correctie + ABN-engagement beëindigd — WP mogelijk nog "founded and run the meetup" (fout) + ABN in heden-toon |
| **principles.html** | 2026-07-02 | ❓ | **NEW/behind** | Principles & manifesto-subpagina (27-jun) + concepts-nav |
| **mdde.html** | 2026-07-02 | ❓ | behind | MDDE-framework-pagina + concepts-nav |
| **services.html** | 2026-07-02 | v01/v03? | behind | transfer-by-design + demo-driven + engagement-model + concepts-nav |
| **references.html** | 2026-07-02 | ❓ | behind | concepts-nav |
| **ideas.html** | 2026-07-02 | ❓ | behind | concepts-nav |
| **approach.html** | 2026-07-02 | ❓ | behind | concepts-nav |
| **articles.html** | 2026-07-02 | ❓ | behind | concepts-nav |
| **index.html** | 2026-07-02 | v01? | behind | concepts-nav + evt. positionering |
| **contact.html** | 2026-07-02 | v01 | ~up-to-date? | e-mail/LinkedIn + form (mogelijk al ok) |

## Grootste gaten (prioriteit voor de volgende outbound-zending v05)
1. **6 expertise-subpagina's + expertise-hub** — geheel nieuw op WP, sterkste inhoudelijke uitbreiding.
2. **concepts.html** — nieuwe named-concept-pagina (60+ concepten).
3. **⚠️ work.html + about.html correcties** — MDDE-meetup "founded and run" is FOUT (overgedragen aan Harmen/community) + ABN in heden-toon terwijl beëindigd. Feitelijke onjuistheden → prioriteit voor correctie op WP.
4. **concepts-nav** op alle pagina's (dropdown "Concepts & vocabulary").

## Onderhoud van dit bestand
- Regenereer de Pages-wijziging-datums met: `for f in *.html; do git log -1 --format="%ad %s" --date=short -- "$f"; done`.
- Na een outbound-zending: vul "Doorgegeven" (vNN + datum) + zet WP-status op up-to-date wanneer Annemarie 't verwerkt heeft.
- Toekomst (spoor 3, plan): content-pagina's evt. via WP-API pushen i.p.v. handmatig — dan schrijft dat script deze tabel bij.
