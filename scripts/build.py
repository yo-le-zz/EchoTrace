
#!/usr/bin/env python3
"""Build EchoTrace avec Nuitka et cache incrémental.

Options :
  --force       Ignore le cache et recompile.
  --clean       Supprime le cache et dist/, puis quitte.
  --onefile     Produit un exécutable unique.
  --with-image  Active les dépendances optionnelles de détection d'images.
  --skip-tests  Ignore pytest.
  --archive     Crée une archive ZIP du résultat.

Le cache se trouve dans .build-cache/.
Les builds sont natifs : chaque système compile pour sa propre plateforme.
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
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build-cache"
STATE = CACHE / "state.json"
DIST = ROOT / "dist"
PYPROJECT = ROOT / "pyproject.toml"
APP_NAME = "EchoTrace"


def digest(paths: list[Path], extra: str = "") -> str:
    """Calcule une empreinte SHA-256 des fichiers et des options."""
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
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    """Exécute une commande et propage son code d'erreur."""
    print("$", subprocess.list2cmdline(command), flush=True)

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        env={**os.environ, **(env or {})},
    )


def read_project() -> dict:
    """Charge les métadonnées du projet."""
    with PYPROJECT.open("rb") as file:
        return tomllib.load(file)


def find_entrypoint(project: dict) -> tuple[Path | None, str | None]:
    """Détermine le point d'entrée depuis pyproject.toml ou src/."""
    scripts = project.get("project", {}).get("scripts", {})

    if scripts:
        preferred = next(
            (
                value
                for name, value in scripts.items()
                if name.lower().replace("-", "") == "echotrace"
            ),
            next(iter(scripts.values())),
        )

        module = preferred.split(":", 1)[0].strip()
        package = module.split(".", 1)[0]

        if not module or not package:
            raise ValueError(
                f"Point d'entrée invalide dans pyproject.toml : {preferred!r}"
            )

        return None, preferred

    source_dir = ROOT / "src"
    candidates = sorted(source_dir.glob("*/__main__.py"))

    if len(candidates) == 1:
        entrypoint = candidates[0]
        return entrypoint, None

    raise FileNotFoundError(
        "Point d'entrée introuvable.\n"
        "Déclare un script dans [project.scripts] de pyproject.toml, "
        "ou ajoute src/<package>/__main__.py."
    )


def artifact(onefile: bool) -> Path:
    """Renvoie le fichier ou dossier produit par Nuitka."""
    if onefile:
        filename = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
        return DIST / filename

    return DIST / f"{APP_NAME}.dist"


def executable_in(target: Path) -> Path:
    """Renvoie l'exécutable situé dans le dossier standalone."""
    filename = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
    return target / filename


def artifact_exists(target: Path, onefile: bool) -> bool:
    if onefile:
        return target.is_file()

    return target.is_dir() and executable_in(target).is_file()


def make_archive(target: Path) -> None:
    """Archive le résultat complet, y compris les dépendances."""
    name = (
        f"{APP_NAME}-{sys.platform}-{platform.machine().lower()}"
        f"{'-onefile' if target.is_file() else '-standalone'}"
    )

    archive = shutil.make_archive(
        str(DIST / name),
        "zip",
        root_dir=target.parent,
        base_dir=target.name,
    )

    print(f"Archive : {archive}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile EchoTrace avec Nuitka."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore le cache et recompile",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="supprime le cache et dist/, puis quitte",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="produit un exécutable unique",
    )
    parser.add_argument(
        "--with-image",
        action="store_true",
        help="inclut les dépendances optionnelles de détection d'images",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="ne lance pas pytest avant le build",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="crée une archive ZIP dans dist/",
    )
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(CACHE, ignore_errors=True)
        shutil.rmtree(DIST, ignore_errors=True)
        print("Cache et dist/ supprimés.")
        return 0

    if shutil.which("uv") is None:
        print(
            "uv est introuvable : "
            "https://docs.astral.sh/uv/getting-started/installation/",
            file=sys.stderr,
        )
        return 1

    try:
        project = read_project()
        entrypoint_file, entrypoint_script = find_entrypoint(project)
    except (OSError, ValueError, KeyError, FileNotFoundError) as error:
        print(f"Configuration du build invalide : {error}", file=sys.stderr)
        return 1

    state = {} if args.force else load_state()
    sync_args = ["--group", "build"]

    if args.with_image:
        sync_args.extend(["--extra", "image"])

    def deps_digest() -> str:
        return digest(
            [PYPROJECT, ROOT / "uv.lock"],
            " ".join(sync_args),
        )

    # 1. Synchronisation des dépendances.
    deps_hash = deps_digest()

    if state.get("deps") == deps_hash and (ROOT / ".venv").exists():
        print("Dépendances à jour (cache).")
    else:
        run(["uv", "sync", *sync_args])
        deps_hash = deps_digest()
        state["deps"] = deps_hash
        save_state(state)

    # 2. Préparation du point d'entrée.
    CACHE.mkdir(parents=True, exist_ok=True)

    if entrypoint_script:
        module, function = entrypoint_script.split(":", 1) if ":" in entrypoint_script else (
            entrypoint_script,
            "",
        )
        module = module.strip()
        function = function.strip().split("[", 1)[0]

        if not function:
            print(
                "Le script déclaré dans [project.scripts] doit préciser "
                "une fonction, par exemple echotrace = "
                '"echotrace.cli:main".',
                file=sys.stderr,
            )
            return 1

        package = module.split(".", 1)[0]
        launcher = CACHE / "launcher.py"
        launcher.write_text(
            f"from {module} import {function}\n"
            f"\n"
            f"if __name__ == '__main__':\n"
            f"    raise SystemExit({function}())\n",
            encoding="utf-8",
        )
        main_file = launcher
    else:
        assert entrypoint_file is not None
        package = entrypoint_file.parent.name
        main_file = entrypoint_file

    # 3. Empreinte des sources et des options.
    sources = list((ROOT / "src").rglob("*.py"))
    sources.extend(
        path
        for path in [PYPROJECT, ROOT / "uv.lock"]
        if path.is_file()
    )
    sources.append(main_file)

    build_options = (
        f"{deps_hash}|{args.onefile}|{args.with_image}|"
        f"{sys.platform}|{platform.machine()}|{sys.version_info[:3]}"
    )
    build_hash = digest(sources, build_options)
    target = artifact(args.onefile)

    if (
        not args.force
        and state.get("build") == build_hash
        and artifact_exists(target, args.onefile)
    ):
        print(f"Build à jour (cache) : {target}")

        if args.archive:
            make_archive(target)

        return 0

    # 4. Tests.
    if not args.skip_tests:
        run(["uv", "run", "--no-sync", "pytest"])

    # 5. Compilation Nuitka.
    # Invalider le cache avant la compilation : un build interrompu
    # ne doit jamais être considéré comme valide.
    state.pop("build", None)
    save_state(state)

    DIST.mkdir(parents=True, exist_ok=True)

    # Éviter qu'un ancien artefact soit pris pour le nouveau.
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()

    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "nuitka",
        "--mode=onefile" if args.onefile else "--mode=standalone",
        f"--output-dir={DIST}",
        f"--output-filename={APP_NAME}",
        f"--include-package={package}",
        str(main_file),
    ]

    if sys.platform == "darwin":
        command.append("--macos-create-app-bundle")

    try:
        run(command)
    except subprocess.CalledProcessError as error:
        print(
            f"Échec de la compilation Nuitka (code {error.returncode}).",
            file=sys.stderr,
        )
        return error.returncode or 1

    if not artifact_exists(target, args.onefile):
        print(
            f"Compilation terminée, mais l'artefact attendu est absent : {target}",
            file=sys.stderr,
        )
        return 1

    # 6. Enregistrer uniquement un build validé.
    state["build"] = build_hash
    save_state(state)

    if args.archive:
        make_archive(target)

    print(f"Build terminé : {target}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCompilation interrompue.", file=sys.stderr)
        sys.exit(130)
    except subprocess.CalledProcessError as error:
        print(
            f"Commande échouée (code {error.returncode}).",
            file=sys.stderr,
        )
        sys.exit(error.returncode or 1)
