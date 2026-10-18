# Development

## Setup

```bash
uv sync                    # runtime + dev dependencies (pytest, ruff)
uv run echotrace           # start the app
```

The old `uv.lock` was an empty placeholder: run `uv lock` once after pulling this layout.

## Checks

```bash
uv run pytest              # tests (offline, isolated through ECHOTRACE_HOME)
uv run ruff check src tests scripts
uv run ruff format src tests scripts
```

## Build

```bash
./build.sh                 # build.bat on Windows
```

`scripts/build.py` does the work (standard library only) and keeps a cache in `.build-cache/`:

1. **Dependencies**: hash of `pyproject.toml` + `uv.lock` + extras. `uv sync` is skipped when the hash
   matches and `.venv` exists.
2. **Build**: hash of every `src/**/*.py`, `echotrace.spec`, the dependency hash, the build mode and the
   platform. When it matches and the output exists, nothing is rebuilt. Otherwise tests run, then
   PyInstaller, reusing its work directory `.build-cache/pyinstaller` for a faster analysis.

| Option | Effect |
|---|---|
| `--force` | ignore the cache |
| `--clean` | delete `.build-cache/` and `dist/` |
| `--onefile` | single executable (slower to start) |
| `--with-image` | bundle OpenCV (face counting) |
| `--skip-tests` | do not run pytest first |
| `--archive` | also create a zip in `dist/` |

PyInstaller does not cross-compile: build on each target OS. Linux builds need the usual Qt
system libraries (`libxcb-cursor0` on Debian/Ubuntu).

## Conventions

- Code identifiers in English, code comments in French, user-facing documentation in English.
- Every module path that talks to the network goes through `echotrace.network`.
- New behaviour comes with a test; parsing and decision logic are kept in pure functions.
