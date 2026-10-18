# EchoTrace

Desktop OSINT correlation engine. Give it what you know about a target (usernames, email, phone,
name, profile pictures...), it checks public sources, scores every hit, reads the profiles it found
to look for supporting evidence, and exports the result as a report.

Works on Windows, Linux and macOS. Python 3.10+. GUI and command line.

## Responsible use

EchoTrace only queries **public** pages and search engines. It does not bypass protections, log in
to anything or access private data. It does not do facial recognition.

- A hit is a lead, not proof of identity. Namesakes and reused usernames are common: verify.
- Every analysis records its **purpose** (your own footprint, with the person's consent, professional
  check, journalism/research, protecting your rights) and the reports repeat it. Read
  [docs/privacy.md](docs/privacy.md): searching for a person processes personal data, GDPR applies.
- Do not use it to harass, stalk or profile people. Be gentle with the sites you query.

## Features

| Module | Needs | What it does |
|---|---|---|
| Username | `pseudo` | ~50 sites; several usernames; spelling variants (`yolezz` → `yo_le_zz`, `yo-le-zz`, `yole.zz`...); wildcard mode (`yolezz.` → `yolezz.secret`, `yolezz.dev`...) |
| Web search | name, username, email, company | Dork queries on Google, Bing and DuckDuckGo |
| Email | `email` | Known breaches (HaveIBeenPwned, API key required), provider/WHOIS lead, public mentions |
| Phone | `telephone` | Normalisation, country/line type, public mentions |
| Image | `photo` | Several photos; hashes, faces counted (optional), duplicates, reverse-search links for URLs |

Around the modules:

- **Profile verification**: found profiles are re-read; name / company / city in the page and a profile
  picture that is the *same image* as one of yours (file comparison, not face recognition) raise the
  confidence. Login walls are detected and cap it.
- **Live results**, two-pass search (variants first on fast reliable sites), per-site request limits.
- **Review**: mark results confirmed / to check / false positive (never proposed again for that
  target), add notes, search and sort the table.
- **History**: reload, compare two analyses, rescan from the CLI (exit code 3 when something new appears).
- **Exports**: HTML, JSON, CSV, PDF, SVG graph; selection of rows; false positives are never exported.
- **Settings**: profiles (rapide, equilibre, complet, discret), retention, API keys.
- **Extensible**: sites in a JSON file you can extend, plugin modules in your config folder.

## Install and run

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone <your-repository-url> echotrace
cd echotrace
uv sync                  # creates .venv and installs everything
uv run echotrace         # graphical interface
uv run echotrace-cli --help
```

Face counting needs OpenCV, which is optional because it is large: `uv sync --extra image`.
Without uv: `pip install .`.

## Usage

See [docs/usage.md](docs/usage.md) for the details (variants, wildcard, photos, review, CLI).

1. Fill in what you know. The score must reach **100 points** (configurable) with at least two fields.
2. Choose the **purpose** of the search, then **LANCER L'ANALYSE**. Results appear as each module ends.
3. Review them in **Résultats** (right click for status/notes), export, or compare analyses in **Historique**.

```bash
uv run echotrace-cli run --pseudo "yolezz" --pseudo "yolezz." --email me@example.org \
    --photo ~/me.jpg --purpose 1 --export html,json
uv run echotrace-cli rescan 3          # again, with a diff against the previous run
```

## Where files are stored

| What | Location |
|---|---|
| Settings (API keys), `sites.json`, `plugins/` | per-user config directory (`~/.config/EchoTrace`, `%APPDATA%\EchoTrace`, `~/Library/Application Support/EchoTrace`) |
| History and cache | per-user data directory |
| Logs | per-user log directory |
| Exports | `Documents/EchoTrace` (changeable in the settings) |

`ECHOTRACE_HOME=/some/folder` keeps everything in one folder (portable use, tests). Analyses older
than the retention period (90 days by default) are deleted at startup.

## Build an executable

```bash
./build.sh               # Linux / macOS     (build.bat on Windows)
./build.sh --onefile     # single file instead of a folder
./build.sh --force       # ignore the cache
```

The result is in `dist/`. Unchanged dependencies and sources are detected and skipped; see
[docs/development.md](docs/development.md).

## Documentation

- [Usage](docs/usage.md) · [Privacy and legal notes](docs/privacy.md)
- [Architecture](docs/architecture.md) · [Configuration](docs/configuration.md)
- [Writing a module or plugin](docs/modules.md) · [Development, tests and build](docs/development.md)
- [Changelog](CHANGELOG.md) · [Examples](examples/)

## License

MIT, see [LICENSE](LICENSE). Author: yolezz.
