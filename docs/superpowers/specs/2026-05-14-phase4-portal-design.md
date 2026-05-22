# Phase 4 — GitHub Pages Download Portal Design

**Date:** 2026-05-14
**Branch:** `claude/eloquent-payne-7d7c9c`
**Parent spec:** `docs/superpowers/specs/2026-05-14-full-review-fix-portal-design.md`
**Public URL (when published):** `https://aleled.github.io/mac-converter-2/`

## Goal

Single static page served from `/docs` on the default branch (GitHub Pages auto-serves), giving end users a friendly URL to download the latest Windows installer. Auto-fetches the release tag and exe URL via the GitHub Releases API on page load, so no rebuild is needed when a new version ships.

## Decisions

- **Hosting:** `docs/` folder on `dev`/`main`. GitHub Pages source set to "Branch: main, Folder: /docs" (or "/dev" if Pages serves from dev). One-time repo setting; no workflow file.
- **Pre-release behavior:** if `api.github.com/repos/aleled/mac-converter-2/releases/latest` returns 404 (no releases yet), the page shows "v2.4.0 release coming soon" and the primary CTA links to the GitHub repo root instead of an installer asset. When the release is published, the page auto-updates on next load.
- **No build tooling.** Hand-written `index.html` + `styles.css` + 30 lines of vanilla JS. No npm, no React, no static site generator.
- **Self-contained:** the app icon is copied into `docs/` so the portal doesn't depend on raw.githubusercontent URLs.
- **Style:** dark theme matching the app (`#2b2b2b` background, `#0078d4` accent, `#e0e0e0` body text). Single readable column max-width ~720px, generous whitespace, no animations beyond CSS hover states.

## Files

- `docs/index.html` — single page
- `docs/styles.css` — full stylesheet
- `docs/icon-v1.png` — copied from repo root
- `docs/README.md` — one-page operator instructions: how to enable GitHub Pages in the repo settings

## Page structure

```
[icon 128x128 centered]
[H1: MAC Address Converter]
[version badge: "v2.4.0" or "release pending"]
[tagline: "Lightweight Windows tray utility for converting MAC addresses between 10 formats — with a global hotkey, auto-cycling, and OUI vendor lookup."]

[primary button: "Download for Windows" → installer.exe, OR "Coming soon → View on GitHub"]

[Section: What it does]
- 10 MAC address format conversions, cycled by a configurable hotkey (default Alt+Shift+M)
- OUI vendor lookup against the IEEE database (~38,900 vendors)
- Runs from the system tray, no admin rights required
- Dark-themed Settings and About dialogs
- Optional autostart with Windows
- Settings persist between sessions

[Section: System requirements]
- Windows 7 or later (10/11 recommended)
- No admin rights required
- ~50 MB disk space

[Footer]
[link: View source on GitHub] · [text: MIT License · © 2026 Alejandro Lichtenfeld]
```

## JS behavior (one inline `<script>` tag, ≤30 lines)

```javascript
const REPO = 'aleled/mac-converter-2';
const FALLBACK_VERSION = '2.4.0';
fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(release => {
        const tag = release.tag_name; // e.g., "v2.4.0"
        const exe = (release.assets || []).find(a => a.name.endsWith('.exe'));
        document.querySelector('[data-version]').textContent = tag;
        const btn = document.querySelector('[data-download]');
        if (exe) {
            btn.href = exe.browser_download_url;
            btn.textContent = `Download ${tag} for Windows`;
        }
    })
    .catch(() => {
        document.querySelector('[data-version]').textContent = `v${FALLBACK_VERSION} pending release`;
        const btn = document.querySelector('[data-download]');
        btn.href = `https://github.com/${REPO}`;
        btn.textContent = 'Coming soon — view on GitHub';
    });
```

(Exact code may differ slightly to handle edge cases — e.g., assets with non-exe names — but the shape is fixed.)

## Out of scope

- Screenshots (no source asset; the icon alone is enough).
- Dark/light toggle, language selector, analytics, contact form, search.
- Custom domain or HTTPS configuration (GitHub Pages handles HTTPS automatically on the default `*.github.io` domain).
- Sitemap, robots.txt, Open Graph metadata beyond basic `<title>` and `<meta description>`.
- CI auto-deploy: GitHub Pages already auto-deploys whenever `docs/` changes on the configured branch.

## Success criteria

- The portal renders correctly when loaded with `file://` from the worktree (basic visual check before pushing).
- After enabling Pages in the repo settings, `https://aleled.github.io/mac-converter-2/` loads within ~1 minute.
- The version badge and download button auto-update when a GitHub Release is published.
- The page degrades gracefully when no releases exist yet.
- The page is readable on a phone (basic responsive design — `viewport` meta tag, fluid container).

## Deliverable

One commit on `claude/eloquent-payne-7d7c9c` adding the four files in `docs/`. The user then enables Pages once in repo settings per `docs/README.md` instructions.
