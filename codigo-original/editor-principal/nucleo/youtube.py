"""Versão YouTube: corta silêncios e trechos ruins (erros, repetições) apontados pela IA."""
import json, os, re
from .util import FFMPEG, run, probe, tmpdir, ler_config, opcao_filtro_arquivo
from .transcrever import frases
from . import ia

PROMPT_LIMPEZA = """Você é editora de vídeo do canal da Natinha (YouTube, falas em português).
Recebe a transcrição de um vídeo BRUTO dividida em frases numeradas, com tempos.
Marque o que deve SAIR da versão final:
- tentativas repetidas da mesma fala (mantenha só a ÚLTIMA versão completa)
- frases interrompidas/começos falsos, gaguejadas longas, "corta", "de novo", "pera", testes de áudio
- conversa fora do conteúdo (falando com alguém fora da câmera, bastidores)
NÃO remova conteúdo bom só para encurtar. Na dúvida, mantenha.
NOS PRIMEIROS 40 SEGUNDOS seja RIGOROSA (é o trecho que decide se a pessoa fica): tire hesitação, "então, então",
"desculpa", "tipo assim", repetição, começo de frase quebrado e frase cortada pela metade.

GANCHO: escolha a frase MAIS FORTE do vídeo para abrir (afirmação surpreendente, pergunta provocadora ou promessa),
de no máximo 12 segundos, que faça sentido sozinha. Ela vai aparecer como prévia antes do começo.
Se a 1ª frase do vídeo já for o melhor gancho, "gancho" = null.
DESPEDIDA: se no fim ela se despede de forma genérica ("espero que tenham gostado", "é isso", "tchau", "até o próximo",
"beijo"), dê o número da frase onde a despedida começa (ela sai do vídeo). Chamada para outro vídeo/ação NÃO é despedida.
TÍTULOS: 3 opções diferentes para teste A/B (curiosidade + promessa clara, sem mentir, até 60 caracteres, no máximo
1 palavra em CAIXA ALTA). CAPAS: 3 textos para a capa (2 a 4 palavras de impacto, NÃO repetir o título), e para cada
um a palavra que vai em destaque.
Também sugira descrição curta e capítulos.
TEMA VISUAL: a família visual das animações do vídeo inteiro, UMA entre "tech" (tecnologia, sistema, internet;
preto + verde/ciano), "documental" (história, ciência, fatos; grafite + bege/dourado), "psicologico" (mente,
comportamento, emoções; preto + branco + azul/ciano), "alerta" (polêmica, manipulação, denúncia; preto + branco +
vermelho), "espiritual" (energia, consciência, simbólico; preto + dourado + violeta).

Responda em JSON:
{"remover": [{"de": n, "ate": n, "motivo": "..."}], "gancho": n ou null, "despedida": n ou null,
 "titulo": "o melhor dos 3", "titulos": ["...", "...", "..."],
 "capas": [{"texto": "2 a 4 palavras", "destaque": "palavra"}],
 "descricao": "2-3 frases", "capitulos": [{"frase": n, "titulo": "..."}], "tema_visual": "tech|documental|psicologico|alerta|espiritual"}"""


def silencios(video, db, minimo):
    r = run([FFMPEG, "-i", video, "-af", f"silencedetect=noise={db}dB:d={minimo}", "-f", "null", "-"])
    out, st = [], None
    for ln in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", ln)
        if m:
            st = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", ln)
        if m and st is not None:
            out.append((st, float(m.group(1))))
            st = None
    return out


def manter(dur, remover):
    rem = sorted((max(0.0, s), min(dur, e)) for s, e in remover if e > s)
    keep, cur = [], 0.0
    for s, e in rem:
        if s > cur:
            keep.append((cur, s))
        cur = max(cur, e)
    if cur < dur:
        keep.append((cur, dur))
    return [(round(s, 3), round(e, 3)) for s, e in keep if e - s > 0.15]


def proteger_palavras(remover, words, cortados_ia=(), margem=0.04):
    """Nenhuma emenda cai no MEIO de uma palavra que fica no vídeo (era a causa dos 'engasgos': o detector de
    silêncio cortava sílabas faladas baixinho). Tira de cada trecho a remover o tempo das palavras que ficam."""
    ficam = [(w["s"] - margem, w["e"] + margem) for w in words
             if not any(a <= (w["s"] + w["e"]) / 2 <= b for a, b in cortados_ia)]
    out = []
    for a, b in remover:
        partes = [(a, b)]
        for ws, we in ficam:
            if we <= a or ws >= b:
                continue
            novas = []
            for x, y in partes:
                if we <= x or ws >= y:
                    novas.append((x, y))
                    continue
                if ws > x:
                    novas.append((x, ws))
                if we < y:
                    novas.append((we, y))
            partes = novas
        out += [(x, y) for x, y in partes if y - x > 0.12]
    return out


_ENFASE = {"não", "nao", "muito", "nunca", "sim", "bem", "tá", "ta", "né", "ne", "já", "ja", "mais", "tudo", "vai", "olha"}


def palavras_repetidas(words, cortados_ia=()):
    """A mesma palavra dita 2x seguidas (gaguejo) → tira a 1ª. Repetição de ênfase ("não, não", "muito muito") fica."""
    import re as _re
    norm = lambda w: _re.sub(r"[^\wà-ú]", "", str(w.get("w", "")).lower())
    out = []
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        p = norm(a)
        if len(p) < 2 or p in _ENFASE or p != norm(b):
            continue
        if str(a.get("w", "")).rstrip().endswith((",", ".", "!", "?", "…")):      # pausa de fala: pode ser ênfase
            continue
        if p == "para" and i + 2 < len(words) and _re.search(r"[aei]r$", norm(words[i + 2])):
            continue                                   # "para para pensar" = parar para pensar (não é gaguejo)
        if b["s"] - a["e"] > 0.8 or any(x <= (a["s"] + a["e"]) / 2 <= y for x, y in cortados_ia):
            continue
        out.append((a["s"] - 0.03, b["s"] - 0.02))
    return out


def sem_pedacinhos(keep, words, cortados_ia=(), minimo=0.5):
    """Pedacinho que sobrou entre dois cortes, curto e sem nenhuma palavra inteira, sai (era o 'blip')."""
    ficam = [w for w in words if not any(a <= (w["s"] + w["e"]) / 2 <= b for a, b in cortados_ia)]
    out = []
    for s, e in keep:
        if e - s < minimo and not any(s - 0.02 <= w["s"] and w["e"] <= e + 0.02 for w in ficam):
            continue
        out.append((s, e))
    return out


def remapear(words, keep, cortados=()):
    offs, o = [], 0.0
    for s, e in keep:
        offs.append(o)
        o += e - s

    def f(t):
        for (s, e), oo in zip(keep, offs):
            if t < s:
                return oo
            if t <= e:
                return oo + t - s
        return o

    out = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        if any(a <= mid <= b for a, b in cortados):
            continue  # palavra de um trecho que a IA mandou tirar (os silêncios não apagam palavras)
        s, e = f(w["s"]), f(w["e"])
        if e - s < 0.1:
            e = s + 0.1
        if out and s < out[-1]["e"]:
            s = out[-1]["e"]
            e = max(e, s + 0.1)
        out.append({"w": w["w"], "s": round(s, 2), "e": round(e, 2)})
    return out


def ts_srt(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def srt(words, path, maxw=8):
    out, chunk, n = [], [], 1
    for i, w in enumerate(words):
        chunk.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if len(chunk) >= maxw or not nxt or nxt["s"] - w["e"] > 0.6 or re.search(r"[.!?…]$", w["w"]):
            out.append(f"{n}\n{ts_srt(chunk[0]['s'])} --> {ts_srt(chunk[-1]['e'])}\n{' '.join(c['w'] for c in chunk)}\n")
            chunk, n = [], n + 1
    open(path, "w", encoding="utf-8").write("\n".join(out))


GIRO = {90: "transpose=1,", -90: "transpose=2,", 180: "hflip,vflip,", 0: ""}


def renderizar(bruto, keep, saida, info, preset="medium", girar=0):
    """Um passo só (select/aselect), sem guardar tudo na memória — serve para vídeos longos."""
    expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)
    td = tmpdir()
    fc = os.path.join(td, "fc.txt")
    # fps=30 antes de cortar: vídeos de celular/WhatsApp têm quadros irregulares; sem isso a imagem se atrasa em relação ao som
    v = f"[0:v]{GIRO.get(int(girar), '')}fps=30,select='{expr}',setpts=N/30/TB[v]"
    a = (f"[0:a]aselect='{expr}',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,"
         f"aformat=sample_fmts=fltp:channel_layouts=stereo[a]")
    open(fc, "w").write(v + ";" + a if info["audio"] else v)
    cmd = [FFMPEG, "-y", "-i", bruto, opcao_filtro_arquivo(), fc, "-map", "[v]"]
    if info["audio"]:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    parcial = saida + ".parcial.mp4"
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", parcial]
    run(cmd)
    os.replace(parcial, saida)


def _tela_final(video, seg, saida, info_v, preset="medium"):
    """Tela final (para os elementos de 'assista o próximo' do YouTube): último quadro desfocado + texto."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    from .util import FONTES
    td = tmpdir()
    q = os.path.join(td, "ultimo.png")
    run([FFMPEG, "-y", "-v", "error", "-sseof", "-0.5", "-i", video, "-frames:v", "1", q])
    W, H = info_v["w"], info_v["h"]
    im = Image.open(q).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(max(8, W // 60)))
    escuro = Image.new("RGB", (W, H), (24, 12, 44))
    im = Image.blend(im, escuro, 0.55)
    d = ImageDraw.Draw(im)
    F = lambda t: ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), int(t))
    f1 = F(H * 0.095)
    t1 = "ASSISTA O PRÓXIMO"
    d.text(((W - f1.getlength(t1)) / 2, H * 0.12), t1, font=f1, fill=(246, 238, 227), stroke_width=max(2, H // 270),
           stroke_fill=(15, 10, 25))
    # lugares dos elementos da tela final (vídeo à esquerda, inscrever-se à direita)
    vw, vh = W * 0.40, W * 0.40 * 9 / 16
    vx, vy = W * 0.10, H * 0.36
    d.rounded_rectangle([vx, vy, vx + vw, vy + vh], radius=int(H * 0.02), outline=(240, 200, 90), width=max(3, H // 200))
    r = H * 0.13
    cx, cy = W * 0.73, vy + vh / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(240, 200, 90), width=max(3, H // 200))
    png = os.path.join(td, "final.png")
    im.save(png)
    parcial = saida + ".parcial.mp4"
    run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", f"{seg:.2f}", "-i", png,
         "-f", "lavfi", "-t", f"{seg:.2f}", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", "fade=t=in:st=0:d=0.4,format=yuv420p", "-c:v", "libx264", "-preset", preset, "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", parcial])
    os.replace(parcial, saida)


def _juntar(partes, saida):
    td = tmpdir()
    lista = os.path.join(td, "lista.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for p in partes:
            f.write("file '" + p.replace("\\", "/").replace("'", "'\\''") + "'\n")
    parcial = saida + ".parcial.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", "-movflags", "+faststart",
         parcial])
    os.replace(parcial, saida)


DESPEDIDA = re.compile(r"(espero que (voc[eê]s?|tenha|tenham)|é isso|tchau|beij(o|ão)|até (o|a) pr[oó]xim|"
                       r"at[eé] mais|curte,? compartilh|me sig[am]|deixa (seu|o) like|se inscrev|"
                       r"fico muito feliz de|um prazer conversar)", re.I)


def versao_youtube(bruto, words, pasta, log=print, girar=0, vertical=False):
    """vertical=True (vídeo da 'entrada_vertical'): mesma limpeza de erros e silêncios, mas sem prévia (gancho)
    na abertura e sem tela final — o resultado é a base limpa para as partes verticais."""
    c = ler_config()
    info = probe(bruto)
    fr = frases(words)
    # 1) IA aponta erros e repetições
    remover = []
    cortados_ia = []
    meta = {}
    try:
        texto = "\n".join(f"[{k}] ({f['s']:.1f}-{f['e']:.1f}s) {f['texto']}" for k, f in enumerate(fr))
        cache = os.path.join(pasta, "ia_limpeza.json")
        if os.path.exists(cache):          # já respondida antes: não pergunta de novo
            resp, modelo = json.load(open(cache, encoding="utf-8")), "salvo"
        else:
            resp, modelo = ia.pedir("limpeza", PROMPT_LIMPEZA, texto, temperatura=0.3, log=log)
            json.dump(resp, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
        log(f"IA ({modelo}) marcou {len(resp.get('remover', []))} trecho(s) para tirar")
        for r in resp.get("remover", []):
            a, b = int(r["de"]), int(r.get("ate", r["de"]))
            if 0 <= a <= b < len(fr):
                remover.append((fr[a]["s"] - 0.05, fr[b]["e"] + 0.12))
                cortados_ia.append((fr[a]["s"] - 0.05, fr[b]["e"] + 0.12))
        meta = {k: resp.get(k) for k in ("titulo", "descricao", "capitulos", "titulos", "capas", "gancho", "despedida",
                                     "tema_visual")}
        # despedida genérica no fim sai (só se estiver mesmo no fim e for curta)
        dsp = resp.get("despedida")
        if not isinstance(dsp, int):              # a IA não marcou: procura a despedida nas últimas frases
            k = len(fr) - 1
            while k > 0 and fr[-1]["e"] - fr[k]["s"] <= 40 and DESPEDIDA.search(fr[k]["texto"]):
                k -= 1
            dsp = k + 1 if k + 1 < len(fr) else None
        if isinstance(dsp, int) and 0 < dsp < len(fr) and fr[-1]["e"] - fr[dsp]["s"] <= 40 \
                and any(DESPEDIDA.search(f["texto"]) for f in fr[dsp:]):
            remover.append((fr[dsp]["s"] - 0.05, info["dur"]))
            cortados_ia.append((fr[dsp]["s"] - 0.05, info["dur"]))
            log(f"Despedida genérica do fim sai: \"{fr[dsp]['texto'][:60]}…\"")
    except ia.ErroIA as e:
        log(f"Sem IA para limpeza ({e}); só os silêncios serão cortados.")
    # 1b) palavra repetida colada ("porque porque", "que que"): sai a primeira, sem IA
    dup = palavras_repetidas(words, cortados_ia)
    if dup:
        remover += dup
        cortados_ia += dup
        log(f"{len(dup)} palavra(s) repetida(s) sem querer saíram (ex.: \"porque porque\")")
    # 2) silêncios
    sil = silencios(bruto, c["silencio_db"], c["silencio_min"])
    folga = float(c.get("silencio_folga", 0.25))   # respiro mantido antes e depois de cada fala
    remover += [(s + folga, e - folga) for s, e in sil if e - s > c["silencio_min"] and e - s - 2 * folga > 0.3]
    remover = proteger_palavras(remover, words, cortados_ia)
    keep = manter(info["dur"], remover)
    keep = sem_pedacinhos(keep, words, cortados_ia)
    novos = remapear(words, keep, cortados_ia)
    dur_final = sum(e - s for s, e in keep)
    log(f"Versão YouTube: {info['dur'] / 60:.1f} min → {dur_final / 60:.1f} min ({len(keep)} trechos)")
    # gancho: a frase mais forte aparece antes, como prévia (só se não for já a 1ª frase e couber em 12 s)
    teaser = None
    g = meta.get("gancho")
    if not vertical and c.get("youtube_gancho", True) and isinstance(g, int) and 0 < g < len(fr) and fr[g]["s"] > 8:
        ts_, te_ = fr[g]["s"] - 0.08, fr[g]["e"] + 0.3
        if 1.5 <= te_ - ts_ <= 12.5 and not any(a <= (ts_ + te_) / 2 <= b for a, b in cortados_ia):
            teaser = (round(ts_, 3), round(te_, 3))
            log(f"Gancho na abertura: \"{fr[g]['texto'][:80]}\"")
    extra = {"teaser": 0.0, "fim_conteudo": dur_final}
    if teaser:
        d_t = teaser[1] - teaser[0]
        ws_t = [{"w": w["w"], "s": round(w["s"] - teaser[0], 2), "e": round(w["e"] - teaser[0], 2)}
                for w in words if w["s"] >= teaser[0] and w["e"] <= teaser[1] + 0.05]
        novos = ws_t + [dict(w, s=round(w["s"] + d_t, 2), e=round(w["e"] + d_t, 2)) for w in novos]
        extra = {"teaser": round(d_t, 3), "fim_conteudo": round(dur_final + d_t, 3)}
    trechos = ([list(teaser)] if teaser else []) + [list(k) for k in keep]
    json.dump(trechos, open(os.path.join(pasta, "youtube_trechos.json"), "w"))
    json.dump(novos, open(os.path.join(pasta, "youtube_palavras.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    srt(novos, os.path.join(pasta, "youtube.srt"))
    # 3) título/descrição/capítulos
    if meta.get("titulo"):
        linhas = [meta["titulo"], "", meta.get("descricao") or "", ""]
        caps = []
        for cp in meta.get("capitulos") or []:
            try:
                alvo = words[fr[int(cp["frase"])]["i0"]]["s"]       # tempo no bruto
                t = remapear([{"w": "x", "s": alvo, "e": alvo + 0.2}], keep)
                caps.append(((t[0]["s"] + extra["teaser"]) if t else 0.0, cp["titulo"]))
            except Exception:
                pass
        if caps:
            caps.sort()
            caps[0] = (0.0, caps[0][1])
            linhas.append("Capítulos:")
            for t, tt in caps:
                linhas.append(f"{int(t // 60):02}:{int(t % 60):02} {tt}")
        tits = [t for t in (meta.get("titulos") or []) if isinstance(t, str) and t.strip()]
        if tits:
            linhas += ["", "Opções de título para testar (YouTube Studio > Test & Compare):"] + [f"{i + 1}. {t}" for i, t in enumerate(tits[:3])]
        open(os.path.join(pasta, "youtube_info.txt"), "w", encoding="utf-8").write("\n".join(linhas))
        json.dump({"titulos": tits[:3], "capas": (meta.get("capas") or [])[:3], "titulo": meta["titulo"],
                   "tema_visual": meta.get("tema_visual") or ""},
                  open(os.path.join(pasta, "youtube_meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    saida = os.path.join(pasta, "youtube.mp4")
    seg_final = 0.0 if vertical else float(c.get("tela_final_seg", 15))
    if not teaser and seg_final <= 0:
        renderizar(bruto, keep, saida, info, c["preset"], girar)
    else:
        corpo = os.path.join(pasta, "_yt_corpo.mp4")
        renderizar(bruto, keep, corpo, info, c["preset"], girar)
        partes = []
        if teaser:
            f_t = os.path.join(pasta, "_yt_gancho.mp4")
            renderizar(bruto, [teaser], f_t, info, c["preset"], girar)
            partes.append(f_t)
        partes.append(corpo)
        if seg_final > 0:
            f_f = os.path.join(pasta, "_yt_final.mp4")
            _tela_final(corpo, seg_final, f_f, probe(corpo), c["preset"])
            partes.append(f_f)
            log(f"Tela final de {seg_final:.0f} s no fim (coloque os elementos 'próximo vídeo' e 'inscrever-se' nela)")
        _juntar(partes, saida)
        for p_ in partes:
            try:
                os.remove(p_)
            except OSError:
                pass
    json.dump(extra, open(os.path.join(pasta, "youtube_extra.json"), "w"))
    return keep, novos
