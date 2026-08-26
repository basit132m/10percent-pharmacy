# ArabSeed Download Manager

A WordPress plugin that lets you manage download links **from the admin panel**,
drop an SEO-friendly download button into any post, and route visitors through a
branded, redesigned countdown **download page** — replacing the old manual
`download-page/index.html`.

## What it does

| Piece | Where | What |
|---|---|---|
| **ArabSeed Download** meta box | Post/Page editor (sidebar) | Paste the real download link, an optional alternative link, a feature image, and a button label. |
| `[arabseed_download]` shortcode / block | Post content | Renders the download button. Uses the post's link automatically. |
| Managed download page | `/download/` | Redesigned countdown page. Same *count down → reveal button → redirect* logic as the original `index.html`. |
| Settings screen | Settings → ArabSeed Download | Brand name, logo, colours, countdown length, page slug, and page copy. |

## The flow

```
Post with [arabseed_download]
        │  visitor clicks the button
        ▼
Link saved to sessionStorage  ──►  /download/  (redesigned page)
                                        │  countdown (default 10s)
                                        ▼
                                   button revealed
                                        │  click
                                        ▼
                                 real download link
```

The link resolves in this order on the download page:
`sessionStorage` → URL fragment (`#u=…`, base64url — makes shared links work) →
the configured **Fallback URL**.

## Install

1. Copy the `arabseed-download-manager` folder into `wp-content/plugins/`.
2. Activate it in **Plugins**.
3. Open **Settings → ArabSeed Download**, set your brand/logo/colours, and save
   (saving refreshes the permalink for the `/download/` page).
4. Edit a post → fill the **ArabSeed Download** box → add the button:
   - Shortcode: `[arabseed_download]`
   - Or override the link inline: `[arabseed_download url="https://datadock-host.site/f/XXXX"]`
   - Or insert the **ArabSeed Download Button** block.

## Migrating from the old button

Your old markup used `data-download-url` + a hand-made `download-page/index.html`.
This plugin reproduces that behaviour with the same `arabseedDownloadURL`
sessionStorage key, so nothing about the visitor experience breaks — you just
manage the link in the editor instead of pasting HTML, and the page is served by
WordPress at `/download/`.

## SEO notes

- The download (gateway) page sends `noindex, nofollow` + `X-Robots-Tag`, so it
  never competes with your real content in search.
- Content pages get clean, semantic, crawlable button markup (real `<button>`
  elements, `aria-label`s, no layout-shifting inline junk).
- The download page is a lightweight standalone document (it skips the theme),
  so it loads fast and keeps a good Core Web Vitals profile.
