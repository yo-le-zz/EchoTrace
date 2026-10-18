#!/usr/bin/env bash
# Build EchoTrace avec cache incrémental.
#
# Usage :
#   ./build.sh                 Build incrémental
#   ./build.sh --force         Ignore le cache
#   ./build.sh --clean         Supprime le cache et dist/
#   ./build.sh --help          Affiche l'aide
#
# La compilation Linux/macOS est réalisée localement.
# La compilation Windows doit être effectuée sur un runner Windows
# (par exemple via GitHub Actions).

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Vérifier la présence de uv.
if ! command -v uv >/dev/null 2>&1; then
    echo "Erreur : uv est introuvable." >&2
    echo "Installation : https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

# Vérifier la présence du script Python.
BUILD_SCRIPT="$ROOT_DIR/scripts/build.py"

if [[ ! -f "$BUILD_SCRIPT" ]]; then
    echo "Erreur : script de build introuvable : $BUILD_SCRIPT" >&2
    exit 1
fi

# Exécuter le gestionnaire de build sans installer le projet lui-même.
exec uv run --no-project python "$BUILD_SCRIPT" "$@"