@echo off
REM ============================================================
REM  Mantem o ultima.CSV sempre fresco: gera o relatorio GPS no
REM  SIGLA a cada N minutos (assim o painel/site sempre tem dados
REM  recentes). Feche a janela para parar.
REM ============================================================
cd /d "%~dp0"
set SEG=300
:loop
echo [%date% %time%] Limpando instancias antigas do SIGLA...
taskkill /F /IM sigla.exe /T >nul 2>&1
echo [%date% %time%] Gerando relatorios (GPS + Atrasos)...
python sigla_gps.py
echo [%date% %time%] Garantindo que o SIGLA foi fechado...
taskkill /F /IM sigla.exe /T >nul 2>&1
echo Proxima geracao em %SEG% segundos (Ctrl+C para parar)...
timeout /t %SEG% /nobreak >nul
goto loop
