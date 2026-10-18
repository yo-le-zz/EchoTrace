@echo off
rem Build EchoTrace (Windows) avec cache incremental.
rem
rem Usage :
rem   build.bat            Build incremental
rem   build.bat --force    Ignore le cache
rem   build.bat --clean    Supprime le cache et dist\
rem   build.bat --help     Affiche l'aide
rem
rem La compilation Windows est realisee localement.
rem La compilation Linux/macOS doit etre effectuee sur un runner adapte.

setlocal
cd /d "%~dp0"

rem Verifier la presence de uv.
where uv >nul 2>nul
if errorlevel 1 (
    echo Erreur : uv est introuvable. 1>&2
    echo Installation : https://docs.astral.sh/uv/getting-started/installation/ 1>&2
    exit /b 1
)

rem Verifier la presence du script de build.
if not exist "scripts\build.py" (
    echo Erreur : scripts\build.py est introuvable. 1>&2
    exit /b 1
)

rem Executer le gestionnaire de build sans installer le projet lui-meme.
uv run --no-project python scripts\build.py %*
set "BUILD_EXIT_CODE=%errorlevel%"

exit /b %BUILD_EXIT_CODE%