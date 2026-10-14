"""Editor Natinha — interface local no navegador (http://localhost:7860)."""
import json, os, re, shutil, threading, time, webbrowser
from flask import Flask, jsonify, request, send_from_directory, abort, Response
from nucleo.util import PROJETOS, RAIZ, ler_config, salvar_config, PADRAO, pasta_nuvem, VERSOES
from nucleo import pipeline

app = Flask(__name__)
# Módulo Remotion isolado: registro aditivo, sem alterar as rotas antigas.
from integracoes.remotion.bridge import bp as remotion_bp
app.register_blueprint(remotion_bp)
from integracoes.drive_automacao import bp as drive_bp, vigiar_integrado
app.register_blueprint(drive_bp)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 ** 3
os.makedirs(PROJETOS, exist_ok=True)
TRABALHOS = {}


def _slug(s):
    s = re.sub(r"[^\w\-]+", "_", os.path.splitext(os.path.basename(s))[0]).strip("_")
    return (s or "video")[:40]


def _rodar(nome, fn, *a):
    if TRABALHOS.get(nome) and TRABALHOS[nome].is_alive():
        return False
    def com_versao():                     # refazer/remontar usam a mesma versão escolhida para o vídeo
        from nucleo.util import usar_versao
        pj = _j(os.path.join(PROJETOS, os.path.basename(nome), "projeto.json"), {})
        usar_versao(pj.get("versao") or ler_config(sem_versao=True).get("versao_padrao", "v3.1"))
        try:
            fn(*a)
        finally:
            usar_versao(None)
    t = threading.Thread(target=com_versao, daemon=True)
    TRABALHOS[nome] = t
    t.start()
    return True


def _proj(nome):
    p = os.path.join(PROJETOS, os.path.basename(nome))
    if not os.path.isdir(p):
        abort(404)
    return p


def _j(p, padrao=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return padrao


VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp")


def ip_local():
    import socket
    try:
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.connect(("8.8.8.8", 80))   # não envia nada; só descobre o IP do PC na rede de casa
        ip = s_.getsockname()[0]
        s_.close()
        return ip
    except Exception:
        return None


def _algum_rodando():
    return any(t.is_alive() for t in TRABALHOS.values())


def vigiar_nuvem():
    """A cada 20 s olha a pasta 'entrada' do OneDrive. Vídeo novo (já baixado por completo) vira projeto."""
    import shutil
    vistos = {}
    while True:
        try:
            # continua sozinho um vídeo do celular que ficou pela metade (ex.: o editor reiniciou no meio)
            if not _algum_rodando():
                for n in sorted(os.listdir(PROJETOS)):
                    p = os.path.join(PROJETOS, n)
                    pj, est = _j(os.path.join(p, "projeto.json"), {}), _j(os.path.join(p, "estado.json"), {})
                    if pj and pj.get("origem") == "nuvem" and not est.get("pronto") and not est.get("erro"):
                        print(f"Continuando o vídeo {n}")
                        _rodar(n, pipeline.processar, p)
                        break
            base = pasta_nuvem()
            if base:
              for sub, tipo in (("entrada", None), ("entrada_vertical", "vertical")):
                ent = os.path.join(base, sub)
                if not os.path.isdir(ent):
                    continue
                for f in sorted(os.listdir(ent)):
                    cam = os.path.join(ent, f)
                    if not (os.path.isfile(cam) and f.lower().endswith(VIDEO_EXT)):
                        continue
                    tam = os.path.getsize(cam)
                    if vistos.get(cam) != tam or tam == 0:   # ainda sincronizando: espera o tamanho parar
                        vistos[cam] = tam
                        continue
                    if _algum_rodando():
                        continue                             # um vídeo de cada vez
                    nome = _slug(f) + time.strftime("_%d%m_%H%M")
                    p = os.path.join(PROJETOS, nome)
                    os.makedirs(p, exist_ok=True)
                    destino = os.path.join(p, "bruto" + os.path.splitext(f)[1].lower())
                    shutil.move(cam, destino)
                    vistos.pop(cam, None)
                    pj = {"nome": nome, "bruto": destino, "origem": "nuvem",
                          "versao": ler_config(sem_versao=True).get("versao_padrao", "v3.1"),
                          "exportar_para": os.path.join(base, "prontos", _slug(f))}
                    if tipo == "vertical":               # já é vertical: não gira e não vira YouTube
                        pj.update(tipo="vertical", girar=0)
                    json.dump(pj, open(os.path.join(p, "projeto.json"), "w", encoding="utf-8"), ensure_ascii=False)
                    print(f"Vídeo novo vindo do celular{' (vertical)' if tipo else ''}: {f}")
                    _rodar(nome, pipeline.processar, p)
        except Exception as e:
            print("vigia da nuvem:", e)
        time.sleep(20)


def _rclone():
    exe = os.path.join(RAIZ, "rclone", "rclone.exe" if os.name == "nt" else "rclone")
    return exe if os.path.exists(exe) else None


def sincronizar_drive():
    """Google Drive sem instalar nada: a cada minuto o rclone (pasta rclone\\ do editor) traz os vídeos de
    '<drive_remoto>/entrada' para a pasta local 'entrada' e manda a pasta 'prontos' de volta para o Drive."""
    import subprocess
    while True:
        try:
            c = ler_config()
            remoto, base, exe = c.get("drive_remoto"), pasta_nuvem(), _rclone()
            if remoto and base and exe:
                conf = ["--config", os.path.join(RAIZ, "rclone", "rclone.conf")]
                kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
                for args in (["move", remoto.rstrip("/") + "/entrada", os.path.join(base, "entrada"), "--min-age", "20s"],
                             ["mkdir", remoto.rstrip("/") + "/entrada_vertical"],     # cria a pasta no Drive
                             ["move", remoto.rstrip("/") + "/entrada_vertical", os.path.join(base, "entrada_vertical"),
                              "--min-age", "20s"],
                             ["copy", os.path.join(base, "prontos"), remoto.rstrip("/") + "/prontos"]):
                    r = subprocess.run([exe, *args, *conf, "--retries", "3"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", **kw)
                    if r.returncode != 0:
                        print("Google Drive:", r.stderr[-300:])
        except Exception as e:
            print("Google Drive:", e)
        time.sleep(60)


@app.get("/api/acesso")
def acesso():
    porta = int(os.environ.get("PORTA", 7860))
    ip = ip_local() if ler_config().get("acesso_celular", True) else None
    return jsonify(celular=f"http://{ip}:{porta}" if ip else None, nuvem=pasta_nuvem())


@app.get("/")
def index():
    return Response(open(os.path.join(RAIZ, "interface.html"), encoding="utf-8").read(), mimetype="text/html")


def _titulo_proj(p):
    """Nome do vídeo pela descrição (título que a IA escreveu); se ainda não tem, fica vazio."""
    t = (_j(os.path.join(p, "youtube_meta.json"), {}) or {}).get("titulo") or ""
    if not t:
        info = os.path.join(p, "youtube_info.txt")
        if os.path.exists(info):
            t = open(info, encoding="utf-8").read().strip().split("\n")[0]
    if not t:
        cs = _j(os.path.join(p, "cortes.json"), [])
        t = cs[0].get("titulo", "") if cs else ""
    t = " ".join(str(t).split())
    return t[:80] + ("…" if len(t) > 80 else "")


def _data_proj(p):
    """Data e hora em que o vídeo foi enviado (criação do projeto)."""
    arq = os.path.join(p, "projeto.json")
    try:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getctime(arq if os.path.exists(arq) else p)))
    except OSError:
        return ""


@app.get("/api/projetos")
def projetos():
    out = []
    for n in sorted(os.listdir(PROJETOS), key=lambda x: -os.path.getmtime(os.path.join(PROJETOS, x))):
        p = os.path.join(PROJETOS, n)
        if os.path.isdir(p):
            est = _j(os.path.join(p, "estado.json"), {})
            out.append({"nome": n, "etapa": est.get("etapa"), "pct": est.get("pct", 0), "erro": est.get("erro"),
                        "pronto": est.get("pronto", False), "titulo": _titulo_proj(p), "data": _data_proj(p)})
    return jsonify(out)


@app.post("/api/enviar")
def enviar():
    f = request.files.get("video")
    caminho = request.form.get("caminho", "").strip().strip('"')
    if not f and not caminho:
        return jsonify(erro="Envie um vídeo ou cole o caminho do arquivo"), 400
    base = _slug(f.filename if f else caminho)
    nome = base + time.strftime("_%d%m_%H%M")
    p = os.path.join(PROJETOS, nome)
    os.makedirs(p, exist_ok=True)
    if f:
        destino = os.path.join(p, "bruto" + os.path.splitext(f.filename)[1].lower())
        f.save(destino)
    else:
        if not os.path.exists(caminho):
            return jsonify(erro="Arquivo não encontrado: " + caminho), 400
        destino = caminho
    versao = request.form.get("versao", "").strip()
    if versao not in VERSOES:
        versao = ler_config(sem_versao=True).get("versao_padrao", "v3.1")
    dados = {"nome": nome, "bruto": destino, "versao": versao}
    base_drive = pasta_nuvem()
    if base_drive:
        dados["exportar_para"] = os.path.join(base_drive, "prontos", nome)
    json.dump(dados, open(os.path.join(p, "projeto.json"), "w", encoding="utf-8"), ensure_ascii=False)
    _rodar(nome, pipeline.processar, p)
    return jsonify(nome=nome)


@app.get("/api/projeto/<nome>")
def projeto(nome):
    p = _proj(nome)
    est = _j(os.path.join(p, "estado.json"), {})
    est["rodando"] = bool(TRABALHOS.get(nome) and TRABALHOS[nome].is_alive())
    est["nome"] = nome
    est["youtube"] = os.path.exists(os.path.join(p, "youtube.mp4"))
    est["youtube_imagens"] = os.path.exists(os.path.join(p, "youtube_com_imagens.mp4"))
    est["insercoes"] = _j(os.path.join(p, "insercoes.json"), [])
    info = os.path.join(p, "youtube_info.txt")
    est["youtube_info"] = open(info, encoding="utf-8").read() if os.path.exists(info) else ""
    cortes = _j(os.path.join(p, "cortes.json"), [])
    for c in cortes:
        pc = os.path.join(p, f"corte_{c['n']}")
        arq = c.get("arquivo_final", f"corte_{c['n']}.mp4")
        c["video"] = f"corte_{c['n']}/{arq}" if os.path.exists(os.path.join(pc, arq)) else None
        c["brolls"] = _j(os.path.join(pc, "brolls.json"), [])
        for b in c["brolls"]:
            b["video"] = f"corte_{c['n']}/{b['arquivo']}" if os.path.exists(os.path.join(pc, b["arquivo"])) else None
    est["cortes"] = cortes
    return jsonify(est)


@app.post("/api/projeto/<nome>/refazer_imagens")
def refazer_imagens(nome):
    p = _proj(nome)
    return jsonify(ok=_rodar(nome, pipeline.refazer_imagens, p))


@app.post("/api/projeto/<nome>/continuar")
def continuar(nome):
    p = _proj(nome)
    return jsonify(ok=_rodar(nome, pipeline.processar, p))


@app.post("/api/projeto/<nome>/refazer")
def refazer(nome):
    p = _proj(nome)
    d = request.get_json(force=True)
    return jsonify(ok=_rodar(nome, pipeline.refazer_broll, p, int(d["corte"]), int(d["broll"]), d.get("pedido", "")))


@app.post("/api/projeto/<nome>/tirar")
def tirar(nome):
    p = _proj(nome)
    d = request.get_json(force=True)
    return jsonify(ok=_rodar(nome, pipeline.tirar_broll, p, int(d["corte"]), int(d["broll"])))


@app.get("/api/projeto/<nome>/miniatura")
def miniatura(nome):
    from nucleo.util import FFMPEG
    import subprocess
    p = _proj(nome)
    proj = _j(os.path.join(p, "projeto.json"), {})
    giro = {90: "transpose=1,", -90: "transpose=2,", 180: "hflip,vflip,"}.get(int(proj.get("girar", 0)), "")
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", "3", "-i", proj["bruto"], "-frames:v", "1",
                        "-vf", giro + "scale=480:-2", "-f", "image2", "-c:v", "mjpeg", "-"], capture_output=True)
    return Response(r.stdout, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/projeto/<nome>/girar")
def girar(nome):
    p = _proj(nome)
    d = request.get_json(force=True)
    proj = _j(os.path.join(p, "projeto.json"), {})
    novo = (int(proj.get("girar", 0)) + int(d["graus"]) + 180) % 360 - 180
    if novo == -180:
        novo = 180
    return jsonify(ok=_rodar(nome, pipeline.girar, p, novo), girar=novo)


@app.get("/arquivo/<nome>/<path:arq>")
def arquivo(nome, arq):
    p = _proj(nome)
    return send_from_directory(p, arq, conditional=True)


@app.post("/api/projeto/<nome>/abrir")
def abrir_pasta(nome):
    p = _proj(nome)
    if os.name == "nt":
        os.startfile(p)
    return jsonify(ok=True, pasta=p)


@app.get("/api/versoes")
def versoes():
    return jsonify(lista=[{"id": k, "nome": v[0]} for k, v in VERSOES.items()],
                   padrao=ler_config(sem_versao=True).get("versao_padrao", "v3.1"))


@app.get("/api/config")
def get_config():
    c = ler_config(sem_versao=True)
    for k in ("gemini_chave", "pexels_chave", "pixabay_chave"):
        c[k] = ("•" * 8 + c[k][-4:]) if c.get(k) else ""
    return jsonify(c)


@app.post("/api/config")
def set_config():
    c = ler_config(sem_versao=True)
    d = request.get_json(force=True)
    for k, v in d.items():
        if k not in PADRAO:
            continue
        if k in ("gemini_chave", "pexels_chave", "pixabay_chave") and (not v or v.startswith("•")):
            continue
        if isinstance(PADRAO[k], bool):
            v = v not in ("", "0", "false", False, None)
        elif isinstance(PADRAO[k], int):
            v = int(v)
        elif isinstance(PADRAO[k], float):
            v = float(v)
        c[k] = v
    salvar_config(c)
    return jsonify(ok=True)


if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", 7860))
    if not os.environ.get("SEM_NAVEGADOR"):
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{porta}")).start()
    celular = ler_config().get("acesso_celular", True)
    print(f"Editor Natinha rodando em http://localhost:{porta}  (feche esta janela para desligar)")
    if celular and ip_local():
        print(f"No celular (mesmo Wi-Fi): http://{ip_local()}:{porta}")
    nv = pasta_nuvem()
    if nv:
        print(f"Pasta do celular (OneDrive): {nv}")
        threading.Thread(target=vigiar_integrado,
                         args=(_algum_rodando, _rodar, _slug, _j, VIDEO_EXT),
                         daemon=True).start()
        if ler_config().get("drive_remoto"):
            print(f"Google Drive ligado: {ler_config()['drive_remoto']} (entrada / prontos)")
            threading.Thread(target=sincronizar_drive, daemon=True).start()
    app.run(host="0.0.0.0" if celular else "127.0.0.1", port=porta, threaded=True)
