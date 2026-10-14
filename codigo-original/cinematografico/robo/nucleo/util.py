"""Utilidades comuns do robô (caminhos, execução, sondagem, log, estado do job)."""
import json, os, subprocess, sys, time
ROBO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.dirname(ROBO)
REMOTION = os.path.join(PROJ, "remotion")
sys.path.insert(0, os.path.join(ROBO, "_libs"))          # OpenCV isolado do Python global


def cfg():
    return json.load(open(os.path.join(ROBO, "config_robo.json"), encoding="utf-8"))


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        raise RuntimeError(f"falhou: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r.stdout


def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd: rot = int(float(sd["rotation"]))
    rot = int(v.get("tags", {}).get("rotate", rot) or rot)
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate", "30/1")).split("/")
    return dict(w=int(v["width"]), h=int(v["height"]), sar=v.get("sample_aspect_ratio", "1:1"),
                dar=v.get("display_aspect_ratio", ""), rot=rot, fps=float(num) / float(den or 1),
                dur=float(j["format"]["duration"]), audio=a is not None, vcodec=v["codec_name"])


class Job:
    """Pasta isolada do job + log + checkpoints (estado.json)."""
    def __init__(self, pasta):
        self.pasta = pasta
        os.makedirs(pasta, exist_ok=True)
        self.arq_estado = os.path.join(pasta, "estado.json")
        self.estado = json.load(open(self.arq_estado, encoding="utf-8")) if os.path.exists(self.arq_estado) else {}
        self.t0 = time.time()

    def p(self, *n):
        return os.path.join(self.pasta, *n)

    def log(self, msg):
        linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linha, flush=True)
        open(self.p("robo.log"), "a", encoding="utf-8").write(linha + "\n")

    def feito(self, etapa):
        return self.estado.get(etapa, {}).get("ok", False)

    def marcar(self, etapa, **info):
        self.estado[etapa] = dict(ok=True, quando=time.strftime("%Y-%m-%d %H:%M:%S"), **info)
        json.dump(self.estado, open(self.arq_estado, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def salvar(self, nome, obj):
        json.dump(obj, open(self.p(nome), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def ler(self, nome):
        return json.load(open(self.p(nome), encoding="utf-8"))
