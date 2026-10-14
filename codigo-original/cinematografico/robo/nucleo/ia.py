"""IA de texto (Gemini, plano gratuito) — cópia enxuta de editor_natinha/nucleo/ia.py.
A chave é LIDA do config do editor antigo em modo somente leitura (ou GEMINI_API_KEY); nunca é copiada nem impressa."""
import json, os, re, time, urllib.request, urllib.error
from .util import cfg


class ErroIA(RuntimeError):
    pass


def _cfg_antigo():
    try:
        return json.load(open(cfg()["config_editor_antigo_somente_leitura"], encoding="utf-8"))
    except Exception:
        return {}


def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


def _json(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    try: return json.loads(txt)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", txt, re.S)
        if m: return json.loads(m.group(1))
        raise ErroIA("IA não devolveu JSON")


def pedir(sistema, usuario, log, temperatura=0.4, rodadas=3, imagens=None):
    """imagens: lista opcional de bytes JPEG enviados junto (V6: avaliacao visual de B-roll)."""
    import base64
    c = _cfg_antigo()
    chave = os.environ.get("GEMINI_API_KEY") or c.get("gemini_chave", "")
    if not chave:
        raise ErroIA("sem chave Gemini")
    modelos = c.get("gemini_modelos") or ["gemini-flash-latest"]
    partes = [{"text": usuario}] + [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode()}} for b in (imagens or [])]
    body = {"systemInstruction": {"parts": [{"text": sistema}]}, "contents": [{"role": "user", "parts": partes}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": temperatura}}
    fora, ultimo = set(), ""
    for r in range(rodadas):
        for m in modelos:
            if m in fora: continue
            st, j = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body, {"x-goog-api-key": chave})
            if st == 200:
                try:
                    return _json("".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])), m
                except Exception as e:
                    ultimo = f"{m}: {e}"; continue
            ultimo = f"{m}: {st}"
            if st not in (429, 500, 502, 503, 504, 0): fora.add(m)
        log(f"IA ocupada ({ultimo}); nova rodada"); time.sleep(6 * (r + 1))
    raise ErroIA("IA indisponível: " + ultimo)
