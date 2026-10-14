"""Imagens no vídeo do YouTube: cartões animados (1 ícone, ou 2 ícones com ≠ → +) que mostram a IDEIA da fala."""
import json, math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .util import FFMPEG, FONTES, run, probe, tmpdir, ler_config, opcao_filtro_arquivo
from .transcrever import frases
from . import ia
from motor import icones

PROMPT = """Você é diretora de arte do canal de YouTube da Natinha (análise comportamental, crítica social, espiritualidade).
Você recebe a fala do vídeo em frases, com o tempo de cada palavra (segundos). Vai escolher momentos para mostrar um CARTÃO
animado com ícone(s) e uma frase curta, do lado da tela.

O QUE FAZ UM BOM CARTÃO (o mais importante):
- ilustra a IDEIA que ela está defendendo naquela frase — o argumento, a tese, a virada — e NÃO uma palavra solta.
  Ruim: ela diz "quando você fala pra sua mãe que vai viajar" → ícone de mãe. Isso é só um exemplo passageiro.
  Bom: ela diz "como se Deus fosse um gerente perverso de banco" → cartão CONTRASTE: [mãos rezando] ≠ [banco], texto "DEUS NÃO É BANCO".
- quem vê o cartão SEM som precisa entender a ideia. Por isso o texto resume a ideia em 2 a 4 palavras
  (ex.: "REZAR COM MEDO", "CULPA O DIA TODO", "AGRADEÇA ANTES", "4 MIL ANOS"), nunca uma palavra genérica como "SISTEMA" ou "CERTEZA".
- tipos de cartão:
  "um": um único ícone concreto que mostra a ideia (ex.: corrente quebrada = libertação; balança = julgamento);
  "contraste": A ≠ B (ela compara ou nega: "não é X, é Y", "X não é Y");
  "causa": A → B (uma coisa leva à outra: "medo vira doença", "pedido vira agradecimento");
  "soma": A + B (duas coisas juntas formam a ideia).
  Prefira contraste/causa quando a frase tiver essa estrutura: são os cartões que mais explicam.
- cada ícone tem que ser um OBJETO ou FIGURA fácil de desenhar (pessoa, mãos rezando, igreja, banco, dinheiro, corrente,
  cadeado, chave, coração, cérebro, balança, relógio, coroa, olho, máscara, fogo, sol, livro, celular, casa, mundo...).
  Nada de carinha triste para emoções: mostre a emoção por um objeto/cena (culpa = peso/mochila pesada, medo = corrente, etc.).
- não force: se o trecho não tem ideia visual boa, pule. Exemplos banais e piadas não merecem cartão.

REGRAS DE TEMPO E QUANTIDADE:
- de {qtd} a {qtd_max} cartões, ESPALHADOS pelo vídeo inteiro (o vídeo tem {dur} s; mais ou menos 1 a cada {passo} s);
- nada antes de 4 s; dois cartões nunca a menos de {gap} s um do outro;
- "tempo" = o segundo exato em que a palavra-chave da ideia é dita (copie do tempo da palavra).

PARA CADA CARTÃO:
- "frase": o trecho exato da fala (até 20 palavras);
- "ideia": a ideia em 1 frase curta;
- "tipo": "um" | "contraste" | "causa" | "soma";
- "a": {{"conceito": o que o 1º ícone mostra, em português, bem concreto (ex.: "mãos juntas rezando"),
        "busca": 5 ou 6 palavras simples em inglês para achar o desenho, da mais exata à mais genérica
                 (ex.: ["pray","hands","prayer","praying","faith"])}};
- "b": igual ao "a", para o 2º ícone (só quando o tipo não for "um");
- "texto": 2 a 4 palavras em CAIXA ALTA, sem símbolos (sem ≠ → +), no máximo 18 letras.

Responda em JSON: {{"tese": "a tese do vídeo em 1 frase", "insercoes": [{{"tempo": s, "frase": "...", "ideia": "...", "tipo": "...",
"a": {{"conceito": "...", "busca": ["..."]}}, "b": {{"conceito": "...", "busca": ["..."]}}, "texto": "..."}}]}}"""

PROMPT_ESCOLHA = """Você é diretora de arte. Para cada ícone a escolher há UMA imagem com ícones numerados (em preto).
Escolha o número do ícone que mostra o CONCEITO de forma mais fiel e fácil de reconhecer na hora, para qualquer pessoa.
Seja exigente: um livro qualquer NÃO é uma Bíblia (a Bíblia precisa de cruz); um cadeado não é uma chave; um gráfico de
pizza não é dinheiro. Se nenhum ícone mostrar bem o conceito, responda 0.
Responda em JSON: {"escolhas": [{"icone": 1, "numero": 3}]}"""

PROMPT_REVISAO = """Você é uma editora de vídeo MUITO exigente revisando os cartões que vão aparecer no vídeo do YouTube da Natinha.
Cada imagem é um cartão (ícones dourados + frase curta). Para cada um você recebe a frase que ela está falando naquele momento.
Dê uma nota de 1 a 5: "uma pessoa que vê o cartão enquanto ouve a frase entende na hora a ideia e acha que a imagem
combina com o que está sendo dito?" (5 = reforça a ideia com clareza; 3 = genérico, só repete uma palavra; 1 = sem relação
ou confuso). Se o texto do cartão puder ficar mais claro, sugira "texto" melhor (2 a 4 palavras, caixa alta, sem símbolos).
Responda em JSON: {"notas": [{"cartao": 1, "nota": 4, "motivo": "...", "texto": "opcional"}]}"""

ROXO_ESC = (34, 18, 60)
ROXO = (58, 32, 104)
ROXO_CLARO = (118, 70, 186)
OURO = (242, 193, 78)
OURO_CLARO = (255, 232, 160)
OURO_ESC = (196, 132, 34)
CREME = (246, 238, 227)
DUR = 3.4          # segundos na tela
FPS = 30


_TIPOS = {"um", "contraste", "causa", "soma"}


def _limpa_texto(t):
    import re
    t = re.sub(r"[^0-9A-Za-zÀ-ÿ%!? ]+", " ", str(t or "")).upper()
    pal, out = re.sub(r"\s+", " ", t).strip().split(" "), ""
    for p in pal:                                   # corta em palavra inteira, nunca no meio ("VS ER")
        if len((out + " " + p).strip()) > 22:
            break
        out = (out + " " + p).strip()
    while out.split(" ")[-1] in ("VS", "E", "O", "A", "DE", "DO", "DA", "QUE", "É", "NO", "NA", "OU") and " " in out:
        out = out.rsplit(" ", 1)[0]
    return out or (pal[0][:22] if pal else "")


def _filtrar(resp, dur, gap):
    lista, ultimo = [], -999.0
    for r in sorted(resp, key=lambda x: float(x.get("tempo", 0) or 0)):
        try:
            t = float(r["tempo"])
        except Exception:
            continue
        if t < 4 or t - ultimo < gap or t > dur - 2:
            continue
        a = r.get("a") if isinstance(r.get("a"), dict) else {"conceito": r.get("conceito", r.get("palavra", "")),
                                                               "busca": r.get("busca") or r.get("icone") or [r.get("palavra", "")]}
        b = r.get("b") if isinstance(r.get("b"), dict) and r.get("b", {}).get("busca") else None
        tipo = r.get("tipo") if r.get("tipo") in _TIPOS else "um"
        if tipo != "um" and not b:
            tipo = "um"
        texto = _limpa_texto(r.get("texto") or r.get("palavra"))
        item = {"tempo": round(t, 2), "frase": r.get("frase", r.get("palavra", "")), "ideia": r.get("ideia", ""),
                "tipo": tipo, "a": a, "texto": texto}
        if tipo != "um":
            item["b"] = b
        lista.append(item)
        ultimo = t
    return lista


def _folha(cands, tam=110):
    """Imagem com os ícones candidatos numerados (para a IA olhar e escolher)."""
    col = 6
    lin = (len(cands) + col - 1) // col
    cw, ch = tam + 40, tam + 52
    im = Image.new("RGB", (col * cw, lin * ch), "white")
    dr = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), 24)
    for i, (conj, nome) in enumerate(cands):
        x, y = (i % col) * cw, (i // col) * ch
        try:
            m = icones.mascara(conj, nome, tam)
            if m.width > tam:
                m = m.resize((tam, max(1, int(m.height * tam / m.width))))
            im.paste((0, 0, 0), (x + (cw - m.width) // 2, y + 8 + (tam - m.height) // 2), m)
        except Exception:
            pass
        dr.text((x + cw / 2, y + tam + 26), str(i + 1), font=fnt, fill=(200, 0, 60), anchor="mm")
        dr.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(220, 220, 220))
    import io
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def escolher_icones(lista, log=print):
    """Para cada ícone de cada cartão: junta candidatos e pede para a IA OLHAR e escolher o certo.
    Cartão sem ícone bom é tirado; cartão duplo que perdeu um ícone vira cartão simples."""
    if not lista:
        return lista
    slots = []                                    # (índice do cartão, "a"|"b", candidatos)
    for k, ins in enumerate(lista):
        for lado in ("a", "b"):
            if lado in ins and isinstance(ins[lado], dict):
                cands = icones.candidatos(ins[lado].get("busca") or [ins[lado].get("conceito", "")], limite=24)
                slots.append((k, lado, cands))
    texto, imagens = [], []
    for j, (k, lado, cands) in enumerate(slots):
        if not cands:
            continue
        imagens.append(_folha(cands))
        ins = lista[k]
        texto.append(f"Ícone {j + 1} → imagem {len(imagens)}: conceito = {ins[lado].get('conceito', '')} "
                     f"(cartão \"{ins['texto']}\", ideia: {ins.get('ideia', '')})")
    escolhas = {}
    try:
        resp, modelo = ia.pedir("insercoes_icones", PROMPT_ESCOLHA, "\n".join(texto), temperatura=0.2, log=log,
                                imagens=imagens, forte=True)
        for e in resp.get("escolhas", []):
            escolhas[int(e.get("icone", e.get("momento", 0)))] = int(e.get("numero", 0) or 0)
        log(f"IA ({modelo}) conferiu os ícones olhando")
    except Exception as e:
        log(f"(não deu para conferir os ícones olhando: {e}; usando o mais provável)")
        escolhas = {j + 1: 1 for j in range(len(slots))}
    for j, (k, lado, cands) in enumerate(slots):
        n = escolhas.get(j + 1, 1)
        if cands and 1 <= n <= len(cands):
            lista[k][lado]["icone_id"] = f"{cands[n - 1][0]}:{cands[n - 1][1]}"
    final = []
    for ins in lista:
        tem_a = bool(ins.get("a", {}).get("icone_id"))
        tem_b = bool(ins.get("b", {}).get("icone_id")) if ins.get("b") else False
        if ins["tipo"] != "um" and not (tem_a and tem_b):
            if tem_a or tem_b:
                if not tem_a:
                    ins["a"] = ins["b"]
                ins["tipo"] = "um"
                ins.pop("b", None)
            else:
                tem_a = False
        if not tem_a and ins["tipo"] == "um" and not ins.get("a", {}).get("icone_id"):
            log(f"Sem ícone bom para \"{ins.get('texto')}\" — pulando")
            continue
        final.append(ins)
    return final


def revisar(lista, H, log=print):
    """A IA OLHA cada cartão pronto junto com a frase dita e dá nota; os fracos (nota < 4) saem."""
    if not lista:
        return lista
    import io
    imagens, ok = [], []
    for ins in lista:
        try:
            q = previa(ins, H)
        except Exception as e:                  # ex.: sem ícone adequado → o cartão sai
            log(f"(cartão \"{ins.get('texto')}\" saiu: {e})")
            continue
        ok.append(ins)
        fundo = Image.new("RGBA", q.size, (70, 60, 75, 255))
        fundo.alpha_composite(q)
        b = io.BytesIO()
        fundo.convert("RGB").save(b, "PNG")
        imagens.append(b.getvalue())
    lista = ok
    if not lista:
        return lista
    texto = "\n".join(f"Cartão {k + 1} (imagem {k + 1}): ela diz \"{ins.get('frase', '')}\" — ideia: {ins.get('ideia', '')}"
                      for k, ins in enumerate(lista))
    try:
        resp, modelo = ia.pedir("insercoes_revisao", PROMPT_REVISAO, texto, temperatura=0.2, log=log, imagens=imagens, forte=True)
    except Exception as e:
        log(f"(revisão dos cartões não rodou: {e}; ficam todos)")
        return lista
    notas = {}
    for r in resp.get("notas", []):
        try:
            notas[int(r.get("cartao"))] = r
        except Exception:
            pass
    final = []
    for k, ins in enumerate(lista):
        r = notas.get(k + 1, {})
        nota = float(r.get("nota", 4) or 4)
        ins["nota"] = nota
        if r.get("texto"):
            ins["texto"] = _limpa_texto(r["texto"]) or ins["texto"]
        if nota >= 4:
            final.append(ins)
        else:
            log(f"Cartão \"{ins.get('texto')}\" saiu (nota {nota:g}: {r.get('motivo', '')})")
    log(f"IA ({modelo}) revisou: ficaram {len(final)} de {len(lista)} cartões")
    return final


def planejar_corte(words, corte, pasta_proj, pasta_corte, log=print):
    """Cartões do corte vertical: reaproveita os do YouTube que caem dentro do corte (já revisados) e,
    se forem poucos, pede mais só para o trecho do corte. Tempos relativos ao início do corte."""
    cache = os.path.join(pasta_corte, "cartoes.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    c = ler_config()
    s, e = corte["s"], corte["e"]
    L = e - s
    maximo = int(c.get("cartoes_por_corte", 4))
    gap = 6.0
    yt = os.path.join(pasta_proj, "insercoes.json")
    lista = []
    for ins in (json.load(open(yt, encoding="utf-8")) if os.path.exists(yt) else []):
        if s + 3.5 <= ins["tempo"] <= e - 3:
            x = json.loads(json.dumps(ins))
            x["tempo"] = round(ins["tempo"] - s, 2)
            lista.append(x)
    if len(lista) < min(3, maximo) and L > 15:
        ws = [dict(w, s=round(w["s"] - s, 2), e=round(w["e"] - s, 2)) for w in words if s - 0.05 <= w["s"] and w["e"] <= e + 0.3]
        linhas = [" ".join(f"{ws[k]['w']}({ws[k]['s']:.1f})" for k in range(f["i0"], f["i1"] + 1)) for f in frases(ws)]
        ja = ", ".join(f"{x['tempo']:.0f}s" for x in lista) or "nenhum"
        qtd = max(1, min(maximo, int(L // 10)) - len(lista))
        sistema = PROMPT.format(qtd=qtd, qtd_max=qtd + 2, dur=int(L), passo=max(6, int(L / (qtd + 1))), gap=int(gap))
        try:
            resp, modelo = ia.pedir(f"cartoes_corte_{corte['n']}", sistema,
                                    "\n".join(linhas) + f"\n\nJá existem cartões em: {ja}. Não repita esses momentos.",
                                    temperatura=0.6, log=log, forte=True)
            novos = [x for x in _filtrar(resp.get("insercoes", []), L, gap)
                     if 3.5 <= x["tempo"] <= L - 3 and all(abs(x["tempo"] - y["tempo"]) >= gap for y in lista)]
            novos = revisar(escolher_icones(novos, log), 576, log)
            lista += novos
        except Exception as ex:
            log(f"(corte {corte['n']}: sem cartões novos agora: {ex})")
    lista.sort(key=lambda x: x["tempo"])
    final, ultimo = [], -99.0
    for x in lista:
        if x["tempo"] - ultimo >= gap and len(final) < maximo:
            final.append(x)
            ultimo = x["tempo"]
    log(f"Corte {corte['n']}: {len(final)} cartão(ões) na parte de cima da tela")
    json.dump(final, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return final


def planejar(words, pasta, log=print, altura=576):
    cache = os.path.join(pasta, "insercoes.json")
    if os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    c = ler_config()
    dur = words[-1]["e"] if words else 0
    qtd = max(1, int(c.get("insercoes_quantidade", 12)))
    qtd = min(qtd, max(1, int(dur // 12)))                      # vídeo curto: menos imagens
    passo = max(8, int(dur / (qtd + 1)))
    gap = max(7.0, dur / (qtd * 1.8))
    linhas = []
    for f in frases(words):
        linhas.append(" ".join(f"{words[k]['w']}({words[k]['s']:.1f})" for k in range(f["i0"], f["i1"] + 1)))
    # pede alguns a mais, porque a revisão tira os fracos
    sistema = PROMPT.format(qtd=qtd + 3, qtd_max=qtd + 6, dur=int(dur), passo=passo, gap=int(gap))
    resp, modelo = ia.pedir("insercoes", sistema, "\n".join(linhas), temperatura=0.6, log=log, forte=True)
    brutos = list(resp.get("insercoes", []))
    lista = _filtrar(brutos, dur, gap)
    if len(lista) < qtd:                                         # veio pouco: pede mais uma vez
        try:
            ja = ", ".join(f"{x['tempo']:.0f}s" for x in lista)
            resp2, _ = ia.pedir("insercoes_mais", sistema, "\n".join(linhas) +
                                f"\n\nJá escolhidos: {ja}. Escolha MAIS {qtd + 3 - len(lista)} cartões em OUTRAS partes do vídeo.",
                                temperatura=0.7, log=log, forte=True)
            lista = _filtrar(brutos + list(resp2.get("insercoes", [])), dur, gap)
        except Exception as e:
            log(f"(não deu para pedir mais imagens: {e})")
    log(f"IA ({modelo}) escolheu {len(lista)} cartão(ões) — tese: {resp.get('tese', '')}")
    lista = escolher_icones(lista, log)
    lista = revisar(lista, altura, log)
    log(f"{len(lista)} imagem(ns) aprovadas para o vídeo do YouTube")
    json.dump(lista, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return lista


# ---------------------------------------------------------------- desenho

def _grad_vertical(w, h, c1, c2):
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)) + (255,))
    return g.resize((w, h))


def _disco(D):
    """Disco roxo com degradê radial, anel dourado duplo e brilho no topo."""
    S = 2
    d = D * S
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    # degradê radial (do centro-alto mais claro para a borda escura)
    rad = Image.radial_gradient("L").resize((d, d))           # 0 no centro, 255 na borda
    base = Image.composite(Image.new("RGBA", (d, d), ROXO_ESC + (255,)), Image.new("RGBA", (d, d), ROXO_CLARO + (255,)), rad)
    base = base.transform((d, d), Image.AFFINE, (1, 0, 0, 0, 1, -d * 0.12), resample=Image.BILINEAR)
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
    im.paste(base, (0, 0), m)
    dr = ImageDraw.Draw(im)
    w1 = max(4, int(d * 0.035))
    dr.ellipse([w1 // 2, w1 // 2, d - w1 // 2, d - w1 // 2], outline=OURO + (255,), width=w1)
    r2 = int(d * 0.085)
    dr.ellipse([r2, r2, d - r2, d - r2], outline=OURO + (110,), width=max(2, int(d * 0.008)))
    # reflexo suave no topo
    ref = Image.new("L", (d, d), 0)
    ImageDraw.Draw(ref).ellipse([d * 0.18, d * 0.06, d * 0.82, d * 0.42], fill=46)
    ref = ref.filter(ImageFilter.GaussianBlur(d * 0.04))
    branco = Image.new("RGBA", (d, d), (255, 255, 255, 0))
    branco.putalpha(ref)
    im.alpha_composite(branco)
    return im.resize((D, D), Image.LANCZOS)


def _anel_tracejado(R):
    S = 2
    d = int(R * 2 * S)
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    w = max(3, int(d * 0.012))
    for k in range(28):
        a0 = k * 360 / 28
        dr.arc([w, w, d - w, d - w], a0, a0 + 6, fill=OURO + (210,), width=w)
    for k in range(4):                                        # 4 pontinhos maiores
        a = math.radians(k * 90 + 45)
        cx, cy = d / 2 + (d / 2 - w) * math.cos(a), d / 2 + (d / 2 - w) * math.sin(a)
        rr = w * 1.6
        dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=OURO_CLARO + (255,))
    return im.resize((d // S, d // S), Image.LANCZOS)


def _brilho(D):
    g = Image.new("L", (int(D * 1.6), int(D * 1.6)), 0)
    c = g.width / 2
    ImageDraw.Draw(g).ellipse([c - D * 0.5, c - D * 0.5, c + D * 0.5, c + D * 0.5], fill=150)
    g = g.filter(ImageFilter.GaussianBlur(D * 0.10))
    im = Image.new("RGBA", g.size, OURO + (0,))
    im.putalpha(g)
    return im


def _icone(spec, alt):
    if spec.get("icone_id") and ":" in spec["icone_id"]:
        conj, nome = spec["icone_id"].split(":", 1)
    else:
        achado = icones.achar(spec.get("busca") or spec.get("icone") or spec.get("palavra"))
        if not achado:
            raise ValueError("sem ícone adequado")      # o cartão não entra (nada de ícone aleatório)
        conj, nome = achado
    m = icones.mascara(conj, nome, alt)
    if m.width > alt * 1.15:
        m = m.resize((int(alt * 1.15), int(m.height * alt * 1.15 / m.width)), Image.LANCZOS)
    ouro = _grad_vertical(m.width, m.height, OURO_CLARO, OURO_ESC)
    ouro.putalpha(m)
    pad = int(alt * 0.08)
    im = Image.new("RGBA", (m.width + pad * 2, m.height + pad * 2), (0, 0, 0, 0))
    sombra = Image.new("RGBA", m.size, (10, 4, 24, 0))
    sombra.putalpha(m.point(lambda v: v * 0.55))
    im.alpha_composite(sombra, (pad + int(alt * 0.02), pad + int(alt * 0.035)))
    im = im.filter(ImageFilter.GaussianBlur(alt * 0.012))
    im.alpha_composite(ouro, (pad, pad))
    return im


def _operador(tipo, tam):
    """Sinal entre os dois ícones: ≠ (contraste), → (causa), + (soma), desenhado (não depende da fonte)."""
    S = 3
    d = tam * S
    m = Image.new("L", (d, d), 0)
    dr = ImageDraw.Draw(m)
    g = d * 0.13
    if tipo == "contraste":
        dr.rounded_rectangle([d * .12, d * .30, d * .88, d * .30 + g], radius=g / 2, fill=255)
        dr.rounded_rectangle([d * .12, d * .58, d * .88, d * .58 + g], radius=g / 2, fill=255)
        dr.line([(d * .66, d * .10), (d * .34, d * .90)], fill=255, width=int(g))
    elif tipo == "causa":
        dr.rounded_rectangle([d * .08, d * .5 - g / 2, d * .62, d * .5 + g / 2], radius=g / 2, fill=255)
        dr.polygon([(d * .55, d * .24), (d * .92, d * .5), (d * .55, d * .76)], fill=255)
    else:
        dr.rounded_rectangle([d * .12, d * .5 - g / 2, d * .88, d * .5 + g / 2], radius=g / 2, fill=255)
        dr.rounded_rectangle([d * .5 - g / 2, d * .12, d * .5 + g / 2, d * .88], radius=g / 2, fill=255)
    m = m.resize((tam, tam), Image.LANCZOS)
    ouro = _grad_vertical(tam, tam, OURO_CLARO, OURO_ESC)
    ouro.putalpha(m)
    im = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    sombra = Image.new("RGBA", (tam, tam), (10, 4, 24, 0))
    sombra.putalpha(m.point(lambda v: v * 0.6))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(tam * 0.03)), (0, 0))
    im.alpha_composite(ouro)
    return im


def _etiqueta(texto, H):
    if not texto:
        return None
    S = 2
    fnt = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), int(H * 0.068 * S))
    bb = fnt.getbbox(texto)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    h = int(H * 0.115 * S)
    w = int(tw + h * 0.9)
    pad = int(h * 0.15)
    im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sombra = Image.new("L", im.size, 0)
    ImageDraw.Draw(sombra).rounded_rectangle([pad, pad + h * 0.08, pad + w, pad + h + h * 0.08], radius=h // 2, fill=140)
    sombra = sombra.filter(ImageFilter.GaussianBlur(h * 0.08))
    sb = Image.new("RGBA", im.size, (8, 2, 20, 0))
    sb.putalpha(sombra)
    im.alpha_composite(sb)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad + w, pad + h], radius=h // 2, fill=255)
    fundo = _grad_vertical(im.width, im.height, OURO_CLARO, OURO)
    fundo.putalpha(m)
    im.alpha_composite(fundo)
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([pad, pad, pad + w, pad + h], radius=h // 2, outline=OURO_ESC + (255,), width=max(2, h // 30))
    dr.text((pad + (w - tw) / 2 - bb[0], pad + (h - th) / 2 - bb[1]), texto, font=fnt, fill=ROXO_ESC + (255,))
    return im.resize((im.width // S, im.height // S), Image.LANCZOS)


def _estrela(dr, cx, cy, r, alfa):
    if alfa <= 0 or r < 1:
        return
    pts = []
    for k in range(8):
        a = math.radians(k * 45 - 90)
        rr = r if k % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    dr.polygon(pts, fill=OURO_CLARO + (int(255 * alfa),))


def _back(x):           # ease-out com leve passada do ponto (efeito "pop")
    x = min(1.0, max(0.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _suave(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def duracao(ins):
    return DUR if ins.get("tipo", "um") == "um" else DUR + 0.8


def _cena(ins, H, seed=0, h_texto=None):
    """Prepara o cartão e devolve (largura, altura, centro_x, centro_y, desenhar(t) -> imagem RGBA, duração)."""
    duplo = ins.get("tipo", "um") != "um" and ins.get("b")
    slot_a = ins.get("a") or ins                              # cartões antigos guardavam o ícone no próprio cartão
    etq = _etiqueta(ins.get("texto", ""), h_texto or H)
    dur = duracao(ins)
    rnd = random.Random(seed)
    if duplo:
        D = int(H * 0.30)
        op_t = int(D * 0.42)
        discos = [(_disco(D), _icone(slot_a, int(D * 0.56)), 0.0), (_disco(D), _icone(ins["b"], int(D * 0.56)), 0.45)]
        sep = D / 2 + op_t * 0.62
        W = int(max(2 * sep + D * 1.45, (etq.width + 30) if etq else 0))
        Hc = int(D * 1.95)
        cx, cy = W / 2, D * 0.85
        centros = [cx - sep, cx + sep]
        operador = _operador(ins["tipo"], op_t)
    else:
        D = int(H * 0.50)
        discos = [(_disco(D), _icone(slot_a, int(D * 0.56)), 0.0)]
        W = int(max(D * 1.75, (etq.width + 30) if etq else 0))
        Hc = int(D * 1.75)
        cx, cy = W / 2, D * 0.875
        centros = [cx]
        operador = None
    anel = _anel_tracejado(D * 0.6)
    brilho = _brilho(D)
    estrelas = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.66, 0.78), rnd.uniform(0.04, 0.065), rnd.uniform(0, 6.28), rnd.randrange(len(centros)))
                for _ in range(6 if not duplo else 8)]

    def desenhar(t):
        ent = _back(t / 0.45)
        saida = 1 - _suave((t - (dur - 0.35)) / 0.35)
        esc = (0.25 + 0.75 * ent) * (0.82 + 0.18 * saida)
        alfa = min(1.0, t / 0.18) * saida
        q = Image.new("RGBA", (W, Hc), (0, 0, 0, 0))
        for (disco, icone, atraso), x in zip(discos, centros):
            ed = _back((t - atraso) / 0.45)
            if ed <= 0.01:
                continue
            b = brilho.copy()
            b.putalpha(b.getchannel("A").point(lambda v, k=(0.75 + 0.25 * math.sin(t * 3.2)) * min(1, ed): int(v * k)))
            q.alpha_composite(b, (int(x - b.width / 2), int(cy - b.height / 2)))
            a = anel.rotate(-t * 40, resample=Image.BICUBIC)
            dd = disco
            if ed < 0.999:
                dd = disco.resize((max(1, int(D * ed)), max(1, int(D * ed))), Image.BICUBIC)
                a = a.resize((max(1, int(a.width * ed)), max(1, int(a.height * ed))), Image.BICUBIC)
            q.alpha_composite(a, (int(x - a.width / 2), int(cy - a.height / 2)))
            q.alpha_composite(dd, (int(x - dd.width / 2), int(cy - dd.height / 2)))
            ei = _back((t - atraso - 0.12) / 0.45)
            if ei > 0.01:
                s_ic = max(0.01, ei) * (1 + 0.03 * math.sin(t * 2.6))
                ic = icone.resize((max(1, int(icone.width * s_ic)), max(1, int(icone.height * s_ic))), Image.BICUBIC)
                yb = math.sin(t * 2.2 + x) * D * 0.015
                q.alpha_composite(ic, (int(x - ic.width / 2), int(cy - ic.height / 2 + yb)))
        if operador is not None:
            eo = _back((t - 0.3) / 0.35)
            if eo > 0.01:
                o = operador.resize((max(1, int(operador.width * eo)), max(1, int(operador.height * eo))), Image.BICUBIC)
                q.alpha_composite(o, (int(cx - o.width / 2), int(cy - o.height / 2)))
        dr = ImageDraw.Draw(q)
        for ang, rr, tam, fase, qual in estrelas:
            k = max(0.0, math.sin(t * 3.0 + fase))
            ang2 = ang + t * 0.25
            _estrela(dr, centros[qual] + D * rr * math.cos(ang2), cy + D * rr * math.sin(ang2), D * tam * (0.4 + 0.6 * k),
                     k * min(1.0, t / 0.5))
        if etq is not None:
            ee = _suave((t - (0.28 if not duplo else 0.6)) / 0.3)
            if ee > 0:
                e = etq.copy()
                e.putalpha(e.getchannel("A").point(lambda v, k=ee: int(v * k)))
                y = cy + D * (0.40 if not duplo else 0.62) + (1 - ee) * H * 0.04
                q.alpha_composite(e, (int(cx - e.width / 2), int(y)))
        if abs(esc - 1) > 0.002:
            sw, sh = max(1, int(W * esc)), max(1, int(Hc * esc))
            outro = q.resize((sw, sh), Image.BICUBIC)
            q = Image.new("RGBA", (W, Hc), (0, 0, 0, 0))
            q.paste(outro, (int(cx - cx * esc), int(cy - cy * esc)))
        if alfa < 1:
            q.putalpha(q.getchannel("A").point(lambda v, k=alfa: int(v * k)))
        return q

    return W, Hc, cx, cy, desenhar, dur


def cena_vertical(ins, seed=0, altura=410, texto_px=54):
    """Cartão no tamanho do espaço de cima do corte vertical (altura total ~410 px, texto legível no celular)."""
    duplo = ins.get("tipo", "um") != "um" and ins.get("b")
    H = altura / (0.585 if duplo else 0.875)
    return _cena(ins, int(H), seed, h_texto=int(texto_px / 0.068))


def previa(ins, H):
    """Um quadro do cartão já montado (para a revisão da IA)."""
    *_, desenhar, dur = _cena(ins, H)
    return desenhar(min(1.8, dur - 0.5))


def quadros(ins, H, pasta, prefixo, seed=0):
    """Gera os quadros PNG (com transparência) da animação. Devolve (largura, altura, centro_x, centro_y) do quadro."""
    W, Hc, cx, cy, desenhar, dur = _cena(ins, H, seed)
    for f in range(int(dur * FPS)):
        desenhar(f / FPS).save(os.path.join(pasta, f"{prefixo}_{f:03d}.png"), compress_level=1)
    return W, Hc, cx, cy


def _destaque_png(texto, W, H, arq):
    """Palavras-chave no estilo 'lower third' (canto de baixo à esquerda): faixa escura translúcida, fio dourado
    e texto serifado claro — longe do rosto e sem disputar com outros textos."""
    from PIL import ImageFont
    tam = int(H * 0.062)
    try:
        f = ImageFont.truetype(os.path.join(FONTES, "Lora-Variable.ttf"), tam)
        f.set_variation_by_name("SemiBold")
    except Exception:
        f = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), tam)
    pal, linhas, cur = str(texto).split(), [], ""
    for p in pal:
        t = (cur + " " + p).strip()
        if f.getlength(t) <= W * 0.42 or not cur:
            cur = t
        else:
            linhas.append(cur)
            cur = p
    linhas.append(cur)
    linhas = linhas[:2]
    pad = int(H * 0.025)
    larg = int(max(f.getlength(l) for l in linhas)) + pad * 3
    alt = int(len(linhas) * tam * 1.18) + pad * 2
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = int(W * 0.05), int(H * 0.86) - alt
    d.rounded_rectangle([x0, y0, x0 + larg, y0 + alt], radius=int(H * 0.012), fill=(14, 10, 22, 190))
    d.rectangle([x0, y0, x0 + max(4, H // 180), y0 + alt], fill=OURO + (255,))
    for i, l in enumerate(linhas):
        d.text((x0 + pad * 2, y0 + pad + i * tam * 1.18 - tam * 0.08), l, font=f, fill=(248, 243, 234, 255))
    im.save(arq)


def aplicar(youtube_mp4, lista, saida, log=print, extras=None):
    """Coloca B-rolls (vídeo real em tela cheia / animação em painel) e os medalhões animados num passo só do ffmpeg."""
    c = ler_config()
    info = probe(youtube_mp4)
    W, H = info["w"], info["h"]
    extras = extras or []
    if not lista and not extras:
        return None
    td = tmpdir()
    lado = c.get("insercoes_lado", "esquerda")
    centro_x = W * (0.25 if lado == "esquerda" else 0.75)
    entradas, filtros, ultimo, n_in = ["-i", youtube_mp4], [], "0:v", 0
    # punch-in (aproxima o rosto por alguns segundos): uma cópia ampliada do próprio vídeo, ligada nas janelas
    punches = [x for x in extras if x.get("modo") == "punch"]
    if punches:
        # dois enquadramentos alternados (mais perto e centrado / um pouco mais aberto e deslocado): não fica robótico
        grupos = [(1.12, 0.5, 0.35, punches[0::2]), (1.07, 0.32, 0.30, punches[1::2])]
        grupos = [g for g in grupos if g[3]]
        filtros.append(f"[0:v]split={len(grupos) + 1}[pb]" + "".join(f"[pz{i}]" for i in range(len(grupos))))
        base = "pb"
        for i, (z, fx, fy, ps) in enumerate(grupos):
            jan = "+".join(f"between(t,{float(x['inicio']):.3f},{float(x['inicio']) + float(x['dur']):.3f})" for x in ps)
            filtros.append(f"[pz{i}]crop=iw/{z}:ih/{z}:(iw-iw/{z})*{fx}:(ih-ih/{z})*{fy},scale={W}:{H},setsar=1[pzz{i}];"
                           f"[{base}][pzz{i}]overlay=0:0:enable='{jan}'[pun{i}]")
            base = f"pun{i}"
        ultimo = base
    # destaques (2-4 palavras dela, discretos, no terço direito)
    for k, x in enumerate([x for x in extras if x.get("modo") == "texto" and x.get("texto")]):
        png = os.path.join(td, f"dest{k}.png")
        _destaque_png(x["texto"], W, H, png)
        a, d = float(x["inicio"]), float(x["dur"])
        n_in += 1
        entradas += ["-loop", "1", "-t", f"{d:.2f}", "-i", png]
        filtros.append(f"[{n_in}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(0.1, d - 0.35):.2f}:"
                       f"d=0.35:alpha=1,setpts=PTS-STARTPTS+{a:.3f}/TB[d{k}]")
        # entra deslizando da esquerda (0,35 s)
        filtros.append(f"[{ultimo}][d{k}]overlay=x='-{int(W * 0.08)}*max(0,1-(t-{a:.3f})/0.35)':y=0:eof_action=pass:"
                       f"enable='between(t,{a:.3f},{a + d:.3f})'[dd{k}]")
        ultimo = f"dd{k}"
    extras = [x for x in extras if x.get("modo") not in ("punch", "texto")]
    for k, x in enumerate(extras):
        a = float(x["inicio"])
        d = min(float(x["dur"]), info["dur"] - 0.05 - a)
        if d < 1:
            continue
        n_in += 1
        entradas += ["-i", x["arquivo"]]
        fd = min(0.3, d / 4)
        fades = f"fade=t=in:st=0:d={fd:.2f}:alpha=1,fade=t=out:st={d - fd:.2f}:d={fd:.2f}:alpha=1"
        ox = "0"
        if x.get("modo") == "tela":
            # entradas e saídas variadas conforme o tipo (nada de fade idêntico em tudo)
            tipo = x.get("tipo") or "template"
            b_ = a + d
            zoom_ent = ""
            if tipo == "video_real":                      # vídeo real: entra assentando (leve zoom que volta ao normal)
                zoom_ent = (f"scale=w='trunc({W}*(1+0.06*max(0,1-t/0.6))/2)*2':h='trunc({H}*(1+0.06*max(0,1-t/0.6))/2)*2'"
                            f":eval=frame,crop={W}:{H},")
            elif tipo == "template" and k % 2 == 1:       # animação: às vezes desliza da direita e sai pela esquerda
                fades = f"fade=t=in:st=0:d=0.12:alpha=1"
                ox = (f"'if(lt(t,{a + 0.45:.3f}),{W}*pow(max(0,1-(t-{a:.3f})/0.45),3),"
                      f"if(gt(t,{b_ - 0.35:.3f}),-{W}*pow(min(1,(t-{b_ - 0.35:.3f})/0.35),3),0))'")
            filtros.append(f"[{n_in}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                           f"trim=0:{d:.3f},{zoom_ent}format=rgba,{fades},setpts=PTS-STARTPTS+{a:.3f}/TB[b{k}]")
            px, py = 0, 0
        else:
            ph = int(H * 0.88) // 2 * 2
            pw = int(ph * 9 / 16) // 2 * 2
            borda = max(2, H // 270)
            filtros.append(f"[{n_in}:v]scale={pw}:{ph},setsar=1,pad={pw + 2 * borda}:{ph + 2 * borda}:{borda}:{borda}:"
                           f"color=0xF6EEE3,trim=0:{d:.3f},format=rgba,{fades},setpts=PTS-STARTPTS+{a:.3f}/TB[b{k}]")
            px = int(min(max(0, centro_x - pw / 2 - borda), W - pw - 2 * borda))
            py = (H - ph) // 2 - borda
        xo = ox if ox != "0" else str(px)
        filtros.append(f"[{ultimo}][b{k}]overlay=x={xo}:y={py}:eof_action=pass:"
                       f"enable='between(t,{a:.3f},{a + d:.3f})'[w{k}]")
        ultimo = f"w{k}"
    for k, ins in enumerate(lista):
        log(f"Desenhando imagem {k + 1} de {len(lista)}: {ins.get('texto') or ins.get('palavra')}")
        try:
            qw, qh, cx, cy = quadros(ins, H, td, f"c{k}", seed=k)
        except Exception as e:
            log(f"(cartão \"{ins.get('texto')}\" não entra: {e})")
            continue
        a = max(0.0, ins["tempo"] - 0.2)
        b = min(info["dur"] - 0.05, a + duracao(ins))
        n_in += 1
        entradas += ["-framerate", str(FPS), "-i", os.path.join(td, f"c{k}_%03d.png")]
        filtros.append(f"[{n_in}:v]format=rgba,setpts=PTS-STARTPTS+{a:.3f}/TB[c{k}]")
        x = int(min(max(0, centro_x - cx), W - qw))
        y = int(min(max(0, H * 0.45 - cy), H - qh))
        filtros.append(f"[{ultimo}][c{k}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{a:.3f},{b:.3f})'[v{k}]")
        ultimo = f"v{k}"
    if ultimo == "0:v":
        return None
    fc = os.path.join(td, "fc.txt")
    open(fc, "w").write(";".join(filtros))
    parcial = saida + ".parcial.mp4"
    log("Juntando as imagens e os B-rolls no vídeo do YouTube…")
    run([FFMPEG, "-y", *entradas, opcao_filtro_arquivo(), fc, "-map", f"[{ultimo}]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", c["preset"], "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", parcial])
    os.replace(parcial, saida)
    log(f"Vídeo do YouTube pronto com {len(lista)} cartão(ões) e {len(extras)} B-roll(s)")
    return saida
