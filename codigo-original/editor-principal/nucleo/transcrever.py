"""Transcrição com tempo de cada palavra. Padrão: faster-whisper (baixa o modelo na 1ª vez).
Reserva: whisper.cpp (pywhispercpp) com modelo ggml em recursos/modelos."""
import json, os, re
from .util import FFMPEG, RAIZ, run, tmpdir, ler_config


def _audio(video, wav):
    run([FFMPEG, "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])


def _faster(wav, modelo, idioma, log):
    from faster_whisper import WhisperModel
    log(f"Carregando modelo de transcrição '{modelo}' (na 1ª vez ele é baixado)…")
    m = WhisperModel(modelo, device="auto", compute_type="int8")
    import wave
    import numpy as np
    with wave.open(wav, "rb") as wf:   # lê o áudio aqui mesmo (evita incompatibilidade da biblioteca 'av')
        audio = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768.0
    segs, info = m.transcribe(audio, language=idioma, word_timestamps=True, vad_filter=True,
                              condition_on_previous_text=False, beam_size=5)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(w.start, 2), "e": round(w.end, 2)})
        log(f"…transcrito até {s.end:.0f}s")
    return words


def _whispercpp(wav, idioma, log):
    from pywhispercpp.model import Model
    mod = os.path.join(RAIZ, "recursos", "modelos", "ggml-base.bin")
    m = Model(mod, n_threads=os.cpu_count() or 2, print_progress=False, print_realtime=False,
              language=idioma, token_timestamps=True, max_len=1, split_on_word=True)
    words = []
    for s in m.transcribe(wav):
        t = s.text.strip().lstrip("-").strip()
        if t and not t.startswith("["):
            words.append({"w": t, "s": round(s.t0 / 100, 2), "e": round(s.t1 / 100, 2)})
    return words


def transcrever(video, saida_json, log=print):
    c = ler_config()
    wav = os.path.join(tmpdir(), "a.wav")
    _audio(video, wav)
    if c["whisper_motor"] == "whispercpp":
        words = _whispercpp(wav, c["idioma"], log)
    else:
        try:
            words = _faster(wav, c["whisper_modelo"], c["idioma"], log)
        except ImportError:
            log("faster-whisper não instalado; usando whisper.cpp")
            words = _whispercpp(wav, c["idioma"], log)
    # garante ordem e tempos crescentes
    last = 0.0
    for w in words:
        w["s"] = max(w["s"], last)
        w["e"] = max(w["e"], w["s"] + 0.05)
        last = w["s"]
    json.dump(words, open(saida_json, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return words


def frases(words, max_palavras=22):
    """Agrupa palavras em frases numeradas (para mandar à IA)."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if (re.search(r"[.!?…]$", w["w"]) or len(cur) >= max_palavras or not nxt or nxt["s"] - w["e"] > 0.9):
            out.append({"i0": cur[0], "i1": cur[-1], "s": words[cur[0]]["s"], "e": words[cur[-1]]["e"],
                        "texto": " ".join(words[j]["w"] for j in cur)})
            cur = []
    return out
