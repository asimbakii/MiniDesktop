@echo off
cd /d "%~dp0"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSPATH=%%i"
if not defined VSPATH (echo Visual Studio C++ araclari bulunamadi.& pause & exit /b 1)
call "%VSPATH%\VC\Auxiliary\Build\vcvars64.bat" >nul
cmake -S . -B build -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release || goto :err
cmake --build build || goto :err
echo.
echo Kopru derlendi: build\dcbridge.exe
exit /b 0
:err
echo Derleme basarisiz.
exit /b 1
