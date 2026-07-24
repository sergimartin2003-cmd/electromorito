@echo off
REM Lanzador para Windows (doble clic o desde la consola).
REM La primera vez crea el entorno e instala todo; despues solo ejecuta.
REM Uso:  run.bat --pisos pisos.csv    (analiza un fichero)
REM       run.bat --web                (interfaz web local)
cd /d "%~dp0"

if not exist venv (
  echo Creando entorno virtual ^(solo la primera vez^)...
  python -m venv venv
  call venv\Scripts\python.exe -m pip install --upgrade pip
  call venv\Scripts\pip.exe install -r requirements.txt
)

call venv\Scripts\python.exe run.py %*
echo.
pause
