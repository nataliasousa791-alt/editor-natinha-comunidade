"""Utilidades: caminhos, configuração, ffmpeg, log de progresso."""
import json, os, shutil, subprocess, sys, tempfile, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = os.path.join(RAIZ, "recursos", "fontes")
PROJETOS = os.path.join(RAIZ, "projetos")
CONFIG = os.path.join(RAIZ, "config.json")

PADRAO = {
    "gemini_chave": "",
    "gemini_modelos": ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash",
                       "gemini-flash-latest", "gemini-3.5-flash-lite"],
    "openai_compat_url": "",          # opcional: DeepSeek, Ollama, OpenRouter… (ex.: http://localhost:11434/v1)
    "openai_compat_chave": "",
    "openai_compat_modelo": "",
    "whisper_modelo": "small",        # tiny | base | small | medium | large-v3-turbo
    "whisper_motor": "faster-whisper",  # faster-whisper | whispercpp
    "idioma": "pt",
    "n_cortes": 3,
    "corte_min": 45, "corte_max": 120,
    "brolls_por_corte": 2,            # (antigo; agora vale brolls_intervalo_corte)
    "brolls_intervalo_corte": 10,     # cortes: 1 B-roll a cada X segundos
    "animacoes_por_corte": 2,         # quantos desses são animação (o resto, vídeo real)
    "broll_engine_v2": True,          # B-roll Engine V2 (decisão editorial, templates novos). False = jeito antigo
    "nota_minima_stock": 4,           # vídeo/foto de banco só entra com nota >= 4 (de 5)
    "youtube_brolls_por_minuto": 5,   # V2: até isso por minuto no YouTube (pede pelo menos 70% disso)
    "versao_padrao": "v3.1",          # versão usada nos vídeos que chegam pelo Drive (dá para trocar no site)
    "variedade": True,                # V3.1: o editor varia as cenas (False = V3 original)
    "estetica": "nova",               # "nova" (preto + cor com função + mini cenas) ou "editorial" (V2 anterior)
    "lacuna_corte": 6.0,              # cortes: punch-in automático depois de ~6 s só no rosto
    "youtube_lacuna": 18,             # V2: punch-in automático só depois de ~18 s de rosto sem nenhuma variação
    "v2_intervalo_corte": 7,          # V2: cortes verticais: até ~8 intervenções visuais por minuto (a fala manda)
    "youtube_brolls": True,
    "youtube_gancho": True,           # YouTube: a frase mais forte aparece como prévia no começo
    "tela_final_seg": 15,             # YouTube: segundos de tela final (para os elementos "próximo vídeo"); 0 = sem
    "youtube_capas": True,            # YouTube: gerar 3 capas para o Test & Compare
    "gancho_corte_seg": 3.0,          # cortes: segundos da frase-gancho no topo + rosto de perto
    "youtube_nota_video": 4,          # YouTube: vídeo real só fica com nota >= 4 na revisão (senão vira animação)           # B-rolls também no vídeo do YouTube
    "youtube_video_intervalo": 30,    # YouTube: 1 vídeo real (tela cheia) a cada X segundos
    "youtube_animacao_intervalo": 60, # YouTube: 1 animação (painel do lado) a cada X segundos
    "cartoes_cortes": True,           # cartões (ícones + frase) em cima do vídeo nos cortes
    "cartoes_por_corte": 6,
    "formato_vertical": "faixa",      # faixa (vídeo inteiro com fundo desfocado) | recorte (preenche a tela)
    "recorte_x": 0.5,
    "legenda_cor_destaque": "#FFD23F",
    "legenda_y": 1560,
    "silencio_db": -35, "silencio_min": 0.9, "silencio_folga": 0.25,
    "preset": "medium",
    "insercoes_youtube": True,        # cartõezinhos com ícone no vídeo do YouTube
    "insercoes_quantidade": 12,       # quantas imagens no vídeo do YouTube (mais ou menos)
    "insercoes_lado": "esquerda",     # lado onde aparecem (esquerda | direita)
    "acesso_celular": True,           # deixa abrir o editor pelo celular no mesmo Wi-Fi
    "pasta_nuvem": "",                # pasta do OneDrive (vazio = OneDrive\Editor Natinha)
    "girar_vertical_auto": -90,       # vídeo em pé sem aviso de rotação: girar quantos graus (0 = não girar)
    "pexels_chave": "",               # vídeos reais grátis para B-roll (pexels.com/api)
    "pixabay_chave": "",              # vídeos reais grátis para B-roll (pixabay.com/api/docs)
    "brolls_video": True,             # usar vídeo real quando a cena pedir
    "drive_remoto": "",               # Google Drive via rclone (ex.: gdrive:Editor Natinha); vazio = desligado
    "drive_modo": "classico",         # modo da pasta entrada: classico, vertical, youtube ou pacote
    "drive_cortes": 3,
    "drive_alvo": 90,
    "drive_estilo": "completo",
    "drive_permitir_online": False,    # consulta gratuita/busca de B-roll apenas com autorizacao
}


def pasta_nuvem():
    """Pasta sincronizada (OneDrive): 'entrada' recebe vídeos do celular, 'prontos' recebe os resultados."""
    c = ler_config()
    base = c.get("pasta_nuvem") or ""
    if not base:
        od = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer") or os.path.join(os.path.expanduser("~"), "OneDrive")
        if not os.path.isdir(od):
            return None
        base = os.path.join(od, "Editor Natinha")
    for sub in ("entrada", "entrada_vertical", "prontos"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return base


# Versões do editor que dá para escolher no site (por vídeo) ou como padrão (vídeos que chegam pelo Drive).
VERSOES = {
    "v3.1": ("V3.1 — cenas com bonecos variadas", {"broll_engine_v2": True, "estetica": "nova", "variedade": True}),
    "v3": ("V3 — primeiras cenas (escada, bonecos)", {"broll_engine_v2": True, "estetica": "nova", "variedade": False}),
    "v2": ("V2 — a que você aprovou (fotos, vídeos e animações editoriais)", {"broll_engine_v2": True, "estetica": "editorial"}),
    "v1": ("V1 — motor de imagens antigo", {"broll_engine_v2": False, "estetica": "editorial"}),
}
_VERSAO_ATIVA = None


def usar_versao(v):
    """Liga a versão escolhida para o vídeo que está sendo processado (um vídeo de cada vez)."""
    global _VERSAO_ATIVA
    _VERSAO_ATIVA = v if v in VERSOES else None


def ler_config(sem_versao=False):
    c = dict(PADRAO)
    if os.path.exists(CONFIG):
        try:
            c.update(json.load(open(CONFIG, encoding="utf-8")))
        except Exception:
            pass
    if not sem_versao and _VERSAO_ATIVA in VERSOES:
        c.update(VERSOES[_VERSAO_ATIVA][1])
    return c


def salvar_config(c):
    json.dump(c, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def ffmpeg_bin(nome="ffmpeg"):
    local = os.path.join(RAIZ, "ffmpeg", "bin", nome + (".exe" if os.name == "nt" else ""))
    return local if os.path.exists(local) else (shutil.which(nome) or nome)


FFMPEG = ffmpeg_bin("ffmpeg")
FFPROBE = ffmpeg_bin("ffprobe")


def opcao_filtro_arquivo():
    """ffmpeg 7+ lê o filtro de um arquivo com '-/filter_complex'; versões antigas usam '-filter_complex_script'."""
    try:
        r = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        v = r.stdout.split()[2] if r.stdout else ""
        if v.startswith("N-") or v[:1].isdigit() and int(v.split(".")[0]) >= 7:
            return "-/filter_complex"
    except Exception:
        pass
    return "-filter_complex_script"


def run(cmd, **kw):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise RuntimeError(f"Falhou: {os.path.basename(cmd[0])}\n{r.stderr[-2500:]}")
    return r


def probe(path):
    d = json.loads(run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", path]).stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    w, h = (int(v["width"]), int(v["height"])) if v else (0, 0)
    rot = 0
    if v:
        rot = int(float(v.get("tags", {}).get("rotate", 0) or 0))
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
    if abs(rot) in (90, 270):
        w, h = h, w
    fps = 30.0
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        a, b = v["avg_frame_rate"].split("/")
        fps = float(a) / float(b) if float(b) else 30.0
    return {"dur": float(d["format"]["duration"]), "w": w, "h": h, "fps": fps,
            "audio": any(s["codec_type"] == "audio" for s in d["streams"])}


def tmpdir():
    return tempfile.mkdtemp(prefix="editor_")


class Progresso:
    """Guarda o estado do projeto em estado.json (a interface lê este arquivo)."""
    def __init__(self, pasta):
        self.arq = os.path.join(pasta, "estado.json")
        self.estado = json.load(open(self.arq, encoding="utf-8")) if os.path.exists(self.arq) else {
            "etapa": "fila", "pct": 0, "log": [], "erro": None}

    def salvar(self):
        # no Windows o arquivo pode estar aberto pela tela no mesmo instante: tenta de novo, nunca derruba o trabalho
        dados = json.dumps(self.estado, ensure_ascii=False, indent=1)
        tmp = self.arq + ".tmp"
        for _ in range(20):
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(dados)
                os.replace(tmp, self.arq)
                return
            except OSError:
                time.sleep(0.05)
        try:
            with open(self.arq, "w", encoding="utf-8") as f:
                f.write(dados)
        except OSError:
            pass

    def etapa(self, nome, pct=None):
        self.estado["etapa"] = nome
        if pct is not None:
            self.estado["pct"] = int(pct)
        self.log(nome)

    def log(self, msg):
        self.estado["log"].append(time.strftime("%H:%M:%S ") + msg)
        self.estado["log"] = self.estado["log"][-200:]
        try:
            print(msg, flush=True)
        except Exception:
            pass
        self.salvar()

    def set(self, **kw):
        self.estado.update(kw)
        self.salvar()
