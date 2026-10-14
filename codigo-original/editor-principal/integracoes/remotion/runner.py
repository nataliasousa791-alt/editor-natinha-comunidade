"""Inicializador reversível: perfil aprovado isolado; motor anterior preservado."""
import json, os, runpy, sys
from pathlib import Path
from types import ModuleType
HERE=Path(__file__).resolve().parent
ROBO=HERE.parents[2]/'NATINHA_CINEMATIC_EDITOR_V1'/'robo'
sys.path.insert(0,str(ROBO))
sys.path.insert(1,str(HERE.parent.parent))
# O robô e o editor tradicional possuem namespaces nucleo diferentes.
pacote_motor=ModuleType('nucleo');pacote_motor.__path__=[str(ROBO/'nucleo')];pacote_motor.__package__='nucleo'
sys.modules['nucleo']=pacote_motor
flag=HERE/'resgate_ativo.json'
resgate=flag.exists() and json.loads(flag.read_text(encoding='utf-8')).get('ativo',False)
modo_hibrido='--hibrido' in sys.argv
if modo_hibrido:sys.argv.remove('--hibrido')
if resgate:
    from integracoes.remotion.resgate_v1 import ativar
    ativar()
    print('NATINHA_RESGATE_APROVADO=ativo',flush=True)
elif modo_hibrido:
    from nucleo import render,cortes
    from integracoes.remotion import hibrido
    render.renderizar=hibrido.renderizar
    _escolher_anterior=cortes.escolher
    cortes.escolher=lambda words,c,n,log:hibrido.escolher_cortes_adaptativos(_escolher_anterior,words,c,n,log)
    print('NATINHA_HIBRIDO_BETA=ativo',flush=True)
if os.environ.get('NATINHA_REMOTION_OFFLINE','1')!='0':
    from nucleo import biblioteca
    biblioteca._buscar=lambda *args,**kwargs:[]
sys.argv=[str(ROBO/'robo.py'),*sys.argv[1:]]
runpy.run_path(str(ROBO/'robo.py'),run_name='__main__')
