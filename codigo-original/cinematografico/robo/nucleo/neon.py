"""Estilo NEON MATRIX do canal: decide, para cada trecho, o MODO de tela (full / take / split / over) e a CENA de bonequinhos.
Só mexe na camada visual: cortes, áudio, legendas e B-roll continuam vindo do plano. B-roll real vira modo 'split' com vídeo.
IA (Gemini) escolhe modo/cena pela fala; sem IA, um ritmo alternado é usado. Regras são garantidas em código depois."""
import re
from . import ia

CATALOGO = {
    "vazio": "multidão no celular, ninguém se vê; solidão urbana, desconexão",
    "solidao": "pessoa sozinha sentada; solidão, ansiedade, falta de propósito",
    "projeto": "robô manipulando pessoas como marionetes; sistema controlando, manipulação",
    "fabrica": "esteira transformando corações em dinheiro; industrialização, lucro, mercantilização",
    "tempo": "pessoa trabalhando e relógio girando; tempo, horas, jornada",
    "dinheiro": "salário dividido em aluguel, mercado e contas; renda, despesas, custo de vida",
    "piramide": "pirâmide social com robô/dono no topo; poder, hierarquia, desigualdade",
    "heranca": "casa passando de geração em geração; herança, patrimônio, famílias ricas",
    "celular": "pessoa rolando perfis e corações; redes sociais, aplicativos, relacionamentos online",
    "emprego": "robô tomando o lugar de uma pessoa; automação, perder emprego, IA no trabalho",
    "policia": "robô vigiando pessoas; vigilância, controle",
    "seguranca": "robô guardando cofre; segurança, proteção, dados",
    "monolito": "monolito surgindo; tecnologia nova, algo grande chegando",
    "musica": "música/arte feita por IA",
    "filme": "cinema, ficção científica",
    "pos": "mundo pós-apocalíptico",
    "vai": "glitch de impacto: frase de choque curta (só 1x, com modo over)",
}
MODOS = {"full", "take", "split", "over"}

# palavras que PRECISAM aparecer na fala (trecho) para a cena ser aceita — trava contra a IA escolher cena sem relação
PALAVRAS = {
    "vazio": ["celular", "vazio", "sozinh", "solid", "conex", "ocupad", "redes", "ninguém", "multidão", "pessoas"],
    "solidao": ["solid", "ansied", "sozinh", "vazio", "propósito", "depress", "abandon"],
    "projeto": ["sistema", "matrix", "matriz", "control", "manipul", "projeto", "programad", "enganad", "dominar", "dominad"],
    "fabrica": ["industrial", "lucro", "lucra", "vend", "produto", "fábrica", "consum", "mercantil", "ganhar dinheiro", "monetiz"],
    "tempo": ["hora", "tempo", "jornada", "expediente", "relógio", "minuto"],
    "dinheiro": ["salário", "salario", "dinheiro", "pag", "conta", "aluguel", "mercado", "renda", "despesa", "gast", "boleto", "reais", "caro", "preço"],
    "piramide": ["poder", "rico", "dono", "patrão", "patrao", "chefe", "desigual", "topo", "elite", "classe", "hierarq", "empresári", "bilion", "milion"],
    "heranca": ["herança", "heranca", "herd", "patrimônio", "patrimonio", "geração", "gerações", "filhos", "família", "familia", "avô", "pais"],
    "celular": ["celular", "aplicativo", "redes sociais", "instagram", "tiktok", "perfil", "internet", "app", "tela", "scroll"],
    "emprego": ["emprego", "robô", "robo", "automa", "inteligência artificial", " ia ", "substitu", "demit", "desempreg"],
    "policia": ["vigi", "polícia", "policia", "câmera", "monitor", "fiscal"],
    "seguranca": ["seguran", "dados", "proteg", "cofre", "senha", "privacidade"],
    "monolito": ["tecnologia", "futuro", "inteligência artificial", " ia ", "novo mundo"],
    "musica": ["música", "musica", "cantor", "artista", "arte "],
    "filme": ["filme", "cinema", "ficção", "ficcao", "série"],
    "pos": ["apocal", "fim do mundo", "colapso", "destru"],
    "vai": ["vai acontecer", "já está acontecendo"],
}


def _combina(cena, texto):
    t = " " + texto.lower() + " "
    return any(k in t for k in PALAVRAS.get(cena, []))


def _sentencas(plano):
    """Unidades de fala (frases) a partir das legendas: [{ini, fim, texto}]."""
    ws = []
    for l in plano.get("legendas") or []:
        for w in l["palavras"]:
            ws.append((w["s"], w["w"], l["fim"]))
    out, cur = [], []
    for i, (s, w, fl) in enumerate(ws):
        cur.append((s, w, fl))
        nx = ws[i + 1][0] if i + 1 < len(ws) else None
        fim_ant = fl
        if nx is None or re.search(r"[.!?…]$", w) or (nx - fim_ant > 0.7) or len(cur) >= 22:
            out.append(dict(ini=cur[0][0], fim=cur[-1][2], texto=" ".join(x[1] for x in cur))); cur = []
    # junta unidades muito curtas (<2.5 s) com a seguinte
    ok = []
    for u in out:
        if ok and (ok[-1]["fim"] - ok[-1]["ini"]) < 2.5:
            ok[-1]["fim"] = u["fim"]; ok[-1]["texto"] += " " + u["texto"]
        else:
            ok.append(u)
    return ok


def _blocos_broll(plano):
    """Janelas de painel que contêm B-roll real -> modo split com vídeo."""
    br = [c for c in plano.get("cenas", []) if c.get("tipo") == "broll" and c.get("asset")]
    jan = []
    for a, b in list(plano.get("blocosB") or []) + list(plano.get("blocosC") or []):
        if any(a - 0.2 <= c["ini"] and c["fim"] <= b + 0.7 for c in br):
            jan.append([round(a, 2), round(b, 2)])
    return sorted(jan)


def _decidir_ia(unids, jan, alvo_pct, total, log):
    cat = "- gen: uma cena animada nova, criada sob medida para o trecho (use sempre que o trecho tiver uma ideia visualizável)"
    lista = "\n".join(f"{i}\t{u['ini']:.1f}-{u['fim']:.1f}\t{u['texto']}" for i, u in enumerate(unids))
    sis = ("Você dirige a edição de um canal brasileiro de crítica social (estilo 'neon matrix', bonequinhos animados). "
           "Para cada trecho de fala escolha o MODO de tela e a CENA. Responda SOMENTE JSON: lista de {\"i\":n,\"m\":\"full|take|split|over\",\"cena\":\"nome ou null\"}, um item por trecho.\n"
           "MODOS: full = a apresentadora em tela cheia (opiniões diretas, perguntas, fechamento); take = a animação toma conta (ideia nova, mundo/ficção, 'e se' visual); "
           "split = ela em cima e animação embaixo (explicações); over = ela em tela cheia + animação pequena (SÓ momentos de impacto, no máximo 1 a cada 60 s).\n"
           f"Teto: no máximo ~{int(alvo_pct * 100)}% do tempo com animação (take/split/over) — é um LIMITE, não uma meta. A cena DEVE ilustrar de forma específica o que é dito naquele trecho (o conceito da frase); "
           "se o trecho não tem ideia visual clara (opinião pura, pergunta retórica), use full. Prefira full a uma cena forçada. Em m diferente de full use sempre cena \"gen\"; em full use null. "
           "Primeiro trecho: full. Último trecho: full.\nCENA:\n" + cat)
    usr = f"Duração total {total:.0f}s. Trechos (i, tempo, fala):\n{lista}"
    res, modelo = ia.pedir(sis, usr, log, temperatura=0.3)
    if isinstance(res, dict):
        res = res.get("trechos") or res.get("itens") or list(res.values())[0]
    por_i = {int(x["i"]): x for x in res if isinstance(x, dict) and "i" in x}
    log(f"neon: IA {modelo} escolheu modos para {len(por_i)}/{len(unids)} trechos")
    return [por_i.get(i, {"m": "full", "cena": None}) for i in range(len(unids))]


def _decidir_ritmo(unids):
    """Sem IA: alternância full / take / full / split, cenas em rodízio."""
    ordem = ["vazio", "projeto", "tempo", "dinheiro", "piramide", "celular", "fabrica", "heranca", "solidao"]
    padrao = ["full", "take", "full", "split"]
    out, k = [], 0
    for i, _ in enumerate(unids):
        m = padrao[i % 4]
        if m == "full": out.append({"m": "full", "cena": None})
        else: out.append({"m": m, "cena": ordem[k % len(ordem)]}); k += 1
    return out


# ---------------- CENAS GERADAS SOB MEDIDA (sem cena pré-pronta) ----------------
OBJ_OK = {"casa", "moeda", "nota", "coracao", "celular", "relogio", "predio", "caixa", "cofre", "grafico", "documento", "carrinho",
          "cadeado", "engrenagem", "olho", "balanca", "lampada", "seta", "estrela", "sacola"}
ACAO_OK = {"parado", "andar", "correr", "trabalhar", "sentado", "comemorar", "apontar", "cabisbaixo", "carregar", "pedir"}
COR_OK = {"lime", "rosa", "branco", "verde"}
ANIM_OK = {"flutuar", "pulsar", "girar", "tremer", "subir", "sumir"}


def _n(v, a, b, d):
    try:
        v = float(v)
        return max(a, min(b, v))
    except Exception:
        return d


def _par(v):
    try:
        return [_n(v[0], 0, 100, 50), _n(v[1], 0, 100, 50)]
    except Exception:
        return None


def _validar(sp):
    """Aceita só peças conhecidas e coordenadas dentro da área segura; devolve spec limpa ou None."""
    if not isinstance(sp, dict):
        return None
    out = {"atores": [], "objetos": [], "fluxos": [], "linhas": [], "textos": [], "matriz": bool(sp.get("matriz"))}
    for a in (sp.get("atores") or [])[:5]:
        if not isinstance(a, dict): continue
        d = {"tipo": "robo" if a.get("tipo") in ("robo", "robot") else "pessoa", "x": _n(a.get("x"), 8, 92, 50),
             "acao": a.get("acao") if a.get("acao") in ACAO_OK else "parado", "quando": _n(a.get("quando"), 0, 0.8, 0)}
        if a.get("x2") is not None: d["x2"] = _n(a.get("x2"), 8, 92, d["x"]); d["mov_ini"] = _n(a.get("mov_ini"), 0, 0.6, 0.1); d["mov_fim"] = _n(a.get("mov_fim"), 0.3, 1, 0.8)
        if a.get("cor") in COR_OK: d["cor"] = a["cor"]
        if a.get("olhar") == "esq": d["olhar"] = "esq"
        if a.get("tam") is not None: d["tam"] = _n(a.get("tam"), 0.8, 1.8, 1.3)
        out["atores"].append(d)
    for o in (sp.get("objetos") or [])[:8]:
        if not isinstance(o, dict) or o.get("tipo") not in OBJ_OK: continue
        d = {"tipo": o["tipo"], "x": _n(o.get("x"), 8, 92, 50), "y": _n(o.get("y"), 5, 95, 40), "quando": _n(o.get("quando"), 0, 0.85, 0),
             "tam": _n(o.get("tam"), 0.5, 2.6, 1)}
        if o.get("x2") is not None or o.get("y2") is not None:
            d["x2"] = _n(o.get("x2"), 8, 92, d["x"]); d["y2"] = _n(o.get("y2"), 5, 95, d["y"])
            d["mov_ini"] = _n(o.get("mov_ini"), 0, 0.7, 0.2); d["mov_fim"] = _n(o.get("mov_fim"), 0.3, 1, 0.8)
        if o.get("anim") in ANIM_OK: d["anim"] = o["anim"]
        if o.get("cor") in COR_OK: d["cor"] = o["cor"]
        if o.get("rotulo"): d["rotulo"] = str(o["rotulo"])[:18]
        out["objetos"].append(d)
    for fl in (sp.get("fluxos") or [])[:2]:
        if not isinstance(fl, dict): continue
        de, pa = _par(fl.get("de")), _par(fl.get("para"))
        if de and pa:
            out["fluxos"].append({"item": fl.get("item") if fl.get("item") in OBJ_OK else "moeda", "de": de, "para": pa,
                                  "n": int(_n(fl.get("n"), 2, 6, 4)), "cor": fl.get("cor") if fl.get("cor") in COR_OK else "lime"})
    for l in (sp.get("linhas") or [])[:6]:
        if not isinstance(l, dict): continue
        de, pa = _par(l.get("de")), _par(l.get("para"))
        if de and pa:
            out["linhas"].append({"de": de, "para": pa, "quando": _n(l.get("quando"), 0, 0.8, 0.1), "tracejada": bool(l.get("tracejada")),
                                  "cor": l.get("cor") if l.get("cor") in COR_OK else "verde"})
    for t in (sp.get("textos") or [])[:3]:
        if not isinstance(t, dict) or not t.get("t"): continue
        d = {"t": str(t["t"])[:24], "x": _n(t.get("x"), 15, 85, 50), "y": _n(t.get("y"), 3, 60, 12), "tam": _n(t.get("tam"), 28, 100, 56),
             "cor": t.get("cor") if t.get("cor") in COR_OK else "branco", "quando": _n(t.get("quando"), 0, 0.85, 0.1)}
        if t.get("de") is not None and t.get("para") is not None: d["de"] = _n(t["de"], 0, 1e9, 0); d["para"] = _n(t["para"], 0, 1e9, 0)
        out["textos"].append(d)
    # objetos soltos não podem cair em cima dos bonequinhos (corpo ocupa y>=42 em volta do x do ator)
    xs = []
    for a in out["atores"]:
        xs.append(a["x"])
        if "x2" in a: xs.append(a["x2"])
    for o in out["objetos"]:
        if o["y"] > 40 and "y2" not in o and any(abs(o["x"] - x) < 13 for x in xs):
            o["y"] = 24
    if not (out["atores"] or out["objetos"] or out["fluxos"]):
        return None
    return out


GEN_SIS = (
    "Você é diretor de motion design de um canal brasileiro de crítica social, estilo neon matrix com bonequinhos. "
    "Para cada trecho de fala você desenha UMA cena nova, feita sob medida para aquela frase, descrita em JSON. "
    "A cena precisa ilustrar de forma concreta e específica o que foi dito (uma metáfora visual clara), nunca algo genérico. "
    "Cada cena deve ter composição diferente das outras (outros objetos, outras posições, outras ações).\n"
    "Responda SOMENTE JSON: lista de {\"i\":n,\"spec\":{...}}.\n"
    "A área é um quadro; coordenadas em PORCENTAGEM: x 0-100 (esq→dir), y 0-100 (topo→chão; o chão é y=100; pessoas ficam no chão; objetos soltos y 10-60). "
    "Evite colocar coisas fora de x 10-90.\n"
    "spec: {\"atores\":[{\"tipo\":\"pessoa|robo\",\"x\":n,\"x2\":n(opcional, se anda até lá),\"acao\":\"parado|andar|correr|trabalhar|sentado|comemorar|apontar|cabisbaixo|carregar|pedir\",\"quando\":0-0.8,\"cor\":\"lime|rosa|branco\"(opcional),\"olhar\":\"esq\"(opcional)}] (máx 4), "
    "\"objetos\":[{\"tipo\":\"casa|moeda|nota|coracao|celular|relogio|predio|caixa|cofre|grafico|documento|carrinho|cadeado|engrenagem|olho|balanca|lampada|seta|estrela|sacola\",\"x\":n,\"y\":n,\"tam\":0.6-2,\"anim\":\"flutuar|pulsar|girar|tremer|subir|sumir\"(opcional),\"quando\":0-0.85,\"x2\":n,\"y2\":n (opcional: o objeto se move até lá),\"rotulo\":\"texto curto\"(opcional),\"cor\":\"lime|rosa|branco\"}] (máx 7), "
    "\"fluxos\":[{\"item\":tipo de objeto,\"de\":[x,y],\"para\":[x,y],\"n\":2-6,\"cor\":...}] (máx 2; coisas viajando de um ponto a outro, ex.: dinheiro saindo do salário para as contas), "
    "\"linhas\":[{\"de\":[x,y],\"para\":[x,y],\"quando\":0-0.8}] (máx 5; conexões/hierarquia), "
    "\"textos\":[{\"t\":\"até 20 caracteres, ex.: R$ {n}\",\"x\":n,\"y\":n,\"tam\":40-90,\"cor\":\"lime|rosa|branco\",\"quando\":0-0.8,\"de\":0,\"para\":3000 (opcional: número que conta de 'de' até 'para' no lugar de {n})}] (máx 2), \"matriz\":false}\n"
    "REGRAS: pessoas = gente comum (cor lime); robôs só para sistema, IA, poder, empresas, controle. Use texto só quando um número ou palavra-chave ajudar "
    "(use números só se a fala os citar; não invente dados). Sem logotipos ou marcas reais. Poucos elementos bem compostos valem mais que muitos. "
    "Mostre AÇÃO: algo se move, muda, aparece ou é trocado, em sincronia com a ideia. "
    "Cada cena deve ter de 3 a 6 elementos (atores + objetos + fluxos), com um começo e um desfecho visual (use 'quando' para escalonar e x2/y2 para mover). "
    "Pessoas e robôs ocupam y 45-100 em volta do seu x: coloque objetos soltos em y 8-38 (acima das cabeças) ou longe do x dos atores; "
    "só use objetos y>40 se estiverem longe de qualquer ator ou se forem se mover (x2,y2). Texto só com palavras que aparecem na fala; nunca palavras de efeito inventadas como PERIGO."
)


def _gerar_specs(segs, plano, log):
    """Pede à IA uma cena sob medida para cada segmento animado ('gen'). Sem spec válida -> o trecho vira full."""
    ws = [(w["s"], w["w"]) for l in plano.get("legendas") or [] for w in l["palavras"]]
    alvo = [i for i, sg in enumerate(segs) if sg.get("cena") == "gen"]
    if not alvo:
        return
    textos = {}
    for i in alvo:
        sg = segs[i]
        textos[i] = " ".join(w for s, w in ws if sg["s"] - 0.05 <= s < sg["e"])
    prontos = 0
    for k in range(0, len(alvo), 6):
        lote = alvo[k:k + 6]
        usr = "Trechos (i, duração em s, fala):\n" + "\n".join(f"{i}\t{segs[i]['e'] - segs[i]['s']:.1f}\t{textos[i]}" for i in lote)
        try:
            res, modelo = ia.pedir(GEN_SIS, usr, log, temperatura=0.8)
            if isinstance(res, dict):
                res = res.get("cenas") or res.get("itens") or list(res.values())[0]
            for x in res:
                i = int(x.get("i", -1))
                if i in lote:
                    v = _validar(x.get("spec"))
                    if v: segs[i]["spec"] = v; prontos += 1
        except Exception as e:
            log(f"neon: IA falhou ao gerar cenas do lote ({e})")
    for i in alvo:
        if "spec" not in segs[i]:
            segs[i]["m"], segs[i]["cena"] = "full", None          # sem cena válida: mantém ela em tela (sem desenho pré-pronto)
    log(f"neon: {prontos}/{len(alvo)} cenas geradas sob medida")


def aplicar(plano, c, log, cta=True):
    fmt, total = plano["formato"], plano["frames"] / plano["fps"]
    horiz = fmt == "16x9"
    alvo_pct = c.get("neon_anim_yt", 0.35) if horiz else c.get("neon_anim_corte", 0.5)
    unids = _sentencas(plano)
    jan = _blocos_broll(plano)
    ia_ok = False
    if unids and c.get("usar_ia", True):
        try:
            dec = _decidir_ia(unids, jan, alvo_pct, total, log); ia_ok = True
        except Exception as e:
            log(f"neon: IA indisponível ({e}); usando ritmo alternado")
    if not ia_ok:
        dec = _decidir_ritmo(unids)
    # monta segmentos
    segs = []
    for u, d in zip(unids, dec):
        m = d.get("m", "full"); cena = d.get("cena")
        if ia_ok and m != "full": cena = "gen"
        if m not in MODOS or (m != "full" and cena not in CATALOGO and cena != "gen"): m, cena = "full", None
        if m != "full" and cena != "gen" and not _combina(cena, u["texto"]):          # cena sem relação com a fala: troca por uma que combine ou vira full
            alt = [k for k in CATALOGO if k != "vai" and _combina(k, u["texto"])]
            if alt: cena = alt[0]
            else: m, cena = "full", None
        if m == "full": cena = None
        segs.append(dict(s=round(u["ini"], 2), e=round(u["fim"], 2), m=m, cena=cena))
    if not segs:
        segs = [dict(s=0, e=round(total + 1, 2), m="full", cena=None)]
    segs[0]["s"] = 0.0
    segs[-1]["e"] = round(total + 1, 2)
    for a, b in zip(segs, segs[1:]): a["e"] = b["s"]          # sem buracos
    # janelas com B-roll real mandam: split + broll nesse intervalo
    for a, b in jan:
        novos = []
        for sg in segs:
            if sg["e"] <= a or sg["s"] >= b: novos.append(sg); continue
            if sg["s"] < a: novos.append(dict(sg, e=a))
            if sg["e"] > b: novos.append(dict(sg, s=b))
        novos.append(dict(s=a, e=b, m="split", cena="broll"))
        segs = sorted(novos, key=lambda x: x["s"])
    # remove trechos minúsculos (< 1.2 s) absorvendo-os no anterior
    lim = []
    for sg in segs:
        if lim and (sg["e"] - sg["s"]) < 1.2 and sg["cena"] != "broll": lim[-1]["e"] = sg["e"]
        else: lim.append(sg)
    segs = lim
    # regras: 'over' curto e raro; animação contínua <= 9 s; cena sem repetir em 60 s; início/fim em full
    ult_over, hist = -99, {}
    for sg in segs:
        dur = sg["e"] - sg["s"]
        if sg["m"] == "over" and (sg["s"] - ult_over < 60 or dur > 4.0):
            sg["m"] = "take" if dur > 4.0 else "full"
            if sg["m"] == "full": sg["cena"] = None
        if sg["m"] == "over": ult_over = sg["s"]
        if sg["cena"] and sg["cena"] not in ("broll", "gen"):
            if sg["s"] - hist.get(sg["cena"], -99) < 60:
                alt = [k for k in CATALOGO if sg["s"] - hist.get(k, -99) >= 60 and k != "vai"]
                if alt: sg["cena"] = alt[0]
                else: sg["m"], sg["cena"] = "full", None
            if sg["cena"]: hist[sg["cena"]] = sg["s"]
    out = []
    for sg in segs:
        dur = sg["e"] - sg["s"]
        if sg["m"] in ("take", "split") and dur > 9.0 and sg["cena"] != "broll":
            meio = round(sg["s"] + 6.0, 2)
            out.append(dict(sg, e=meio)); out.append(dict(s=meio, e=sg["e"], m="full", cena=None))
        else:
            out.append(sg)
    segs = out
    if segs[0]["m"] != "full": segs[0]["m"], segs[0]["cena"] = "full", None
    if total > 12 and segs[-1]["m"] != "full": segs[-1]["m"], segs[-1]["cena"] = "full", None
    # junta segmentos adjacentes idênticos
    fim = []
    for sg in segs:
        if fim and fim[-1]["m"] == sg["m"] == "full": fim[-1]["e"] = sg["e"]
        else: fim.append(sg)
    _gerar_specs(fim, plano, log)
    anim = sum(s["e"] - s["s"] for s in fim if s["m"] != "full")
    plano["segs"] = fim
    plano["canal"] = "Natinha"
    plano["cta"] = bool(cta and not horiz)
    tema = (plano.get("corte") or {}).get("tema") or ""
    pal = tema.split()
    if pal:
        k = 1 if len(pal[-1]) >= 4 or len(pal) == 1 else 2
        plano["vtitle"] = dict(pre=" ".join(pal[:-k]), acc=" ".join(pal[-k:]).upper())
    log(f"neon: {len(fim)} segmentos, animação {100 * anim / max(1, total):.0f}% do tempo "
        f"({sum(1 for s in fim if s['cena'] == 'broll')} com B-roll real)")
    return plano


def aplicar_cache(plano, c, log, arq):
    """Decisão determinística entre execuções: reaproveita os segmentos já escolhidos (não invalida partes renderizadas)."""
    import json, os
    chaves = ("segs", "canal", "cta", "vtitle")
    if os.path.exists(arq):
        try:
            d = json.load(open(arq, encoding="utf-8"))
            if d.get("frames") == plano["frames"] and d.get("formato") == plano["formato"]:
                plano.update({k: d[k] for k in chaves if k in d}); log("neon: segmentos reaproveitados do job"); return plano
        except Exception:
            pass
    aplicar(plano, c, log)
    json.dump(dict({k: plano[k] for k in chaves if k in plano}, frames=plano["frames"], formato=plano["formato"]), open(arq, "w", encoding="utf-8"), ensure_ascii=False)
    return plano