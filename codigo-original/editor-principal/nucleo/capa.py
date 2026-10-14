"""Capas (thumbnails) do YouTube: a IA olha quadros do vídeo, escolhe as melhores expressões e o lado livre;
o editor monta 3 capas 1280x720 com 2 a 4 palavras grandes (uma em destaque), para o Test & Compare."""
import io, json, os, subprocess
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from .util import FFMPEG, FONTES, ler_config, probe
from . import ia

CW, CH = 1280, 720
ROXO = (34, 16, 58)
OURO = (255, 205, 60)

PROMPT = """Você é designer de capas de YouTube. A imagem mostra quadros numerados do vídeo da apresentadora.
Escolha os {n} quadros DIFERENTES que dariam a melhor capa: expressão forte e clara (surpresa, convicção, ironia,
sorriso marcante), olhos abertos olhando para a câmera, boca numa expressão bonita (não no meio de uma sílaba feia),
imagem nítida. Para cada um, diga de que lado da imagem há mais espaço livre para um texto grande ("esquerda" ou
"direita", o lado oposto ao rosto dela).
Responda em JSON: {{"capas": [{{"numero": 3, "lado": "esquerda"}}]}}"""


def _quadro(video, t, w=None):
    vf = ["-vf", f"scale={w}:-2"] if w else []
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", *vf,
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True,
                       **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def _folha(ims):
    tw, th, col = 320, 180, 4
    lin = (len(ims) + col - 1) // col
    folha = Image.new("RGB", (col * (tw + 8), lin * (th + 34)), "white")
    d = ImageDraw.Draw(folha)
    f = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), 24)
    for i, im in enumerate(ims):
        x, y = (i % col) * (tw + 8), (i // col) * (th + 34)
        folha.paste(im.resize((tw, th)), (x, y))
        d.text((x + tw / 2, y + th + 16), str(i + 1), font=f, fill=(200, 0, 60), anchor="mm")
    b = io.BytesIO()
    folha.save(b, "PNG")
    return b.getvalue()


def _linhas(texto, F, larg):
    palavras = texto.split()
    linhas, cur = [], ""
    for p in palavras:
        t = (cur + " " + p).strip()
        if F.getlength(t) <= larg or not cur:
            cur = t
        else:
            linhas.append(cur)
            cur = p
    if cur:
        linhas.append(cur)
    return linhas


def montar(foto, texto, destaque, lado, saida):
    """foto: quadro do vídeo (RGB). Texto grande do lado livre, palavra em destaque em amarelo."""
    im = foto.resize((CW, CH))
    # aproxima um pouco puxando o rosto para o lado oposto ao texto (rosto maior)
    z = 1.25
    cw, ch = int(CW / z), int(CH / z)
    x0 = 0 if lado == "esquerda" else CW - cw      # texto à esquerda: o rosto vai para a direita (e vice-versa)
    im = im.crop((x0, (CH - ch) // 2, x0 + cw, (CH - ch) // 2 + ch)).resize((CW, CH), Image.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im = ImageEnhance.Color(im).enhance(1.18)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    # degradê escuro do lado do texto
    grad = Image.new("L", (CW, 1))
    for x in range(CW):
        k = x / CW if lado == "direita" else 1 - x / CW
        grad.putpixel((x, 0), int(235 * max(0.0, min(1.0, (k - 0.35) / 0.4)) ** 1.2))
    sombra = Image.new("RGB", (CW, CH), ROXO)
    im = Image.composite(sombra, im, grad.resize((CW, CH)))
    d = ImageDraw.Draw(im)
    texto = " ".join((texto or "").upper().split()[:5])
    destaque = (destaque or "").upper().strip()
    larg = CW * 0.46
    tam = 150
    while tam > 70:
        F = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), tam)
        linhas = _linhas(texto, F, larg)
        if len(linhas) <= 3 and max(F.getlength(l) for l in linhas) <= larg:
            break
        tam -= 6
    alt = tam * 1.08
    y = (CH - alt * len(linhas)) / 2
    x_base = CW * 0.04 if lado == "esquerda" else CW * 0.50
    for l in linhas:
        x = x_base
        for p in l.split():
            cor = OURO if destaque and p.strip(".,!?") == destaque.strip(".,!?") else (255, 255, 255)
            d.text((x, y), p, font=F, fill=cor, stroke_width=max(4, tam // 14), stroke_fill=(12, 6, 22))
            x += F.getlength(p + " ")
        y += alt
    im.save(saida, "JPEG", quality=92)


def gerar(pasta, log=print, n=3):
    video = os.path.join(pasta, "youtube.mp4")
    f_meta = os.path.join(pasta, "youtube_meta.json")
    meta = json.load(open(f_meta, encoding="utf-8")) if os.path.exists(f_meta) else {}
    extra_f = os.path.join(pasta, "youtube_extra.json")
    extra = json.load(open(extra_f, encoding="utf-8")) if os.path.exists(extra_f) else {}
    dur = probe(video)["dur"]
    ini, fim = float(extra.get("teaser", 0)) + 2, float(extra.get("fim_conteudo", dur)) - 2
    tempos = [ini + (fim - ini) * (k + 0.5) / 16 for k in range(16)]
    quadros = [(t, _quadro(video, t, 640)) for t in tempos]
    quadros = [(t, q) for t, q in quadros if q is not None]
    escolhas = []
    try:
        resp, modelo = ia.pedir("capas", PROMPT.format(n=n), f"{len(quadros)} quadros numerados.", temperatura=0.3,
                                log=log, imagens=[_folha([q for _, q in quadros])], forte=True)
        for e in resp.get("capas", []):
            k = int(e.get("numero", 0)) - 1
            if 0 <= k < len(quadros) and k not in [x[0] for x in escolhas]:
                escolhas.append((k, "direita" if str(e.get("lado", "")).lower().startswith("d") else "esquerda"))
        log(f"IA ({modelo}) escolheu {len(escolhas)} quadro(s) para as capas")
    except Exception as e:
        log(f"(não deu para a IA escolher os quadros das capas: {e}; usando quadros do meio)")
    for k in (len(quadros) // 4, len(quadros) // 2, 3 * len(quadros) // 4):
        if len(escolhas) >= n:
            break
        if k not in [x[0] for x in escolhas]:
            escolhas.append((k, "esquerda"))
    textos = [c for c in (meta.get("capas") or []) if isinstance(c, dict) and c.get("texto")]
    if not textos:
        textos = [{"texto": " ".join((meta.get("titulo") or "").split()[:4]), "destaque": ""}]
    feitas = []
    for i, (k, lado) in enumerate(escolhas[:n]):
        t = quadros[k][0]
        foto = _quadro(video, t)
        if foto is None:
            continue
        tx = textos[i % len(textos)]
        arq = os.path.join(pasta, f"capa_{i + 1}.jpg")
        montar(foto, tx["texto"], tx.get("destaque", ""), lado, arq)
        feitas.append(arq)
    log(f"{len(feitas)} capa(s) prontas para o Test & Compare")
    return feitas
