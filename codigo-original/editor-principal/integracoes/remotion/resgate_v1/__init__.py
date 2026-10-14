"""Perfil aprovado pela criadora: integração reversível pelo runner."""
def ativar():
    from nucleo import render, planejar as antigo, montar, biblioteca
    from . import renderer, planejar, montagem, broll, apoios
    # Guard normal de 2.5 GiB. Somente recuperacao com YouTube ja validado
    # pode iniciar sob perfil vertical de memoria reduzida.
    import sys, json
    from pathlib import Path
    from nucleo.util import ROBO
    minimo = 2.5
    if '--nome' in sys.argv:
        pos = sys.argv.index('--nome')
        if pos + 1 < len(sys.argv):
            job_name = sys.argv[pos + 1]
            folder = Path(ROBO) / 'jobs' / job_name / 'youtube' / 'broll'
            qa_path = folder / 'qa.json'
            marker_path = folder / (job_name + '_YOUTUBE_BROLL_16x9.resgate.json')
            video_path = folder / (job_name + '_YOUTUBE_BROLL_16x9.mp4')
            if qa_path.is_file() and marker_path.is_file() and video_path.is_file():
                qa = json.loads(qa_path.read_text(encoding='utf-8'))
                marker = json.loads(marker_path.read_text(encoding='utf-8'))
                if qa.get('ok_tecnico') is True and marker.get('formato') == '16x9' and marker.get('frames', 0) > 0:
                    minimo = 1.85
    renderer.exigir_recursos(minimo)
    broll.configurar(biblioteca)
    biblioteca._avaliar=broll._avaliar
    biblioteca.obter=broll.obter
    render.renderizar=renderer.renderizar
    antigo.planejar=apoios.planejar
    montar.normalizar=montagem.normalizar
    montar.montar=montagem.montar

