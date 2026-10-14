"""Monta o corte vertical: base 9:16 + zoom alternado nos cortes + B-rolls + legenda dinâmica + whoosh."""
import json, math, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .util import FFMPEG, FONTES, probe, run, tmpdir, ler_config

W, H, FPS = 1080, 1920, 30
BRANCO, TINTA = (255, 255, 255), (22, 15, 34)
CENTRO_FAIXA = 880


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _leitor(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _frame(p):
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3:
        return None
    return np.frombuffer(b, np.uint8).reshape(H, W, 3)


def _zoom(fr, z, centro):
    if z == 1.0:
        return fr
    cw, ch = int(W / z), int(H / z)
    x0 = int(min(max(centro[0] - cw / 2, 0), W - cw))
    y0 = int(min(max(centro[1] - ch / 2, 0), H - ch))
    return np.asarray(Image.fromarray(fr[y0:y0 + ch, x0:x0 + cw]).resize((W, H), Image.BICUBIC))


def _filtro_base(info, modo, crop_x):
    if info["h"] > info["w"]:       # já é vertical
        return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=rgb24"
    if modo == "recorte":
        return (f"crop=ih*9/16:ih:(iw-ih*9/16)*{crop_x}:0,scale={W}:{H},fps={FPS},format=rgb24")
    y = CENTRO_FAIXA - int(W * info["h"] / info["w"]) // 2
    return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=28:2,eq=brightness=-0.07:saturation=1.1[bg];[b]scale={W}:-2[fg];"
            f"[bg][fg]overlay=0:{y},fps={FPS},format=rgb24")


class Legendas:
    def __init__(self, words, cor, y):
        self.F = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), 84)
        self.cor, self.y = cor, y
        self.ch = self._chunks(words)

    def _chunks(self, ws, maxw=3, maxc=18):
        out, cur = [], []
        for i, w in enumerate(ws):
            cur.append(dict(w, txt=w["w"].upper()))
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            if (len(cur) >= maxw or sum(len(x["w"]) + 1 for x in cur) >= maxc or not nxt
                    or nxt["s"] - w["e"] > 0.35 or w["w"][-1] in ".,!?…"):
                out.append(cur)
                cur = []
        for k, c in enumerate(out):
            nxt = out[k + 1][0]["s"] if k + 1 < len(out) else c[-1]["e"] + 0.5
            fim = min(nxt, c[-1]["e"] + 0.6)
            larg = [self.F.getlength(w["txt"]) for w in c]
            total = sum(larg) + 22 * (len(c) - 1)
            if total > W - 80:   # palavra muito longa: reduz a escala do bloco
                for w in c:
                    w["esc"] = (W - 80) / total
            x = (W - min(total, W - 80)) / 2
            for w, lw in zip(c, larg):
                e = w.get("esc", 1)
                w["x"], w["wd"] = x, lw * e
                x += (lw + 22) * e
            for w in c:
                w["fim"] = fim
        return out

    def desenhar(self, frame, t):
        cur = next((c for c in self.ch if c[0]["s"] - 0.03 <= t < c[0]["fim"]), None)
        if not cur:
            return frame
        img = Image.fromarray(frame)
        ov = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        idade = t - cur[0]["s"]
        yb = 98 + int(16 * (1 - min(1, max(0, idade / 0.12))))
        al = int(255 * min(1, max(0, idade / 0.08 + 0.3)))
        ativo = None
        for i, w in enumerate(cur):
            fim = cur[i + 1]["s"] if i + 1 < len(cur) else cur[0]["fim"]
            if w["s"] <= t < fim:
                ativo = i
        for i, w in enumerate(cur):
            esc = w.get("esc", 1)
            F = self.F if esc == 1 else ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), int(84 * esc))
            if i == ativo:
                a2 = t - w["s"]
                s = (1 + 0.12 * math.exp(-a2 * 18) - 0.12 * (1 - min(1, a2 / 0.05))) * esc
                cx = w["x"] + w["wd"] / 2
                bw = w["wd"] / esc * s / 2 + 16
                d.rounded_rectangle([cx - bw, yb - 2, cx + bw, yb + 104 * s - 2], radius=18, fill=self.cor + (al,))
                fs = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), max(10, int(84 * s)))
                d.text((cx - fs.getlength(w["txt"]) / 2, yb - (s - 1) * 40), w["txt"], font=fs, fill=TINTA + (al,))
            else:
                d.text((w["x"] + 4, yb + 6), w["txt"], font=F, fill=(0, 0, 0, int(al * 0.45)))
                d.text((w["x"], yb), w["txt"], font=F, fill=BRANCO + (al,), stroke_width=7, stroke_fill=(15, 10, 25, al))
        img.paste(ov, (0, self.y - 150), ov)
        return np.asarray(img)


def _gancho_png(texto):
    """Frase-gancho grande no topo (primeiros segundos do corte): caixa roxa, texto branco, palavra-chave em amarelo."""
    texto = " ".join((texto or "").upper().split()[:6])
    if not texto:
        return None
    larg = W - 140
    tam = 96
    while True:
        F = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), tam)
        linhas, cur = [], ""
        for p in texto.split():
            t = (cur + " " + p).strip()
            if F.getlength(t) <= larg or not cur:
                cur = t
            else:
                linhas.append(cur)
                cur = p
        linhas.append(cur)
        if (len(linhas) <= 3 and max(F.getlength(l) for l in linhas) <= larg) or tam <= 56:
            break
        tam -= 6
    chave = max(texto.split(), key=len)
    alt = int(tam * 1.12)
    bw = int(max(F.getlength(l) for l in linhas)) + 70
    bh = alt * len(linhas) + 46
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=28, fill=(24, 12, 44, 225))
    y = 18
    for l in linhas:
        x = (bw - F.getlength(l)) / 2
        for p in l.split():
            d.text((x, y), p, font=F, fill=(255, 205, 60) if p == chave else (255, 255, 255))
            x += F.getlength(p + " ")
        y += alt
    return im


def _destaque_corte(texto):
    """Palavras-chave discretas no espaço de cima do corte: serifada clara + fio dourado (sem caixa)."""
    texto = " ".join(str(texto or "").split()[:5])
    if not texto:
        return None
    try:
        F = ImageFont.truetype(os.path.join(FONTES, "Lora-Variable.ttf"), 92)
        F.set_variation_by_name("SemiBold")
    except Exception:
        F = ImageFont.truetype(os.path.join(FONTES, "Poppins-Bold.ttf"), 86)
    larg = W - 160
    linhas, cur = [], ""
    for p in texto.split():
        t = (cur + " " + p).strip()
        if F.getlength(t) <= larg or not cur:
            cur = t
        else:
            linhas.append(cur)
            cur = p
    linhas.append(cur)
    linhas = linhas[:2]
    alt = int(F.size * 1.15)
    im = Image.new("RGBA", (W, alt * len(linhas) + 40), (0, 0, 0, 0))
    sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds, d = ImageDraw.Draw(sombra), ImageDraw.Draw(im)
    for i, l in enumerate(linhas):
        x = (W - F.getlength(l)) / 2
        ds.text((x + 3, i * alt + 5), l, font=F, fill=(0, 0, 0, 180))
    from PIL import ImageFilter as _IF
    im.alpha_composite(sombra.filter(_IF.GaussianBlur(6)))
    for i, l in enumerate(linhas):
        d.text(((W - F.getlength(l)) / 2, i * alt), l, font=F, fill=(250, 245, 236, 255))
    yl = alt * len(linhas) + 12
    d.rectangle([W / 2 - 60, yl, W / 2 + 60, yl + 6], fill=(242, 193, 78, 255))
    return im


def _continua_png(cor_acento):
    """'CONTINUA' discreto, na linguagem da estética nova (branco + pontos na cor principal)."""
    F = ImageFont.truetype(os.path.join(FONTES, "Poppins-Medium.ttf"), 46)
    txt = "CONTINUA"
    trk = 9
    larg = sum(F.getlength(ch) + trk for ch in txt) + 3 * 26
    im = Image.new("RGBA", (int(larg) + 40, 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 20
    for ch in txt:
        d.text((x + 2, 14), ch, font=F, fill=(0, 0, 0, 150))
        d.text((x, 12), ch, font=F, fill=(246, 244, 240, 255))
        x += F.getlength(ch) + trk
    return im, x, cor_acento


def montar(youtube_mp4, words_yt, trechos, corte, plano, pasta_corte, saida, log=print, cartoes=None):
    c = ler_config()
    info = probe(youtube_mp4)
    s, e = corte["s"], corte["e"]
    L = e - s
    n = int(round(L * FPS))
    # palavras do corte (tempo relativo)
    ws = [dict(w, s=round(w["s"] - s, 2), e=round(w["e"] - s, 2)) for w in words_yt if w["s"] >= s - 0.05 and w["e"] <= e + 0.3]
    leg = Legendas(ws, _hex(c["legenda_cor_destaque"]), int(c["legenda_y"]))
    # pontos de corte (para o zoom alternado)
    cuts, o = [], 0.0
    for a, b in trechos:
        o += b - a
        if s < o < e:
            cuts.append(o - s)
    # zoom só troca em cortes espaçados (no mínimo 5 s), para não ficar frenético
    escolhidos, ultimo_c = [], 0.0
    for t_c in cuts:
        if t_c - ultimo_c >= 5.0 and L - t_c >= 2.0:
            escolhidos.append(t_c)
            ultimo_c = t_c
    bounds = [0.0] + escolhidos + [L]
    centro = (W / 2, CENTRO_FAIXA if (info["w"] > info["h"] and c["formato_vertical"] == "faixa") else H * 0.42)

    # intervenções leves (V2): punch-in e destaque; lacunas longas ganham punch-in automático (rosto com tratamento)
    leves = []
    f_l = os.path.join(pasta_corte, "leves.json")
    if os.path.exists(f_l) and c.get("broll_engine_v2", True):
        try:
            from . import brolls_v2
            leves = json.load(open(f_l, encoding="utf-8"))
            ocup_l = [(float(b["inicio"]) - 0.3, float(b["inicio"]) + float(b["dur"]) + 0.3) for b in plano
                      if os.path.exists(os.path.join(pasta_corte, b["arquivo"])) and not b.get("erro")]
            for k_, ins in enumerate(cartoes or []):
                a_ = float(ins["tempo"]) - 0.2
                ocup_l.append((a_, a_ + 3.6))
            leves = [l for l in leves if not any(l["inicio"] < b and l["inicio"] + l["dur"] > a for a, b in ocup_l)]
            leves = brolls_v2.preencher_lacunas(leves, ocup_l, words_yt, 3.5, L - 1.0, lacuna=float(c.get("lacuna_corte", 6.0)), s0=s)
        except Exception as ex:
            log(f"(intervenções leves não entraram: {ex})")
            leves = []
    # nos cortes a legenda já mostra as palavras: o destaque vira aproximação do rosto (nada de texto em cima de texto)
    punches = [(l["inicio"], l["inicio"] + l["dur"]) for l in leves]
    destaques = []
    if leves:
        log(f"Corte {corte['n']}: {len(punches)} punch-in(s) e {len(destaques)} destaque(s)")
    seg_g = float(c.get("gancho_corte_seg", 3.0))
    if corte.get("vertical"):          # partes de vídeo vertical: sem frase-gancho por cima (a fala dela já abre)
        seg_g = 0.0
    gancho = _gancho_png(corte.get("gancho") or corte.get("titulo")) if seg_g > 0 else None
    continua = None
    if corte.get("continua"):
        try:
            from . import brolls_v2
            from motor import templates as _tp
            fam = brolls_v2.familia_visual(pasta_corte, None, log)
            continua = _continua_png(_tp.TEMAS.get(fam, _tp.TEMAS["documental"])["acento"])
        except Exception as ex:
            log(f"(\"continua\" sem a cor da família: {ex})")
            continua = _continua_png((255, 206, 64))

    def zoom_de(t):
        if t < seg_g:                       # começo: rosto bem perto (prende nos primeiros segundos)
            return 1.30 - 0.06 * (t / seg_g)
        if any(a <= t < b for a, b in punches):   # ênfase: aproxima o rosto por alguns segundos
            return 1.16
        for k in range(len(bounds) - 1):
            if bounds[k] <= t < bounds[k + 1]:
                return 1.0 if k % 2 == 0 else 1.07
        return 1.0

    base = _leitor([FFMPEG, "-v", "error", "-ss", f"{s:.3f}", "-t", f"{L:.3f}", "-i", youtube_mp4,
                    "-filter_complex", "[0:v]" + _filtro_base(info, c["formato_vertical"], c["recorte_x"]) + "[o]",
                    "-map", "[o]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    brs = []
    for b in plano:
        arq = os.path.join(pasta_corte, b["arquivo"])
        if os.path.exists(arq) and not b.get("erro"):
            brs.append((float(b["inicio"]), arq, float(b["dur"])))
    # cartões (ícones + frase) no espaço de cima, sem cobrir o rosto; nunca junto com um B-roll
    cards = []
    faixa = info["w"] > info["h"] and c["formato_vertical"] == "faixa"
    if cartoes and faixa:
        from . import insercoes
        topo_faixa = CENTRO_FAIXA - int(W * info["h"] / info["w"]) // 2
        for k, ins in enumerate(cartoes):
            try:
                cw_, ch_, ccx, ccy, desenhar_c, dur_c = insercoes.cena_vertical(ins, seed=k)
            except Exception as ex:
                log(f"(cartão {ins.get('texto')} não deu: {ex})")
                continue
            a = max(0.0, float(ins["tempo"]) - 0.2)
            if any(a - 0.4 < bs + bd and bs < a + dur_c + 0.4 for bs, _, bd in brs) or a + dur_c > L - 0.3:
                continue
            area_top, area_bot = 150, topo_faixa - 15
            y = int(area_top + max(0, (area_bot - area_top - ch_) / 2))
            cards.append((a, dur_c, desenhar_c, int(W / 2 - ccx), y))
    abertos = {}
    tmpv = os.path.join(tmpdir(), "v.mp4")
    out = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", c["preset"], "-crf", "18",
                            "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
    TR = 5
    ultimo = None
    for i in range(n):
        t = i / FPS
        fr = _frame(base)
        if fr is None:
            fr = ultimo
            if fr is None:
                break
        ultimo = fr
        fr = _zoom(fr, zoom_de(t), centro)
        for k, (bs, arq, bd) in enumerate(brs):
            if bs <= t < bs + bd:
                if k not in abertos:
                    abertos[k] = _leitor([FFMPEG, "-v", "error", "-i", arq, "-vf", f"scale={W}:{H},fps={FPS}",
                                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
                bf = _frame(abertos[k])
                if bf is None:
                    continue
                fi, fo = int((t - bs) * FPS), int((bs + bd - t) * FPS)
                if fi < TR:
                    p = fi / TR
                    zi = 0.10 if c.get("broll_engine_v2", True) else 0.18    # V2: entrada com movimento
                    bf = _zoom(bf, 1 + zi - zi * (1 - (1 - p) ** 3), (W / 2, H / 2))
                    fr = (bf.astype(np.float32) * p + fr.astype(np.float32) * (1 - p)).astype(np.uint8)
                elif fo < TR:
                    p = fo / TR
                    fr = (bf.astype(np.float32) * p + fr.astype(np.float32) * (1 - p)).astype(np.uint8)
                else:
                    fr = bf
        for a, dc, desenhar_c, cx_, cy_ in cards:
            if a <= t < a + dc:
                im = Image.fromarray(fr)
                q = desenhar_c(t - a)
                im.paste(q, (cx_, cy_), q)
                fr = np.asarray(im)
        if gancho is not None and t < seg_g:
            idade = t
            esc = 0.86 + 0.14 * (1 - (1 - min(1.0, idade / 0.18)) ** 3)
            g = gancho if esc >= 0.999 else gancho.resize((max(1, int(gancho.width * esc)), max(1, int(gancho.height * esc))))
            if seg_g - t < 0.2:                # some suave
                g = g.copy()
                g.putalpha(g.getchannel("A").point(lambda v: int(v * (seg_g - t) / 0.2)))
            im = Image.fromarray(fr)
            im.paste(g, (int((W - g.width) / 2), int(330 - g.height / 2)), g)
            fr = np.asarray(im)
        for a_d, d_d, img_d in destaques:
            if img_d is not None and a_d <= t < a_d + d_d and not any(a <= t < a + dc for a, dc, *_ in cards) \
                    and not any(bs <= t < bs + bd for bs, _, bd in brs):
                k_d = min(1.0, (t - a_d) / 0.25, (a_d + d_d - t) / 0.3)
                g_d = img_d if k_d >= 1 else img_d.copy()
                if k_d < 1:
                    g_d.putalpha(img_d.getchannel("A").point(lambda v, k_d=k_d: int(v * max(0.0, k_d))))
                im = Image.fromarray(fr)
                im.paste(g_d, (0, int(300 - g_d.height / 2 + 12 * (1 - min(1.0, (t - a_d) / 0.3)))), g_d)
                fr = np.asarray(im)
        fr = leg.desenhar(fr, t)
        if continua is not None and t >= L - 1.4:      # "CONTINUA…" nos últimos ~1,4 s (abaixo da legenda)
            img_c, x_pts, cor_c = continua
            k_c = min(1.0, (t - (L - 1.4)) / 0.3)
            g_c = img_c.copy()
            dc = ImageDraw.Draw(g_c)
            for j in range(3):                        # os três pontos aparecem um a um
                if t >= L - 1.1 + j * 0.22:
                    cx_ = x_pts + 8 + j * 26
                    dc.ellipse([cx_ - 7, 50 - 7, cx_ + 7, 50 + 7], fill=tuple(cor_c) + (255,))
            if k_c < 1:
                g_c.putalpha(g_c.getchannel("A").point(lambda v, k_c=k_c: int(v * k_c)))
            im = Image.fromarray(fr)
            im.paste(g_c, (int((W - g_c.width) / 2), int(c["legenda_y"]) + 120 - int(10 * (1 - k_c))), g_c)
            fr = np.asarray(im)
        out.stdin.write(np.ascontiguousarray(fr).tobytes())
        if i % 150 == 0:
            log(f"…montando corte {corte['n']}: {int(100 * i / n)}%")
    out.stdin.close()
    out.wait()
    base.kill()
    for p in abertos.values():
        p.kill()
    # áudio: fala do corte + whoosh baixinho na entrada de cada B-roll
    inputs = ["-i", tmpv, "-ss", f"{s:.3f}", "-t", f"{L:.3f}", "-i", youtube_mp4]
    flt = []
    for k, (bs, arq, bd) in enumerate(brs):
        inputs += ["-f", "lavfi", "-t", "0.45", "-i", f"anoisesrc=color=pink:amplitude=0.6:seed={k + 3}"]
        dms = int(max(0, bs - 0.12) * 1000)
        flt.append(f"[{k + 2}:a]highpass=f=500,lowpass=f=5000,afade=t=in:d=0.18,afade=t=out:st=0.18:d=0.27,"
                   f"volume=0.22,adelay={dms}|{dms},aformat=channel_layouts=stereo[w{k}]")
    mix = ("[1:a]aformat=channel_layouts=stereo" + "[voz];[voz]" + "".join(f"[w{k}]" for k in range(len(brs))) +
           f"amix=inputs={len(brs) + 1}:normalize=0:duration=first[a]")
    run([FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(flt + [mix]), "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", saida])
    return saida
