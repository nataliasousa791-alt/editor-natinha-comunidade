"""B-roll com vídeo real (Pexels ou Pixabay, grátis): busca clipes, a IA OLHA as opções e escolhe (todas de uma vez),
o editor baixa, corta no tamanho (em pé para os cortes, deitado para o YouTube), puxa a cor para o roxo/dourado
da Natinha e coloca o título por cima."""
import io, json, os, re, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .util import FFMPEG, FONTES, ler_config, run
from . import ia

UA = {"User-Agent": "EditorNatinha/1.0"}

PROMPT_ESCOLHA = """Você é uma editora de vídeo MUITO exigente. Para cada B-roll há UMA imagem com opções numeradas de vídeos
(um quadro de cada) para cobrir a tela enquanto ela fala a frase indicada. Escolha um vídeo SÓ se a cena mostra
LITERALMENTE o que ela está dizendo (a pessoa/ação/lugar/objeto da frase) — quem vê tem que ligar a imagem à fala na hora.
Responda 0 (nenhum) se as opções forem genéricas ou só "de clima": paisagem, céu, flor, ponte, prédio, textura, luzes,
objeto qualquer, cena abstrata, ou algo que só combina com UMA palavra solta. Na dúvida, 0 — vira desenho, que é melhor
que uma imagem aleatória. Evite também texto/logo na imagem e cenas feias ou confusas.
Responda em JSON: {"escolhas": [{"broll": 1, "numero": 3}]}"""


def chave():
    return (ler_config().get("pexels_chave") or os.environ.get("PEXELS_API_KEY") or "").strip()


def chave_pixabay():
    return (ler_config().get("pixabay_chave") or os.environ.get("PIXABAY_API_KEY") or "").strip()


def tem_fonte():
    return bool(chave() or chave_pixabay())


def _get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


_EPOCA = {"ancient", "antique", "ancestral", "mesopotamia", "mesopotamian", "sumer", "sumerian", "sumerians", "babylon",
          "babylonian", "assyrian", "egypt", "egyptian", "pharaoh", "roman", "greek", "greece", "medieval",
          "prehistoric", "caveman", "historical", "archaeology", "archaeological", "cuneiform", "ziggurat",
          "biblical", "antiquity", "mythology"}
_EPOCA_ITEM = _EPOCA | {"history", "museum", "artifact", "artefact", "ruins", "ruin", "temple", "pyramid", "pyramids",
                        "clay", "tablet", "tribal", "tribe", "old", "primitive", "myth", "rome", "iraq", "desert"}
_VAZIAS = {"a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "to", "for", "from", "by", "scene", "view",
           "shot", "close", "up", "closeup", "people", "person", "man", "woman", "walking", "standing", "looking"}


def _palavras(t):
    return {w for w in re.split(r"[^a-z]+", str(t or "").lower()) if len(w) > 2}


def _combina(descricao, consulta):
    """Filtro sem IA contra imagem 'bonita e errada': a descrição do vídeo/foto (tags ou nome da página) precisa ter
    pelo menos uma palavra concreta da busca; e se a busca é de época/história ("ancient mesopotamia…"), o item
    também precisa ser de época (um mercado de Bangkok de hoje não ilustra a Suméria)."""
    d = _palavras(descricao)
    if not d:
        return True                                   # sem descrição: deixa a IA avaliar
    q = _palavras(consulta)
    concretas = {w for w in q - _VAZIAS if w not in _GENERICAS}
    if concretas and not (d & concretas) and not any(w.rstrip("s") in {x.rstrip("s") for x in d} for w in concretas):
        return False
    if q & _EPOCA and not (d & _EPOCA_ITEM):
        return False
    return True


def buscar(consultas, dur_min, limite=9, deitado=False):
    """Pexels: candidatos com duração suficiente: [{id, imagem, arquivo, autor, url, duracao, site}]."""
    k = chave()
    vistos, out = set(), []
    if not k:
        return out
    for q in consultas[:3]:
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": q, "orientation": "landscape" if deitado else "portrait", "per_page": 8, "size": "medium"})
        try:
            dados = json.loads(_get(url, {"Authorization": k}))
        except Exception:
            continue
        for v in dados.get("videos", []):
            if v.get("id") in vistos or float(v.get("duration", 0)) < dur_min + 0.6:
                continue
            if not _combina(str(v.get("url", "")).rstrip("/").split("/")[-1], q):
                continue
            ok = (lambda f: (f.get("width") or 0) > (f.get("height") or 0) and (f.get("height") or 0) >= 700) if deitado else \
                 (lambda f: (f.get("height") or 0) > (f.get("width") or 0) and (f.get("height") or 0) >= 960)
            arqs = [f for f in v.get("video_files", []) if f.get("link") and ok(f)]
            if not arqs:
                continue
            alvo = 1080 if deitado else 1920
            arqs.sort(key=lambda f: abs((f.get("height") or 0) - alvo))
            vistos.add(v["id"])
            out.append({"id": v["id"], "imagem": v.get("image"), "arquivo": arqs[0]["link"],
                        "autor": (v.get("user") or {}).get("name", ""), "url": v.get("url", ""),
                        "duracao": float(v.get("duration", 0)), "site": "Pexels"})
            if len(out) >= limite:
                return out
    return out


def buscar_pixabay(consultas, dur_min, limite=9, deitado=False):
    """Pixabay: vídeos grátis (a maioria deitada; para os cortes o editor recorta o meio)."""
    k = chave_pixabay()
    if not k:
        return []
    vistos, bons, outros = set(), [], []
    for q in consultas[:3]:
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": k, "q": q[:100], "per_page": 12, "safesearch": "true", "video_type": "film"})
        try:
            dados = json.loads(_get(url))
        except Exception:
            continue
        for h in dados.get("hits", []):
            if h.get("id") in vistos or float(h.get("duration", 0)) < dur_min + 0.6:
                continue
            if not _combina(str(h.get("tags", "")) + " " + str(h.get("pageURL", "")), q):
                continue
            vs = h.get("videos") or {}
            # "medium" costuma ser 1920x1080 (o "large" pode ser 4K: pesado demais à toa)
            opcoes = [vs.get(t) for t in ("medium", "large", "small") if (vs.get(t) or {}).get("url")]
            opcoes = [o for o in opcoes if (o.get("height") or 0) <= 2200 and (o.get("width") or 0) <= 2200] or opcoes
            if not opcoes:
                continue
            certo = [o for o in opcoes if ((o.get("width") or 0) > (o.get("height") or 0)) == deitado]
            esc = (certo or [o for o in opcoes if min(o.get("height") or 0, o.get("width") or 0) >= 720] or opcoes)[0]
            thumb = next(((vs.get(t) or {}).get("thumbnail") for t in ("medium", "large", "small")
                          if (vs.get(t) or {}).get("thumbnail")), None)
            if not thumb:
                continue
            vistos.add(h["id"])
            item = {"id": f"pb{h['id']}", "imagem": thumb, "arquivo": esc["url"], "autor": h.get("user", ""),
                    "url": h.get("pageURL", ""), "duracao": float(h.get("duration", 0)), "site": "Pixabay"}
            (bons if certo else outros).append(item)
    return (bons + outros)[:limite]


# buscas genéricas que costumam trazer imagem "bonita e aleatória" (só passam se a fala citar a coisa)
_GENERICAS = {
    "flower": "flor", "flowers": "flor", "sky": "céu", "clouds": "nuvem", "landscape": "paisagem", "nature": "natureza",
    "sunset": "pôr do sol", "sunrise": "amanhecer", "bridge": "ponte", "coffee": "café", "cup": "xícara",
    "mountain": "montanha", "ocean": "mar", "sea": "mar", "beach": "praia", "forest": "floresta", "tree": "árvore",
    "abstract": None, "concept": None, "energy": None, "spiritual": None, "vibration": None, "divine": None,
    "universe": None, "light": None, "background": None, "texture": None, "bokeh": None, "particles": None,
}


def limpar_buscas(buscas, frase=""):
    """Fica só com buscas de CENA concreta (sujeito + ação + ambiente); tira as genéricas que não estão na fala."""
    frase = (frase or "").lower()
    out = []
    for q in buscas or []:
        if not isinstance(q, str):
            continue
        q = " ".join(q.lower().replace(",", " ").split())[:90]
        pal = q.split()
        if len(pal) < 3:
            continue
        ruim = False
        for p in pal:
            if p in _GENERICAS:
                pt = _GENERICAS[p]
                if pt is None or pt not in frase:
                    ruim = True
                    break
        if not ruim and q not in out:
            out.append(q)
    return out[:3]


def buscar_pixabay_fotos(consultas, limite=4, deitado=False):
    """Fotos de banco do Pixabay (mesma chave): entram como opção junto com os vídeos (viram imagem animada)."""
    k = chave_pixabay()
    if not k:
        return []
    out, vistos = [], set()
    for q in consultas[:2]:
        url = "https://pixabay.com/api/?" + urllib.parse.urlencode(
            {"key": k, "q": q[:100], "image_type": "photo", "per_page": 6, "safesearch": "true",
             "orientation": "horizontal" if deitado else "all"})
        try:
            dados = json.loads(_get(url))
        except Exception:
            continue
        for h in dados.get("hits", []):
            if h.get("id") in vistos or not h.get("largeImageURL"):
                continue
            if not _combina(str(h.get("tags", "")) + " " + str(h.get("pageURL", "")), q):
                continue
            vistos.add(h["id"])
            out.append({"id": f"pbf{h['id']}", "imagem": h.get("webformatURL") or h["largeImageURL"],
                        "arquivo": h["largeImageURL"], "autor": h.get("user", ""), "url": h.get("pageURL", ""),
                        "site": "Pixabay", "tipo": "foto", "licenca": "Pixabay License"})
            if len(out) >= limite:
                return out
    return out


def candidatos(b, deitado=False):
    v = b.get("video") or {}
    buscas = limpar_buscas(v.get("buscas") or b.get("buscas") or [], b.get("frase", ""))
    if not buscas:
        return []
    dur = float(b.get("dur", 4))
    a = buscar(buscas, dur, limite=4, deitado=deitado)
    p = buscar_pixabay(buscas, dur, limite=6 - min(len(a), 3), deitado=deitado)
    cands = []
    for i in range(max(len(a), len(p))):          # intercala Pexels e Pixabay
        cands += [x for x in (a[i] if i < len(a) else None, p[i] if i < len(p) else None) if x]
    cands = cands[:6]
    if ler_config().get("fotos_banco", True):     # + fotos de banco (mais chance de achar a cena certa)
        cands += buscar_pixabay_fotos(buscas, limite=9 - len(cands), deitado=deitado)
    return cands[:9]


# ------------------------------------------------------------------ fotos / documentos (Wikimedia Commons)
_LIC_OK = ("cc0", "public domain", "pd", "cc by", "cc-by", "cc by-sa", "cc-by-sa", "no restrictions")


def _sem_html(t):
    import re as _re
    return _re.sub(r"<[^>]+>", "", str(t or "")).strip()


def buscar_commons(consultas, limite=9):
    """Fotos, documentos, mapas e obras com licença livre no Wikimedia Commons (sem chave)."""
    out, vistos = [], set()
    for q in consultas[:3]:
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "generator": "search", "gsrsearch": q[:100] + " filetype:bitmap", "gsrnamespace": 6,
            "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1080,
            "format": "json"})
        try:
            dados = json.loads(_get(url, {"User-Agent": "EditorNatinha/1.0 (editor de video pessoal)"}))
        except Exception:
            continue
        for pg in sorted((dados.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 99)):
            ii = (pg.get("imageinfo") or [{}])[0]
            if pg.get("pageid") in vistos or ii.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if (ii.get("width") or 0) < 700:
                continue
            meta = ii.get("extmetadata") or {}
            lic = _sem_html((meta.get("LicenseShortName") or {}).get("value", ""))
            if not lic.lower().startswith(_LIC_OK):
                continue
            thumb = ii.get("thumburl") or ii.get("url")
            if not thumb:
                continue
            vistos.add(pg.get("pageid"))
            autor = _sem_html((meta.get("Artist") or {}).get("value", ""))[:60] or "Wikimedia Commons"
            out.append({"id": f"wm{pg.get('pageid')}", "imagem": thumb, "arquivo": thumb, "autor": autor,
                        "url": ii.get("descriptionurl", ""), "licenca": lic, "site": "Wikimedia Commons"})
            if len(out) >= limite:
                return out
    return out


def candidatos_foto(b):
    buscas = [q for q in (b.get("buscas") or []) if isinstance(q, str) and q.strip()][:3]
    return buscar_commons(buscas) if buscas else []


PROMPT_ESCOLHA_V2 = """Você é uma editora de vídeo MUITO exigente. Para cada item há UMA imagem com opções numeradas
(vídeos de banco ou fotos/documentos). Ela vai cobrir a tela enquanto a apresentadora fala a frase indicada.
A pergunta NÃO é "a imagem é do mesmo assunto?". A pergunta é: "essa cena representa a AÇÃO ou a IDEIA central da
frase?". Ex.: "atendimento nos hospitais públicos" → paciente conversando com profissional, recepção, espera, cuidado
(aparelho médico, prédio de hospital ou maca vazia NÃO representam a ideia); "a energia das pessoas" → pessoas
interagindo, multidão, tensão social (objeto ou paisagem NÃO). Notebook, prédio, objeto solto ou equipamento só servem
se a frase for exatamente sobre aquilo.
Para cada item: escolha o número da opção que melhor mostra a ação/ideia e dê uma NOTA de 1 a 5:
5 = mostra exatamente a ação/ideia; 4 = representa a ideia com clareza; 3 = só do mesmo assunto/"clima";
2 = fraca; 1 = sem relação.
Se nenhuma opção representar a ideia, responda numero 0. Evite texto/logo/marca d'água, imagem feia ou confusa.
Responda em JSON: {"escolhas": [{"item": 1, "numero": 3, "nota": 4, "motivo": "curto: que ação/ideia aparece"}]}"""


def escolher_v2(itens, log=print):
    """itens: [(rotulo_da_fala, ideia, cands, deitado)] → {indice: (cand, nota)} só com nota suficiente.
    Uma chamada de visão para todos. Se a IA falhar: nada é escolhido (nunca 'o primeiro')."""
    if not itens:
        return {}
    imagens, linhas = [], []
    for j, (frase, ideia, cands, deitado) in enumerate(itens):
        imagens.append(_folha(cands, deitado))
        linhas.append(f"Item {j + 1} (imagem {j + 1}, {len(cands)} opções): ela diz \"{frase}\" — ideia: {ideia}")
    minimo = float(ler_config().get("nota_minima_stock", 4))
    try:
        resp, modelo = ia.pedir("stock_escolha_v2", PROMPT_ESCOLHA_V2, "\n".join(linhas), temperatura=0.2, log=log,
                                imagens=imagens, forte=True)
    except Exception as e:
        log(f"(a IA não conseguiu olhar as opções: {e}; nenhum vídeo/foto de banco desta vez)")
        return {}
    out = {}
    for e in resp.get("escolhas", []):
        try:
            j, n, nota = int(e.get("item", 0)) - 1, int(e.get("numero", 0) or 0), float(e.get("nota", 0) or 0)
        except (TypeError, ValueError):
            continue
        if 0 <= j < len(itens) and 1 <= n <= len(itens[j][2]):
            if nota >= minimo:
                out[j] = (itens[j][2][n - 1], nota)
            else:
                log(f"(item {j + 1}: melhor opção só tirou nota {nota:g} — não entra)")
    log(f"IA ({modelo}) avaliou {len(itens)} item(ns) de banco; {len(out)} aprovado(s)")
    return out


def baixar_foto(cand, pasta):
    arq = os.path.join(pasta, f"_foto_{cand['id']}.jpg")
    if not os.path.exists(arq):
        dados = _get(cand["arquivo"], {"User-Agent": "EditorNatinha/1.0 (editor de video pessoal)"}, timeout=90)
        with open(arq + ".parcial", "wb") as f:
            f.write(dados)
        os.replace(arq + ".parcial", arq)
    return arq


def _folha(cands, deitado=False):
    """Folha com um quadro de cada candidato, numerados, para a IA olhar."""
    tw, th = (300, 170) if deitado else (180, 320)
    col = 3
    lin = (len(cands) + col - 1) // col
    folha = Image.new("RGB", (col * (tw + 10), lin * (th + 40)), "white")
    dr = ImageDraw.Draw(folha)
    fnt = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), 26)
    for i, c in enumerate(cands):
        x, y = (i % col) * (tw + 10), (i // col) * (th + 40)
        try:
            im = Image.open(io.BytesIO(_get(c["imagem"], timeout=20))).convert("RGB")
            esc = max(tw / im.width, th / im.height)
            im = im.resize((int(im.width * esc) + 1, int(im.height * esc) + 1))
            l, t = (im.width - tw) // 2, (im.height - th) // 2
            folha.paste(im.crop((l, t, l + tw, t + th)), (x, y))
        except Exception:
            pass
        dr.text((x + tw / 2, y + th + 18), str(i + 1), font=fnt, fill=(200, 0, 60), anchor="mm")
    b = io.BytesIO()
    folha.save(b, "PNG")
    return b.getvalue()


FAIXA_FAMILIA = {"papel": (34, 26, 24), "escuro": (14, 12, 16), "matrix": (6, 18, 12), "roxo": (24, 12, 44),
                 "tech": (4, 10, 10), "documental": (14, 13, 12), "psicologico": (6, 8, 14), "alerta": (10, 8, 8),
                 "espiritual": (10, 7, 16)}
ACENTO_FAMILIA = {"papel": (214, 104, 74), "escuro": (226, 178, 76), "matrix": (104, 226, 156), "roxo": (242, 193, 78),
                  "tech": (60, 255, 160), "documental": (240, 190, 80), "psicologico": (60, 200, 255),
                  "alerta": (255, 64, 64), "espiritual": (255, 200, 80)}
GRADE_FAMILIA = {   # tratamento de cor coerente com a família visual do vídeo
    "papel": "eq=saturation=0.86:contrast=1.04:brightness=-0.01,colorbalance=rs=0.04:bs=-0.03:rm=0.03:bm=-0.02",
    "escuro": "eq=saturation=0.74:contrast=1.08:brightness=-0.045,colorbalance=rh=0.04:gh=0.02:bh=-0.03",
    "matrix": "eq=saturation=0.70:contrast=1.07:brightness=-0.04,colorbalance=rs=-0.02:gs=0.05:gm=0.04:bs=-0.01",
    "roxo": "eq=saturation=0.82:contrast=1.06:brightness=-0.035,"
            "colorbalance=rs=0.03:gs=-0.02:bs=0.09:rm=0.02:bm=0.05:rh=0.04:bh=0.02",
    # estética nova: imagem mais escura e contrastada, puxando para a cor da família
    "tech": "eq=saturation=0.72:contrast=1.12:brightness=-0.06,colorbalance=rs=-0.03:gs=0.04:bs=0.04:gm=0.03",
    "documental": "eq=saturation=0.70:contrast=1.10:brightness=-0.05,colorbalance=rs=0.04:bs=-0.04:rm=0.03:bm=-0.03",
    "psicologico": "eq=saturation=0.68:contrast=1.12:brightness=-0.06,colorbalance=rs=-0.03:bs=0.06:bm=0.04",
    "alerta": "eq=saturation=0.62:contrast=1.14:brightness=-0.06,colorbalance=rs=0.05:rm=0.04",
    "espiritual": "eq=saturation=0.74:contrast=1.10:brightness=-0.05,colorbalance=rs=0.03:bs=0.07:rm=0.03:bm=0.04",
}


def _familia(estilo):
    e = str(estilo or "roxo")
    return next((f for f in sorted(FAIXA_FAMILIA, key=len, reverse=True) if e.startswith(f)), "roxo")


def _titulo_png(texto, arq, W=1080, H=1920, familia="roxo"):
    """Título sobre o vídeo real, na cor da família do vídeo. Vertical: faixa no topo (a legenda fica embaixo).
    Horizontal (YouTube): legenda editorial embaixo à esquerda, igual às fotos/documentos."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    deitado = W > H
    cor_faixa = FAIXA_FAMILIA.get(familia, FAIXA_FAMILIA["roxo"])
    texto = (texto or "").strip()
    if deitado:
        gh = int(H * 0.45)
        grad = Image.new("L", (1, gh))
        for y in range(gh):
            grad.putpixel((0, y), int(205 * (y / gh) ** 1.5))
        faixa = Image.new("RGBA", (W, gh), cor_faixa + (255,))
        faixa.putalpha(grad.resize((W, gh)))
        im.alpha_composite(faixa, (0, H - gh))
        if texto:
            d = ImageDraw.Draw(im)
            tam = int(H * 0.07)
            F = ImageFont.truetype(os.path.join(FONTES, "Lora-Variable.ttf"), tam)
            try:
                F.set_variation_by_name("SemiBold")
            except Exception:
                pass
            while tam > H * 0.045 and F.getlength(texto) > W * 0.6:
                tam -= 2
                F = F.font_variant(size=tam)
            x, y = int(W * 0.06), int(H * 0.86 - tam)
            d.rectangle([x, y - int(tam * 0.45), x + int(W * 0.05), y - int(tam * 0.45) + max(3, H // 270)],
                        fill=ACENTO_FAMILIA.get(familia, (242, 193, 78)) + (255,))
            d.text((x + 3, y + 3), texto, font=F, fill=(0, 0, 0, 150))
            d.text((x, y), texto, font=F, fill=(246, 240, 230, 255))
        im.save(arq)
        return
    gh = int(H * (0.42 if deitado else 0.40))
    grad = Image.new("L", (1, gh))
    for y in range(gh):
        grad.putpixel((0, y), int(185 * (1 - y / gh) ** 1.6))
    faixa = Image.new("RGBA", (W, gh), cor_faixa + (255,))
    faixa.putalpha(grad.resize((W, gh)))
    im.alpha_composite(faixa)
    texto = texto.upper()
    if texto:
        d = ImageDraw.Draw(im)
        larg = W * (0.62 if deitado else 1) - 120
        tam0 = H * (0.085 if deitado else 0.068)
        tam, linhas = tam0, [texto]
        F = lambda t: ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), max(10, int(t)))
        while tam > tam0 * 0.65 and F(tam).getlength(texto) > larg:
            tam -= 2
        if F(tam).getlength(texto) > larg and " " in texto:
            p = texto.split()
            c = min(range(1, len(p)), key=lambda i: abs(len(" ".join(p[:i])) - len(" ".join(p[i:]))))
            linhas, tam = [" ".join(p[:c]), " ".join(p[c:])], tam0 * 0.92
            while tam > tam0 * 0.45 and max(F(tam).getlength(l) for l in linhas) > larg:
                tam -= 2
        f = F(tam)
        y0 = H * (0.07 if deitado else 0.104) - (tam * 0.5 if len(linhas) > 1 else 0)
        sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sombra)
        for i, l in enumerate(linhas):
            ds.text(((W - f.getlength(l)) / 2 + 4, y0 + i * tam * 1.05 + 6), l, font=f, fill=(0, 0, 0, 170))
        im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(max(2, int(tam * 0.06)))))
        for i, l in enumerate(linhas):
            d.text(((W - f.getlength(l)) / 2, y0 + i * tam * 1.05), l, font=f, fill=(246, 238, 227, 255))
    im.save(arq)


def render(cand, titulo, dur, saida, pasta, W=1080, H=1920, estilo=None, seed=0):
    """Baixa o clipe escolhido e monta o B-roll final (tamanho W x H, cor da família visual, título).
    O movimento muda de um B-roll para outro (pan para um lado, para o outro, aproxima, afasta)."""
    fonte = os.path.join(pasta, f"_pexels_{cand['id']}.mp4")
    if not os.path.exists(fonte):
        dados = _get(cand["arquivo"], timeout=180)
        with open(fonte + ".parcial", "wb") as f:
            f.write(dados)
        os.replace(fonte + ".parcial", fonte)
    fam = _familia(estilo)
    png = os.path.join(pasta, f"_titulo_{os.path.basename(saida)}.png")
    _titulo_png(titulo, png, W, H, fam)
    ini = 0.4 if cand.get("duracao", 0) > dur + 1.2 else 0.0
    mov = int(seed) % 4
    z = 1.10
    zw, zh = int(W * z) // 2 * 2, int(H * z) // 2 * 2
    if mov in (0, 1):                                 # pan lento para um lado ou para o outro
        x = f"(iw-{W})*(0.2+0.6*t/{dur:.2f})" if mov == 0 else f"(iw-{W})*(0.8-0.6*t/{dur:.2f})"
        movimento = (f"scale={zw}:{zh}:force_original_aspect_ratio=increase,"
                     f"crop={W}:{H}:x='{x}':y='(ih-{H})/2'")
    else:                                             # aproxima / afasta devagar, centrado no assunto
        k = f"(1+0.10*t/{dur:.2f})" if mov == 2 else f"(1.10-0.10*t/{dur:.2f})"
        movimento = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"scale=w='trunc({W}*{k}/2)*2':h='trunc({H}*{k}/2)*2':eval=frame,"
                     f"crop={W}:{H}:x='(iw-{W})/2':y='(ih-{H})*0.45'")
    fc = (f"[0:v]{movimento},fps=30,setsar=1,{GRADE_FAMILIA[fam]},vignette=PI/5[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.15:d=0.35:alpha=1[t];[v][t]overlay=0:0,format=yuv420p[o]")
    parcial = saida + ".parcial.mp4"
    run([FFMPEG, "-y", "-v", "error", "-ss", f"{ini:.2f}", "-i", fonte, "-loop", "1", "-t", f"{dur:.2f}", "-i", png,
         "-filter_complex", fc, "-map", "[o]", "-t", f"{dur:.2f}", "-an", "-c:v", "libx264", "-preset",
         ler_config().get("preset", "medium"), "-crf", "20", parcial])
    os.replace(parcial, saida)


def _titulo_de(b):
    return b.get("titulo") or next((a.get("texto") for a in (b.get("receita") or {}).get("acoes", [])
                                    if a.get("tipo") == "titulo"), "")


def processar(plano, indices, pasta, log=print, W=1080, H=1920):
    """Faz com vídeo real os B-rolls indicados. Busca tudo, pede à IA para escolher TODOS numa só olhada,
    baixa e monta. Devolve o conjunto de índices que deram certo."""
    if not indices or not tem_fonte():
        return set()
    deitado = W > H
    itens = []
    for k in indices:
        try:
            cands = candidatos(plano[k], deitado)
        except Exception:
            cands = []
        if cands:
            itens.append((k, cands))
        else:
            log(f"(nenhum vídeo real para o B-roll {k + 1})")
    if not itens:
        return set()
    imagens, linhas = [], []
    for j, (k, cands) in enumerate(itens):
        imagens.append(_folha(cands, deitado))
        b = plano[k]
        buscas = ", ".join((b.get("video") or {}).get("buscas") or [])
        linhas.append(f"B-roll {j + 1} (imagem {j + 1}, {len(cands)} opções): ela diz \"{b.get('frase', '')}\" — "
                      f"ideia: {b.get('ideia', '')} — cena procurada: {buscas}")
    escolhas = {}
    try:
        resp, modelo = ia.pedir("brolls_video_escolha", PROMPT_ESCOLHA, "\n".join(linhas), temperatura=0.2, log=log,
                                imagens=imagens, forte=True)
        for e in resp.get("escolhas", []):
            escolhas[int(e.get("broll", 0))] = int(e.get("numero", 0) or 0)
        log(f"IA ({modelo}) escolheu os vídeos reais olhando")
    except Exception as e:
        # sem a IA olhar, nenhum vídeo é confiável: fica animação/rosto (nunca "o primeiro serve")
        log(f"(não deu para escolher os vídeos olhando: {e}; nenhum vídeo real desta vez)")
        escolhas = {}
    feitos = set()
    for j, (k, cands) in enumerate(itens):
        n = escolhas.get(j + 1, 0)
        if not 1 <= n <= len(cands):
            log(f"B-roll {k + 1}: nenhum vídeo real serviu; fica animação")
            continue
        c = cands[n - 1]
        b = plano[k]
        try:
            render(c, _titulo_de(b), float(b.get("dur", 4)), os.path.join(pasta, b["arquivo"]), pasta, W, H)
        except Exception as e:
            log(f"(B-roll {k + 1}: não deu para baixar/montar o vídeo: {e})")
            continue
        b["fonte"] = c.get("site", "Pexels").lower()
        b["credito"] = f"{c['autor']} ({c.get('site', 'Pexels')}) — {c['url']}"
        log(f"B-roll {k + 1}: vídeo real de {c['autor']} ({c.get('site')})")
        feitos.add(k)
    return feitos


def tentar(b, pasta, log=print):
    """Um B-roll só (botão Refazer)."""
    return 0 in processar([b], [0], pasta, log)
