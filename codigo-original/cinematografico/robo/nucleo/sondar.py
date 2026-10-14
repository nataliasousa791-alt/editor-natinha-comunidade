"""Sonda o bruto: metadados, orientação REAL (testa 4 rotações com detector de rosto) e posição/tamanho do rosto.
Nada é medido à mão: tudo sai daqui para o job."""
import subprocess
import numpy as np
from .util import probe

ROT = {0: None, 90: "transpose=1", 270: "transpose=2", 180: "hflip,vflip"}


def _quadro(src, t):
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=-2:540",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    import cv2
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None


def _girar(img, graus):
    import cv2
    return {0: img, 90: cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), 270: cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE),
            180: cv2.rotate(img, cv2.ROTATE_180)}[graus]


def sondar(src, ini, fim, log):
    import cv2
    info = probe(src)
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    tempos = list(np.linspace(ini + 1, max(ini + 1.5, fim - 1), 8))
    quadros = [q for q in (_quadro(src, t) for t in tempos) if q is not None]
    olho = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    rostos, notas = {}, {}
    for g in (0, 90, 270, 180):
        achados, nota = [], 0.0
        for q in quadros:
            im = _girar(q, g); h, w = im.shape[:2]
            cinza = cv2.equalizeHist(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
            f, _, pes = cas.detectMultiScale3(cinza, 1.1, 6, minSize=(int(min(w, h) * 0.12),) * 2, outputRejectLevels=True)
            if len(f) == 0: continue
            k = int(np.argmax(np.ravel(pes))); x, y, fw, fh = f[k]; peso = float(np.ravel(pes)[k])
            topo = cinza[y:y + fh // 2, x:x + fw]                       # olhos na metade de CIMA = rosto em pé
            olhos = olho.detectMultiScale(topo, 1.1, 4, minSize=(max(8, fw // 10),) * 2) if topo.size else []
            nota += peso * (1.0 if len(olhos) else 0.25)
            achados.append(((x + fw / 2) / w, (y + fh / 2) / h, fh / h, fw / w))
        rostos[g], notas[g] = achados, round(nota, 2)
        log(f"orientação {g}°: rosto em {len(achados)}/{len(quadros)} quadros, nota {notas[g]}")
    melhor = max(notas, key=lambda g: (notas[g], -g))
    a = rostos[melhor]
    if a:
        cx, cy, fh, fw = (float(np.median([r[i] for r in a])) for i in range(4))
    else:
        cx, cy, fh, fw = 0.5, 0.4, 0.3, 0.2
        log("AVISO: nenhum rosto detectado; enquadramento central")
    larg, alt = (info["h"], info["w"]) if melhor in (90, 270) else (info["w"], info["h"])
    if info["rot"] in (90, -90, 270, -270) and melhor in (0, 180):   # ffmpeg já autogira pela metadata
        larg, alt = info["h"], info["w"]
    try:
        n, d = (int(x) for x in info["sar"].split(":"))
        sar = n / d if n and d else 1.0
    except Exception:
        sar = 1.0
    return dict(bruto=info, giro=melhor, filtro_giro=ROT[melhor], sar=sar, largura=larg, altura=alt,
                rosto=dict(cx=round(cx, 4), cy=round(cy, 4), h=round(fh, 4), w=round(fw, 4), amostras=len(a)))
