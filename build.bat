@echo off
rem Build EchoTrace (Windows) avec cache. Options : build.bat --help
rem   build.bat            build incremental (saute ce qui n'a pas change)
rem   build.bat --force    ignore le cache
rem   build.bat --clean    supprime le cache et dist\
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv est introuvable. Installation : https://docs.astral.sh/uv/getting-started/installation/ 1>&2
    exit /b 1
)

uv run --no-project python scripts\build.py %*
exit /b %errorlevel%
