# -*- coding: utf-8 -*-
"""
fila_prioridade.py - Arbitro de teclado/mouse entre as duas "pontes".

  - FLUXO (PonteWhats)        = ALTA  prioridade (envio de WhatsApp)
  - NEWS  (sigla_gps / GPS)   = BAIXA prioridade (relatorio no SIGLA)

Regra: quando o FLUXO esta enviando, o NEWS CEDE o teclado e espera.

O PonteWhats.exe NAO foi alterado. Como ele e compilado e nao avisa quando
usa o teclado, a deteccao de "Fluxo ativo" e feita observando a janela em
PRIMEIRO PLANO: ao enviar, a Ponte abre o WhatsApp Web, cujo titulo contem
"whatsapp". Esse e exatamente o instante em que o NEWS precisa parar. Como a
Ponte espera ~15s entre abrir o WhatsApp e digitar, o NEWS tem margem de
sobra para pausar antes de qualquer colisao.

Tambem ha um sinal EXPLICITO opcional (arquivo de flag). Se um dia voce
quiser coordenacao deterministica, basta envolver o envio no ponte.py com:

    import fila_prioridade as fila
    with fila.fluxo_ocupado():
        ...  # codigo que usa teclado/mouse

Sem dependencias externas (usa apenas ctypes, no Windows).
"""
import os
import sys
import time
import tempfile

EH_WINDOWS = sys.platform.startswith("win")

# Palavra(s) que aparecem no TITULO da janela quando a Ponte esta enviando.
PALAVRAS_FLUXO = ("whatsapp",)


def _dir_estado():
    d = os.path.join(tempfile.gettempdir(), "fila_prioridade_cardnews")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


FLAG_FLUXO = os.path.join(_dir_estado(), "fluxo_ocupado.flag")


# --------------------------------------------------------------------------
# Inspecao da janela em primeiro plano (Windows / ctypes)
# --------------------------------------------------------------------------
def _titulo_janela_frente():
    """Retorna o titulo da janela atualmente em primeiro plano ("" se nao der)."""
    if not EH_WINDOWS:
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value or ""
    except Exception:
        return ""


def fluxo_esta_ativo():
    """True se a Ponte (Fluxo) esta usando o teclado/mouse agora.

    Considera ativo se:
      - existe o flag explicito (caso o ponte.py seja integrado no futuro); ou
      - a janela em primeiro plano tem 'whatsapp' no titulo (envio em curso).
    """
    if os.path.exists(FLAG_FLUXO):
        return True
    titulo = _titulo_janela_frente().lower()
    return any(p in titulo for p in PALAVRAS_FLUXO)


def reativar_janela(titulo_alvo):
    """Traz para frente a primeira janela visivel cujo titulo contenha
    `titulo_alvo` (ex.: 'Coordenacao de Viagens'). Best-effort."""
    if not EH_WINDOWS or not titulo_alvo:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        alvo = titulo_alvo.lower()
        achados = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if alvo in (buf.value or "").lower():
                achados.append(hwnd)
                return False
            return True

        user32.EnumWindows(_cb, 0)
        if not achados:
            return False
        hwnd = achados[0]
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def aguardar_fluxo(reativar_titulo=None, timeout=120.0, intervalo=0.4, log=None):
    """Se o Fluxo estiver ativo, CEDE o teclado: bloqueia ate o Fluxo liberar
    (ou ate `timeout`). Ao retomar, opcionalmente re-foca a janela do SIGLA.

    Retorna sempre True (o chamador pode prosseguir). Se nada estiver ativo,
    retorna imediatamente.
    """
    if not fluxo_esta_ativo():
        return True

    if log:
        log("[fila] Fluxo (WhatsApp) ativo -> News cedendo o teclado e aguardando...")
    t0 = time.time()
    estourou = False
    while fluxo_esta_ativo():
        if time.time() - t0 > timeout:
            estourou = True
            break
        time.sleep(intervalo)

    if log:
        if estourou:
            log("[fila] AVISO: timeout (%.0fs) aguardando o Fluxo; prosseguindo." % timeout)
        else:
            log("[fila] Fluxo liberou o teclado -> News retomando.")

    # pequena folga + re-foco do SIGLA antes de continuar a digitar
    time.sleep(0.8)
    if reativar_titulo:
        reativar_janela(reativar_titulo)
        time.sleep(0.6)
    return True


# --------------------------------------------------------------------------
# Sinal EXPLICITO (opcional) - para uso FUTURO dentro do ponte.py
# --------------------------------------------------------------------------
class fluxo_ocupado:
    """Context manager para o lado do FLUXO marcar que esta usando o teclado.
    Uso futuro (no ponte.py):  with fila.fluxo_ocupado(): enviar(...)"""
    def __enter__(self):
        try:
            with open(FLAG_FLUXO, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        return self

    def __exit__(self, *_exc):
        try:
            os.remove(FLAG_FLUXO)
        except Exception:
            pass
        return False


if __name__ == "__main__":
    # Diagnostico rapido: mostra o titulo da janela em foco e se o Fluxo esta ativo.
    print("Plataforma Windows:", EH_WINDOWS)
    print("Dir de estado     :", _dir_estado())
    print("Janela em foco    :", repr(_titulo_janela_frente()))
    print("Fluxo ativo agora :", fluxo_esta_ativo())
