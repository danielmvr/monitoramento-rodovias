@echo off
REM ============================================================
REM  Loop UNICO de coleta (tudo em sequencia, nunca ao mesmo tempo):
REM   - GPS + Atrasos no SIGLA a cada ciclo (SEG segundos).
REM   - Noticias (Google News) a cada 3 ciclos (~15 min).
REM  Feche a janela para parar.
REM ============================================================
cd /d "%~dp0"
set SEG=900
set /a CICLO=0
:loop
set /a CICLO+=1
echo ============================================================
echo [%date% %time%] Ciclo %CICLO% - 1/2 Gerando GPS + Atrasos no SIGLA...
taskkill /F /IM sigla.exe /T >nul 2>&1
python sigla_gps.py
taskkill /F /IM sigla.exe /T >nul 2>&1
set /a NEWS=CICLO %% 3
if "%NEWS%"=="1" (
  echo [%date% %time%] Ciclo %CICLO% - 2/2 Coletando NOTICIAS [Google News]...
  python coletar_noticias.py
) else (
  echo [%date% %time%] Ciclo %CICLO% - 2/2 Noticias: pulado [coleta a cada ~15 min].
)
echo ------------------------------------------------------------
echo [%date% %time%] Ciclo %CICLO% concluido. Proximo em %SEG%s [Ctrl+C para parar]...
timeout /t %SEG% /nobreak
goto loop
