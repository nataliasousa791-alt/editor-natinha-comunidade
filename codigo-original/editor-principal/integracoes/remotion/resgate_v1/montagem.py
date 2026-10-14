"""FFmpeg: normaliza o trecho bruto (orientação, pixels quadrados, 30 fps) e monta A-roll + voz a partir do MAPA automático."""
from nucleo.util import run


def normalizar(src, ini, fim, son, fps, saida_v, wav48, wav16):
    giro = (son["filtro_giro"] + ",") if son["filtro_giro"] else ""
    vf = f"{giro}scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1,fps={fps}"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", src, "-an", "-vf", vf,
         "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-g", "15", "-bf", "0", "-pix_fmt", "yuv420p", "-threads", "3", saida_v])
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", "48000", wav48])
    run(["ffmpeg", "-v", "error", "-y", "-i", wav48, "-ar", "16000", wav16])


def montar(fonte_v, wav48, mapa, fps, saida_v, saida_a, grupo=40):
    """A-roll + voz a partir do MAPA, em GRUPOS de blocos (nunca um filtro gigante), com checkpoint por grupo."""
    import os,hashlib,json
    # Preflight: interrompe antes de consumir disco se um checkpoint pedir quadros fora da fonte.
    frames_fonte=int(json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames','-of','json',fonte_v]))['streams'][0]['nb_frames'])
    for i,b in enumerate(mapa):
        inicio=round(b['src']*fps)
        if inicio<0 or b['n']<1 or inicio+b['n']>=frames_fonte:
            raise RuntimeError(f'Mapa fora da fonte no bloco {i}: inicio={inicio}, n={b["n"]}, total={frames_fonte}; corrigir mapa antes de montar')
    signature=hashlib.sha256(json.dumps([mapa,fps,os.path.getsize(fonte_v),os.path.getmtime(fonte_v),os.path.getsize(wav48),os.path.getmtime(wav48)],sort_keys=True).encode()).hexdigest()[:20]
    pasta = os.path.join(os.path.dirname(saida_v), "_montagem_resgate_"+signature); os.makedirs(pasta, exist_ok=True)
    def valid_video(path,expected):
        if not os.path.exists(path):return False
        try:
            r=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames','-of','json',path]))
            return int(r['streams'][0].get('nb_frames',0))==expected
        except (RuntimeError,ValueError,KeyError,IndexError):return False
    def valid_audio(path,seconds):
        if not os.path.exists(path):return False
        import wave
        try:
            with wave.open(path,'rb') as w:return abs(w.getnframes()/w.getframerate()-seconds)<1/48000
        except (wave.Error,EOFError,OSError):return False
    vs, as_ = [], []
    for g in range(0, len(mapa), grupo):
        bl = mapa[g:g + grupo]
        v, a = os.path.join(pasta, f"v_{g:05}.mp4"), os.path.join(pasta, f"a_{g:05}.wav")
        vs.append(v); as_.append(a)
        if not valid_video(v,sum(b["n"] for b in bl)):
            sel = "+".join(f"between(n,{round(b['src'] * fps)},{round(b['src'] * fps) + b['n'] - 1})" for b in bl)
            ini = max(0, round(bl[0]["src"] * fps) - 2 * fps)          # busca rápida até perto do grupo
            sel = "+".join(f"between(n,{round(b['src'] * fps) - ini},{round(b['src'] * fps) - ini + b['n'] - 1})" for b in bl)
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ini / fps:.4f}", "-i", fonte_v, "-an", "-vf",
                 f"select='{sel}',setpts=N/{fps}/TB", "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-g", "15", "-bf", "0",
                 "-pix_fmt", "yuv420p", "-threads", "3", v])
        if not valid_audio(a,sum(b["n"] for b in bl)/fps):
            n = len(bl)
            fc = f"[0:a]asplit={n}" + "".join(f"[s{k}]" for k in range(n)) + ";"
            for k, b in enumerate(bl):
                a0 = round(b["src"] * fps) / fps; d = b["n"] / fps
                fc += (f"[s{k}]atrim=start={a0:.5f}:duration={d:.5f},asetpts=PTS-STARTPTS,"
                       f"afade=t=in:d=0.006,afade=t=out:st={max(0, d - 0.008):.5f}:d=0.008[a{k}];")
            fc += "".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[out]"
            run(["ffmpeg", "-v", "error", "-y", "-i", wav48, "-filter_complex", fc, "-map", "[out]", "-ar", "48000", a])
    lv, la = os.path.join(pasta, "v.txt"), os.path.join(pasta, "a.txt")
    open(lv, "w", encoding="utf-8").write("".join(f"file '{x.replace(os.sep, '/')}'\n" for x in vs))
    open(la, "w", encoding="utf-8").write("".join(f"file '{x.replace(os.sep, '/')}'\n" for x in as_))
    total = sum(b["n"] for b in mapa)
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lv,"-frames:v",str(total),"-c:v","copy",saida_v])
    count=json.loads(run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=nb_frames","-of","json",saida_v]))
    if int(count["streams"][0].get("nb_frames",0))!=total:raise RuntimeError("Montagem incompleta; não prolongar quadro congelado para esconder erro.")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", la, "-af",
         "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,loudnorm=I=-14:TP=-1.5:LRA=9,apad",
         "-t", f"{total / fps:.4f}", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", saida_a])


def planos_camera(cortes, total, minimo=4.0):
    """Mesma regra da composição Remotion: troca de enquadramento só em cortes espaçados (esconde o jump cut)."""
    pl = [0.0]
    for c in cortes:
        if c - pl[-1] >= minimo and total - c >= 2: pl.append(c)
    return pl


def yt_limpo(natinha, voz, cortes, total, fps, fonte_wh, rosto, saida, pasta, log):
    """YouTube 16:9 SEM B-roll: A-roll editado, punch-in alternado (1.00/1.08) centrado no rosto, grão e vinheta leves.
    Escala ÚNICA em x e y (cover); fonte que não seja horizontal entra inteira sobre fundo desfocado dela mesma."""
    import os
    W, H = 1920, 1080
    fw, fh = fonte_wh
    par = lambda x: int(round(x / 2)) * 2
    pl = planos_camera(cortes, total)
    os.makedirs(pasta, exist_ok=True)
    segs, escalas = [], []
    for k, a in enumerate(pl):
        b = pl[k + 1] if k + 1 < len(pl) else total
        n = round(b * fps) - round(a * fps)
        if n <= 0: continue
        z = 1.08 if k % 2 else 1.0
        arq = os.path.join(pasta, f"plano_{k:04}.mp4"); segs.append(arq)
        if fw / fh >= 1.5:                                   # horizontal: preenche 16:9 sem deformar
            s = max(W / fw, H / fh) * z
            sw, sh = par(fw * s), par(fh * s)
            x = min(max(0, round(rosto["cx"] * sw - W / 2)), sw - W); y = min(max(0, round(rosto["cy"] * sh - H * 0.42)), sh - H)
            vf = f"scale={sw}:{sh}:flags=lanczos,crop={W}:{H}:{x}:{y},setsar=1"
            escalas.append(round(abs(sw / fw - sh / fh), 4))
        else:                                                # vertical/quadrado: inteiro + fundo desfocado
            s = H / fh * z; sw, sh = par(fw * s), par(fh * s)
            vf = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,eq=brightness=-0.18[bg];"
                  f"[b]scale={sw}:{sh}:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
            escalas.append(round(abs(sw / fw - sh / fh), 4))
        if os.path.exists(arq): continue
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{round(a * fps) / fps:.4f}", "-i", natinha, "-frames:v", str(n), "-an",
             "-vf", vf + ",noise=alls=3:allf=t,vignette=angle=PI/5", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
             "-pix_fmt", "yuv420p", "-r", str(fps), "-threads", "3", arq])
    lista = os.path.join(pasta, "planos.txt")
    open(lista, "w", encoding="utf-8").write("".join(f"file '{p.replace(os.sep, '/')}'\n" for p in segs))
    mudo = os.path.join(pasta, "mudo.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", mudo])
    run(["ffmpeg", "-v", "error", "-y", "-i", mudo, "-i", voz, "-map", "0:v", "-map", "1:a", "-c", "copy",
         "-t", f"{total:.3f}", "-movflags", "+faststart", saida])
    log(f"YouTube limpo: {len(segs)} planos, erro máximo de proporção {max(escalas or [0])}")
    return dict(planos=len(segs), erro_proporcao_max=max(escalas or [0]))
