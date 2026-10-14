"""Corte narrativo automático: escolhe o trecho (gancho -> argumento -> fechamento) e gera o MAPA de tempos
bruto -> timeline editada, cortando só em silêncio. Nenhum tempo é escrito à mão."""
import re
from .transcrever import frases, limpo
from . import ia

HESITACAO = {"ahn", "hum", "hã", "éé", "eh", "ã", "hmm", "uhm"}
CONECTIVO = {"e", "mas", "porque", "então", "aí", "que", "né", "tipo", "ou", "pra", "daí"}
GANCHO = {"quando", "você", "vocês", "por", "quem", "sabe", "imagina", "olha", "já", "como", "qual", "o"}


def _idx(v, F, inicio):
    """Aceita 'F7', 7 ou segundos (converte para a frase que contém o tempo)."""
    if v is None: return None
    if isinstance(v, str):
        v = v.strip().upper().lstrip("F")
        try: v = float(v)
        except ValueError: return None
    if float(v).is_integer() and 0 <= int(v) < len(F) and not (isinstance(v, float) and v > len(F)):
        return int(v)
    x = float(v)
    if inicio:
        return min(range(len(F)), key=lambda i: abs(F[i]["s"] - x))
    return min(range(len(F)), key=lambda i: abs(F[i]["e"] - x) if F[i]["s"] <= x + 0.5 else 1e9)


def _gatilhos(c):
    return {g for k in c["conceitos"].values() for g in k["gatilhos"]}


def _dur_comprimida(words, i0, i1, pmax):
    d = 0.0
    for i in range(i0, i1 + 1):
        d += words[i]["e"] - words[i]["s"]
        if i < i1: d += min(pmax, max(0.0, words[i + 1]["s"] - words[i]["e"]))
    return d


def _nota(F, a, b, words, c, dur):
    ini, fim = F[a], F[b]
    p0 = limpo(words[ini["i0"]]["w"])
    n = 0.0
    n += 2 if ini["fim"] == "?" else 0
    n += 1 if p0 in GANCHO else 0
    n -= 2.5 if p0 in CONECTIVO else 0
    w0 = words[ini["i0"]]["w"]
    n -= 3 if w0[:1].islower() else 0                      # whisper põe maiúscula em início de frase
    n -= 3 if a == 0 and words[0]["s"] < 0.4 else 0        # 1ª frase da janela provavelmente começou antes
    n += 2 if fim["fim"] in (".", "!", "?") else -3
    n -= 1.5 if fim["i1"] - fim["i0"] < 3 else 0
    g = _gatilhos(c)
    ws = [limpo(words[i]["w"]) for i in range(ini["i0"], fim["i1"] + 1)]
    n += 6 * sum(1 for w in ws if w in g) / max(1, len(ws))
    n += 2 * sum(words[i].get("p", 0.9) for i in range(ini["i0"], fim["i1"] + 1)) / max(1, len(ws))
    n -= abs(dur - c["duracao_alvo"]) / 12
    return round(n, 3)


def candidatos(words, F, c):
    out = []
    for a in range(len(F)):
        for b in range(a, len(F)):
            d = _dur_comprimida(words, F[a]["i0"], F[b]["i1"], c["pausa_max"])
            if d > c["duracao_max"]: break
            if d >= c["duracao_min"]:
                out.append(dict(a=a, b=b, dur=round(d, 2), nota=_nota(F, a, b, words, c, d)))
    return sorted(out, key=lambda x: -x["nota"])


def escolher(words, c, n_cortes, log):
    F = frases(words)
    cands = candidatos(words, F, c)
    if not cands:
        raise RuntimeError("trecho curto demais para um corte entre "
                           f"{c['duracao_min']} e {c['duracao_max']} s")
    escolhidos, metodo = [], "regras"
    if c.get("usar_ia"):
        try:
            lista = "\n".join(f"F{i} | {f['s']:.1f}-{f['e']:.1f}s | {f['texto']}" for i, f in enumerate(F))
            sis = ("Você é montador de vídeos curtos documentais da criadora brasileira Natinha (crítica social, comportamento). "
                   "Escolha trechos CONTÍNUOS de frases que funcionem sozinhos: gancho forte no início, uma ideia central, "
                   "fechamento conclusivo. Não comece com conectivo solto nem no meio de uma frase. Responda só JSON.")
            usu = (f"Frases (ID | tempo | texto):\n{lista}\n\nEscolha {n_cortes} trecho(s) sem sobreposição, cada um com fala entre "
                   f"{c['duracao_min']} e {c['duracao_max']} segundos (ideal {c['duracao_alvo']}). Use os IDs das frases. JSON: "
                   '{"cortes":[{"inicio":"F<id da frase inicial>","fim":"F<id da frase final>","tema":"<3-6 palavras>","motivo":"<1 frase>"}]}')
            r, modelo = ia.pedir(sis, usu, log)
            for k in r.get("cortes", [])[:n_cortes]:
                a, b = _idx(k.get("inicio"), F, True), _idx(k.get("fim"), F, False)
                if a is None or b is None or b < a: log(f"IA: índices inválidos {k}"); continue
                d = _dur_comprimida(words, F[a]["i0"], F[b]["i1"], c["pausa_max"])
                while d > c["duracao_max"] and b > a:
                    b -= 1; d = _dur_comprimida(words, F[a]["i0"], F[b]["i1"], c["pausa_max"])
                while d < c["duracao_min"] and b + 1 < len(F):
                    b += 1; d = _dur_comprimida(words, F[a]["i0"], F[b]["i1"], c["pausa_max"])
                if c["duracao_min"] * 0.8 <= d <= c["duracao_max"] * 1.1 and all(b < e["a"] or a > e["b"] for e in escolhidos):
                    escolhidos.append(dict(a=a, b=b, dur=round(d, 2), nota=_nota(F, a, b, words, c, d),
                                           tema=k.get("tema", ""), motivo=k.get("motivo", ""), ia_bruto=k))
                else:
                    log(f"IA: trecho F{a}-F{b} com {d:.1f}s fora da faixa")
            if escolhidos: metodo = f"ia:{modelo}"
            else: log("IA devolveu cortes inválidos; usando regras")
        except Exception as e:
            log(f"IA indisponível ({e}); usando regras")
    for k in cands:
        if len(escolhidos) >= n_cortes: break
        if all(k["b"] < e["a"] or k["a"] > e["b"] for e in escolhidos):
            escolhidos.append(dict(k, tema="", motivo="maior nota: gancho/fechamento/conceitos/duração"))
    return F, sorted(escolhidos, key=lambda e: e["a"]), metodo


_ENV = None   # V6: envelope de energia do audio (10 ms) para nunca cortar dentro de palavra


def carregar_audio(wav16):
    """Le o WAV 16 kHz mono do trecho e guarda a energia em dB a cada 10 ms (mesma base de tempo das palavras)."""
    global _ENV
    try:
        import wave, numpy as np
        with wave.open(wav16, "rb") as w:
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        n = len(x) // 160
        db = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-6)
        piso, fala = np.percentile(db, 10), np.percentile(db, 95)
        _ENV = dict(db=db, lim=piso + 0.35 * (fala - piso))
    except Exception:
        _ENV = None


def _silencio(t0, t1, minimo=0.06):
    """Primeiro e ultimo instante de silencio continuo (>= minimo) em [t0, t1]; None se nao houver."""
    if _ENV is None: return None
    db, lim = _ENV["db"], _ENV["lim"]
    a, b = max(0, int(t0 * 100)), min(len(db), int(t1 * 100) + 1)
    q = {i for i in range(a, b) if db[i] < lim}
    runs, ini = [], None
    for i in range(a, b + 1):
        if i < b and i in q:
            ini = i if ini is None else ini
        elif ini is not None:
            if (i - ini) / 100 >= minimo: runs.append((ini / 100, i / 100))
            ini = None
    return (runs[0], runs[-1]) if runs else None


def mapa_palavras(ws, c, fps, quadros_fonte=None):
    """Palavras mantidas -> blocos do bruto (cortes no meio do silêncio) -> timeline nova em quadros inteiros.
    V6: cada corte é conferido na energia do áudio; se a 'pausa' do Whisper não for silêncio real, o corte é desfeito."""
    ws = [w for w in ws if limpo(w["w"]) not in HESITACAO]
    folga, pmax = c["folga_palavra"], c["pausa_max"]
    s0 = _silencio(ws[0]["s"] - 0.4, ws[0]["s"] + 0.05)
    blocos, a = [], (s0[1][1] - 0.05 if s0 else ws[0]["s"] - folga)
    for k in range(len(ws) - 1):
        gap = ws[k + 1]["s"] - ws[k]["e"]
        if gap > pmax:
            cauda = min(0.18 if re.search(r"[.!?…]$", ws[k]["w"]) else 0.11, gap / 2)
            fim_a, ini_b = ws[k]["e"] + cauda, ws[k + 1]["s"] - min(0.10, gap / 2)
            if _ENV is not None:
                sil = _silencio(ws[k]["e"] - 0.08, ws[k + 1]["s"] + 0.08)
                if not sil: continue                                # sem silêncio real: não corta aqui
                (p0, p1), (u0, u1) = sil
                fim_a, ini_b = p0 + min(0.10, (p1 - p0) / 2), u1 - min(0.08, (u1 - u0) / 2)
                if ini_b - fim_a < 0.12: continue                   # pausa curta demais para valer um corte
            blocos.append((a, fim_a)); a = ini_b
    sf = _silencio(ws[-1]["e"] - 0.08, ws[-1]["e"] + 0.6)
    blocos.append((a, (sf[0][0] + 0.15) if sf else ws[-1]["e"] + 0.22))
    m, t = [], 0
    for i, (x, y) in enumerate(blocos):
        src = round(max(0.0, x), 3)
        n = max(1, round((y - x) * fps))
        if quadros_fonte is not None:
            # Reserva um quadro para compensar a busca -ss/rounding do FFmpeg.
            disponiveis = int(quadros_fonte) - round(src * fps) - 1
            if disponiveis < 1:
                raise RuntimeError(f"Corte inicia fora da fonte: bloco {i}, src={src}s")
            if n > disponiveis:
                if i == len(blocos) - 1 and ws[-1]["e"] > src + disponiveis / fps + 0.5:
                    raise RuntimeError("Fim da fonte atinge a ultima palavra; revisar limite sem cortar a fala")
                n = disponiveis
        m.append(dict(src=src, n=n, out=round(t / fps, 4)))
        t += n
    return m, t, ws


def mapa(words, F, esc, c, fps, quadros_fonte=None):
    return mapa_palavras(words[F[esc["a"]]["i0"]:F[esc["b"]]["i1"] + 1], c, fps, quadros_fonte=quadros_fonte)


def tomadas_descartadas(words, F, c, log):
    """Versão YouTube: frases que são tomadas erradas (começo falso, frase repetida — fica a ÚLTIMA versão —,
    'corta', 'pera', conversa fora do conteúdo). IA propõe, regras limitam (máx. 25% das frases)."""
    fora = set()
    for i in range(len(F) - 1):                        # regra: frase quase igual à seguinte = tomada repetida
        a = [limpo(x) for x in F[i]["texto"].split()]; b = [limpo(x) for x in F[i + 1]["texto"].split()]
        if len(a) >= 3 and a[:3] == b[:3] and len(a) <= len(b) + 2:
            fora.add(i)
    for i, f in enumerate(F):
        if re.search(r"\b(corta|cortar isso|vou repetir|deixa eu começar de novo|pera aí|peraí)\b", f["texto"].lower()) and len(f["texto"].split()) <= 8:
            fora.add(i)
    if c.get("usar_ia") and len(F) > 3:
        try:
            for ini in range(0, len(F), 120):                 # lotes para vídeos longos
                lote = F[ini:ini + 120]
                lista = "\n".join(f"F{ini + k} | {f['texto']}" for k, f in enumerate(lote))
                r, _ = ia.pedir("Você é editor de YouTube. Responda só JSON.",
                                f"Transcrição em frases:\n{lista}\n\nMarque SÓ as frases que são tomadas descartáveis: começo falso, "
                                "frase repetida porque a pessoa errou (mantenha a ÚLTIMA versão), pedidos de corte, conversa com alguém fora "
                                "do conteúdo. Não marque frases de conteúdo, mesmo informais. JSON: {\"descartar\":[\"F12\",...]}", log, temperatura=0.1)
                for x in r.get("descartar", []):
                    k = _idx(x, F, True)
                    if k is not None and ini <= k < ini + len(lote): fora.add(k)
        except Exception as e:
            log(f"IA de tomadas indisponível ({e}); só regras")
    if len(fora) > 0.25 * len(F):
        log(f"descartes demais ({len(fora)}); mantendo só os 25% mais curtos")
        fora = set(sorted(fora, key=lambda k: len(F[k]["texto"]))[:int(0.25 * len(F))])
    return sorted(fora)


def T(m, s, fps):
    for b in m:
        if s < b["src"]: return b["out"]
        if s <= b["src"] + b["n"] / fps: return b["out"] + s - b["src"]
    return m[-1]["out"] + m[-1]["n"] / fps
