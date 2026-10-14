"""B-rolls ilustrativos: a IA escolhe os momentos e escreve a receita; o motor desenha."""
import json, os, re
from .transcrever import frases
from .util import RAIZ, ler_config
from . import ia, videos_reais
from motor import motor

RECEITAS = open(os.path.join(RAIZ, "motor", "prompt_receitas.md"), encoding="utf-8").read()

PEDIDO = """Este é um corte vertical de {dur:.1f}s. Abaixo, as frases com o tempo (em segundos, relativo ao início do corte)
de cada palavra. Escolha {n} momentos para B-roll (mais ou menos 1 a cada {intervalo} s, espalhados pelo corte todo):
{n_video} deles com VÍDEO REAL (com "video") e {n_anim} como ANIMAÇÃO (desenho, "video": null) — as animações nas
ideias mais abstratas (comparação, número, metáfora), os vídeos reais nas cenas concretas.

ANTES de escolher, entenda o ARGUMENTO do corte: qual é a tese e quais frases são os passos dele.
Um B-roll bom mostra a IDEIA que ela está defendendo naquela frase (a comparação, a crítica, a virada), de um jeito que
quem vê SEM som entende. Exemplos passageiros, piadas e frases de ligação NÃO ganham B-roll.
Estruturas que funcionam: CONTRASTE (o jeito errado à esquerda riscado × o certo à direita brilhando), TRANSFORMAÇÃO
(A some e vira B), CAUSA→EFEITO (sombra/fios de A dominando B), NÚMERO (contador/rótulos), PESO/LIBERTAÇÃO (cair/voar).
Todo B-roll tem 1 título no topo com 2 a 4 palavras-chave DITAS por ela naquela frase (ex.: "DEUS NÃO É BANCO"),
para amarrar a imagem à fala.

VÍDEO REAL: uma CENA REAL filmada que mostra a ideia (pessoas, emoções, lugares, objetos: "woman praying alone at night",
"anxious man looking at phone", "bank building facade", "crowd walking city", "hands counting money", "church interior
candles", "person writing gratitude journal"). Escreva "video": {{"buscas": [2 ou 3 buscas em inglês, bem visuais e
concretas, da mais específica à mais geral]}} e "titulo": as 2 a 4 palavras dela. SEMPRE escreva a "receita" (desenho)
também: ela é o plano B se nenhum vídeo servir.

REGRA DO VÍDEO REAL: só use vídeo real quando a frase fala de algo LITERAL que dá para filmar (uma pessoa rezando,
chorando, ajoelhada, com medo, abraçando; dinheiro, contas, banco; igreja, vela, Bíblia; multidão, família, celular...).
As buscas descrevem exatamente essa cena, com QUEM e FAZENDO O QUÊ ("woman kneeling praying in church", "man worried
looking at bills"). Proibido nas buscas: palavras abstratas (concept, energy, spiritual, vibration, divine, faith, universe,
light, abstract) e paisagens/céu/natureza/objetos soltos. Ideia abstrata (vibração, merecimento, universo, certeza) = ANIMAÇÃO.
Se não houver momentos literais suficientes, faça MENOS vídeos reais e mais animações (não force).

Regras de tempo:
- nenhum B-roll antes de 3.5s (o gancho mostra o rosto e a frase na tela) nem depois de {fim:.1f}s (a frase final
  de impacto é com o rosto);
- cada B-roll dura de 3 a 5s; pelo menos 2.5s de rosto entre um B-roll e outro;
- escolha frases com IDEIA visual forte (comparação, número, metáfora, objeto, lugar, emoção);
- dentro da receita, os tempos "t" são relativos ao início do B-roll: se uma palavra-chave é dita
  em 14.2s e o B-roll começa em 13.0s, a ação ligada a ela vai em t=1.2.

Responda em JSON:
{{"tese": "a tese do corte", "brolls": [{{"inicio": segundos, "dur": segundos, "frase": "trecho ilustrado",
  "ideia": "a ideia da fala + como a cena mostra, em 1 frase", "titulo": "2 a 4 palavras",
  "video": {{"buscas": ["...", "..."]}} ou null,
  "receita": {{"dur": igual ao dur, "fundo": ..., "objetos": [...], "acoes": [...]}}}}]}}

FALAS:
{falas}"""

PROMPT_REVISAO = """

REVISÃO: você agora é uma editora MUITO exigente. Cada imagem mostra 2 quadros de um B-roll (desenho animado ou vídeo real)
que aparece no corte enquanto ela fala a frase indicada. VÍDEO REAL DE BANCO É DESEJADO e convive com os desenhos: NUNCA tire
nota de um vídeo real por não ser desenho/silhueta/flat; julgue o vídeo só pela ligação da cena com a fala: se é cena
genérica/aleatória (paisagem, flor, ponte, objeto qualquer) que não mostra o que ela diz, nota 1 ou 2 e escreva a nova_receita. Dê nota de 1 a 5: "quem vê a cena enquanto ouve a frase entende
na hora a ligação com a IDEIA dita?" (5 = reforça a ideia com clareza; 3 = genérico/vago; 1 = sem relação, confuso,
objetos sem sentido ou texto cortado). Para nota menor que 4, escreva uma NOVA receita melhor (mesma dur), com uma
metáfora mais direta e um título com as palavras-chave dela. Para nota 4 ou 5, "nova_receita" = null.
Responda em JSON: {"notas": [{"broll": 1, "nota": 4, "motivo": "...", "ideia": "...", "nova_receita": null}]}"""

REFAZER = """Refaça a receita deste B-roll com uma metáfora visual DIFERENTE da anterior.
Mostre a IDEIA da frase de forma que quem vê sem som entenda; use 1 título com 2 a 4 palavras-chave ditas por ela.
Frase: "{frase}" (palavras com tempo relativo ao início do B-roll: {palavras})
Duração: {dur:.1f}s
Ideia anterior (não repita): {ideia}
{pedido_extra}
Responda em JSON: {{"ideia": "...", "receita": {{"dur": {dur:.1f}, "fundo": ..., "objetos": [...], "acoes": [...]}}}}"""


def _falas(words, s, e):
    ws = [w for w in words if w["s"] >= s - 0.05 and w["e"] <= e + 0.3]
    rel = [{"w": w["w"], "s": round(w["s"] - s, 2), "e": round(w["e"] - s, 2)} for w in ws]
    linhas = []
    for f in frases(rel):
        linhas.append(" ".join(f"{rel[k]['w']}({rel[k]['s']:.1f})" for k in range(f["i0"], f["i1"] + 1)))
    return "\n".join(linhas), rel


def _validar(lista, dur):
    out, fim_ant = [], 2.5 - 2.5
    for b in sorted(lista, key=lambda x: float(x.get("inicio", 0))):
        try:
            ini, d = float(b["inicio"]), float(b.get("dur", 4))
        except Exception:
            continue
        d = min(5.0, max(3.0, d))
        ini = max(ini, 3.5, fim_ant + 2.5 if out else 3.5)
        if ini + d > dur - 3.0:
            d = dur - 3.0 - ini
        if d < 2.5 or not isinstance(b.get("receita"), dict):
            continue
        b["inicio"], b["dur"] = round(ini, 2), round(d, 2)
        b["receita"]["dur"] = b["dur"]
        out.append(b)
        fim_ant = ini + d
    return out


def _v2():
    return bool(ler_config().get("broll_engine_v2", True))


def planejar(words, corte, pasta, log=print):
    if _v2():                                       # B-roll Engine V2 (decisão editorial; rosto é válido)
        from . import brolls_v2
        return brolls_v2.planejar_corte(words, corte, pasta, log)
    c = ler_config()
    dur = corte["e"] - corte["s"]
    falas, _ = _falas(words, corte["s"], corte["e"])
    intervalo = max(6, int(c.get("brolls_intervalo_corte", 10)))
    n = max(1, round((dur - 3) / intervalo))
    n_anim = min(n, int(c.get("animacoes_por_corte", 2)))
    n_video = n - n_anim if videos_reais.tem_fonte() and c.get("brolls_video", True) else 0
    n_anim = n - n_video
    pedido = PEDIDO.format(dur=dur, n=n, intervalo=intervalo, n_video=n_video, n_anim=n_anim, fim=dur - 3.0, falas=falas)
    resp, modelo = ia.pedir(f"brolls_{corte['n']}", RECEITAS, pedido, temperatura=0.8, log=log, forte=True)
    plano = _validar(resp.get("brolls", []), dur)
    log(f"Corte {corte['n']}: IA ({modelo}) planejou {len(plano)} B-roll(s)")
    for k, b in enumerate(plano):
        b["arquivo"] = f"broll_{k + 1}.mp4"
    json.dump(plano, open(os.path.join(pasta, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return plano


def _nome_versao(b, k):
    """broll_3.mp4 -> broll_3_v2.mp4 (usa o nome atual, para não colidir com outro B-roll)."""
    base = re.sub(r"(_v\d+)?\.mp4$", "", b.get("arquivo") or f"broll_{k + 1}.mp4")
    return f"{base}_v{b['versao']}.mp4"


def desenhar(plano, pasta, log=print, so=None, W=1080, H=1920):
    """so = None (todos), um índice ou uma lista de índices."""
    if any(b.get("v2") for b in plano):
        from . import brolls_v2
        return brolls_v2.desenhar(plano, pasta, log, so=so, W=W, H=H)
    alvo = [k for k in range(len(plano)) if so is None or k == so or (isinstance(so, (list, set, tuple)) and k in so)]
    feitos = set()
    com_video = [k for k in alvo if plano[k].get("video") and not plano[k].get("so_desenho")]
    if com_video and ler_config().get("brolls_video", True):
        log(f"Procurando vídeos reais para {len(com_video)} B-roll(s)")
        try:
            feitos = videos_reais.processar(plano, com_video, pasta, log, W, H)
        except Exception as e:
            log(f"(vídeos reais não deram: {e}; vão animações)")
    for k in alvo:
        b = plano[k]
        if k in feitos:
            b.pop("erro", None)
            continue
        try:
            b.pop("fonte", None)
            b.pop("credito", None)
            log(f"Desenhando B-roll {k + 1}: {b.get('ideia', '')}")
            motor.render(json.loads(json.dumps(b["receita"])), os.path.join(pasta, b["arquivo"]))
            b.pop("erro", None)
        except Exception as e:
            b["erro"] = str(e)[:300]
            log(f"B-roll {k + 1} falhou: {e}")
    json.dump(plano, open(os.path.join(pasta, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def refazer(words, corte, pasta, k, pedido_extra="", log=print):
    plano = json.load(open(os.path.join(pasta, "brolls.json"), encoding="utf-8"))
    if plano[k].get("v2"):
        from . import brolls_v2
        return brolls_v2.refazer(words, corte, pasta, k, pedido_extra, log)
    b = plano[k]
    s = corte["s"] + b["inicio"]
    _, rel = _falas(words, s, s + b["dur"])
    palavras = " ".join(f"{w['w']}({w['s']:.1f})" for w in rel)
    extra = f"Pedido da Natinha: {pedido_extra}" if pedido_extra else ""
    resp, modelo = ia.pedir(f"refazer_{corte['n']}_{k}", RECEITAS,
                            REFAZER.format(frase=b.get("frase", ""), palavras=palavras, dur=b["dur"],
                                           ideia=b.get("ideia", ""), pedido_extra=extra),
                            temperatura=1.0, log=log, forte=True)
    b["ideia"], b["receita"] = resp.get("ideia", ""), resp["receita"]
    b["so_desenho"] = True
    b["receita"]["dur"] = b["dur"]
    b["versao"] = b.get("versao", 1) + 1
    b["arquivo"] = _nome_versao(b, k)
    desenhar(plano, pasta, log, so=k)
    return plano


def _quadros_png(mp4, dur):
    """2 quadros do B-roll (meio e fim), lado a lado, para a IA olhar."""
    import io, subprocess
    from PIL import Image
    from .util import FFMPEG
    ims = []
    for t in (dur * 0.45, max(0.1, dur - 0.5)):
        r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=270:-2",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True,
                           **({"creationflags": 0x08000000} if os.name == "nt" else {}))
        if r.stdout:
            ims.append(Image.open(io.BytesIO(r.stdout)).convert("RGB"))
    if not ims:
        return None
    w = sum(i.width for i in ims) + 10 * (len(ims) - 1)
    folha = Image.new("RGB", (w, max(i.height for i in ims)), "white")
    x = 0
    for i in ims:
        folha.paste(i, (x, 0))
        x += i.width + 10
    b = io.BytesIO()
    folha.save(b, "PNG")
    return b.getvalue()


def revisar(words, corte, plano, pasta, log=print, min_video=4):
    """A IA OLHA cada B-roll pronto junto com a frase. Nota < 4: troca pela receita nova que ela escreveu e redesenha.
    Nota < 3 sem receita nova: o B-roll sai. (Na V2 não roda: o banco já foi avaliado com nota na escolha.)"""
    if any(b.get("v2") for b in plano):
        return plano
    imagens, idx = [], []
    for k, b in enumerate(plano):
        f = os.path.join(pasta, b.get("arquivo", ""))
        if os.path.exists(f):
            png = _quadros_png(f, float(b.get("dur", 4)))
            if png:
                imagens.append(png)
                idx.append(k)
    if not imagens:
        return plano
    linhas = []
    for j, k in enumerate(idx):
        b = plano[k]
        s = corte["s"] + b["inicio"]
        _, rel = _falas(words, s, s + b["dur"])
        palavras = " ".join(f"{w['w']}({w['s']:.1f})" for w in rel)
        linhas.append(f"B-roll {j + 1} (imagem {j + 1}), dur {b['dur']:.1f}s — ela diz: {palavras} — ideia: {b.get('ideia', '')}")
    try:
        resp, modelo = ia.pedir(f"brolls_revisao_{corte['n']}", RECEITAS + PROMPT_REVISAO, "\n".join(linhas),
                                temperatura=0.5, log=log, imagens=imagens, forte=True)
    except Exception as e:
        log(f"(revisão dos B-rolls do corte {corte['n']} não rodou: {e})")
        return plano
    tirar = []
    for r in resp.get("notas", []):
        try:
            j = int(r.get("broll")) - 1
            k = idx[j]
        except Exception:
            continue
        nota = float(r.get("nota", 4) or 4)
        plano[k]["nota"] = nota
        nova = r.get("nova_receita")
        # vídeo real é ilustração de clima/cena: só sai se não tiver NADA a ver (nota 1); animação precisa de 4
        if nota >= 4 or (plano[k].get("fonte") in ("pixabay", "pexels") and nota >= min_video):
            continue
        if isinstance(nova, dict) and nova.get("objetos"):
            nova["dur"] = plano[k]["dur"]
            plano[k]["receita"] = nova
            plano[k]["so_desenho"] = True
            plano[k]["ideia"] = r.get("ideia") or plano[k].get("ideia", "")
            plano[k]["versao"] = plano[k].get("versao", 1) + 1
            plano[k]["arquivo"] = _nome_versao(plano[k], k)
            log(f"B-roll {k + 1} do corte {corte['n']} refeito (nota {nota:g}: {r.get('motivo', '')})")
            desenhar(plano, pasta, log, so=k)
        elif nota < 3:
            tirar.append(k)
            log(f"B-roll {k + 1} do corte {corte['n']} saiu (nota {nota:g}: {r.get('motivo', '')})")
    if tirar:
        plano = [b for k, b in enumerate(plano) if k not in tirar]
        json.dump(plano, open(os.path.join(pasta, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"Corte {corte['n']}: IA ({modelo}) revisou os B-rolls olhando")
    return plano
