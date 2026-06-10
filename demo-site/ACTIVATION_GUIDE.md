# Activating Smart Navigation on Any Website — Step-by-Step

This guide uses the **Lumo Travel demo site** (live at https://d6kupsfl5u4c6.cloudfront.net)
as the worked example. The same steps apply to any site.

---

## What you need

| Item | Where it comes from |
|---|---|
| `nav-widget.js` | One file, from this repo (`widget/nav-widget.js`) |
| API URL | The deployed brain: `https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com` |
| API key | Issued per site — stored in the Lambda's `API_KEYS` env var |

---

## Step 1 — Put the widget file on the site

Copy `widget/nav-widget.js` into the site's assets folder (e.g. `/assets/nav-widget.js`).
It is one self-contained file with zero dependencies.

## Step 2 — Add one line to every page

Paste this just before `</body>` (or in a shared layout/footer template so it
appears on all pages automatically):

```html
<script src="assets/nav-widget.js"
        data-api-url="https://3jz6sk8vt7.execute-api.eu-west-1.amazonaws.com"
        data-api-key="nav-9eadef81559f12263d150308a53b2975"
        data-placeholder="Ask anything... e.g. 'cancel my trip'"></script>
```

That's the installation. Done.

## Step 3 — Make sure the site is served over HTTPS

Voice search requires it (browsers block the microphone on plain HTTP).
Everything else works on HTTP too.

## Step 4 — Teach it the pages (pick one; both are zero-code)

**Option A — just browse (self-discovery, recommended).**
Open each page of the site once in a normal browser. The widget reads the
page's own title, headings and buttons and registers it with the brain
automatically. A 5-page site is fully indexed in under a minute of clicking.

**Option B — bulk seed (for large sites).**
POST the page list once to `/admin/index` — see `scripts/seed-index.sh`
for the template. Or point `/admin/crawl` at the site's `sitemap.xml`.

## Step 5 — Try it

- Press **Ctrl+K** on any page and type a question: *"where do I change my flight"*
- Or click the **microphone** and say it out loud
- Pick a result once — the engine remembers that phrasing and answers
  instantly next time. It gets smarter with every use, automatically.

---

## Quick checks if something looks wrong

| Symptom | Fix |
|---|---|
| Search box doesn't open | Script tag missing on that page, or JS console shows "API URL and key required" |
| "Authentication error" | Wrong/revoked `data-api-key` |
| Mic shows "access blocked" | Site is on HTTP — needs HTTPS |
| New page not found in search | Visit the page once in a browser (self-discovery), or seed it via Option B |

## Per-site configuration (optional script-tag attributes)

| Attribute | Default | What it does |
|---|---|---|
| `data-threshold` | `0.85` | Confidence needed to auto-navigate without a click |
| `data-hotkey` | `k` | Ctrl/Cmd + this key opens the palette |
| `data-voice-lang` | `en-ZA` | Speech recognition language |
| `data-base-path` | `""` | Prefix when the site lives under a sub-path |
| `data-discover` | `on` | Set `off` to disable self-discovery on a page |
| `data-cache-version` | `1` | Bump after a site restructure to clear visitors' local cache |

> **Note (current limitation):** all sites share one page index, so two sites
> must not use identical paths (e.g. both having `/index.html`). Per-site
> index separation is the next planned enhancement.
