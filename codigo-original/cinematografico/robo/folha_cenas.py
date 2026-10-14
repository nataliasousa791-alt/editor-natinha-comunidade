"""Folha de controle: 1 quadro no meio de cada cena do plano (+ trechos só com rosto), lido do MP4 final ou das partes prontas.
Uso: python folha_cenas.py <pasta_da_saida> [colunas]"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")
D = sys.argv[1]; cols = int(sys.argv[2]) if len(sys.argv) > 2 else 4
p = json.load(open(os.path.join(D, "plano.json"), encoding="utf-8"))
vert = p.get("formato", "9x16") == "9x16"; tw, th = (240, 426) if vert else (480, 270)
mp4s = [os.path.join(D, f) for f in os.listdir(D) if f.endswith(".mp4") and ("CORTE" in f or "YOUTUBE" in f)]
pd = os.path.join(D, "partes")
partes = sorted(os.path.join(pd, f) for f in os.listdir(pd) if f.endswith(".mp4")) if os.path.isdir(pd) else []
cen = p.get("cenas", [])
tempos = [(round(1.6 if c["tipo"] == "abertura" else (c["ini"] + c["fim"]) / 2, 2), c["tipo"]) for c in cen]
lim = [0.0] + [c["fim"] for c in cen]; ini = [c["ini"] for c in cen] + [p["frames"] / p["fps"]]
tempos += [(round((a + b) / 2, 2), "rosto") for a, b in zip(sorted(lim), sorted(ini)) if b - a > 4]
ims = []
for t, tipo in sorted(set(tempos)):
    if mp4s: src, tt = mp4s[0], t
    else:
        k = int(t // 30)
        if k >= len(partes): continue
        src, tt = partes[k], t - k * 30
    out = os.path.join(D, f"_q_{t:07.2f}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.2f}", "-i", src, "-frames:v", "1", "-vf", f"scale={tw}:{th}", out])
    if os.path.exists(out):
        im = Image.open(out).convert("RGB"); d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 150, 22], fill=(0, 0, 0)); d.text((5, 5), f"{t:.1f}s {tipo}", fill=(255, 220, 0))
        ims.append(im); os.remove(out)
lin = max(1, -(-len(ims) // cols))
folha = Image.new("RGB", (tw * cols, th * lin))
for i, im in enumerate(ims): folha.paste(im, ((i % cols) * tw, (i // cols) * th))
folha.save(os.path.join(D, "folha_cenas.jpg"), quality=85)
print("folha:", len(ims), "quadros")
