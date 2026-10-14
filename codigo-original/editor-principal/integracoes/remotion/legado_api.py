"""Endpoints do acoplamento real do motor Natinha original à camada Remotion."""
import json
import os
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from flask import jsonify, request

def registrar(bp, ROOT, RESULTADOS, PY_MOTOR, HERE, lock, ativos, ocupado):
    projetos = ROOT / "projetos"

    @bp.get("/api/remotion/original/projetos")
    def listar_originais():
        out = []
        if not projetos.is_dir():
            return jsonify(out)
        for p in sorted(projetos.iterdir(), key=lambda v: v.stat().st_mtime, reverse=True):
            if not p.is_dir() or not (p / "youtube.mp4").is_file():
                continue
            try:
                cortes = json.loads((p / "cortes.json").read_text(encoding="utf-8"))
                aprovados = [{"n": int(c["n"]), "titulo": c.get("titulo") or f"Corte {c['n']}",
                              "segundos": round(float(c["e"]) - float(c["s"]), 1)}
                             for c in cortes if isinstance(c, dict) and c.get("n")]
                if aprovados:
                    out.append({"nome": p.name, "cortes": aprovados})
            except (OSError, ValueError, KeyError):
                continue
            if len(out) >= 25:
                break
        return jsonify(out)

    def _rodar_original(p, nome, n):
        status = p / "status.json"
        with (p / "integracao.log").open("a", encoding="utf-8") as log:
            proc = None
            try:
                args = [str(PY_MOTOR), "-u", str(HERE / "legado_remotion.py"),
                        "--projeto", nome, "--corte", str(n), "--job", p.name]
                env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
                proc = subprocess.Popen(args, cwd=str(HERE), stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=subprocess.STDOUT, env=env,
                                        creationflags=(subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0))
                proc.wait()
                if proc.returncode:
                    d = json.loads(status.read_text(encoding="utf-8"))
                    if d.get("status") != "erro":
                        d.update(status="erro", erro=f"Motor finalizou com código {proc.returncode}")
                        status.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                d = json.loads(status.read_text(encoding="utf-8"))
                d.update(status="erro", erro=str(exc))
                status.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    @bp.post("/api/remotion/original/jobs")
    def iniciar_original():
        d = request.get_json(silent=True) or {}
        nome = d.get("projeto")
        try:
            corte = int(d.get("corte", 0))
        except (ValueError, TypeError):
            return jsonify(erro="Número de corte inválido"), 400
        if not isinstance(nome, str) or not re.fullmatch(r"[\w.\-]+", nome) or corte < 1:
            return jsonify(erro="Identificação inválida"), 400
        origem = (projetos / nome).resolve()
        if origem.parent != projetos.resolve() or not origem.is_dir():
            return jsonify(erro="Projeto não encontrado"), 404
        if not (origem / "youtube.mp4").is_file() or not (origem / "youtube_palavras.json").is_file():
            return jsonify(erro="O Natinha original ainda não terminou de preparar esse vídeo"), 409
        try:
            cortes = json.loads((origem / "cortes.json").read_text(encoding="utf-8"))
            if not any(int(c.get("n", -1)) == corte for c in cortes):
                return jsonify(erro="Corte não encontrado"), 404
        except (OSError, ValueError):
            return jsonify(erro="Projeto original sem cortes válidos"), 409
        with lock:
            if any(t.is_alive() for t in ativos.values()) or ocupado():
                return jsonify(erro="Há outra renderização cinematográfica em andamento."), 409
            nome_job = "rm_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + token_hex(3)
            p = RESULTADOS / nome_job
            p.mkdir(parents=True)
            estado = {"id": nome_job, "status": "fila", "etapa": "Aguardando integração com Natinha original",
                      "formato": "9x16", "estilo": "natinha_original+remotion",
                      "origem_editor": nome, "corte_original": corte,
                      "criado": datetime.now().isoformat(), "arquivos": []}
            (p / "status.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
            t = threading.Thread(target=_rodar_original, args=(p, nome, corte), daemon=True)
            ativos[nome_job] = t
            t.start()
        return jsonify(id=nome_job, reusa=["limpeza original", "cortes originais",
                                             "palavras originais", "B-rolls originais", "Remotion"]), 202

    return _rodar_original
