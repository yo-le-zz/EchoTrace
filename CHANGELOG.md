# Changelog

## 1.0.0

### Added
- Several usernames per target and automatic variants: separators and syllables (`yolezz` →
  `yo_le_zz`, `yo-le-zz`, `yole.zz`), prefixes/suffixes, leet. Wildcard mode (`yolezz.`) finds
  `yolezz.<word>` handles through search engines and a list of common suffixes.
- Several profile pictures per target; duplicates between them are reported.
- Profile verification (name, company, city, same picture, login-wall detection) that adjusts confidence.
- Two-pass username search, per-site request limits, live results while the analysis runs.
- Review of results: confirmed / to check / false positive (remembered per target) and notes;
  search, sort and multi-selection in the results table; exports of the selection.
- Compare two analyses (GUI and CLI), `echotrace-cli` (run, rescan, list, show, diff, purge...).
- Settings profiles (rapide, equilibre, complet, discret).
- Data protection: mandatory purpose per analysis (shown in reports), retention with automatic purge,
  export of all stored data, full erasure.
- Username sites in a JSON catalogue (`sites.json`) extendable by the user, plugin modules in the
  config folder, `scripts/check_sites.py` to detect sites that produce false positives.
- Exports HTML, JSON, CSV and PDF, plus a standalone correlation graph (dependency-free SVG).
- Stop button: a running analysis can be cancelled and keeps the results already found.
- History: reload past analyses with a double-click, delete an entry.
- Minimum-confidence filter in the results tab.
- Request cache (SQLite) actually used by the username module.
- `pyproject.toml` (uv), `build.sh` / `build.bat` with an incremental build cache, PyInstaller spec.
- Test suite, documentation (`docs/`) and a runnable example (`examples/`).

### Changed
- Project moved to a `src/echotrace/` package layout; run it with `uv run echotrace`.
- Settings, database, logs and exports now live in the per-user directories of each OS
  (override everything with `ECHOTRACE_HOME`). Files next to the code are no longer read;
  re-enter API keys once in the configuration dialog.
- TLS certificates are now verified (certifi); response bodies are size-capped.
- Image module: real perceptual hash and face counting (OpenCV is now the optional `image`
  extra). It no longer fabricates reverse-search matches; it provides links to open manually
  when the photo is a URL.
- Email module uses the HaveIBeenPwned v3 API (API key required).
- Search-based modules only report a page when the email / phone actually appears in it.
- Variations of a username are limited, valid in a URL, and score lower than the exact name.

### Fixed
- JSON report crashed (`self_dir`), HTML report was open to injection from scraped titles.
- Opening links from the results used the text of the cell (with a status emoji) instead of the URL.
- The URL filter froze the interface without filtering anything.
- SQLite connections were never closed; `unixepoch()` required SQLite 3.38+.
- French numbers written with 9 digits were normalised incorrectly.
- Removed the HaveIBeenPwned entry of the username list (always a false positive).
- Removed unused dependencies (requests, lxml, matplotlib, networkx, pyvis, opencv by default).
