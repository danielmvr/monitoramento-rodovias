@echo off
REM ============================================================
REM  Coleta as noticias nesta maquina (IP residencial, que o
REM  Google News NAO bloqueia) a cada N minutos e salva o
REM  resultado na pasta do OneDrive (config.yaml -> noticias.arquivo).
REM  O painel na nuvem apenas LE esse arquivo. Feche a janela p/ parar.
REM ============================================================
cd /d "%~dp0"
set SEG=900
:loop
echo [%date% %time%] Coletando noticias...
python coletar_noticias.py
echo Proxima coleta em %SEG% segundos (Ctrl+C para parar)...
timeout /t %SEG% /nobreak >nul
goto loop
