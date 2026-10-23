@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller || goto :err

rmdir /s /q build 2>nul
del /q DeepSeekPet.spec 2>nul

pyinstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name DeepSeekPet ^
  --icon "assets\pet.ico" ^
  --add-data "assets;assets" ^
  "src\main.py" || goto :err

echo.
echo 打包完成: dist\DeepSeekPet.exe
goto :eof

:err
echo.
echo 打包失败，请检查上面的错误信息。
exit /b 1
