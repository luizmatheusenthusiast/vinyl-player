@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Criando o instalador do Vinyl Player para Windows
echo   (a primeira vez demora alguns minutos; pode deixar rodando)
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 goto :semPython

echo [1/4] Preparando o ambiente...
if not exist ".venv\Scripts\python.exe" (
    py -m venv .venv
    if errorlevel 1 goto :erro
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :erro

echo.
echo [2/4] Gerando o programa...
pyinstaller --noconfirm --clean --windowed --name "Vinyl Player" --icon "assets\icon.ico" --add-data "assets;assets" main.py
if errorlevel 1 goto :erro

echo.
echo [3/4] Procurando o Inno Setup (programa que cria o instalador)...
call :acharInno
if defined ISCC goto :criar
echo Inno Setup nao encontrado. Tentando instalar automaticamente...
winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
call :acharInno
if not defined ISCC goto :semInno

:criar
echo.
echo [4/4] Criando o instalador...
"%ISCC%" "installer\vinyl-player.iss"
if errorlevel 1 goto :erro

echo.
echo ============================================================
echo   PRONTO!
echo   Seu instalador esta em:  %~dp0Output\Vinyl-Player-Setup.exe
echo   Basta dar dois cliques nele para instalar (e pode enviar
echo   esse arquivo para qualquer pessoa).
echo ============================================================
explorer "%~dp0Output"
pause
exit /b 0

:acharInno
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0

:semPython
echo [ERRO] O Python nao foi encontrado.
echo.
echo 1. Baixe e instale em https://www.python.org/downloads/
echo 2. Na primeira tela da instalacao, MARQUE "Add python.exe to PATH".
echo 3. Depois de instalar, de dois cliques neste arquivo de novo.
echo.
pause
exit /b 1

:semInno
echo.
echo [AVISO] O programa ja foi gerado, mas falta o Inno Setup para criar o instalador.
echo.
echo 1. Baixe e instale o Inno Setup em https://jrsoftware.org/isdl.php
echo 2. Depois de instalar, de dois cliques neste arquivo de novo.
echo.
echo (Enquanto isso, voce ja pode usar o programa em: dist\Vinyl Player\Vinyl Player.exe)
echo.
pause
exit /b 1

:erro
echo.
echo [ERRO] Algo deu errado. Veja a mensagem acima.
echo Verifique se o computador esta conectado a internet e tente de novo.
echo.
pause
exit /b 1
