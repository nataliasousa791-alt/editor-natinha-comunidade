"""Legenda motion derivada somente das palavras e dos tempos finais do plano real."""
import unicodedata
import re

STOP = set("a o as os um uma umas uns de da do das dos e ou que se sem com para pra por em no na nos nas ao aos como ja mas nao sim voce voces eu ele ela eles elas te me lhe seu sua seus suas ainda entao ta ne aqui la ai porque quando quanto tudo todos toda cada".split())
ENERGY = ("recarreg", "energi", "bateri", "carreg")
SLEEP = ("sono", "dorm", "descans", "noite", "lua")
SHIELD = ("protec", "segur", "defes", "escud", "control")
PUNCT = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)

def normalizar(txt):
    txt = unicodedata.normalize("NFKD", str(txt).lower())
    return "".join(ch for ch in txt if not unicodedata.combining(ch)).strip(".,;:!?()[]{}\"' ")

def icon_for(word):
    token=normalizar(word)
    if any(x in token for x in ENERGY): return "battery"
    if any(x in token for x in SLEEP): return "moon"
    if any(x in token for x in SHIELD): return "shield"
    return None

def gerar_cues(legendas, min_gap=4.0):
    """Não cria palavras ou tempos; substitui destaque apenas por parâmetros visuais."""
    cues=[]
    last_focus=float("-inf")
    for ix, block in enumerate(sorted(legendas or [],key=lambda x:float(x.get("ini",0)))):
        ini=float(block.get("ini",0))
        fim=float(block.get("fim",ini))
        if fim <= ini: continue
        words=[]
        for entry in block.get("palavras",[]):
            word=str(entry.get("w","")).strip()
            if not word: continue
            s=float(entry.get("s",ini))
            words.append({"w":word,"s":s,"destaque":bool(entry.get("destaque",False))})
        if not words: continue
        focus_index=None
        explicit=[(i,w) for i,w in enumerate(words) if w["destaque"] and normalizar(w["w"]) not in STOP]
        semantic=[(i,w) for i,w in enumerate(words) if icon_for(w["w"]) is not None and normalizar(w["w"]) not in STOP]
        generic=[(i,w) for i,w in enumerate(words) if len(normalizar(w["w"])) >= 7 and normalizar(w["w"]) not in STOP]
        candidates=explicit or semantic or generic
        if candidates:
            # Palavra semanticamente forte/explicitamente marcada. Destaque espaçado para não ficar frenético.
            if explicit or ini-last_focus >= min_gap:
                mid=(ini+fim)/2
                focus_index=min(candidates,key=lambda x:(abs(x[1]["s"]-mid),-len(x[1]["w"])))[0]
                if words[focus_index]["s"]-last_focus < min_gap and not explicit:
                    focus_index=None
        focus=words[focus_index] if focus_index is not None else None
        trigger=max(ini,min(fim-.01,float(focus["s"]))) if focus else ini
        if focus:last_focus=trigger
        # Preservar as quebras e o texto fiel ao plano. A renderização posiciona ambos.
        cues.append({
            "id":ix,"ini":ini,"fim":fim,
            "palavras":words,
            "focus":focus["w"] if focus else None,
            "focusIndex":focus_index,
            "icon":icon_for(focus["w"]) if focus else None,
            "trigger":trigger
        })
    return cues

def validar_cues(cues, legendas):
    source=[(float(b["ini"]),float(b["fim"]),tuple(w["w"] for w in b["palavras"])) for b in sorted(legendas,key=lambda x:x["ini"]) if b.get("palavras") and b["fim"]>b["ini"]]
    result=[(c["ini"],c["fim"],tuple(w["w"] for w in c["palavras"])) for c in cues]
    if source!=result:raise ValueError("Cues divergem do texto/tempo do plano original")
    return True
