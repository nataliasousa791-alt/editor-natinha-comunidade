"""Planejador de cenas v2 — fala (palavras na timeline editada) -> plano JSON da composição Remotion genérica.
Formatos: '9x16' (TikTok/Reels/Shorts) e '16x9' (YouTube). Modo 'limpo' (sem B-roll/animação) ou 'completo'.
Todo texto na tela é trecho LITERAL da fala. Cada cena registra fala, gatilho, tempos, justificativa e asset."""
import re, unicodedata
from nucleo.transcrever import frases, limpo
from nucleo import ia, biblioteca

ARTIGO = {"o", "a", "os", "as", "nossas", "nossos", "nossa", "nosso", "seu", "sua", "seus", "suas", "meu", "minha",
          "do", "da", "dos", "das", "no", "na", "mais", "outro", "outra", "esse", "essa", "um", "uma", "de", "pra", "para"}
VAZIA = ARTIGO | {"que", "e", "é", "não", "né", "eu", "você", "ele", "ela", "eles", "a gente", "gente", "isso", "aquilo", "como",
                  "mas", "porque", "então", "aí", "tipo", "tá", "está", "ser", "ter", "tem", "vai", "vou", "foi", "era", "com",
                  "por", "se", "ao", "nos", "nas", "também", "muito", "assim", "só", "já", "quando", "onde", "qual", "quem"}
FRACAS = {"pode", "podem", "posso", "sirvo", "serve", "faz", "fazer", "quer", "quero", "querem", "tem", "temos", "têm", "vai", "vão",
          "sei", "sabe", "acho", "acha", "fala", "falo", "diz", "dizer", "vem", "veio", "deu", "dá", "dar", "são", "estão", "estava",
          "fica", "ficar", "coloca", "colocar", "pega", "pegar", "olha", "olhar", "gente", "coisa", "coisas", "aqui", "agora", "sempre",
          "nunca", "ainda", "mesmo", "tudo", "nada", "todo", "toda", "todos", "todas", "cada", "outro", "outra", "dele", "dela",
          "nosso", "nossa", "realmente", "exatamente", "simplesmente", "galera", "pessoal", "menino", "menina", "cara", "mano"}
DENS = {"9x16": dict(sep=0.8, dur_min=2.2, dur_max=6.0),
        "16x9": dict(sep=1.2, dur_min=2.6, dur_max=7.0)}


def _sem_acento(x):
    return "".join(ch for ch in unicodedata.normalize("NFD", x) if unicodedata.category(ch) != "Mn")


def _n(x):
    return _sem_acento(limpo(x))


def _conceito(wl, c):
    for k, v in c["conceitos"].items():
        if wl in v["gatilhos"]: return k
    return None


PONTA = {"e", "é", "de", "da", "do", "das", "dos", "que", "a", "o", "as", "os", "em", "no", "na", "com", "pra", "para", "por",
         "se", "um", "uma", "mas", "ou", "porque", "então", "aí", "né", "tipo", "isso", "esse", "essa", "ao", "nos", "nas"}


def aparar(words, r):
    """Tira palavras funcionais do começo e do fim de um trecho (i0, i1); None se sobrar nada."""
    if not r: return None
    i0, i1 = r
    while i0 <= i1 and _n(words[i1]["w"]) in PONTA: i1 -= 1
    while i0 <= i1 and _n(words[i0]["w"]) in PONTA - {"a", "o", "as", "os"}: i0 += 1
    return (i0, i1) if i0 <= i1 else None


def trecho(words, texto, i_min=0, i_max=None):
    """Acha 'texto' como sequência de palavras (sem acento/pontuação; tolera 1 palavra diferente se >=4)."""
    alvo = [_n(x) for x in str(texto).split() if _n(x)]
    if not alvo: return None
    i_max = len(words) if i_max is None else i_max
    ws = [_n(w["w"]) for w in words]
    for tol in (0, 1):
        if tol and len(alvo) < 4: break
        for i in range(i_min, i_max - len(alvo) + 1):
            dif = sum(1 for a, b in zip(ws[i:i + len(alvo)], alvo) if a != b)
            if dif <= tol and ws[i] == alvo[0]: return i, i + len(alvo) - 1
    return None


def _legendas(words, destaques, ate):
    out, cur = [], []
    for i, w in enumerate(words):
        if w["s"] >= ate - 0.05: break
        cur.append(i); nx = words[i + 1] if i + 1 < len(words) else None
        if (len(cur) >= 5 or sum(len(words[j]["w"]) + 1 for j in cur) >= 28 or not nx or nx["s"] - w["e"] > 0.25
                or w["w"][-1] in ".,?!…"):
            out.append(cur); cur = []
    if cur: out.append(cur)
    leg = []
    for k, ch in enumerate(out):
        prox = words[out[k + 1][0]]["s"] if k + 1 < len(out) else min(ate, words[ch[-1]]["e"] + 0.6)
        leg.append(dict(ini=round(words[ch[0]]["s"] - 0.03, 3), fim=round(min(prox - 0.03, words[ch[-1]]["e"] + 0.25, ate), 3),
                        palavras=[dict(w=words[j]["w"], s=words[j]["s"], destaque=j in destaques) for j in ch]))
    return leg


def _sugestoes(F, c, formato, log):
    """IA: título, cenas por frase (broll com busca em inglês, cartão, ênfase), destaques e frases sensíveis. Em lotes."""
    sug = dict(titulo="", cenas=[], destaques=[], evitar=set())
    if not c.get("usar_ia"): return sug
    for ini in range(0, len(F), 70):
        lote = F[ini:ini + 70]
        txt = "\n".join(f"F{ini + k} | {f['texto']}" for k, f in enumerate(lote))
        alvo = "vídeo vertical curto (TikTok/Reels)" if formato == "9x16" else "vídeo horizontal do YouTube"
        try:
            r, modelo = ia.pedir(
                "Você é diretor de arte de videoensaios documentais da criadora brasileira Natinha (crítica social, comportamento). "
                "Estética: documentário brasileiro realista, grafite e âmbar. Copie trechos LITERAIS da fala (mesmas palavras e ordem). "
                "Nunca invente fatos. Responda só JSON.",
                f"Fala de um {alvo}, em frases:\n{txt}\n\n"
                "Contexto integral da narrativa:\n" + "\n".join(f["texto"] for f in F) + "\n\n"
                "Identifique tese, argumentos e exemplos. Para as frases que ganham com um recurso visual, proponha UMA cena, sem quota fixa:\n"
                "- broll: filmagem REAL pertinente ao argumento, objeto ou ação. Analogia visual exige justificativa e não pode sugerir fato novo. "
                "'busca' = consulta principal; 'consultas' = até 3 variantes em português/inglês; 'justificativa' = por que ajuda. 'rotulo' = 1-2 palavras em português (maiúsculas); "
                "'gatilho' = a palavra literal da frase que dispara a imagem. Proibido: favela para pobreza, luxo para riqueza, "
                "fábrica antiga para trabalho, multidão genérica, imagens de violência ou tema sensível.\n"
                "- cartao: frase de impacto curta; 'trecho' = 3 a 8 palavras literais.\n"
                "- numero: quando a frase cita um número/valor.\n"
                "- enfase: palavra-chave forte; 'trecho' = 1 a 3 palavras literais.\n"
                "Deixe sem cena as frases em que a apresentadora deve ficar sozinha (perguntas íntimas, ironia no rosto, temas sensíveis).\n"
                'JSON: {"titulo":"trecho literal de 3 a 6 palavras com o tema","cenas":[{"frase":"F3","tipo":"broll","gatilho":"...",'
                '"busca":"...","consultas":["..."],"justificativa":"...","rotulo":"..."},{"frase":"F5","tipo":"cartao","trecho":"..."},{"frase":"F9","tipo":"enfase","trecho":"..."}],'
                '"destaques":["palavras literais importantes"],"evitar_imagem":["F2"]}', log, temperatura=0.35)
            log(f"sugestões de cena ({modelo}): {len(r.get('cenas', []))} para F{ini}-F{ini + len(lote) - 1}")
        except Exception as e:
            log(f"IA de cenas indisponível ({e}); seguindo só com regras"); break
        if not sug["titulo"]: sug["titulo"] = r.get("titulo", "")
        sug["cenas"] += [x for x in r.get("cenas", []) if isinstance(x, dict)]
        sug["destaques"] += [x for x in r.get("destaques", []) if isinstance(x, str)]
        for x in r.get("evitar_imagem", []):
            try: sug["evitar"].add(int(str(x).upper().lstrip("F")))
            except ValueError: pass
    return sug


def planejar(words, blocos, total, chave_job, rosto, fonte_wh, c, log, formato="9x16", modo="completo"):
    chave_video, job_id = chave_job.split("#")
    D = DENS[formato]
    F = frases(words, max_palavras=18, pausa=0.6)
    if len(F) >= 2 and F[-1]["i1"] - F[-1]["i0"] < 3:   # fechamento nunca curto
        a, b = F[-2], F[-1]
        F = F[:-2] + [dict(a, i1=b["i1"], e=b["e"], texto=a["texto"] + " " + b["texto"], fim=b["fim"])]
    sem = {_n(x) for x in c["sem_broll"]}
    nao = [[_n(y) for y in x.split()] for x in c.get("expressoes_nao_conceito", [])]
    lw = [_n(w["w"]) for w in words]
    cenas, usados = [], set()

    # FECHAMENTO: última frase inteira (até 12 palavras finais), palavra a palavra no tempo da fala
    fl = F[-1]; i0f = max(fl["i0"], fl["i1"] - 11)
    fech = dict(id="fechamento", tipo="fechamento", layout="A", ini=round(words[i0f]["s"] - 0.1, 3), fim=round(total, 3),
                palavras=[dict(w=words[i]["w"], s=words[i]["s"]) for i in range(i0f, fl["i1"] + 1)],
                fala=fl["texto"], justificativa="conclusão da própria fala em destaque tipográfico")
    sem_leg_desde = fech["ini"]
    if modo == "limpo":
        return dict(cenas=[], legendas=_legendas(words, set(), total + 1), blocosB=[], blocosC=[],
                    cortesInternos=[b["out"] for b in blocos[1:]], formato=formato, modo=modo,
                    fonte=dict(arquivo="natinha.mp4", w=fonte_wh[0], h=fonte_wh[1], rosto=rosto), audio="voz.m4a")

    sug = _sugestoes(F, c, formato, log)
    # ABERTURA: título literal, fora do fechamento
    ab_fim = min(max(F[0]["e"] + 0.1, 2.6), 3.6)
    tit = aparar(words, trecho(words, sug["titulo"], 0, i0f)) if sug["titulo"] else None
    if not tit or tit[1] - tit[0] > 6 or tit[1] - tit[0] < 1:
        f0 = F[0]; tit = aparar(words, (f0["i0"], f0["i1"]) if f0["i1"] - f0["i0"] < 6 else (f0["i1"] - 5, f0["i1"])) or (f0["i0"], f0["i1"])
    cenas.append(dict(id="abertura", tipo="abertura", layout="A", ini=0.0, fim=round(ab_fim, 3),
                      texto=[words[i]["w"].strip(",.;:") for i in range(tit[0], tit[1] + 1)],
                      fala=F[0]["texto"], justificativa="título literal da fala que resume o tema"))
    livre_ini, livre_fim = ab_fim + 0.8, fech["ini"] - 0.9

    def cabe(a, b):
        return (a >= livre_ini and b <= livre_fim and
                all(b + D["sep"] <= x["ini"] or a >= x["fim"] + D["sep"] for x in cenas[1:]))

    def em_expressao(i):
        return any(lw[j:j + len(e)] == e for e in nao for j in range(max(0, i - len(e) + 1), i + 1))

    def sensivel(f):
        return any(lw[i] in sem for i in range(f["i0"], f["i1"] + 1))

    def tempo_frase(f, i):
        a = f["s"] - 0.1 if words[i]["s"] - f["s"] < 2.5 else words[i]["s"] - 0.4
        return a, max(a + D["dur_min"], min(f["e"] + 0.25, a + D["dur_max"]))

    def frase_de(i):
        return next(f for f in F if f["i0"] <= i <= f["i1"])

    lay_broll = "C" if formato == "16x9" else "B"
    cands = []
    # números falados -> contador (prioridade máxima)
    for i, w in enumerate(words):
        m = re.search(r"(\d+[\d.,]*)", w["w"])
        if not m: continue
        try: val = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError: continue
        prox = words[i + 1]["w"].strip(",.?!") if i + 1 < len(words) else ""
        unid = prox if _n(prox) in ("horas", "reais", "mil", "anos", "dias", "vezes", "pessoas", "milhoes", "bilhoes", "por cento", "meses") else ""
        if not unid and "%" not in w["w"] and "R$" not in w["w"]: continue
        f_ = frase_de(i); ctx = [words[j]["w"].strip(",.?!;:") for j in range(max(f_["i0"], i - 5), i)]
        while ctx and _n(ctx[0]) in VAZIA - {"com", "por"}: ctx = ctx[1:]
        cands.append((0, dict(tipo="numero", layout="B", ini=w["s"] - 0.3, fim=w["e"] + 2.4, valor=val, contexto=" ".join(ctx[-4:]),
                              prefixo="R$" if "R$" in w["w"] or (i and words[i - 1]["w"] == "R$") else "",
                              sufixo="%" if "%" in w["w"] or _n(prox) == "porcento" else "", unidade=unid,
                              gatilho=dict(palavra=w["w"], t=w["s"]), fala=frase_de(i)["texto"],
                              justificativa="número dito na fala vira contador com o valor exato")))
    nums = [x for pr, x in cands if x["tipo"] == "numero"]
    grupos = []
    for x in nums:
        g = grupos[-1] if grupos else None
        if g and x["gatilho"]["t"] - g[-1]["gatilho"]["t"] < 3.0 and x["fala"] == g[-1]["fala"]: g.append(x)
        else: grupos.append([x])
    cands = [(pr, x) for pr, x in cands if x["tipo"] != "numero"]
    for g in grupos:
        y = dict(g[0]); y["fim"] = g[-1]["fim"]
        y["valores"] = [dict(valor=v["valor"], prefixo=v["prefixo"], sufixo=v["sufixo"], unidade=v["unidade"], t=v["gatilho"]["t"],
                             contexto=v.get("contexto", "")) for v in g]
        cands.append((0, y))
    # sugestões da IA (validadas: literais, frase não sensível, gatilho fora de expressão não-conceito)
    for x in sug["cenas"]:
        try: fi = int(str(x.get("frase", "")).upper().lstrip("F"))
        except ValueError: continue
        if not (0 <= fi < len(F)) or fi in sug["evitar"] or sensivel(F[fi]): continue
        f = F[fi]
        if x.get("tipo") == "broll" and x.get("busca"):
            r = trecho(words, x.get("gatilho", ""), f["i0"], f["i1"] + 1)
            if not r or em_expressao(r[0]): continue
            a, b = tempo_frase(f, r[0])
            cands.append((1, dict(tipo="broll", layout=lay_broll, ini=a, fim=b, i=r[0], busca=str(x["busca"])[:60],
                                  rotulo=str(x.get("rotulo", "")).upper()[:24], fala=f["texto"],
                                  consultas=[str(q)[:80] for q in x.get("consultas", []) if isinstance(q,str)][:3],
                                  justificativa=str(x.get("justificativa", "recurso pertinente à fala"))[:300])))
        elif x.get("tipo") in ("cartao", "enfase"):
            r = aparar(words, trecho(words, x.get("trecho", ""), f["i0"], f["i1"] + 1))
            lim = 8 if x["tipo"] == "cartao" else 3
            if r and x["tipo"] == "cartao" and r[1] - r[0] < 1: continue
            if not r or r[1] - r[0] >= lim: continue
            a, b = words[r[0]]["s"] - 0.25, words[r[1]]["e"] + (0.7 if x["tipo"] == "cartao" else 0.9)
            cands.append((2 if x["tipo"] == "cartao" else 3, dict(tipo=x["tipo"], layout="B" if x["tipo"] == "cartao" else "A",
                          ini=a, fim=max(b, a + (1.8 if x["tipo"] == "cartao" else 1.6)),
                          palavras=[dict(w=words[j]["w"].strip(",;:" if (x["tipo"] == "cartao" and j == r[1]) else ",.;:!…"), s=words[j]["s"])
                                    for j in range(r[0], r[1] + 1)], fala=f["texto"])))
    # regras (sem IA ou complemento): conceitos do config e perguntas curtas
    for fi, f in enumerate(F):
        if fi in sug["evitar"] or sensivel(f): continue
        for i in range(f["i0"], f["i1"] + 1):
            k = _conceito(lw[i], c) or _conceito(limpo(words[i]["w"]), c)
            if k and not em_expressao(i):
                a, b = tempo_frase(f, i)
                cands.append((4, dict(tipo="broll", layout=lay_broll, ini=a, fim=b, i=i, conceito=k,
                                      rotulo=c["conceitos"][k]["rotulo"], fala=f["texto"]))); break
        if f["fim"] in ("?", "!") and 4 <= f["i1"] - f["i0"] + 1 <= 9:
            cands.append((5, dict(tipo="cartao", layout="B", ini=f["s"] - 0.25, fim=f["e"] + 0.7,
                                  palavras=[dict(w=words[j]["w"].strip(",;:"), s=words[j]["s"]) for j in range(f["i0"], f["i1"] + 1)],
                                  fala=f["texto"])))
    # Agenda por pertinência e duração legível; sem quota de cobertura.
    for pr, x in sorted(cands, key=lambda z: (z[0], z[1]["ini"])):
        a, b = round(x["ini"], 3), round(x["fim"], 3)
        if not cabe(a, b): continue
        
        if x["tipo"] == "broll":
            i = x.pop("i")
            if "busca" in x:
                clip = biblioteca.obter(biblioteca.chave_busca(x["busca"]), chave_video, usados, log, job_id, x.get("consultas") or [x["busca"]], frase=x["fala"])
                origem = f"sugestão da IA: busca '{x['busca']}'"
            else:
                clip = biblioteca.obter(x["conceito"], chave_video, usados, log, job_id, frase=x["fala"])
                origem = f"conceito '{x['conceito']}' do config"
            if not clip:
                f0=frase_de(i); j0=max(f0["i0"],i-2); j1=min(f0["i1"],j0+5)
                cenas.append(dict(id=f"alternativa{len(cenas)}",tipo="cartao",layout="B",ini=a,fim=b,
                    palavras=[dict(w=words[j]["w"],s=words[j]["s"]) for j in range(j0,j1+1)],fala=x["fala"],
                    justificativa="Sem imagem pertinente disponível; destaque literal da fala.",
                    busca_tentada=x.get("consultas") or [x.get("busca") or x.get("conceito")]))
                log(f"Sem B-roll pertinente: cartão literal, {a:.1f}-{b:.1f}s")
                continue
            usados.add(clip["id"])
            j0 = i - 1 if i > frase_de(i)["i0"] and lw[i - 1] in ARTIGO else i
            dur_cena = b - a + 0.9
            ini_clip = 0.6 if clip.get("duracao", 8) >= dur_cena + 0.8 else 0.0
            x.update(frase=[dict(w=words[j]["w"].strip(",.?!;:"), s=words[j]["s"]) for j in range(j0, i + 1)],
                     gatilho=dict(palavra=words[i]["w"], t=words[i]["s"]),
                     asset=dict(id=clip["id"], arquivo="broll_" + clip["arquivo"], origem=clip["caminho"], fonte=clip["fonte"],
                                autor=clip["autor"], licenca=clip["licenca"], revisado=clip.get("revisado", False),
                                inicio=ini_clip, duracao=clip.get("duracao", 8), w=clip.get("largura"), h=clip.get("altura"),
                                laco=clip.get("duracao", 8) < dur_cena + ini_clip),
                     justificativa=x.get("justificativa") or f"Apoio ao conceito mencionado: {origem}")
            if not x.get("rotulo"): x["rotulo"] = "CONTEXTO"
        x.update(ini=a, fim=b, id=f"{x['tipo']}{len(cenas)}")
        cenas.append(x)
    # Sem preencher lacunas por cronômetro.
    pal_ia = {_n(x) for x in sug["destaques"]}
    cenas.append(fech)
    cenas.sort(key=lambda x: x["ini"])
    dest, ult = set(), -9
    for i, w in enumerate(words):
        if (lw[i] in pal_ia or _conceito(lw[i], c)) and w["s"] - ult > 4 and lw[i] not in VAZIA:
            dest.add(i); ult = w["s"]

    def blocos_de(lay):
        out = []
        for x in cenas:
            if x["layout"] != lay: continue
            if out and x["ini"] - out[-1][1] < 0.6: out[-1][1] = x["fim"]
            else: out.append([x["ini"], x["fim"]])
        return out
    return dict(cenas=cenas, legendas=_legendas(words, dest, total + 1), blocosB=blocos_de("B"), blocosC=blocos_de("C"),
                cortesInternos=[b["out"] for b in blocos[1:]], formato=formato, modo=modo,
                fonte=dict(arquivo="natinha.mp4", w=fonte_wh[0], h=fonte_wh[1], rosto=rosto), audio="voz.m4a")
