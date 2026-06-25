@echo off
REM ============================================================
REM  Mantem o ultima.CSV sempre fresco: gera o relatorio GPS no
REM  SIGLA a cada N minutos (assim o painel/site sempre tem dados
REM  recentes). Feche a janela para parar.
REM ============================================================
cd /d "%~dp0"
set SEG=1800
:loop
echo [%date% %time%] Gerando relatorio GPS...
python sigla_gps.py
echo Proxima geracao em %SEG% segundos (Ctrl+C para parar)...
timeout /t %SEG% /nobreak >nul
goto loop
