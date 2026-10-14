"""B-roll Engine V2: decisões visuais editoriais.

Uma chamada ao Gemini por corte (ou por janela do YouTube) decide, para cada momento forte da fala:
  rosto | video_real | foto_documento_print | grafico_dado_mapa | animacao_editorial
e já traz buscas, template, dados, título e um plano B. Qualidade > quantidade: "rosto" é a escolha padrão.
Vídeo/foto de banco só entra com nota >= 4 (uma chamada de visão para todos os itens). Se a IA falhar: plano B
(template) ou rosto — nunca "o primeiro resultado", nunca ícone aleatório.
"""
import json, os, re, unicodedata
from .transcrever import frases
from .util import ler_config
from . import ia, videos_reais
from motor import templates

VISUAIS = ("rosto", "video_real", "foto_documento_print", "grafico_dado_mapa", "animacao_editorial")

CATALOGO = """CENAS — OBRIGATÓRIO: pelo menos METADE dos momentos de animação têm que ser CENAS (a imagem EXPLICA a
ideia com bonecos simples, objetos e movimento; pouco texto). Texto sozinho (palavra_chave/lista) só quando nenhuma
cena servir. Exemplos de "dados":
  {"template": "duelo", "dados": {"a": {"rotulo": "força"}, "b": {"rotulo": "desejo"}, "frase": "controle pelo desejo"}}
  {"template": "energia", "dados": {"rotulo": "sua energia", "de": 100, "para": 10, "texto": "o lugar te suga"}}
  {"template": "pilha", "dados": {"a": {"rotulo": "propaganda"}, "b": {"rotulo": "entretenimento"}, "resultado": "consumo"}}

- duelo {"a": {"rotulo": "1-2 palavras"}, "b": {"rotulo": "..."}, "frase": "opcional, até 8 palavras"}
    dois personagens = dois conceitos opostos; A cansa e a bateria acaba, B segue firme (ex.: motivação × disciplina)
- energia {"rotulo": "1-3 palavras", "de": 100, "para": 15, "texto": "opcional"}  pessoa anda e a energia cai
    (ou sobe, se "para" > "de"): cansaço, lugar que suga, vício, esgotamento, recuperar a energia
- escada {"passos": ["2 a 3 etapas curtas"], "meta": "1-2 palavras"}  progresso, evolução, subir de nível
- alvos {"a": "1-3 palavras (o disperso)", "b": "1-3 palavras (o focado)"}  foco × dispersão, várias metas × uma
- caminho {"texto": "frase curta", "meta": "1-2 palavras"}  jornada, propósito, futuro, caminho que se revela
- pilha {"a": {"rotulo": "..."}, "b": {"rotulo": "..."}, "resultado": "1-2 palavras"}  acúmulo, constância ×
    perfeccionismo, pequenos hábitos que somam
- barras {"titulo": "...", "itens": [{"rotulo": "curto", "valor": "número dito"}], "destaque": índice}  comparar
    grandezas (2 a 4 barras; só números que ela disse)
- pessoas {"itens": [{"numero": "93%", "texto": "curto"}]}  proporção de pessoas (1 a 3 linhas; só números ditos)
- relogio {"texto": "frase curta", "numero": "ano/prazo opcional, se dito"}  tempo passando, prazo, urgência
- plataformas / sequencia {"passos": [...], "meta": "..."}  outras formas de progresso
- balanca / caminhos {"a": {"rotulo": ...}, "b": {"rotulo": ...}}  outras formas de comparação/escolha
- domino / fluxo {"causa": "curta", "efeito": "curta"}  outras formas de causa e consequência
- chegada {"texto": "frase curta", "rotulo": "1-2 palavras"}  algo que vem de fora, do céu, de longe
- pontos / anel {"numero": "75%", "texto": "curto"}  outras formas de porcentagem (só números ditos)
VARIE: não repita a mesma cena no mesmo corte; os exemplos acima são formatos, não textos para copiar.
TEMPLATES (escolha 1 e preencha "dados" com textos CURTOS, em português, usando palavras DITAS por ela):
- palavra_chave {"texto": "1-3 palavras", "apoio": "frase curta opcional", "etiqueta": "rótulo opcional"}
- citacao {"frase": "a frase de impacto dela, até 12 palavras", "autor": "opcional"}
- contraste {"titulo": "opcional", "a": {"rotulo": "1-2 palavras", "texto": "curto"}, "b": {"rotulo": "...", "texto": "..."}}
- comparacao {"titulo": "...", "a": {"rotulo": "...", "itens": ["2-3 itens curtos"]}, "b": {"rotulo": "...", "itens": [...]}}
- transformacao {"de": "1-3 palavras", "para": "1-3 palavras", "titulo": "opcional"}
- causa_efeito {"causa": "curta", "efeito": "curta", "ligacao": "1-2 palavras (ex.: acumula, gera)"}
- dado {"numero": "80% | 2018 | 3x | R$ 500", "rotulo": "o que é", "contexto": "opcional"}  (SÓ números que ela disse)
- espectro {"titulo": "...", "esquerda": "polo 1", "direita": "polo 2", "posicao": 0.0-1.0, "marcador": "opcional"}
- linha_tempo {"titulo": "...", "itens": [{"data": "2018", "texto": "curto"}]}  (2 a 4 itens, só datas ditas)
- processo {"titulo": "...", "passos": ["2 a 4 etapas curtas"]}
- lista {"titulo": "...", "itens": ["2 a 5 itens"], "destaque": índice_ou_null}
- conceito {"titulo": "...", "icone_a": ["substantivo concreto em inglês", "alternativa"], "icone_b": [...] ou null,
            "relacao": "dentro|fonte|sobre|contra|ao_lado", "rotulo_a": "...", "rotulo_b": "..."}
- foco {"icone": ["substantivo concreto em inglês", "alternativa"], "texto": "frase curta", "etiqueta": "opcional"}
- documento {"legenda": "curta", "etiqueta": "ex.: arquivo, mapa, 1964", "foco": [x 0-1, y 0-1] do ponto importante
            (opcional), "marcacao": "circulo|sublinhado|seta"}  (só para foto_documento_print)
A família de cores do vídeo é fixa (o editor aplica): varie o TEMPLATE e a composição, não as cores.
TEXTO NA TELA: só palavras/conceitos que ELA DISSE nesse trecho. PROIBIDO rótulo genérico ou de preenchimento
("A"/"B", "lado A", "polo oposto", "opção 1", "conceito X", "Essência × Estado" se ela não disse isso).
Se a comparação/relação não está clara na fala, NÃO force o template: use palavra_chave, citacao ou rosto."""

SISTEMA = """Você é a diretora de arte do canal da Natinha (análise comportamental, crítica social, espiritualidade e
consciência; tom direto). Você decide ONDE e COMO entra imagem por cima da fala. O objetivo NÃO é encher o vídeo:
é mostrar a IDEIA que está sendo dita quando isso realmente acrescenta informação ou emoção.

PRINCÍPIOS
- O vídeo precisa ser VISUALMENTE ANIMADO: ilustre bastante, com variedade (vídeo real, foto de banco, animação,
  gráfico). Fique só no rosto quando a frase for pessoal/emocional e o rosto dela for o mais forte.
  Mesmo assim, nunca use imagem genérica sem ligação com a fala.
- Nunca ilustre uma palavra solta. Ilustre a IDEIA da frase (o argumento, a comparação, a virada).
- SEMPRE preencha "buscas" (2 buscas de cena REAL em inglês, SUJEITO + AÇÃO + AMBIENTE), mesmo quando escolher
  animação: o editor usa como alternativa para não repetir a mesma ilustração.
- Para cada momento escolha o "visual":
  * "video_real": a frase fala de algo CONCRETO que dá para filmar (pessoas fazendo algo, um lugar, um objeto real).
    "buscas": 2-3 buscas em inglês no formato SUJEITO + AÇÃO + AMBIENTE (ex.: "teen students listening teacher
    classroom", "nurse caring for elderly patient hospital", "woman pouring herbs into bath water").
    PROIBIDO em buscas: flores, céu, paisagem, pôr do sol, café, ponte, natureza, "abstract", "energy", "spiritual",
    "concept" — a não ser que ela fale exatamente disso.
  * "foto_documento_print": fato histórico, pessoa pública, documento, obra de arte, lugar real específico ou mapa.
    "buscas": 1-3 buscas para o Wikimedia Commons (nome próprio/termo factual, ex.: "Carl Jung portrait",
    "map of Brazil", "Hermetic Corpus manuscript"). template "documento".
  * "grafico_dado_mapa": número, porcentagem, data, escala, etapas, evolução → dado, espectro, linha_tempo, processo,
    comparacao.
  * "animacao_editorial": ideia abstrata → PRIMEIRO uma CENA (duelo, energia, escada, alvos, caminho, pilha,
    relogio) quando a ideia vira uma pequena ação; senão contraste, transformacao, causa_efeito, citacao, lista,
    palavra_chave. Evite "conceito"/"foco" com ícone (ícone genérico não explica ideia complexa).
  * "grafico_dado_mapa" também pode ser barras, pessoas ou relogio.
  * "rosto": nada acrescenta de verdade → não ponha nada (pode nem listar).
- Para "video_real" e "foto_documento_print" SEMPRE mande também "template"+"dados" de uma animação editorial como
  PLANO B (usado se nenhuma imagem de banco for boa o bastante), ou "template": null para manter o rosto.
- Nunca invente fatos, números, datas ou nomes que ela não disse. Textos na tela: curtos, com as palavras dela.
- Vídeo/foto de banco tem que mostrar a AÇÃO ou a IDEIA central da frase, não só o assunto. Ex.: "atendimento nos
  hospitais públicos" → paciente sendo atendido, recepção, espera (NÃO aparelho médico, prédio, notebook);
  "a energia das pessoas" → pessoas interagindo, multidão, tensão social (NÃO objeto, NÃO paisagem).
- Não sobrecarregue: um B-roll completo já basta naquele momento; não ponha "destaque" junto.
- "titulo": 2 a 4 palavras-chave ditas por ela (aparece sobre vídeos/fotos reais).
- HIERARQUIA: B-roll excelente > intervenção editorial (template) > rosto com tratamento visual > (NUNCA) B-roll genérico.
- "Manter o rosto" NÃO é deixar o vídeo parado: onde não houver momento visual forte, use INTERVENÇÕES LEVES ("leves"):
  * "punch_in": aproxima o rosto dela numa frase de ênfase (1.5 a 3 s);
  * "destaque": 2 a 4 palavras DITAS por ela aparecem na tela, discretas (2 a 3 s), na hora em que ela fala.
  Leves não cobrem o rosto. Use nas frases de ênfase, viradas, perguntas e números.

""" + CATALOGO

PEDIDO_CORTE = """Corte vertical de {dur:.1f}s. Frases com o tempo (s, relativo ao início do corte) de cada palavra.
Escolha de {n_min} a {n_max} momentos visuais (o corte vertical NÃO pode ficar só no rosto). Intervenha onde a fala
tiver: conceito importante, comparação, número, lugar, pessoa, objeto, evento, causa e efeito, mudança, contraste,
pergunta forte, conclusão ou frase de impacto. Sem carnaval: cada imagem tem que explicar a ideia.
"inicio" = o segundo em que a FRASE começa (o editor encaixa na palavra exata); "frase" = as palavras exatas dela.
Prefira VÍDEO REAL ou FOTO de banco nas frases concretas e animação nas abstratas; misture os tipos.
Entre os momentos, use "leves" do tipo "punch_in" (aproximar o rosto) nas frases de ênfase.
Regras de tempo: nenhum antes de 3.5s (gancho com o rosto) nem depois de {fim:.1f}s (frase final com o rosto);
cada momento dura 3 a 5s; pelo menos 1.5s de rosto entre um e outro.

Responda em JSON:
{{"tese": "a tese do corte", "momentos": [{{"inicio": s, "dur": s, "frase": "trecho", "ideia": "a ideia em 1 frase",
  "visual": "video_real|foto_documento_print|grafico_dado_mapa|animacao_editorial|rosto", "porque": "curto",
  "titulo": "2-4 palavras", "buscas": ["..."] ou [], "template": "nome ou null", "dados": {{...}},
}}],
 "leves": [{{"inicio": s, "dur": s, "tipo": "punch_in|destaque", "texto": "2-4 palavras (só no destaque)"}}]}}

FALAS:
{falas}"""

PEDIDO_YT = """Trecho de {ini:.0f}s a {fim:.0f}s de um vídeo HORIZONTAL do YouTube. Frases com o tempo (s, desde o começo
do vídeo) de cada palavra. Vídeo real, foto/documento, gráfico e animação entram em TELA CHEIA por alguns segundos.
Escolha de {n_min} a {n_max} momentos visuais: o vídeo tem que ser ANIMADO, com imagem na tela com frequência
quando a fala pede (o ritmo vem da fala, não do relógio). Prefira VÍDEO REAL ou FOTO de banco nas frases concretas e
animação nas abstratas; misture os tipos. Entre os momentos, use "leves" (punch_in / destaque) só nas frases de ênfase
de verdade (no máximo 1 destaque de texto a cada 30 s).
Cada momento dura 3 a 5s; pelo menos 4s entre um e outro; NÃO use estes intervalos (já têm cartão): {ocupados}.

Responda em JSON:
{{"momentos": [{{"inicio": s, "dur": s, "frase": "trecho", "ideia": "...", "visual": "...", "porque": "curto",
  "titulo": "2-4 palavras", "buscas": [...], "template": "nome ou null", "dados": {{...}}}}],
 "leves": [{{"inicio": s, "dur": s, "tipo": "punch_in|destaque", "texto": "2-4 palavras (só no destaque)"}}]}}

FALAS:
{falas}"""

REFAZER = """Refaça a decisão visual deste momento com uma solução DIFERENTE da anterior (outro template ou outra
composição), mais clara para quem vê sem som. Frase: "{frase}". Ideia: {ideia}. Antes foi: {antes}.
{extra}
Responda em JSON: {{"visual": "grafico_dado_mapa|animacao_editorial", "template": "...", "dados": {{...}},
"estilo": "...", "titulo": "2-4 palavras", "ideia": "..."}}"""


# ------------------------------------------------------------------ planejamento
def _falas(words, s, e, relativo=True):
    ws = [w for w in words if w["s"] >= s - 0.05 and w["e"] <= e + 0.3]
    if relativo:
        ws = [{"w": w["w"], "s": round(w["s"] - s, 2), "e": round(w["e"] - s, 2)} for w in ws]
    return "\n".join(" ".join(f"{ws[k]['w']}({ws[k]['s']:.1f})" for k in range(f["i0"], f["i1"] + 1)) for f in frases(ws))


# ------------------------------------------------------------------ família visual do vídeo
_PALAVRAS_FAMILIA = {
    "espiritual": "energi espir alma sombr consci medit erva banho oraca reza deus unive vibra chakr astro intui "
                  "sagra luz campo aura cura anunn",
    "tech": "siste tecno algor inter rede celul dados progr tela app digit strea",
    "documental": "histo livro escol cienc pesqu estud docum arqui anos secul civil sumer antig egito",
    "psicologico": "mente cereb compo psico emoca medo ansie trauma habit dopam vicio",
    "alerta": "manip contr gover propa guerr polic viol perig engan menti midia",
}


def _raiz_projeto(pasta):
    return pasta if os.path.exists(os.path.join(pasta, "youtube.mp4")) else os.path.dirname(os.path.abspath(pasta))


def familia_visual(pasta, words=None, log=print):
    """Uma família visual por VÍDEO (YouTube e cortes iguais). Vem da chamada de limpeza (sem chamada a mais);
    se não veio, escolhe pelas palavras do vídeo e guarda em analise_video.json."""
    raiz = _raiz_projeto(pasta)
    arq = os.path.join(raiz, "analise_video.json")
    dados = {}
    try:
        dados = json.load(open(arq, encoding="utf-8")) if os.path.exists(arq) else {}
    except ValueError:
        dados = {}
    nova = ler_config().get("estetica", "nova") == "nova"
    validas = templates.NOVAS if nova else ("papel", "escuro", "matrix", "roxo")
    fam = dados.get("tema_visual")
    if nova and fam in templates.DA_ANTIGA:
        fam = templates.DA_ANTIGA[fam]
    if fam not in validas:
        try:
            meta = json.load(open(os.path.join(raiz, "youtube_meta.json"), encoding="utf-8"))
            fam = meta.get("tema_visual")
            if nova and fam in templates.DA_ANTIGA:
                fam = templates.DA_ANTIGA[fam]
        except (OSError, ValueError):
            fam = None
    if fam not in validas:
        if words is None:
            try:
                words = json.load(open(os.path.join(raiz, "youtube_palavras.json"), encoding="utf-8"))
            except (OSError, ValueError):
                words = []
        raizes = [_norm(w["w"])[:5] for w in words or []]
        pontos = {f: sum(1 for r in raizes if r and any(r.startswith(k) for k in ch.split()))
                  for f, ch in _PALAVRAS_FAMILIA.items()}
        fam = max(pontos, key=pontos.get) if max(pontos.values()) >= 4 else "documental"
        if not nova:
            fam = {"espiritual": "roxo", "tech": "matrix", "documental": "papel", "psicologico": "escuro",
                   "alerta": "escuro"}[fam]
        log(f"Família visual do vídeo (pelas palavras): {fam}")
    if dados.get("tema_visual") != fam:
        dados["tema_visual"] = fam
        try:
            json.dump(dados, open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
    return fam


def _estilo_da_familia(fam, k):
    """A maior parte na cor principal da família; de vez em quando a variação da mesma família (outro 'capítulo')."""
    var = templates.FAMILIAS.get(fam) or templates.FAMILIAS["escuro"]
    return var[1] if k % 4 == 3 else var[0]


# ------------------------------------------------------------------ texto ruim (sem chamar a IA)
_STOP = set("que para com uma uns umas por mais mas nao sim isso isto essa esse esta este ela ele elas eles voce "
            "voces gente aqui ali entao tudo todo toda todos quando como onde porque pra pro tem ter ser sao foi "
            "vai the and das dos nas nos num numa pelo pela sua seu suas seus".split())
_PLACEHOLDER = re.compile(
    r"^\s*((lado|polo|op[cç][aã]o|item|conceito|ideia|exemplo|texto|r[oó]tulo|t[ií]tulo|palavra|grupo|tipo|caso|"
    r"ponto|elemento|coisa|fator|termo|aspecto|nome)\s*(oposto|contr[aá]rio|positivo|negativo|um|dois)?\s*)?"
    r"([a-d]|[1-5]|x|y|um|dois|tr[eê]s|\.\.\.|…|-|\?)?\s*$", re.I)
_LIXO = re.compile(r"lorem|placeholder|texto aqui|xxx|\[.*\]|\{.*\}", re.I)
_NUM_EXTENSO = re.compile(r"\b(dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|vinte|trinta|quarenta|cinquenta|"
                          r"sessenta|setenta|oitenta|noventa|cem|cento|mil|milh|metade|dobro|triplo)", re.I)


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return t


def _raizes(texto):
    return {tok[:5] for tok in re.findall(r"[a-z0-9]+", _norm(texto)) if len(tok) >= 3 and tok not in _STOP}


def texto_ruim(t):
    t = str(t or "").strip()
    return bool(t) and (bool(_PLACEHOLDER.match(t)) or bool(_LIXO.search(t)))


def _ancorado(texto, fala, minimo=1, fracao=0.0):
    """O texto usa palavras que ela realmente disse por perto?"""
    r = _raizes(texto)
    if not r:
        return False
    ach = len(r & fala)
    return ach >= minimo and ach >= fracao * len(r)


def _numeros_ditos(numero, fala_txt):
    dig = re.findall(r"\d+", str(numero or ""))
    if not dig:
        return False
    fala_dig = set(re.findall(r"\d+", fala_txt))
    return all(d in fala_dig for d in dig) or bool(_NUM_EXTENSO.search(_norm(fala_txt)))


def checar_textos(tpl, dados, titulo, fala_txt):
    """Validação local dos textos do template. Devolve (template, dados, motivo_da_recusa_ou_None).
    Campos opcionais ruins saem; campos principais ruins → o template não serve."""
    fala = _raizes(fala_txt)
    d = json.loads(json.dumps(dados or {}))          # cópia
    for lado in ("a", "b"):                           # a IA às vezes manda "a": "texto" em vez de {"rotulo": ...}
        if tpl in ("duelo", "pilha", "contraste", "comparacao") and isinstance(d.get(lado), str):
            d[lado] = {"rotulo": d[lado]}
        if tpl == "alvos" and isinstance(d.get(lado), dict):
            d[lado] = d[lado].get("rotulo") or d[lado].get("texto") or ""
    if tpl in ("duelo", "pilha") and not (d.get("a") or d.get("b")) and d.get("esquerda") and d.get("direita"):
        d["a"], d["b"] = {"rotulo": d.pop("esquerda")}, {"rotulo": d.pop("direita")}
    if tpl in ("conceito", "foco") and ler_config().get("estetica", "nova") == "nova":
        tpl, d = "palavra_chave", {"texto": titulo or d.get("texto") or d.get("titulo") or ""}
        if not d["texto"] or not _ancorado(d["texto"], fala, 1, 0.5):
            return None, {}, "ícone genérico não explica a ideia"
    for k in ("titulo", "apoio", "etiqueta", "contexto", "marcador", "autor", "rotulo_a", "rotulo_b", "legenda"):
        v = d.get(k)
        if isinstance(v, str) and (texto_ruim(v) or (k in ("titulo", "apoio", "rotulo_a", "rotulo_b", "legenda")
                                                    and not _ancorado(v, fala))):
            d.pop(k)
    ruim = None
    if tpl in ("contraste", "comparacao"):
        for lado in ("a", "b"):
            x = d.get(lado) if isinstance(d.get(lado), dict) else {}
            rot = str(x.get("rotulo", ""))
            itens = [str(i) for i in (x.get("itens") or []) if i]
            if texto_ruim(rot) or not rot.strip():
                ruim = f"rótulo genérico \"{rot}\""
            elif not _ancorado(rot, fala) and not any(_ancorado(i, fala) for i in itens + [str(x.get("texto", ""))]):
                ruim = f"\"{rot}\" não foi dito"
            if itens:
                x["itens"] = [i for i in itens if not texto_ruim(i)]
        a_, b_ = d.get("a") or {}, d.get("b") or {}
        if not ruim and _norm(a_.get("rotulo")).strip() == _norm(b_.get("rotulo")).strip():
            ruim = "os dois lados iguais"
    elif tpl == "espectro":
        for k in ("esquerda", "direita"):
            if texto_ruim(d.get(k)) or not _ancorado(d.get(k), fala):
                ruim = f"polo \"{d.get(k)}\" genérico ou não dito"
    elif tpl == "transformacao":
        for k in ("de", "para"):
            if texto_ruim(d.get(k)) or not _ancorado(d.get(k), fala):
                ruim = f"\"{d.get(k)}\" não foi dito"
    elif tpl == "causa_efeito":
        for k in ("causa", "efeito"):
            if texto_ruim(d.get(k)) or not _ancorado(d.get(k), fala):
                ruim = f"\"{d.get(k)}\" não foi dito"
    elif tpl == "palavra_chave":
        if texto_ruim(d.get("texto")) or not _ancorado(d.get("texto"), fala, 1, 0.5):
            ruim = f"\"{d.get('texto')}\" não foi dito"
    elif tpl == "citacao":
        if not _ancorado(d.get("frase") or d.get("texto"), fala, 2, 0.6):
            ruim = "citação que ela não falou"
    elif tpl == "dado":
        if not _numeros_ditos(d.get("numero"), fala_txt):
            ruim = f"número \"{d.get('numero')}\" não foi dito"
    elif tpl == "linha_tempo":
        itens = [i for i in (d.get("itens") or []) if isinstance(i, dict) and _numeros_ditos(i.get("data"), fala_txt)]
        if len(itens) < 2:
            ruim = "datas que ela não disse"
        d["itens"] = itens
    elif tpl in ("lista", "processo"):
        k = "itens" if tpl == "lista" else "passos"
        itens = [str(i) for i in (d.get(k) or []) if i and not texto_ruim(i)]
        bons = [i for i in itens if _ancorado(i, fala)]
        if len(itens) < 2 or len(bons) < max(2, (len(itens) + 1) // 2):
            ruim = "itens genéricos ou não ditos"
        d[k] = itens
        if tpl == "lista" and d.get("destaque") is not None:
            try:
                if int(d["destaque"]) >= len(itens):
                    d["destaque"] = None
            except (TypeError, ValueError):
                d["destaque"] = None
    elif tpl == "foco":
        if texto_ruim(d.get("texto")) or not _ancorado(d.get("texto"), fala):
            ruim = "frase que ela não disse"
    elif tpl in ("duelo", "pilha", "balanca", "caminhos"):
        for lado in ("a", "b"):
            x = d.get(lado) if isinstance(d.get(lado), dict) else {}
            rot = str(x.get("rotulo", ""))
            if texto_ruim(rot) or not _ancorado(rot, fala):
                ruim = f"\"{rot}\" genérico ou não dito"
        for k in ("frase", "resultado"):
            if d.get(k) and (texto_ruim(d[k]) or not _ancorado(d[k], fala)):
                d.pop(k)
    elif tpl == "alvos":
        for k in ("a", "b"):
            if texto_ruim(d.get(k)) or not _ancorado(d.get(k), fala):
                ruim = f"\"{d.get(k)}\" genérico ou não dito"
    elif tpl in ("domino", "fluxo"):
        for k in ("causa", "efeito"):
            if texto_ruim(d.get(k)) or not _ancorado(d.get(k), fala):
                ruim = f"\"{d.get(k)}\" não foi dito"
    elif tpl in ("pontos", "anel"):
        if not _numeros_ditos(d.get("numero"), fala_txt):
            ruim = f"número \"{d.get('numero')}\" não foi dito"
        if d.get("texto") and (texto_ruim(d["texto"]) or not _ancorado(d["texto"], fala)):
            d.pop("texto")
    elif tpl in ("energia", "caminho", "relogio", "chegada"):
        for k in ("rotulo", "texto", "meta"):
            if d.get(k) and (texto_ruim(d[k]) or not _ancorado(d[k], fala)):
                d.pop(k)
        if tpl == "relogio" and d.get("numero") and not _numeros_ditos(d.get("numero"), fala_txt):
            d.pop("numero")
        if not any(d.get(k) for k in ("rotulo", "texto", "meta")):
            ruim = "cena sem nenhum texto dito"
    elif tpl in ("escada", "plataformas", "sequencia"):
        passos = [str(p) for p in (d.get("passos") or []) if p and not texto_ruim(p) and _ancorado(p, fala)]
        d["passos"] = passos[:3]
        if d.get("meta") and (texto_ruim(d["meta"]) or not _ancorado(d["meta"], fala)):
            d.pop("meta")
        if not passos and not d.get("meta"):
            ruim = "escada sem etapas ditas"
    elif tpl == "barras":
        itens = [i for i in (d.get("itens") or []) if isinstance(i, dict) and not texto_ruim(i.get("rotulo"))
                 and _numeros_ditos(i.get("valor"), fala_txt)]
        d["itens"] = itens
        if len(itens) < 2:
            ruim = "barras sem números ditos"
    elif tpl == "pessoas":
        itens = [i for i in (d.get("itens") or []) if isinstance(i, dict) and _numeros_ditos(i.get("numero"), fala_txt)]
        d["itens"] = itens
        if not itens:
            ruim = "porcentagens que ela não disse"
    elif tpl == "conceito":
        if not (d.get("rotulo_a") or d.get("titulo")):
            ruim = "conceito sem nenhum texto dito"
    if ruim is None:
        return tpl, d, None
    # não força o template: tenta uma palavra-chave com o título (se for fala dela); senão fica o rosto
    if titulo and not texto_ruim(titulo) and _ancorado(titulo, fala, 1, 0.5):
        return "palavra_chave", {"texto": titulo}, ruim
    return None, {}, ruim


def ancorar_inicio(frase, ini, words, janela=6.0, antes=0.15):
    """A IA dá o segundo 'de cabeça' (medimos erros de até 1,5–3 s). Aqui o momento é encaixado no início EXATO
    da frase na transcrição: a imagem entra junto (ou um pouquinho antes) da fala que ela ilustra."""
    alvo = [t for t in re.findall(r"[a-z0-9]+", _norm(frase))][:5]
    if len(alvo) < 2 or not words:
        return ini, False
    cand = [i for i, w in enumerate(words) if ini - janela <= w["s"] <= ini + janela]
    melhor = None
    for i in cand:
        pal = [re.sub(r"[^a-z0-9]", "", _norm(w["w"])) for w in words[i:i + len(alvo) + 2]]
        pal = [p for p in pal if p]
        if not pal or pal[0][:4] != alvo[0][:4]:      # a frase tem que COMEÇAR nesta palavra
            continue
        acertos, j = 0, 0
        pesos = [2, 2, 1, 1, 1][:len(alvo)]      # o começo da frase vale mais
        for t, peso in zip(alvo, pesos):        # casa em ordem, tolerando uma palavra a mais no meio
            for k in range(j, min(j + 2, len(pal))):
                if pal[k][:4] == t[:4]:
                    acertos += peso
                    j = k + 1
                    break
        nota = acertos / sum(pesos)
        if nota >= 0.6 and (melhor is None or (nota, -abs(words[i]["s"] - ini)) > (melhor[0], -abs(melhor[1] - ini))):
            melhor = (nota, words[i]["s"])
    if melhor is None:
        return ini, False
    return round(max(0.0, melhor[1] - antes), 2), True


def _fala_perto(words, a, b):
    return " ".join(w["w"] for w in (words or []) if a - 0.2 <= w["s"] <= b + 0.2)


def _validar(lista, ini_min, fim_max, gap, ocupados=(), words=None, familia="escuro", log=print, youtube=False):
    out = []
    for m in sorted([x for x in lista if isinstance(x, dict)], key=lambda x: float(x.get("inicio", 0) or 0)):
        vis = str(m.get("visual", "")).strip()
        if vis not in VISUAIS or vis == "rosto":
            continue
        try:
            ini, d = float(m["inicio"]), min(5.0, max(3.0, float(m.get("dur", 4))))
        except (KeyError, TypeError, ValueError):
            continue
        if words:
            ini, _ = ancorar_inicio(m.get("frase", ""), ini, words)
        ini = max(ini, ini_min)
        if ini + d > fim_max:
            d = fim_max - ini
        if d < 2.5 or (out and ini < out[-1]["inicio"] + out[-1]["dur"] + gap):
            continue
        if any(ini < b and ini + d > a for a, b in ocupados):
            continue
        tpl = m.get("template")
        if tpl is not None and tpl not in templates.TEMPLATES:
            tpl = "palavra_chave"
        dados = m.get("dados") if isinstance(m.get("dados"), dict) else {}
        titulo = str(m.get("titulo", "") or "")[:40]
        if tpl == "palavra_chave" and not dados.get("texto"):
            dados["texto"] = titulo
        fala_txt = _fala_perto(words, ini - 8, ini + d + 8) if words else ""
        if texto_ruim(titulo) or (fala_txt and titulo and not _ancorado(titulo, _raizes(fala_txt))):
            titulo = ""
        if tpl and tpl != "documento" and fala_txt:
            tpl_novo, dados, motivo = checar_textos(tpl, dados, titulo, fala_txt)
            if motivo:
                log(f"(texto recusado em {ini:.1f}s — {tpl}: {motivo}; " +
                    (f"vira {tpl_novo})" if tpl_novo else "fica sem animação)"))
            tpl = tpl_novo
        if vis in ("grafico_dado_mapa", "animacao_editorial") and not tpl:
            continue
        if vis == "foto_documento_print":
            tpl_b = tpl if tpl and tpl != "documento" else None
        else:
            tpl_b = tpl
        if vis in ("video_real", "foto_documento_print") and not (m.get("buscas") or []):
            if not tpl_b:
                continue
            vis = "animacao_editorial"
            tpl = tpl_b
        out.append({
            "v2": True, "visual": vis, "inicio": round(ini, 2), "dur": round(d, 2),
            "frase": str(m.get("frase", ""))[:200], "ideia": str(m.get("ideia", ""))[:200],
            "porque": str(m.get("porque", ""))[:120], "titulo": titulo,
            "buscas": [q for q in (m.get("buscas") or []) if isinstance(q, str)][:3],
            "template": tpl if vis in ("grafico_dado_mapa", "animacao_editorial") else tpl_b,
            "dados": dados,
        })
    if ler_config().get("estetica", "nova") == "nova":
        if ler_config().get("variedade", True):
            out = diversificar(out, log, youtube=youtube)
        else:                                   # V3 original: troca fixa texto → cena
            for b in out:
                if b.get("template") and b.get("visual") in ("animacao_editorial", "grafico_dado_mapa"):
                    b["template"], b["dados"] = para_cena(b["template"], b.get("dados"))
    for k, b in enumerate(out):                 # uma família de cor por vídeo
        b["estilo"] = _estilo_da_familia(familia, k)
    # o mesmo template duas vezes seguidas parece slide repetido: a 2ª vira palavra-chave se der
    for k in range(1, len(out)):
        if out[k]["template"] and out[k]["template"] == out[k - 1]["template"] and \
                out[k]["template"] not in ("palavra_chave", "documento") and out[k]["visual"] != "video_real":
            if out[k]["titulo"]:
                out[k]["template"], out[k]["dados"] = "palavra_chave", {"texto": out[k]["titulo"]}
    return out


def validar_leves(lista, ini_min, fim_max, ocupados=(), words=None):
    out = []
    for m in sorted([x for x in (lista or []) if isinstance(x, dict)], key=lambda x: float(x.get("inicio", 0) or 0)):
        tipo = m.get("tipo")
        if tipo not in ("punch_in", "destaque"):
            continue
        try:
            ini = max(float(m["inicio"]), ini_min)
            d = min(3.0, max(1.5, float(m.get("dur", 2.5))))
        except (KeyError, TypeError, ValueError):
            continue
        if ini + d > fim_max or any(ini < b and ini + d > a for a, b in ocupados):
            continue
        if out and ini < out[-1]["inicio"] + out[-1]["dur"] + 1.0:
            continue
        pals = str(m.get("texto", "")).split() if tipo == "destaque" else []
        txt = " ".join(pals) if 0 < len(pals) <= 5 else ""      # texto longo não é cortado no meio: vira punch-in
        if txt and (texto_ruim(txt) or (words and not _ancorado(txt, _raizes(_fala_perto(words, ini - 3, ini + d + 3)),
                                                              1, 0.6))):
            txt = ""                                            # texto que ela não disse ali: vira punch-in
        if tipo == "destaque" and not txt:
            tipo = "punch_in"
        out.append({"inicio": round(ini, 2), "dur": round(d, 2), "tipo": tipo, "texto": txt})
    return out


def preencher_lacunas(leves, ocupados, words, ini_min, fim_max, lacuna=12.0, s0=0.0):
    """Rosto com tratamento: onde passar muito tempo sem nenhuma variação, entra um punch-in no começo de uma frase.
    Não chama a IA. 'ocupados' = [(a, b)] de B-rolls/cartões; tempos relativos a s0."""
    ws = [dict(w, s=w["s"] - s0, e=w["e"] - s0) for w in words if ini_min <= w["s"] - s0 <= fim_max]
    frs = frases(ws) if ws else []
    inicios = [ws[f["i0"]]["s"] for f in frs]
    # frases de ênfase (pergunta, exclamação, ou depois de uma pausa): é ali que a aproximação faz sentido
    enfase = {ws[f["i0"]]["s"] for k, f in enumerate(frs)
              if re.search(r"[?!]", f["texto"]) or (k > 0 and f["s"] - frs[k - 1]["e"] > 0.5)}
    marcos = sorted([(a, b) for a, b in ocupados] + [(x["inicio"], x["inicio"] + x["dur"]) for x in leves])
    novos, ultimo = [], ini_min
    for a, b in marcos + [(fim_max, fim_max)]:
        while a - ultimo > lacuna:
            alvo = ultimo + (a - ultimo) / 2 if a - ultimo < lacuna * 2 else ultimo + lacuna * 0.8
            cands = [t for t in inicios if ultimo + 2.0 <= t <= a - 3.0]
            if not cands:
                break
            fortes = [t for t in cands if t in enfase and abs(t - alvo) <= lacuna * 0.5]
            t = min(fortes or cands, key=lambda x: abs(x - alvo))
            novos.append({"inicio": round(t, 2), "dur": 2.4, "tipo": "punch_in", "texto": "", "auto": True})
            ultimo = t + 2.4
        ultimo = max(ultimo, b)
    return sorted(leves + novos, key=lambda x: x["inicio"])


def planejar_corte(words, corte, pasta, log=print):
    c = ler_config()
    dur = corte["e"] - corte["s"]
    intervalo = max(5, int(c.get("v2_intervalo_corte", 7)))
    n_max = max(2, round((dur - 6) / intervalo))
    n_min = max(1, round(n_max * 0.7))
    pedido = PEDIDO_CORTE.format(dur=dur, n_max=n_max, n_min=n_min, fim=dur - 3.0,
                                 falas=_falas(words, corte["s"], corte["e"]))
    resp, modelo = ia.pedir(f"brolls_v2_{corte['n']}", SISTEMA, pedido, temperatura=0.6, log=log, forte=True)
    ws = [dict(w, s=w["s"] - corte["s"], e=w["e"] - corte["s"]) for w in words
          if corte["s"] - 0.05 <= w["s"] and w["e"] <= corte["e"] + 0.3]
    fam = familia_visual(pasta, words, log)
    plano = _validar(resp.get("momentos", []), 3.5, dur - 3.0, 1.5, words=ws, familia=fam, log=log)
    _nomear(plano)
    leves = validar_leves(resp.get("leves"), 3.5, dur - 0.5, [(b["inicio"] - 0.3, b["inicio"] + b["dur"] + 0.3) for b in plano],
                          words=ws)
    json.dump(leves, open(os.path.join(pasta, "leves.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if leves:
        log(f"Corte {corte['n']}: {len(leves)} intervenção(ões) leve(s) (punch-in/destaque)")
    log(f"Corte {corte['n']}: IA ({modelo}) escolheu {len(plano)} momento(s) visual(is) — " +
        (", ".join(f"{b['visual']}/{b.get('template') or '-'}" for b in plano) or "só rosto"))
    _salvar(plano, pasta)
    return plano


def planejar_youtube(words, pasta_b, cartoes, log=print, ocupados_extra=()):
    from .insercoes import duracao as dur_cartao
    c = ler_config()
    dur = words[-1]["e"] if words else 0
    por_min = float(c.get("youtube_brolls_por_minuto", 5))
    ocup = [(float(x["tempo"]) - 1.0, float(x["tempo"]) + dur_cartao(x) + 0.8) for x in cartoes or []]
    ocup += list(ocupados_extra)
    janela = 240.0
    partes = max(1, round(dur / janela))
    passo = dur / partes
    todos, leves_brutas = [], []
    for p in range(partes):
        ini, fim = p * passo, (p + 1) * passo
        n_max = max(2, round((fim - ini) / 60 * por_min))
        n_min = max(1, round(n_max * 0.7))
        ocup_txt = ", ".join(f"{a:.0f}-{b:.0f}s" for a, b in ocup if b > ini and a < fim) or "nenhum"
        pedido = PEDIDO_YT.format(ini=ini, fim=fim, n_max=n_max, n_min=n_min, ocupados=ocup_txt,
                                  falas=_falas(words, ini, fim, relativo=False))
        try:
            resp, modelo = ia.pedir(f"youtube_brolls_v2_{p + 1}", SISTEMA, pedido, temperatura=0.6, log=log, forte=True)
        except Exception as e:
            log(f"(YouTube parte {p + 1}: a IA não respondeu ({e}); essa parte fica só com o rosto)")
            continue
        achados = [m for m in resp.get("momentos", []) if isinstance(m, dict)
                   and ini - 1 <= float(m.get("inicio", -99) or -99) < fim]
        todos += achados
        leves_brutas += [m for m in (resp.get("leves") or []) if isinstance(m, dict)]
        log(f"YouTube parte {p + 1}/{partes}: IA ({modelo}) escolheu {len(achados)} momento(s)")
    os.makedirs(pasta_b, exist_ok=True)
    fam = familia_visual(pasta_b, words, log)
    plano = _validar(todos, 3.0, dur - 1.0, 4.0, ocup, words=words, familia=fam, log=log, youtube=True)
    _nomear(plano)
    _salvar(plano, pasta_b)
    ocup_l = ocup + [(b["inicio"] - 1.0, b["inicio"] + b["dur"] + 1.0) for b in plano]
    leves = validar_leves(leves_brutas, 3.0, dur - 1.0, ocup_l, words=words)
    json.dump(leves, open(os.path.join(pasta_b, "leves.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"{len(plano)} momento(s) visual(is) no YouTube — " +
        (", ".join(f"{b['visual']}/{b.get('template') or '-'}" for b in plano) or "só rosto"))
    return plano


def _nomear(plano):
    for k, b in enumerate(plano):
        b["arquivo"] = f"broll_{k + 1}.mp4"


def _salvar(plano, pasta):
    json.dump(plano, open(os.path.join(pasta, "brolls.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ desenho
def _quadro_base(video_base, t, pasta, nome):
    """Um quadro do vídeo dela naquele instante (vira fundo integrado, desfocado)."""
    if not video_base or not os.path.exists(video_base):
        return None
    import subprocess
    from .util import FFMPEG
    arq = os.path.join(pasta, f"_fundo_{nome}.jpg")
    if not os.path.exists(arq):
        subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", f"{max(0.0, t):.2f}", "-i", video_base, "-frames:v", "1",
                        "-vf", "scale=640:-2", arq], **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    return arq if os.path.exists(arq) else None


def para_cena(nome, dados):
    """Estética nova: o editor transforma tela de texto em CENA quando a ideia combina (a IA simples quase não
    escolhe cenas sozinha). Comparação → dois personagens; lista/etapas → escada; causa → pilha; % de pessoas → pessoas."""
    d = dict(dados or {})
    rot = lambda x: (x.get("rotulo") if isinstance(x, dict) else x) or ""
    if nome in ("contraste", "comparacao") and rot(d.get("a")) and rot(d.get("b")):
        return "duelo", {"a": {"rotulo": rot(d["a"])}, "b": {"rotulo": rot(d["b"])}, "frase": d.get("titulo") or ""}
    if nome in ("lista", "processo"):
        itens = [str(i) for i in (d.get("itens") or d.get("passos") or []) if i][:3]
        if len(itens) >= 2:
            return "escada", {"passos": itens, "meta": d.get("titulo") or ""}
    if nome == "causa_efeito" and d.get("causa") and d.get("efeito"):
        return "pilha", {"b": {"rotulo": d["causa"]}, "resultado": d["efeito"]}
    if nome == "transformacao" and d.get("de") and d.get("para"):
        return "caminho", {"texto": d["de"], "meta": d["para"]}
    if nome == "dado" and "%" in str(d.get("numero", "")) and \
            re.search(r"pessoa|gente|popula|jove|brasileir|mulher|homen|criança", _norm(d.get("rotulo", ""))):
        return "pessoas", {"itens": [{"numero": d["numero"], "texto": d.get("rotulo", "")}]}
    return nome, d


# ------------------------------------------------------------------ variedade das cenas (o editor controla)
# Cada TIPO de ideia tem várias formas visuais; o editor escolhe uma que ainda não apareceu por perto.
OPCOES = {
    "comparacao": ["duelo", "balanca", "caminhos", "contraste"],
    "progressao": ["escada", "plataformas", "sequencia", "pilha"],
    "causa": ["domino", "fluxo", "pilha", "caminho"],
    "origem": ["chegada", "fluxo", "caminho"],
    "quantidade": ["pontos", "anel", "pessoas", "dado"],
}
_PARECIDO = re.compile(r"\b(mesm[ao]s?|igua(l|is)|parecid|similar|semelhan|identic|a mesma coisa)", re.I)
_ORIGEM = re.compile(r"\b(ceu|estrel|planet|espaco|de fora|vieram|vindo|desce|chegar|alien|extraterr|outro mundo|"
                     r"sinal|transmi|cosm|anunn)", re.I)


def _ideia(b):
    """(categoria, conteúdo) de um momento já validado; None se não for uma ideia que tenha várias formas."""
    nome, d = b.get("template"), b.get("dados") or {}
    rot = lambda x: str((x.get("rotulo") if isinstance(x, dict) else x) or "").strip()
    texto_frase = _norm(" ".join([b.get("frase", ""), b.get("ideia", ""), b.get("titulo", "")]))
    if nome in ("contraste", "comparacao", "duelo", "balanca", "caminhos") and rot(d.get("a")) and rot(d.get("b")):
        return "comparacao", {"a": rot(d["a"]), "b": rot(d["b"]), "titulo": d.get("titulo") or d.get("frase") or ""}
    if nome in ("lista", "processo", "escada", "plataformas", "sequencia"):
        itens = [str(i) for i in (d.get("itens") or d.get("passos") or []) if i]
        if len(itens) >= 2 or (itens and d.get("meta")):
            return "progressao", {"passos": itens[:3], "meta": d.get("meta") or d.get("titulo") or ""}
    if nome in ("causa_efeito", "transformacao", "domino", "fluxo"):
        c, e = d.get("causa") or d.get("de"), d.get("efeito") or d.get("para")
        if c and e:
            return "causa", {"causa": str(c), "efeito": str(e)}
    if nome in ("dado", "pessoas", "pontos", "anel"):
        it = (d.get("itens") or [{}])[0] if nome == "pessoas" else d
        num, txt = str(it.get("numero", "")), it.get("texto") or it.get("rotulo") or ""
        if re.search(r"\d\s*%", num):
            return "quantidade", {"numero": num, "texto": txt}
    if nome in ("palavra_chave", "citacao", "caminho", "chegada") and _ORIGEM.search(texto_frase):
        txt = d.get("texto") or d.get("frase") or b.get("titulo") or ""
        if txt:
            return "origem", {"texto": txt, "rotulo": b.get("titulo") if b.get("titulo") != txt else ""}
    return None, None


def _montar(cena, cat, c):
    """Dados da cena escolhida a partir do conteúdo (só textos já validados contra a fala)."""
    if cat == "comparacao":
        if cena == "contraste":
            return {"a": {"rotulo": c["a"]}, "b": {"rotulo": c["b"]}, "titulo": c["titulo"]}
        return {"a": {"rotulo": c["a"]}, "b": {"rotulo": c["b"]}, "frase": c["titulo"] if cena != "caminhos" else ""}
    if cat == "progressao":
        if cena == "pilha":
            return {"b": {"rotulo": c["passos"][0] if c["passos"] else ""}, "resultado": c["meta"] or (c["passos"] or [""])[-1]}
        return {"passos": c["passos"], "meta": c["meta"]}
    if cat == "causa":
        if cena == "pilha":
            return {"b": {"rotulo": c["causa"]}, "resultado": c["efeito"]}
        if cena == "caminho":
            return {"texto": c["causa"], "meta": c["efeito"]}
        return {"causa": c["causa"], "efeito": c["efeito"]}
    if cat == "origem":
        if cena == "fluxo":
            return {"causa": c["rotulo"] or "", "efeito": c["texto"]} if c["rotulo"] else None
        if cena == "caminho":
            return {"texto": c["texto"], "meta": c["rotulo"]}
        return {"texto": c["texto"], "rotulo": c["rotulo"]}
    if cat == "quantidade":
        if cena == "pessoas":
            return {"itens": [{"numero": c["numero"], "texto": c["texto"]}]}
        if cena == "dado":
            return {"numero": c["numero"], "rotulo": c["texto"]}
        return {"numero": c["numero"], "texto": c["texto"]}
    return None


CENAS_BONECO = {"duelo", "energia", "escada", "alvos", "caminho", "pilha", "barras", "pessoas", "relogio", "plataformas",
                "sequencia", "balanca", "caminhos", "domino", "fluxo", "chegada", "pontos", "anel"}
SO_TEXTO = {"palavra_chave", "citacao", "conceito", "foco"}


VIDEO_USADAS = {}          # cenas já usadas neste vídeo (zera no começo de cada projeto: pipeline.processar)
MAX_CENAS = 2              # no máximo 2 cenas de bonecos por corte; o resto é foto/vídeo real, cartão ou rosto


def _buscas_ok(b):
    return any(isinstance(q, str) and len(q.split()) >= 3 for q in (b.get("buscas") or []))


def diversificar(plano, log=print, max_texto=0.2, youtube=False):
    """Não repete a mesma cena no mesmo corte/trecho, nem a mesma estrutura em momentos vizinhos; a escada é
    uma possibilidade entre várias. Texto puro vira exceção: o excesso de telas só de palavras sai (fica o rosto)."""
    # YouTube: memória própria (não rouba cenas dos cortes); ~1 cena de boneco a cada 3 momentos, nunca repetida
    memoria = {} if youtube else VIDEO_USADAS
    max_cenas = max(3, len(plano) // 3) if youtube else MAX_CENAS
    usadas, recentes, trocas, repetidas = dict(memoria), [], 0, 0
    cenas_aqui = 0
    for b in plano:
        if not b.get("template") or b.get("visual") not in ("animacao_editorial", "grafico_dado_mapa"):
            if b.get("template"):
                recentes.append(b["template"])
            continue
        cat, conteudo = _ideia(b)
        if not cat:
            recentes.append(b["template"])
            continue
        if cat == "comparacao" and _PARECIDO.search(_norm(" ".join([b.get("frase", ""), b.get("ideia", "")]))):
            b["_sai"] = True          # ela diz que as coisas são IGUAIS/parecidas: cena de "um ganha do outro" contradiz
            repetidas += 1
            continue
        opcoes = list(OPCOES[cat])
        if b["template"] in opcoes and b["template"] not in ("contraste", "dado"):   # cena escolhida pela IA vem primeiro
            opcoes.remove(b["template"])
            opcoes.insert(0, b["template"])
        livres = [o for o in opcoes if usadas.get(o, 0) == 0 and o not in recentes[-2:]]
        quase = [o for o in opcoes if o not in recentes[-6:]]
        escolha = None
        for o in dict.fromkeys(livres + quase):          # tenta todas as opções sem repetir antes de desistir
            dados = _montar(o, cat, conteudo)
            if dados:
                escolha = (o, dados)
                break
        if not escolha and b["template"] in CENAS_BONECO and b["template"] in recentes[-6:]:
            b["_sai"] = True                              # mesma cena de novo logo em seguida: sai (fica o rosto)
            repetidas += 1
            continue
        if escolha and escolha[0] != b["template"]:
            trocas += 1
        if escolha:
            b["template"], b["dados"] = escolha
        usadas[b["template"]] = usadas.get(b["template"], 0) + 1
        recentes.append(b["template"])
    # cena de boneco: no máximo MAX_CENAS por corte e nunca a mesma de outro corte do vídeo (nem 2x no mesmo)
    vistas = set(memoria)
    for b in plano:
        t = b.get("template")
        if b.get("_sai") or t not in CENAS_BONECO or b.get("visual") not in ("animacao_editorial", "grafico_dado_mapa"):
            continue
        if cenas_aqui < max_cenas and t not in vistas:
            cenas_aqui += 1
            vistas.add(t)
            memoria[t] = memoria.get(t, 0) + 1
            continue
        if _buscas_ok(b):                      # vira foto/vídeo real da mesma ideia (se não achar bom, fica o rosto)
            b["visual"], b["template"] = "video_real", None
            trocas += 1
        else:
            b["_sai"] = True
            repetidas += 1
    if repetidas:
        plano[:] = [b for b in plano if not b.pop("_sai", False)]
        log(f"({repetidas} cena(s) repetida(s) ou que contradiziam a fala saíram: fica o rosto)")
    # texto não é a solução padrão: no máximo ~20% das animações podem ser só palavras
    anim = [b for b in plano if b.get("template") and b.get("visual") in ("animacao_editorial", "grafico_dado_mapa")]
    so_texto = [b for b in anim if b["template"] in ("palavra_chave", "citacao")]
    limite = max(1, int(len(anim) * max_texto))
    tirar = set(id(b) for b in so_texto[limite:])
    if tirar:
        plano[:] = [b for b in plano if id(b) not in tirar]
        log(f"({len(tirar)} tela(s) só de texto saíram: no lugar fica o rosto com movimento)")
    if trocas:
        log(f"Variedade: {trocas} cena(s) trocada(s) para não repetir a mesma forma visual")
    return plano


def _template(b, pasta, log, seed=0, W=1080, H=1920, video_base=None):
    nome = b.get("template")
    if not nome:
        return None
    dados = dict(b.get("dados") or {})

    fundo_img = _quadro_base(video_base, float(b["inicio"]) + 0.5, pasta, b["arquivo"]) if W > H else None
    # templates sempre na resolução de projeto (1920x1080 ou 1080x1920); o vídeo final redimensiona
    lw, lh = (1920, 1080) if W > H else (1080, 1920)
    usado = templates.render(nome, dados, float(b["dur"]), os.path.join(pasta, b["arquivo"]),
                             tema=b.get("estilo", "escuro"), seed=seed, largura=lw, altura=lh, fundo_img=fundo_img)
    if usado:
        log(f"B-roll {b['arquivo']}: {b['visual']} → template {usado} ({b.get('estilo')}) — {b.get('ideia', '')[:70]}")
    return usado


def desenhar(plano, pasta, log=print, so=None, W=1080, H=1920, video_base=None):
    """Desenha os momentos (todos ou os índices em 'so'). Itens sem resultado bom são TIRADOS (fica o rosto).
    Mexe na própria lista 'plano' (quem chamou vê o resultado)."""
    alvo = [k for k in range(len(plano)) if so is None or k == so or (isinstance(so, (list, set, tuple)) and k in so)]
    deitado = W > H
    # 1) banco (vídeo/foto): reaproveita escolha salva; senão busca e a IA avalia todos de uma vez
    pend = []
    for k in alvo:
        b = plano[k]
        if b["visual"] not in ("video_real", "foto_documento_print") or b.get("so_template"):
            continue
        esc = b.get("stock")
        if esc:                          # escolha já feita antes: não pergunta de novo à IA
            try:
                _aplicar_stock(b, esc, pasta, W, H, log)
                continue
            except Exception as e:
                log(f"(não deu para refazer o {b['arquivo']} com a escolha salva: {e})")
                b.pop("stock", None)
        try:
            cands = (videos_reais.candidatos(b, deitado) if b["visual"] == "video_real"
                     else videos_reais.candidatos_foto(b))
        except Exception:
            cands = []
        if cands:
            pend.append((k, cands))
        else:
            log(f"({b['arquivo']}: nenhuma opção de banco para \"{b.get('titulo')}\")")
    if pend:
        for i in range(0, len(pend), 8):
            lote = pend[i:i + 8]
            itens = [(plano[k].get("frase", ""), plano[k].get("ideia", ""), cands,
                      deitado if plano[k]["visual"] == "video_real" else True) for k, cands in lote]
            esc = videos_reais.escolher_v2(itens, log)
            for j, (k, cands) in enumerate(lote):
                b = plano[k]
                if j not in esc:
                    continue
                cand, nota = esc[j]
                if str(cand.get("site", "")).startswith("Wiki") and nota < 5:
                    log(f"({b['arquivo']}: documento do Wikimedia só entra se for exato (nota {nota:g}) — não entra)")
                    continue
                try:
                    b["stock"] = dict(cand, nota=nota)
                    _aplicar_stock(b, b["stock"], pasta, W, H, log)
                except Exception as e:
                    log(f"({b['arquivo']}: não deu para baixar/montar: {e})")
                    b.pop("stock", None)
    # 2) o resto vira template (plano B) ou sai
    tirar = []
    nova = ler_config().get("estetica", "nova") == "nova"
    def _eh_texto(x):
        return (x.get("template_usado") or (x.get("template") if not x.get("stock") else None)) in SO_TEXTO
    teto = max(1, int(len(plano) * 0.2))
    for k in alvo:
        b = plano[k]
        if b.get("stock") and os.path.exists(os.path.join(pasta, b["arquivo"])):
            continue
        if nova and b["visual"] in ("video_real", "foto_documento_print") and b.get("template") in SO_TEXTO:
            ja = sum(1 for j, x in enumerate(plano) if j != k and j not in tirar and _eh_texto(x))
            vizinho = any(_eh_texto(plano[j]) for j in (k - 1, k + 1) if 0 <= j < len(plano) and j not in tirar)
            if ja >= teto or vizinho:
                tirar.append(k)
                log(f"({b['arquivo']}: não achou foto/vídeo bom; não vira mais uma tela de texto — fica o rosto)")
                continue
        b.pop("fonte", None)
        b.pop("credito", None)
        b.pop("stock", None)
        try:
            usado = _template(b, pasta, log, seed=k, W=W, H=H, video_base=video_base)
        except Exception as e:
            log(f"({b['arquivo']}: template falhou: {e})")
            usado = None
        if usado:
            b["visual_final"] = "template"
            b["template_usado"] = usado
            b.pop("erro", None)
        else:
            tirar.append(k)
            log(f"({b['arquivo']}: sem imagem boa o bastante — fica o rosto)")
    if tirar:
        plano[:] = [b for k, b in enumerate(plano) if k not in tirar]
    _salvar(plano, pasta)
    return plano


def _num(arquivo):
    m = re.search(r"(\d+)", str(arquivo))
    return int(m.group(1)) if m else 0


def _aplicar_stock(b, cand, pasta, W, H, log):
    saida = os.path.join(pasta, b["arquivo"])
    if b["visual"] == "video_real" and cand.get("tipo") != "foto":
        videos_reais.render(cand, b.get("titulo", ""), float(b["dur"]), saida, pasta, W, H,
                            estilo=b.get("estilo"), seed=_num(b["arquivo"]))
        b["fonte"] = cand.get("site", "Pixabay").lower()
        b["visual_final"] = "video_real"
    else:
        foto = videos_reais.baixar_foto(cand, pasta)
        dados = dict(b.get("dados") if b["visual"] != "video_real" else {}, imagem=foto,
                     credito=f"{cand.get('autor', '')} · {cand.get('licenca', '')} · {cand.get('site', '')}")
        if b["visual"] == "video_real":            # foto de banco no lugar do vídeo: legenda = título, sem marcação
            dados.update(legenda=b.get("titulo", ""), marcacao="nenhuma")
        if not dados.get("legenda"):
            dados["legenda"] = b.get("titulo", "")
        usado = templates.render("documento", dados, float(b["dur"]), saida, tema=b.get("estilo", "papel"), seed=_num(b["arquivo"]),
                                 largura=1920 if W > H else 1080, altura=1080 if W > H else 1920)
        if usado != "documento":
            raise RuntimeError("foto não abriu")
        b["fonte"] = "wikimedia" if cand.get("site", "").startswith("Wiki") else "pixabay_foto"
        b["visual_final"] = "foto_banco" if b["visual"] == "video_real" else "foto_documento_print"
    b["credito"] = f"{cand.get('autor', '')} ({cand.get('site', '')}{', ' + cand['licenca'] if cand.get('licenca') else ''}) — {cand.get('url', '')}"
    log(f"B-roll {b['arquivo']}: {b['visual_final']} de {cand.get('autor', '')} ({cand.get('site')}, nota {cand.get('nota', '?')})")


def refazer(words, corte, pasta, k, pedido_extra="", log=print):
    """Botão Refazer: pede outra solução editorial (template) para o momento k."""
    plano = json.load(open(os.path.join(pasta, "brolls.json"), encoding="utf-8"))
    b = plano[k]
    antes = f"{b.get('visual_final') or b.get('visual')}/{b.get('template_usado') or b.get('template')}"
    extra = f"Pedido da Natinha: {pedido_extra}" if pedido_extra else ""
    resp, modelo = ia.pedir(f"refazer_v2_{corte['n']}_{k}", SISTEMA,
                            REFAZER.format(frase=b.get("frase", ""), ideia=b.get("ideia", ""), antes=antes, extra=extra),
                            temperatura=0.9, log=log, forte=True)
    tpl = resp.get("template") if resp.get("template") in templates.TEMPLATES else "palavra_chave"
    b.update(visual=resp.get("visual") if resp.get("visual") in VISUAIS else "animacao_editorial",
             template=tpl, dados=resp.get("dados") if isinstance(resp.get("dados"), dict) else {},
             estilo=b.get("estilo") or _estilo_da_familia(familia_visual(pasta), k),
             ideia=resp.get("ideia") or b.get("ideia", ""), so_template=True)
    if b["visual"] not in ("grafico_dado_mapa", "animacao_editorial"):
        b["visual"] = "animacao_editorial"
    b["versao"] = b.get("versao", 1) + 1
    b["arquivo"] = f"broll_{k + 1}_v{b['versao']}.mp4"
    desenhar(plano, pasta, log, so=k)
    return plano
