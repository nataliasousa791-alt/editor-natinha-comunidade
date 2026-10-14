"""Escolha dos cortes (Reels/TikTok) com começo, meio e fim."""
import json, os, re
from .transcrever import frases
from .util import ler_config
from . import ia

PROMPT_CORTES = """Você é editora-chefe dos cortes verticais (Reels/TikTok) do vídeo da Natinha (análise comportamental,
crítica social, consciência; tom direto, visceral, sem moralismo). Recebe a transcrição da versão final INTEIRA em frases
numeradas, com tempos.

PASSO 1 — ANTES de escolher, leia o vídeo inteiro e entenda:
- o tema principal e os subtemas (cada parte do vídeo fala de quê);
- onde estão as ideias mais fortes: opinião firme, conflito, surpresa, revelação, contradição, quebra de crença,
  comparação, pergunta provocadora, algo que muita gente vive mas não costuma dizer, explicação prática,
  exemplo/história concreta, frase que gera debate, informação surpreendente;
- quais trechos têm mais chance natural de reter, gerar comentário, compartilhamento ou identificação
  (critério editorial, não fórmula; nada de clickbait artificial).

PASSO 2 — escolha {n_cand} candidatos (os {n} melhores primeiro), cada um um PEQUENO VÍDEO COMPLETO:
- COMEÇO: a primeira frase ABRE a ideia sozinha (afirmação polêmica, pergunta, descoberta, contradição, opinião
  forte, curiosidade ou contextualização curta). Nunca começa com "e", "e aí", "então", "porque", "mas", "mas isso",
  "por isso", "como eu falei", nem fazendo referência a algo de antes que o espectador não viu
  (se precisar, comece algumas frases antes para recuperar o contexto);
- MEIO: desenvolvimento suficiente para a pessoa entender o argumento;
- FIM: conclusão, virada, revelação ou frase que FECHA o raciocínio (de preferência conversa com o começo).
  NUNCA termina no meio da ideia, numa enumeração pela metade, nem com "entendeu?" sozinho;
- NÃO depende de contexto que ficou fora (quem nunca viu o vídeo entende);
- NÃO escolha só porque UMA frase parece viral isolada: o trecho todo precisa sustentar;
- NUNCA inclui despedida ("espero que tenham gostado", "é isso", "tchau") nem pedido genérico de like;
- dura entre {mn} e {mx} segundos. NÃO termine porque "deu o tempo": se a ideia precisa de 1min40 ou 2min,
  preserve a ideia (1min40 completo é melhor que 58 s mutilados); não se sobrepõe a outro candidato;
- TESTE FINAL de cada candidato: "funciona para quem nunca viu o vídeo original?" Se não, descarte;
- prefira assuntos com potencial de polêmica, debate, surpresa, crença quebrada, descoberta, informação
  inesperada, comparação provocativa, opinião controversa ou história curiosa;
- DIVERSIDADE: os {n} primeiros devem tratar de SUBTEMAS DIFERENTES. Nada de três cortes dizendo a mesma coisa.
"gancho": 2 a 5 palavras em CAIXA ALTA que aparecem grandes na tela nos 3 primeiros segundos (a promessa do corte,
não repete a legenda; ex.: "SEU CORPO É ELÉTRICO"). Use palavras do próprio corte, sem exagero.
"legenda_post": 1-2 frases + uma PERGUNTA direta para a pessoa responder nos comentários + 3 hashtags.
Responda em JSON:
{{"analise": {{"tema": "1 frase", "subtemas": ["..."], "momentos_fortes": ["frase [k]: por quê"]}},
  "cortes": [{{"de": frase_inicial, "ate": frase_final, "subtema": "de que parte do vídeo é",
   "titulo": "título curto em caixa alta (máx. 6 palavras)", "gancho": "2 a 5 palavras",
   "por_que": "1 frase: o que prende, o que desenvolve, como fecha", "nota": 1 a 10,
   "legenda_post": "..."}}]}}"""


DESPEDIDA = re.compile(r"(espero que (voc[eê]s?|tenha|tenham)|é isso\.?$|tchau|beij(o|ão)|até (o|a) pr[oó]xim|"
                       r"gostou do v[ií]deo|deixa (seu|o) like|se inscrev|curte,? compartilh|me sig[am]|"
                       r"fico muito feliz de|um prazer conversar)", re.I)


def escolher(words, pasta, log=print):
    c = ler_config()
    extra_f = os.path.join(pasta, "youtube_extra.json")
    extra = json.load(open(extra_f, encoding="utf-8")) if os.path.exists(extra_f) else {}
    t0 = float(extra.get("teaser", 0) or 0)
    t1 = float(extra.get("fim_conteudo", 1e9) or 1e9)
    # a prévia (gancho do começo) é uma cópia de outra parte: não entra na escolha dos cortes
    words = [w for w in words if t0 - 0.01 <= w["s"] and w["e"] <= t1 + 0.05]
    fr = frases(words)
    texto = "\n".join(f"[{k}] ({f['s']:.1f}-{f['e']:.1f}s) {f['texto']}" for k, f in enumerate(fr))
    n = int(c["n_cortes"])
    prompt = PROMPT_CORTES.format(n=n, n_cand=n + 2, mn=c["corte_min"], mx=c["corte_max"])
    out = []
    for tentativa in range(2):
        extra_msg = "" if tentativa == 0 else (
            "\n\nATENÇÃO: a resposta anterior não serviu. Use os NÚMEROS das frases entre colchetes [k] em \"de\" e "
            "\"ate\" (não segundos), e cada corte com pelo menos " + str(c["corte_min"]) + " segundos.")
        resp, modelo = ia.pedir("cortes", prompt, texto + extra_msg, temperatura=0.5 + 0.2 * tentativa, log=log, forte=True)
        out = _validar(resp, fr, c, log)
        if out:
            _salvar_analise(resp, pasta, log)
            out = _diversos(out, n, log)
            break
        log("Nenhum corte da IA serviu; pedindo de novo…")
    log(f"IA ({modelo}) escolheu {len(out)} corte(s)")
    json.dump(out, open(os.path.join(pasta, "cortes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


CONECTOR_INICIO = re.compile(r"^(e|então|entao|porque|mas|aí|ai|daí|dai|tipo|né|ou seja|por isso|como eu (falei|disse)|"
                             r"como falei|voltando|isso a[ií]|e a[ií])\b[ ,.]", re.I)


# abertura que só faz sentido com o que veio antes: "Eles levavam isso…", "Isso mostra…", "Por causa disso…"
REFERENCIA_INICIO = re.compile(r"^(\W*(eles|elas|ele|ela)\b(\W+\w+){0,4}\W+(isso|isto|disso|nisso|aquilo)\b"
                               r"|\W*(isso|isto|disso|nisso|daquilo|aquilo|esse|essa|esses|essas|desse|dessa)\b"
                               r"|\W*por causa disso\b|\W*por qu[eê]\s*\?)", re.I)


def _salvar_analise(resp, pasta, log):
    """Guarda a análise do vídeo inteiro (vem na MESMA chamada dos cortes; nenhuma chamada a mais)."""
    an = resp.get("analise") if isinstance(resp.get("analise"), dict) else {}
    if not an:
        return
    arq = os.path.join(pasta, "analise_video.json")
    try:
        dados = json.load(open(arq, encoding="utf-8")) if os.path.exists(arq) else {}
        dados["analise"] = an
        json.dump(dados, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except (OSError, ValueError):
        pass
    if an.get("tema"):
        log(f"Tema do vídeo: {an.get('tema')}")


def _palavras(t):
    return {w for w in re.findall(r"[a-zà-ú]{4,}", (t or "").lower())}


def _diversos(cands, n, log):
    """Dos candidatos (em ordem de preferência), fica com n que não repitam o mesmo subtema/ideia."""
    escolhidos = []
    for c in cands:
        if len(escolhidos) >= n:
            break
        sub = (c.get("subtema") or "").strip().lower()
        pal = _palavras(c.get("titulo", "") + " " + c.get("gancho", "") + " " + sub)
        repetido = None
        for o in escolhidos:
            osub = (o.get("subtema") or "").strip().lower()
            opal = _palavras(o.get("titulo", "") + " " + o.get("gancho", "") + " " + osub)
            inter = len(pal & opal) / max(1, min(len(pal), len(opal)))
            if (sub and sub == osub) or inter >= 0.6:
                repetido = o
                break
        if repetido and len(cands) - cands.index(c) > n - len(escolhidos):
            log(f"(candidato \"{c.get('titulo', '')}\" parecido com \"{repetido.get('titulo', '')}\"; usando outro)")
            continue
        escolhidos.append(c)
    for k, c in enumerate(escolhidos):
        c["n"] = k + 1
    return escolhidos


def _indice(v, fr):
    """Número da frase; se a IA mandou segundos (número maior que a lista), acha a frase daquele tempo."""
    if isinstance(v, str) and not v.strip().replace(".", "", 1).isdigit():
        # a IA mandou o TEXTO da frase: acha a frase que mais combina
        alvo = v.strip().lower()[:60]
        ach = [k for k, f in enumerate(fr) if alvo[:30] and alvo[:30] in f["texto"].lower()]
        if not ach:
            import difflib
            ach = [max(range(len(fr)), key=lambda k: difflib.SequenceMatcher(None, alvo, fr[k]["texto"].lower()[:60]).ratio())]
        return ach[0]
    x = float(v)
    if x.is_integer() and 0 <= x < len(fr):
        return int(x)
    return min(range(len(fr)), key=lambda k: abs(fr[k]["s"] - x) if x < fr[k]["e"] else abs(fr[k]["e"] - x))


def _validar(resp, fr, c, log=print):
    out = []
    for r in resp.get("cortes", []):
        try:
            a, b = _indice(r["de"], fr), _indice(r["ate"], fr)
        except Exception:
            log(f"(corte ignorado: resposta sem números de frase: {str(r)[:80]})")
            continue
        a, b = max(0, a), min(len(fr) - 1, b)
        while b > a and DESPEDIDA.search(fr[b]["texto"]):      # tira despedida do fim do corte
            b -= 1
        if b < a:
            continue
        # ajusta a duração respeitando frases inteiras
        while fr[b]["e"] - fr[a]["s"] > c["corte_max"] + 5 and b > a:
            b -= 1
        while fr[b]["e"] - fr[a]["s"] < c["corte_min"] - 3 and b + 1 < len(fr) and not DESPEDIDA.search(fr[b + 1]["texto"]):
            b += 1
        # fim no meio da ideia (sem ponto final, ou a próxima frase continua com conector): estende até fechar
        for _ in range(3):
            aberto = not re.search(r"[.!?…]\W*$", fr[b]["texto"].strip()) or (
                b + 1 < len(fr) and CONECTOR_INICIO.match(fr[b + 1]["texto"].strip())
                and fr[b + 1]["s"] - fr[b]["e"] < 0.6)
            if not aberto or b + 1 >= len(fr) or DESPEDIDA.search(fr[b + 1]["texto"]) \
                    or fr[b + 1]["e"] - fr[a]["s"] > c["corte_max"] + 5:
                break
            b += 1
        # começo continuando algo de antes ("e…", "então…"): pula para a frase seguinte se ainda sobra corte
        if CONECTOR_INICIO.match(fr[a]["texto"].strip()) and a + 1 <= b and \
                fr[b]["e"] - fr[a + 1]["s"] >= c["corte_min"] - 3:
            a += 1
        # começo que depende de algo dito antes ("Eles levavam isso…"): puxa a frase anterior (dá o contexto);
        # se não couber, começa na frase seguinte
        for _ in range(2):
            if not (REFERENCIA_INICIO.search(fr[a]["texto"].strip()) or CONECTOR_INICIO.match(fr[a]["texto"].strip())):
                break
            if a > 0 and fr[b]["e"] - fr[a - 1]["s"] <= c["corte_max"] + 5 \
                    and not any(o["s"] < fr[a - 1]["s"] < o["e"] for o in out):
                a -= 1
                log(f"(corte começa com a frase anterior para não abrir com \"{fr[a + 1]['texto'][:30]}…\" sem contexto)")
            elif a + 1 <= b and fr[b]["e"] - fr[a + 1]["s"] >= c["corte_min"] - 3:
                a += 1
            else:
                break
        s = max(0.0, fr[a]["s"] - 0.15, fr[a - 1]["e"] + 0.05 if a > 0 else 0.0)
        e = fr[b]["e"] + 0.35
        if b + 1 < len(fr):
            e = min(e, fr[b + 1]["s"] - 0.05)
        e = max(e, fr[b]["e"] + 0.05)
        for o in out:   # encosta em cortes vizinhos sem sobrepor
            if o["s"] < e and s < o["e"]:
                if s >= o["s"] and o["e"] - s < 1.0:
                    s = o["e"]
                elif e <= o["e"] and e - o["s"] < 1.0:
                    e = o["s"]
        if any(o["s"] < e and s < o["e"] for o in out) or e - s < max(15, c["corte_min"] - 5):
            log(f"(corte \"{r.get('titulo', '')}\" ignorado: {e - s:.0f} s ou em cima de outro corte)")
            continue        # curto demais (ex.: só a frase final do vídeo) não vira corte
        post = (r.get("legenda_post") or "").strip()
        if "?" not in post:
            post = (post + "\n\nE você, o que acha? Me conta aqui nos comentários 👇").strip()
        out.append({"n": len(out) + 1, "s": round(s, 2), "e": round(e, 2), "f0": a, "f1": b,
                    "titulo": r.get("titulo", ""), "por_que": r.get("por_que", ""),
                    "subtema": r.get("subtema", ""),
                    "gancho": (r.get("gancho") or r.get("titulo") or "").strip().upper(),
                    "legenda_post": post})
    return out
