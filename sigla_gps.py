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
import sys
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


def fazer_login(cfg):
    login = cfg["login"]
    log.info("Login como %s", login.get("usuario", "?"))
    _trazer_sigla_frente(cfg)
    pyautogui.click(login["campo_usuario"]["x"], login["campo_usuario"]["y"])
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(login["usuario"], interval=0.03)
    pyautogui.click(login["campo_senha"]["x"], login["campo_senha"]["y"])
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite(login["senha"], interval=0.03)
    pyautogui.click(login["botao_login"]["x"], login["botao_login"]["y"])
    time.sleep(login.get("espera_apos_login_seg", 5))


# ---------- GERACAO DO RELATORIO (passos por teclado) ----------
def _subst(txt):
    """Substitui tokens dinamicos no texto dos passos."""
    agora = dt.datetime.now()
    return (str(txt)
            .replace("{hoje}", agora.strftime("%d/%m/%Y"))
            .replace("{hoje_digitos}", agora.strftime("%d%m%Y")))


def executar_passos(passos):
    """Executa a lista de passos (acoes de teclado/mouse) da config."""
    for i, st in enumerate(passos, 1):
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

    if not args.sem_login:
        abrir_sigla(cfg)
        fazer_login(cfg)

    time.sleep(float(gps.get("espera_inicial_seg", 2)))

    if not passos:
        log.warning("Nenhum passo definido em config.json -> gps.passos.")
        log.warning("Informe a sequencia de teclas para gerar/exportar o relatorio.")
        sys.exit(4)

    log.info("Executando %d passos de geracao do relatorio...", len(passos))
    executar_passos(passos)

    if destino:
        d = Path(destino)
        if d.exists():
            idade = time.time() - d.stat().st_mtime
            log.info("Arquivo destino OK: %s (atualizado ha %.0fs)", d, idade)
        else:
            log.warning("Arquivo destino nao encontrado apos os passos: %s", d)
    log.info("Concluido.")


if __name__ == "__main__":
    main()
