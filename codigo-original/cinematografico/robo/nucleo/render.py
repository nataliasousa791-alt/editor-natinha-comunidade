"""Render Remotion em PARTES com checkpoint: empacota uma vez por job, renderiza blocos de N segundos (mudos),
pula os já prontos, concatena sem reencodar e junta a voz. Uma falha só refaz a parte que falhou."""
import os, subprocess, time
from .util import REMOTION, probe, run

NPX = "npx.cmd" if os.name == "nt" else "npx"


def _ram_livre_gb():
    try:
        import ctypes
        class M(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("c", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                        ("x1", ctypes.c_ulonglong), ("x2", ctypes.c_ulonglong), ("x3", ctypes.c_ulonglong),
                        ("x4", ctypes.c_ulonglong), ("x5", ctypes.c_ulonglong)]
        m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.a / 2**30
    except Exception:
        return 9.0


def _npx(args, log_arq):
    r = subprocess.run([NPX, "remotion", *args], cwd=REMOTION, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        open(log_arq, "w", encoding="utf-8").write((r.stderr or "") + (r.stdout or ""))
    return r.returncode == 0


def renderizar(sub, plano_json, pub, saida, frames, fps, c, log):
    t0 = time.time()
    bundle = sub.p("bundle")
    if not sub.feito("bundle"):
        if not _npx(["bundle", c.get("remotion_entrada", os.path.join("src", "robo", "index.jsx")), f"--out-dir={bundle}", f"--public-dir={pub}", "--log=error"],
                    sub.p("erro_bundle.txt")):
            raise RuntimeError("falha ao empacotar a composição (ver erro_bundle.txt)")
        sub.marcar("bundle")
    passo = int(c.get("render_parte_seg", 30) * fps)
    partes_dir = sub.p("partes"); os.makedirs(partes_dir, exist_ok=True)
    partes = []
    for k, a in enumerate(range(0, frames, passo)):
        b = min(frames, a + passo) - 1
        arq = os.path.join(partes_dir, f"parte_{k:03}.mp4"); partes.append(arq)
        if os.path.exists(arq):
            try:
                if abs(probe(arq)["dur"] - (b - a + 1) / fps) < 0.1: continue      # checkpoint válido
            except Exception: pass
        ok = False
        conc0 = c.get("render_concorrencia", 2) if _ram_livre_gb() >= 1.5 else 1   # PC com pouca RAM: 1 por vez (não trava)
        for tent, conc in enumerate((conc0, 1, 1), 1):      # V6: 3 tentativas só na parte que falhou
            if _npx(["render", bundle, c.get("remotion_comp", "Robo"), arq, f"--props={plano_json}", f"--frames={a}-{b}", "--muted", "--codec=h264",
                     "--crf=14", f"--concurrency={conc}", "--log=error"],
                    sub.p(f"erro_parte{k:03}_t{tent}.txt")):
                ok = True; break
            log(f"parte {k} falhou (tentativa {tent}, concorrência {conc})"); time.sleep(5)
        if not ok:
            raise RuntimeError(f"parte {k} falhou 2 vezes — rode de novo para retomar daqui (ver erro_parte{k:03}_*.txt)")
        log(f"parte {k + 1}/{-(-frames // passo)} pronta ({time.time() - t0:.0f}s)")
    lista = sub.p("partes.txt")
    open(lista, "w", encoding="utf-8").write("".join(f"file '{p.replace(os.sep, '/')}'\n" for p in partes))
    mudo = sub.p("video_mudo.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", mudo])
    run(["ffmpeg", "-v", "error", "-y", "-i", mudo, "-i", os.path.join(pub, "voz.m4a"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "copy", "-t", f"{frames / fps:.3f}", "-movflags", "+faststart", saida])
    return round(time.time() - t0, 1)
