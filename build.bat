@echo off
setlocal
title Build Crosshair Crafter v1.0.1

cd /d "%~dp0"

echo Installing/updating build requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Cleaning old build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set ICON_ARG=
if exist assets\icon.ico set ICON_ARG=--icon assets\icon.ico

echo.
echo Building EXE...
python -m PyInstaller --noconfirm --clean --windowed --name "Crosshair Crafter" %ICON_ARG% --add-data "assets;assets" --add-data "settings;settings" --add-data "images;images" CrosshairCrafter.py

echo.
echo Done. Check the dist folder.
pause
