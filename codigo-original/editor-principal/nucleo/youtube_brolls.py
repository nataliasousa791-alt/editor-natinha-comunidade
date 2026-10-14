"""B-rolls no vídeo do YouTube: vídeos reais do banco (tela cheia) e animações (painel do lado, o rosto continua
aparecendo). A IA escolhe os momentos fora dos cartões, o editor busca/desenha, a IA revisa olhando."""
import json, os
from .transcrever import frases
from .util import ler_config
from . import ia, brolls, videos_reais
from .insercoes import duracao as dur_cartao

PEDIDO = """Este é um trecho de {ini:.0f}s a {fim:.0f}s de um vídeo de YouTube (horizontal). Abaixo, as frases com o tempo
(em segundos, desde o começo do vídeo) de cada palavra. Escolha {n} momentos para B-roll, espalhados pelo trecho todo:
{n_video} com VÍDEO REAL (cena filmada do banco de vídeos, cobre a tela inteira por alguns segundos) e {n_anim} como
ANIMAÇÃO (desenho, aparece num painel ao lado dela) — as animações nas ideias mais abstratas (comparação, número,
metáfora), os vídeos reais nas cenas concretas (pessoas, emoções, lugares, objetos).

Entenda o ARGUMENTO: o B-roll mostra a IDEIA que ela está defendendo naquela frase, de um jeito que quem vê sem som entende.
Exemplos passageiros, piadas e frases de ligação NÃO ganham B-roll.
Todo B-roll tem "titulo": 2 a 4 palavras-chave DITAS por ela naquela frase.

VÍDEO REAL: "video": {{"buscas": [2 ou 3 buscas em inglês, bem visuais e concretas, da mais específica à mais geral]}}
(ex.: "woman praying alone at night", "hands counting money", "church interior candles") e "receita": null.
ANIMAÇÃO: "video": null e "receita" (o desenho, regras abaixo) com "dur" igual ao dur.

REGRA DO VÍDEO REAL: só use vídeo real quando a frase fala de algo LITERAL que dá para filmar (uma pessoa rezando,
chorando, ajoelhada, com medo, abraçando; dinheiro, contas, banco; igreja, vela, Bíblia; multidão, família, celular...).
As buscas descrevem exatamente essa cena, com QUEM e FAZENDO O QUÊ ("woman kneeling praying in church", "man worried
looking at bills"). Proibido nas buscas: palavras abstratas (concept, energy, spiritual, vibration, divine, faith, universe,
light, abstract) e paisagens/céu/natureza/objetos soltos. Ideia abstrata (vibração, merecimento, universo, certeza) = ANIMAÇÃO.
Se não houver momentos literais suficientes, faça MENOS vídeos reais e mais animações (não force).

Regras de tempo:
- cada B-roll dura de 3 a 5s; pelo menos 6s de rosto entre um B-roll e outro;
- NÃO coloque B-roll nestes intervalos (já têm cartão na tela): {ocupados};
- dentro da receita, os tempos "t" são relativos ao início do B-roll.

Responda em JSON:
{{"brolls": [{{"inicio": segundos, "dur": segundos, "frase": "trecho ilustrado", "ideia": "a ideia + como a cena mostra",
  "titulo": "2 a 4 palavras", "video": {{"buscas": ["...", "..."]}} ou null, "receita": {{...}} ou null}}]}}

FALAS:
{falas}"""


def _ocupados(cartoes):
    return [(float(c["tempo"]) - 1.0, float(c["tempo"]) + dur_cartao(c) + 0.8) for c in cartoes or []]


def _falas(words, ini, fim):
    ws = [w for w in words if w["s"] >= ini - 0.05 and w["e"] <= fim + 0.3]
    linhas = []
    for f in frases(ws):
        linhas.append(" ".join(f"{ws[k]['w']}({ws[k]['s']:.1f})" for k in range(f["i0"], f["i1"] + 1)))
    return "\n".join(linhas)


def _validar(lista, dur, ocup, gap=6.0):
    out = []
    for b in sorted(lista, key=lambda x: float(x.get("inicio", 0) or 0)):
        try:
            ini, d = float(b["inicio"]), min(5.0, max(3.0, float(b.get("dur", 4))))
        except Exception:
            continue
        tem_video = isinstance(b.get("video"), dict) and b["video"].get("buscas")
        tem_receita = isinstance(b.get("receita"), dict) and b["receita"].get("objetos")
        if not (tem_video or tem_receita):
            continue
        ini = max(ini, 3.0)
        if ini + d > dur - 1.0:
            continue
        if out and ini < out[-1]["inicio"] + out[-1]["dur"] + gap:
            continue
        if any(ini < o_fim and ini + d > o_ini for o_ini, o_fim in ocup):
            # tenta escorregar para depois do cartão
            fim_c = max(o_fim for o_ini, o_fim in ocup if ini < o_fim and ini + d > o_ini)
            if fim_c - ini > 3 or any(fim_c < f and fim_c + d > i for i, f in ocup):
                continue
            ini = fim_c
            if ini + d > dur - 1.0 or (out and ini < out[-1]["inicio"] + out[-1]["dur"] + gap):
                continue
        b["inicio"], b["dur"] = round(ini, 2), round(d, 2)
        if not tem_video:
            b["video"] = None
        if tem_receita:
            b["receita"]["dur"] = b["dur"]
        else:
            b["receita"] = None
        out.append(b)
    return out


def planejar(words, pasta_b, cartoes, log=print):
    c = ler_config()
    dur = words[-1]["e"] if words else 0
    iv_v = max(10, int(c.get("youtube_video_intervalo", 30)))
    iv_a = max(15, int(c.get("youtube_animacao_intervalo", 60)))
    usa_video = videos_reais.tem_fonte() and c.get("brolls_video", True)
    ocup = _ocupados(cartoes)
    f_ex = os.path.join(os.path.dirname(pasta_b), "youtube_extra.json")
    if os.path.exists(f_ex):                      # prévia do começo e tela final ficam sem B-roll
        ex = json.load(open(f_ex, encoding="utf-8"))
        ocup += [(0.0, float(ex.get("teaser", 0) or 0) + 6.0), (float(ex.get("fim_conteudo", 1e9)) - 4.0, 1e9)]
    janela = 240.0
    partes = max(1, round(dur / janela))
    passo = dur / partes
    todos = []
    for p in range(partes):
        ini, fim = p * passo, (p + 1) * passo
        n_video = round((fim - ini) / iv_v) if usa_video else 0
        n_anim = max(1, round((fim - ini) / iv_a)) if fim - ini > 20 else 0
        n = n_video + n_anim
        if n == 0:
            continue
        ocup_txt = ", ".join(f"{a:.0f}-{b:.0f}s" for a, b in ocup if b > ini and a < fim) or "nenhum"
        pedido = PEDIDO.format(ini=ini, fim=fim, n=n, n_video=n_video, n_anim=n_anim, ocupados=ocup_txt,
                               falas=_falas(words, ini, fim))
        try:
            resp, modelo = ia.pedir(f"youtube_brolls_{p + 1}", brolls.RECEITAS, pedido, temperatura=0.8, log=log, forte=True)
        except Exception as e:
            log(f"(B-rolls do YouTube, parte {p + 1}: a IA não respondeu: {e})")
            continue
        achados = [b for b in resp.get("brolls", []) if ini - 1 <= float(b.get("inicio", -99) or -99) < fim]
        todos += achados
        log(f"YouTube parte {p + 1}/{partes}: IA ({modelo}) sugeriu {len(achados)} B-roll(s)")
    plano = _validar(todos, dur, ocup)
    for k, b in enumerate(plano):
        b["arquivo"] = f"broll_{k + 1}.mp4"
    os.makedirs(pasta_b, exist_ok=True)
    json.dump(plano, open(os.path.join(pasta_b, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"{len(plano)} B-roll(s) planejados para o vídeo do YouTube "
        f"({sum(1 for b in plano if b.get('video'))} com vídeo real)")
    return plano


def desenhar(plano, pasta_b, log, W, H, quais):
    """Vídeos reais em lotes (a IA olha até 8 folhas por vez); o que não tiver vídeo vira desenho; sem receita, sai."""
    com_video = [k for k in quais if plano[k].get("video") and not plano[k].get("so_desenho")]
    feitos = set()
    for i in range(0, len(com_video), 8):
        lote = com_video[i:i + 8]
        try:
            feitos |= videos_reais.processar(plano, lote, pasta_b, log, W, H)
        except Exception as e:
            log(f"(vídeos reais do YouTube não deram: {e})")
    for k in quais:
        b = plano[k]
        if k in feitos:
            b.pop("erro", None)
            continue
        b.pop("fonte", None)
        b.pop("credito", None)
        if not b.get("receita"):
            b["erro"] = "sem vídeo e sem desenho"
            continue
        try:
            from motor import motor
            log(f"Desenhando animação do YouTube {k + 1}: {b.get('ideia', '')}")
            motor.render(json.loads(json.dumps(b["receita"])), os.path.join(pasta_b, b["arquivo"]))
            b.pop("erro", None)
        except Exception as e:
            b["erro"] = str(e)[:300]
            log(f"Animação {k + 1} do YouTube falhou: {e}")


def _salvar(plano, pasta_b):
    json.dump(plano, open(os.path.join(pasta_b, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def preparar(words, pasta, cartoes, log=print, W=1920, H=1080):
    """Devolve a lista de B-rolls prontos para colocar no vídeo do YouTube: [{arquivo, inicio, dur, modo}]."""
    pasta_b = os.path.join(pasta, "youtube_brolls")
    f_b = os.path.join(pasta_b, "brolls.json")
    if ler_config().get("broll_engine_v2", True):
        return _preparar_v2(words, pasta, pasta_b, f_b, cartoes, log, W, H)
    novo = not os.path.exists(f_b)
    plano = planejar(words, pasta_b, cartoes, log) if novo else json.load(open(f_b, encoding="utf-8"))
    quais = (list(range(len(plano))) if novo else
             [k for k, b in enumerate(plano) if not os.path.exists(os.path.join(pasta_b, b["arquivo"]))])
    if quais:
        desenhar(plano, pasta_b, log, W, H, quais)
        _salvar(plano, pasta_b)
    if novo and plano:
        dur = words[-1]["e"] if words else 0
        revisado = []
        prontos = [b for b in plano if os.path.exists(os.path.join(pasta_b, b["arquivo"]))]
        for i in range(0, len(prontos), 10):
            sub = prontos[i:i + 10]
            try:
                revisado += brolls.revisar(words, {"n": f"YouTube-{i // 10 + 1}", "s": 0, "e": dur}, sub, pasta_b, log,
                                           min_video=int(ler_config().get("youtube_nota_video", 4)))
            except Exception as e:
                log(f"(revisão dos B-rolls do YouTube não rodou: {e})")
                revisado += sub
        plano = revisado
        _salvar(plano, pasta_b)
    extras = []
    for b in plano:
        f = os.path.join(pasta_b, b["arquivo"])
        if os.path.exists(f) and not b.get("erro"):
            extras.append({"arquivo": f, "inicio": b["inicio"], "dur": b["dur"],
                           "modo": "tela" if b.get("fonte") in ("pixabay", "pexels") else "painel"})
    return extras


def _preparar_v2(words, pasta, pasta_b, f_b, cartoes, log, W, H):
    """V2: uma decisão editorial por janela; banco só com nota >= 4; sem revisão extra (economiza o Gemini)."""
    from . import brolls_v2
    ocup = []
    f_ex = os.path.join(pasta, "youtube_extra.json")
    if os.path.exists(f_ex):                      # prévia do começo e tela final ficam sem B-roll
        ex = json.load(open(f_ex, encoding="utf-8"))
        ocup = [(0.0, float(ex.get("teaser", 0) or 0) + 6.0), (float(ex.get("fim_conteudo", 1e9)) - 4.0, 1e9)]
    novo = not os.path.exists(f_b)
    plano = (brolls_v2.planejar_youtube(words, pasta_b, cartoes, log, ocup) if novo
             else json.load(open(f_b, encoding="utf-8")))
    quais = (list(range(len(plano))) if novo else
             [k for k, b in enumerate(plano) if not os.path.exists(os.path.join(pasta_b, b["arquivo"]))])
    if quais:
        brolls_v2.desenhar(plano, pasta_b, log, so=quais, W=W, H=H, video_base=os.path.join(pasta, "youtube.mp4"))
    extras = []
    for b in plano:
        f = os.path.join(pasta_b, b["arquivo"])
        if os.path.exists(f) and not b.get("erro"):
            # V2: tudo em tela cheia horizontal (nada de retângulo vertical colado)
            tipo = b.get("visual_final") or "template"
            tipo = "video_real" if tipo == "video_real" else ("foto" if tipo.startswith("foto") else "template")
            extras.append({"arquivo": f, "inicio": b["inicio"], "dur": b["dur"], "modo": "tela", "tipo": tipo})
    # intervenções leves (punch-in / destaque) + preenchimento das lacunas longas, sem chamar a IA
    from .insercoes import duracao as dur_cartao
    f_l = os.path.join(pasta_b, "leves.json")
    leves = json.load(open(f_l, encoding="utf-8")) if os.path.exists(f_l) else []
    ocup = [(x["inicio"] - 0.5, x["inicio"] + x["dur"] + 0.5) for x in extras]
    ocup += [(float(c["tempo"]) - 0.3, float(c["tempo"]) + dur_cartao(c) + 0.3) for c in cartoes or []]
    leves = [l for l in leves if not any(l["inicio"] < b and l["inicio"] + l["dur"] > a for a, b in ocup)]
    # hierarquia: texto na tela não encosta em B-roll nem cartão (1,5 s de folga) e no máximo 1 a cada 30 s
    perto = [(a - 1.0, b + 1.0) for a, b in ocup]
    ult_txt = -1e9
    for l in leves:
        if l["tipo"] == "destaque":
            if any(l["inicio"] < b and l["inicio"] + l["dur"] > a for a, b in perto) or l["inicio"] - ult_txt < 30:
                l["tipo"], l["texto"] = "punch_in", ""
            else:
                ult_txt = l["inicio"]
    fim = float(json.load(open(f_ex, encoding="utf-8")).get("fim_conteudo", 1e9)) if os.path.exists(f_ex) else 1e9
    ini = (float(json.load(open(f_ex, encoding="utf-8")).get("teaser", 0) or 0) + 4.0) if os.path.exists(f_ex) else 4.0
    fim = min(fim, words[-1]["e"] if words else fim) - 2.0
    # o ritmo vem da fala: só entra punch-in automático em trecho MUITO longo sem nenhuma variação
    leves = brolls_v2.preencher_lacunas(leves, ocup, words, ini, fim, lacuna=float(ler_config().get("youtube_lacuna", 18)))
    for l in leves:
        extras.append({"modo": "punch" if l["tipo"] == "punch_in" else "texto", "inicio": l["inicio"], "dur": l["dur"],
                       "texto": l.get("texto", "")})
    n_auto = sum(1 for l in leves if l.get("auto"))
    log(f"YouTube: {len(plano)} momento(s) visual(is), {len(leves)} intervenção(ões) leve(s) ({n_auto} automática(s))")
    return extras
