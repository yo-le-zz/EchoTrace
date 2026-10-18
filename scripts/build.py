#!/usr/bin/env python3
"""Build PyInstaller d'EchoTrace avec cache, identique sur Windows, Linux et macOS.

Le cache vit dans `.build-cache/` :
  - state.json    : empreintes des dépendances et des sources du dernier build réussi ;
  - pyinstaller/  : dossier de travail de PyInstaller, réutilisé pour accélérer l'analyse.

Deux étapes sont sautées quand rien n'a changé :
  1. `uv sync`   si pyproject.toml et uv.lock sont identiques et que .venv existe ;
  2. PyInstaller si les sources, la spec, les dépendances et les options sont identiques
     et que le résultat existe déjà.

Ce script n'utilise que la bibliothèque standard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build-cache"
STATE = CACHE / "state.json"
DIST = ROOT / "dist"
SPEC = ROOT / "echotrace.spec"
APP_NAME = "EchoTrace"


def digest(paths: list[Path], extra: str = "") -> str:
    """SHA-256 stable du contenu (et des noms relatifs) d'une liste de fichiers."""
    sha = hashlib.sha256(extra.encode())
    for path in sorted(paths):
        if path.is_file():
            sha.update(path.relative_to(ROOT).as_posix().encode())
            sha.update(path.read_bytes())
    return sha.hexdigest()


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    CACHE.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run(command: list[str], env: dict | None = None) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True, env={**os.environ, **(env or {})})


def artifact(onefile: bool) -> Path:
    if onefile:
        return DIST / (f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME)
    return DIST / (f"{APP_NAME}.app" if sys.platform == "darwin" else APP_NAME)


def make_archive(target: Path) -> None:
    name = f"{APP_NAME}-{sys.platform}-{platform.machine().lower()}"
    archive = shutil.make_archive(str(DIST / name), "zip", root_dir=DIST, base_dir=target.name)
    print(f"Archive : {archive}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile EchoTrace avec PyInstaller.")
    parser.add_argument("--force", action="store_true", help="ignore le cache et recompile")
    parser.add_argument("--clean", action="store_true", help="supprime le cache et dist/ puis quitte")
    parser.add_argument("--onefile", action="store_true", help="un seul exécutable (démarrage plus lent)")
    parser.add_argument("--with-image", action="store_true",
                        help="inclut la détection de visages (OpenCV, alourdit le binaire)")
    parser.add_argument("--skip-tests", action="store_true", help="ne lance pas pytest avant le build")
    parser.add_argument("--archive", action="store_true", help="crée une archive zip dans dist/")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(CACHE, ignore_errors=True)
        shutil.rmtree(DIST, ignore_errors=True)
        print("Cache et dist/ supprimés.")
        return 0

    if shutil.which("uv") is None:
        print("uv est introuvable : https://docs.astral.sh/uv/getting-started/installation/",
              file=sys.stderr)
        return 1

    state = {} if args.force else load_state()
    sync_args = ["--group", "build"] + (["--extra", "image"] if args.with_image else [])

    # 1. Dépendances
    def deps_digest() -> str:
        return digest([ROOT / "pyproject.toml", ROOT / "uv.lock"], " ".join(sync_args))

    deps_hash = deps_digest()
    if state.get("deps") == deps_hash and (ROOT / ".venv").exists():
        print("Dépendances à jour (cache).")
    else:
        run(["uv", "sync", *sync_args])
        # uv sync peut créer ou réécrire uv.lock : l'empreinte se calcule après, sinon le
        # build suivant croirait que les dépendances ont changé.
        deps_hash = deps_digest()
        state["deps"] = deps_hash
        save_state(state)

    # 2. Build
    sources = [*ROOT.joinpath("src").rglob("*.py"), SPEC]
    build_hash = digest(sources, f"{deps_hash}|{args.onefile}|{sys.platform}|{platform.machine()}")
    target = artifact(args.onefile)
    if state.get("build") == build_hash and target.exists():
        print(f"Build à jour (cache) : {target}")
        if args.archive:
            make_archive(target)
        return 0

    if not args.skip_tests:
        run(["uv", "run", "--no-sync", "pytest"])

    state.pop("build", None)  # un build interrompu ne doit pas passer pour valide
    save_state(state)
    run(
        ["uv", "run", "--no-sync", "pyinstaller", str(SPEC), "--noconfirm",
         "--workpath", str(CACHE / "pyinstaller"), "--distpath", str(DIST)],
        env={"ECHOTRACE_ONEFILE": "1" if args.onefile else "0"},
    )
    if not target.exists():
        print(f"Build terminé mais {target} est introuvable.", file=sys.stderr)
        return 1

    state["build"] = build_hash
    save_state(state)

    if args.archive:
        make_archive(target)

    print(f"Build terminé : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
