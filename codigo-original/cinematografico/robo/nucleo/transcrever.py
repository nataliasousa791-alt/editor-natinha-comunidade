"""Transcrição com tempo por palavra (cópia adaptada de editor_natinha/nucleo/transcrever.py) + agrupamento em frases."""
import re, wave
import numpy as np


def transcrever(wav16, modelo, idioma, log):
    from faster_whisper import WhisperModel
    log(f"transcrevendo (faster-whisper {modelo}, CPU int8)…")
    m = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=4)
    with wave.open(wav16, "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768.0
    segs, _ = m.transcribe(audio, language=idioma, word_timestamps=True, vad_filter=True,
                           condition_on_previous_text=False, beam_size=5)
    words, last = [], 0.0
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                st = max(round(w.start, 3), last)
                words.append({"w": t, "s": st, "e": max(round(w.end, 3), st + 0.05), "p": round(w.probability, 3)})
                last = st
    return words


def frases(words, max_palavras=26, pausa=0.75):
    """Frases = índices de palavras; quebra em pontuação final, pausa longa ou tamanho."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if re.search(r"[.!?…]$", w["w"]) or len(cur) >= max_palavras or not nxt or nxt["s"] - w["e"] > pausa:
            out.append({"i0": cur[0], "i1": cur[-1], "s": words[cur[0]]["s"], "e": words[cur[-1]]["e"],
                        "texto": " ".join(words[j]["w"] for j in cur), "fim": w["w"][-1] if w["w"][-1] in ".!?…" else ""})
            cur = []
    return out


def limpo(w):
    return re.sub(r"[^\wà-úÀ-Ú%$]", "", w.lower())


def revisar(words, c, log, limiar=0.55):
    """Revisa palavras de BAIXA confiança do whisper com a IA, pelo contexto. Só troca por palavra parecida
    (mesma quantidade de palavras e semelhança de grafia), preservando os tempos. Devolve (words, trocas)."""
    import difflib
    from . import ia
    duv = [i for i, w in enumerate(words) if w.get("p", 1) < limiar and len(limpo(w["w"])) >= 3]
    if not c.get("usar_ia"): return words, []
    for ini in range(0, len(words), 250):                     # varredura do texto corrido (palavras com confiança alta)
        txt = " ".join(f"{w['w']}#{ini + k}" for k, w in enumerate(words[ini:ini + 250]))
        try:
            r, _ = ia.pedir("Você revisa transcrições automáticas de português brasileiro falado. Responda só JSON.",
                            "Texto com o índice de cada palavra após '#'. Liste SÓ palavras que o reconhecimento de voz claramente "
                            "errou (palavra inexistente ou sem sentido no contexto, com som parecido à certa). Não corrija gíria, "
                            f"oralidade nem concordância.\n{txt}\nJSON: {{\"suspeitas\": [<índices>]}}", log, temperatura=0.1)
            duv += [int(i) for i in r.get("suspeitas", []) if str(i).isdigit() and ini <= int(i) < ini + 250]
        except Exception as e:
            log(f"varredura de transcrição indisponível ({e})"); break
    duv = sorted(set(duv))
    if not duv: return words, []
    trocas = []
    for ini in range(0, len(duv), 60):
        lote = duv[ini:ini + 60]
        itens = "\n".join(f"W{i} | ...{' '.join(x['w'] for x in words[max(0, i - 8):i])} [[{words[i]['w']}]] "
                          f"{' '.join(x['w'] for x in words[i + 1:i + 9])}..." for i in lote)
        try:
            r, _ = ia.pedir("Você revisa transcrições em português brasileiro falado. Responda só JSON.",
                            "Cada item tem uma palavra entre [[ ]] que o reconhecimento de voz pode ter errado. Se o contexto mostrar "
                            "claramente a palavra certa (som parecido), corrija; senão repita a original. Preserve gírias e oralidade. "
                            f"Itens:\n{itens}\nJSON: {{\"W<i>\": \"palavra\"}}", log, temperatura=0.1)
        except Exception as e:
            log(f"revisão de transcrição indisponível ({e})"); break
        for k, nova in r.items():
            try: i = int(str(k).upper().lstrip("W"))
            except ValueError: continue
            if i not in lote or not isinstance(nova, str): continue
            velha = words[i]["w"]; pont = velha[len(velha.rstrip(",.?!;:…")):]
            nova = nova.strip().rstrip(",.?!;:…")
            if (not nova or " " in nova or limpo(nova) == limpo(velha)
                    or difflib.SequenceMatcher(None, limpo(nova), limpo(velha)).ratio() < 0.5): continue
            words[i]["w"] = (nova[0].upper() + nova[1:] if velha[:1].isupper() else nova) + pont
            words[i]["revisada"] = velha; trocas.append((velha, words[i]["w"]))
    log(f"revisão: {len(duv)} palavras duvidosas, {len(trocas)} corrigidas {trocas[:12]}")
    return words, trocas
