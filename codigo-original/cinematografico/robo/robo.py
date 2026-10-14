"""ROBÔ EDITOR NATINHA v2 (Remotion) — vídeo bruto -> até 3 produtos, para APROVAÇÃO (nada é publicado):
  yt        YouTube 16:9 limpo (sem silêncios/tomadas erradas, punch-ins, sem B-roll) + .srt
  yt_broll  YouTube 16:9 com B-roll real e animações (mesma edição) + .srt
  cortes    1 a 3 cortes 9:16 (TikTok/Reels/Shorts) com B-roll, animações e legenda
Uso:  python robo.py VIDEO.mp4 [--saidas yt,yt_broll,cortes] [--cortes 2] [--inicio S] [--fim S] [--alvo S] [--nome N] [--sem-ia]
Nada aqui é específico de um vídeo: tempos, cortes, cenas e enquadramento saem da análise automática."""
import argparse, hashlib, json, os, re, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleo.util import Job, ROBO, REMOTION, cfg, probe, run
from nucleo import sondar, transcrever, cortes, montar, planejar, biblioteca, qa, render, neon
from nucleo.transcrever import frases

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("--inicio", type=float, default=0); ap.add_argument("--fim", type=float, default=0)
ap.add_argument("--saidas", default="yt,yt_broll,cortes"); ap.add_argument("--cortes", type=int, default=2)
ap.add_argument("--alvo", type=float, default=0); ap.add_argument("--nome", default=""); ap.add_argument("--sem-ia", action="store_true")
ar = ap.parse_args()
SAIDAS = {x.strip() for x in ar.saidas.split(",") if x.strip()}
c = cfg(); FPS = c["fps"]
if ar.sem_ia: c["usar_ia"] = False
if ar.alvo: c["duracao_alvo"] = ar.alvo; c["duracao_min"] = max(15, ar.alvo - 15); c["duracao_max"] = ar.alvo + 15
src = os.path.abspath(ar.video)
info = probe(src)
fim = ar.fim if ar.fim > 0 else info["dur"]
base = re.sub(r"[^\w-]+", "_", os.path.splitext(os.path.basename(src))[0])[:40]
nome = ar.nome or f"{base}_{int(ar.inicio)}-{int(fim)}"
job = Job(os.path.join(ROBO, "jobs", nome))
T0 = time.time(); tempos, saidas = {}, []
def etapa(n):
    tempos[n] = round(time.time() - T0, 1); job.log(f"== {n}")

GRAO = os.path.join(ROBO, "assets", "grao.png")
if not os.path.exists(GRAO):                                   # textura de grão gerada uma vez (sem asset de terceiros)
    import numpy as np
    from PIL import Image
    os.makedirs(os.path.dirname(GRAO), exist_ok=True)
    Image.fromarray(np.clip(np.random.default_rng(7).normal(128, 42, (256, 256)), 0, 255).astype("uint8")).save(GRAO)


def preparar_pub(pub, plano):
    """Fontes, grão, fundo pré-desfocado (barato no render) e B-roll convertido: <=1920px (tela cheia) ou <=1280px (painel),
    30 fps, sem B-frames, só o trecho usado — evita estourar o cache de quadros do Remotion."""
    from nucleo.util import run
    os.makedirs(os.path.join(pub, "fonts"), exist_ok=True)
    fmt = plano["formato"]; W, H = (480, 270) if fmt == "16x9" else (270, 480)
    fundo = os.path.join(pub, f"fundo_{fmt}.mp4")
    if not os.path.exists(fundo):
        fw, fh = plano["fonte"]["w"], plano["fonte"]["h"]; s = max(W / fw, H / fh)
        sw, sh = int(round(fw * s / 2)) * 2, int(round(fh * s / 2)) * 2
        x = min(max(0, round(plano["fonte"]["rosto"]["cx"] * sw - W / 2)), sw - W)
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(pub, "natinha.mp4"), "-an", "-vf",
             f"scale={sw}:{sh},crop={W}:{H}:{x}:0,boxblur=9:2,eq=brightness=-0.42:saturation=0.75,setsar=1",
             "-c:v", "libx264", "-crf", "24", "-g", "15", "-bf", "0", "-pix_fmt", "yuv420p", fundo])
    plano["fundo"] = os.path.basename(fundo)
    for f in os.listdir(os.path.join(REMOTION, "public", "fonts")):
        shutil.copy2(os.path.join(REMOTION, "public", "fonts", f), os.path.join(pub, "fonts", f))
    shutil.copy2(GRAO, os.path.join(pub, "grao.png"))
    for x in plano["cenas"]:
        if x.get("asset"):
            a = x["asset"]; larg = 1920 if x["layout"] == "C" else 1280
            dur = round(x["fim"] - x["ini"] + 1.6, 2)
            a["arquivo"] = f"broll_{a['id']}_{larg}_{int(a['inicio'] * 10)}_{int(dur * 10)}.mp4"
            dst = os.path.join(pub, a["arquivo"])
            if not os.path.exists(dst):
                laco = ["-stream_loop", "-1"] if a.get("laco") else []
                run(["ffmpeg", "-v", "error", "-y", *laco, "-ss", f"{a['inicio']:.2f}", "-i", a["origem"], "-t", f"{dur:.2f}", "-an", "-vf",
                     f"scale='min({larg},iw)':-2:flags=lanczos,fps=30,setsar=1", "-c:v", "libx264", "-crf", "18", "-g", "15", "-bf", "0",
                     "-pix_fmt", "yuv420p", dst])
            a.update(inicio=0.0, duracao=dur, laco=False)


def creditos(sub, plano):
    linhas = ["| Asset | Uso (fala) | Fonte | Autor | Licença | Revisado |", "|---|---|---|---|---|---|"]
    for x in plano["cenas"]:
        if x.get("asset"):
            a = x["asset"]
            linhas.append(f"| {a['id']} | {x['ini']:.1f}-{x['fim']:.1f}s \"{x.get('gatilho', {}).get('palavra', '')}\" | {a['fonte']} | {a['autor']} | {a['licenca']} | {'sim' if a['revisado'] else 'não'} |")
    open(sub.p("CREDITOS_E_LICENCAS.md"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")


def srt(words, arq):
    ts = lambda t: f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(round((t % 1) * 1000)) % 1000:03}"
    out, ch, n = [], [], 1
    for i, w in enumerate(words):
        ch.append(w); nx = words[i + 1] if i + 1 < len(words) else None
        if len(ch) >= 7 or not nx or nx["s"] - w["e"] > 0.6 or re.search(r"[.!?]$", w["w"]):
            out.append(f"{n}\n{ts(ch[0]['s'])} --> {ts(ch[-1]['e'])}\n{' '.join(x['w'] for x in ch)}\n"); ch, n = [], n + 1
    open(arq, "w", encoding="utf-8").write("\n".join(out))


def remotion(sub, plano, pub, saida):
    """Render em partes. Plano diferente do último render -> descarta bundle e partes antigas."""
    cc, arqs = c, ("Robo.jsx", "index.jsx")
    if c.get("estilo", "neon") == "neon":      # camada visual NEON MATRIX (mesmo pipeline, só muda o visual)
        neon.aplicar_cache(plano, c, sub.log, sub.p("segs_neon.json"))
        cc = dict(c, remotion_entrada=os.path.join("src", "robo", "index_neon.jsx"), remotion_comp="RoboNeon")
        arqs = ("RoboNeon.jsx", "index_neon.jsx", "neon/CenasNatinha.tsx", "neon/CenasMais.tsx", "neon/CenaGen.tsx", "neon/Opcoes.tsx", "neon/Cenas.tsx")
    tpl = "".join(open(os.path.join(REMOTION, "src", "robo", f), encoding="utf-8").read() for f in arqs)
    h = hashlib.sha1((json.dumps(plano, sort_keys=True, ensure_ascii=False) + tpl).encode()).hexdigest()
    if sub.estado.get("plano_hash") != h:
        for k in ("bundle",): sub.estado.pop(k, None)
        shutil.rmtree(sub.p("partes"), ignore_errors=True); shutil.rmtree(sub.p("bundle"), ignore_errors=True)
        sub.estado["plano_hash"] = h; sub.marcar("plano", hash=h)
    sub.salvar("plano.json", plano)
    return render.renderizar(sub, sub.p("plano.json"), pub, saida, plano["frames"], FPS, cc, sub.log)


def mapear(m, ws):
    wout = [dict(w=w["w"], s=round(cortes.T(m, w["s"], FPS), 3), e=round(cortes.T(m, w["e"], FPS), 3)) for w in ws]
    for i in range(len(wout) - 1): wout[i]["e"] = min(wout[i]["e"], wout[i + 1]["s"])
    return wout


def finalizar(sub, saida, plano, rotulo, extra=None, legendas=None):
    etapa(f"{rotulo}: QA")
    rq = qa.qa(saida, plano, sub, c, legendas=legendas, extra=extra)
    sub.salvar("qa.json", rq)
    open(sub.p("STATUS.txt"), "w", encoding="utf-8").write(
        "PREVIA_PARA_APROVACAO\n" + ("QA técnico OK" if rq["ok_tecnico"] else "QA técnico com pendências — ver qa.json") + "\n")
    saidas.append((rotulo, saida, rq["ok_tecnico"]))


# ------------------------------------------------ comum: sondagem, normalização, transcrição revisada
etapa("sondagem")
if not job.feito("sondagem"):
    son = sondar.sondar(src, ar.inicio, fim, job.log)
    montar.normalizar(src, ar.inicio, fim, son, FPS, job.p("fonte.mp4"), job.p("fonte48.wav"), job.p("fonte16.wav"))
    job.salvar("sondagem.json", son); job.marcar("sondagem")
son = job.ler("sondagem.json")
fv = probe(job.p("fonte.mp4"))
# Fonte normalizada em CFR: usa contagem real, jamais duracao arredondada.
fonte_quadros = int(json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "json", job.p("fonte.mp4")]))["streams"][0]["nb_frames"])
if fonte_quadros <= 0: raise RuntimeError("Fonte normalizada sem quadros validos")
job.log(f"bruto {son['bruto']['w']}x{son['bruto']['h']} SAR {son['bruto']['sar']} rot-meta {son['bruto']['rot']} -> giro {son['giro']}° "
        f"-> fonte {fv['w']}x{fv['h']}; rosto {son['rosto']}")
etapa("transcricao")
if not job.feito("transcricao"):
    job.salvar("palavras_whisper.json", transcrever.transcrever(job.p("fonte16.wav"), c["whisper_modelo"], c["idioma"], job.log))
    job.marcar("transcricao")
if not job.feito("revisao"):
    w0 = job.ler("palavras_whisper.json")
    w1, trocas = transcrever.revisar([dict(x) for x in w0], c, job.log)
    job.salvar("palavras.json", w1); job.marcar("revisao", trocas=trocas)
words = job.ler("palavras.json")
F = frases(words)
cortes.carregar_audio(job.p("fonte16.wav"))      # V6: cortes conferidos na energia real do áudio

# ------------------------------------------------ YouTube 16:9 (limpo e com B-roll), mesma edição
if SAIDAS & {"yt", "yt_broll"}:
    etapa("youtube: edição (silêncios e tomadas)")
    yt = Job(job.p("youtube")); pub = yt.p("public")
    if not yt.feito("edicao"):
        fora = cortes.tomadas_descartadas(words, F, c, yt.log)
        idx = {i for k in fora for i in range(F[k]["i0"], F[k]["i1"] + 1)}
        yt.salvar("tomadas_descartadas.json", [F[k]["texto"] for k in fora])
        m, nq, ws = cortes.mapa_palavras([w for i, w in enumerate(words) if i not in idx], c, FPS, quadros_fonte=fonte_quadros)
        yt.salvar("mapa.json", dict(blocos=m, quadros=nq, palavras=mapear(m, ws))); yt.marcar("edicao", descartes=len(fora))
    mj = yt.ler("mapa.json"); m, nq, wout = mj["blocos"], mj["quadros"], mj["palavras"]
    os.makedirs(pub, exist_ok=True)
    if not yt.feito("montagem"):
        montar.montar(job.p("fonte.mp4"), job.p("fonte48.wav"), m, FPS, os.path.join(pub, "natinha.mp4"), os.path.join(pub, "voz.m4a"))
        yt.marcar("montagem")
    srt(wout, yt.p(f"{nome}_YOUTUBE.srt"))
    dur_yt = nq / FPS
    yt.log(f"YouTube: {sum(b['n'] for b in m) / FPS:.1f}s de {fim - ar.inicio:.1f}s do bruto, {len(m)} blocos")
    if "yt" in SAIDAS:
        etapa("youtube limpo: render FFmpeg")
        sub = Job(yt.p("limpo")); saida = sub.p(f"{nome}_YOUTUBE_LIMPO_16x9.mp4")
        pl = planejar.planejar(wout, m, dur_yt, f"{base}:yt#{nome}_yt", son["rosto"], (fv["w"], fv["h"]), c, sub.log, "16x9", "limpo")
        pl.update(fps=FPS, frames=nq, status="PREVIA_PARA_APROVACAO"); sub.salvar("plano.json", pl)
        ex = montar.yt_limpo(os.path.join(pub, "natinha.mp4"), os.path.join(pub, "voz.m4a"), pl["cortesInternos"], dur_yt, FPS,
                             (fv["w"], fv["h"]), son["rosto"], saida, sub.p("planos"), sub.log)
        shutil.copy2(yt.p(f"{nome}_YOUTUBE.srt"), sub.p(f"{nome}_YOUTUBE_LIMPO_16x9.srt"))
        finalizar(sub, saida, pl, "youtube limpo", extra=ex)
    if "yt_broll" in SAIDAS:
        etapa("youtube com B-roll: plano")
        sub = Job(yt.p("broll")); saida = sub.p(f"{nome}_YOUTUBE_BROLL_16x9.mp4")
        qa_anterior = sub.p("qa.json")
        marker_anterior = os.path.splitext(saida)[0] + ".resgate.json"
        if os.path.isfile(saida) and os.path.isfile(qa_anterior) and os.path.isfile(marker_anterior):
            qa_salva = sub.ler("qa.json")
            marker_salvo = sub.ler(os.path.basename(marker_anterior))
            vprobe = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=nb_frames,width,height", "-of", "json", saida]))["streams"][0]
            if not (qa_salva.get("ok_tecnico") is True and
                    marker_salvo.get("frames") == nq and
                    marker_salvo.get("formato") == "16x9" and
                    int(vprobe.get("nb_frames", 0)) == nq and
                    (int(vprobe["width"]), int(vprobe["height"])) == (1920, 1080)):
                raise RuntimeError("YouTube anterior existe mas falhou na conferencia; arquivo preservado")
            yt.log("Resgate: vídeo YouTube concluído reaproveitado após validar QA, marker e quadros")
            saidas.append(("youtube com B-roll", saida, True))
        else:
            pl = planejar.planejar(wout, m, dur_yt, f"{base}:yt#{nome}_yt", son["rosto"], (fv["w"], fv["h"]), c, sub.log, "16x9", "completo")
            pl.update(fps=FPS, frames=nq, status="PREVIA_PARA_APROVACAO", legendaHorizontal=c.get("legenda_youtube", False))
            preparar_pub(pub, pl); creditos(sub, pl)
            etapa("youtube com B-roll: render Remotion (partes)")
            tr = remotion(sub, pl, pub, saida)
            biblioteca.registrar([x["asset"]["id"] for x in pl["cenas"] if x.get("asset")], f"{base}:yt", f"{nome}_yt")
            shutil.copy2(yt.p(f"{nome}_YOUTUBE.srt"), sub.p(f"{nome}_YOUTUBE_BROLL_16x9.srt"))
            finalizar(sub, saida, pl, "youtube com B-roll", extra=dict(tempo_render_s=tr))

# ------------------------------------------------ cortes 9:16
if "cortes" in SAIDAS:
    etapa("cortes: escolha")
    if not job.feito("cortes"):
        Fc, esc, metodo = cortes.escolher(words, c, ar.cortes, job.log)
        job.salvar("cortes.json", dict(metodo=metodo, frases=Fc, escolhidos=esc)); job.marcar("cortes", metodo=metodo)
    cj = job.ler("cortes.json")
    for k, esc in enumerate(cj["escolhidos"], 1):
        sub = Job(job.p(f"corte{k}")); pub = sub.p("public")
        etapa(f"corte{k}: mapa e montagem")
        m, nq, ws = cortes.mapa(words, cj["frases"], esc, c, FPS, quadros_fonte=fonte_quadros)
        wout = mapear(m, ws)
        sub.salvar("mapa.json", dict(blocos=m, quadros=nq, palavras=wout, escolha=esc))
        os.makedirs(pub, exist_ok=True)
        if not sub.feito("montagem"):
            montar.montar(job.p("fonte.mp4"), job.p("fonte48.wav"), m, FPS, os.path.join(pub, "natinha.mp4"), os.path.join(pub, "voz.m4a"))
            sub.marcar("montagem")
        etapa(f"corte{k}: plano")
        # Plano previamente concluido: nao repetir pesquisa ou download de B-roll.
        if sub.feito("plano") and os.path.isfile(sub.p("plano.json")):
            pl = sub.ler("plano.json")
            if pl.get("frames") != nq or pl.get("formato") != "9x16":
                raise RuntimeError("Checkpoint do corte nao corresponde ao mapa atual")
            for nome_base in ("natinha.mp4", "voz.m4a"):
                if not os.path.isfile(os.path.join(pub, nome_base)):
                    raise RuntimeError("Falta artefato do checkpoint: " + nome_base)
            sub.log("Plano do corte reaproveitado do checkpoint; render retomavel")
        else:
            pl = planejar.planejar(wout, m, nq / FPS, f"{base}:cortes#{nome}_c{k}", son["rosto"], (fv["w"], fv["h"]), c, sub.log, "9x16", "completo")
            pl.update(fps=FPS, frames=nq, status="PREVIA_PARA_APROVACAO", corte=dict(indice=k, tema=esc.get("tema", ""),
                      motivo=esc.get("motivo", ""), metodo=cj["metodo"], duracao=round(nq / FPS, 2), bruto=src,
                      trecho_bruto=[round(ar.inicio + m[0]["src"], 2), round(ar.inicio + m[-1]["src"] + m[-1]["n"] / FPS, 2)]))
            preparar_pub(pub, pl); creditos(sub, pl)
        etapa(f"corte{k}: render Remotion (partes)")
        saida = sub.p(f"{nome}_CORTE{k}_9x16.mp4")
        # Checkpoint de vídeo concluído: código atualizado não invalida um MP4
        # validado por quadros e QA técnico. Não renderizar nem transcrever de novo.
        if os.path.isfile(saida):
            mk = os.path.splitext(saida)[0] + ".resgate.json"
            qa_path = sub.p("qa.json")
            if not (os.path.isfile(mk) and os.path.isfile(qa_path)):
                raise RuntimeError("MP4 existente sem checkpoint completo; preservado para análise")
            previous = sub.ler("qa.json")
            metadata = sub.ler(os.path.basename(mk))
            pr = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=nb_frames,width,height,r_frame_rate", "-of", "json", saida]))["streams"][0]
            dur_ok = abs(float(previous.get("formato", {}).get("dur", -1)) - nq/FPS) < .05
            ok = (previous.get("ok_tecnico") is True and dur_ok
                  and metadata.get("frames") == nq and metadata.get("formato") == "9x16"
                  and int(pr.get("nb_frames", 0)) == nq
                  and (int(pr["width"]), int(pr["height"])) == (1080, 1920))
            if not ok:
                raise RuntimeError("MP4 existente não passou validação do checkpoint; arquivo preservado")
            sub.log(f"Resgate: Corte {k} concluído e QA validado; MP4 e legendas reaproveitados")
            saidas.append((f"corte {k}", saida, True))
            continue
        tr = remotion(sub, pl, pub, saida)
        biblioteca.registrar([x["asset"]["id"] for x in pl["cenas"] if x.get("asset")], f"{base}:cortes", f"{nome}_c{k}")
        finalizar(sub, saida, pl, f"corte {k}", extra=dict(tempo_render_s=tr))

tempos["total"] = round(time.time() - T0, 1)
job.salvar("tempos.json", tempos)
for r_, s, ok in saidas: job.log(f"SAÍDA [{r_}]: {s}  QA técnico: {'OK' if ok else 'PENDÊNCIAS'}")
