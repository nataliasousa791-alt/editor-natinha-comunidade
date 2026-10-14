"""Integração verdadeira: dados editados pelo Natinha original -> composição Remotion.
Não executa algoritmos alternativos de seleção, legenda, transcrição ou B-roll.
Fonte legada em leitura; todas as gravações em Resultados/Remotion.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PROJETOS = ROOT / "projetos"
RESULTADOS = ROOT / "Resultados" / "Remotion"
ROBO = ROOT.parent / "NATINHA_CINEMATIC_EDITOR_V1" / "robo"
REMOTION = ROBO.parent / "remotion"
sys.path.insert(0, str(ROBO))
from nucleo.util import Job, cfg, probe
from nucleo import sondar, qa, render

FPS = 30


def ler(p, padrao=None):
    if not p.is_file():
        return padrao
    return json.loads(p.read_text(encoding="utf-8"))


def salvar(p, dados):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(".tmp")
    t.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(t, p)


def ffmpeg(args, log):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("FFmpeg: " + r.stderr[-1000:])
    log("FFmpeg finalizou: " + str(args[-1]))


def palavras_corte(ws, inicio, fim):
    saida = []
    for x in ws:
        a = float(x["s"]); b = float(x["e"])
        if a >= inicio - 0.07 and b <= fim + 0.15 and b > inicio:
            a = max(0, a - inicio)
            b = max(a + 0.04, b - inicio)
            saida.append({"w": str(x["w"]), "s": round(a, 3), "e": round(b, 3)})
    return saida


def legendas_original_timing(ws, dur):
    # Mesmo material temporal usado pelo Natinha original; o Remotion estiliza.
    out = []
    bloco = []
    def flush():
        if bloco:
            fim = min(dur, bloco[-1]["e"] + 0.25)
            out.append({"ini": max(0, round(bloco[0]["s"] - 0.03, 3)),
                        "fim": round(fim, 3),
                        "palavras": [{"w": x["w"], "s": x["s"], "destaque": False} for x in bloco]})
            bloco.clear()
    for i, w in enumerate(ws):
        if w["s"] > dur - 0.1:
            break
        bloco.append(w)
        seguinte = ws[i + 1] if i + 1 < len(ws) else None
        if len(bloco) >= 3 or sum(len(x["w"]) + 1 for x in bloco) >= 18 or (
            seguinte and seguinte["s"] - w["e"] > 0.35
        ) or re.search(r"[,.!?…]$", w["w"]) or not seguinte:
            flush()
    flush()
    for k in range(len(out) - 1):
        out[k]["fim"] = round(min(out[k]["fim"], out[k + 1]["ini"]), 3)
    return [x for x in out if x["fim"] > x["ini"]]


def escolher_cenas(pasta_original, numero, ws, dur, public, log):
    bp = pasta_original / f"corte_{numero}" / "brolls.json"
    brolls = ler(bp, []) or []
    cenas = []
    blocos = []
    creditos = []
    for i, b in enumerate(brolls):
        ini = float(b.get("inicio", -1)); tempo = float(b.get("dur", 0))
        fim = min(dur, ini + tempo)
        if ini < 0 or ini > dur - 1 or fim - ini < 0.5:
            continue
        origem = pasta_original / f"corte_{numero}" / Path(b.get("arquivo", "")).name
        if not origem.is_file() or origem.suffix.lower() != ".mp4":
            log("B-roll legado ausente: " + origem.name)
            continue
        novo = f"legado_cena_{i + 1:02}.mp4"
        destino = public / novo
        if not destino.is_file() or destino.stat().st_size != origem.stat().st_size:
            shutil.copy2(origem, destino)
        fala = [dict(w=w["w"], s=w["s"]) for w in ws if ini - 0.04 <= w["s"] <= fim + 0.04]
        if not fala:
            log("B-roll ignorado por ausência de fala sincronizada: " + origem.name)
            continue
        cenas.append({
            "id": "natinha_legado_" + str(i + 1),
            "tipo": "broll", "layout": "C", "ini": round(ini, 3), "fim": round(fim, 3),
            "fala": b.get("frase", ""), "frase": fala[:13],
            "justificativa": b.get("porque") or b.get("ideia") or "B-roll planejado pelo Natinha original",
            "rotulo": str(b.get("titulo") or "")[:40],
            "asset": {"arquivo": novo, "inicio": 0, "duracao": fim-ini + 1,
                      "laco": False, "fonte": b.get("fonte"), "revisado": False}
        })
        blocos.append([round(ini, 3), round(fim, 3)])
        creditos.append({"cena": i+1, "fonte": b.get("credito") or b.get("fonte"),
                         "fala": b.get("frase"), "porque": b.get("porque"),
                         "original": str(origem)})
    return cenas, blocos, creditos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--projeto", required=True)
    p.add_argument("--corte", required=True, type=int)
    p.add_argument("--job", required=True)
    p.add_argument("--max-segundos", type=float, default=0)
    args = p.parse_args()
    if Path(args.projeto).name != args.projeto or not re.fullmatch(r"rm_\d{8}_\d{6}_[a-f0-9]{6}", args.job):
        raise ValueError("Identificadores inválidos")
    projeto = (PROJETOS / args.projeto).resolve()
    if projeto.parent != PROJETOS.resolve() or not projeto.is_dir():
        raise ValueError("Projeto fora da pasta oficial")
    saida = (RESULTADOS / args.job).resolve()
    if saida.parent != RESULTADOS.resolve():
        raise ValueError("Saída inválida")
    saida.mkdir(parents=True, exist_ok=True)
    status_path = saida / "status.json"
    st = ler(status_path, {}) or {}
    if st.get("status") == "concluido":
        print("Job já concluído", flush=True)
        return
    def etapa(nome):
        st.update(status="executando", etapa=nome, atualizado=datetime.now().isoformat())
        salvar(status_path, st)
        print("ETAPA:", nome, flush=True)
    try:
        info = ler(projeto / "cortes.json", []) or []
        corte = next((x for x in info if int(x.get("n", -1)) == args.corte), None)
        if not corte:
            raise ValueError("Corte não existe no projeto original")
        origem = projeto / "youtube.mp4"
        if not origem.is_file():
            raise ValueError("Primeiro é necessário limpar o vídeo pelo Natinha original")
        words_full = ler(projeto / "youtube_palavras.json", [])
        if not words_full:
            raise ValueError("Tempos de palavras do Natinha original indisponíveis")
        inicio = float(corte["s"])
        dur = float(corte["e"]) - inicio
        if args.max_segundos > 0:
            dur = min(dur, args.max_segundos)
        if not 3 <= dur <= 3600:
            raise ValueError("Duração inválida")
        ws = palavras_corte(words_full, inicio, inicio + dur)
        if len(ws) < 5:
            raise ValueError("Transcrição não cobre o corte")
        pub = saida / "tecnico" / "public"
        pub.mkdir(parents=True, exist_ok=True)
        video = pub / "natinha.mp4"
        audio = pub / "voz.m4a"
        etapa("Reaproveitando limpeza e cortes do Natinha original")
        if not video.is_file():
            ffmpeg(["-ss", f"{inicio:.3f}", "-i", origem, "-t", f"{dur:.3f}",
                    "-an", "-vf", "fps=30,setsar=1", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", video], print)
        if not audio.is_file():
            ffmpeg(["-ss", f"{inicio:.3f}", "-i", origem, "-t", f"{dur:.3f}",
                    "-vn", "-c:a", "aac", "-b:a", "192k", audio], print)
        for arq in (REMOTION / "public" / "fonts").glob("*"):
            d = pub / "fonts" / arq.name
            d.parent.mkdir(exist_ok=True)
            if not d.exists():
                shutil.copy2(arq, d)
        grao = ROBO / "assets" / "grao.png"
        if grao.exists():
            shutil.copy2(grao, pub / "grao.png")
        etapa("Usando B-rolls e tempos planejados pelo Natinha original")
        cenas, blocos, creditos = escolher_cenas(projeto, args.corte, ws, dur, pub, print)
        fonte = probe(str(video))
        try:
            reconhecimento = sondar.sondar(str(video), 0, dur, print)
            rosto = reconhecimento["rosto"]
        except Exception as e:
            print("AVISO: rosto não detectado:", str(e), flush=True)
            rosto = {"cx": 0.5, "cy": 0.45, "w": 0.25, "h": 0.38}
        abertura = ws[:min(5, len(ws))]
        fechamento = ws[max(0, len(ws)-11):]
        cenas = [{
            "id": "abertura", "tipo": "abertura", "layout": "A",
            "ini": 0.0, "fim": min(2.4, dur / 3),
            "texto": [x["w"] for x in abertura], "fala": " ".join(x["w"] for x in abertura),
            "justificativa": "Gancho literal da seleção do Natinha original"
        }, *cenas, {
            "id": "fechamento", "tipo": "fechamento", "layout": "A",
            "ini": max(0, fechamento[0]["s"] - 0.1), "fim": dur,
            "palavras": [{"w": x["w"], "s": x["s"]} for x in fechamento],
            "fala": " ".join(x["w"] for x in fechamento),
            "justificativa": "Última frase do corte selecionado pelo Natinha original"
        }]
        plano = {
            "fps": FPS, "frames": int(round(dur * FPS)), "formato": "9x16",
            "fonte": {"arquivo": "natinha.mp4", "w": fonte["w"], "h": fonte["h"], "rosto": rosto},
            "audio": "voz.m4a", "cenas": cenas, "blocosB": [], "blocosC": blocos,
            "legendas": legendas_original_timing(ws, dur), "cortesInternos": [],
            "status": "PREVIA_PARA_APROVACAO", "origem_editor": "Natinha original",
            "projeto_original": args.projeto, "corte_original": args.corte,
            "duracao": dur
        }
        tecnico = Job(str(saida / "tecnico"))
        tecnico.salvar("plano.json", plano)
        salvar(saida / "relatorios" / "rastreabilidade.json", {
            "origem": str(projeto), "corte": args.corte, "de": inicio, "ate": inicio + dur,
            "motor_limpeza": "nucleo/youtube.py original (artefato youtube.mp4)",
            "motor_cortes": "nucleo/cortes.py original (cortes.json)",
            "motor_legendas": "nucleo/transcrever.py original (youtube_palavras.json)",
            "motor_brolls": "brolls.json e vídeos originais pré-gerados",
            "motor_composicao": "Remotion", "brolls": creditos
        })
        etapa("Render cinematográfico Remotion sobre edição Natinha original")
        destino = saida / "videos" / "verticais"
        destino.mkdir(parents=True, exist_ok=True)
        final = destino / (args.job + "_NATINHA_ORIGINAL_COM_REMOTION_9x16.mp4")
        render.renderizar(tecnico, tecnico.p("plano.json"), str(pub), str(final),
                          plano["frames"], FPS, cfg(), print)
        etapa("Validando áudio, vídeo e legendas")
        q = qa.qa(str(final), plano, tecnico, cfg(), legendas=ws)
        salvar(saida / "relatorios" / "qa.json", q)
        if not q.get("ok_tecnico"):
            raise RuntimeError("QA indicou pendências, veja relatorios/qa.json")
        st.update(status="concluido", etapa="Corte integrado concluído, aguardando revisão estética",
                  arquivos=[{"nome": final.name,
                             "grupo": "verticais",
                             "url": f"/api/remotion/media/{args.job}/videos/verticais/{final.name}"}])
        salvar(status_path, st)
        print("ENTREGA:", final, flush=True)
    except Exception as e:
        st.update(status="erro", etapa="Erro na integração Natinha + Remotion", erro=str(e))
        salvar(status_path, st)
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
