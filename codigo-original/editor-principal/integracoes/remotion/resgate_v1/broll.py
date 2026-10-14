"""Busca ampliada somente para apoios: biblioteca semântica, vídeos e fotografias."""
import hashlib, json, os, subprocess, time, urllib.parse, urllib.request
from pathlib import Path
from nucleo.util import cfg
from nucleo.biblioteca import UA

_biblioteca = None
_obter_original = None


def configurar(biblioteca):
    global _biblioteca, _obter_original
    _biblioteca = biblioteca
    if biblioteca.obter is not obter:
        _obter_original = biblioteca.obter


def _nota(imagens, frase, log):
    if not imagens:
        return []
    from nucleo import ia
    try:
        r, _ = ia.pedir(
            'Você seleciona imagens documentais para Natinha. Seja exigente e responda somente JSON.',
            f'Fala: {frase}\nAs {len(imagens)} imagens abaixo representam candidatos de apoio. '
            'Dê nota de 0 a 10 por pertinência ao argumento: objeto, ação, consequência ou analogia sustentada. '
            'Não exija que a imagem ilustre todas as palavras da frase. Celular pode representar a chegada de '
            'uma mensagem; organização de contas pode representar dívida, sem precisar mostrar os valores ditos. '
            'Quando houver intenção editorial e consultas, a ação/objeto desejado precisa aparecer de fato. '
            'Não basta um clima emocional parecido. Não atribua ações aos quadros que eles não mostram. '
            'Uma pessoa genérica numa ação pode ilustrar uma situação, sem identificá-la como a pessoa '
            'citada nem atribuir fatos pessoais a alguém identificável. '
            'Nota baixa para clichês (iate/mansão/luxo para riqueza, favela para pobreza, multidão genérica '
            'para sociedade, fábrica antiga para trabalho), imagens aleatórias, pose publicitária, animação, IA, abstração energética '
            'ou algo que introduza um fato. JSON: {"notas":[n1,n2,...]}.',
            log, temperatura=.1, imagens=imagens)
        notas=[float(n) for n in r.get('notas', [])]
        log(f'Notas de pertinência: {notas}.')
        return notas
    except Exception as e:
        log(f'Triagem de apoio indisponível ({type(e).__name__}); material não inserido.')
        return []


def _avaliar(hits, frase, log):
    imagens, validos = [], []
    for h in hits[:10]:
        vs = h.get('videos', {})
        url = (vs.get('tiny') or {}).get('thumbnail') or (vs.get('small') or {}).get('thumbnail') or h.get('webformatURL') or h.get('previewURL')
        if not url:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as f:
                imagens.append(f.read())
            validos.append(h)
        except Exception:
            continue
    notas = _nota(imagens, frase, log)
    minimo = cfg().get('broll_nota_min', 7)
    aprovados = sorted([(n, h) for n, h in zip(notas, validos) if n >= minimo], key=lambda x: -x[0])
    for n, h in aprovados:
        h['_nota_ia'] = n
    log(f'Triagem de apoio: {len(aprovados)}/{len(validos)} pertinentes (mínimo {minimo}).')
    return [h for n, h in aprovados]


def _online():
    return os.environ.get('NATINHA_REMOTION_OFFLINE', '1') == '0'


def _confirmar(clip, contexto, log):
    """Confere o arquivo baixado, não apenas a miniatura ou os rótulos do banco."""
    if clip.get('revisado') or not _online():
        return True
    frames=[]
    for t in (1, min(3.5, max(1, clip.get('duracao',6)-.5))):
        try:
            r=subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(t),'-i',clip['caminho'],
                '-frames:v','1','-vf','scale=480:-2','-threads','1','-f','image2pipe','-vcodec','mjpeg','-'],
                capture_output=True,timeout=20,check=True)
            if r.stdout:frames.append(r.stdout)
        except (OSError,subprocess.SubprocessError):
            return False
    notas=_nota(frames,contexto,log)
    ok=len(notas)==2 and min(notas)>=cfg().get('broll_nota_min',7)
    if not ok:log(f"Apoio rejeitado após conferir o arquivo real: {clip['id']}.")
    return ok


def _livre(m, chave_video, usados, job, uso):
    return (m.get('id') not in usados and bool(m.get('fonte') and m.get('licenca'))
        and Path(_biblioteca.B, 'clipes', m['arquivo']).is_file()
        and not any(u.split('|')[0] == chave_video and u != f'{chave_video}|{job}' for u in uso.get(m['id'], [])))


def _local(man, uso, chave_video, usados, job, consultas, frase, log):
    livres = [m for m in man if _livre(m, chave_video, usados, job, uso)]
    if not livres or not _online():
        return None
    from nucleo import ia
    # Metadados escolhem candidatos; quadro real decide pertinência, inclusive nos itens antigos sem nota.
    meta = [{'indice':i, 'conceito':m.get('conceito'), 'busca':m.get('busca'), 'tags':m.get('tags'),
             'frase_anterior':m.get('frase_avaliada'), 'tipo':m.get('tipo_midia', 'video')} for i, m in enumerate(livres)]
    try:
        r, _ = ia.pedir('Você pesquisa a biblioteca documental de Natinha. Responda só JSON.',
            f'Fala: {frase}\nConsultas: {consultas}\nBiblioteca: {json.dumps(meta, ensure_ascii=False)}\n'
            'Selecione até 4 índices que possam apoiar o argumento por objeto ou ação. '
            'Não precisa coincidir com a chave de cadastro. Exclua os sem relação. '
            'Esta seleção só prepara inspeção de quadros reais. JSON: {"indices":[0,3]}.', log, temperatura=.1)
        ids = list(dict.fromkeys(i for i in r.get('indices', []) if isinstance(i, int) and 0 <= i < len(livres)))[:4]
    except Exception as e:
        log(f'Consulta à biblioteca indisponível ({type(e).__name__}).')
        return None
    itens, imagens = [], []
    for i in ids:
        m = livres[i]; path = str(Path(_biblioteca.B, 'clipes', m['arquivo']))
        # Dois instantes do clipe: não confunde isso com aprovação humana em movimento.
        frames = []
        for t in (1, min(3.5, max(1, m.get('duracao', 6) - .5))):
            try:
                p = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(t),'-i',path,
                    '-frames:v','1','-vf','scale=480:-2','-threads','1','-f','image2pipe','-vcodec','mjpeg','-'],
                    capture_output=True, timeout=20, check=True)
                if p.stdout:
                    frames.append(p.stdout)
            except (OSError, subprocess.SubprocessError):
                continue
        if frames:
            itens.append(m); imagens.append(frames[0])
            # Inspeção da segunda amostra em chamada separada abaixo, sem mudar a indexação dos candidatos.
            m = dict(m); m['_segunda_amostra'] = frames[-1]; itens[-1] = m
    notas1 = _nota(imagens, frase, log)
    notas2 = _nota([m['_segunda_amostra'] for m in itens], frase, log)
    minimo = cfg().get('broll_nota_min', 7)
    av = [(min(a, b), m) for a, b, m in zip(notas1, notas2, itens) if min(a, b) >= minimo]
    if not av:
        return None
    _, m = max(av, key=lambda x:x[0]); m = dict(m); m.pop('_segunda_amostra', None)
    m['caminho'] = str(Path(_biblioteca.B, 'clipes', m['arquivo']))
    log(f"Apoio recuperado da biblioteca por contexto: {m['id']}.")
    return m


def _alternativas(frase, consultas, log):
    from nucleo import ia
    try:
        r, _ = ia.pedir('Você pesquisa filmagens e fotografias documentais. Responda apenas JSON.',
            f'Fala: {frase}\nBuscas sem resultado suficiente: {consultas}\n'
            'Reformule em objetos e ações concretas que apoiam o argumento. '
            'Não busque ilustração literal de frase abstrata, cérebro animado ou luz energética. '
            'Até 3 consultas curtas em inglês, com até 4 palavras cada. '
            'Exemplo: ausência de salário -> mãos organizando contas; privação de sono -> pessoa acordada na cama. '
            'Sem inventar fato. JSON: {"consultas":["..."]}.', log, temperatura=.2)
        return [str(q)[:80] for q in r.get('consultas', []) if isinstance(q,str) and q.strip()][:3]
    except Exception:
        return []


def _fotos(conceito, consultas, man, log, frase):
    from nucleo.ia import _cfg_antigo
    chave = (_cfg_antigo().get('pixabay_chave') or os.environ.get('PIXABAY_API_KEY') or '').strip()
    if not chave or not _online():
        return
    B = Path(_biblioteca.B); (B/'imagens').mkdir(exist_ok=True)
    ids = {m['id'] for m in man}; proibidas = cfg()['busca_proibida']
    for q in consultas[:3]:
        args = {'q':q,'image_type':'photo','orientation':'horizontal','min_width':1280,
                'safesearch':'true','per_page':15}
        try:
            cache=B/'cache_fotografia';cache.mkdir(exist_ok=True)
            cached=cache/(hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()+'.json')
            if cached.is_file() and time.time()-cached.stat().st_mtime<86400:
                hits=json.loads(cached.read_text(encoding='utf-8')).get('hits',[])
            else:
                with urllib.request.urlopen(urllib.request.Request('https://pixabay.com/api/?'+urllib.parse.urlencode(dict(args,key=chave)),headers=UA),timeout=20) as f:
                    result=json.load(f)
                hits=result.get('hits',[])
                tempcache=cached.with_suffix('.tmp');tempcache.write_text(json.dumps(result),encoding='utf-8');tempcache.replace(cached)
        except Exception as e:
            # Nunca registra a URL que contém a chave.
            log(f'Busca fotográfica indisponível ({type(e).__name__}).');continue
        hits=[h for h in hits if f"PXIMG_{h['id']}" not in ids and h.get('type')=='photo'
              and not any(p in h.get('tags','').lower() for p in proibidas)]
        for h in _avaliar(hits,frase,log):
            ident=f"PXIMG_{h['id']}";img=B/'imagens'/f'{ident}.jpg';proxy=B/'clipes'/f'{ident}.mp4'
            temp=proxy.with_name(proxy.stem+'.partial.mp4')
            try:
                with urllib.request.urlopen(urllib.request.Request(h['largeImageURL'],headers=UA),timeout=40) as f:
                    img.write_bytes(f.read())
                subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-loop','1','-i',str(img),'-t','12',
                    '-vf',"scale='min(1280,iw)':-2:flags=lanczos,setsar=1",'-r','30','-an',
                    '-c:v','libx264','-preset','fast','-crf','18','-g','30','-bf','0','-threads','1',
                    '-pix_fmt','yuv420p',str(temp)],capture_output=True,timeout=60,check=True)
                temp.replace(proxy);pr=_biblioteca.probe(str(proxy))
            except (OSError, subprocess.SubprocessError, ValueError, KeyError) as e:
                log(f'Fotografia não preparada ({type(e).__name__}).');continue
            item=dict(id=ident,conceito=conceito,arquivo=proxy.name,fonte=h['pageURL'],autor=h['user'],
                licenca='Pixabay Content License',tipo_midia='fotografia',original=str(img),
                tags=h.get('tags',''),duracao=pr['dur'],largura=pr['w'],altura=pr['h'],revisado=False,
                busca=q,nota_ia=h['_nota_ia'],frase_avaliada=frase[:200])
            man.append(item);_biblioteca._salvar(_biblioteca.MAN,man)
            log(f'Fotografia documental preparada: {ident}; mesma composição e tratamento dos apoios.')
            return


def obter(conceito, chave_video, ja_no_job, log, job='', consultas=None, frase='', intencao=''):
    man=_biblioteca._ler(_biblioteca.MAN,[]);uso=_biblioteca._ler(_biblioteca.USO,{})
    qs=consultas or cfg()['conceitos'].get(conceito,{}).get('busca',[])
    contexto=frase + ('\nIntenção editorial do apoio: '+intencao if intencao else '')
    contexto+='\nObjeto/ação sugeridos pelas consultas: '+', '.join(qs)
    rejeitados=set(ja_no_job)
    minimo=cfg().get('broll_nota_min',7)
    if any(m.get('conceito')==conceito and _livre(m,chave_video,rejeitados,job,uso)
           and (m.get('revisado') or (m.get('nota_ia') or 0)>=minimo) for m in man):
        clip=_obter_original(conceito,chave_video,rejeitados,log,job,consultas,frase=contexto)
        if clip and _confirmar(clip,contexto,log):return clip
        if clip:rejeitados.add(clip['id'])
    if _online():
        local=_local(man,uso,chave_video,rejeitados,job,qs,contexto or ' '.join(qs),log)
        if local:
            return local
    clip=_obter_original(conceito,chave_video,rejeitados,log,job,consultas,frase=contexto)
    if not _online() or (clip and _confirmar(clip,contexto,log)):
        return clip
    if clip:rejeitados.add(clip['id'])
    outras=_alternativas(contexto,qs,log)
    if outras:
        clip=_obter_original(conceito,chave_video,rejeitados,log,job,outras,frase=contexto)
        if clip and _confirmar(clip,contexto,log):
            return clip
        if clip:rejeitados.add(clip['id'])
    man=_biblioteca._ler(_biblioteca.MAN,[])
    _fotos(conceito,list(dict.fromkeys(outras+qs)),man,log,contexto)
    # Agora o original encontra a fotografia como mídia compatível, sem redesenhar Remotion.
    foto=next((dict(m) for m in man if m.get('tipo_midia')=='fotografia' and m['conceito']==conceito
               and _livre(m,chave_video,rejeitados,job,uso)
               and (m.get('nota_ia') or 0)>=cfg().get('broll_nota_min',7)),None)
    if foto:
        foto['caminho']=str(Path(_biblioteca.B,'clipes',foto['arquivo']))
        if not _confirmar(foto,contexto,log):return None
    return foto
