"""Adaptador isolado Remotion para o Editor Natinha. Não altera motores anteriores."""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from secrets import token_hex

from flask import Blueprint, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MOTOR = ROOT.parent / "NATINHA_CINEMATIC_EDITOR_V1" / "robo"
JOBS_MOTOR = MOTOR / "jobs"
RESULTADOS = ROOT / "Resultados" / "Remotion"
PY_MOTOR = MOTOR / ".venv" / "Scripts" / "python.exe"
EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi", ".3gp"}
bp = Blueprint("natinha_remotion", __name__)
lock = threading.RLock()
ativos = {}


def _json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _gravar(p, d):
    p = Path(p)
    tmp = p.with_name(p.name + "." + token_hex(5) + ".tmp")
    try:
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        for tentativa in range(10):
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if tentativa == 9:
                    raise
                time.sleep(0.16 * (tentativa + 1))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _pasta(job):
    if not re.fullmatch(r"rm_\d{8}_\d{6}_[a-f0-9]{6}", job):
        raise ValueError("Identificador inválido")
    p = RESULTADOS / job
    if not p.is_dir():
        raise ValueError("Projeto não encontrado")
    return p


def _motor_ocupado():
    # Inclui execução do painel experimental, sem depender de psutil instalado.
    if os.name != "nt":
        return False
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { ($_.Name -match 'python' -and $_.CommandLine -match 'robo[.]py|runner[.]py|legado_remotion[.]py') -or ($_.Name -match 'node' -and $_.CommandLine -match 'remotion.*render|remotion-cli[.]js.*render') } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=10
        )
        return bool(ps.stdout.strip())
    except Exception:
        return True  # na dúvida, não iniciar outra renderização


def _em_execucao():
    return any(t.is_alive() for t in ativos.values())


def _bloquear_destino(p):
    texto = str(p).replace("/", "\\").lower()
    restritos = ("postador", "onedrive", "meu drive", "google drive",
                 "\\prontos\\", "\\entrada\\", "com_jesus", "hermes")
    if any(x in texto for x in restritos):
        raise ValueError("Pasta de saída potencialmente monitorada ou de outro projeto")
    if p == Path(p.anchor):
        raise ValueError("Escolha uma subpasta, não a raiz do disco")


def _progresso(p, estado):
    log = JOBS_MOTOR / p.name / "robo.log"
    textos = []
    if log.exists():
        textos.extend(log.read_text(encoding="utf-8", errors="replace").splitlines()[-16:])
    eng = JOBS_MOTOR / p.name
    for sub in sorted(eng.rglob("robo.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:3] if eng.is_dir() else []:
        if sub == log:
            continue
        textos.extend(sub.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
    etapa = estado.get("etapa", "Aguardando")
    ultimos = [x for x in textos if "== " in x or "parte " in x.lower()]
    if ultimos and estado.get("status") not in ("concluido", "erro", "interrompido"):
        etapa = ultimos[-1].split("] ", 1)[-1].replace("== ", "")
    marcadores = ("sondagem", "transcricao", "edição", "montagem", "plano", "render", "QA")
    n = 0
    for indice, chave in enumerate(marcadores, 1):
        if any(chave.lower() in x.lower() for x in textos):
            n = max(n, indice)
    return {"etapa": etapa, "fase": n, "total_fases": len(marcadores),
            "registro": textos[-30:]}


def _coletar(p, estado):
    origem = JOBS_MOTOR / p.name
    arquivos = []
    for src in origem.rglob("*"):
        if not src.is_file():
            continue
        if src.suffix.lower() == ".mp4" and (
            "CORTE" in src.name or "YOUTUBE_" in src.name
        ) and "public" not in src.parts:
            grupo = "verticais" if "CORTE" in src.name else "horizontais"
            destino = p / "videos" / grupo / src.name
        elif src.suffix.lower() == ".srt":
            destino = p / "legendas" / src.name
        elif src.name in ("qa.json", "plano.json", "CREDITOS_E_LICENCAS.md", "mapa.json", "tempos.json"):
            rel = src.relative_to(origem)
            destino = p / "relatorios" / rel
        else:
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, destino)
        if destino.suffix.lower() in (".mp4", ".srt"):
            arquivos.append({"nome": destino.name, "url": "/api/remotion/media/" + p.name + "/" + destino.relative_to(p).as_posix(),
                             "grupo": destino.parent.name})
    if not any(x["nome"].endswith(".mp4") for x in arquivos):
        raise RuntimeError("O motor terminou sem gerar MP4. Consulte os registros.")
    estado["arquivos"] = arquivos
    if estado.get("origem_nuvem") or estado.get("exportar_drive"):
        _exportar_nuvem(p, estado)
    custom = estado.get("destino_externo")
    if custom:
        base = Path(custom) / p.name
        _bloquear_destino(base)
        for f in arquivos:
            local = p / f["url"].split("/" + p.name + "/", 1)[1]
            dst = base / local.relative_to(p)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, dst)
        estado["exportado_para"] = str(base)


def _executar(p):
    st = _json(p / "status.json", {})
    try:
        st.update(status="executando", erro=None, etapa="Inicializando motor")
        _gravar(p / "status.json", st)
        flags = ["--saidas", st["saida_motor"], "--cortes", str(st["cortes"]),
                 "--alvo", str(st["alvo"]), "--nome", p.name]
        if st["inicio"] > 0:
            flags += ["--inicio", str(st["inicio"])]
        if st["fim"] > 0:
            flags += ["--fim", str(st["fim"])]
        if not st["permitir_online"]:
            flags += ["--sem-ia"]
        if st.get("modo_render") == "hibrido":
            flags += ["--hibrido"]
        cmd = [str(PY_MOTOR), "-u", str(HERE / "runner.py"), st["origem"], *flags]
        env = dict(os.environ, PYTHONUTF8="1", NATINHA_REMOTION_OFFLINE="0" if st["permitir_online"] else "1")
        with open(p / "execucao.log", "a", encoding="utf-8") as out:
            out.write("\n=== INICIO " + datetime.now().isoformat() + " ===\n")
            out.flush()
            creation = subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 0
            proc = subprocess.Popen(cmd, cwd=str(MOTOR), stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=subprocess.STDOUT, env=env, creationflags=creation)
            st["pid"] = proc.pid
            _gravar(p / "status.json", st)
            retorno = proc.wait()
        if retorno:
            raise RuntimeError("O motor terminou com código " + str(retorno) + ". Consulte o registro.")
        st["etapa"] = "Organizando resultados"
        _gravar(p / "status.json", st)
        _coletar(p, st)
        st.update(status="concluido", etapa="Prévia disponível para aprovação", terminado=datetime.now().isoformat())
    except Exception as e:
        st.update(status="erro", erro=str(e), etapa="Falha isolada do Remotion")
    finally:
        _gravar(p / "status.json", st)


@bp.get("/remotion")
def painel():
    return send_from_directory(str(HERE), "painel.html")


@bp.get("/api/remotion/capacidades")
def capacidades():
    return jsonify(pacote_cinematografico=True, hibrido_beta=True,
                   saidas=["yt_broll", "cortes"], max_cortes=3,
                   aviso_hibrido="Experimental: Remotion apenas em cenas-chave; resultado sujeito à revisão")


@bp.get("/api/remotion/jobs")
def listar():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    dados = []
    for p in sorted(RESULTADOS.glob("rm_*"), reverse=True)[:30]:
        if p.is_dir():
            s = _json(p / "status.json", {})
            dados.append({k: s.get(k) for k in ("id", "status", "formato", "estilo", "etapa", "criado")})
    return jsonify(dados)


@bp.post("/api/remotion/jobs")
def iniciar():
    with lock:
        if _em_execucao() or _motor_ocupado():
            return jsonify(erro="Há uma edição cinematográfica em andamento. Aguarde a conclusão."), 409
        if not MOTOR.is_dir() or not PY_MOTOR.is_file():
            return jsonify(erro="Motor Remotion ou Python experimental indisponível."), 503
        formato = request.form.get("formato", "9x16")
        estilo = request.form.get("estilo", "completo")
        if formato not in ("9x16", "16x9", "pacote", "hibrido") or estilo not in ("completo", "limpo"):
            return jsonify(erro="Formato ou estilo inválido."), 400
        if formato == "9x16" and estilo == "limpo":
            return jsonify(erro="O motor atual ainda não oferece cortes verticais limpos testados."), 400
        if formato in ("pacote", "hibrido") and estilo != "completo":
            return jsonify(erro="O pacote cinematográfico exige o estilo completo."), 400
        try:
            cortes = int(request.form.get("cortes", 1))
            alvo = int(request.form.get("alvo", 45))
            inicio = float(request.form.get("inicio", 0))
            fim = float(request.form.get("fim", 0))
        except ValueError:
            return jsonify(erro="Informe números válidos."), 400
        if cortes not in (1, 2, 3) or not 15 <= alvo <= 600 or inicio < 0 or fim < 0 or (fim and fim <= inicio):
            return jsonify(erro="Quantidade, duração ou trecho inválido."), 400
        arquivo = request.files.get("video")
        caminho = request.form.get("caminho", "").strip().strip('"')
        if not arquivo and not caminho:
            return jsonify(erro="Selecione um arquivo ou informe o caminho no PC."), 400
        if arquivo and Path(arquivo.filename).suffix.lower() not in EXT:
            return jsonify(erro="Formato de vídeo não suportado."), 400
        if not arquivo:
            src = Path(caminho)
            if not src.is_file() or src.suffix.lower() not in EXT:
                return jsonify(erro="Vídeo não encontrado ou extensão não suportada."), 400
        destino = request.form.get("destino", "").strip().strip('"')
        if destino:
            try:
                if not Path(destino).is_absolute():
                    raise ValueError("Informe o caminho completo da pasta")
                dd = Path(destino).resolve()
                _bloquear_destino(dd)
            except (OSError, ValueError) as e:
                return jsonify(erro=str(e)), 400
        else:
            dd = None
        livre = shutil.disk_usage(RESULTADOS.parent if RESULTADOS.parent.exists() else ROOT).free
        reserva_gb = 4 if formato == "hibrido" else (6 if formato == "pacote" else 3)
        if livre < reserva_gb * 1024 ** 3:
            return jsonify(erro=f"Pouco espaço no disco para este modo. Deixe pelo menos {reserva_gb} GB livres."), 507
        if arquivo and request.content_length and request.content_length * 2 > livre - reserva_gb * 1024 ** 3:
            return jsonify(erro="O upload deixaria o disco sem espaço para renderizar. Use o caminho local."), 507
        nome = "rm_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + token_hex(3)
        p = RESULTADOS / nome
        p.mkdir(parents=True)
        if arquivo:
            entrada = p / "entrada"
            entrada.mkdir()
            src = entrada / ("original" + Path(arquivo.filename).suffix.lower())
            arquivo.save(src)
        st = {"id": nome, "origem": str(src), "status": "fila", "formato": formato, "estilo": estilo,
              "cortes": cortes if formato in ("9x16", "pacote", "hibrido") else 1, "alvo": alvo, "inicio": inicio, "fim": fim,
              "permitir_online": request.form.get("permitir_online") == "sim", "destino_externo": str(dd) if dd else None,
              "saida_motor": "yt_broll,cortes" if formato in ("pacote", "hibrido") else ("cortes" if formato == "9x16" else ("yt" if estilo == "limpo" else "yt_broll")),
              "modo_render": "hibrido" if formato == "hibrido" else "remotion",
              "criado": datetime.now().isoformat(), "etapa": "Na fila", "arquivos": []}
        # Edições iniciadas pelo painel também retornam automaticamente a prontos.
        from nucleo.util import pasta_nuvem
        base_drive = pasta_nuvem()
        if base_drive:
            st["exportar_drive"] = True
            st["destino_nuvem"] = str(Path(base_drive) / "prontos" /
                (datetime.now().strftime("%Y-%m-%d") + " - Painel Natinha - " + nome))
        _gravar(p / "status.json", st)
        t = threading.Thread(target=_executar, args=(p,), daemon=True)
        ativos[nome] = t
        t.start()
        return jsonify(id=nome), 202


@bp.get("/api/remotion/jobs/<nome>")
def acompanhar(nome):
    try:
        p = _pasta(nome)
    except ValueError:
        return jsonify(erro="Projeto não encontrado"), 404
    st = _json(p / "status.json", {})
    if st.get("status") == "executando" and not (nome in ativos and ativos[nome].is_alive()):
        st.update(status="interrompido", erro="Editor reiniciado ou execução interrompida. Use Retomar.")
        _gravar(p / "status.json", st)
    st.update(_progresso(p, st))
    log = p / "execucao.log"
    if log.exists():
        st["registro"] = (st.get("registro") or []) + log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
    log_legado = p / "integracao.log"
    if log_legado.exists():
        st["registro"] = (st.get("registro") or []) + log_legado.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
    return jsonify(st)


@bp.post("/api/remotion/jobs/<nome>/retomar")
def retomar(nome):
    try:
        p = _pasta(nome)
    except ValueError:
        return jsonify(erro="Projeto não encontrado"), 404
    with lock:
        st = _json(p / "status.json", {})
        if st.get("status") == "concluido":
            return jsonify(erro="Projeto já concluído."), 409
        if _em_execucao() or _motor_ocupado():
            return jsonify(erro="Existe uma edição em andamento."), 409
        if st.get("estilo") == "natinha_original+remotion":
            target, args = RUNNER_LEGADO, (p, st["origem_editor"], int(st["corte_original"]))
        else:
            target, args = _executar, (p,)
        t = threading.Thread(target=target, args=args, daemon=True)
        ativos[nome] = t
        t.start()
    return jsonify(ok=True)


@bp.get("/api/remotion/media/<nome>/<path:arquivo>")
def media(nome, arquivo):
    try:
        p = _pasta(nome)
    except ValueError:
        return jsonify(erro="Projeto não encontrado"), 404
    if not arquivo.startswith(("videos/", "legendas/")):
        return jsonify(erro="Arquivo não disponível."), 404
    return send_from_directory(str(p), arquivo, conditional=True)


@bp.post("/api/remotion/jobs/<nome>/abrir")
def abrir(nome):
    try:
        p = _pasta(nome)
    except ValueError:
        return jsonify(erro="Projeto não encontrado"), 404
    if os.name == "nt":
        os.startfile(str(p))
    return jsonify(ok=True, pasta=str(p))


# Rotas adicionais: reutilizam os artefatos e a seleção do editor original.
from .legado_api import registrar as _registrar_legado
RUNNER_LEGADO = _registrar_legado(bp, ROOT, RESULTADOS, PY_MOTOR, HERE, lock, ativos, _motor_ocupado)


# === Entrada automatica do Drive: mantida fora das rotas de upload manuais. ===
def _exportar_nuvem(p, estado):
    """Publica um conjunto completo, nunca MP4 parcial, na pasta prontos do rclone."""
    import tempfile
    destino = Path(estado["destino_nuvem"]).resolve()
    prontos = destino.parent
    prontos.mkdir(parents=True, exist_ok=True)
    if destino.is_dir() and (destino / "ENTREGA_NATINHA.json").is_file():
        estado["exportado_para"] = str(destino)
        return
    # Diretório temporário FORA de prontos: a sincronização só vê o pacote pronto.
    with tempfile.TemporaryDirectory(prefix="_preparando_natinha_" + p.name + "_",
                                     dir=str(prontos.parent)) as stage_name:
        stage = Path(stage_name)
        incluidos = []
        for arquivo in estado.get("arquivos", []):
            src = (p / arquivo["url"].split("/" + p.name + "/", 1)[1]).resolve()
            if not src.is_file() or p.resolve() not in src.parents:
                raise RuntimeError("Arquivo de resultado inválido para exportação")
            grupo = ("YouTube" if arquivo["grupo"] == "horizontais"
                     else "Cortes" if arquivo["grupo"] == "verticais" else "Legendas")
            dst = stage / grupo / arquivo["nome"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            incluidos.append({"arquivo": str(dst.relative_to(stage)),
                              "bytes": dst.stat().st_size})
        if not any(x["arquivo"].lower().endswith(".mp4") for x in incluidos):
            raise RuntimeError("Não existem vídeos prontos para enviar ao Drive")
        manifest = {"projeto": p.name,
                    "tipo": estado.get("formato"),
                    "origem": estado.get("arquivo_original"),
                    "status": "PREVIAS_PARA_REVISAO",
                    "videos_e_legendas": incluidos,
                    "finalizado": datetime.now().isoformat()}
        (stage / "ENTREGA_NATINHA.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        if destino.exists():
            raise RuntimeError("A pasta final já existe, mas não possui manifesto validado")
        os.replace(stage, destino)
    estado["exportado_para"] = str(destino)


def iniciar_job_drive(caminho, opcoes, base, slug):
    """Admite um arquivo local estável da pasta entrada, sem render concorrente."""
    caminho, base = Path(caminho), Path(base)
    modo = opcoes["modo"]
    formato = {"vertical": "9x16", "youtube": "16x9", "pacote": "pacote", "hibrido": "hibrido"}[modo]
    cortes = int(opcoes["cortes"])
    alvo = int(opcoes["alvo"])
    estilo = str(opcoes["estilo"]) if modo == "youtube" else "completo"
    with lock:
        if _em_execucao() or _motor_ocupado():
            raise RuntimeError("Motor cinematográfico ocupado. O arquivo permanece na entrada")
        if not caminho.is_file() or caminho.suffix.lower() not in EXT:
            raise RuntimeError("Vídeo incompatível com o motor Remotion")
        if not MOTOR.is_dir() or not PY_MOTOR.is_file():
            raise RuntimeError("Motor cinematográfico indisponível")
        livre = shutil.disk_usage(ROOT).free
        reserva = 4 if modo == "hibrido" else (6 if modo == "pacote" else 3)
        if livre < reserva * 1024 ** 3:
            raise RuntimeError(f"Espaço insuficiente para editar via Drive: mínimo {reserva} GB livres")
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        job_id = "rm_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + token_hex(3)
        p = RESULTADOS / job_id
        p.mkdir()
        entrada = p / "entrada"
        entrada.mkdir()
        destino_bruto = entrada / ("original" + caminho.suffix.lower())
        # Não duplica o bruto. Se o status falhar, devolve o arquivo para a entrada.
        try:
            shutil.move(str(caminho), str(destino_bruto))
            final = base / "prontos" / (
                datetime.now().strftime("%Y-%m-%d") + " - " + slug + " - " + job_id[-6:])
            estado = {"id": job_id, "origem": str(destino_bruto), "arquivo_original": caminho.name,
                      "origem_nuvem": True, "destino_nuvem": str(final),
                      "status": "fila", "formato": formato, "estilo": estilo,
                      "cortes": cortes if modo in ("vertical", "pacote", "hibrido") else 1, "alvo": alvo,
                      "inicio": 0, "fim": 0, "permitir_online": bool(opcoes["permitir_online"]),
                      "destino_externo": None,
                      "modo_render": "hibrido" if modo == "hibrido" else "remotion",
                      "saida_motor": ("yt_broll,cortes" if modo in ("pacote", "hibrido") else
                                      "cortes" if modo == "vertical" else
                                      "yt" if estilo == "limpo" else "yt_broll"),
                      "criado": datetime.now().isoformat(), "etapa": "Na fila", "arquivos": []}
            _gravar(p / "status.json", estado)
        except Exception:
            if destino_bruto.exists() and not caminho.exists():
                shutil.move(str(destino_bruto), str(caminho))
            raise
        thread = threading.Thread(target=_executar, args=(p,), daemon=True)
        ativos[job_id] = thread
        thread.start()
        return job_id


def retomar_job_drive(p):
    p = Path(p)
    with lock:
        if _em_execucao() or _motor_ocupado():
            return False
        st = _json(p / "status.json", {})
        if not st.get("origem_nuvem") or st.get("status") not in ("fila", "interrompido"):
            return False
        if not Path(st.get("origem", "")).is_file():
            return False
        thread = threading.Thread(target=_executar, args=(p,), daemon=True)
        ativos[p.name] = thread
        thread.start()
        return True
