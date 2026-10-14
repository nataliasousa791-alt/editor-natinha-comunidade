"""B-roll Engine V2 — biblioteca de templates editoriais (leves: Pillow + FFmpeg, sem GPU).

Cada template recebe "dados" curtos (escritos pelo Gemini no planejamento) e gera um MP4 1080x1920.
Estilo: editorial, limpo, tipografia forte, movimento sutil (reveal, fade, linha que se desenha, zoom lento).
Temas: "papel" (claro), "escuro", "matrix" (verde discreto) e "roxo" (identidade antiga, opcional).

Uso: templates.render("palavra_chave", {"texto": "..."}, 4.0, "saida.mp4", tema="escuro")
"""
import math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

try:
    from . import icones
except ImportError:  # pragma: no cover
    import icones

W, H, FPS = 1080, 1920, 30
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FF_LOCAL = os.path.join(_RAIZ, "ffmpeg", "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
FFMPEG = _FF_LOCAL if os.path.exists(_FF_LOCAL) else "ffmpeg"
FD = os.path.join(_RAIZ, "recursos", "fontes")
TOPO, BAIXO = 260, 1300          # área útil (embaixo fica a legenda do corte)
# ZONA DA LEGENDA dos cortes (legenda_y=1430: o texto ocupa ~1370-1500). Nada importante do template pode passar de
# LIMITE_LEGENDA (já contando o zoom lento da câmera); se passar, o template sobe, é simplificado ou vira palavra-chave.
LIMITE_LEGENDA = 1305
MARGEM_TOPO = 150                # acima disso ficam o nome do perfil/botões do app
LARG, X0 = 900, 0                # largura máx. de texto; início da "coluna" central de 1080 (no horizontal fica no meio)


def _canvas(w, h):
    """Ajusta a tela: 1080x1920 (cortes) ou 1920x1080 (YouTube, tela cheia)."""
    global W, H, TOPO, BAIXO, LARG, X0
    W, H = int(w), int(h)
    if W > H:
        TOPO, BAIXO = int(H * 0.12), H - int(H * 0.11)
    else:
        TOPO, BAIXO = 260, 1300
    LARG = min(LARG, 1300)
    X0 = max(0, (W - 1080) // 2)

TEMAS = {
    "papel":  dict(fundo=(241, 236, 227), tinta=(26, 22, 30), acento=(178, 66, 44), suave=(128, 118, 108),
                   linha=(205, 196, 184), grao=10),
    "escuro": dict(fundo=(17, 16, 21), tinta=(238, 233, 224), acento=(226, 178, 76), suave=(138, 132, 146),
                   linha=(58, 55, 66), grao=8),
    "matrix": dict(fundo=(8, 13, 11), tinta=(214, 234, 222), acento=(104, 226, 156), suave=(92, 128, 108),
                   linha=(30, 54, 42), grao=6),
    "roxo":   dict(fundo=(26, 17, 42), tinta=(246, 238, 227), acento=(242, 193, 78), suave=(170, 150, 200),
                   linha=(62, 46, 92), grao=7),
}
# variações DENTRO da mesma família (mesma tipografia, acento, grão e linhas): capítulos do mesmo vídeo
TEMAS["papel_escuro"] = dict(fundo=(30, 26, 34), tinta=(241, 236, 227), acento=(214, 104, 74), suave=(160, 150, 140),
                             linha=(72, 64, 72), grao=9)
TEMAS["escuro_claro"] = dict(fundo=(236, 230, 218), tinta=(20, 18, 24), acento=(168, 120, 32), suave=(122, 114, 106),
                             linha=(206, 196, 182), grao=9)
TEMAS["matrix_limpo"] = dict(TEMAS["matrix"], fundo=(11, 19, 15))
TEMAS["roxo_profundo"] = dict(TEMAS["roxo"], fundo=(14, 9, 25), linha=(52, 38, 80))
FAMILIAS = {"papel": ["papel", "papel_escuro"], "escuro": ["escuro", "escuro_claro"],
            "matrix": ["matrix", "matrix_limpo"], "roxo": ["roxo", "roxo_profundo"]}


# ---- ESTÉTICA NOVA (fundo preto/grafite, branco como estrutura, cor com FUNÇÃO e brilho discreto) ----
# acento = elemento principal; positivo = verde; perigo = vermelho; energia = ciano; sec = cor da família.
_SEM = dict(positivo=(70, 230, 120), perigo=(255, 72, 72), energia=(40, 210, 255), amarelo=(255, 206, 64))
TEMAS["tech"] = dict(_SEM, fundo=(5, 9, 9), tinta=(232, 242, 238), acento=(60, 255, 160), sec=(40, 210, 255),
                     suave=(118, 136, 132), linha=(34, 54, 50), grao=3, nova=True)
TEMAS["documental"] = dict(_SEM, fundo=(14, 13, 12), tinta=(240, 234, 222), acento=(240, 190, 80), sec=(214, 196, 160),
                           suave=(140, 132, 118), linha=(56, 52, 46), grao=4, nova=True)
TEMAS["psicologico"] = dict(_SEM, fundo=(6, 8, 12), tinta=(238, 242, 248), acento=(60, 200, 255), sec=(150, 170, 255),
                            suave=(124, 132, 146), linha=(36, 44, 58), grao=3, nova=True)
TEMAS["alerta"] = dict(_SEM, fundo=(8, 7, 7), tinta=(244, 240, 238), acento=(255, 64, 64), sec=(255, 206, 64),
                       suave=(140, 132, 130), linha=(52, 44, 44), grao=3, nova=True)
TEMAS["espiritual"] = dict(_SEM, fundo=(9, 7, 14), tinta=(244, 238, 230), acento=(255, 200, 80), sec=(170, 110, 255),
                           suave=(146, 136, 160), linha=(46, 38, 62), grao=3, nova=True)
for _f in ("tech", "documental", "psicologico", "alerta", "espiritual"):          # variação (outro "capítulo")
    TEMAS[_f + "_2"] = dict(TEMAS[_f], fundo=tuple(min(255, c + 12) for c in TEMAS[_f]["fundo"]),
                            acento=TEMAS[_f]["sec"], sec=TEMAS[_f]["acento"])
FAMILIAS.update({f: [f, f + "_2"] for f in ("tech", "documental", "psicologico", "alerta", "espiritual")})
NOVAS = ("tech", "documental", "psicologico", "alerta", "espiritual")
DA_ANTIGA = {"papel": "documental", "escuro": "documental", "matrix": "tech", "roxo": "espiritual"}


def cor(T, nome):
    """Cor com função narrativa (funciona também nos temas antigos)."""
    return T.get(nome) or {"positivo": (70, 200, 110), "perigo": (220, 70, 60), "energia": (60, 180, 230),
                           "amarelo": T["acento"], "sec": T["suave"]}.get(nome, T["acento"])


def brilho(lay, forca=0.75, raio=5):
    """Glow discreto e barato: desfoque em 1/4 da resolução, por baixo do desenho."""
    w, h = lay.size
    peq = lay.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(raio))
    g = peq.resize((w, h), Image.BILINEAR)
    if forca < 1:
        g.putalpha(g.getchannel("A").point(lambda v: int(v * forca)))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(g)
    out.alpha_composite(lay)
    return out


def familia_de(tema):
    return next((f for f, v in FAMILIAS.items() if tema in v), "escuro")


def _claro(T):
    return sum(T["fundo"]) > 380


CATALOGO = ["palavra_chave", "contraste", "comparacao", "transformacao", "causa_efeito", "dado", "espectro",
            "linha_tempo", "processo", "lista", "citacao", "conceito", "foco", "documento"]


# ------------------------------------------------------------------ utilidades
def _c(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _p(t, s, d):
    return _c((t - s) / d) if d > 0 else float(t >= s)


def _eout(x):
    return 1 - (1 - x) ** 3


def _eio(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def fonte(tipo, tam):
    """serif = Lora (editorial), sans = Poppins."""
    tam = max(10, int(tam))
    try:
        if tipo == "serif":
            f = ImageFont.truetype(os.path.join(FD, "Lora-Variable.ttf"), tam)
            try:
                f.set_variation_by_name("SemiBold")
            except Exception:
                pass
            return f
        if tipo == "serif_it":
            f = ImageFont.truetype(os.path.join(FD, "Lora-Italic-Variable.ttf"), tam)
            try:
                f.set_variation_by_name("Medium Italic")
            except Exception:
                pass
            return f
        nome = {"sans": "Poppins-Bold.ttf", "sans_m": "Poppins-Medium.ttf", "sans_l": "Poppins-Light.ttf"}[tipo]
        return ImageFont.truetype(os.path.join(FD, nome), tam)
    except Exception:
        return ImageFont.truetype(os.path.join(FD, "Poppins-Bold.ttf"), tam)


def quebrar(txt, f, larg, max_linhas=3):
    pal, linhas, cur = str(txt).split(), [], ""
    for p in pal:
        t = (cur + " " + p).strip()
        if f.getlength(t) <= larg or not cur:
            cur = t
        else:
            linhas.append(cur)
            cur = p
    if cur:
        linhas.append(cur)
    return linhas[:max_linhas]


def caber(txt, tipo, tam, larg, max_linhas=3, minimo=40):
    """Maior fonte em que o texto cabe em 'max_linhas' linhas."""
    while tam > minimo:
        f = fonte(tipo, tam)
        ls = quebrar(txt, f, larg, 99)
        if len(ls) <= max_linhas and all(f.getlength(l) <= larg for l in ls):
            return f, ls
        tam -= 4
    f = fonte(tipo, minimo)
    return f, quebrar(txt, f, larg, max_linhas)


def camada_texto(linhas, f, cor, alinhar="centro", entre=1.12, track=0):
    """Imagem RGBA com o bloco de texto (para revelar/mover sem redesenhar)."""
    alt = int(f.size * entre)
    larg = int(max(_largura(l, f, track) for l in linhas)) + 8 if linhas else 1
    im = Image.new("RGBA", (max(1, larg), max(1, alt * len(linhas) + int(f.size * 0.3))), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(linhas):
        lw = _largura(l, f, track)
        x = (larg - lw) / 2 if alinhar == "centro" else 0
        _texto(d, x, i * alt, l, f, cor, track)
    return im


def _largura(t, f, track):
    return f.getlength(t) + track * max(0, len(t) - 1)


def _texto(d, x, y, t, f, cor, track=0):
    if not track:
        d.text((x, y), t, font=f, fill=cor)
        return
    for ch in t:
        d.text((x, y), ch, font=f, fill=cor)
        x += f.getlength(ch) + track


def rotulo(txt, cor, tam=34):
    """Etiqueta pequena em caixa alta e espaçada (estilo editorial)."""
    f = fonte("sans_m", tam)
    return camada_texto([str(txt).upper()], f, cor, track=int(tam * 0.22))


def revelar(lay, k, modo="baixo"):
    """Reveal por máscara: 'baixo' (sobe de dentro de uma janela), 'esq' (wipe da esquerda)."""
    k = _c(k)
    if k <= 0:
        return None, 0
    if k >= 1:
        return lay, 0
    if modo == "esq":
        w = max(1, int(lay.width * _eout(k)))
        out = Image.new("RGBA", lay.size, (0, 0, 0, 0))
        out.paste(lay.crop((0, 0, w, lay.height)), (0, 0))
        return out, 0
    dy = int((1 - _eout(k)) * lay.height * 0.55)
    out = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    out.paste(lay.crop((0, 0, lay.width, lay.height - dy)), (0, dy))
    a = out.getchannel("A").point(lambda v: int(v * _c(k * 1.6)))
    out.putalpha(a)
    return out, 0


def alfa(lay, k):
    if k >= 1:
        return lay
    out = lay.copy()
    out.putalpha(lay.getchannel("A").point(lambda v: int(v * _c(k))))
    return out


def colar(fr, lay, cx, y, k=1.0, modo=None):
    """Cola a camada centralizada em cx, topo em y, com reveal (modo) ou fade (k)."""
    if lay is None:
        return
    if modo:
        lay, _ = revelar(lay, k, modo)
        if lay is None:
            return
    elif k < 1:
        if k <= 0:
            return
        lay = alfa(lay, k)
    fr.alpha_composite(lay, (int(cx - lay.width / 2), int(y)))


def linha(d, x0, y0, x1, y1, k, cor, larg=4):
    if k <= 0:
        return
    k = _eout(_c(k))
    d.line([x0, y0, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k], fill=cor, width=larg)


def fundo(tema, seed=0):
    T = TEMAS[tema]
    rnd = np.random.default_rng(seed)
    if T.get("nova"):
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xx - W / 2) / (W * 0.55)) ** 2 + ((yy - H * 0.45) / (H * 0.55)) ** 2)
        luz = np.clip(1 - r, 0, 1)[..., None] ** 2
        cor_luz = np.array(T["acento"], np.float32) * 0.05 + 10
        base = np.zeros((H, W, 3), np.float32) + np.array(T["fundo"], np.float32) + luz * cor_luz
        base += rnd.normal(0, T["grao"], (H, W, 1))
        return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    base = np.zeros((H, W, 3), np.float32) + np.array(T["fundo"], np.float32)
    # vinheta suave
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
    escurece = 0.10 if _claro(T) else 0.28
    base *= (1 - escurece * np.clip(r - 0.35, 0, 1))[..., None]
    # grão fixo
    base += rnd.normal(0, T["grao"], (H, W, 1))
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGBA")
    if tema == "matrix":         # colunas de código bem discretas
        d = ImageDraw.Draw(im)
        f = fonte("sans_l", 26)
        chars = "01アカサタナ<>/{}#=+"
        for x in range(30, W, 44):
            y = int(rnd.integers(-400, 0))
            for _ in range(int(rnd.integers(10, 40))):
                c = T["linha"] + (int(rnd.integers(40, 110)),)
                d.text((x, y), chars[int(rnd.integers(0, len(chars)))], font=f, fill=c)
                y += 34
    return im


MOVIMENTOS = ("aproxima", "afasta", "pan_esq", "pan_dir", "sobe")


class Saida:
    """Recebe quadros (PIL RGB/RGBA) e grava o MP4 com movimento lento de câmera (varia de tela para tela)."""

    def __init__(self, caminho, dur, zoom=0.035, movimento="aproxima", final=None):
        self.caminho, self.dur = caminho, dur
        amplia = f",scale={final[0]}:{final[1]}:flags=lanczos" if final and tuple(final) != (W, H) else ""
        vf = []
        if zoom:
            fixo = f"(1+{zoom})"
            if movimento == "afasta":
                z, x, y = f"(1+{zoom}*(1-t/{dur:.3f}))", f"(iw-{W})*(0.65-0.3*t/{dur:.3f})", f"(ih-{H})/2"
            elif movimento == "pan_esq":
                z, x, y = fixo, f"(iw-{W})*(0.9-0.8*t/{dur:.3f})", f"(ih-{H})/2"
            elif movimento == "pan_dir":
                z, x, y = fixo, f"(iw-{W})*(0.1+0.8*t/{dur:.3f})", f"(ih-{H})/2"
            elif movimento == "sobe":
                z, x, y = fixo, f"(iw-{W})/2", f"(ih-{H})*(0.85-0.7*t/{dur:.3f})"
            else:                                   # aproxima (zoom lento + leve deslize lateral)
                z, x, y = f"(1+{zoom}*t/{dur:.3f})", f"(iw-{W})*(0.35+0.3*t/{dur:.3f})", f"(ih-{H})/2"
            vf = ["-vf", f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,"
                         f"crop={W}:{H}:x='{x}':y='{y}'{amplia},format=yuv420p"]
        elif amplia:
            vf = ["-vf", amplia.lstrip(",") + ",format=yuv420p"]
        self.parcial = caminho + ".parcial.mp4"
        self.p = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                   "-r", str(FPS), "-i", "-", *vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                                   "-pix_fmt", "yuv420p", self.parcial], stdin=subprocess.PIPE,
                                  **({"creationflags": 0x08000000} if os.name == "nt" else {}))

    def quadro(self, im):
        self.p.stdin.write(im.convert("RGB").tobytes())

    def fechar(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise RuntimeError("ffmpeg falhou ao gravar o template")
        os.replace(self.parcial, self.caminho)


def _titulo_topo(T, txt, y=TOPO):
    """Etiqueta pequena + título curto no topo (amarra a cena à fala)."""
    if not txt:
        return None
    return rotulo(txt, T["acento"], 36)


def _icone(palavras, alt, cor):
    """Ícone limpo (sem fallback aleatório). Devolve None se não houver ícone adequado."""
    if not palavras:
        return None
    r = icones.achar(palavras if isinstance(palavras, list) else [palavras])
    if not r:
        return None
    m = icones.mascara(r[0], r[1], int(alt))
    lay = Image.new("RGBA", m.size, cor + (255,))
    lay.putalpha(m)
    return lay


# ------------------------------------------------------------------ templates
def t_palavra_chave(D, dur, T):
    """Uma palavra/frase curta grande, revelada de baixo, com fio que se desenha e linha de apoio."""
    txt = str(D.get("texto") or D.get("titulo") or "").strip()
    deitado = W > H
    f, ls = caber(txt.upper() if len(txt) <= 18 else txt, "serif", 118 if deitado else 190, LARG, 3, 56 if deitado else 70)
    grande = camada_texto(ls, f, T["tinta"])
    apoio = D.get("apoio")
    ap = None
    if apoio:
        fa, la = caber(apoio, "sans_l", 46, LARG - 40, 2, 30)
        ap = camada_texto(la, fa, T["suave"])
    eti = rotulo(D.get("etiqueta"), T["acento"]) if D.get("etiqueta") else None
    y0 = int(H * 0.42 - grande.height / 2)
    y0 = max(y0, int(H * 0.10) + (110 if eti else 0))       # nunca encosta no topo da tela

    def quadro(fr, d, t):
        if eti:
            colar(fr, eti, W / 2, y0 - 110, _p(t, 0.0, 0.5))
        colar(fr, grande, W / 2, y0, _p(t, 0.1, 0.7), "baixo")
        yl = y0 + grande.height + 30
        linha(d, W / 2 - 160, yl, W / 2 + 160, yl, _p(t, 0.6, 0.6), T["acento"], 5)
        if ap:
            colar(fr, ap, W / 2, yl + 50, _p(t, 0.9, 0.6))
    return quadro


def t_contraste(D, dur, T):
    """Dois polos opostos: metade de cima x metade de baixo, com rótulos e frase curta em cada um."""
    a, b = D.get("a") or {}, D.get("b") or {}
    inv = dict(T, fundo=T["tinta"], tinta=T["fundo"])
    if T.get("nova"):
        painel = tuple(min(255, c + 16) for c in T["fundo"])
        inv = dict(T, fundo=painel, tinta=T["acento"])
    blocos = []
    for lado, tema in ((a, T), (b, inv)):
        f, ls = caber(str(lado.get("rotulo", "")).upper(), "serif", 150 if H > W else 112, LARG - 20, 2, 60)
        tl = camada_texto(ls, f, tema["tinta"])
        ft, lt = caber(lado.get("texto", ""), "sans_l", 44, LARG - 40, 2, 28)
        sec = T["suave"] if tema is T else tuple(int(T["fundo"][j] * 0.55 + T["tinta"][j] * 0.45) for j in range(3))
        tx = camada_texto(lt, ft, sec) if lado.get("texto") else None
        blocos.append((tl, tx))
    tit = rotulo(D.get("titulo"), T["acento"]) if D.get("titulo") else None
    meio = int((TOPO + BAIXO) / 2) + 40

    tB = max(0.8, dur * 0.28)            # 1º entra A; 2º entra B (com a cortina); 3º o elemento da diferença
    tX = tB + max(0.5, dur * 0.18)
    if W > H:                            # YouTube: lado a lado, B entra num painel que desliza da direita
        lados = []
        for lado, tema in ((a, T), (b, inv)):
            f, ls = caber(str(lado.get("rotulo", "")).upper(), "serif", 120, int(W * 0.38), 2, 50)
            tl = camada_texto(ls, f, tema["tinta"])
            ft, lt = caber(lado.get("texto", ""), "sans_l", 36, int(W * 0.36), 2, 24)
            sec = T["suave"] if tema is T else tuple(int(T["fundo"][j] * 0.55 + T["tinta"][j] * 0.45) for j in range(3))
            lados.append((tl, camada_texto(lt, ft, sec) if lado.get("texto") else None))
        cyh = int(H * 0.52)

        def quadro_h(fr, d, t):
            k = _eio(_p(t, tB - 0.25, 0.7))
            xp = int(W - W / 2 * k)
            if xp < W:
                d.rectangle([xp, 0, W, H], fill=inv["fundo"])
            if tit:
                colar(fr, tit, W * 0.25, TOPO - 20, _p(t, 0, 0.5))
            for i, (tl, tx) in enumerate(lados):
                cx = W * (0.25 if i == 0 else 0.75)
                t0 = 0.05 if i == 0 else tB
                alt = tl.height + (tx.height + 24 if tx else 0)
                y = cyh - alt / 2
                colar(fr, tl, cx, y, _p(t, t0, 0.6), "baixo")
                if tx:
                    colar(fr, tx, cx, y + tl.height + 24, _p(t, t0 + 0.4, 0.6))
            kx = _p(t, tX, 0.45)
            if kx > 0:
                dt = max(0.0, t - tX)
                esc = _eout(kx) * (1 + 0.25 * math.exp(-dt * 6) * (1 - math.exp(-dt * 25)))
                r = int(52 * esc)
                if r > 2:
                    d.ellipse([W / 2 - r, cyh - r, W / 2 + r, cyh + r], fill=T["acento"],
                              outline=T["fundo"], width=max(1, int(5 * esc)))
                    f = fonte("serif_it", max(12, int(64 * esc)))
                    vs = camada_texto([str(D.get("conector") or "×")[:3]], f, T["fundo"])
                    colar(fr, vs, W / 2, cyh - vs.height / 2 - r * 0.12, 1.0)
        return quadro_h

    def quadro(fr, d, t):
        k = _eio(_p(t, tB - 0.25, 0.7))
        # metade de baixo invertida sobe como uma cortina junto com B
        yb = int(H - (H - meio) * k)
        if yb < H:
            d.rectangle([0, yb, W, H], fill=inv["fundo"])
        if tit:
            colar(fr, tit, W / 2, TOPO - 40, _p(t, 0, 0.5))
        tl, tx = blocos[0]
        colar(fr, tl, W / 2, meio - 120 - tl.height - (50 if tx else 0), _p(t, 0.05, 0.6), "baixo")
        if tx:
            colar(fr, tx, W / 2, meio - 150, _p(t, 0.45, 0.6))
        tl, tx = blocos[1]
        colar(fr, tl, W / 2, meio + 110, _p(t, tB, 0.6), "baixo")
        if tx:
            colar(fr, tx, W / 2, meio + 120 + tl.height + 10, _p(t, tB + 0.4, 0.6))
        kx = _p(t, tX, 0.45)
        if kx > 0:                       # a diferença: selo no encontro dos dois lados, que "pulsa" ao entrar
            dt = max(0.0, t - tX)
            esc = _eout(kx) * (1 + 0.25 * math.exp(-dt * 6) * (1 - math.exp(-dt * 25)))
            r = int(62 * esc)
            if r > 2:
                d.ellipse([W / 2 - r, meio - r, W / 2 + r, meio + r], fill=T["acento"],
                          outline=T["fundo"], width=max(1, int(6 * esc)))
                f = fonte("serif_it", max(12, int(78 * esc)))
                vs = camada_texto([str(D.get("conector") or "×")[:3]], f, T["fundo"])
                colar(fr, vs, W / 2, meio - vs.height / 2 - r * 0.12, 1.0)
    return quadro


def t_comparacao(D, dur, T):
    """Duas colunas lado a lado (antes/depois, positivo/negativo) com itens curtos."""
    cols = []
    for i, lado in enumerate((D.get("a") or {}, D.get("b") or {})):
        cor = T["suave"] if i == 0 else T["acento"]
        r = rotulo(lado.get("rotulo", ""), cor, 34)
        itens = [str(x) for x in (lado.get("itens") or [lado.get("texto", "")]) if x][:4]
        f = fonte("serif", 66 if H > W else 46)
        its = [camada_texto(quebrar(x, f, W / 2 - 110, 3 if H > W else 1), f, T["tinta"]) for x in itens]
        cols.append((r, its))
    tit = None
    if D.get("titulo"):
        ft, lt = caber(D["titulo"], "serif", 96 if H > W else 64, LARG + 20 if H > W else int(W * 0.8), 2, 40)
        tit = camada_texto(lt, ft, T["tinta"])
    esp = 40 if H > W else 18

    def quadro(fr, d, t):
        y = TOPO
        if tit:
            colar(fr, tit, W / 2, y, _p(t, 0, 0.6), "baixo")
            y += tit.height + (70 if H > W else 36)
        linha(d, W / 2, y, W / 2, BAIXO - 60, _p(t, 0.3, 0.8), T["linha"], 3)
        for i, (r, its) in enumerate(cols):
            cx = W * (0.27 if i == 0 else 0.73)
            t0 = 0.4 + i * 0.9
            colar(fr, r, cx, y + 10, _p(t, t0, 0.4))
            yy = y + 90
            for j, it in enumerate(its):
                colar(fr, it, cx, yy, _p(t, t0 + 0.2 + j * 0.25, 0.5), "baixo")
                yy += it.height + esp
    return quadro


def t_transformacao(D, dur, T):
    """A vira B: A aparece, é riscado/esmaece, B surge no lugar com destaque."""
    fa, la = caber(str(D.get("de", "")), "serif", 150, LARG - 20, 2, 60)
    fb, lb = caber(str(D.get("para", "")), "serif", 170, LARG - 20, 2, 60)
    A = camada_texto(la, fa, T["tinta"])
    B = camada_texto(lb, fb, T["acento"])
    tit = rotulo(D.get("titulo"), T["suave"]) if D.get("titulo") else None
    cy = int(H * 0.42)
    meio = dur * 0.45
    if W > H:                         # horizontal: A à esquerda → B à direita
        fa, la = caber(str(D.get("de", "")), "serif", 130, int(W * 0.36), 2, 50)
        fb, lb = caber(str(D.get("para", "")), "serif", 140, int(W * 0.36), 2, 50)
        A = camada_texto(la, fa, T["tinta"])
        B = camada_texto(lb, fb, T["acento"])
        cyh = int(H * 0.5)

        def quadro_h(fr, d, t):
            if tit:
                colar(fr, tit, W / 2, TOPO, _p(t, 0, 0.5))
            xa, xb = W * 0.27, W * 0.73
            ka = 1 - _p(t, meio, 0.5) * 0.7
            colar(fr, A, xa, cyh - A.height / 2, min(_p(t, 0.05, 0.5), ka), "baixo" if t < 0.6 else None)
            if t > meio - 0.3:
                yl = cyh - A.height / 2 + A.height * 0.45
                linha(d, xa - A.width / 2 - 10, yl, xa + A.width / 2 + 10, yl, _p(t, meio - 0.3, 0.4), T["acento"], 6)
            ks = _p(t, meio, 0.5)
            if ks > 0:
                linha(d, W / 2 - 70, cyh, W / 2 + 60, cyh, ks, T["suave"], 4)
                if ks >= 1:
                    d.polygon([(W / 2 + 50, cyh - 14), (W / 2 + 50, cyh + 14), (W / 2 + 76, cyh)], fill=T["suave"])
            colar(fr, B, xb, cyh - B.height / 2, _p(t, meio + 0.2, 0.7), "baixo")
        return quadro_h

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, TOPO, _p(t, 0, 0.5))
        ka = 1 - _p(t, meio, 0.5) * 0.75
        ya = cy - A.height - 30 - int(_eio(_p(t, meio, 0.7)) * 40)
        colar(fr, A, W / 2, ya, min(_p(t, 0.05, 0.5), ka), "baixo" if t < 0.6 else None)
        if t > meio - 0.3:      # risco sobre A
            yl = ya + A.height * 0.45
            linha(d, W / 2 - A.width / 2 - 10, yl, W / 2 + A.width / 2 + 10, yl, _p(t, meio - 0.3, 0.4), T["acento"], 6)
        ks = _p(t, meio, 0.4)
        if ks > 0:                      # seta desenhada (sem depender de símbolo da fonte)
            linha(d, W / 2, cy - 10, W / 2, cy + 50, ks, T["suave"], 4)
            if ks >= 1:
                d.polygon([(W / 2 - 14, cy + 40), (W / 2 + 14, cy + 40), (W / 2, cy + 62)], fill=T["suave"])
        colar(fr, B, W / 2, cy + 80, _p(t, meio + 0.2, 0.7), "baixo")
    return quadro


def t_causa_efeito(D, dur, T):
    """Causa em cima → linha que se desenha → efeito embaixo, com etiqueta no meio."""
    fc, lc = caber(str(D.get("causa", "")), "serif", 110, LARG - 20, 3, 50)
    fe, le = caber(str(D.get("efeito", "")), "serif", 120, LARG - 20, 3, 50)
    C = camada_texto(lc, fc, T["tinta"])
    E = camada_texto(le, fe, T["acento"])
    lig = rotulo(D.get("ligacao") or "leva a", T["suave"], 30)
    y1 = TOPO + 40
    y2 = BAIXO - E.height - 40
    if W > H:
        fc, lc = caber(str(D.get("causa", "")), "serif", 96, int(W * 0.34), 3, 40)
        fe, le = caber(str(D.get("efeito", "")), "serif", 104, int(W * 0.32), 3, 40)
        C = camada_texto(lc, fc, T["tinta"])
        E = camada_texto(le, fe, T["acento"])
        cyh = int(H * 0.5)

        def quadro_h(fr, d, t):
            rc = rotulo(D.get("rotulo_causa") or "causa", T["suave"], 26)
            xc, xe = W * 0.23, W * 0.73
            colar(fr, rc, xc, cyh - C.height / 2 - 50, _p(t, 0, 0.4))
            colar(fr, C, xc, cyh - C.height / 2, _p(t, 0.05, 0.6), "baixo")
            xa, xb = xc + C.width / 2 + 30, xe - E.width / 2 - 40
            linha(d, xa, cyh, xb, cyh, _p(t, 0.7, 0.8), T["acento"], 5)
            if _p(t, 1.45, 0.2) > 0:
                d.polygon([(xb - 4, cyh - 16), (xb - 4, cyh + 16), (xb + 22, cyh)], fill=T["acento"])
            colar(fr, lig, (xa + xb) / 2, cyh - 50, _p(t, 1.0, 0.5))
            colar(fr, E, xe, cyh - E.height / 2, _p(t, 1.5, 0.7), "baixo")
        return quadro_h

    def quadro(fr, d, t):
        rc = rotulo(D.get("rotulo_causa") or "causa", T["suave"], 30)
        colar(fr, rc, W / 2, y1 - 60, _p(t, 0, 0.4))
        colar(fr, C, W / 2, y1, _p(t, 0.05, 0.6), "baixo")
        ya, yb = y1 + C.height + 40, y2 - 50
        linha(d, W / 2, ya, W / 2, yb, _p(t, 0.7, 0.9), T["acento"], 5)
        if _p(t, 1.5, 0.2) > 0:       # ponta da seta
            d.polygon([(W / 2 - 18, yb - 22), (W / 2 + 18, yb - 22), (W / 2, yb + 4)], fill=T["acento"])
        colar(fr, lig, W / 2 + 120, (ya + yb) / 2 - 20, _p(t, 1.0, 0.5))
        colar(fr, E, W / 2, y2, _p(t, 1.5, 0.7), "baixo")
    return quadro


def t_dado(D, dur, T):
    """Número protagonista que conta até o valor, com barra/anel e rótulo."""
    import re as _re
    bruto = str(D.get("numero", "")).strip()
    m = _re.match(r"^([^\d\-]*)(-?[\d.,]+)(.*)$", bruto)
    pre, num_s, suf = (m.group(1), m.group(2), m.group(3)) if m else ("", "", bruto)
    try:
        alvo = float(num_s.replace(".", "").replace(",", ".")) if num_s else None
    except ValueError:
        alvo = None
    dec = 1 if (num_s and "," in num_s) else 0
    frot, lrot = caber(str(D.get("rotulo", "")), "serif", 70, LARG - 20, 2, 36)
    R = camada_texto(lrot, frot, T["tinta"]) if D.get("rotulo") else None
    fct, lct = caber(str(D.get("contexto", "")), "sans_l", 42, LARG - 40, 2, 28)
    Cx = camada_texto(lct, fct, T["suave"]) if D.get("contexto") else None
    pct = alvo if (alvo is not None and "%" in suf and 0 <= alvo <= 100) else None
    fn = fonte("serif", 300 if len(bruto) <= 4 else 220 if len(bruto) <= 7 else 150)
    cy = int(H * 0.40)

    def quadro(fr, d, t):
        k = _eout(_p(t, 0.1, max(0.8, dur * 0.45)))
        if alvo is not None:
            v = alvo * k
            s = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") if alvo >= 1000 or dec else f"{v:.0f}"
            txt = pre + s + suf
        else:
            txt = bruto
        lay = camada_texto([txt], fn, T["tinta"])
        colar(fr, lay, W / 2, cy - lay.height / 2, _p(t, 0, 0.3))
        yb = cy + lay.height / 2 + 30
        if pct is not None:
            d.rectangle([X0 + 140, yb, X0 + 940, yb + 14], fill=T["linha"])
            d.rectangle([X0 + 140, yb, X0 + 140 + 800 * pct / 100 * k, yb + 14], fill=T["acento"])
        else:
            linha(d, W / 2 - 140, yb + 7, W / 2 + 140, yb + 7, _p(t, 0.3, 0.6), T["acento"], 5)
        tr = 0.1 + max(0.8, dur * 0.45) * 0.7      # o rótulo entra quando o número já está chegando no valor
        if R:
            colar(fr, R, W / 2, yb + 60, _p(t, tr, 0.6), "baixo")
        if Cx:
            colar(fr, Cx, W / 2, yb + 80 + (R.height if R else 0), _p(t, tr + 0.45, 0.6))
    return quadro


def t_espectro(D, dur, T):
    """Régua entre dois polos (ex.: sombra ↔ luz) com marcador que desliza até a posição."""
    esq, dir_ = str(D.get("esquerda", "")), str(D.get("direita", ""))
    try:
        pos = _c(float(D.get("posicao", 0.5)))
    except (TypeError, ValueError):
        pos = 0.5
    fe = fonte("serif", 64)
    LE, LD = camada_texto([esq], fe, T["tinta"]), camada_texto([dir_], fe, T["tinta"])
    tit = None
    if D.get("titulo"):
        ft, lt = caber(D["titulo"], "serif", 100, LARG + 20, 2, 50)
        tit = camada_texto(lt, ft, T["tinta"])
    nota = D.get("marcador")
    cy = int(H * 0.45)
    x0, x1 = X0 + 130, X0 + 1080 - 130

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, TOPO + 20, _p(t, 0, 0.6), "baixo")
        k = _p(t, 0.3, 0.8)
        # barra em degradê do suave ao acento
        n = int((x1 - x0) * _eout(k))
        for i in range(0, n, 6):
            c = tuple(int(T["suave"][j] + (T["acento"][j] - T["suave"][j]) * (i / (x1 - x0))) for j in range(3))
            d.rectangle([x0 + i, cy - 6, x0 + i + 6, cy + 6], fill=c)
        for j in range(11):
            if _p(t, 0.3 + j * 0.05, 0.2) > 0:
                xx = x0 + (x1 - x0) * j / 10
                d.line([xx, cy + 20, xx, cy + (40 if j % 5 == 0 else 30)], fill=T["suave"], width=3)
        colar(fr, LE, x0 + LE.width / 2 - 10, cy + 70, _p(t, 0.6, 0.5))
        colar(fr, LD, x1 - LD.width / 2 + 10, cy + 70, _p(t, 0.8, 0.5))
        km = _eio(_p(t, 1.1, max(0.6, dur * 0.35)))
        xm = x0 + (x1 - x0) * (0.5 + (pos - 0.5) * km)
        if t > 1.0:
            d.ellipse([xm - 22, cy - 22, xm + 22, cy + 22], fill=T["acento"], outline=T["fundo"], width=6)
            if nota:
                rn = camada_texto([str(nota)], fonte("sans", 48), T["acento"])
                colar(fr, rn, xm, cy - 110, _p(t, 1.3, 0.4))
    return quadro


def t_linha_tempo(D, dur, T):
    """Linha vertical que se desenha; datas e textos aparecem em sequência."""
    itens = [i for i in (D.get("itens") or []) if isinstance(i, dict)][:5]
    fdata, ftx = fonte("serif", 84), fonte("serif", 54)
    lays = []
    for it in itens:
        dt = camada_texto([str(it.get("data", ""))], fdata, T["acento"])
        tx = camada_texto(quebrar(str(it.get("texto", "")), ftx, 680, 2), ftx, T["tinta"], alinhar="esq")
        lays.append((dt, tx))
    tit = rotulo(D.get("titulo"), T["suave"]) if D.get("titulo") else None
    y0, y1 = TOPO + 90, BAIXO - 40
    passo = (y1 - y0) / max(1, len(lays))
    xl = X0 + 290

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, TOPO - 20, _p(t, 0, 0.5))
        linha(d, xl, y0, xl, y1, _p(t, 0.1, dur * 0.6), T["linha"], 4)
        for i, (dt, tx) in enumerate(lays):
            yy = y0 + passo * i + 20
            ki = _p(t, 0.3 + i * (dur * 0.55 / max(1, len(lays))), 0.5)
            if ki > 0:
                r = 14 * _eout(ki)
                d.ellipse([xl - r, yy + 30 - r, xl + r, yy + 30 + r], fill=T["acento"])
                colar(fr, dt, xl - 50 - dt.width / 2, yy, ki)
                if ki > 0:
                    lay, _ = revelar(tx, ki, "esq")
                    if lay:
                        fr.alpha_composite(lay, (xl + 50, int(yy + 12)))
    return quadro


def t_processo(D, dur, T):
    """Etapas numeradas que aparecem em sequência, ligadas por um fio."""
    passos = [str(p) for p in (D.get("passos") or []) if p][:4]
    fnum, ftx = fonte("serif", 96), fonte("serif", 58)
    lays = [(camada_texto([f"{i + 1:02d}"], fnum, T["acento"]),
             camada_texto(quebrar(p, ftx, 720, 2), ftx, T["tinta"], alinhar="esq")) for i, p in enumerate(passos)]
    tit = None
    if D.get("titulo"):
        ft, lt = caber(D["titulo"], "serif", 90, LARG + 20, 2, 46)
        tit = camada_texto(lt, ft, T["tinta"])
    y0 = TOPO + (tit.height + 80 if tit else 40)
    passo = (BAIXO - y0) / max(1, len(lays))

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, TOPO, _p(t, 0, 0.6), "baixo")
        for i, (n, tx) in enumerate(lays):
            yy = y0 + passo * i
            ki = _p(t, 0.3 + i * (dur * 0.6 / max(1, len(lays))), 0.6)
            colar(fr, n, X0 + 150, yy, ki)
            if ki > 0:
                lay, _ = revelar(tx, ki, "esq")
                if lay:
                    fr.alpha_composite(lay, (X0 + 250, int(yy + 22)))
            if i < len(lays) - 1:
                linha(d, X0 + 150, yy + n.height + 6, X0 + 150, yy + passo - 10, _p(t, 0.6 + i * (dur * 0.6 / len(lays)), 0.5),
                      T["linha"], 3)
    return quadro


def t_lista(D, dur, T):
    """Lista curta (ex.: escola, polícia, igreja, hospital); um item pode ganhar destaque."""
    itens = [str(x) for x in (D.get("itens") or []) if x][:5]
    try:
        dest = int(D.get("destaque")) if D.get("destaque") is not None else None
    except (TypeError, ValueError):
        dest = None
    deitado = W > H
    f = fonte("serif", (72 if len(itens) <= 3 else 60) if deitado else (96 if len(itens) <= 4 else 80))
    lays = [camada_texto([x], f, T["acento"] if i == dest else T["tinta"]) for i, x in enumerate(itens)]
    tit = rotulo(D.get("titulo"), T["suave"]) if D.get("titulo") else None
    alt = sum(l.height for l in lays) + 40 * max(0, len(lays) - 1)
    y0 = int(H * 0.46 - alt / 2)
    y0 = max(y0, int(H * 0.08) + (110 if tit else 0))       # o título nunca sai pelo topo

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, y0 - 110, _p(t, 0, 0.5))
        yy = y0
        for i, l in enumerate(lays):
            ki = _p(t, 0.15 + i * min(0.45, dur * 0.5 / max(1, len(lays))), 0.5)
            colar(fr, l, W / 2, yy, ki, "baixo")
            if i == dest and ki >= 1:
                yl = yy + l.height + 4
                linha(d, W / 2 - l.width / 2, yl, W / 2 + l.width / 2, yl,
                      _p(t, 0.15 + i * min(0.45, dur * 0.5 / max(1, len(lays))) + 0.5, 0.5), T["acento"], 5)
            yy += l.height + 40
    return quadro


def t_citacao(D, dur, T):
    """Frase de impacto como citação: aspas grandes, texto em itálico revelado palavra por palavra."""
    frase = str(D.get("frase") or D.get("texto") or "")
    f, ls = caber(frase, "serif_it", 92, LARG - 20, 5, 48)
    alt = int(f.size * 1.2)
    autor = rotulo(D.get("autor"), T["suave"], 32) if D.get("autor") else None
    aspas = camada_texto(["“"], fonte("serif", 260), T["acento"])
    total_p = sum(len(l.split()) for l in ls)
    y0 = int(H * 0.42 - alt * len(ls) / 2)

    def quadro(fr, d, t):
        colar(fr, aspas, W / 2, y0 - 230, _p(t, 0, 0.5))
        vis = int(total_p * _p(t, 0.2, max(0.8, dur * 0.6))) + 1
        cont = 0
        for i, l in enumerate(ls):
            pals = l.split()
            mostrar = " ".join(pals[:max(0, vis - cont)])
            cont += len(pals)
            if mostrar:
                lay = camada_texto([mostrar], f, T["tinta"])
                x = W / 2 - f.getlength(l) / 2
                fr.alpha_composite(lay, (int(x), y0 + i * alt))
        if autor:
            colar(fr, autor, W / 2, y0 + alt * len(ls) + 50, _p(t, dur * 0.65, 0.5))
    return quadro


def t_conceito(D, dur, T):
    """Metáfora com 1–2 ícones e relação clara (dentro / sobre / fonte / contra). Sem ícone → None."""
    ia = _icone(D.get("icone_a"), 380, T["tinta"])
    ib = _icone(D.get("icone_b"), 300, T["acento"]) if D.get("icone_b") else None
    if ia is None or (D.get("icone_b") and ib is None):
        return None
    rel = str(D.get("relacao", "ao_lado"))
    fa = fonte("sans_m", 34)
    ra = rotulo(D.get("rotulo_a"), T["suave"], 32) if D.get("rotulo_a") else None
    rb = rotulo(D.get("rotulo_b"), T["acento"], 32) if D.get("rotulo_b") else None
    tit = None
    if D.get("titulo"):
        ft, lt = caber(D["titulo"], "serif", 100, LARG + 20, 2, 50)
        tit = camada_texto(lt, ft, T["tinta"])
    cy = int(H * 0.47)

    def quadro(fr, d, t):
        if tit:
            colar(fr, tit, W / 2, TOPO, _p(t, 0, 0.6), "baixo")
        if ib is None:
            colar(fr, ia, W / 2, cy - ia.height / 2, _p(t, 0.2, 0.7))
            if ra:
                colar(fr, ra, W / 2, cy + ia.height / 2 + 40, _p(t, 0.7, 0.5))
            return
        if rel == "dentro":         # B aparece dentro de um círculo que contém A
            r = 300
            k = _p(t, 0.2, 0.8)
            d.arc([W / 2 - r, cy - r, W / 2 + r, cy + r], -90, -90 + 360 * _eout(k), fill=T["linha"], width=5)
            colar(fr, ia, W / 2, cy - ia.height / 2, _p(t, 0.3, 0.6))
            colar(fr, ib, W / 2 + r * 0.75, cy - r * 0.9, _p(t, 1.0, 0.6))
        elif rel == "fonte":        # A emite linhas até B
            xa, xb = W * 0.28, W * 0.74
            colar(fr, ia, xa, cy - ia.height / 2, _p(t, 0.1, 0.6))
            for j in range(3):
                yy = cy - 60 + j * 60
                linha(d, xa + ia.width / 2 + 20, yy, xb - ib.width / 2 - 20, cy, _p(t, 0.7 + j * 0.15, 0.6), T["acento"], 3)
            colar(fr, ib, xb, cy - ib.height / 2, _p(t, 1.2, 0.6))
        elif rel == "sobre":        # A em cima pesando sobre B
            colar(fr, ia, W / 2, cy - ia.height - 40, _p(t, 0.1, 0.6))
            colar(fr, ib, W / 2, cy + 80, _p(t, 0.8, 0.6))
            linha(d, W / 2 - 200, cy + 30, W / 2 + 200, cy + 30, _p(t, 0.5, 0.5), T["linha"], 4)
        else:                       # lado a lado / contra
            xa, xb = W * 0.3, W * 0.7
            colar(fr, ia, xa, cy - ia.height / 2, _p(t, 0.1, 0.6))
            colar(fr, ib, xb, cy - ib.height / 2, _p(t, 0.7, 0.6))
            sinal = camada_texto(["≠" if rel == "contra" else "+"], fonte("serif", 110), T["suave"])
            colar(fr, sinal, W / 2, cy - sinal.height / 2, _p(t, 0.5, 0.4))
        if ra:
            colar(fr, ra, W * (0.3 if rel not in ("dentro", "sobre") else 0.5),
                  cy + (ia.height / 2 + 40 if rel not in ("sobre",) else -ia.height - 100), _p(t, 0.9, 0.5))
        if rb:
            colar(fr, rb, W * (0.7 if rel not in ("dentro", "sobre") else 0.5),
                  cy + (ib.height / 2 + 40 if rel not in ("sobre", "dentro") else ib.height + 110), _p(t, 1.3, 0.5))
    return quadro


def t_foco(D, dur, T):
    """Um elemento forte (ícone) + frase curta, com muito respiro. Sem ícone → None."""
    ic = _icone(D.get("icone"), 420, T["tinta"])
    if ic is None:
        return None
    f, ls = caber(str(D.get("texto", "")), "serif", 110, LARG, 2, 50)
    tx = camada_texto(ls, f, T["tinta"])
    eti = rotulo(D.get("etiqueta"), T["acento"]) if D.get("etiqueta") else None
    cy = int(H * 0.36)

    def quadro(fr, d, t):
        k = _eout(_p(t, 0.0, 0.9))
        lay = ic if k >= 1 else ic.resize((max(1, int(ic.width * (0.94 + 0.06 * k))),
                                            max(1, int(ic.height * (0.94 + 0.06 * k)))))
        colar(fr, lay, W / 2, cy - lay.height / 2, k)
        if eti:
            colar(fr, eti, W / 2, cy + ic.height / 2 + 50, _p(t, 0.6, 0.4))
        colar(fr, tx, W / 2, cy + ic.height / 2 + 120, _p(t, 0.7, 0.6), "baixo")
    return quadro


def t_documento(D, dur, T):
    """Foto/documento/mapa real em sangria (sem moldura): zoom lento até o ponto importante, destaque desenhado
    (círculo, sublinhado ou seta), legenda editorial e crédito."""
    caminho = D.get("imagem")
    if not caminho or not os.path.exists(caminho):
        return None
    foto = ImageOps.exif_transpose(Image.open(caminho)).convert("RGB")
    deitado = W > H
    # área da imagem: tela toda (horizontal) ou o alto da tela (vertical, a legenda do corte fica embaixo)
    ax, ay, aw, ah = (0, 0, W, H) if deitado else (0, 0, W, int(BAIXO - 300))
    sem = int(D.get("_seed", 0) or 0)
    ent = sem % 3                                   # entrada: 0 fade, 1 cortina da esquerda, 2 máscara que se abre
    afasta = (sem // 3) % 2 == 1 and not D.get("foco")    # foto de banco: às vezes começa perto e se afasta
    rnd = random.Random(sem)
    alvo_padrao = [0.5, 0.45] if D.get("foco") else [rnd.uniform(0.35, 0.65), rnd.uniform(0.35, 0.6)]
    try:
        fx, fy = [float(v) for v in (D.get("foco") or alvo_padrao)][:2]
    except (TypeError, ValueError):
        fx, fy = 0.5, 0.45
    fx, fy = _c(fx, 0.1, 0.9), _c(fy, 0.1, 0.9)
    zf = 1.22
    esc = max(aw / foto.width, ah / foto.height) * zf
    base = foto.resize((max(aw, int(foto.width * esc)), max(ah, int(foto.height * esc))), Image.BILINEAR)
    marca = str(D.get("marcacao", "circulo" if D.get("foco") else "sublinhado"))
    larg_leg = min(LARG, 1100) if deitado else LARG
    f, ls = caber(str(D.get("legenda", "")), "serif", 76 if deitado else 70, larg_leg, 2, 40)
    leg = camada_texto(ls, f, (246, 240, 230) if deitado else T["tinta"], alinhar="esq" if deitado else "centro") \
        if D.get("legenda") else None
    eti = rotulo(D.get("etiqueta"), T["acento"], 30) if D.get("etiqueta") else None
    cred = camada_texto([str(D.get("credito", ""))[:100]], fonte("sans_l", 22),
                        (200, 196, 188) if deitado else T["suave"]) if D.get("credito") else None
    # degradê para a legenda ficar legível sobre a foto (horizontal)
    scrim = None
    if deitado:
        g = Image.new("L", (1, H))
        for y in range(H):
            g.putpixel((0, y), int(215 * _c((y / H - 0.45) / 0.55) ** 1.5))
        scrim = Image.new("RGBA", (W, H), (10, 8, 14, 255))
        scrim.putalpha(g.resize((W, H)))

    def quadro(fr, d, t):
        k = _eio(_p(t, 0, dur))
        if afasta:
            k = 1 - k
        z = 1 + (zf - 1) * k                       # aproxima do ponto importante aos poucos
        vis_w = base.width / z
        vis_h = vis_w * ah / aw
        if vis_h > base.height / z:
            vis_h = base.height / z
            vis_w = vis_h * aw / ah
        cx = base.width / 2 + (fx * base.width - base.width / 2) * k
        cy = base.height / 2 + (fy * base.height - base.height / 2) * k
        x0 = _c(cx - vis_w / 2, 0, base.width - vis_w)
        y0 = _c(cy - vis_h / 2, 0, base.height - vis_h)
        rec = base.crop((int(x0), int(y0), int(x0 + vis_w), int(y0 + vis_h))).resize((aw, ah), Image.BILINEAR)
        ka = _p(t, 0, 0.35 if ent == 0 else 0.6)
        lay = rec.convert("RGBA")
        if ka < 1 and ent == 1:                    # cortina: a foto entra da esquerda para a direita
            w_ = max(1, int(aw * _eout(ka)))
            lay = lay.crop((0, 0, w_, ah))
        elif ka < 1 and ent == 2:                  # máscara: um recorte se abre a partir do centro
            e = 0.35 + 0.65 * _eout(ka)
            mw, mh = max(1, int(aw * e)), max(1, int(ah * e))
            m = Image.new("L", (aw, ah), 0)
            ImageDraw.Draw(m).rounded_rectangle([(aw - mw) // 2, (ah - mh) // 2, (aw + mw) // 2, (ah + mh) // 2],
                                                radius=int(40 * (1 - ka)), fill=int(255 * _c(ka * 2)))
            lay.putalpha(m)
        elif ka < 1:
            lay.putalpha(int(255 * ka))
        fr.alpha_composite(lay, (ax, ay))
        # posição do ponto de foco na tela
        px = ax + (fx * base.width - x0) / vis_w * aw
        py = ay + (fy * base.height - y0) / vis_h * ah
        km = _p(t, dur * 0.35, 0.8)
        if km > 0 and marca == "circulo":
            r = min(aw, ah) * 0.16
            d.arc([px - r * 1.25, py - r, px + r * 1.25, py + r], -100, -100 + 360 * _eout(km), fill=T["acento"], width=6)
        elif km > 0 and marca == "seta":
            sx, sy = px + min(aw, ah) * 0.28, py - min(aw, ah) * 0.22
            linha(d, sx, sy, px + 30, py - 24, km, T["acento"], 6)
        if scrim is not None:
            fr.alpha_composite(scrim)
        if deitado:
            xl = int(W * 0.06)
            if eti:
                fr.alpha_composite(alfa(eti, _p(t, 0.3, 0.4)), (xl, int(H - 300)))
            if leg:
                lay, _ = revelar(leg, _p(t, 0.5, 0.7), "baixo")
                if lay:
                    fr.alpha_composite(lay, (xl, int(H - 250)))
                if marca == "sublinhado":
                    linha(d, xl, H - 250 + leg.height + 6, xl + min(leg.width, 420), H - 250 + leg.height + 6,
                          _p(t, 1.0, 0.6), T["acento"], 5)
            if cred:
                fr.alpha_composite(cred, (int(W - cred.width - 40), int(H - 50)))
        else:
            y = ay + ah + 40
            if eti:
                colar(fr, eti, W / 2, y, _p(t, 0.3, 0.4))
                y += 60
            if leg:
                colar(fr, leg, W / 2, y, _p(t, 0.5, 0.7), "baixo")
                if marca == "sublinhado":
                    yl = y + leg.height + 8
                    linha(d, W / 2 - 140, yl, W / 2 + 140, yl, _p(t, 1.0, 0.6), T["acento"], 5)
            if cred:
                fr.alpha_composite(cred, (int(W - cred.width - 30), int(ay + ah - 34)))
    return quadro


TEMPLATES = {
    "palavra_chave": t_palavra_chave, "contraste": t_contraste, "comparacao": t_comparacao,
    "transformacao": t_transformacao, "causa_efeito": t_causa_efeito, "dado": t_dado, "espectro": t_espectro,
    "linha_tempo": t_linha_tempo, "processo": t_processo, "lista": t_lista, "citacao": t_citacao,
    "conceito": t_conceito, "foco": t_foco, "documento": t_documento,
}

try:                                  # mini cenas (estética nova): bonecos, bateria, escada, alvos, caminho...
    from . import cenas as _cenas
except ImportError:  # pragma: no cover
    import cenas as _cenas
TEMPLATES.update(_cenas.CENAS)
CATALOGO = CATALOGO + list(_cenas.CENAS)


# ------------------------------------------------------------------ zona segura e simplificação
def _medir(quadro, dur):
    """Linhas (y) ocupadas por informação: topo e base, ignorando faixas que cobrem a largura toda (fundos/cortinas)."""
    top, bot = H, 0
    for t in (dur * 0.5, dur * 0.8, max(0.0, dur - 0.05)):
        fr = Image.new("RGBA", (W, int(H * 1.6)), (0, 0, 0, 0))      # tela mais alta: enxerga o que vazaria
        quadro(fr, ImageDraw.Draw(fr), t)
        arr = np.asarray(fr)[:, ::3].astype(np.int16)
        # cor das duas bordas de cada linha (fundo, cortina, painel): o que destoa das duas é informação
        dif = (np.abs(arr - arr[:, :1]).max(axis=2) > 50) & (np.abs(arr - arr[:, -1:]).max(axis=2) > 50)                      # pixel que destoa = informação (texto, seta…)
        cob = dif.mean(axis=1)
        linhas = np.where((cob > 0.002) & (cob < 0.85))[0]
        if len(linhas):
            top, bot = min(top, int(linhas[0])), max(bot, int(linhas[-1]))
    return top, bot


SECUNDARIOS = ("apoio", "contexto", "autor", "etiqueta", "marcador", "conector")


def _simplificar(dados, passo):
    """Passo 1: tira textos de apoio. Passo 2: encurta listas e tira título. Nunca diminui a letra até ficar ilegível."""
    d = {k: v for k, v in dados.items() if k not in SECUNDARIOS}
    for lado in ("a", "b"):
        if isinstance(d.get(lado), dict) and passo >= 1:
            d[lado] = {k: v for k, v in d[lado].items() if k != "texto" or passo < 2}
            if isinstance(d[lado].get("itens"), list):
                d[lado]["itens"] = d[lado]["itens"][:3 if passo == 1 else 2]
    for k in ("itens", "passos"):
        if isinstance(d.get(k), list):
            d[k] = d[k][:4 if passo == 1 else 3]
    if passo >= 2:
        d.pop("titulo", None)
    return d


def _na_zona_segura(fn, nome, dados, dur, T, quadro, log=None):
    """Cortes (vertical): garante que nada importante entre na área da legenda. Devolve (quadro, usado, desloc)."""
    usado = nome
    limite = LIMITE_LEGENDA if H > W else H - int(H * 0.08)
    margem = MARGEM_TOPO if H > W else int(H * 0.08)
    for passo in range(3):
        top, bot = _medir(quadro, dur)
        if bot <= limite:
            return quadro, usado, 0
        sobe = bot - limite + 10
        if top - sobe >= margem:                       # cabe subindo a composição inteira
            return quadro, usado, sobe
        if passo == 2:
            break
        novo = fn(_simplificar(dados, passo + 1), dur, T) if fn else None
        if novo is None:
            break
        quadro = novo
    txt = _texto_principal(dados)
    if not txt:
        return None, None, 0
    q = t_palavra_chave({"texto": txt}, dur, T)
    return q, "palavra_chave", 0


def _texto_principal(dados):
    for k in ("texto", "titulo", "frase", "legenda", "para", "efeito"):
        if dados.get(k):
            return str(dados[k])
    b = dados.get("b")
    return str(b.get("rotulo")) if isinstance(b, dict) and b.get("rotulo") else ""


def render(nome, dados, dur, saida, tema="escuro", seed=0, largura=1080, altura=1920, fundo_img=None, movimento=None):
    """Desenha o template. Devolve o nome do template usado (pode cair para 'palavra_chave');
    devolve None se nem a palavra-chave tiver texto (aí o B-roll não deve existir: fica o rosto).
    largura/altura: 1080x1920 (cortes) ou 1920x1080 (YouTube, tela cheia).
    fundo_img: quadro do próprio vídeo, que vira fundo desfocado e tingido (fundo integrado).
    movimento: câmera lenta ("aproxima", "afasta", "pan_esq", "pan_dir", "sobe"); None = escolhe pelo seed.
    A cena tem ENTRADA (elementos em etapas), DESENVOLVIMENTO e SAÍDA (o conteúdo sai antes do corte)."""
    final = (int(largura), int(altura))
    if largura > altura and nome != "documento":
        _canvas(1440, 810)          # YouTube: desenha numa tela menor e amplia → tudo fica proporcionalmente maior
    else:
        _canvas(largura, altura)
    try:
        tema = tema if tema in TEMAS else "escuro"
        T = TEMAS[tema]
        dur = max(2.0, float(dur))
        dados = dict(dados or {})
        dados.setdefault("_seed", seed)
        fn = TEMPLATES.get(nome)
        quadro = fn(dados, dur, T) if fn else None
        usado = nome
        if quadro is None:                               # faltou ícone/imagem/dado: composição tipográfica
            txt = dados.get("texto") or dados.get("titulo") or dados.get("frase") or dados.get("legenda")
            if not txt:
                return None
            quadro = t_palavra_chave({"texto": txt, "apoio": dados.get("apoio"), "etiqueta": dados.get("etiqueta")},
                                     dur, T)
            usado = "palavra_chave"
            fn = t_palavra_chave
        desloc = 0
        if usado != "documento":       # cortes: fora da legenda; YouTube: nada cortado na borda de baixo
            quadro, novo_usado, desloc = _na_zona_segura(fn, usado, dados, dur, T, quadro)
            if quadro is None:
                return None
            usado = novo_usado or usado
        bg = fundo(tema, seed)
        if fundo_img and os.path.exists(fundo_img) and usado != "documento" and not T.get("nova"):
            try:
                q = ImageOps.fit(Image.open(fundo_img).convert("L"), (W, H)).filter(ImageFilter.GaussianBlur(28))
                q = ImageOps.colorize(q, black=tuple(int(c * 0.5) for c in T["fundo"]), white=T["tinta"])
                # o vídeo dela aparece bem de leve por trás, sem a cor da luz do quarto (não suja a paleta)
                bg = Image.blend(q.convert("RGBA"), bg, 0.93 if _claro(T) else 0.82)
            except Exception:
                pass
        mov = movimento if movimento in MOVIMENTOS else MOVIMENTOS[seed % len(MOVIMENTOS)]
        if usado == "documento":
            zoom = 0                                     # a foto já tem o próprio movimento
        else:
            zoom = 0.05 if H > W else 0.07               # no vertical o zoom é menor (respeita a zona da legenda)
        if usado == "documento" and (W, H) != final:      # caiu para documento: volta à resolução cheia
            _canvas(*final)
            quadro = fn(dados, dur, T)
            bg = fundo(tema, seed)
        out = Saida(saida, dur, zoom=zoom, movimento=mov, final=final)
        n = int(round(dur * FPS))
        sai = 0.0 if usado == "documento" else min(0.35, dur * 0.1)
        try:
            for i in range(n):
                t = i / FPS
                lay = Image.new("RGBA", (W, H + desloc + 40), (0, 0, 0, 0))
                quadro(lay, ImageDraw.Draw(lay), t)
                if T.get("nova") and usado != "documento":
                    lay = brilho(lay)
                ks = _eio(_p(t, dur - sai, sai)) if sai else 0.0
                if ks > 0:                               # saída: o conteúdo sobe um pouco e some antes do corte
                    lay = alfa(lay, 1 - ks)
                dy = desloc + int(28 * ks)
                fr = bg.copy()
                fr.alpha_composite(lay.crop((0, dy, W, dy + H)))
                out.quadro(fr)
        finally:
            out.fechar()
        return usado
    finally:
        _canvas(1080, 1920)
