# Download portal — operator instructions

This folder is the source of the public download portal at
**https://aleled.github.io/mac-converter-2/**.

The portal is plain static files (`index.html` + `styles.css` + `icon-v1.png`),
served by GitHub Pages straight from this `docs/` folder. No build step, no
CI workflow, no npm.

## One-time setup

1. Push the branch containing this folder to GitHub.
2. Go to the repo: <https://github.com/aleled/mac-converter-2>
3. Click **Settings** → **Pages** (in the left sidebar under "Code and automation").
4. Under **Build and deployment**:
   - **Source:** Deploy from a branch
   - **Branch:** `main` (or `dev` if you serve from dev) / `/docs`
5. Click **Save**.
6. Wait ~1 minute. GitHub will show "Your site is live at https://aleled.github.io/mac-converter-2/".

That's it. The page now auto-updates whenever you push changes to `docs/`.

## How the download button works

On every page load, `index.html` calls the GitHub Releases API:

```
https://api.github.com/repos/aleled/mac-converter-2/releases/latest
```

- If a release exists with a `.exe` asset, the button links straight to that
  installer and the version badge shows the tag (e.g. `v2.4.0`).
- If the release exists but has no `.exe` asset attached, the button links to
  the release page on GitHub instead of returning a 404.
- If no releases exist yet (e.g. before the first `v2.4.0` is published), the
  button shows "Coming soon — view on GitHub" and links to the repo root. The
  version badge shows `v2.4.0 pending release`.

So you can ship this folder before you cut the v2.4.0 release; the page just
shows "Coming soon" until you publish, then auto-updates on next load.

## Publishing a release (turning "Coming soon" into a real download)

1. Build the installer locally:
   ```
   pyinstaller mac-converter.spec
   "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
   ```
2. On GitHub, go to **Releases** → **Draft a new release**.
3. Tag: `v2.4.0` (must match the version in `installer.iss`).
4. Title: `v2.4.0 — bug-fix release`.
5. Description: paste the `[2.4.0]` section from `CHANGELOG.md`.
6. Attach `installer-output/MAC-Converter-Setup-v2.4.0.exe` as the release asset.
7. Publish.

Within ~30 seconds of publishing, the portal will auto-detect the release and
the "Coming soon" button will become a working "Download v2.4.0 for Windows"
link. No portal redeploy needed.

## Editing the portal

- Tagline, feature list, system requirements: edit `index.html` directly.
- Colors, layout, spacing: edit `styles.css`.
- Icon: replace `icon-v1.png` in this folder (same filename).

Push to the branch GitHub Pages is configured to serve and the change goes
live in ~1 minute.

## Files in this folder

| File | Purpose |
|------|---------|
| `index.html` | Single-page portal markup + inline JS |
| `styles.css` | Dark-theme stylesheet matching the app |
| `icon-v1.png` | App icon (copied from repo root) |
| `README.md` | This file (operator instructions) |
| `AUDIT-2026-05-14.md` | Phase 1 security audit (not served — GitHub Pages serves `index.html` by default) |
| `superpowers/` | Specs and implementation plans (not served — same reason) |

The `AUDIT-*.md` and `superpowers/` paths technically resolve as URLs on the
deployed site (e.g. `…/AUDIT-2026-05-14.md`), but they're not linked from
`index.html` so end users don't see them.
