"""Render híbrido experimental Natinha: cenas-chave em Remotion, intervalos em FFmpeg.

Só é chamado com --hibrido. Não altera nem acelera retroativamente os modos antigos.
Saídas são prévias para revisão, nunca publicadas automaticamente.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from nucleo.util import REMOTION, probe, run
from nucleo import render as render_antigo

NPX = "npx.cmd" if os.name == "nt" else "npx"


def escolher_cenas(plano, frames, fps, limite_fracao=0.22, max_cenas=4):
    """Trechos cinematográficos disjuntos, com orçamento explícito de quadros."""
    limite_seg = 22 if plano.get("formato") == "16x9" else 16
    orcamento = min(int(frames * limite_fracao), int(limite_seg * fps))
    prioridades = {"abertura": 0, "broll": 1, "numero": 2, "cartao": 3, "fechamento": 4}
    candidatos = []
    for cena in plano.get("cenas", []):
        tipo = cena.get("tipo", "")
        if tipo not in prioridades:
            continue
        if tipo == "broll" and not cena.get("asset"):
            continue
        a = max(0, int(round(float(cena["ini"]) * fps)))
        b = min(frames, int(round(float(cena["fim"]) * fps)))
        if b - a < max(10, int(fps * 0.65)):
            continue
        candidatos.append((prioridades[tipo], a, b, tipo))
    escolhidas, usadas = [], 0
    for _, a, b, tipo in sorted(candidatos):
        if len(escolhidas) >= max_cenas:
            break
        if any(not (b <= x["a"] or a >= x["b"]) for x in escolhidas):
            continue
        n = min(b - a, orcamento - usadas)
        if n < fps * 0.65:
            continue
        escolhidas.append({"a": a, "b": a + n, "tipo": tipo})
        usadas += n
    return sorted(escolhidas, key=lambda x: x["a"])


def linha_tempo(cenas, frames):
    """Alterna segmentos mutuamente exclusivos, sem perder nem repetir quadros."""
    pontos = []
    anterior = 0
    for c in cenas:
        if c["a"] > anterior:
            pontos.append(dict(motor="ffmpeg", a=anterior, b=c["a"]))
        pontos.append(dict(motor="remotion", a=c["a"], b=c["b"], tipo=c["tipo"]))
        anterior = c["b"]
    if anterior < frames:
        pontos.append(dict(motor="ffmpeg", a=anterior, b=frames))
    assert sum(x["b"] - x["a"] for x in pontos) == frames
    return pontos


def _ass_texto(s):
    return str(s).replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _tempo_ass(segundos):
    cs = max(0, int(round(segundos * 100)))
    return f"{cs // 360000}:{(cs // 6000) % 60:02}:{(cs // 100) % 60:02}.{cs % 100:02}"


def _legendas_ass(caminho, plano, a, b, fps):
    """Legenda em tempo local ao segmento FFmpeg, preservando trechos da transcrição."""
    vertical = plano.get("formato") == "9x16"
    w, h = (1080, 1920) if vertical else (1920, 1080)
    tamanho, margem = (61, 180) if vertical else (45, 95)
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", "WrapStyle: 0",
        f"PlayResX: {w}", f"PlayResY: {h}", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Natinha,Poppins,{tamanho},&H00F5F3EE,&H00E8833A,&HBA101114,&H800C0D10,-1,0,0,0,100,100,0,0,1,3,1,2,65,65,{margem},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ini, fim = a / fps, b / fps
    if vertical or plano.get("legendaHorizontal"):
        for bloco in plano.get("legendas", []):
            t0, t1 = float(bloco.get("ini", 0)), float(bloco.get("fim", 0))
            t0, t1 = max(ini, t0), min(fim, t1)
            if t1 - t0 < 0.08:
                continue
            texto = _ass_texto(" ".join(str(p.get("w", "")) for p in bloco.get("palavras", [])))
            if texto:
                linhas.append(f"Dialogue: 0,{_tempo_ass(t0-ini)},{_tempo_ass(t1-ini)},Natinha,,0,0,0,,{texto}")
    Path(caminho).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return len(linhas) > 13


def _codificar_ffmpeg(sub, plano, pub, a, b, fps, output, indice):
    """FFmpeg CPU-friendly para trechos comuns: enquadramento e legendas."""
    w, h = (1080, 1920) if plano["formato"] == "9x16" else (1920, 1080)
    video = os.path.join(pub, "natinha.mp4")
    if not os.path.isfile(video):
        raise RuntimeError("Montagem de fala ausente no motor híbrido")
    leg = sub.p(f"hibrido_leg_{indice:03d}.ass")
    com_legendas = _legendas_ass(leg, plano, a, b, fps)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=bicubic,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x121316,setsar=1")
    if com_legendas:
        # Arquivo ASS relativo; evita escapamento problemático de C: no Windows.
        vf += f",ass={os.path.basename(leg)}"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y",
           "-ss", f"{a/fps:.6f}", "-i", video,
           "-frames:v", str(b-a), "-vf", vf, "-an",
           "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "21", "-profile:v", "high", "-g", str(fps),
           "-bf", "0", "-pix_fmt", "yuv420p", "-threads", "2", output]
    subprocess.run(cmd, cwd=str(Path(leg).parent), check=True, stdin=subprocess.DEVNULL,
                   creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0)


def _remotion_trecho(sub, bundle, plano_json, a, b, fps, output, indice, log):
    bruto = sub.p(f"hibrido_rem_{indice:03d}_bruto.mp4")
    if not os.path.isfile(bruto):
        ok = render_antigo._npx(
            ["render", bundle, "Robo", bruto, f"--props={plano_json}",
             f"--frames={a}-{b-1}", "--muted", "--codec=h264",
             "--crf=21", "--concurrency=1", "--log=error"],
            sub.p(f"hibrido_erro_rem_{indice:03d}.txt"))
        if not ok:
            raise RuntimeError(f"Trecho Remotion {indice} falhou (log disponível)")
    # Normaliza FPS, perfil e GOP para concat seguro com os trechos FFmpeg.
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", bruto,
         "-frames:v", str(b-a), "-vf", f"fps={fps},format=yuv420p",
         "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-profile:v", "high", "-g", str(fps), "-bf", "0",
         "-pix_fmt", "yuv420p", "-threads", "2", output])
    log(f"Híbrido: cena especial {indice} pronta ({(b-a)/fps:.1f}s)")


def renderizar(sub, plano_json, pub, saida, frames, fps, c, log):
    """Substitui APENAS o renderizador quando o job solicita --hibrido."""
    t0 = time.monotonic()
    plano = json.loads(Path(plano_json).read_text(encoding="utf-8"))
    cenas = escolher_cenas(plano, frames, fps)
    pontos = linha_tempo(cenas, frames)
    if not cenas:
        log("Híbrido: nenhuma cena especial; FFmpeg assume toda a edição")
    else:
        log(f"Híbrido: {len(cenas)} cenas Remotion ({sum(x['b']-x['a'] for x in cenas)/fps:.1f}s); "
            f"restante FFmpeg ({(frames-sum(x['b']-x['a'] for x in cenas))/fps:.1f}s)")
    bundle = sub.p("hibrido_bundle")
    if cenas and not Path(bundle).is_dir():
        ok = render_antigo._npx(
            ["bundle", os.path.join("src", "robo", "index.jsx"),
             f"--out-dir={bundle}", f"--public-dir={pub}", "--log=error"],
            sub.p("hibrido_erro_bundle.txt"))
        if not ok:
            raise RuntimeError("Falha ao preparar as cenas especiais")
    segmentos = []
    for indice, x in enumerate(pontos):
        arq = sub.p(f"hibrido_seg_{indice:03d}.mp4")
        segmentos.append(arq)
        if os.path.isfile(arq) and abs(probe(arq)["dur"] - (x["b"]-x["a"])/fps) < 0.18:
            continue
        if x["motor"] == "remotion":
            _remotion_trecho(sub, bundle, plano_json, x["a"], x["b"], fps, arq, indice, log)
        else:
            _codificar_ffmpeg(sub, plano, pub, x["a"], x["b"], fps, arq, indice)
            log(f"Híbrido: fala com FFmpeg {indice} pronta ({(x['b']-x['a'])/fps:.1f}s)")
        medido = probe(arq)
        if abs(medido["dur"] - (x["b"] - x["a"])/fps) > 0.2:
            raise RuntimeError(f"Duração inválida no segmento híbrido {indice}")
    lista = sub.p("hibrido_partes.txt")
    Path(lista).write_text("".join(f"file '{str(x).replace(os.sep, '/')}'\n" for x in segmentos), encoding="utf-8")
    mudo = sub.p("hibrido_mudo.mp4")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i",
         lista, "-c:v", "copy", mudo])
    voz = os.path.join(pub, "voz.m4a")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", mudo, "-i", voz,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
         "-t", f"{frames/fps:.4f}", "-movflags", "+faststart", saida])
    medido = probe(saida)
    if abs(medido["dur"] - frames/fps) > 0.5:
        raise RuntimeError("Conferência de duração falhou no render híbrido")
    relatorio = dict(modo="hibrido_beta", frames=frames, fps=fps, cenas_especiais=cenas,
                     segmentos=pontos, tempo_render_s=round(time.monotonic()-t0, 1),
                     videos_preservados=True)
    Path(sub.p("hibrido_relatorio.json")).write_text(
        json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    return relatorio["tempo_render_s"]


def escolher_cortes_adaptativos(escolher_normal, words, configuracao, solicitados, log):
    """No híbrido, tenta reduzir a duração para obter o número pedido, sem inventar cortes.

    Retorna menos que o pedido quando o conteúdo realmente não é suficiente.
    Não altera a lógica do Remotion clássico.
    """
    frases, cortes, metodo = escolher_normal(words, configuracao, solicitados, log)
    if len(cortes) >= solicitados or solicitados <= 1 or not words:
        return frases, cortes, metodo
    fala_total = float(words[-1]["e"]) - float(words[0]["s"])
    alvo = max(30, min(round(float(configuracao["duracao_alvo"]) * 0.65),
                       int((fala_total / solicitados) * 0.88)))
    ajuste = dict(configuracao, usar_ia=False, duracao_alvo=alvo,
                  duracao_min=max(15, alvo - 20), duracao_max=alvo + 20)
    f2, c2, _ = escolher_normal(words, ajuste, solicitados, log)
    if len(c2) > len(cortes):
        log(f"Híbrido: trechos adaptados para {len(c2)} cortes de cerca de {alvo}s; "
            f"pedido original {solicitados} cortes")
        return f2, c2, "hibrido:duracao_adaptada"
    return frases, cortes, metodo
