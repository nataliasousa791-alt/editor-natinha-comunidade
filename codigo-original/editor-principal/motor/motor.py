#!/usr/bin/env python3
"""Motor de cenas: transforma uma RECEITA (JSON curto escrito por uma IA barata) em B-roll animado 9:16.

Uso: python3 motor.py receita.json saida.mp4
"""
import json, math, os, random, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
try:
    from . import icones
except ImportError:
    import icones

W, H, FPS = 1080, 1920, 30
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FF_LOCAL = os.path.join(_RAIZ, "ffmpeg", "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
FFMPEG = _FF_LOCAL if os.path.exists(_FF_LOCAL) else "ffmpeg"
FD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recursos", "fontes") + os.sep
CORES = {
    "tinta": (22, 15, 34), "creme": (246, 238, 227), "dourado": (242, 193, 78),
    "vermelho": (214, 58, 72), "cinza": (70, 58, 84), "lilas": (178, 150, 220), "branco": (255, 255, 255),
}
GOLD, CREAM, INK = CORES["dourado"], CORES["creme"], CORES["tinta"]
POS_X = {"esq": 280, "centro": 540, "dir": 800, "esq2": 170, "dir2": 910, "meio-esq": 410, "meio-dir": 670}
TAM = {"P": 260, "M": 400, "G": 560, "GG": 720}


# ------------------------------------------------------------------ utilidades
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, s, d):
    return clamp((t - s) / d) if d > 0 else float(t >= s)


def eio(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def eout(x):
    return 1 - (1 - x) ** 3


def eback(x, s=1.7):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def lerpc(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def font(nome, tam):
    return ImageFont.truetype(FD + nome, max(8, int(tam)))


def texto_espacado(d, cx, y, txt, fnt, fill, track=10):
    w = sum(fnt.getlength(c) for c in txt) + track * (len(txt) - 1)
    x = cx - w / 2
    for c in txt:
        d.text((x, y), c, font=fnt, fill=fill)
        x += fnt.getlength(c) + track


def grad(c1, c2, h):
    y = np.linspace(0, 1, h)[:, None]
    col = np.array(c1) * (1 - y) + np.array(c2) * y
    return np.repeat(col[:, None, :], W, axis=1).astype(np.float32)


# ------------------------------------------------------------------ fundos
FUNDOS = {
    "anoitecer": dict(ceu=[(20, 14, 40), (74, 44, 122), (198, 108, 132)], chao=[(40, 24, 52), (14, 10, 22)]),
    "noite": dict(ceu=[(8, 8, 22), (26, 18, 52), (60, 36, 92)], chao=[(22, 16, 34), (8, 6, 14)]),
    "por-do-sol": dict(ceu=[(28, 22, 52), (150, 70, 70), (250, 160, 80)], chao=[(70, 40, 34), (22, 14, 14)]),
    "parede": dict(ceu=[(150, 112, 190), (96, 70, 140), (96, 70, 140)], chao=[(18, 12, 28), (10, 8, 16)]),
    "raios": dict(ceu=[(30, 20, 54), (70, 40, 110), (70, 40, 110)], chao=None),
    "liso": dict(ceu=[(24, 16, 44), (58, 34, 92), (58, 34, 92)], chao=None),
}


def montar_fundo(nome, hz):
    f = FUNDOS.get(nome, FUNDOS["anoitecer"])
    arr = np.zeros((H, W, 3), np.float32)
    top, mid, low = map(np.array, f["ceu"])
    lim = hz if f["chao"] else H
    y = np.linspace(0, 1, lim)[:, None]
    a = np.clip(y / 0.6, 0, 1)
    b = np.clip((y - 0.6) / 0.4, 0, 1)
    col = (top * (1 - a) + mid * a) * (1 - b) + low * b
    arr[:lim] = np.repeat(col[:, None, :], W, axis=1)
    if f["chao"]:
        arr[hz:] = grad(f["chao"][0], f["chao"][1], H - hz)
    return arr, bool(f["chao"])


# ------------------------------------------------------------------ objeto
class Obj:
    def __init__(self, spec, hz, chao):
        self.id = spec["id"]
        achado = icones.achar(spec.get("icone", spec["id"]))
        self.sem_icone = achado is None          # sem ícone adequado: o objeto não aparece (nada aleatório)
        self.conj, self.nome = achado or ("mdi", None)
        self.h = TAM.get(spec.get("tam", "M"), 400)
        self.x = POS_X.get(spec.get("pos", "centro"), spec.get("x", 540)) if isinstance(spec.get("pos", "centro"), str) else spec["pos"]
        no_chao = spec.get("chao", chao)
        self.base = hz + 4 if no_chao else spec.get("y", 900) + self.h / 2
        self.cor = CORES.get(spec.get("cor", "tinta"), INK)
        self.cor_final = None
        self.t_entra = float(spec.get("entra_em", 0.0))
        self.entra = {"subir": "sobe", "surgir": "fade", "aparecer": "fade", "deslizar": "desliza",
                      "cair": "cai"}.get(spec.get("entra", "sobe"), spec.get("entra", "sobe"))
        self.espelhar = bool(spec.get("espelhar", False))
        m = icones.mascara(self.conj, self.nome, self.h) if not self.sem_icone else Image.new("L", (2, 2), 0)
        if self.espelhar:
            m = m.transpose(Image.FLIP_LEFT_RIGHT)
        self.mask = m
        # estado dinâmico (zerado a cada frame)
        self.reset()

    def reset(self):
        self.dx = self.dy = 0.0
        self.rot = 0.0
        self.esc = 1.0
        self.alfa = 1.0
        self.k_cor = 0.0
        self.visivel = True

    def caixa(self):
        w = self.mask.width * self.esc
        h = self.mask.height * self.esc
        x0 = self.x + self.dx - w / 2
        y0 = self.base + self.dy - h
        return x0, y0, x0 + w, y0 + h

    def topo(self, fx=0.5):
        """ponto do contorno superior na fração horizontal fx."""
        a = np.asarray(self.mask)
        col = int(clamp(fx, 0, 0.999) * a.shape[1])
        rows = np.nonzero(a[:, col] > 80)[0]
        r = rows[0] if len(rows) else 0
        x0, y0, x1, y1 = self.caixa()
        return x0 + col * self.esc, y0 + r * self.esc

    def desenhar(self, frame):
        if self.sem_icone or not self.visivel or self.alfa <= 0.01:
            return
        m = self.mask
        if self.esc != 1.0:
            m = m.resize((max(1, int(m.width * self.esc)), max(1, int(m.height * self.esc))), Image.BICUBIC)
        cor = self.cor if self.cor_final is None else lerpc(self.cor, self.cor_final, self.k_cor)
        lay = Image.new("RGBA", m.size, cor + (255,))
        a = m if self.alfa >= 1 else m.point(lambda v: int(v * self.alfa))
        lay.putalpha(a)
        if self.rot:
            lay = lay.rotate(self.rot, resample=Image.BICUBIC, expand=True)
        cx = self.x + self.dx
        by = self.base + self.dy - m.height / 2
        frame.paste(lay, (int(cx - lay.width / 2), int(by - lay.height / 2)), lay)


# ------------------------------------------------------------------ organização automática do espaço
TOPO_TEXTO = 560      # abaixo disso ficam os objetos quando há título/contador no topo
LIMITE_BAIXO = 1320   # objetos no ar não descem além disso (a legenda do vídeo fica embaixo)


def _bbox(o):
    w, h = o.mask.width, o.mask.height
    return [o.x - w / 2, o.base - h, o.x + w / 2, o.base]


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _reescalar(o, fator):
    if getattr(o, "sem_icone", False):
        return
    nova = max(80, int(o.mask.height * fator))
    m = icones.mascara(o.conj, o.nome, nova)
    o.mask = m.transpose(Image.FLIP_LEFT_RIGHT) if o.espelhar else m
    o.h = nova


def organizar(objs, hz, tem_chao, texto_topo, acoes):
    global LIMITE_BAIXO
    juntos = any(a["tipo"] == "titulo" for a in acoes) and any(a["tipo"] == "contador" for a in acoes)
    topo_min = (TOPO_TEXTO + 80 if juntos else TOPO_TEXTO) if texto_topo else 380
    LIMITE_BAIXO = 1120 if sum(1 for a in acoes if a["tipo"] == "titulo") >= 2 else 1320
    lista = list(objs.values())
    for o in lista:
        no_chao = abs(o.base - (hz + 4)) < 2
        # cabe na altura disponível
        disponivel = ((hz + 4) if no_chao else LIMITE_BAIXO) - topo_min
        if o.mask.height > disponivel:
            _reescalar(o, disponivel / o.mask.height)
        if not no_chao:
            bb = _bbox(o)
            if bb[1] < topo_min:
                o.base += topo_min - bb[1]
            if o.base > LIMITE_BAIXO:
                o.base = LIMITE_BAIXO
        # margens laterais
        w = o.mask.width
        if w > W - 120:
            _reescalar(o, (W - 120) / w)
            w = o.mask.width
        o.x = min(max(o.x, 60 + w / 2), W - 60 - w / 2)
    # sobreposições
    for _ in range(8):
        mexeu = False
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                A, B = _bbox(a), _bbox(b)
                inter = _inter(A, B)
                menor = min((A[2] - A[0]) * (A[3] - A[1]), (B[2] - B[0]) * (B[3] - B[1])) or 1
                if inter / menor < 0.05:
                    continue
                # objetos intencionalmente sobrepostos no centro (ex.: seta atrás do relógio) ficam
                if abs(a.x - b.x) < 5 and abs(a.base - b.base) < 5:
                    continue
                mexeu = True
                movel = b if abs(b.base - (hz + 4)) >= 2 else a
                fixo = a if movel is b else b
                if abs(movel.base - (hz + 4)) >= 2:   # objeto no ar: tenta subir, senão vai pro lado
                    FB = _bbox(fixo)
                    novo_base = FB[1] - 30
                    if novo_base - movel.mask.height >= topo_min:
                        movel.base = novo_base
                        continue
                lado = 1 if movel.x >= fixo.x else -1
                alvo = fixo.x + lado * (fixo.mask.width / 2 + movel.mask.width / 2 + 40)
                if 60 + movel.mask.width / 2 <= alvo <= W - 60 - movel.mask.width / 2:
                    movel.x = alvo
                else:
                    # não cabe do lado: diminui os dois e separa, um de cada lado do centro
                    _reescalar(movel, 0.8)
                    _reescalar(fixo, 0.85)
                    total = fixo.mask.width + movel.mask.width + 50
                    if total <= W - 120:
                        esq, dir_ = (fixo, movel) if fixo.x <= movel.x else (movel, fixo)
                        esq.x = W / 2 - total / 2 + esq.mask.width / 2
                        dir_.x = W / 2 + total / 2 - dir_.mask.width / 2
        if not mexeu:
            break
    # textos do topo ficam na faixa reservada; título + contador juntos: título em cima, número menor embaixo dele
    n_tit = 0
    juntos = any(a["tipo"] == "titulo" for a in acoes) and any(a["tipo"] == "contador" for a in acoes)
    for a in acoes:
        if a["tipo"] == "titulo":
            if n_tit == 0:
                a["y"] = 210 if juntos else min(float(a.get("y", 300)), 330)
                a["tam"] = min(float(a.get("tam", 200)), 140 if juntos else 200)
            else:
                a["y"], a["tam"] = 1170, min(float(a.get("tam", 200)), 110)
            n_tit += 1
        if a["tipo"] == "contador":
            if juntos:
                a["y"], a["tam_num"] = 430, 96
                a.pop("rotulo", None)
                a.pop("rotulo_fim", None)
            else:
                a["y"] = min(float(a.get("y", 230)), 260)
        if a["tipo"] == "camera":
            a["zoom"] = min(float(a.get("zoom", 1.3)), 1.22)


# ------------------------------------------------------------------ cena
def render(rec, out):
    dur = float(rec.get("dur", 4.0))
    n = int(dur * FPS)
    hz = int(rec.get("horizonte", 1400))
    fundo, tem_chao = montar_fundo(rec.get("fundo", "anoitecer"), hz)
    objs = {}
    for k, spec in enumerate(rec.get("objetos", [])[:6]):
        spec = dict(spec)
        spec.setdefault("id", f"obj{k}")
        if spec.get("tam") not in TAM:
            spec["tam"] = "M"
        if isinstance(spec.get("pos"), str) and spec["pos"] not in POS_X:
            spec["pos"] = "centro"
        objs[spec["id"]] = Obj(spec, hz, tem_chao)
    acoes = [a for a in rec.get("acoes", []) if isinstance(a, dict) and "tipo" in a][:8]
    rng = random.Random(7)
    tem_texto_topo = any(a["tipo"] in ("titulo", "contador") for a in acoes)
    if tem_texto_topo:
        rec["lua"] = False            # a lua ficava em cima do título
    tit_e_cont = any(a["tipo"] == "titulo" for a in acoes) and any(a["tipo"] == "contador" for a in acoes)
    organizar(objs, hz, tem_chao, tem_texto_topo, acoes)
    # multidões: clona um objeto em fila
    for a in acoes:
        if a["tipo"] == "multiplicar" and a.get("obj") in objs:
            src = objs[a["obj"]]
            nq = int(a.get("n", 5))
            dest = a.get("destaque")
            xs = np.linspace(180, 900, nq)
            for i in range(nq):
                spec = {"id": f"{src.id}_{i}", "icone": src.nome, "tam": "M", "chao": True,
                        "entra_em": float(a.get("t", 0)) + i * 0.06, "entra": "sobe"}
                o = Obj(spec, hz, tem_chao)
                o.conj, o.nome = src.conj, src.nome
                fator = 1.25 if dest is not None and i == dest else rng.uniform(0.82, 0.95)
                o.mask = icones.mascara(src.conj, src.nome, int(src.h * fator))
                o.h = o.mask.height
                o.x = float(xs[i])
                if dest is not None and i == dest:
                    o.cor = src.cor
                objs[o.id] = o
            src.mask = Image.new("L", (1, 1), 0)
            meio = f"{src.id}_{nq // 2 if dest is None else dest}"
            for b in acoes:   # ações que apontavam para o original passam a apontar para um clone
                if b is a:
                    continue
                for campo in ("obj", "de", "para"):
                    if b.get(campo) == src.id:
                        b[campo] = meio

    estrelas = [(rng.uniform(0, W), rng.uniform(0, hz * 0.6), rng.uniform(0.7, 2.2), rng.uniform(1.5, 4.5)) for _ in range(70)]
    gr = np.random.default_rng(3)
    grains = [(gr.normal(0, 1, (H // 2, W // 2)) * 8).astype(np.int16) for _ in range(6)]
    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2)
    vign = (1 - np.clip(rr - 0.3, 0, 1) * 0.8)[..., None].astype(np.float32)
    rachaduras = {}

    proc = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                             "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    camera = next((a for a in acoes if a["tipo"] == "camera"), None)

    for i in range(n):
        t = i / FPS
        fr = Image.fromarray(fundo.astype(np.uint8))
        d = ImageDraw.Draw(fr, "RGBA")
        nome_fundo = rec.get("fundo", "anoitecer")
        if nome_fundo in ("anoitecer", "noite", "por-do-sol"):
            k = 0.4 + 0.6 * prog(t, 0.5, dur)
            for sx, sy, sr, tw in estrelas:
                al = int(255 * k * (0.5 + 0.5 * math.sin(t * tw + sx)))
                d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 240, 230, max(0, al)))
            if rec.get("lua", True) and nome_fundo != "por-do-sol":
                d.ellipse([790, 300, 920, 430], fill=(255, 236, 210, 230))
        if nome_fundo == "por-do-sol":
            sy_ = 980 + 300 * eio(prog(t, 0, dur))
            for rad, al in ((230, 28), (160, 45), (105, 255)):
                d.ellipse([170 - rad, sy_ - rad, 170 + rad, sy_ + rad], fill=(255, 210, 130, al))
            fr.paste(Image.fromarray(fundo[hz:].astype(np.uint8)), (0, hz))
            d = ImageDraw.Draw(fr, "RGBA")
        if nome_fundo == "raios":
            rk = prog(t, 0.1, 0.8)
            for k_ in range(14):
                a0 = k_ / 14 * 2 * math.pi + t * 0.15
                d.polygon([(W / 2, 930), (W / 2 + math.cos(a0) * 1500, 930 + math.sin(a0) * 1500),
                           (W / 2 + math.cos(a0 + 0.12) * 1500, 930 + math.sin(a0 + 0.12) * 1500)],
                          fill=(255, 220, 150, int(20 * rk)))

        for o in objs.values():
            o.reset()
        # entradas
        for o in objs.values():
            p = prog(t, o.t_entra, 0.55)
            if p <= 0:
                o.visivel = False
                continue
            if o.entra == "sobe":
                o.dy = (1 - eout(p)) * 120
                o.alfa = clamp(p * 2.5)
            elif o.entra == "pop":
                o.esc = max(0.01, eback(p))
                o.alfa = clamp(p * 3)
            elif o.entra == "desliza":
                lado = -1 if o.x < W / 2 else 1
                o.dx = lado * (1 - eout(p)) * 420
                o.alfa = clamp(p * 2)
            elif o.entra == "cai":
                o.dy = -(1 - eout(p) ** 2) * 900
            else:
                o.alfa = eio(p)

        overlay_after = []   # desenhos por cima dos objetos
        sombra_jobs = []
        for a in acoes:
            tp = a["tipo"]
            t0 = float(a.get("t", 0))
            du = float(a.get("dur", 1.0))
            p = prog(t, t0, du)
            o = objs.get(a.get("obj")) if a.get("obj") else None
            if tp == "crescer" and o:
                o.esc *= 1 + (float(a.get("fator", 1.4)) - 1) * eio(p)
            elif tp == "encolher" and o:
                o.esc *= 1 - (1 - float(a.get("fator", 0.5))) * eio(p)
            elif tp == "tremer" and o and 0 < p < 1:
                o.dx += math.sin(t * 90) * 12 * (1 - p)
            elif tp == "girar" and o and p > 0:
                vel = float(a.get("vel", 360)) * (1 if a.get("sentido", "anti") == "anti" else -1)
                o.rot += vel * (t - t0) if p < 1 else vel * du
            elif tp == "cair" and o and p > 0:
                e = eio(p)
                o.rot += -80 * e * (1 if a.get("lado", "dir") == "dir" else -1)
                o.dy += 60 * e
                o.dx += 120 * e * (1 if a.get("lado", "dir") == "dir" else -1)
            elif tp == "voar" and o and p > 0:  # sobe girando, em espiral
                u = (t - t0)
                o.dy -= (1 - math.exp(-u * 0.9)) * float(a.get("altura", 800))
                o.dx += math.sin(u * 3.2 + hash(o.id) % 7) * 80 * (1 - math.exp(-u))
                o.rot += u * 160 * (1 if hash(o.id) % 2 else -1)
                o.esc *= 1 - 0.3 * (1 - math.exp(-u))
            elif tp == "flutuar" and o:
                o.dy += math.sin(t * 2.2 + o.x) * 10
            elif tp == "mudar_cor" and o:
                o.cor_final = CORES.get(a.get("cor", "cinza"), CORES["cinza"])
                o.k_cor = eio(p)
            elif tp == "sumir" and o:
                o.alfa *= 1 - eio(p)
            elif tp in ("fios", "conectar", "sombra") and (a.get("de") not in objs or (a.get("para") not in objs and tp != "sombra")):
                continue
            elif tp == "fios" and p > 0:
                alvo = objs[a["para"]]
                alvo.dy += math.sin(t * 6.5) * 8 * prog(t, t0 + du, 0.6)
                overlay_after.append(("fios", objs[a["de"]], alvo, p))
            elif tp == "conectar" and p > 0:
                overlay_after.append(("conectar", objs[a["de"]], objs[a["para"]], p))
            elif tp == "sombra" and p > 0 and tem_chao:
                sombra_jobs.append((objs[a["de"]], objs.get(a.get("para")), eout(p)))
            elif tp == "escurecer" and o:
                o.cor_final = (52, 40, 44)
                o.k_cor = eio(p)
            elif tp == "brilho" and o and p > 0:
                overlay_after.append(("brilho_atras", o, None, p))
            elif tp in ("rachar", "riscar", "rotulo", "seta") and p > 0:
                overlay_after.append((tp, o, a, p))
            elif tp in ("contador", "titulo", "palavra") and p > 0:
                overlay_after.append((tp, None, a, p))

        # sombras no chão (antes dos objetos)
        for de, para, k in sombra_jobs:
            full = Image.new("L", (W, H), 0)
            m = de.mask
            full.paste(m, (int(de.x - m.width / 2), int(de.base - m.height)))
            sentido = 1 if (para is None or para.x >= de.x) else -1
            ky, kx = 0.075, 0.62 * k * sentido
            sh = full.transform((W, H), Image.AFFINE, (1, -kx / ky, kx / ky * hz, 0, -1 / ky, hz + hz / ky), Image.BILINEAR)
            sh = sh.crop((0, hz, W, H)).filter(ImageFilter.GaussianBlur(2.5))
            g = fr.crop((0, hz, W, H))
            g = Image.composite(Image.new("RGB", g.size, (12, 8, 12)), g, sh.point(lambda v: int(v * 0.8)))
            fr.paste(g, (0, hz))

        # halos atrás
        d = ImageDraw.Draw(fr, "RGBA")
        for kind, o, a, p in overlay_after:
            if kind == "brilho_atras" and o.visivel:
                x0, y0, x1, y1 = o.caixa()
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                pul = 1 + 0.05 * math.sin(t * 5)
                for f_, al in ((0.75, 35), (0.6, 55), (0.48, 70)):
                    rx, ry = (x1 - x0) * f_ * pul * eback(p), (y1 - y0) * f_ * pul * eback(p)
                    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=GOLD + (int(al * p),))

        for o in objs.values():
            o.desenhar(fr)

        d = ImageDraw.Draw(fr, "RGBA")
        for kind, o, a, p in overlay_after:
            if kind == "fios":
                de, para = o, a
                sx, sy = de.topo(0.5)
                lay = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                for j, fx in enumerate((0.2, 0.5, 0.8)):
                    pj = eout(clamp(p * 1.5 - j * 0.2))
                    if pj <= 0:
                        continue
                    ex, ey = para.topo(fx)
                    pts = []
                    for s_ in np.linspace(0, pj, 40):
                        x = sx + (ex - sx) * s_
                        y = sy + (ey - sy) * s_ + math.sin(math.pi * s_) * (40 - 30 * j)
                        pts.append((x * 2, y * 2))
                    ld.line(pts, fill=GOLD + (235,), width=6)
                    if pj >= 1:
                        ld.ellipse([ex * 2 - 12, ey * 2 - 12, ex * 2 + 12, ey * 2 + 12], fill=GOLD + (255,))
                lay = lay.resize((W, H), Image.LANCZOS)
                glow = lay.filter(ImageFilter.GaussianBlur(8))
                fr.paste(glow, (0, 0), glow)
                fr.paste(lay, (0, 0), lay)
                d = ImageDraw.Draw(fr, "RGBA")
            elif kind == "conectar":
                de, para = o, a
                x0, y0 = (de.caixa()[0] + de.caixa()[2]) / 2, (de.caixa()[1] + de.caixa()[3]) / 2
                x1, y1 = (para.caixa()[0] + para.caixa()[2]) / 2, (para.caixa()[1] + para.caixa()[3]) / 2
                e = eout(p)
                xe, ye = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
                n_ = 22
                for s_ in range(n_):
                    if s_ / n_ > e:
                        break
                    if s_ % 2 == 0:
                        a0, a1 = s_ / n_, min(e, (s_ + 1) / n_)
                        d.line([(x0 + (x1 - x0) * a0, y0 + (y1 - y0) * a0), (x0 + (x1 - x0) * a1, y0 + (y1 - y0) * a1)],
                               fill=GOLD + (230,), width=6)
                fase = (t * 0.8) % 1
                d.ellipse([x0 + (x1 - x0) * fase * e - 12, y0 + (y1 - y0) * fase * e - 12,
                           x0 + (x1 - x0) * fase * e + 12, y0 + (y1 - y0) * fase * e + 12], fill=CREAM + (255,))
            elif kind == "rachar" and o:
                x0, y0, x1, y1 = o.caixa()
                if o.id not in rachaduras:
                    r2 = random.Random(hash(o.id))
                    pts = [((x0 + x1) / 2 + r2.uniform(-30, 30), y0)]
                    for s_ in range(1, 8):
                        pts.append(((x0 + x1) / 2 + r2.uniform(-(x1 - x0) * 0.3, (x1 - x0) * 0.3), y0 + (y1 - y0) * s_ / 7))
                    rachaduras[o.id] = pts
                pts = rachaduras[o.id]
                m = max(2, int(len(pts) * eout(p)))
                d.line(pts[:m], fill=(255, 255, 255, 235), width=6)
                if p < 0.25:
                    o.dx = math.sin(t * 120) * 10
            elif kind == "riscar" and o:
                x0, y0, x1, y1 = o.caixa()
                e = eout(p)
                pad = 30
                d.line([(x0 - pad, y0 - pad), (x0 - pad + (x1 - x0 + 2 * pad) * e, y0 - pad + (y1 - y0 + 2 * pad) * e)],
                       fill=CORES["vermelho"] + (255,), width=22)
                e2 = eout(prog(p, 0.4, 0.6))
                if e2 > 0:
                    d.line([(x1 + pad, y0 - pad), (x1 + pad - (x1 - x0 + 2 * pad) * e2, y0 - pad + (y1 - y0 + 2 * pad) * e2)],
                           fill=CORES["vermelho"] + (255,), width=22)
            elif kind == "rotulo" and o:
                x0, y0, x1, y1 = o.caixa()
                s = eback(clamp(p * 1.8))
                txt = str(a.get("texto", ""))
                cor = CORES.get(a.get("cor", "creme"), CREAM)
                f_ = font("Poppins-Bold.ttf", float(a.get("tam", 90)) * max(0.2, s))
                tw = f_.getlength(txt)
                d.text(((x0 + x1) / 2 - tw / 2, max(150, y0 - float(a.get("tam", 90)) * 1.35)), txt, font=f_, fill=cor + (int(255 * clamp(p * 3)),))
            elif kind == "contador":
                e = eio(p)
                de_, ate = float(a.get("de", 0)), float(a.get("ate", 100))
                v = de_ + (ate - de_) * e
                txt = (a.get("fim") if (p >= 1 and a.get("fim")) else
                       f"{int(round(v))}{a.get('sufixo', '')}")
                al = int(255 * prog(t, float(a.get("t", 0)), 0.3))
                rot = a.get("rotulo_fim") if (p >= 0.15 and a.get("rotulo_fim")) else a.get("rotulo", "")
                if rot:
                    texto_espacado(d, W / 2, float(a.get("y", 230)), rot, font("Poppins-Medium.ttf", 38), GOLD + (al,), 12)
                f_ = font("Poppins-Light.ttf", float(a.get("tam_num", 132)))
                d.text(((W - f_.getlength(txt)) / 2, float(a.get("y", 230)) + 40), txt, font=f_, fill=CREAM + (al,))
            elif kind == "titulo":
                e = eout(p)
                al = int(255 * clamp(p * 2))
                if a.get("rotulo"):
                    texto_espacado(d, W / 2, float(a.get("y", 300)) - 60, a["rotulo"], font("Poppins-Medium.ttf", 40), GOLD + (al,), 14)
                txt = str(a.get("texto", "")).strip()
                tam = float(a.get("tam", 200))
                linhas_t = [txt]
                while tam > 96 and font("Poppins-Bold.ttf", tam).getlength(txt) > W - 120:
                    tam -= 6
                if font("Poppins-Bold.ttf", tam).getlength(txt) > W - 120 and " " in txt:
                    pal = txt.split()
                    corte = min(range(1, len(pal)), key=lambda i: abs(len(" ".join(pal[:i])) - len(" ".join(pal[i:]))))
                    linhas_t = [" ".join(pal[:corte]), " ".join(pal[corte:])]
                    tam = min(float(a.get("tam", 200)), 130)
                    while tam > 60 and max(font("Poppins-Bold.ttf", tam).getlength(l) for l in linhas_t) > W - 120:
                        tam -= 6
                f_ = font("Poppins-Bold.ttf", tam)
                y0 = float(a.get("y", 300)) + 50 * (1 - e) - (tam * 0.55 if len(linhas_t) > 1 else 0)
                for li, linha in enumerate(linhas_t):
                    d.text(((W - f_.getlength(linha)) / 2, y0 + li * tam * 1.05), linha, font=f_,
                           fill=CORES.get(a.get("cor", "creme"), CREAM) + (al,))
            elif kind == "palavra":
                e = eout(p)
                txt = a.get("texto", "")
                f_ = font("Lora-Italic-Variable.ttf", float(a.get("tam", 90)))
                nch = int(len(txt) * clamp(p * 1.6) + 0.999)
                tw = f_.getlength(txt)
                d.text(((W - tw) / 2, float(a.get("y", 1500))), txt[:nch], font=f_, fill=CREAM + (255,))
            elif kind == "seta" and o:
                x0, y0, x1, y1 = o.caixa()
                cx = (x0 + x1) / 2
                bob = math.sin(t * 6) * 12
                ytop = y0 - 230 + bob
                d.polygon([(cx - 40, ytop), (cx + 40, ytop), (cx + 40, ytop + 80), (cx + 80, ytop + 80), (cx, ytop + 150),
                           (cx - 80, ytop + 80), (cx - 40, ytop + 80)], fill=GOLD + (int(255 * clamp(p * 3)),))

        # câmera (empurrão lento; pode mirar num objeto)
        z = 1.04 + 0.05 * eio(prog(t, 0, dur))
        cx, cy = W / 2, 1000
        if camera:
            pc = eio(prog(t, float(camera.get("t", 0)), float(camera.get("dur", dur))))
            z += (float(camera.get("zoom", 1.3)) - 1) * pc
            alvo = objs.get(camera.get("obj"))
            if alvo:
                x0, y0, x1, y1 = alvo.caixa()
                cx = W / 2 + ((x0 + x1) / 2 - W / 2) * pc
                cy = 1000 + ((y0 + y1) / 2 - 1000) * pc
        cw, ch = int(W / z), int(H / z)
        bx = int(clamp(cx - cw / 2, 0, W - cw))
        by = int(clamp(cy - ch / 2, 0, H - ch))
        fr = fr.crop((bx, by, bx + cw, by + ch)).resize((W, H), Image.BICUBIC)
        arr = np.asarray(fr).astype(np.float32) * vign
        arr += np.repeat(np.repeat(grains[i % 6], 2, 0), 2, 1)[..., None]
        if i < 4:
            arr *= (i + 1) / 5
        proc.stdin.write(np.clip(arr, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    return out


if __name__ == "__main__":
    rec = json.load(open(sys.argv[1], encoding="utf-8"))
    print("ok:", render(rec, sys.argv[2]))
