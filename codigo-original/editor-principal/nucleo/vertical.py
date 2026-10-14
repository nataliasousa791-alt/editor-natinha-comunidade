"""Entrada VERTICAL: vídeo que já chega em pé (pasta 'entrada_vertical').

Não gira, não vira YouTube, não escolhe cortes. Faz a mesma limpeza (erros, repetições, silêncios), e:
- até ~2 min: um vídeo só;
- mais que isso: partes de ~1 min a 1 min 30, divididas em fim de frase (de preferência nas pausas maiores),
  na ordem original, sem repetir e sem pular nada (a parte 2 começa exatamente onde a 1 terminou);
- cada parte ganha legenda, B-rolls/animações (mesmo motor dos cortes) e, menos a última, um "CONTINUA…" no fim.
A divisão é feita aqui, sem IA (não aumenta as chamadas ao Gemini).
"""
import json, os, re
from .transcrever import frases
from .util import ler_config


def dividir_partes(words, max_unico=125.0, alvo=78.0, minimo=58.0, maximo=95.0):
    """Devolve [(s, e)] contíguos cobrindo a fala toda. Cada fronteira fica no meio de uma pausa entre frases."""
    if not words:
        return []
    fim = words[-1]["e"] + 0.4
    if fim <= max_unico:
        return [(0.0, round(fim, 2))]
    fr = frases(words)
    # fronteiras possíveis: fim de frase; nota maior para pontuação final e pausa longa
    cands = []
    for k in range(len(fr) - 1):
        pausa = fr[k + 1]["s"] - fr[k]["e"]
        ponto = bool(re.search(r"[.!?…]$", fr[k]["texto"].strip()))
        if not ponto and pausa < 0.35:
            continue
        corte = round(fr[k]["e"] + pausa / 2, 2)
        cands.append((corte, (1.5 if ponto else 0) + min(pausa, 1.5) * 2))
    partes, ini = [], 0.0
    while fim - ini > maximo + 10:
        ok = [(t, n) for t, n in cands if minimo <= t - ini <= maximo]
        if not ok:                                         # sem fim de frase no intervalo: a primeira depois do mínimo
            ok = [(t, n) for t, n in cands if t - ini >= minimo][:1]
        if not ok:
            break
        t, _ = max(ok, key=lambda x: x[1] - abs((x[0] - ini) - alvo) / 12.0)
        partes.append((ini, t))
        ini = t
    partes.append((ini, round(fim, 2)))
    # sobra muito curta no fim: junta com a anterior (se couber) ou divide as duas de novo ao meio
    if len(partes) >= 2 and partes[-1][1] - partes[-1][0] < 45:
        a, _ = partes[-2]
        b = partes[-1][1]
        if b - a <= 125:
            partes[-2:] = [(a, b)]
        else:
            meio = [(t, n) for t, n in cands if a + 45 <= t <= b - 45]
            if meio:
                t, _ = max(meio, key=lambda x: x[1] - abs(x[0] - (a + b) / 2) / 12.0)
                partes[-2:] = [(a, t), (t, b)]
    return [(round(a, 2), round(b, 2)) for a, b in partes]


def processar_vertical(pasta, pr, proj):
    from . import transcrever, youtube, brolls, compor
    log = pr.log
    bruto = proj["bruto"]
    f_pal = os.path.join(pasta, "palavras_bruto.json")
    if not os.path.exists(f_pal):
        pr.etapa("Transcrevendo o áudio", 5)
        transcrever.transcrever(bruto, f_pal, log)
    words = json.load(open(f_pal, encoding="utf-8"))
    log(f"{len(words)} palavras transcritas")
    base = os.path.join(pasta, "youtube.mp4")              # aqui é a base vertical limpa (não é um vídeo do YouTube)
    if not os.path.exists(base):
        pr.etapa("Limpando o vídeo vertical (erros e silêncios)", 20)
        youtube.versao_youtube(bruto, words, pasta, log, 0, vertical=True)
    words_v = json.load(open(os.path.join(pasta, "youtube_palavras.json"), encoding="utf-8"))
    trechos = json.load(open(os.path.join(pasta, "youtube_trechos.json"), encoding="utf-8"))
    f_c = os.path.join(pasta, "cortes.json")
    if not os.path.exists(f_c):
        partes = dividir_partes(words_v)
        n = len(partes)
        meta = {}
        try:
            meta = json.load(open(os.path.join(pasta, "youtube_meta.json"), encoding="utf-8"))
        except (OSError, ValueError):
            pass
        tit = (meta.get("titulo") or "").strip()
        cortes = [{"n": k + 1, "s": a, "e": b, "titulo": (f"Parte {k + 1} de {n}" if n > 1 else (tit or "Vídeo")),
                   "gancho": "", "vertical": True, "continua": k < n - 1, "partes": n,
                   "legenda_post": (tit + (f" (parte {k + 1}/{n})" if n > 1 else "")).strip()}
                  for k, (a, b) in enumerate(partes)]
        json.dump(cortes, open(f_c, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log("Vídeo vertical: " + (f"{n} partes — " + ", ".join(f"{(b - a):.0f} s" for a, b in partes) if n > 1
                                  else f"um vídeo só ({partes[0][1]:.0f} s)"))
    lista = json.load(open(f_c, encoding="utf-8"))
    for k, ct in enumerate(lista):
        pc = os.path.join(pasta, f"corte_{ct['n']}")
        os.makedirs(pc, exist_ok=True)
        base_pct = 40 + 55 * k / max(1, len(lista))
        f_b = os.path.join(pc, "brolls.json")
        f_out = os.path.join(pc, f"corte_{ct['n']}.mp4")
        novo = False
        if not os.path.exists(f_b):
            pr.etapa(f"Criando imagens da parte {ct['n']}", base_pct)
            try:
                brolls.planejar(words_v, ct, pc, log)
                novo = True
            except Exception as e:
                log(f"Parte {ct['n']} vai sem B-roll por enquanto ({e}).")
        plano = json.load(open(f_b, encoding="utf-8")) if os.path.exists(f_b) else []
        faltando = (list(range(len(plano))) if novo else
                    [i for i, b in enumerate(plano) if not os.path.exists(os.path.join(pc, b["arquivo"]))])
        if faltando:
            brolls.desenhar(plano, pc, log, so=faltando)
        if not os.path.exists(f_out) or novo or faltando:
            pr.etapa(f"Montando a parte {ct['n']}", base_pct + 25 / max(1, len(lista)))
            compor.montar(base, words_v, trechos, ct, plano, pc, f_out, log)
