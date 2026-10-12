import cv2
import numpy as np
import mss
import json
import pyautogui
import threading
import time
import subprocess
import shutil

from flask import Flask, render_template_string
from flask_sock import Sock

try:
    import psutil
except ImportError:
    psutil = None

try:
    import GPUtil
except ImportError:
    GPUtil = None

app = Flask(__name__)
sock = Sock(app)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

MODO_ESCOLHIDO = 1
FPS_ALVO = 30
TEMPO_FRAME = 1.0 / FPS_ALVO
LARGURA = 800
ALTURA = 450
MONITOR_INDEX = 1

metricas = {
    "cpu": 0.0,
    "freq": 0.0,
    "ram": 0.0,
    "ram_livre": 0.0,
    "gpu_nome": "Detectando...",
    "gpu_uso": 0.0,
    "gpu_vram": 0.0,
    "gpu_temp": None,
    "gpu_ok": False,
    "status": "Iniciando"
}
lock = threading.Lock()


def detectar_gpu():
    dados = {
        "gpu_nome": "GPU indisponível",
        "gpu_uso": 0.0,
        "gpu_vram": 0.0,
        "gpu_temp": None,
        "gpu_ok": False
    }

    if GPUtil is not None:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                dados.update({
                    "gpu_nome": gpu.name,
                    "gpu_uso": float(gpu.load or 0) * 100,
                    "gpu_vram": float(gpu.memoryUtil or 0) * 100,
                    "gpu_temp": (
                        float(gpu.temperature)
                        if gpu.temperature is not None else None
                    ),
                    "gpu_ok": True
                })
                return dados
        except Exception as e:
            print("[GPU/GPUtil]", e)

    # Alternativa para placas NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            resultado = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,"
                    "memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits"
                ],
                stderr=subprocess.DEVNULL,
                timeout=2,
                creationflags=getattr(
                    subprocess, "CREATE_NO_WINDOW", 0
                )
            ).decode().strip().splitlines()[0]

            p = [x.strip() for x in resultado.split(",")]

            if len(p) >= 5:
                total = float(p[3])
                usada = float(p[2])

                dados.update({
                    "gpu_nome": p[0],
                    "gpu_uso": float(p[1]),
                    "gpu_vram": usada / total * 100 if total else 0,
                    "gpu_temp": float(p[4]),
                    "gpu_ok": True
                })
        except Exception as e:
            print("[GPU/NVIDIA]", e)

    return dados


def atualizar_metricas():
    if psutil:
        psutil.cpu_percent(interval=None)

    while True:
        try:
            novos = {}

            if psutil:
                novos["cpu"] = psutil.cpu_percent(interval=None)

                freq = psutil.cpu_freq()
                novos["freq"] = freq.current if freq else 0

                ram = psutil.virtual_memory()
                novos["ram"] = ram.percent
                novos["ram_livre"] = ram.available / (1024 ** 3)

            novos.update(detectar_gpu())
            novos["status"] = (
                "Monitoramento ativo"
                if novos.get("gpu_ok")
                else "CPU/RAM ativos; GPU indisponível"
            )

            with lock:
                metricas.update(novos)

        except Exception as e:
            print("[MÉTRICAS]", e)

        time.sleep(0.5)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>
body {
    margin:0; background:black; overflow:hidden;
    touch-action:none; user-select:none;
}
#screen {
    width: 100vw;
    height: 100vh;
    object-fit: contain;
    display: block;
}
#status {
    position:fixed; top:5px; left:5px;
    color:white; background:#222a;
    padding:5px; font:12px Arial;
}
</style>
</head>
<body>
<img id="screen" src="" draggable="false">
<div id="status">Conectando...</div>
<script>
const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
const ws = new WebSocket(proto + location.host + '/stream');
ws.binaryType = 'arraybuffer';

const img = document.getElementById('screen');
const status = document.getElementById('status');
let oldUrl = null;

ws.onopen = () => status.textContent = 'SP_Desk conectado';
ws.onclose = () => status.textContent = 'Desconectado';

ws.onmessage = e => {
    if (typeof e.data === 'string') return;
    const url = URL.createObjectURL(
        new Blob([e.data], {type:'image/jpeg'})
    );
    const previous = oldUrl;
    oldUrl = url;
    img.onload = () => {
        if (previous) URL.revokeObjectURL(previous);
    };
    img.src = url;
};

function send(action, e) {
    e.preventDefault();
    if (ws.readyState !== WebSocket.OPEN) return;

    const t = e.changedTouches?.[0] ||
              e.touches?.[0] || e;
    const r = img.getBoundingClientRect();

    const x = Math.max(0, Math.min(1, (t.clientX-r.left)/r.width));
    const y = Math.max(0, Math.min(1, (t.clientY-r.top)/r.height));

    ws.send(JSON.stringify({action, x, y}));
}

img.addEventListener('touchstart', e => send('down',e), {passive:false});
img.addEventListener('touchmove', e => send('move',e), {passive:false});
img.addEventListener('touchend', e => send('up',e), {passive:false});
img.addEventListener('touchcancel', e => send('up',e), {passive:false});

img.addEventListener('mousedown', e => send('down',e));
img.addEventListener('mousemove', e => {
    if (e.buttons === 1) send('move',e);
});
img.addEventListener('mouseup', e => send('up',e));
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


def desenhar_dashboard():
    img = np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)
    img[:] = (18, 20, 28)

    with lock:
        d = metricas.copy()

    branco = (240, 240, 240)
    cinza = (150, 155, 165)
    verde = (0, 230, 100)
    azul = (255, 160, 50)
    roxo = (220, 80, 220)

    def texto(s, pos, escala=0.65, cor=branco, esp=1):
        cv2.putText(
            img, str(s), pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            escala, cor, esp, cv2.LINE_AA
        )

    def barra(x, y, valor, cor):
        valor = float(np.clip(valor, 0, 100))
        cv2.rectangle(img, (x,y), (x+300,y+12), (45,45,55), -1)
        largura = int(valor * 3)
        if largura:
            cv2.rectangle(
                img, (x,y), (x+largura,y+12), cor, -1
            )

    texto("SP_DESK | MONITORAMENTO", (30, 40), 0.8, (0,255,255), 2)
    cv2.line(img, (30,55), (770,55), (65,70,85), 1)

    texto("CPU", (40,95), 0.7, azul, 2)
    texto(f"Uso: {d['cpu']:.1f}%", (40,130))
    texto(f"Clock: {d['freq']:.0f} MHz", (40,160), 0.55, cinza)
    barra(40,175,d["cpu"],verde)

    texto("MEMORIA RAM", (40,235), 0.7, azul, 2)
    texto(f"Uso: {d['ram']:.1f}%", (40,270))
    texto(f"Livre: {d['ram_livre']:.1f} GB", (40,300), 0.55, cinza)
    barra(40,315,d["ram"],azul)

    texto("GPU", (420,95), 0.7, verde, 2)
    texto(d["gpu_nome"][:30], (420,125), 0.48, cinza)

    if d["gpu_ok"]:
        texto(f"Uso: {d['gpu_uso']:.1f}%", (420,165))
        barra(420,180,d["gpu_uso"],verde)

        texto(f"VRAM: {d['gpu_vram']:.1f}%", (420,225))
        barra(420,240,d["gpu_vram"],roxo)
    else:
        texto("Metricas indisponiveis", (420,165), 0.5, cinza)

    if d["gpu_temp"] is not None:
        texto(f"Temperatura: {d['gpu_temp']:.0f} C", (420,290))
    else:
        texto("Temperatura: N/D", (420,290), 0.6, cinza)

    cv2.line(img, (30,375), (770,375), (65,70,85), 1)
    texto(d["status"], (35,410), 0.5, cinza)
    texto("30 FPS | SP_Desk", (630,435), 0.45, cinza)

    return img
@sock.route("/stream")
def stream(ws):
    botao = threading.Event()

    try:
        with mss.MSS() as sct:
            if len(sct.monitors) <= MONITOR_INDEX:
                print("[ERRO] Monitor não encontrado.")
                return

            monitor = sct.monitors[MONITOR_INDEX]
            mw = monitor["width"]
            mh = monitor["height"]

            def receber_touch():
                pressionado = False

                try:
                    while True:
                        data = ws.receive()
                        if not data:
                            break

                        msg = json.loads(data)

                        if MODO_ESCOLHIDO != 1:
                            continue

                        x = float(np.clip(msg["x"], 0, 1))
                        y = float(np.clip(msg["y"], 0, 1))

                        rx = monitor["left"] + min(int(x*mw), mw-1)
                        ry = monitor["top"] + min(int(y*mh), mh-1)

                        acao = msg.get("action")

                        if acao == "down":
                            pyautogui.moveTo(rx, ry)
                            pyautogui.mouseDown()
                            pressionado = True

                        elif acao == "move":
                            pyautogui.moveTo(rx, ry)

                        elif acao == "up":
                            pyautogui.moveTo(rx, ry)
                            if pressionado:
                                pyautogui.mouseUp()
                                pressionado = False

                except Exception as e:
                    print("[TOUCH]", e)

                finally:
                    if pressionado:
                        try:
                            pyautogui.mouseUp()
                        except Exception:
                            pass

            threading.Thread(
                target=receber_touch, daemon=True
            ).start()

            print(f"[STREAM] Modo {MODO_ESCOLHIDO}: cliente conectado")

            while True:
                inicio = time.perf_counter()

                try:
                    if MODO_ESCOLHIDO == 1:
                        captura = sct.grab(monitor)
                        frame = np.asarray(captura, dtype=np.uint8)

                        if len(frame.shape) == 3 and frame.shape[2] == 4:
                            frame = cv2.cvtColor(
                                frame, cv2.COLOR_BGRA2BGR
                            )

                        mx, my = pyautogui.position()

                        if (
                            monitor["left"] <= mx < monitor["left"]+mw
                            and monitor["top"] <= my < monitor["top"]+mh
                        ):
                            px = mx-monitor["left"]
                            py = my-monitor["top"]

                            cv2.drawMarker(
                                frame, (px,py), (0,0,0),
                                cv2.MARKER_TILTED_CROSS, 15, 3
                            )
                            cv2.drawMarker(
                                frame, (px,py), (255,255,255),
                                cv2.MARKER_TILTED_CROSS, 13, 1
                            )

                        frame = cv2.resize(
                            frame, (LARGURA,ALTURA),
                            interpolation=cv2.INTER_NEAREST
                        )
                    else:
                        frame = desenhar_dashboard()

                    ok, buffer = cv2.imencode(
                        ".jpg", frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY),45]
                    )

                    if ok:
                        ws.send(buffer.tobytes())

                    restante = TEMPO_FRAME - (
                        time.perf_counter()-inicio
                    )
                    if restante > 0:
                        time.sleep(restante)

                except Exception as e:
                    print("[STREAM] Cliente desconectado:", e)
                    break

    except Exception as e:
        print("[WEBSOCKET]", e)


def main():
    global MODO_ESCOLHIDO

    print("=" * 40)
    print("        SP_DESK INTEGRADO")
    print("=" * 40)
    print("1 - Tela estendida com touch")
    print("2 - Painel de hardware")

    try:
        escolha = input("Escolha o modo (1 ou 2): ").strip()
        MODO_ESCOLHIDO = 2 if escolha == "2" else 1
    except (EOFError, KeyboardInterrupt):
        MODO_ESCOLHIDO = 1

    threading.Thread(
        target=atualizar_metricas,
        daemon=True
    ).start()

    print(f"Modo ativo: {MODO_ESCOLHIDO}")
    print("Abra http://IP_DO_PC:5000 no tablet.")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("SP_Desk encerrado.")