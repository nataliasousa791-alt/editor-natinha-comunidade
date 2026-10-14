"""QA automático do MP4: formato (9:16 ou 16:9), duração, áudio, telas pretas, congelamentos, sincronia das legendas
(retranscrição com comparação tolerante), repetição de assets e proporção. Registra o que NÃO é verificável por máquina."""
import difflib, re, subprocess, unicodedata
import numpy as np
from .util import probe, run
from .transcrever import transcrever, limpo

DIM = {"9x16": (1080, 1920), "16x9": (1920, 1080)}


def _n(x):
    return "".join(ch for ch in unicodedata.normalize("NFD", limpo(x)) if unicodedata.category(ch) != "Mn")


def _parecida(a, b):
    a, b = _n(a), _n(b)
    return a == b or (len(a) >= 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.75)


def qa(mp4, plano, job, c, legendas=None, extra=None):
    r = {}
    info = probe(mp4)
    W, H = DIM[plano.get("formato", "9x16")]
    esperado = plano["frames"] / plano["fps"]
    r["formato"] = dict(w=info["w"], h=info["h"], fps=round(info["fps"], 3), audio=info["audio"], dur=round(info["dur"], 3),
                        dur_esperada=round(esperado, 3), sar=info["sar"])
    r["formato_ok"] = (info["w"], info["h"]) == (W, H) and info["audio"] and abs(info["dur"] - esperado) < 0.15 and info["sar"] in ("1:1", "N/A", "")
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", mp4, "-vf", "blackdetect=d=0.25:pix_th=0.06", "-an", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    pretas = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    r["telas_pretas"] = [p for p in pretas if p[0] < esperado - 0.6]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", mp4, "-vf", "scale=96:96,format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    fr = np.frombuffer(p.stdout.read(), np.uint8).reshape(-1, 96, 96).astype(np.int16)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))
    seq, maxseq = 0, 0
    for v in d[:-15]:
        seq = seq + 1 if v < 0.02 else 0; maxseq = max(maxseq, seq)
    r["congelamento_max_quadros"] = int(maxseq)
    legs = legendas if legendas is not None else plano.get("legendas", [])
    if legs:
        wav = job.p("qa16.wav"); run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-ac", "1", "-ar", "16000", wav])
        ouv = transcrever(wav, c["whisper_modelo"], c["idioma"], job.log)
        desv, falt = [], []
        for l in legs:
            ok = False
            for x in l["palavras"][:2]:
                cand = [o for o in ouv if _parecida(o["w"], x["w"]) and abs(o["s"] - x["s"]) < 1.0]
                if cand:
                    desv.append(min(abs(o["s"] - x["s"]) for o in cand)); ok = True; break
            if not ok: falt.append(" ".join(x["w"] for x in l["palavras"]))
        a = np.array(desv) if desv else np.array([9.0])
        r["legendas"] = dict(conferidas=len(desv), total=len(legs), mediana_s=round(float(np.median(a)), 3),
                             p90_s=round(float(np.percentile(a, 90)), 3), nao_localizadas=falt)
    else:
        r["legendas"] = dict(conferidas=0, total=0, mediana_s=0.0, p90_s=0.0, nao_localizadas=[])
    ids = [x["asset"]["id"] for x in plano.get("cenas", []) if x.get("asset")]
    r["assets"] = dict(ids=ids, repetidos=sorted({i for i in ids if ids.count(i) > 1}))
    if extra: r.update(extra)
    leg_ok = not legs or (r["legendas"]["conferidas"] >= 0.8 * len(legs) and r["legendas"]["mediana_s"] <= 0.15)
    r["ok_tecnico"] = bool(r["formato_ok"] and not r["telas_pretas"] and maxseq < 20 and not r["assets"]["repetidos"] and leg_ok
                          and r.get("erro_proporcao_max", 0) < 0.002)
    r["nao_verificado"] = "estética, naturalidade do movimento e pertinência fina das imagens exigem revisão humana"
    return r
