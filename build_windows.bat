@echo off
setlocal
set APP=MabuiETool
python -m pip install pyinstaller PySide6 pyusb pyserial pycryptodome colorama mock
python -m PyInstaller --noconfirm --clean --onedir --name %APP% --windowed ^
  --add-data "mabuietool\resources;mabuietool\resources" ^
  --add-data "mtkclient\Loader;mtkclient\Loader" ^
  --add-data "mtkclient\payloads;mtkclient\payloads" ^
  --add-data "mtkclient\gui\images;mtkclient\gui\images" ^
  --add-data "spd_gui;spd_gui" ^
  --hidden-import PySide6.QtSvg ^
  mabuietool\__main__.py
if errorlevel 1 exit /b %errorlevel%
echo Built dist\%APP%\%APP%.exe
echo Validate the onedir build before creating a onefile executable.
endlocal
