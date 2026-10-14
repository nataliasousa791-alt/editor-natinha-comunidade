"""Busca e desenho de ícones (game-icons, Material Design Icons, Phosphor) como silhuetas.
Renderização com PyMuPDF (funciona no Windows sem dependências extras)."""
import json, os, re
from functools import lru_cache
import numpy as np
from PIL import Image
import pymupdf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(RAIZ, "recursos", "icones")
SETS = ["game-icons", "mdi", "ph"]          # ordem de preferência (game-icons = estilo silhueta)
_DATA = {}

SINONIMOS = {
    "mortarboard": "graduate-cap", "graduation-cap": "graduate-cap", "graduation": "graduate-cap", "cap": "graduate-cap",
    "government": "capitol", "parliament": "capitol", "congress": "capitol", "senate": "capitol", "politics": "capitol",
    "cathedral": "church", "temple": "church", "religion": "church",
    "mobile": "smartphone", "cellphone": "smartphone", "cell-phone": "smartphone", "phone": "smartphone",
    "social-media": "smartphone", "screen": "smartphone",
    "award": "trophy", "prize": "trophy", "medal": "medal",
    "user": "person", "man": "person", "human": "person", "people": "person", "student": "person", "girl": "woman",
    "certificate": "diploma", "degree": "diploma",
    "gear": "cog", "cogs": "gears", "machine": "gears",
    "coin": "coins", "cash": "money-stack", "money": "money-stack",
    "ai": "robot", "artificial-intelligence": "robot", "robot-head": "robot",
    "vision": "eye", "attention": "eye", "watch": "eye",
    "wedding": "ring", "marriage": "ring",
    "strings": "puppet", "marionette": "puppet", "control": "puppet",
    "time": "hourglass", "past": "hourglass",
    "school": "school-bag", "classroom": "desk",
    "speech-bubble": "chat", "talk": "chat", "conversation": "chat", "message": "chat",
    "bible": "book-cross", "scripture": "book-cross", "holy-book": "book-cross", "prayer": "hands-pray", "pray": "hands-pray",
    "crowd": "person", "brainwash": "brain", "mind": "brain", "idea": "light-bulb", "lightbulb": "light-bulb",
}


def _load():
    if _DATA:
        return _DATA
    for s in SETS:
        _DATA[s] = json.load(open(os.path.join(BASE, s, "icons.json"), encoding="utf-8"))
    return _DATA


def _norm(k):
    return re.sub(r"[^a-z0-9]+", "-", str(k).lower()).strip("-")


def _exato(k):
    d = _load()
    for s in SETS:
        icons, al = d[s]["icons"], d[s].get("aliases", {})
        for cand in ([k + "-fill", k] if s == "ph" else [k]):
            if cand in icons:
                return s, cand
            if cand in al:
                return s, al[cand]["parent"]
    return None


def buscar(palavra, _sin=True):
    """Retorna (conjunto, nome) do ícone mais adequado para a palavra (em inglês)."""
    d = _load()
    k = _norm(palavra)
    if not k:
        return None
    if _sin and k in SINONIMOS:
        r = buscar(SINONIMOS[k], _sin=False)
        if r:
            return r
    r = _exato(k)
    if r:
        return r
    # nome que contém a palavra como token inteiro (prefere o mais curto)
    for s in SETS:
        names = [n for n in d[s]["icons"] if k in n.split("-") or (len(k) >= 4 and n.startswith(k))]
        if s == "ph":
            names = [n for n in names if n.endswith("-fill")]
        if s == "mdi":
            names = [n for n in names if "outline" not in n and "off" not in n.split("-")]
        if names:
            return s, sorted(names, key=len)[0]
    if len(k) >= 5:
        for s in SETS:
            names = [n for n in d[s]["icons"] if k in n]
            if names:
                return s, sorted(names, key=len)[0]
    return None


_MODIFICADORES = {"outline", "off", "plus", "minus", "remove", "alert", "arrow", "check", "edit", "cancel", "sync",
                  "refresh", "settings", "search", "marker", "lock", "open", "multiple", "box", "circle", "network",
                  "cog", "sync", "account", "file", "folder", "cloud", "variant", "down", "up", "left", "right"}


def candidatos(palavras, limite=24):
    """Lista de ícones possíveis (conjunto, nome) para as palavras-chave, os mais prováveis primeiro."""
    d = _load()
    chaves, tokens = [], set()
    for p in palavras if isinstance(palavras, (list, tuple)) else [palavras]:
        k = _norm(p)
        if not k:
            continue
        if k not in chaves:
            chaves.append(k)
        tokens.update(t for t in k.split("-") if len(t) > 2)
        if k in SINONIMOS and SINONIMOS[k] not in chaves:
            chaves.append(SINONIMOS[k])           # sinônimo vale só como nome exato
    achados = {}
    for s in SETS:
        for n in d[s]["icons"]:
            base = n[:-5] if s == "ph" and n.endswith("-fill") else n
            if s == "ph" and not n.endswith("-fill"):
                continue
            partes = base.split("-")
            if "logo" in partes and base not in chaves:
                continue
            if s == "mdi" and any(x in _MODIFICADORES for x in partes):
                if base not in chaves:
                    continue
            exato = base in chaves
            casa = [t for t in tokens if t in partes]
            if not exato and not casa:
                continue
            ordem = min([i for i, k in enumerate(chaves) if any(t in partes for t in k.split("-"))] or [99])
            pont = (0 if exato else 1, -len(casa), ordem, len(partes), len(base))
            if (s, base) not in [(x[0], x[1]) for x in achados.values()]:
                achados[(s, n)] = (s, base, pont)
    lista = sorted(achados.items(), key=lambda kv: kv[1][2])
    out, vistos = [], set()
    for (s, n), (_, base, _) in lista:
        if base in vistos and len(out) > limite // 2:
            continue
        vistos.add(base)
        out.append((s, n))
        if len(out) >= limite:
            break
    return out


def achar(palavras):
    """Aceita uma palavra ou lista de alternativas; devolve a primeira encontrada, ou None (nunca um ícone aleatório)."""
    if isinstance(palavras, str):
        palavras = [palavras]
    for p in palavras:
        r = buscar(p)
        if r:
            return r
    for p in palavras:  # palavra por palavra (a mais longa primeiro)
        for w in sorted(_norm(p).split("-"), key=len, reverse=True):
            if len(w) > 2:
                r = buscar(w)
                if r:
                    return r
    return None          # sem ícone adequado: quem chamou decide (outra composição ou manter o rosto)


@lru_cache(maxsize=512)
def mascara(conjunto, nome, altura):
    """Silhueta (canal alfa) do ícone com a altura pedida, recortada no conteúdo."""
    d = _load()[conjunto]
    ic = d["icons"][nome]
    w = ic.get("width", d.get("width", 24))
    h = ic.get("height", d.get("height", 24))
    px = altura * 2
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{px}" height="{px}">'
           f'{ic["body"]}</svg>').replace("currentColor", "#000000")
    doc = pymupdf.open(stream=svg.encode(), filetype="svg")
    pix = doc[0].get_pixmap(alpha=True)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    a = Image.fromarray(np.ascontiguousarray(arr[..., -1]))
    bb = a.getbbox()
    if not bb:
        return Image.new("L", (altura, altura), 255)
    a = a.crop(bb)
    s = altura / a.height
    return a.resize((max(1, int(a.width * s)), altura), Image.LANCZOS)


CREDITO = "Ícones: game-icons.net (CC BY 3.0), Material Design Icons (Apache 2.0), Phosphor Icons (MIT)"
