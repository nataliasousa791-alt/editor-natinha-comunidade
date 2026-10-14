"""Biblioteca de B-roll REAL licenciado (Pixabay), por conceito fixo (config) ou por busca proposta pela IA para a frase.
Chave Pixabay lida só-leitura do config antigo. Filtra renders/ilustrações. Nunca repete clipe entre jobs do mesmo vídeo."""
import json, os, re, urllib.parse, urllib.request
from .util import ROBO, cfg, probe
from .ia import _cfg_antigo

B = os.path.join(ROBO, "biblioteca")
MAN, USO = os.path.join(B, "manifest.json"), os.path.join(B, "usados.json")
UA = {"User-Agent": "Mozilla/5.0 NatinhaRobo"}
_SEM_IMAGEM = set()   # temas sem imagem aprovada nesta execução do robô (um vídeo)


def _ler(p, padrao):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else padrao


def _salvar(p, o):
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def chave_busca(q):
    return "q:" + re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()


def _avaliar(hits, frase, log):
    """V6: a IA OLHA a miniatura de cada candidato e da nota 0-10 de pertinencia a frase exata.
    Devolve os hits aprovados (nota >= broll_nota_min), do melhor para o pior. Sem IA -> lista vazia (Natinha fica em cena)."""
    c = cfg(); nmin = c.get("broll_nota_min", 7)
    imgs, ok = [], []
    for h in hits[:10]:
        u = h.get("videos", {}).get("tiny", {}).get("thumbnail") or h.get("videos", {}).get("small", {}).get("thumbnail")
        if not u: continue
        try:
            imgs.append(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()); ok.append(h)
        except Exception: pass
    if not ok: return []
    try:
        from . import ia
        r, _ = ia.pedir(
            "Voce e pesquisador de imagens de um documentario brasileiro de critica social. Seja exigente. Responda so JSON.",
            f"Frase falada pela apresentadora: \"{frase}\"\nSeguem {len(ok)} miniaturas de videos (imagem 1 a {len(ok)}). "
            "De nota 0-10 para o quanto cada uma ilustra LITERALMENTE o que a frase diz (acao, objeto ou lugar citado) e ajuda o "
            "espectador a entender. Nota baixa (0-3) para: animais/natureza/paisagem sem relacao, 3D/ilustracao/IA, pessoas posando, "
            "cliches (favela=pobreza, luxo=riqueza, fabrica antiga=trabalho), qualquer coisa que sugira fato nao dito. "
            "Bonus leve para cenario brasileiro real. JSON: {\"notas\":[n1,n2,...]}", log, temperatura=0.1, imagens=imgs)
        notas = [float(x) for x in r.get("notas", [])]
    except Exception as e:
        log(f"avaliacao visual indisponivel ({e}); sem B-roll novo"); return []
    av = sorted([(n, h) for n, h in zip(notas, ok) if n >= nmin], key=lambda z: -z[0])
    log(f"avaliacao visual: notas {notas} -> {len(av)} aprovado(s) (min {nmin})")
    for n, h in av: h["_nota_ia"] = n
    return [h for n, h in av]


def _buscar(conceito, consultas, man, log, limite=2, frase=""):
    c = cfg(); chave = (_cfg_antigo().get("pixabay_chave") or os.environ.get("PIXABAY_API_KEY") or "").strip()
    if not chave: return []
    proib, novos, ids = c["busca_proibida"], [], {m["id"] for m in man}
    for q in consultas:
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": chave, "q": q, "per_page": 15, "safesearch": "true"})
        try:
            hits = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30)).get("hits", [])
        except Exception as e:
            log(f"busca Pixabay falhou ({e})"); continue
        hits = [h for h in hits if f"PX_{h['id']}" not in ids and not any(p in h.get("tags", "").lower() for p in proib)]
        if c.get("broll_avaliacao_visual", True):
            hits = _avaliar(hits, frase or q, log)
        for h in hits:
            tags = h.get("tags", "").lower()
            v = h["videos"].get("medium") if (h["videos"].get("medium") or {}).get("width", 0) >= 1280 else h["videos"].get("large") or {}
            if (f"PX_{h['id']}" in ids or any(p in tags for p in proib) or h["duration"] < 6 or not v.get("url")
                    or v.get("width", 0) < 1280 or v.get("width", 0) < v.get("height", 0)):
                continue
            arq = os.path.join(B, "clipes", f"PX_{h['id']}.mp4")
            try:
                with urllib.request.urlopen(urllib.request.Request(v["url"], headers=UA), timeout=240) as r:
                    open(arq, "wb").write(r.read())
            except Exception as e:
                log(f"download falhou {h['id']}: {e}"); continue
            item = dict(id=f"PX_{h['id']}", conceito=conceito, arquivo=os.path.basename(arq), fonte=h["pageURL"], autor=h["user"],
                        licenca="Pixabay Content License", tags=tags, duracao=h["duration"], largura=v.get("width"), altura=v.get("height"),
                        revisado=False, busca=q, nota_ia=h.get("_nota_ia"), frase_avaliada=frase[:200])
            man.append(item); ids.add(item["id"]); novos.append(item)
            log(f"B-roll baixado: {item['id']} ({conceito}, '{q}', {h['user']}, {v.get('width')}x{v.get('height')})")
            if len(novos) >= limite: return novos
    return novos


def obter(conceito, chave_video, ja_no_job, log, job="", consultas=None, frase=""):
    """Clipe do conceito ainda não usado neste vídeo por OUTRO job. conceito = nome do config ou chave_busca(q).
    V6: só entra clipe revisado por humano ou aprovado na avaliação visual (nota_ia) — os antigos sem nota ficam fora."""
    man, uso = _ler(MAN, []), _ler(USO, {})
    cc = cfg(); nmin = cc.get("broll_nota_min", 7); exigir = cc.get("broll_avaliacao_visual", True)
    def aprovado(m):
        return m.get("revisado") or not exigir or (m.get("nota_ia") or 0) >= nmin
    def livres():
        return [m for m in man if m["conceito"] == conceito and m["id"] not in ja_no_job and aprovado(m)
                and not any(u.split("|")[0] == chave_video and u != f"{chave_video}|{job}" for u in uso.get(m["id"], []))
                and os.path.exists(os.path.join(B, "clipes", m["arquivo"]))]
    op = livres()
    if not op and conceito in _SEM_IMAGEM:            # já buscou neste vídeo e nada passou: não repete busca/avaliação
        log(f"'{conceito}' sem imagem aprovada neste vídeo — pulando busca"); return None
    if not op:
        cs = consultas or cfg()["conceitos"].get(conceito, {}).get("busca", [])
        if cs: _buscar(conceito, cs, man, log, frase=frase); _salvar(MAN, man); op = livres()
    if not op:
        _SEM_IMAGEM.add(conceito); return None
    op.sort(key=lambda m: (not m.get("revisado"), len(uso.get(m["id"], []))))
    m = dict(op[0]); m["caminho"] = os.path.join(B, "clipes", m["arquivo"])
    try:
        pr = probe(m["caminho"]); m["duracao"] = pr["dur"]; m["largura"], m["altura"] = pr["w"], pr["h"]
    except Exception: pass
    return m


def registrar(ids, chave_video, job=""):
    uso = _ler(USO, {})
    for i in ids:
        uso.setdefault(i, [])
        if f"{chave_video}|{job}" not in uso[i]: uso[i].append(f"{chave_video}|{job}")
    _salvar(USO, uso)
