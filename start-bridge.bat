@echo off
REM One-click start for the photo bridge. Keep this window open while sending.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting up. This takes a minute...
    py -m venv .venv || goto :nopython
    .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    .venv\Scripts\python.exe -m pip install --quiet -e .
)

if not exist "photos" mkdir "photos"
.venv\Scripts\python.exe -m iphone_tk bridge --inbox "%~dp0photos"
goto :end

:nopython
echo.
echo Python is not installed. Get it from https://python.org/downloads
echo During install, tick "Add Python to PATH".
echo.
pause

:end
pause
