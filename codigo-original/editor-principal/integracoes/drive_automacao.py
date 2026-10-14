"""Fluxo de nuvem do Editor Natinha. Um vídeo por vez, modos separados e retorno a prontos."""
import json
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from secrets import token_hex

from flask import Blueprint, jsonify, request
from nucleo.util import PROJETOS, VERSOES, ler_config, salvar_config, pasta_nuvem
from nucleo import pipeline
from integracoes.remotion import bridge

bp = Blueprint("drive_modos_natinha", __name__)
MODOS = ("classico", "vertical", "youtube", "pacote", "hibrido")
ROTULOS = {
    "classico": "Vídeo completo + cortes (tradicional)",
    "vertical": "Cortes cinematográficos",
    "youtube": "YouTube cinematográfico",
    "pacote": "Pacote cinematográfico: YouTube + cortes",
    "hibrido": "Híbrido (beta): Remotion nas cenas + FFmpeg no restante",
}


def _opcoes(config):
    return {
        "modo": config.get("drive_modo", "classico"),
        "versao": config.get("versao_padrao", "v3.1"),
        "cortes": int(config.get("drive_cortes", 3)),
        "alvo": int(config.get("drive_alvo", 90)),
        "estilo": config.get("drive_estilo", "completo"),
        "permitir_online": bool(config.get("drive_permitir_online", False)),
    }


@bp.get("/api/drive/modo")
def consultar_modo():
    c = ler_config(sem_versao=True)
    op = _opcoes(c)
    op.update(rotulo=ROTULOS.get(op["modo"], "Edição tradicional"),
              ativo=bool(c.get("drive_remoto") and pasta_nuvem()),
              pasta_entrada=(c.get("drive_remoto", "").rstrip("/") + "/entrada") if c.get("drive_remoto") else "")
    return jsonify(op)


@bp.post("/api/drive/modo")
def definir_modo():
    body = request.get_json(silent=True) or {}
    modo = body.get("modo")
    if modo not in MODOS:
        return jsonify(erro="Modo de edição inválido"), 400
    try:
        cortes = int(body.get("cortes", 3))
        alvo = int(body.get("alvo", 90))
    except (TypeError, ValueError):
        return jsonify(erro="Cortes e duração devem ser números"), 400
    estilo = body.get("estilo", "completo")
    versao = body.get("versao")
    online = body.get("permitir_online", False)
    if type(online) is not bool or cortes not in (1, 2, 3) or not 15 <= alvo <= 600:
        return jsonify(erro="Quantidade, duração ou autorização inválida"), 400
    if estilo not in ("completo", "limpo") or (modo in ("vertical", "pacote", "hibrido") and estilo != "completo"):
        return jsonify(erro="Estilo incompatível com o modo escolhido"), 400
    if modo == "classico" and versao is not None and versao not in VERSOES:
        return jsonify(erro="Versão clássica não encontrada"), 400
    c = ler_config(sem_versao=True)
    # Configuração do Drive não muda o modo de edições já iniciadas.
    c.update(drive_modo=modo, drive_cortes=cortes, drive_alvo=alvo,
             drive_estilo=estilo, drive_permitir_online=online)
    if modo == "classico" and versao:
        c["versao_padrao"] = versao
    salvar_config(c)
    return consultar_modo()


def _ocupado(algum_rodando):
    return bool(algum_rodando() or bridge._em_execucao() or bridge._motor_ocupado())


def _ler(p, padrao=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if padrao is None else padrao


def _continuar_legados(rodar, slug):
    for nome in sorted(os.listdir(PROJETOS)):
        p = Path(PROJETOS) / nome
        if not p.is_dir():
            continue
        proj, estado = _ler(p / "projeto.json"), _ler(p / "estado.json")
        if proj.get("origem") == "nuvem" and not estado.get("pronto") and not estado.get("erro"):
            if not Path(proj.get("bruto", "")).is_file():
                continue
            print("Drive: retomando vídeo tradicional", nome, flush=True)
            return rodar(nome, pipeline.processar, str(p))
    return False


def _continuar_remotion():
    """Recupera somente jobs de nuvem pendentes/interrompidos, respeitando ocupação."""
    if not bridge.RESULTADOS.exists():
        return False
    for p in sorted(bridge.RESULTADOS.glob("rm_*")):
        st = _ler(p / "status.json")
        if not st.get("origem_nuvem"):
            continue
        if st.get("status") == "executando" and not bridge._motor_ocupado():
            st.update(status="interrompido", etapa="Retomada após reinício")
            bridge._gravar(p / "status.json", st)
        if st.get("status") not in ("fila", "interrompido"):
            continue
        if not Path(st.get("origem", "")).is_file():
            continue
        if bridge.retomar_job_drive(p):
            print("Drive: retomando Remotion", p.name, flush=True)
            return True
    return False


def _receber_classico(caminho, base, tipo, op, rodar, slug):
    nome = slug(caminho.name) + datetime.now().strftime("_%d%m_%H%M%S") + "_" + token_hex(2)
    p = Path(PROJETOS) / nome
    p.mkdir(parents=True, exist_ok=False)
    destino = p / ("bruto" + caminho.suffix.lower())
    try:
        shutil.move(str(caminho), str(destino))
        projeto = {"nome": nome, "bruto": str(destino), "origem": "nuvem",
                   "versao": op["versao"], "exportar_para": str(base / "prontos" / slug(caminho.name))}
        if tipo == "vertical":
            projeto.update(tipo="vertical", girar=0)
        (p / "projeto.json").write_text(json.dumps(projeto, ensure_ascii=False), encoding="utf-8")
        if not rodar(nome, pipeline.processar, str(p)):
            raise RuntimeError("O motor clássico estava ocupado")
        print("Drive: edição tradicional iniciada", nome, flush=True)
    except Exception:
        if destino.exists() and not caminho.exists():
            shutil.move(str(destino), str(caminho))
        raise


def vigiar_integrado(algum_rodando, rodar, slug, load_json, ext):
    """Pasta entrada segue o modo salvo; entrada_vertical mantém seu fluxo vertical antigo."""
    vistos = {}
    while True:
        try:
            base_s = pasta_nuvem()
            if not base_s:
                time.sleep(20)
                continue
            base = Path(base_s)
            if _ocupado(algum_rodando):
                time.sleep(20)
                continue
            if _continuar_legados(rodar, slug) or _continuar_remotion():
                time.sleep(20)
                continue
            op = _opcoes(ler_config(sem_versao=True))
            iniciou = False
            for sub in ("entrada", "entrada_vertical"):
                pasta = base / sub
                if not pasta.is_dir():
                    continue
                for caminho in sorted(pasta.iterdir()):
                    if not caminho.is_file() or caminho.suffix.lower() not in ext:
                        continue
                    tam = caminho.stat().st_size
                    # A cópia do Drive precisa manter o tamanho estável por pelo menos uma rodada.
                    if not tam or vistos.get(str(caminho)) != tam:
                        vistos[str(caminho)] = tam
                        continue
                    if _ocupado(algum_rodando):
                        break
                    if sub == "entrada_vertical" or op["modo"] == "classico":
                        _receber_classico(caminho, base,
                                         "vertical" if sub == "entrada_vertical" else None,
                                         op, rodar, slug)
                    else:
                        bridge.iniciar_job_drive(caminho, op, base, slug(caminho.name))
                        print("Drive: Remotion iniciado", caminho.name, op["modo"], flush=True)
                    vistos.pop(str(caminho), None)
                    iniciou = True
                    break
                if iniciou:
                    break
        except Exception as e:
            print("Drive: erro no monitor integrado:", e, flush=True)
        time.sleep(20)
