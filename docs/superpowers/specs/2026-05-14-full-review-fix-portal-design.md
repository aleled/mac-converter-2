# MAC Address Converter — Full Review, Bug Fix, and Portal Design

**Date:** 2026-05-14
**Author:** Alejandro Lichtenfeld (with Claude)
**Branch:** `claude/eloquent-payne-7d7c9c` (worktree off `dev`)
**Project version at start:** v2.3.0

## Goal

Owner-level pass over the entire `mac-converter-2` repository: review every file, identify and fix real bugs, then publish a GitHub Pages download portal so end users have a clean place to grab the installer. The current state is production-ready, so this work hardens what exists rather than adding features.

## Scope

The work is decomposed into four phases, executed sequentially. Each phase is its own deliverable that the user reviews before the next phase begins.

| Phase | Deliverable | Decision gate |
|-------|-------------|---------------|
| 1. Audit | `docs/AUDIT-2026-05-14.md` committed to branch | User picks which findings to fix |
| 2. Fixes | One commit per finding (or grouped logically), tests where applicable | User reviews diff |
| 3. Installer | Touched only if Phase 1 finds installer-side issues | User reviews diff |
| 4. Portal | `docs/` directory (or `gh-pages` branch) serving a download page | User approves and enables GitHub Pages |

This spec covers Phases 1–4 at a design level. Each phase produces its own implementation plan via the `writing-plans` skill when it begins.

## Phase 1 — Audit

### Severity threshold

Per user direction: **real bugs and security only**. Findings must show wrong behavior, a crash path, a thread/concurrency hazard, a resource leak, or a security weakness.

Explicit non-findings (will not be reported as bugs):
- Style, naming, docstring coverage
- The 1,747-line size of `clipboard_hotkey.py` (a maintainability concern, separate from this audit)
- Test coverage gaps (already tracked in `TODO.md`)
- README/CHANGELOG prose quality

### Files in scope

All tracked files at the repository root:

- Python source: `clipboard_hotkey.py`, `mac_formats.py`, `oui_lookup.py`
- Build/distribution: `mac-converter.spec`, `installer.iss`, `requirements.txt`
- Environment: `env_load.ps1`, `env_load.sh`, `.gitignore`
- Documentation: `README.md`, `CHANGELOG.md`, `TODO.md`, `DEVELOPMENT_LOG.md`, `LICENSE.txt`

Out of scope: the `old/` archive directory, the `icon-v1.png` binary.

### Threat surface to inspect

These are the areas where bugs are most likely to hide. The auditor will read every file end-to-end but pay particular attention to:

1. **OUI download path** (`oui_lookup.py`): HTTPS verification, file size sanity check, atomic rename behavior on Windows, error message surfaces, timeout, retry behavior.
2. **Settings I/O** (`clipboard_hotkey.py`): JSON load/save atomicity, schema migrations, default-value fallback when keys are missing or malformed.
3. **Threading**: queue producer/consumer pairs, hotkey listener lifecycle, notification timer cancellation, OUI download thread vs main Qt thread, popup replacement race conditions.
4. **Hotkey parsing**: pynput input validation, behavior with invalid hotkey strings from settings.
5. **Clipboard handling**: behavior with non-text clipboard content, very long strings, locked clipboard.
6. **Format conversion** (`mac_formats.py`): regex correctness, edge cases on the README-vs-code mismatch already flagged.
7. **Installer** (`installer.iss`): privileges, file paths, uninstaller correctness, startup entry behavior.
8. **PyInstaller spec** (`mac-converter.spec`): hidden imports completeness, data files, icon embedding.

### Audit report format

The report is a single Markdown file at `docs/AUDIT-2026-05-14.md`. Structure:

```markdown
# MAC Address Converter — Security & Bug Audit (2026-05-14)

## Summary
- N findings: X critical, Y high, Z medium, W low
- Files reviewed: <list>

## Findings

### F1 [CRITICAL] One-line title
- **File:** path/to/file.py:line-range
- **What:** Description of the observable bug or weakness
- **Why it's a bug:** Reasoning, including the trigger condition
- **Proposed fix:** Concrete remediation
- **Effort:** S | M | L

(repeated for each finding)

## Non-findings
Brief list of areas inspected that were OK, so the user knows coverage was real.
```

Severities:
- **Critical** — data loss, remote code execution, or persistent app failure
- **High** — crash or wrong result on a common path
- **Medium** — wrong behavior in edge cases, or latent bug behind unlikely input
- **Low** — defensive hardening, robustness improvement

### Phase 1 deliverable

One commit on `claude/eloquent-payne-7d7c9c`: add `docs/AUDIT-2026-05-14.md`. No source code changes. No GitHub issues opened. User reviews and selects which findings move to Phase 2.

## Phase 2 — Bug fixes

Triggered after Phase 1 approval. For each finding the user picks:

- Create a fix per finding (or group obviously-related findings into one commit).
- Where the fix touches pure logic in `mac_formats.py` or `oui_lookup.py`, add a regression test under a new `tests/` directory using `pytest`. Set up minimal `pytest` config; existing `requirements.txt` does not include test dependencies, so add a `requirements-dev.txt`.
- UI-level fixes in `clipboard_hotkey.py` will be manually verified (start the app, exercise the flow) — there's no Qt test harness in the repo and adding one is out of scope.
- Update `CHANGELOG.md` under a new `[Unreleased]` section as fixes land.
- Bump version only if Phase 2 produces a user-visible behavior change worth releasing; otherwise version bump is deferred to Phase 4.

Phase 2 deliverable: one or more commits on the branch, all green where tests apply. User reviews diff before merge.

## Phase 3 — Installer (conditional)

Only executed if Phase 1 finds installer-side bugs (e.g., uninstaller leaves files, startup entry malfunctions, version mismatches between `installer.iss` and the executable).

If no installer findings, this phase is skipped and a note added to the audit report stating the installer was reviewed and is sound.

If executed: changes are confined to `installer.iss`, `mac-converter.spec`, and possibly a `BUILDING.md` if build steps need clarification. No rewrite to a different installer technology.

## Phase 4 — GitHub Pages download portal

A static HTML page served from GitHub Pages so end users have a public URL to download the latest release without navigating the GitHub UI.

### Goals

- A single-page site at `https://aleled.github.io/mac-converter-2/` (assuming default Pages domain).
- Shows: app name, one-line description, the screenshot/icon, "Download for Windows" primary button, version label, system requirements, link to source on GitHub, MIT license note.
- Pulls the latest release asset URL via the GitHub Releases API at page load (no rebuild needed when a new version ships).
- No build tooling: hand-written `index.html` + `styles.css`. No React, no static site generator, no npm.

### Hosting layout

Two options to be decided when Phase 4 starts:

- **`docs/` folder on `main`/`dev`** — GitHub Pages serves `/docs` of the default branch. Simplest, lives next to the code, no separate branch to maintain.
- **Dedicated `gh-pages` branch** — Pages serves the branch root. Keeps portal HTML out of the main tree but requires branch maintenance.

Recommendation at design time: `docs/` folder, because the repo is small and there is no reason to fork a maintenance branch.

### Visual design

Reuse the existing `icon-v1.png` and the dark theme palette already in the app (`#2b2b2b` background, `#0078d4` accent). The portal should feel like the same product, not a stock landing page. Final visual treatment is brainstormed at the start of Phase 4.

### Phase 4 deliverable

- `docs/index.html`, `docs/styles.css`, `docs/icon-v1.png` (copied so the site is self-contained)
- A short README update with the portal URL
- Instructions to the user for the one-time GitHub Pages setup in repository settings
- No automated deployment workflow in this phase; if requested later, GitHub Pages already auto-deploys from `docs/`

## Non-goals (for the entire engagement)

- New app features
- Refactoring `clipboard_hotkey.py` into smaller modules
- macOS or Linux support beyond what already exists
- CI/CD workflows
- Automated release pipeline
- Code signing the installer
- Localization
- Replacing PyQt5 with PyQt6 or PySide

## Open questions deferred to phase start

These are decided when the relevant phase begins, not now:

- Phase 2: do we add `pytest` and a `tests/` directory, or test ad-hoc?
- Phase 4: `docs/` folder vs `gh-pages` branch; copy assets vs CDN; light/dark mode toggle on the portal.

## Success criteria

- Phase 1 produces a committed audit report listing every real bug with file:line precision.
- Phase 2 commits fix every finding the user approved; tests pass where applicable; app still launches and the hotkey flow still works.
- Phase 4 produces a working GitHub Pages portal that auto-shows the latest release.
- The branch is in a state where the user can open a PR against `dev` with confidence.
