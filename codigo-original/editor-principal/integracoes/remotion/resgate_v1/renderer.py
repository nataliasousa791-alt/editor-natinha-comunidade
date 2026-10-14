"""Composição aprovada integral, sem quota de motion; uma codificação por parte."""
from pathlib import Path
import copy,ctypes,hashlib,json,os,shutil,subprocess,time
from .legendas import exportar
ROOT=Path(__file__).resolve().parent

def exigir_recursos(minimo_gb=2.5):
    if os.name!='nt':return None
    class MEM(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ['total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extended']]
    m=MEM();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise RuntimeError('Não foi possível conferir a memória antes da edição.')
    free=m.available/2**30
    if free<minimo_gb:raise RuntimeError(f'Render não iniciado: {free:.2f} GB de RAM livre; o perfil aprovado reserva {minimo_gb:.1f} GB. Feche aplicativos que você não esteja usando e tente novamente. Seus vídeos foram preservados.')
    return free

def adaptar_plano(original):
    p=copy.deepcopy(original);total=p['frames']/p['fps'];scenes=[]
    for old in sorted(p.get('cenas',[]),key=lambda x:x['ini']):
        c=copy.deepcopy(old)
        if c['ini']>=total:continue
        if c['tipo'] in ('abertura','fechamento','enfase'):
            if c['tipo']=='abertura':c['palavras']=[{'w':w,'s':c['ini']+.12+i*.12} for i,w in enumerate(c.get('texto',[]))]
            if not c.get('palavras'):continue
            c['tipo']='cartao'
        c['layout']='B'
        if c['tipo']=='broll' and not c.get('asset'):raise ValueError('B-roll sem arquivo; resolver na pauta antes do render.')
        if c['tipo'] in ('broll','cartao','numero'):scenes.append(c)
    out=[]
    for i,c in enumerate(scenes):
        nxt=scenes[i+1]['ini'] if i+1<len(scenes) else total
        c['fim']=min(c['fim'],nxt,total)
        if c['tipo'] in ('cartao','numero'):c['fim']=nxt
        out.append(c)
        if c['tipo']=='broll' and nxt-c['fim']>.45 and c.get('frase'):
            a=c['fim'];out.append({'id':c['id']+'_sustentacao','tipo':'cartao','layout':'B','ini':a,'fim':nxt,
             'palavras':[dict(w=w['w'],s=a-.55) for w in c['frase']],'fala':c.get('fala',''),
             'justificativa':'Sustentar o conceito já mencionado após a imagem, sem repetir o clipe.'})
    p.update(cenas=out,layoutFixo='B',blocosB=[[-1,total+1]],blocosC=[],semLegendas=True,semAudio=True)
    p.pop('fundo',None) # Mesmo fundo da amostra aprovada; o intermediário antigo tinha outro tratamento.
    mode=original.get("captionMode") or json.loads((ROOT/"caption_profile.json").read_text(encoding="utf-8"))["default"]
    if mode not in ("legacy","motion_orange_v1"):
        raise ValueError("Perfil de legenda desconhecido")
    p["captionMode"]=mode
    if mode=="motion_orange_v1":
        from .caption_cues import gerar_cues,validar_cues
        p["captionCues"]=gerar_cues(p.get("legendas",[]))
        validar_cues(p["captionCues"],p.get("legendas",[]))
    return p

def fingerprint(plan,pub):
    h=hashlib.sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True).encode())
    names={plan['fonte']['arquivo'],plan.get('audio','voz.m4a'),'grao.png'}
    names.update(c['asset']['arquivo'] for c in plan['cenas'] if c.get('asset'))
    files=[Path(pub)/n for n in names]+list((Path(pub)/'fonts').glob('*'))
    files += [f for f in ROOT.rglob('*') if f.is_file() and f.suffix in ('.py','.jsx','.json','.cjs')]
    for f in sorted(files):
        if not f.is_file():raise FileNotFoundError(f)
        h.update(f.name.encode())
        with f.open('rb') as source:
            for b in iter(lambda:source.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))

def valid_segment(path,frames,fps,formato):
    if not Path(path).is_file():return False
    try:
        p=probe(path);v=next(x for x in p['streams'] if x['codec_type']=='video')
        return (int(v.get('nb_frames',0))==frames and v['r_frame_rate']==f'{fps}/1'
         and (v['width'],v['height'])==((1080,1920) if formato=='9x16' else (1920,1080)))
    except (OSError,ValueError,KeyError,StopIteration,subprocess.CalledProcessError):return False

def renderizar(sub,plano_json,pub,saida,frames,fps,c,log):
    from nucleo.util import REMOTION
    t=time.monotonic();p=adaptar_plano(json.loads(Path(plano_json).read_text(encoding='utf-8')))
    # Um unico browser para cortes verticais; guard adaptado para PC de 8 GiB.
    minimo_inicial=1.85 if p['formato']=='9x16' else 2.5
    minimo_partes=1.70 if p['formato']=='9x16' else 2.0
    initial_ram=exigir_recursos(minimo_inicial)
    pub=str(Path(pub).resolve());saida=Path(saida).resolve();key=fingerprint(p,pub)
    cache=Path(sub.p('resgate_cache')).resolve()/key;cache.mkdir(parents=True,exist_ok=True)
    final_marker=saida.with_suffix('.resgate.json')
    if saida.exists():
        if final_marker.exists() and json.loads(final_marker.read_text())['hash']==key and valid_segment(saida,frames,fps,p['formato']):
            log('Resgate: saída validada por hash e quadros; reaproveitada.');return 0
        raise RuntimeError('MP4 anterior preservado. Inicie um projeto novo para aplicar o padrão aprovado.')
    (cache/'plano_aplicado.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
    log('Resgate aprovado: composição original, sem quota de motion; partes sequenciais de até 8s.')
    segments=[];measure=[];step=max(fps,min(int(c.get('render_parte_seg',8)*fps),8*fps))
    for i,a in enumerate(range(0,frames,step)):
        b=min(frames,a+step);output=cache/f'parte_{i:04d}.mp4';segments.append(output)
        if valid_segment(output,b-a,fps,p['formato']):continue
        exigir_recursos(minimo_partes);ass=cache/f'legendas_{i:04d}.ass';exportar(ass,p,a/fps,b/fps)
        cfg={'plan':p,'publicDir':pub,'remotionRoot':str(REMOTION),'bundleDir':str(cache/'bundle'),
         'cacheDir':str(cache),'assPath':str(ass),'start':a,'end':b,'output':str(output)}
        settings=cache/f'render_{i:04d}.json';settings.write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
        start=time.monotonic()
        proc=subprocess.run(['node',str(ROOT/'render_part.cjs'),str(settings)],cwd=REMOTION,capture_output=True,text=True,encoding='utf-8',errors='replace',
         creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0)
        (cache/f'parte_{i:04d}.log').write_text((proc.stdout or '')+'\n'+(proc.stderr or ''),encoding='utf-8')
        if proc.returncode or not valid_segment(output,b-a,fps,p['formato']):raise RuntimeError(f'Parte {i+1} falhou; checkpoint preservado, consultar {cache.name}/parte_{i:04d}.log')
        measure.append({'a':a,'b':b,'seconds':round(time.monotonic()-start,3)})
        log(f'Resgate: parte {i+1}/{(frames+step-1)//step} pronta; {b/fps:.1f}s de vídeo.')
    for i,seg in enumerate(segments):
        if not valid_segment(seg,min(step,frames-i*step),fps,p['formato']):
            raise RuntimeError(f'Parte {i+1} incompleta antes da união; retome este mesmo projeto.')
    listing=cache/'partes.txt'
    listing.write_text(''.join("file '"+s.as_posix().replace("'","'\\''")+"'\n" for s in segments),encoding='utf-8')
    audio=Path(pub)/p.get('audio','voz.m4a');temporary=cache/'saida_validacao.mp4'
    cmd=['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','copy' if audio.suffix.lower() in ('.m4a','.aac') else 'aac']
    if audio.suffix.lower() not in ('.m4a','.aac'):cmd+=['-b:a','192k','-ar','48000']
    subprocess.run(cmd+['-t',f'{frames/fps:.9f}','-movflags','+faststart',str(temporary)],check=True)
    if not valid_segment(temporary,frames,fps,p['formato']):raise RuntimeError('Validação final de quadros/formato falhou; produção preservada.')
    report={'perfil':'resgate_aprovado_v1','hash':key,'frames':frames,'fps':fps,'formato':p['formato'],'seconds':round(time.monotonic()-t,3),
     'initialFreeRAMGiB':initial_ram,'segments':measure,'videoEncodesPerSegment':1,'concatReencode':False,'audioContinuous':True,
     'artisticApprovalPerVideoRequired':True,'note':'Composição Remotion integral para preservar acabamento; FFmpeg prepara, legenda, codifica e concatena.'}
    publish=saida.with_name(saida.name+".partial")
    shutil.copy2(temporary,publish)
    with publish.open("r+b") as f:os.fsync(f.fileno())
    os.replace(publish,saida)
    final_marker.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path(sub.p('resgate_relatorio.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report['seconds']

