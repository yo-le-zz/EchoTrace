#!/usr/bin/env bash
# Build EchoTrace (Linux / macOS) avec cache. Options : voir `./build.sh --help`.
#   ./build.sh                 build incrémental (saute ce qui n'a pas changé)
#   ./build.sh --force         ignore le cache
#   ./build.sh --clean         supprime le cache et dist/
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv est introuvable. Installation : https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

# --no-project : le script n'a besoin que de la bibliothèque standard.
exec uv run --no-project python scripts/build.py "$@"
