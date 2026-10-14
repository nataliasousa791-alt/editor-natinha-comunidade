"""Mini cenas editoriais (estética nova): bonecos simples fazendo ações, objetos geométricos e diagramas
animados — a imagem EXPLICA a ideia, em vez de um texto dentro de um retângulo.

Cada cena: fn(D, dur, T) -> quadro(fr, d, t)  (mesma interface dos templates; registradas em templates.TEMPLATES).
Leve: só Pillow (linhas, elipses, polígonos). Funciona em 1080x1920 (cortes) e na tela horizontal do YouTube.
Cor com função: T['acento'] = principal; cor(T,'positivo') verde; cor(T,'perigo') vermelho; cor(T,'energia') ciano.
"""
import math

from . import templates as tp


# ------------------------------------------------------------------ palco e utilidades
def palco():
    """Área útil da cena (respeita a legenda dos cortes e as bordas do YouTube)."""
    if tp.H > tp.W:
        return 70, tp.TOPO + 30, tp.W - 70, tp.LIMITE_LEGENDA - 30
    return 70, tp.TOPO - 10, tp.W - 70, tp.BAIXO + 10


def _pt(x, y, ang, l):
    """Ponto a partir de (x,y), ângulo em graus medido a partir de 'para baixo' (positivo = para a frente/direita)."""
    a = math.radians(ang)
    return x + l * math.sin(a), y + l * math.cos(a)


def _mix(c1, c2, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))


def _texto(txt, tipo, tam, cor, larg=None, linhas=2, minimo=26):
    if larg:
        f, ls = tp.caber(str(txt), tipo, tam, larg, linhas, minimo)
    else:
        f, ls = tp.fonte(tipo, tam), [str(txt)]
    return tp.camada_texto(ls, f, cor)


def _rot(txt, cor, tam=30):
    return tp.rotulo(txt, cor, tam) if txt else None


# ------------------------------------------------------------------ o boneco
POSES = {
    "em_pe": dict(coxa_l=2, coxa_r=-2, joelho_l=2, joelho_r=2, braco_l=8, braco_r=-6, cotovelo_l=12, cotovelo_r=12),
    "mirar": dict(coxa_l=12, coxa_r=-10, braco_l=88, cotovelo_l=0, braco_r=80, cotovelo_r=-70, tronco=-4),
    "alcancar": dict(coxa_l=4, coxa_r=-4, braco_l=168, braco_r=160, cotovelo_l=0, cotovelo_r=0, dy=-0.03),
    "comemorar": dict(coxa_l=6, coxa_r=-6, braco_l=150, braco_r=-150, cotovelo_l=-15, cotovelo_r=15),
}


def pose_andar(fase, amp=24, tronco=4, cansado=0.0):
    s, c = math.sin(fase), math.cos(fase)
    amp = amp * (1 - 0.55 * cansado)
    return dict(coxa_l=amp * s, coxa_r=-amp * s,
                joelho_l=8 + 30 * max(0.0, c), joelho_r=8 + 30 * max(0.0, -c),
                braco_l=-amp * 0.9 * s * (1 - cansado), braco_r=amp * 0.9 * s * (1 - cansado),
                cotovelo_l=20 + 10 * cansado, cotovelo_r=20 + 10 * cansado,
                tronco=tronco + 24 * cansado, dy=-0.012 * abs(c) + 0.02 * cansado)


def pose_subir(fase):
    s = math.sin(fase)
    return dict(coxa_l=35 + 30 * max(0.0, s), coxa_r=35 + 30 * max(0.0, -s),
                joelho_l=40 + 40 * max(0.0, s), joelho_r=40 + 40 * max(0.0, -s),
                braco_l=-20 * s, braco_r=20 * s, cotovelo_l=30, cotovelo_r=30, tronco=12)


def boneco(d, x, y, alt, cor, pose=None, olha=1, alfa=255, cor_tras=None):
    """Boneco de perfil (silhueta simples). (x, y) = chão entre os pés; olha=1 direita, -1 esquerda."""
    p = dict(POSES["em_pe"])
    p.update(pose or {})
    g = lambda k: p.get(k, 0.0) * olha
    lw = max(3, int(alt * 0.085))
    hip = (x, y - 0.50 * alt + p.get("dy", 0.0) * alt)
    sh = _pt(hip[0], hip[1], 180 - g("tronco"), 0.30 * alt)
    cab = _pt(sh[0], sh[1], 180 - g("tronco"), 0.135 * alt)
    c_frente = cor + (alfa,)
    tras = cor_tras or _mix(cor, (0, 0, 0), 0.38)
    c_tras = tras + (alfa,)

    def membro(origem, a1, a2, l1, l2, c):
        j = _pt(origem[0], origem[1], a1, l1)
        e = _pt(j[0], j[1], a2, l2)
        d.line([origem, j, e], fill=c, width=lw, joint="curve")
        for q in (j, e):
            d.ellipse([q[0] - lw / 2, q[1] - lw / 2, q[0] + lw / 2, q[1] + lw / 2], fill=c)

    # membros de trás (mais escuros, dão profundidade), corpo, membros da frente
    membro(hip, g("coxa_r"), g("coxa_r") - g("joelho_r"), 0.25 * alt, 0.25 * alt, c_tras)
    membro(sh, g("braco_r"), g("braco_r") + g("cotovelo_r"), 0.17 * alt, 0.16 * alt, c_tras)
    d.line([hip, sh], fill=c_frente, width=int(lw * 1.7))
    for q in (hip, sh):
        r = lw * 0.85
        d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=c_frente)
    r = 0.085 * alt
    d.ellipse([cab[0] - r, cab[1] - r, cab[0] + r, cab[1] + r], fill=c_frente)
    membro(hip, g("coxa_l"), g("coxa_l") - g("joelho_l"), 0.25 * alt, 0.25 * alt, c_frente)
    membro(sh, g("braco_l"), g("braco_l") + g("cotovelo_l"), 0.17 * alt, 0.16 * alt, c_frente)
    return sh, cab


def bateria(d, cx, cy, w, h, nivel, T, alfa=255):
    """Bateria com nível 0–1: verde cheia → amarela → vermelha vazia."""
    nivel = max(0.0, min(1.0, nivel))
    cor_n = _mix(tp.cor(T, "perigo"), tp.cor(T, "amarelo"), nivel * 2) if nivel < 0.5 else \
        _mix(tp.cor(T, "amarelo"), tp.cor(T, "positivo"), (nivel - 0.5) * 2)
    x0, y0 = cx - w / 2, cy - h / 2
    b = max(3, int(h * 0.09))
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=int(h * 0.18), outline=T["tinta"] + (alfa,), width=b)
    d.rectangle([x0 + w, cy - h * 0.22, x0 + w + b * 2, cy + h * 0.22], fill=T["tinta"] + (alfa,))
    m = b * 2
    if nivel > 0.01:
        d.rounded_rectangle([x0 + m, y0 + m, x0 + m + (w - 2 * m) * nivel, y0 + h - m], radius=int(h * 0.1),
                            fill=cor_n + (alfa,))


# ------------------------------------------------------------------ cenas
def c_duelo(D, dur, T):
    """Dois personagens = dois conceitos. Os dois andam; a bateria de A esvazia e ele cansa e para;
    B segue firme, com a bateria cheia e a cor principal. Ex.: motivação × disciplina."""
    a, b = D.get("a") or {}, D.get("b") or {}
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    alt = min(alt_p * (0.50 if not deitado else 0.50), larg * (0.44 if not deitado else 0.30))
    chao = y0 + alt_p * (0.80 if not deitado else 0.80)
    xa, xb = x0 + larg * 0.27, x0 + larg * 0.73
    la = _texto(str(a.get("rotulo", "")).upper(), "sans", 54 if not deitado else 34, T["suave"], larg * 0.46, 1)
    lb = _texto(str(b.get("rotulo", "")).upper(), "sans", 54 if not deitado else 34, T["acento"], larg * 0.46, 1)
    fim_a = float(D.get("nivel_a", 0.08))
    frase = D.get("frase")
    fr_lay = _texto(frase, "serif", 70 if not deitado else 46, T["tinta"], larg * 0.92, 2) if frase else None
    bw, bh = alt * 0.62, alt * 0.22

    def quadro(fr, d, t):
        k_in = tp._p(t, 0, 0.5)
        d.line([x0, chao, x1, chao], fill=T["linha"] + (int(255 * k_in),), width=3)
        kd = tp._eio(tp._p(t, 0.6, dur * 0.65))
        nivel_a = 1 - (1 - fim_a) * kd
        cans = max(0.0, (0.55 - nivel_a) / 0.55)
        fase = t * 7.0
        fase_a = t * 7.0 * (1 - 0.6 * cans)
        alfa = int(255 * k_in)
        boneco(d, xa, chao, alt, T["suave"], pose_andar(fase_a, cansado=cans), alfa=alfa)
        boneco(d, xb, chao, alt, T["acento"], pose_andar(fase + 1.3), alfa=alfa)
        yb = chao - alt * 1.18
        bateria(d, xa - bw / 2 + bw / 2, yb, bw, bh, nivel_a, T, alfa)
        bateria(d, xb, yb, bw, bh, 1.0, T, alfa)
        tp.colar(fr, la, xa, yb - bh - la.height - 6, tp._p(t, 0.2, 0.5))
        tp.colar(fr, lb, xb, yb - bh - lb.height - 6, tp._p(t, 0.5, 0.5))
        if fr_lay:
            tp.colar(fr, fr_lay, tp.W / 2, chao + 40, tp._p(t, dur * 0.62, 0.6), "baixo")
    return quadro


def c_energia(D, dur, T):
    """Uma pessoa anda e a energia muda (cai: vai cansando; sobe: vai se endireitando)."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    try:
        de, para = float(D.get("de", 100)) / 100, float(D.get("para", 15)) / 100
    except (TypeError, ValueError):
        de, para = 1.0, 0.15
    alt = min(alt_p * 0.52, larg * (0.5 if not deitado else 0.36))
    chao = y0 + alt_p * (0.80 if not deitado else 0.82)
    rot = _texto(str(D.get("rotulo", "")).upper(), "sans", 54 if not deitado else 34, T["tinta"], larg * 0.8, 1) \
        if D.get("rotulo") else None
    txt = _texto(D.get("texto"), "serif", 70 if not deitado else 48, T["tinta"], larg * 0.92, 2) if D.get("texto") else None
    bw, bh = alt * 0.7, alt * 0.25

    def quadro(fr, d, t):
        k = tp._eio(tp._p(t, 0.4, dur * 0.7))
        nivel = de + (para - de) * k
        cans = max(0.0, (0.6 - nivel) / 0.6) if para < de else max(0.0, (0.6 - nivel) / 0.6)
        x = x0 + larg * (0.30 + 0.40 * tp._p(t, 0, dur))
        d.line([x0, chao, x1, chao], fill=T["linha"] + (255,), width=3)
        for i in range(0, int(larg), 46):           # chão tracejado que corre (sensação de caminhada)
            xx = x0 + (i - (t * 120) % 46)
            if x0 <= xx <= x1 - 20:
                d.line([xx, chao + 14, xx + 20, chao + 14], fill=T["linha"] + (255,), width=3)
        cor_b = tp.cor(T, "perigo") if (para < de and nivel < 0.3) else T["tinta"]
        boneco(d, x, chao, alt, cor_b, pose_andar(t * 6.5, cansado=cans))
        bateria(d, x, chao - alt * 1.22, bw, bh, nivel, T)
        if rot:
            tp.colar(fr, rot, x, chao - alt * 1.22 - bh - rot.height - 8, tp._p(t, 0.2, 0.5))
        if txt:
            tp.colar(fr, txt, tp.W / 2, chao + 46, tp._p(t, dur * 0.55, 0.6), "baixo")
    return quadro


def c_escada(D, dur, T):
    """Pessoa sobe uma escada; cada degrau alcançado acende (progresso); no topo, a meta brilha."""
    passos = [str(p) for p in (D.get("passos") or []) if p][:4]
    n = max(3, len(passos) + 1 if passos else 5)
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    meta = D.get("meta")
    ml = _texto(str(meta).upper(), "sans", 76 if not deitado else 50, T["acento"], larg * 0.9, 1) if meta else None
    topo_txt = (ml.height + 40) if ml is not None else 20
    ex0, ey0 = x0 + larg * 0.04, y1 - alt_p * 0.04
    alt = min(alt_p * 0.30, larg * 0.28)
    ex1, ey1 = x0 + larg * (0.70 if not deitado else 0.62), y0 + topo_txt + alt + 10
    dx, dy = (ex1 - ex0) / n, (ey0 - ey1) / n
    alt = min(alt, dy * 2.6)
    fl = 46 if not deitado else 30
    labs = [_texto(p, "sans_m", fl, T["tinta"], larg * 0.42, 2, 22) for p in passos]
    t_sub = dur * 0.72

    def quadro(fr, d, t):
        prog = tp._eio(tp._p(t, 0.35, t_sub)) * n
        for i in range(n):
            xs, ys = ex0 + dx * i, ey0 - dy * i
            ki = tp._p(t, 0.05 * i, 0.35)
            if ki <= 0:
                continue
            aceso = prog >= i + 0.6
            c = (T["acento"] if aceso else T["tinta"]) + (int(255 * ki),)
            d.line([xs, ys, xs + dx, ys], fill=c, width=6)
            if i > 0:
                d.line([xs, ys, xs, ys + dy], fill=T["linha"] + (int(255 * ki),), width=3)
            if 0 < i <= len(labs) and aceso:
                lay = labs[i - 1]
                tp.colar(fr, lay, xs + dx + 30 + lay.width / 2, ys - lay.height / 2 - 10, tp._p(t, 0.35 + (i + 0.6) / n * t_sub, 0.4))
        k = min(prog, n - 0.5)
        i = int(k)
        f = k - i
        x = ex0 + dx * (i + 0.5) + dx * f * 0.6
        y = ey0 - dy * i - dy * tp._eio(min(1.0, f * 1.6))
        pose = pose_subir(t * 7) if prog < n - 0.6 else POSES["comemorar"]
        boneco(d, x, y, alt, T["tinta"], pose)
        if ml is not None:
            km = tp._p(t, t_sub, 0.5)
            tp.colar(fr, ml, tp.W / 2 if not deitado else x0 + larg * 0.78, y0, km, "baixo")
    return quadro


def _alvo(d, cx, cy, r, cor, alfa=255, tracejado=False, giro=0.0):
    for k, rr in enumerate((r, r * 0.66, r * 0.33)):
        if tracejado and k == 0:
            for a in range(0, 360, 18):
                aa = a + giro
                d.arc([cx - rr, cy - rr, cx + rr, cy + rr], aa, aa + 10, fill=cor + (alfa,), width=max(2, int(r * 0.08)))
        else:
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=cor + (alfa,), width=max(2, int(r * 0.08)))
    d.ellipse([cx - r * 0.1, cy - r * 0.1, cx + r * 0.1, cy + r * 0.1], fill=cor + (alfa,))


def c_alvos(D, dur, T):
    """Em cima: atenção dividida (três alvos, flechas erram). Embaixo: foco (um alvo, flechas acertam)."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    ra = _texto(str(D.get("a", "")).upper(), "sans", 50 if not deitado else 32, T["suave"], larg * 0.8, 1) if D.get("a") else None
    rb = _texto(str(D.get("b", "")).upper(), "sans", 50 if not deitado else 32, T["acento"], larg * 0.8, 1) if D.get("b") else None
    faixa = alt_p / 2
    alt = min(faixa * 0.62, larg * (0.30 if not deitado else 0.2))

    def linha_cena(fr, d, t, y_chao, foco, lay, t0):
        k = tp._p(t, t0, 0.4)
        if k <= 0:
            return
        cor_b = T["acento"] if foco else T["tinta"]
        d.line([x0, y_chao, x1, y_chao], fill=T["linha"] + (int(255 * k),), width=3)
        bx = x0 + larg * 0.18
        boneco(d, bx, y_chao, alt, cor_b, POSES["mirar"], alfa=int(255 * k))
        mao = (bx + alt * 0.33, y_chao - alt * 0.80)
        d.arc([mao[0] - alt * 0.12, mao[1] - alt * 0.28, mao[0] + alt * 0.12, mao[1] + alt * 0.28], -80, 80,
              fill=cor_b + (int(255 * k),), width=4)
        if lay:
            tp.colar(fr, lay, x0 + lay.width / 2, y_chao - alt * 1.12 - lay.height - 10, k)
        tx = x0 + larg * 0.78
        if foco:
            r = alt * 0.34
            cy = y_chao - alt * 0.6
            _alvo(d, tx, cy, r, T["tinta"], int(255 * k))
            for j in range(3):
                kf = tp._eout(tp._p(t, t0 + 0.5 + j * 0.45, 0.35))
                if kf <= 0:
                    continue
                ax = mao[0] + (tx - mao[0]) * kf
                ay = mao[1] + (cy + (j - 1) * r * 0.12 - mao[1]) * kf
                d.line([ax - 46, ay, ax, ay], fill=cor_b + (255,), width=4)
                if kf >= 1:
                    rr = r * (1 + 0.25 * math.exp(-(t - t0 - 0.85 - j * 0.45) * 6))
                    d.ellipse([tx - rr * 0.12, cy - rr * 0.12, tx + rr * 0.12, cy + rr * 0.12], fill=T["acento"] + (255,))
        else:
            r = alt * 0.2
            pos = [(tx, y_chao - alt * 1.05), (tx + r * 0.6, y_chao - alt * 0.6), (tx - r * 0.3, y_chao - alt * 0.18)]
            for j, (cx, cy) in enumerate(pos):
                _alvo(d, cx, cy, r, T["suave"], int(255 * k), tracejado=True, giro=t * 40 * (1 if j % 2 else -1))
            for j in range(3):
                kf = tp._eout(tp._p(t, t0 + 0.5 + j * 0.45, 0.35))
                if kf <= 0:
                    continue
                cx, cy = pos[j]
                ex, ey = cx - r * 1.3, cy + r * (0.9 if j % 2 else -0.9)       # erra: passa do lado
                ax, ay = mao[0] + (ex - mao[0]) * kf, mao[1] + (ey - mao[1]) * kf
                d.line([ax - 40, ay, ax, ay], fill=T["suave"] + (255,), width=3)

    def quadro(fr, d, t):
        linha_cena(fr, d, t, y0 + faixa * 0.92, False, ra, 0.0)
        linha_cena(fr, d, t, y0 + faixa * 1.92, True, rb, max(0.8, dur * 0.3))
    return quadro


def c_caminho(D, dur, T):
    """Caminho em perspectiva que vai aparecendo até uma luz no horizonte; uma frase curta entra."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    hx, hy = tp.W / 2, y0 + alt_p * 0.30
    txt = _texto(D.get("texto"), "serif", 60 if not deitado else 44, T["tinta"], larg * 0.85, 2) if D.get("texto") else None
    meta = _texto(str(D.get("meta", "")).upper(), "sans_m", 34 if not deitado else 26, T["acento"], larg * 0.6, 1) \
        if D.get("meta") else None
    n = 9

    def quadro(fr, d, t):
        kl = tp._p(t, 0.1, 0.8)
        r = 22 * kl * (1 + 0.06 * math.sin(t * 5))
        if r > 0:
            d.rectangle([hx - r, hy - r, hx + r, hy + r], fill=T["tinta"] + (255,))
            for g in range(1, 5):                # halo
                rr = r + g * 14
                d.rectangle([hx - rr, hy - rr, hx + rr, hy + rr], outline=T["acento"] + (int(60 / g * kl),), width=6)
        for i in range(n):
            ki = tp._eout(tp._p(t, 0.3 + (n - 1 - i) * 0.12, 0.4))
            if ki <= 0:
                continue
            p0 = (i / n) ** 1.8
            p1 = ((i + 0.75) / n) ** 1.8
            yt, yb = hy + (y1 - hy) * p0, hy + (y1 - hy) * p1
            wt, wb = 20 + larg * 0.55 * p0, 20 + larg * 0.55 * p1
            c = T["tinta"] + (int(255 * ki),)
            d.polygon([(hx - wt, yt), (hx + wt, yt), (hx + wb, yb), (hx - wb, yb)], outline=c, width=3)
            d.line([hx - wb, yb, hx + wb, yb], fill=c, width=max(3, int(8 * p1)))
        if meta:
            tp.colar(fr, meta, hx, hy - 50 - meta.height, tp._p(t, dur * 0.45, 0.5))
        if txt:
            tp.colar(fr, txt, tp.W / 2, y0 + 10, tp._p(t, dur * 0.25, 0.6), "baixo")
    return quadro


def c_pilha(D, dur, T):
    """Dois montes de blocos: A cresce pouco e desmorona; B cresce com constância; o resultado acende sobre B."""
    a, b = D.get("a") or {}, D.get("b") or {}
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    chao = y0 + alt_p * (0.88 if not deitado else 0.86)
    bw, bh = larg * (0.24 if not deitado else 0.10), alt_p * 0.058
    la = _texto(str(a.get("rotulo", "")).upper(), "sans", 46 if not deitado else 30, T["suave"], larg * 0.46, 1) if a.get("rotulo") else None
    lb = _texto(str(b.get("rotulo", "")).upper(), "sans", 46 if not deitado else 30, T["acento"], larg * 0.46, 1) if b.get("rotulo") else None
    res = _texto(str(D.get("resultado", "")).upper(), "sans", 64 if not deitado else 48, tp.cor(T, "amarelo"),
                 larg * 0.8, 1) if D.get("resultado") else None
    xa, xb = x0 + larg * 0.28, x0 + larg * 0.72
    so_b = not a.get("rotulo")                  # uma pilha só: a causa acumula e o resultado aparece
    if so_b:
        xb = tp.W / 2
    nb = 11

    def quadro(fr, d, t):
        d.line([x0, chao, x1, chao], fill=T["linha"] + (255,), width=3)
        kb = tp._p(t, 0.3, dur * 0.62)
        for i in range(int(nb * kb + 0.999)):
            ki = min(1.0, nb * kb - i)
            y = chao - bh * (i + 1) - (1 - tp._eout(ki)) * bh * 3
            d.rectangle([xb - bw / 2, y, xb + bw / 2, y + bh - 6], fill=_mix(T["linha"], T["tinta"], 0.75) + (int(255 * ki),))
        ka = 0.0 if so_b else tp._p(t, 0.3, dur * 0.4)
        queda = tp._eio(tp._p(t, 0.3 + dur * 0.45, 0.6))
        for i in range(int(5 * ka + 0.999)):
            ki = min(1.0, 5 * ka - i)
            y = chao - bh * (i + 1) - (1 - tp._eout(ki)) * bh * 3
            ang = queda * (18 + i * 9)
            dx = queda * i * bw * 0.35
            yq = y + queda * bh * i * 0.7
            cx_, cy_ = xa + dx, yq + bh / 2
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            pts = [(cx_ + px * ca - py * sa, cy_ + px * sa + py * ca)
                   for px, py in ((-bw / 2, -bh / 2 + 3), (bw / 2, -bh / 2 + 3), (bw / 2, bh / 2 - 3), (-bw / 2, bh / 2 - 3))]
            c = _mix(T["suave"], tp.cor(T, "perigo"), queda)
            d.polygon(pts, fill=c + (int(255 * ki),))
        if la:
            tp.colar(fr, la, xa, chao + 16, tp._p(t, 0.1, 0.5))
        if lb:
            tp.colar(fr, lb, xb, chao + 16, tp._p(t, 0.3, 0.5))
        if res:
            tp.colar(fr, res, xb if not deitado else tp.W / 2, chao - bh * nb - res.height - 40,
                     tp._p(t, 0.3 + dur * 0.62, 0.5), "baixo")
    return quadro


def c_barras(D, dur, T):
    """Barras que sobem (comparação de grandezas); a barra em destaque acende na cor principal."""
    itens = [i for i in (D.get("itens") or []) if isinstance(i, dict)][:4]
    if len(itens) < 2:
        return None
    vals = []
    for i in itens:
        try:
            vals.append(max(0.0, float(str(i.get("valor", 1)).replace("%", "").replace(",", "."))))
        except ValueError:
            vals.append(1.0)
    vmax = max(vals) or 1
    try:
        dest = int(D.get("destaque")) if D.get("destaque") is not None else vals.index(max(vals))
    except (TypeError, ValueError):
        dest = vals.index(max(vals))
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    tit = _texto(D.get("titulo"), "serif", 62 if not deitado else 46, T["tinta"], larg * 0.9, 2) if D.get("titulo") else None
    topo = y0 + (tit.height + 50 if tit else 20)
    chao = y1 - 90
    n = len(itens)
    passo = larg / n
    bw = min(passo * 0.55, 240)
    labs = [_texto(str(i.get("rotulo", "")), "sans_m", 42 if not deitado else 28, T["tinta"], passo * 0.95, 2, 20)
            for i in itens]

    def quadro(fr, d, t):
        if tit:
            tp.colar(fr, tit, tp.W / 2, y0, tp._p(t, 0, 0.5), "baixo")
        d.line([x0, chao, x1, chao], fill=T["linha"] + (255,), width=3)
        for j, v in enumerate(vals):
            k = tp._eout(tp._p(t, 0.3 + j * 0.25, max(0.8, dur * 0.4)))
            h = (chao - topo - 60) * v / vmax * k
            cx = x0 + passo * (j + 0.5)
            c = T["acento"] if j == dest else _mix(T["linha"], T["tinta"], 0.45)
            d.rectangle([cx - bw / 2, chao - h, cx + bw / 2, chao], fill=c + (255,))
            num = str(itens[j].get("valor", ""))
            if num and k > 0.05:
                nl = _texto(num, "sans", 64 if not deitado else 40, T["acento"] if j == dest else T["tinta"])
                tp.colar(fr, nl, cx, chao - h - nl.height - 8, k)
            tp.colar(fr, labs[j], cx, chao + 12, tp._p(t, 0.1 + j * 0.15, 0.4))
    return quadro


def c_pessoas(D, dur, T):
    """Linhas de porcentagem com pessoas (ex.: 93% / 6% / 1%): a minoria acende na cor principal."""
    itens = [i for i in (D.get("itens") or []) if isinstance(i, dict) and i.get("numero")][:3]
    if not itens:
        return None
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    faixa = alt_p / len(itens)
    alt = min(faixa * 0.62, 240 if not deitado else 150)
    lays = []
    for j, it in enumerate(itens):
        cor_n = T["acento"] if j == len(itens) - 1 else T["tinta"]
        num = _texto(str(it["numero"]), "sans", 110 if not deitado else 64, cor_n)
        tx = _texto(str(it.get("texto", "")), "sans_m", 44 if not deitado else 30, T["suave"], larg * 0.55, 2, 20) \
            if it.get("texto") else None
        lays.append((num, tx))

    def quadro(fr, d, t):
        for j, (num, tx) in enumerate(lays):
            t0 = 0.2 + j * min(0.9, dur * 0.22)
            k = tp._p(t, t0, 0.45)
            if k <= 0:
                continue
            yc = y0 + faixa * (j + 0.5)
            ult = j == len(lays) - 1
            tp.colar(fr, num, x0 + num.width / 2, yc - num.height / 2 - (14 if tx else 0), k, "baixo")
            if tx:
                tp.colar(fr, tx, x0 + tx.width / 2, yc + num.height / 2 - 6, tp._p(t, t0 + 0.2, 0.4))
            bx = x0 + larg * 0.78
            fase = (t - t0) * 6 if ult else 0
            pose = pose_andar(fase) if ult else (POSES["em_pe"] if j == 0 else dict(POSES["em_pe"], tronco=14))
            boneco(d, bx, yc + alt * 0.55, alt, T["acento"] if ult else T["suave"], pose, alfa=int(255 * k))
            d.line([bx - alt * 0.6, yc + alt * 0.55, bx + alt * 0.9, yc + alt * 0.55], fill=T["linha"] + (int(255 * k),), width=3)
    return quadro


def c_relogio(D, dur, T):
    """Relógio: os ponteiros correm (o tempo passa) e desaceleram; a frase entra embaixo."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    r = min(larg, alt_p) * (0.26 if not deitado else 0.30)
    cx, cy = tp.W / 2 if not deitado else x0 + larg * 0.30, y0 + alt_p * (0.40 if not deitado else 0.5)
    txt = _texto(D.get("texto"), "serif", 62 if not deitado else 48, T["tinta"], larg * (0.85 if not deitado else 0.5), 3) \
        if D.get("texto") else None
    num = _texto(str(D.get("numero")), "sans", 120 if not deitado else 96, T["acento"]) if D.get("numero") else None

    def quadro(fr, d, t):
        k = tp._eout(tp._p(t, 0, 0.5))
        rr = r * (0.9 + 0.1 * k)
        a = int(255 * k)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=T["tinta"] + (a,))
        ri = rr * 0.86
        d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=T["fundo"] + (a,))
        for i in range(12):
            ang = math.radians(i * 30)
            p0 = (cx + math.sin(ang) * ri * 0.88, cy - math.cos(ang) * ri * 0.88)
            p1 = (cx + math.sin(ang) * ri * (0.74 if i % 3 == 0 else 0.82), cy - math.cos(ang) * ri * (0.74 if i % 3 == 0 else 0.82))
            d.line([p0, p1], fill=T["tinta"] + (a,), width=6 if i % 3 == 0 else 3)
        # o tempo corre e depois desacelera
        giro = 360 * 3 * tp._eout(tp._p(t, 0.2, dur * 0.7))
        for ang, l, w, c in ((giro, ri * 0.72, 4, T["acento"]), (giro / 12, ri * 0.5, 8, T["tinta"])):
            aa = math.radians(ang)
            d.line([cx, cy, cx + math.sin(aa) * l, cy - math.cos(aa) * l], fill=c + (a,), width=w)
        d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=T["acento"] + (a,))
        d.rectangle([cx - rr * 0.18, cy - rr - 40, cx + rr * 0.18, cy - rr - 18], fill=T["tinta"] + (a,))
        if num:
            tp.colar(fr, num, cx if not deitado else x0 + larg * 0.72, (cy + rr + 30) if not deitado else cy - num.height - 10,
                     tp._p(t, dur * 0.4, 0.5), "baixo")
        if txt:
            if deitado:
                tp.colar(fr, txt, x0 + larg * 0.72, cy + 10, tp._p(t, dur * 0.5, 0.6), "baixo")
            else:
                tp.colar(fr, txt, tp.W / 2, cy + rr + 40 + (num.height + 10 if num else 0), tp._p(t, dur * 0.5, 0.6), "baixo")
    return quadro


def _pct(numero):
    import re as _re
    m = _re.search(r"(\d+(?:[.,]\d+)?)\s*%", str(numero or ""))
    return max(0.0, min(100.0, float(m.group(1).replace(",", ".")))) if m else None


def c_plataformas(D, dur, T):
    """Progressão: plataformas flutuantes subindo; a pessoa salta de uma para outra; a última (meta) acende."""
    passos = [str(p) for p in (D.get("passos") or []) if p][:3]
    n = max(3, len(passos) + 1)
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    meta = _texto(str(D.get("meta", "")).upper(), "sans", 64 if not deitado else 44, tp.cor(T, "amarelo"), larg * 0.8, 1) \
        if D.get("meta") else None
    topo = y0 + (meta.height + 50 if meta is not None else 30)
    alt = min(alt_p * 0.26, larg * 0.24)
    pw = larg * (0.34 if not deitado else 0.18)
    pos = [(x0 + pw / 2 + (larg - pw) * i / (n - 1), y1 - 40 - (y1 - 40 - topo - alt - 20) * i / (n - 1)) for i in range(n)]
    labs = [_texto(p, "sans_m", 46 if not deitado else 30, T["tinta"], pw * 1.2, 2, 20) for p in passos]
    t_sub = dur * 0.75

    def quadro(fr, d, t):
        prog = tp._p(t, 0.3, t_sub) * (n - 1)
        for i, (cx, cy) in enumerate(pos):
            ki = tp._eout(tp._p(t, 0.08 * i, 0.4))
            if ki <= 0:
                continue
            alcan = prog >= i - 0.05
            ult = i == n - 1
            c = (tp.cor(T, "amarelo") if ult else tp.cor(T, "positivo")) if alcan else _mix(T["linha"], T["tinta"], 0.5)
            yy = cy + (1 - ki) * 40
            d.rounded_rectangle([cx - pw / 2, yy, cx + pw / 2, yy + 16], radius=8, fill=c + (int(255 * ki),))
            if 0 < i <= len(labs):
                tp.colar(fr, labs[i - 1], cx, yy + 28, ki)
        i = min(int(prog), n - 2)
        f = prog - i
        (xa, ya), (xb, yb) = pos[i], pos[i + 1]
        x = xa + (xb - xa) * tp._eio(f)
        y = ya + (yb - ya) * f - math.sin(math.pi * f) * alt * 0.55       # salto em arco
        pose = POSES["comemorar"] if prog >= n - 1.02 else (pose_andar(t * 9, amp=30) if f < 0.15 or f > 0.85 else
                                                            dict(POSES["alcancar"], coxa_l=40, joelho_l=60, coxa_r=-20))
        boneco(d, x, y, alt, T["tinta"], pose)
        if meta is not None:
            tp.colar(fr, meta, tp.W / 2, y0, tp._p(t, t_sub, 0.5), "baixo")
    return quadro


def c_sequencia(D, dur, T):
    """Progressão: pontos ligados por um fio que se desenha; cada etapa acende em sequência; a última é a meta."""
    passos = [str(p) for p in (D.get("passos") or []) if p][:4]
    if D.get("meta"):
        passos.append(str(D["meta"]))
    if len(passos) < 2:
        return None
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    n = len(passos)
    r = 26 if not deitado else 20
    if deitado:
        pts = [(x0 + larg * (0.1 + 0.8 * i / (n - 1)), y0 + alt_p * (0.55 - 0.18 * math.sin(math.pi * i / (n - 1)))) for i in range(n)]
    else:
        pts = [(x0 + larg * (0.16 + 0.12 * (i % 2)), y0 + 40 + (alt_p - 120) * i / (n - 1)) for i in range(n)]
    labs = [_texto(p.upper() if i == n - 1 and D.get("meta") else p, "sans" if i == n - 1 else "sans_m",
                   (54 if i == n - 1 else 46) if not deitado else (38 if i == n - 1 else 30),
                   tp.cor(T, "amarelo") if i == n - 1 else T["tinta"], larg * (0.62 if not deitado else 0.2), 2, 20)
            for i, p in enumerate(passos)]
    passo_t = dur * 0.7 / n

    def quadro(fr, d, t):
        for i in range(n - 1):
            k = tp._p(t, 0.2 + passo_t * (i + 0.5), passo_t)
            if k > 0:
                (xa, ya), (xb, yb) = pts[i], pts[i + 1]
                d.line([xa, ya, xa + (xb - xa) * tp._eout(k), ya + (yb - ya) * tp._eout(k)], fill=tp.cor(T, "energia") + (255,), width=5)
        for i, (x, y) in enumerate(pts):
            k = tp._p(t, 0.2 + passo_t * i, 0.35)
            if k <= 0:
                continue
            ult = i == n - 1
            c = tp.cor(T, "amarelo") if ult else tp.cor(T, "energia")
            rr = r * (1.4 if ult else 1) * (0.6 + 0.4 * tp._eout(k))
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c + (int(255 * k),))
            lay = labs[i]
            if deitado:
                tp.colar(fr, lay, x, y + rr + 16, k, "baixo")
            else:
                fr.alpha_composite(tp.alfa(lay, k), (int(x + rr + 30), int(y - lay.height / 2)))
    return quadro


def c_balanca(D, dur, T):
    """Comparação: balança que pende para o lado que pesa mais (B)."""
    a, b = D.get("a") or {}, D.get("b") or {}
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    cx, base_y = tp.W / 2, y1 - 30
    topo_y = y0 + alt_p * 0.30
    braco = larg * (0.40 if not deitado else 0.26)
    la = _texto(str(a.get("rotulo", "")).upper(), "sans", 50 if not deitado else 34, tp.cor(T, "perigo"), braco * 1.1, 2)
    lb = _texto(str(b.get("rotulo", "")).upper(), "sans", 50 if not deitado else 34, tp.cor(T, "positivo"), braco * 1.1, 2)
    fr_lay = _texto(D.get("frase"), "serif", 62 if not deitado else 44, T["tinta"], larg * 0.9, 2) if D.get("frase") else None

    def quadro(fr, d, t):
        k = tp._p(t, 0, 0.5)
        al = int(255 * k)
        d.line([cx, topo_y, cx, base_y], fill=T["tinta"] + (al,), width=10)
        d.polygon([(cx - 90, base_y), (cx + 90, base_y), (cx, base_y - 60)], fill=T["tinta"] + (al,))
        ang = math.radians(-14 * tp._eio(tp._p(t, 0.9, dur * 0.4)) + 3 * math.sin(t * 3) * (1 - tp._p(t, 0.9, 0.6)))
        pa = (cx - braco * math.cos(ang), topo_y - braco * math.sin(ang))
        pb = (cx + braco * math.cos(ang), topo_y + braco * math.sin(ang))
        d.line([pa, pb], fill=T["tinta"] + (al,), width=10)
        d.ellipse([cx - 16, topo_y - 16, cx + 16, topo_y + 16], fill=tp.cor(T, "amarelo") + (al,))
        for (px, py), lay, cor_, peso in ((pa, la, tp.cor(T, "perigo"), 1), (pb, lb, tp.cor(T, "positivo"), 3)):
            fio = alt_p * 0.16
            d.line([px, py, px - 70, py + fio], fill=T["suave"] + (al,), width=3)
            d.line([px, py, px + 70, py + fio], fill=T["suave"] + (al,), width=3)
            d.arc([px - 110, py + fio - 40, px + 110, py + fio + 40], 0, 180, fill=T["tinta"] + (al,), width=8)
            kb = tp._eout(tp._p(t, 0.4, 0.5))
            for j in range(peso):                          # blocos de peso
                bh = 34
                yb = py + fio - bh * (j + 1) - (1 - kb) * 60
                d.rectangle([px - 40, yb, px + 40, yb + bh - 6], fill=cor_ + (int(255 * kb),))
            tp.colar(fr, lay, px, py + fio + 50, tp._p(t, 0.3, 0.5))
        if fr_lay:
            tp.colar(fr, fr_lay, tp.W / 2, y0, tp._p(t, dur * 0.55, 0.6), "baixo")
    return quadro


def c_caminhos(D, dur, T):
    """Comparação/escolha: o caminho se divide; um leva a um beco (vermelho), o outro à luz (verde/amarelo)."""
    a, b = D.get("a") or {}, D.get("b") or {}
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    base = (tp.W / 2, y1 - 20)
    garfo = (tp.W / 2, y0 + alt_p * 0.62)
    fa = (x0 + larg * 0.14, y0 + alt_p * 0.20)
    fb = (x1 - larg * 0.14, y0 + alt_p * 0.20)
    la = _texto(str(a.get("rotulo", "")).upper(), "sans", 46 if not deitado else 32, tp.cor(T, "perigo"), larg * 0.42, 2)
    lb = _texto(str(b.get("rotulo", "")).upper(), "sans", 46 if not deitado else 32, tp.cor(T, "positivo"), larg * 0.42, 2)
    alt = min(alt_p * 0.28, larg * 0.26)

    def seg(d, p, q, k, cor_, w=8):
        if k > 0:
            d.line([p, (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k)], fill=cor_ + (255,), width=w)

    def quadro(fr, d, t):
        seg(d, base, garfo, tp._eout(tp._p(t, 0, 0.5)), T["tinta"])
        seg(d, garfo, fa, tp._eout(tp._p(t, 0.45, 0.5)), _mix(T["linha"], tp.cor(T, "perigo"), 0.7))
        seg(d, garfo, fb, tp._eout(tp._p(t, 0.45, 0.5)), tp.cor(T, "positivo"))
        if tp._p(t, 0.9, 0.3) > 0:
            k = tp._p(t, 0.9, 0.3)
            r = 30
            c = tp.cor(T, "perigo") + (int(255 * k),)
            d.line([fa[0] - r, fa[1] - r, fa[0] + r, fa[1] + r], fill=c, width=9)
            d.line([fa[0] - r, fa[1] + r, fa[0] + r, fa[1] - r], fill=c, width=9)
            g = 26 * k * (1 + 0.08 * math.sin(t * 6))
            d.ellipse([fb[0] - g, fb[1] - g, fb[0] + g, fb[1] + g], fill=tp.cor(T, "amarelo") + (255,))
        tp.colar(fr, la, max(la.width / 2 + 20, fa[0] + la.width * 0.25), fa[1] - 60 - la.height, tp._p(t, 0.8, 0.4))
        tp.colar(fr, lb, min(tp.W - lb.width / 2 - 20, fb[0] - lb.width * 0.25), fb[1] - 60 - lb.height, tp._p(t, 1.0, 0.4))
        k = tp._eio(tp._p(t, 1.1, dur * 0.6))                 # a pessoa segue pelo caminho certo
        if k < 0.5:
            px, py = base[0] + (garfo[0] - base[0]) * k * 2, base[1] + (garfo[1] - base[1]) * k * 2
        else:
            px, py = garfo[0] + (fb[0] - garfo[0]) * (k - 0.5) * 2, garfo[1] + (fb[1] - garfo[1]) * (k - 0.5) * 2
        esc = 1 - 0.3 * k                                   # perspectiva: diminui um pouco ao se afastar
        boneco(d, px, py, alt * esc, T["tinta"], pose_andar(t * 7))
    return quadro


def c_domino(D, dur, T):
    """Causa e consequência: a peça da causa cai e derruba as outras até o efeito acender."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    chao = y0 + alt_p * (0.70 if not deitado else 0.78)
    n = 6
    hh = min(alt_p * 0.32, 300 if not deitado else 220)
    ww = hh * 0.22
    xs = [x0 + larg * 0.08 + (larg * 0.62) * i / (n - 1) for i in range(n)]
    lc = _texto(str(D.get("causa", "")).upper(), "sans", 46 if not deitado else 32, tp.cor(T, "amarelo"), larg * 0.5, 2) \
        if D.get("causa") else None
    le = _texto(str(D.get("efeito", "")).upper(), "sans", 54 if not deitado else 38, tp.cor(T, "perigo"), larg * 0.42, 2) \
        if D.get("efeito") else None
    xe = x1 - larg * 0.12
    t0, passo = 0.6, max(0.12, dur * 0.4 / n)

    def quadro(fr, d, t):
        d.line([x0, chao, x1, chao], fill=T["linha"] + (255,), width=3)
        for i, x in enumerate(xs):
            k = tp._eio(tp._p(t, t0 + passo * i, passo * 1.4))
            ang = math.radians(72 * k)
            c = tp.cor(T, "amarelo") if i == 0 else _mix(T["linha"], T["tinta"], 0.7)
            pts = [(0, 0), (ww, 0), (ww, -hh), (0, -hh)]
            pts = [(x + px * math.cos(ang) - py * math.sin(ang), chao + px * math.sin(ang) + py * math.cos(ang)) for px, py in pts]
            d.polygon(pts, fill=c + (255,))
        ke = tp._p(t, t0 + passo * n, 0.4)
        g = 70 * (0.5 + 0.5 * tp._eout(ke))
        if ke > 0:
            d.rounded_rectangle([xe - g, chao - 2 * g, xe + g, chao], radius=12, fill=tp.cor(T, "perigo") + (int(255 * ke),))
        if lc:
            tp.colar(fr, lc, max(lc.width / 2 + 20, xs[0] + ww / 2), chao - hh - lc.height - 30, tp._p(t, 0.1, 0.5))
        if le:
            tp.colar(fr, le, xe if deitado else tp.W / 2, (chao - 2 * g - le.height - 20) if deitado else chao + 30 + (lc.height + 20 if lc else 0),
                     ke, "baixo")
    return quadro


def c_fluxo(D, dur, T):
    """Causa e consequência: partículas fluem do ponto A (causa) para o ponto B (efeito), que cresce e acende."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    if deitado:
        A, B = (x0 + larg * 0.18, y0 + alt_p * 0.5), (x1 - larg * 0.18, y0 + alt_p * 0.5)
    else:
        A, B = (tp.W / 2, y0 + alt_p * 0.18), (tp.W / 2, y0 + alt_p * 0.74)
    ra = min(larg, alt_p) * 0.10
    la = _texto(str(D.get("causa", "")).upper(), "sans", 46 if not deitado else 32, tp.cor(T, "energia"), larg * 0.6, 2) \
        if D.get("causa") else None
    lb = _texto(str(D.get("efeito", "")).upper(), "sans", 52 if not deitado else 36, tp.cor(T, "amarelo"), larg * 0.6, 2) \
        if D.get("efeito") else None
    ctrl = ((A[0] + B[0]) / 2 + (0 if deitado else larg * 0.32), (A[1] + B[1]) / 2 - (alt_p * 0.25 if deitado else 0))

    def bez(u):
        return ((1 - u) ** 2 * A[0] + 2 * (1 - u) * u * ctrl[0] + u * u * B[0],
                (1 - u) ** 2 * A[1] + 2 * (1 - u) * u * ctrl[1] + u * u * B[1])

    def quadro(fr, d, t):
        k = tp._p(t, 0, 0.5)
        d.ellipse([A[0] - ra, A[1] - ra, A[0] + ra, A[1] + ra], fill=tp.cor(T, "energia") + (int(255 * k),))
        kl = tp._eout(tp._p(t, 0.4, 0.6))
        prev = A
        for j in range(1, 41):
            u = j / 40 * kl
            q = bez(u)
            d.line([prev, q], fill=T["linha"] + (255,), width=4)
            prev = q
        if t > 0.9:
            for j in range(10):                              # partículas correndo
                u = ((t - 0.9) * 0.6 + j / 10) % 1.0
                px, py = bez(u)
                d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=tp.cor(T, "energia") + (255,))
        kb = tp._p(t, 1.2, dur * 0.5)
        rb = ra * (0.6 + 0.9 * tp._eout(kb))
        if kb > 0:
            d.ellipse([B[0] - rb, B[1] - rb, B[0] + rb, B[1] + rb], fill=tp.cor(T, "amarelo") + (255,))
        if la:
            tp.colar(fr, la, A[0], A[1] + ra + 16 if deitado else A[1] - ra - la.height - 16, k)
        if lb:
            tp.colar(fr, lb, B[0], B[1] + rb + 18, tp._p(t, 1.5, 0.5), "baixo")
    return quadro


def c_chegada(D, dur, T):
    """Origem externa: algo vem de fora do quadro numa trajetória e chega; ondas de sinal se espalham."""
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    R = min(larg * 0.42, alt_p * 0.30)
    pc = (tp.W / 2, y1 - 6)                                  # metade de cima do planeta, apoiada na base do palco
    alvo = (pc[0] - R * 0.25, pc[1] - R * 0.98)
    ini = (x1 + 80, y0 - 60)
    txt = _texto(D.get("texto"), "serif", 62 if not deitado else 46, T["tinta"], larg * 0.9, 2) if D.get("texto") else None
    rot = _texto(str(D.get("rotulo", "")).upper(), "sans", 40 if not deitado else 30, T.get("sec", T["acento"]), larg * 0.6, 1) \
        if D.get("rotulo") else None
    t_ch = dur * 0.5

    def quadro(fr, d, t):
        kp = tp._eout(tp._p(t, 0, 0.6))
        d.arc([pc[0] - R, pc[1] - R + (1 - kp) * 80, pc[0] + R, pc[1] + R + (1 - kp) * 80], 180, 360, fill=T["tinta"] + (255,), width=5)
        d.line([pc[0] - R, pc[1], pc[0] + R, pc[1]], fill=T["tinta"] + (int(255 * kp),), width=5)
        for j in range(1, 4):                               # paralelos do planeta
            rr = R * (1 - j * 0.22)
            d.arc([pc[0] - R, pc[1] - rr, pc[0] + R, pc[1] + rr], 180, 360, fill=T["linha"] + (255,), width=2)
        k = tp._eio(tp._p(t, 0.3, t_ch))
        ctrl = (x1 - larg * 0.1, y0 + alt_p * 0.45)
        pts = []
        for j in range(0, 31):
            u = j / 30 * k
            pts.append(((1 - u) ** 2 * ini[0] + 2 * (1 - u) * u * ctrl[0] + u * u * alvo[0],
                        (1 - u) ** 2 * ini[1] + 2 * (1 - u) * u * ctrl[1] + u * u * alvo[1]))
        for j in range(1, len(pts)):                        # rastro que some
            a_ = int(220 * j / len(pts))
            d.line([pts[j - 1], pts[j]], fill=tp.cor(T, "amarelo") + (a_,), width=6)
        ox, oy = pts[-1]
        d.ellipse([ox - 20, oy - 20, ox + 20, oy + 20], fill=tp.cor(T, "amarelo") + (255,))
        if k >= 1:                                          # chegou: ondas de sinal
            for j in range(3):
                u = ((t - 0.3 - t_ch) * 0.8 + j / 3) % 1.0
                rr = 30 + u * R * 0.9
                d.ellipse([ox - rr, oy - rr * 0.5, ox + rr, oy + rr * 0.5], outline=tp.cor(T, "energia") + (int(220 * (1 - u)),), width=4)
        if rot:
            tp.colar(fr, rot, max(x0 + rot.width / 2, min(x1 - rot.width / 2 - tp.W * 0.04, ox + 40 + rot.width / 2)), oy - 70, tp._p(t, 0.5, 0.4))
        if txt:
            tp.colar(fr, txt, tp.W / 2, y0, tp._p(t, t_ch, 0.6), "baixo")
    return quadro


def c_pontos(D, dur, T):
    """Quantidade: uma grade de 100 pontos; a porcentagem acende ponto a ponto com o contador."""
    pct = _pct(D.get("numero"))
    if pct is None:
        return None
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    lado = min(larg * (0.8 if not deitado else 0.42), alt_p * 0.62)
    gx = tp.W / 2 - lado / 2 if not deitado else x0 + larg * 0.05
    gy = y0 + (alt_p - lado) * (0.62 if not deitado else 0.5)
    passo = lado / 10
    txt = _texto(D.get("texto"), "sans_m", 44 if not deitado else 34, T["tinta"], larg * (0.85 if not deitado else 0.42), 2) \
        if D.get("texto") else None
    alvo = int(round(pct))

    def quadro(fr, d, t):
        k = tp._eout(tp._p(t, 0.4, dur * 0.55))
        acesos = int(alvo * k)
        for i in range(100):
            cx, cy = gx + passo * (i % 10 + 0.5), gy + passo * (i // 10 + 0.5)
            ki = tp._p(t, 0.02 * (i // 10), 0.3)
            if ki <= 0:
                continue
            r = passo * 0.32
            c = tp.cor(T, "amarelo") if i < acesos else _mix(T["linha"], T["tinta"], 0.25)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c + (int(255 * ki),))
        num = _texto(f"{int(round(pct * k))}%", "sans", 120 if not deitado else 110, tp.cor(T, "amarelo"))
        if deitado:
            tp.colar(fr, num, x0 + larg * 0.74, y0 + alt_p * 0.28, 1.0)
            if txt:
                tp.colar(fr, txt, x0 + larg * 0.74, y0 + alt_p * 0.28 + num.height + 20, tp._p(t, dur * 0.5, 0.5), "baixo")
        else:
            tp.colar(fr, num, tp.W / 2, y0, 1.0)
            if txt:
                tp.colar(fr, txt, tp.W / 2, gy + lado + 30, tp._p(t, dur * 0.5, 0.5), "baixo")
    return quadro


def c_anel(D, dur, T):
    """Quantidade: um anel que se preenche até a porcentagem, com o número no centro."""
    pct = _pct(D.get("numero"))
    if pct is None:
        return None
    x0, y0, x1, y1 = palco()
    larg, alt_p = x1 - x0, y1 - y0
    deitado = tp.W > tp.H
    R = min(larg, alt_p) * (0.34 if not deitado else 0.36)
    cx, cy = (tp.W / 2, y0 + alt_p * 0.38) if not deitado else (x0 + larg * 0.3, y0 + alt_p * 0.5)
    txt = _texto(D.get("texto"), "sans_m", 46 if not deitado else 36, T["tinta"], larg * (0.85 if not deitado else 0.45), 3) \
        if D.get("texto") else None
    cor_a = tp.cor(T, "perigo") if pct >= 60 and D.get("alerta") else tp.cor(T, "amarelo")

    def quadro(fr, d, t):
        k = tp._eout(tp._p(t, 0.3, dur * 0.55))
        w = max(14, int(R * 0.16))
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=T["linha"] + (255,), width=w)
        if k > 0:
            d.arc([cx - R, cy - R, cx + R, cy + R], -90, -90 + 360 * pct / 100 * k, fill=cor_a + (255,), width=w)
        num = _texto(f"{int(round(pct * k))}%", "sans", int(R * 0.55), T["tinta"])
        tp.colar(fr, num, cx, cy - num.height / 2, 1.0)
        if txt:
            if deitado:
                tp.colar(fr, txt, x0 + larg * 0.74, cy - txt.height / 2, tp._p(t, dur * 0.45, 0.5), "baixo")
            else:
                tp.colar(fr, txt, tp.W / 2, cy + R + 40, tp._p(t, dur * 0.45, 0.5), "baixo")
    return quadro


CENAS = {"duelo": c_duelo, "energia": c_energia, "escada": c_escada, "alvos": c_alvos, "caminho": c_caminho,
         "pilha": c_pilha, "barras": c_barras, "pessoas": c_pessoas, "relogio": c_relogio,
         "plataformas": c_plataformas, "sequencia": c_sequencia, "balanca": c_balanca, "caminhos": c_caminhos,
         "domino": c_domino, "fluxo": c_fluxo, "chegada": c_chegada, "pontos": c_pontos, "anel": c_anel}
