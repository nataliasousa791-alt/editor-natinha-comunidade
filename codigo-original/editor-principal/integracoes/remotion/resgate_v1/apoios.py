"""Acrescenta apoio documental nas lacunas, preservando todas as cenas existentes."""
import re
from nucleo import ia, biblioteca
from nucleo.transcrever import frases
from . import planejar as original


def complementar(plano, words, c, chave_job, log):
    if plano.get('modo') == 'limpo' or not c.get('usar_ia'):
        return plano
    F = frases(words, max_palavras=18, pausa=0.6)
    D = original.DENS[plano['formato']]
    total = max(w['e'] for w in words)
    existentes = plano['cenas']
    chave_video, job = chave_job.split('#')
    usados = {x['asset']['id'] for x in existentes if x.get('asset')}
    sem = {original._n(x) for x in c['sem_broll']}

    def janela(f, palavra):
        a = max(f['s'] - .1, 0)
        if palavra['s'] - f['s'] >= 2.5:
            a = palavra['s'] - .4
        b = min(total, max(a + D['dur_min'], min(f['e'] + .25, a + D['dur_max'])))
        return round(a, 3), round(b, 3)

    def cabe(a, b):
        return b - a >= D['dur_min'] - .001 and all(
            b + D['sep'] <= x['ini'] or a >= x['fim'] + D['sep'] for x in existentes)

    elegiveis = []
    for k, f in enumerate(F):
        if any(original._n(words[i]['w']) in sem for i in range(f['i0'], f['i1'] + 1)):
            continue
        # Só oferece frases com espaço real; cartões, números e títulos conservados.
        if any(cabe(*janela(f, words[i])) for i in range(f['i0'], f['i1'] + 1)):
            elegiveis.append((k, f))
    novos = []
    contexto = ' '.join(f['texto'] for f in F)
    for start in range(0, len(elegiveis), 50):
        lote = elegiveis[start:start + 50]
        texto = '\n'.join(f"F{k} | {f['texto']}" for k, f in lote)
        try:
            r, _ = ia.pedir(
                'Você pesquisa imagens documentais para o Editor Natinha. Responda apenas JSON. '
                'A edição e o motion estão aprovados: acrescente SOMENTE imagens de apoio pertinentes nas lacunas.',
                'Contexto integral:\n' + contexto + '\n\nFrases com espaço disponível:\n' + texto + '\n\n'
                'Examine todas as frases. Identifique objetos, ações, exemplos e consequências concretas que '
                'ficaram sem imagem. A cobertura atual ficou escassa: procure oportunidades narrativas reais '
                'ao longo de cada argumento, sem impor frequência ou número de cenas. '
                'Não se limite a uma imagem para o tema inteiro: examine os exemplos e ações distintos de '
                'cada passagem disponível e proponha apoio quando torna essa passagem mais clara. '
                'Pode propor vídeo real ou fotografia documental. Mantenha a apresentadora em perguntas pessoais, '
                'ironia, relatos íntimos e passagens sensíveis. Não proponha títulos, cartões ou outros efeitos. '
                'Use termos simples pesquisáveis: mãos organizando contas, pessoa tentando dormir, mensagem '
                'no celular, gaveta com fotografias, conforme a fala. Evite imagens abstratas, animações de cérebro, '
                'luz energética, telas de glitch e consultas que misturem conceitos incompatíveis. '
                'Uma analogia deve ser sustentada pela fala; nunca trate metáfora espiritual como fato visível. '
                'Proibido: iate, mansão ou luxo para representar riqueza; favela para representar pobreza; '
                'multidão ou fábrica antiga genérica para representar sociedade ou trabalho. '
                'O gatilho deve ser literal. Ofereça até três consultas alternativas para o mesmo significado. '
                'JSON: {"cenas":[{"frase":"F3","gatilho":"palavra literal",'
                '"busca":"simple English query","consultas":["outra consulta"],'
                '"justificativa":"por que melhora a compreensão","rotulo":"1-2 palavras"}]}',
                log, temperatura=.25)
        except Exception as e:
            log(f'Apoios adicionais indisponíveis ({type(e).__name__}); cenas aprovadas preservadas.')
            continue
        permitidas = {k for k, _ in lote}
        # A IA pode devolver lista diretamente, em vez do objeto solicitado.
        cenas = r.get('cenas', []) if isinstance(r, dict) else (r if isinstance(r, list) else [])
        if not isinstance(cenas, list):
            cenas = []
        for x in cenas:
            if not isinstance(x, dict):
                continue
            try:
                k = int(str(x.get('frase', '')).upper().lstrip('F'))
            except ValueError:
                continue
            if k not in permitidas or not x.get('busca') or not x.get('justificativa'):
                continue
            f = F[k]
            hit = original.trecho(words, x.get('gatilho', ''), f['i0'], f['i1'] + 1)
            if not hit:
                continue
            i = hit[0]; a, b = janela(f, words[i])
            if cabe(a, b):
                novos.append((a, b, i, f, x))
    log(f'Pesquisa de apoios: {len(novos)} oportunidades com espaço, mantendo as cenas atuais.')
    acrescentadas = 0
    for a, b, i, f, x in sorted(novos, key=lambda y: y[0]):
        if not cabe(a, b):
            continue
        qs = list(dict.fromkeys([x['busca']] + [q for q in x.get('consultas', []) if isinstance(q, str)]))[:4]
        log(f"Apoio em pesquisa {a:.1f}-{b:.1f}s: {qs}; intenção: {x['justificativa']}")
        clip = biblioteca.obter(biblioteca.chave_busca(x['busca']), chave_video, usados, log,
                               job, qs, frase=f['texto'], intencao=x['justificativa'])
        if not clip:
            # Sem acrescentar cartão de substituição: mantém exatamente a cena atual.
            continue
        usados.add(clip['id'])
        j = i - 1 if i > f['i0'] and original._n(words[i - 1]['w']) in original.ARTIGO else i
        dur = b - a + .9; inicio = .6 if clip.get('duracao', 8) >= dur + .8 else 0
        existentes.append(dict(id=f'apoio_extra_{acrescentadas}', tipo='broll',
            layout='C' if plano['formato'] == '16x9' else 'B', ini=a, fim=b,
            frase=[dict(w=words[t]['w'].strip(',.;:?!'), s=words[t]['s']) for t in range(j, i + 1)],
            fala=f['texto'], gatilho=dict(palavra=words[i]['w'], t=words[i]['s']),
            rotulo=str(x.get('rotulo') or 'CONTEXTO').upper()[:24],
            justificativa=str(x['justificativa'])[:300], apoio_adicional=True,
            asset=dict(id=clip['id'], arquivo='broll_' + clip['arquivo'], origem=clip['caminho'],
                fonte=clip['fonte'], autor=clip['autor'], licenca=clip['licenca'],
                revisado=clip.get('revisado', False), inicio=inicio, duracao=clip.get('duracao', 8),
                w=clip.get('largura'), h=clip.get('altura'), tipo_midia=clip.get('tipo_midia', 'video'),
                laco=clip.get('duracao', 8) < dur + inicio)))
        acrescentadas += 1
    existentes.sort(key=lambda x: x['ini'])
    # Mesmo cálculo dos blocos do planejador atual. Layouts e animações não são alterados.
    for lay in ('B', 'C'):
        blocos = []
        for x in existentes:
            if x['layout'] != lay:
                continue
            if blocos and x['ini'] - blocos[-1][1] < .6:
                blocos[-1][1] = x['fim']
            else:
                blocos.append([x['ini'], x['fim']])
        plano['blocos' + lay] = blocos
    log(f'Apoios adicionais: {acrescentadas} inserções pertinentes; todas as cenas anteriores conservadas.')
    return plano


def planejar(words, blocos, total, chave_job, rosto, fonte_wh, c, log, formato='9x16', modo='completo'):
    plano = original.planejar(words, blocos, total, chave_job, rosto, fonte_wh, c, log, formato, modo)
    return complementar(plano, words, c, chave_job, log)
