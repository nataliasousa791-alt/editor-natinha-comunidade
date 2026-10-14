"""Chamada às IAs que escrevem texto/JSON: Gemini (grátis) com novas tentativas e troca de modelo;
opcionalmente qualquer API compatível com OpenAI (DeepSeek, Ollama local, OpenRouter...).
Para testes sem internet: variável IA_RESPOSTAS=pasta com arquivos <tarefa>.json."""
import base64, json, os, re, time, urllib.request, urllib.error
from .util import ler_config


class ErroIA(RuntimeError):
    pass


def _post(url, body, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": {"message": str(e)}}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


def _extrair_json(txt):
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"(\[.*\]|\{.*\})", txt, re.S)
        if m:
            return json.loads(m.group(1))
        raise ErroIA("A IA não devolveu JSON válido")


def gemini(sistema, usuario, temperatura=0.8, log=print, tentativas=3, imagens=None, forte=False):
    c = ler_config()
    chave = c.get("gemini_chave") or os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        raise ErroIA("Falta a chave do Gemini (Configurações).")
    body = {"systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": usuario}] + [
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(im).decode()}} for im in (imagens or [])]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": temperatura}}
    ultimo = ""
    modelos = list(c["gemini_modelos"])
    fortes = [m for m in modelos if "lite" not in m] or modelos
    fora = set()   # modelos que não existem para esta chave
    # tarefas criativas (forte=True): insiste nos modelos bons antes de aceitar os "lite", que pensam pior
    rodadas_fortes = 3 if forte else 0
    for rodada in range(tentativas + rodadas_fortes):
        lista = fortes if rodada < rodadas_fortes else modelos
        for modelo in lista:   # tenta um modelo de cada vez; se estiver lotado, passa para o próximo
            if modelo in fora:
                continue
            st, j = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                          body, {"x-goog-api-key": chave}, timeout=120)
            if st == 200:
                try:
                    txt = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
                    return _extrair_json(txt), modelo
                except Exception as e:
                    ultimo = f"{modelo}: resposta inválida ({e})"
                    continue
            msg = (j.get("error") or {}).get("message", "")
            ultimo = f"{modelo}: {st} {msg[:120]}"
            if st in (429, 500, 502, 503, 504, 0):
                log(f"IA ocupada ({modelo}), tentando outro modelo…")
                continue
            fora.add(modelo)
        espera = (12 if rodada < rodadas_fortes else 5) * (rodada % 3 + 1)
        log(f"Todos os modelos ocupados; nova rodada em {espera}s…")
        time.sleep(espera)
    raise ErroIA("Nenhum modelo Gemini respondeu. Último erro: " + ultimo)


def openai_compat(sistema, usuario, temperatura=0.8):
    c = ler_config()
    url = c["openai_compat_url"].rstrip("/") + "/chat/completions"
    st, j = _post(url, {"model": c["openai_compat_modelo"], "temperature": temperatura,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "system", "content": sistema + "\nResponda em JSON."},
                                     {"role": "user", "content": usuario}]},
                  {"Authorization": "Bearer " + c.get("openai_compat_chave", "")})
    if st != 200:
        raise ErroIA(f"API compatível falhou: {st} {j}")
    return _extrair_json(j["choices"][0]["message"]["content"]), c["openai_compat_modelo"]


def pedir(tarefa, sistema, usuario, temperatura=0.8, log=print, imagens=None, forte=False):
    """Pede um JSON à IA. 'tarefa' só serve para log e para o modo de teste. 'imagens' = lista de PNG (bytes), só Gemini."""
    pasta = os.environ.get("IA_RESPOSTAS")
    if pasta:
        arq = os.path.join(pasta, tarefa + ".json")
        if os.path.exists(arq):
            return json.load(open(arq, encoding="utf-8")), "arquivo"
        open(os.path.join(pasta, tarefa + ".pedido.txt"), "w", encoding="utf-8").write(sistema + "\n\n=====\n\n" + usuario)
        raise ErroIA(f"[teste] falta {arq}")
    c = ler_config()
    erros = []
    if c.get("gemini_chave") or os.environ.get("GEMINI_API_KEY"):
        try:
            return gemini(sistema, usuario, temperatura, log, imagens=imagens, forte=forte)
        except ErroIA as e:
            erros.append(str(e))
    if c.get("openai_compat_url") and not imagens:
        try:
            return openai_compat(sistema, usuario, temperatura)
        except ErroIA as e:
            erros.append(str(e))
    raise ErroIA(" | ".join(erros) or "Nenhuma IA configurada (coloque a chave do Gemini em Configurações).")
