"""Uma configuração e um rasterizador ASS para legendas de ambos os motores."""
from pathlib import Path
import json

STYLE_PATH=Path(__file__).resolve().parent/'src/robo/estilo.json'

def stamp(t):
    n=max(0,round(t*100))
    return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'

def bgr(hexcolor):
    h=hexcolor.lstrip('#')
    return h[4:6]+h[2:4]+h[:2]

def escape(s):
    return s.replace('\\','').replace('{','(').replace('}',')').replace('\n',' ')

def exportar(path,plan,start=0,end=None,style=None):
    style=style or json.loads(STYLE_PATH.read_text())
    end=plan['frames']/plan['fps'] if end is None else end
    c=style['caption'];g=style['geometry'][plan['formato']];colors=style['colors']
    vertical=plan['formato']=='9x16';size=c['size'] if vertical else g['leg']['tam']
    # libass mede altura ascent-descent; CSS usa em. Poppins hhea=1400/em=1000.
    # Compensação tipográfica medida: mantém a altura visual de CSS 62px.
    size=round(size*c.get('assFontScale',1),2)
    top=c['top'] if vertical else g['leg']['max'];x=c['centerX'] if vertical else g['leg']['xc']
    lines=['[Script Info]','ScriptType: v4.00+','WrapStyle: 2',f"PlayResX: {g['W']}",f"PlayResY: {g['H']}",'ScaledBorderAndShadow: yes','',
      '[V4+ Styles]',
      'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
      f"Style: Natinha,{c['font']},{size},&H00{bgr(colors['white'])},&H00{bgr(colors['amber'])},&H330A0B0C,&H800A0B0C,-1,0,0,0,100,100,0,0,1,{c['outline']},1,8,68,68,0,1",'',
      '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    blocks=sorted(plan.get('legendas',[]),key=lambda x:x['ini']) if vertical or plan.get('legendaHorizontal',True) else []
    for k,block in enumerate(blocks):
        next_start=blocks[k+1]['ini'] if k+1<len(blocks) else end
        a=max(start,block['ini']);b=min(end,block['fim'],next_start)
        if b<=a:continue
        parts=[]
        for w in block['palavras']:
            color=colors['amber'] if w.get('destaque') else colors['white']
            parts.append(r'{\c&H'+bgr(color)+'&}'+escape(w['w'])+(r'\N' if w.get('quebraDepois') else ' '))
        # Não reinicia fade se a legenda atravessar uma divisão de motor.
        fade=round(c['entrySeconds']*1000) if a==block['ini'] else 0
        pos=rf'{{\an8\pos({x},{top})\fad({fade},0)}}'
        lines.append(f'Dialogue: 0,{stamp(a-start)},{stamp(b-start)},Natinha,,0,0,0,,{pos}'+''.join(parts).rstrip())
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return sum(x.startswith('Dialogue:') for x in lines)

if __name__=='__main__':
    root=Path(__file__).resolve().parent
    print('Legendas:',exportar(root/'legendas.ass',json.loads((root/'plano_previa.json').read_text())))
