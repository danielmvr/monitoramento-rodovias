"""
sigla_gps.py - Ponte para gerar o relatorio de ultimas posicoes (GPS) no SIGLA
e salva-lo na pasta consumida pelo painel (config.yaml -> frota.arquivo).

Reaproveita o LOGIN do sigla_automacao_v2.py (mesma abordagem pyautogui +
config.json). Da geracao em diante usa uma sequencia de passos por TECLADO,
definida em config.json -> "gps" -> "passos" (lista de acoes), para nao
depender de coordenadas frageis.

Uso:
    python sigla_gps.py                 # abre SIGLA, loga e executa os passos
    python sigla_gps.py --sem-login     # pula abrir/login (SIGLA ja aberto)

Requer (apenas na maquina local, Windows):
    pip install pyautogui pyperclip pygetwindow pyyaml

config.json (mesma estrutura de login do v2) + secao "gps":
{
  "login": {
    "executavel": "C:\\\\Sigla real - atualizado\\\\Coordenacao\\\\sigla.exe",
    "usuario": "SEU_USUARIO",
    "senha": "SUA_SENHA",
    "campo_usuario": {"x": 0, "y": 0},
    "campo_senha":   {"x": 0, "y": 0},
    "botao_login":   {"x": 0, "y": 0},
    "espera_apos_abrir_seg": 8,
    "espera_apos_login_seg": 5
  },
  "gps": {
    "destino": "C:\\\\Users\\\\cco\\\\OneDrive - Guanabara Diesel\\\\ultimaposicarros\\\\ultima.CSV",
    "espera_inicial_seg": 2,
    "passos": [
      {"acao": "hotkey", "teclas": ["alt", "r"]},
      {"acao": "sleep",  "seg": 2},
      {"acao": "press",  "tecla": "enter"},
      {"acao": "write",  "texto": "ultima"},
      {"acao": "colar",  "texto": "C:\\\\...\\\\ultima.CSV"}
    ]
  }
}

Acoes suportadas em "passos":
  hotkey  -> {"acao":"hotkey","teclas":["alt","r"]}
  press   -> {"acao":"press","tecla":"enter","vezes":1}
  write   -> {"acao":"write","texto":"...","intervalo":0.03}
  colar   -> {"acao":"colar","texto":"..."}     (usa a area de transferencia)
  click   -> {"acao":"click","x":123,"y":456}
  sleep   -> {"acao":"sleep","seg":2}
"""
import argparse
import json
import logging
import os
import sys
import threading
import time
import subprocess
import datetime as dt
from pathlib import Path

try:
    import pyautogui
except ImportError:
    print("[ERRO] Falta pyautogui. Rode: pip install pyautogui pyperclip pygetwindow")
    sys.exit(1)

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

# Fila de prioridade: cede o teclado ao FLUXO (PonteWhats) quando ele envia.
# Fallback gracioso: se o modulo nao existir, o script roda como antes.
try:
    import fila_prioridade as fila
except Exception:
    fila = None

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("SIGLA-GPS")

BASE = Path(__file__).resolve().parent
EXECUTAVEL_PADRAO = r"C:\Sigla real - atualizado\Coordenacao\sigla.exe"


def carregar_config(caminho="config.json"):
    p = Path(caminho)
    if not p.is_absolute():
        p = BASE / caminho
    if not p.exists():
        log.error("config.json nao encontrado em %s", p)
        log.error("Crie o config.json com a secao 'login' (mesma do v2) e 'gps'.")
        sys.exit(2)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------- LOGIN (igual ao sigla_automacao_v2.py) ----------
def _trazer_sigla_frente(cfg):
    """Garante que a janela de login do SIGLA esteja na frente do prompt.
    1) minimiza o console (cmd) para nao cobrir a tela do SIGLA;
    2) ativa a janela do SIGLA pelo titulo, se 'login.titulo_janela' definido.
    """
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)  # 6 = SW_MINIMIZE
    except Exception:
        pass
    titulo = (cfg.get("login", {}) or {}).get("titulo_janela", "")
    if titulo and gw is not None:
        try:
            for w in gw.getAllWindows():
                if titulo.lower() in (w.title or "").lower():
                    try:
                        w.minimize()
                        w.restore()
                    except Exception:
                        pass
                    try:
                        w.activate()
                    except Exception:
                        pass
                    break
        except Exception:
            pass
    time.sleep(0.6)


def abrir_sigla(cfg):
    exe = cfg.get("login", {}).get("executavel") or EXECUTAVEL_PADRAO
    if not Path(exe).exists():
        log.error("Executavel nao encontrado: %s", exe)
        sys.exit(3)
    log.info("Abrindo SIGLA: %s", exe)
    subprocess.Popen([exe], cwd=str(Path(exe).parent), shell=False)
    time.sleep(cfg.get("login", {}).get("espera_apos_abrir_seg", 8))


def _fechar_sigla(cfg):
    """Forca o encerramento de QUALQUER instancia do SIGLA (taskkill /F /T).
    Usado para limpar uma sessao travada antes de abrir, e para garantir o
    fechamento ao fim do ciclo, mesmo que os atalhos nao tenham completado."""
    exe = (cfg.get("login", {}) or {}).get("executavel") or EXECUTAVEL_PADRAO
    nome = Path(exe).name  # ex.: sigla.exe
    try:
        r = subprocess.run(["taskkill", "/F", "/IM", nome, "/T"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.info("SIGLA encerrado (taskkill /F %s).", nome)
        else:
            log.info("Nenhuma instancia de %s em execucao.", nome)
    except Exception as e:
        log.warning("Falha ao encerrar SIGLA (%s): %s", nome, e)


def _watchdog(cfg, segundos):
    """Rede de seguranca: apos 'segundos', mata o SIGLA e encerra o processo,
    para um travamento nao prender o loop do .bat indefinidamente."""
    def _stop():
        log.error("TIMEOUT (%ss): encerrando SIGLA e abortando o ciclo.", segundos)
        _fechar_sigla(cfg)
        os._exit(5)
    t = threading.Timer(float(segundos), _stop)
    t.daemon = True
    t.start()
    return t


def fazer_login(cfg):
    login = cfg["login"]
    titulo = login.get("titulo_janela", "")
    log.info("Login como %s", login.get("usuario", "?"))

    def _ceder():
        # Cede o teclado ao Fluxo (se ativo) e re-foca o SIGLA antes de continuar.
        if fila is not None:
            fila.aguardar_fluxo(reativar_titulo=titulo, log=log.info)

    _ceder()
    _trazer_sigla_frente(cfg)
    _ceder()
    pyautogui.click(login["campo_usuario"]["x"], login["campo_usuario"]["y"])
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(login["usuario"], interval=0.03)
    _ceder()
    pyautogui.click(login["campo_senha"]["x"], login["campo_senha"]["y"])
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(login["senha"], interval=0.03)
    _ceder()
    pyautogui.click(login["botao_login"]["x"], login["botao_login"]["y"])
    time.sleep(login.get("espera_apos_login_seg", 5))


# ---------- GERACAO DO RELATORIO (passos por teclado) ----------
def _subst(txt):
    """Substitui tokens dinamicos no texto dos passos."""
    agora = dt.datetime.now()
    return (str(txt)
            .replace("{hoje}", agora.strftime("%d/%m/%Y"))
            .replace("{hoje_digitos}", agora.strftime("%d%m%Y")))


def executar_passos(passos, titulo_sigla=None):
    """Executa a lista de passos (acoes de teclado/mouse) da config.

    Antes de CADA passo, cede o teclado ao FLUXO se ele estiver enviando
    (WhatsApp em primeiro plano) e re-foca o SIGLA ao retomar.
    """
    for i, st in enumerate(passos, 1):
        if fila is not None:
            fila.aguardar_fluxo(reativar_titulo=titulo_sigla, log=log.info)
        acao = (st.get("acao") or "").lower()
        log.info("Passo %d/%d: %s", i, len(passos), acao or st)
        if acao == "hotkey":
            pyautogui.hotkey(*[t.strip() for t in st.get("teclas", [])])
        elif acao == "press":
            for _ in range(int(st.get("vezes", 1))):
                pyautogui.press(st.get("tecla", ""))
                time.sleep(0.05)
        elif acao == "write":
            pyautogui.typewrite(_subst(st.get("texto", "")),
                                interval=float(st.get("intervalo", 0.03)))
        elif acao == "colar":
            if pyperclip is None:
                log.warning("pyperclip ausente; usando write no lugar de colar")
                pyautogui.typewrite(_subst(st.get("texto", "")), interval=0.02)
            else:
                pyperclip.copy(_subst(st.get("texto", "")))
                time.sleep(0.15)
                pyautogui.hotkey("ctrl", "v")
        elif acao == "click":
            pyautogui.click(int(st["x"]), int(st["y"]))
        elif acao == "sleep":
            time.sleep(float(st.get("seg", 1)))
        else:
            log.warning("Acao desconhecida ignorada: %r", st)
        time.sleep(float(st.get("apos_seg", 0.4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-login", action="store_true",
                    help="pula abrir/login (SIGLA ja aberto e logado)")
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    cfg = carregar_config(args.config)
    titulo_sigla = ((cfg.get("login") or {}).get("titulo_janela") or "")
    execu = cfg.get("execucao", {}) or {}
    timeout_seg = int(execu.get("timeout_seg", 600))
    fechar = (not args.sem_login) and (not args.nao_fechar) \
        and bool(execu.get("fechar_sigla", True))

    if fila is not None:
        log.info("Coordenacao de prioridade ATIVA: News cede o teclado ao Fluxo (WhatsApp) a cada passo.")
    else:
        log.warning("Coordenacao de prioridade INATIVA (fila_prioridade.py ausente): rodando SEM ceder ao Fluxo.")

    gps = cfg.get("gps")
    if not gps:
        fb = BASE / "gps_passos.json"
        if fb.exists():
            gps = json.loads(fb.read_text(encoding="utf-8"))
            log.info("Passos carregados de %s", fb.name)
        else:
            gps = {}
    passos = gps.get("passos", [])
    destino = gps.get("destino", "")

    atr = cfg.get("atrasos")
    if not atr:
        fa = BASE / "atrasos_passos.json"
        if fa.exists():
            atr = json.loads(fa.read_text(encoding="utf-8"))
            log.info("Passos de atrasos carregados de %s", fa.name)

    wd = None
    try:
        if not args.sem_login:
            # 1) limpa qualquer instancia travada de um ciclo anterior
            _fechar_sigla(cfg)
            time.sleep(2)
            # 2) watchdog: se algo congelar, mata o SIGLA e aborta o ciclo
            wd = _watchdog(cfg, timeout_seg)
            # 3) abre e loga
            if fila is not None:
                fila.aguardar_fluxo(reativar_titulo=titulo_sigla, log=log.info)
            abrir_sigla(cfg)
            fazer_login(cfg)

        time.sleep(float(gps.get("espera_inicial_seg", 2)))

        if not passos:
            log.warning("Nenhum passo de GPS definido (gps.passos / gps_passos.json).")
            return

        log.info("Executando %d passos de geracao do relatorio GPS...", len(passos))
        executar_passos(passos, titulo_sigla)
        if destino:
            d = Path(destino)
            if d.exists():
                log.info("GPS OK: %s (atualizado ha %.0fs)", d,
                         time.time() - d.stat().st_mtime)
            else:
                log.warning("GPS: destino nao encontrado apos os passos: %s", d)

        # segunda geracao na mesma sessao (SIGLA segue aberto): ATRASOS
        if atr and atr.get("passos"):
            time.sleep(float(atr.get("espera_inicial_seg", 1)))
            log.info("Gerando relatorio de ATRASOS (%d passos)...", len(atr["passos"]))
            executar_passos(atr["passos"], titulo_sigla)
            d2 = Path(atr.get("destino", ""))
            if atr.get("destino") and d2.exists():
                log.info("Atrasos OK: %s (atualizado ha %.0fs)", d2,
                         time.time() - d2.stat().st_mtime)
            elif atr.get("destino"):
                log.warning("Atrasos: destino nao encontrado apos os passos: %s", d2)
        else:
            log.info("Sem passos de atrasos (atrasos_passos.json ausente); pulado.")

        log.info("Concluido.")
    except Exception as e:  # noqa: BLE001
        log.error("Erro durante o ciclo: %s", e)
    finally:
        if wd is not None:
            wd.cancel()
        if fechar:
            _fechar_sigla(cfg)
        elif not args.sem_login:
            log.info("SIGLA mantido aberto (--nao-fechar ou execucao.fechar_sigla=false).")


if __name__ == "__main__":
    main()
