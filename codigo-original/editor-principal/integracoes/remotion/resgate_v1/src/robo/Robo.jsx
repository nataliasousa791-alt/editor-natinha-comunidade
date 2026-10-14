// Composição genérica v2 do robô — 9:16 e 16:9, parametrizada só por plano.json. Escala ÚNICA x/y em todo vídeo.
import React, {useMemo} from 'react';
import ESTILO from './estilo.json';
import {MotionCaption} from './MotionCaption';
import {Video} from '@remotion/media';
import {AbsoluteFill, Audio, Sequence, Loop, Easing, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';

const fh = delayRender('fontes');
Promise.all([
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Bold.ttf')})`, {weight: '700'}).load(),
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Medium.ttf')})`, {weight: '500'}).load(),
  new FontFace('Lora', `url(${staticFile('fonts/Lora-Variable.ttf')})`, {weight: '400 700'}).load(),
]).then((fs) => { fs.forEach((f) => document.fonts.add(f)); continueRender(fh); });

const {amber: AMBAR, white: BRANCO, gray: CINZA, graphite: GRAFITE} = ESTILO.colors;
const cl = (x) => Math.min(1, Math.max(0, x));
const OUT = Easing.bezier(0.16, 1, 0.3, 1), IO = Easing.bezier(0.65, 0, 0.35, 1);
const p = (t, s, d, e = OUT) => e(cl((t - s) / d));
const lerp = (a, b, k) => a + (b - a) * k;

// ---------- geometria por formato ----------
const GEO_ORIGINAL = {
  '9x16': {W: 1080, H: 1920, RA: {x: 0, y: 380, w: 1080, h: 1100, r: 0}, RB: {x: 36, y: 930, w: 1008, h: 720, r: 44},
    PB: {x: 36, y: 150, w: 1008, h: 730, r: 44}, PC: {x: 0, y: 0, w: 1080, h: 1920, r: 0}, alvoRosto: [0.34, 0.40],
    titulo: {top: 160, left: 50, right: 50, align: 'center'}, enfase: {top: 190, left: 60, right: 60, align: 'center'},
    leg: {tam: 62, max: 1640, xc: 540, larg: 1000}, kicker: {left: 64, top: 290}, u: 1},
  '16x9': {W: 1920, H: 1080, RA: {x: 0, y: 0, w: 1920, h: 1080, r: 0}, RB: {x: 1010, y: 90, w: 850, h: 900, r: 40},
    PB: {x: 60, y: 90, w: 910, h: 900, r: 40}, PC: {x: 0, y: 0, w: 1920, h: 1080, r: 0}, alvoRosto: [0.30, 0.40],
    titulo: {top: 300, left: 110, right: 860, align: 'left'}, enfase: {top: 380, left: 110, right: 980, align: 'left'},
    leg: {tam: 50, max: 975, xc: 960, larg: 1500}, kicker: {left: 110, top: 80}, u: 1},
};
const GEO = ESTILO.geometry;

const envelope = (t, blocos, d = 0.55) => (blocos || []).reduce((m, [a, b]) => Math.max(m, p(t, a - 0.05, d, IO) * (1 - p(t, b - 0.1, d, IO))), 0);
const planosCamera = (cortes, total) => {                  // troca de zoom só em cortes espaçados (>= 4 s): esconde o jump cut
  const pl = [0]; for (const c of cortes) if (c - pl[pl.length - 1] >= 4 && total - c >= 2) pl.push(c);
  return pl;
};
const zoomDe = (t, planos, total) => {
  if (!ESTILO.motion.dynamicZoom) return 1;
  let k = 0; while (k + 1 < planos.length && t >= planos[k + 1]) k++;
  const a = planos[k], b = planos[k + 1] ?? total;
  return (k % 2 ? 1.08 : 1.0) + 0.025 * IO(cl((t - a) / Math.max(0.5, b - a)));
};
const enquadrar = (R, f, alvo, zoom, cap = Infinity) => {   // escala única; limite explícito no experimento
  const fcx = f.rosto.cx * f.w, fcy = f.rosto.cy * f.h, fhp = Math.max(40, f.rosto.h * f.h);
  const sCover = Math.max(R.w / f.w, R.h / f.h);
  const s = Math.min(cap, Math.max(sCover, Math.min(alvo * R.h / fhp, sCover * 2.4)) * zoom);
  const vw = f.w * s, vh = f.h * s;
  const left = vw < R.w ? (R.w - vw) / 2 : Math.min(0, Math.max(R.w - vw, R.w / 2 - fcx * s));
  const top = vh < R.h ? (R.h - vh) / 2 : Math.min(0, Math.max(R.h - vh, R.h * 0.42 - fcy * s));
  return {s, vw, vh, left, top, queixo: R.y + top + (fcy + 0.62 * fhp) * s};
};
const mistura = (A, B, k) => Object.fromEntries(Object.keys(A).map((x) => [x, lerp(A[x], B[x], k)]));

const NatinhaFrame = ({fonte, R, e, m, vertical}) => {
  const fe = vertical ? 9 * (1 - m) : 0;
  return (
    <div style={{position: 'absolute', left: R.x, top: R.y, width: R.w, height: R.h, borderRadius: R.r, overflow: 'hidden',
      WebkitMaskImage: fe > 0.2 ? `linear-gradient(to bottom, transparent 0%, #000 ${fe}%, #000 ${100 - fe}%, transparent 100%)` : undefined,
      boxShadow: `0 40px 90px rgba(0,0,0,${0.6 * m})`, outline: `1.5px solid rgba(255,255,255,${0.12 * m})`, outlineOffset: -1.5}}>
      <Video src={staticFile(fonte.arquivo)} muted objectFit="fill" style={{position: 'absolute', left: e.left, top: e.top, width: e.vw, height: e.vh}} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,0) 60%, rgba(8,7,6,0.45) 100%)'}} />
    </div>
  );
};
const FundoDesfocado = ({fonte, G, fundo}) => {
  const bw = G.W / 4, bh = G.H / 4, s = Math.max(bw / fonte.w, bh / fonte.h);
  if (fundo) return (<div style={{position: 'absolute', left: 0, top: 0, width: bw, height: bh, overflow: 'hidden', transform: 'scale(4)', transformOrigin: '0 0'}}>
    <Video src={staticFile(fundo)} muted objectFit="fill" style={{width: bw, height: bh}} /></div>);
  return (
    <div style={{position: 'absolute', left: 0, top: 0, width: bw, height: bh, overflow: 'hidden', transform: 'scale(4)',
      transformOrigin: '0 0', filter: 'blur(7px) brightness(0.30) saturate(0.75)'}}>
      <Video src={staticFile(fonte.arquivo)} muted objectFit="fill" style={{position: 'absolute', width: fonte.w * s, height: fonte.h * s,
        left: Math.min(0, Math.max(bw - fonte.w * s, bw / 2 - fonte.rosto.cx * fonte.w * s)), top: Math.min(0, Math.max(bh - fonte.h * s, 0))}} />
    </div>
  );
};
const Grao = ({f, W, H}) => (                                // grão de filme sutil, deslocado a cada quadro
  <AbsoluteFill style={{backgroundImage: `url(${staticFile('grao.png')})`, backgroundSize: '256px 256px',
    backgroundPosition: `${(f * 73) % 256}px ${(f * 151) % 256}px`, opacity: ESTILO.motion.grainOpacity, mixBlendMode: 'overlay', pointerEvents: 'none'}} />
);

// ---------- tipografia ----------
const Revela = ({t, s, d = 0.5, children, style}) => {
  const k = p(t, s, d);
  return <span style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'top', paddingBottom: '0.12em'}}>
    <span style={{display: 'inline-block', transform: `translateY(${(1 - k) * 105}%)`, filter: `blur(${(1 - k) * 6}px)`, opacity: cl(k * 1.5), ...style}}>{children}</span></span>;
};
const Kicker = ({t, s, children, op = 1, style}) => {
  const k = p(t, s, 0.5);
  return <div style={{display: 'flex', alignItems: 'center', gap: 14, opacity: k * op, transform: `translateX(${(1 - k) * -18}px)`, ...style}}>
    <div style={{width: 10, height: 10, borderRadius: 5, background: AMBAR, boxShadow: `0 0 14px ${AMBAR}`}} />
    <div style={{font: '500 25px Poppins', letterSpacing: 5, color: CINZA, textTransform: 'uppercase'}}>{children}</div></div>;
};
const FUNCAO = new Set(['a', 'o', 'as', 'os', 'de', 'da', 'do', 'das', 'dos', 'e', 'que', 'pra', 'para', 'na', 'no', 'nas', 'nos',
  'um', 'uma', 'com', 'em', 'por', 'se', 'ao', 'à', 'mais', 'muito', 'seu', 'sua', 'meu', 'minha', 'nosso', 'nossa', 'esse', 'essa']);
const quebra = (ws, minimo = 1) => {            // índice da quebra: linhas equilibradas, nunca terminando em palavra funcional
  const n = ws.length; if (n <= 3) return 0;
  let melhor = Math.ceil(n / 2), nota = 1e9;
  for (let k = minimo; k < n; k++) {
    const a = ws.slice(0, k).join(' ').length, b = ws.slice(k).join(' ').length;
    const fim = String(ws[k - 1]).toLowerCase().replace(/[^a-zà-ú]/g, '');
    const v = Math.abs(a - b) + (FUNCAO.has(fim) ? 100 : 0);
    if (v < nota) { nota = v; melhor = k; }
  }
  return melhor;
};
const tam = (txt, max, largura, fator = 0.52) => Math.min(max, Math.floor(largura / Math.max(1, txt.length * fator)));
const Fio = ({t, s, w = 300, align}) => (
  <div style={{margin: align === 'center' ? '16px auto 0' : '16px 0 0', height: 3, width: w, background: AMBAR,
    transform: `scaleX(${p(t, s, 0.8)})`, transformOrigin: align === 'center' ? 'center' : 'left'}} />
);
const Sombra = ({G, lado}) => G.W > G.H ? (     // horizontal: degradê lateral para o texto sobre a imagem
  <AbsoluteFill style={{background: `linear-gradient(${lado === 'esq' ? 'to right' : 'to left'}, rgba(8,7,6,0.82) 0%, rgba(8,7,6,0.45) 38%, rgba(8,7,6,0) 62%)`}} />
) : null;

const Abertura = ({t, c, G, kickerAte}) => {
  const corte = quebra(c.texto);
  const l1 = c.texto.slice(0, corte).join(' '), l2 = c.texto.slice(corte).join(' ');
  const sai = p(t, c.fim - 0.35, 0.4, IO), T = G.titulo, larg = G.W - T.left - T.right;
  return (<>
    {sai < 1 && <><div style={{position: 'absolute', inset: 0, opacity: 1 - sai}}><Sombra G={G} lado="esq" /></div>
      <div style={{position: 'absolute', top: T.top, left: T.left, right: T.right, textAlign: T.align, opacity: 1 - sai, transform: `translateY(${-40 * sai}px)`}}>
        {l1 && <div><Revela t={t} s={0.12} style={{font: `700 ${tam(l1, 50, larg, 0.85)}px Poppins`, letterSpacing: 8, color: BRANCO, textTransform: 'uppercase'}}>{l1}</Revela></div>}
        <div><Revela t={t} s={0.3} d={0.7} style={{font: `700 ${tam(l2, 116, larg)}px Lora`, color: AMBAR, lineHeight: 1.05}}>{l2}</Revela></div>
        <Fio t={t} s={0.7} align={T.align} />
      </div></>}
    {t > c.fim - 0.1 && t < kickerAte + 0.4 && <Kicker t={t} s={c.fim} op={1 - p(t, kickerAte - 0.3, 0.3, IO)}
      style={{position: 'absolute', left: G.kicker.left, top: G.kicker.top}}>{c.texto.join(' ')}</Kicker>}
  </>);
};
const Fechamento = ({t, c, G}) => {
  if (t < c.ini) return null;
  const n = c.palavras.length, corte = n <= 4 ? 0 : Math.max(quebra(c.palavras.map((w) => w.w), 1), n - 5);
  const L1 = c.palavras.slice(0, corte), L2 = c.palavras.slice(corte), T = G.titulo, larg = G.W - T.left - T.right;
  const s1 = tam(L1.map((w) => w.w).join(' '), 76, larg), s2 = tam(L2.map((w) => w.w).join(' '), 108, larg, 0.6);
  return (<>
    <div style={{position: 'absolute', inset: 0, opacity: p(t, c.ini, 0.6)}}><Sombra G={G} lado="esq" /></div>
    <div style={{position: 'absolute', top: T.top, left: T.left, right: T.right, textAlign: T.align}}>
      {L1.length > 0 && <div>{L1.map((w, i) => <Revela key={i} t={t} s={w.s} d={0.45} style={{font: `400 ${s1}px Lora`, color: BRANCO}}>{w.w}&nbsp;</Revela>)}</div>}
      <div>{L2.map((w, i) => <Revela key={i} t={t} s={w.s} d={0.45} style={{font: `700 ${s2}px Poppins`, color: AMBAR}}>{w.w}&nbsp;</Revela>)}</div>
      <Fio t={t} s={c.palavras[n - 1].s + 0.1} w={340} align={T.align} />
    </div></>);
};
const Enfase = ({t, c, G}) => {                              // ênfase literal sem painel: rosto continua em cena
  if (t < c.ini - 0.1 || t > c.fim + 0.5) return null;
  const E = G.enfase, larg = G.W - E.left - E.right, txt = c.palavras.map((w) => w.w).join(' ');
  const sai = p(t, c.fim - 0.1, 0.45, IO), sz = tam(txt, G.W > G.H ? 130 : 120, larg, 0.55);
  return (<>
    <div style={{position: 'absolute', inset: 0, opacity: (1 - sai) * p(t, c.ini, 0.4)}}><Sombra G={G} lado="esq" /></div>
    <div style={{position: 'absolute', top: E.top, left: E.left, right: E.right, textAlign: E.align, opacity: 1 - sai, transform: `translateY(${-24 * sai}px)`}}>
      {c.palavras.map((w, i) => {
        const ult = i === c.palavras.length - 1;
        return <Revela key={i} t={t} s={w.s - 0.05} d={0.5} style={{font: `${ult ? 'italic 700' : '400'} ${sz}px Lora`, color: ult ? AMBAR : BRANCO,
          textShadow: '0 8px 30px rgba(0,0,0,0.6)'}}>{w.w}&nbsp;</Revela>;
      })}
      <Fio t={t} s={c.palavras[c.palavras.length - 1].s + 0.05} w={200} align={E.align} />
    </div></>);
};

// ---------- cenas de painel ----------
const VideoBroll = ({c, fps}) => {
  const v = <Video src={staticFile(c.asset.arquivo)} muted trimBefore={Math.round(c.asset.inicio * fps)} objectFit="cover"
    style={{position: 'absolute', width: '100%', height: '100%', filter: 'contrast(1.08) saturate(0.82) sepia(0.14) brightness(0.88)'}} />;
  if (!c.asset.laco) return v;
  const dur = Math.max(1, Math.floor((c.asset.duracao - c.asset.inicio - 0.05) * fps));
  return <Loop durationInFrames={dur} layout="none">{v}</Loop>;
};
const TimedBroll = ({t, c, fps, P, motionMode=false}) => {
  // No novo modo a mídia permanece, mas a etiqueta e o texto do B-roll
  // saem para evitar uma segunda legenda competindo com MotionCaption.
  if(motionMode) return <>
    <Sequence from={Math.round((c.ini - 0.3) * fps)} durationInFrames={Math.round((c.fim-c.ini + 0.9) * fps)} layout="none">
      <div style={{position:'absolute',inset:0}}><VideoBroll c={c} fps={fps}/></div>
    </Sequence>
    <div style={{position:'absolute',inset:0,background:'linear-gradient(to bottom,rgba(10,9,8,.20),rgba(10,9,8,.40) 60%,rgba(10,9,8,.62))'}}/>
  </>;
  const fr = c.frase.map((w) => w.w).join(' '), cheio = P.w > 1500;
  return (<>
    <Sequence from={Math.round((c.ini - 0.3) * fps)} durationInFrames={Math.round((c.fim - c.ini + 0.9) * fps)} layout="none">
      <div style={{position: 'absolute', inset: 0}}><VideoBroll c={c} fps={fps} /></div>
    </Sequence>
    <div style={{position: 'absolute', inset: 0, background: cheio
      ? 'linear-gradient(to right, rgba(10,9,8,0.75) 0%, rgba(10,9,8,0.25) 45%, rgba(10,9,8,0) 70%), linear-gradient(to bottom, rgba(10,9,8,0.5) 0%, rgba(10,9,8,0) 25%, rgba(10,9,8,0) 60%, rgba(10,9,8,0.75) 100%)'
      : 'radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.5) 100%), linear-gradient(to bottom, rgba(10,9,8,0.55) 0%, rgba(10,9,8,0) 22%, rgba(10,9,8,0) 48%, rgba(10,9,8,0.9) 100%)'}} />
    <Kicker t={t} s={c.ini + 0.3} style={{position: 'absolute', left: cheio ? 110 : 44, top: cheio ? 80 : 40}}>{c.rotulo}</Kicker>
    <div style={{position: 'absolute', left: cheio ? 110 : 44, right: cheio ? 760 : 44, bottom: cheio ? 150 : 60}}>
      {c.frase.map((w, i) => <Revela key={i} t={t} s={w.s - 0.05} style={{font: `${i === c.frase.length - 1 ? 'italic 700' : '400'} ${tam(fr, cheio ? 130 : 112, cheio ? 1050 : P.w - 88)}px Lora`,
        color: i === c.frase.length - 1 ? AMBAR : BRANCO, textShadow: '0 6px 26px rgba(0,0,0,0.5)'}}>{w.w}&nbsp;</Revela>)}
    </div>
  </>);
};
const Cartao = ({t, c, P}) => {
  const txt = c.palavras.map((w) => w.w).join(' ');
  // tamanho pela área útil do painel: o texto ocupa ~45% da área, entre 64 e 120 px
  const sz = Math.round(Math.max(64, Math.min(120, Math.sqrt(((P.w - 120) * (P.h - 160) * 0.45) / Math.max(8, txt.length * 0.62)))));
  return (<>
    <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at ${30 + 20 * p(t, c.ini, c.fim - c.ini, IO)}% 30%, #25262C 0%, ${GRAFITE} 65%)`}} />
    <div style={{position: 'absolute', left: 60, top: 70, height: 3, width: 120, background: AMBAR, transform: `scaleX(${p(t, c.ini, 0.6)})`, transformOrigin: 'left'}} />
    <div style={{position: 'absolute', left: 60, right: 60, top: 0, bottom: 0, display: 'flex', alignItems: 'center'}}>
      <div style={{lineHeight: 1.12}}>{c.palavras.map((w, i) => {
        const ult = i === c.palavras.length - 1;
        return <Revela key={i} t={t} s={w.s - 0.05} style={{font: `${ult ? 'italic 700' : '400'} ${sz}px Lora`, color: ult ? AMBAR : BRANCO}}>{w.w}&nbsp;</Revela>;
      })}</div>
    </div>
  </>);
};
const Numero = ({t, c}) => {
  const vals = c.valores && c.valores.length ? c.valores : [{valor: c.valor, prefixo: c.prefixo, sufixo: c.sufixo, unidade: c.unidade, t: c.gatilho.t, contexto: c.contexto}];
  const sz = vals.length === 1 ? 200 : vals.length === 2 ? 150 : 110;
  return (<>
    <div style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at 50% 45%, #25262C 0%, ${GRAFITE} 70%)`}} />
    <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: vals.length > 1 ? 50 : 0}}>
      {vals.map((v, i) => {
        const k = p(t, v.t - 0.1, 0.9, OUT), dec = v.valor % 1 ? 1 : 0, vis = p(t, v.t - 0.25, 0.35);
        const num = (v.valor * k).toLocaleString('pt-BR', {minimumFractionDigits: dec, maximumFractionDigits: dec});
        return <React.Fragment key={i}>
          {i > 0 && <div style={{width: 2, height: sz * 1.2, background: 'rgba(255,255,255,0.14)', transform: `scaleY(${vis})`}} />}
          <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: vis, transform: `translateY(${(1 - vis) * 16}px)`}}>
            {v.contexto && <div style={{font: '500 28px Poppins', letterSpacing: 5, color: CINZA, textTransform: 'uppercase', marginBottom: 6}}>{v.contexto}</div>}
            <div style={{width: 70, height: 3, background: AMBAR, marginBottom: 14, transform: `scaleX(${vis})`}} />
            <div style={{font: `700 ${sz}px Poppins`, color: AMBAR, letterSpacing: -4, lineHeight: 1}}>{v.prefixo && <span style={{fontSize: sz * 0.43}}>{v.prefixo} </span>}{num}{v.sufixo}</div>
            {v.unidade && <Revela t={t} s={v.t + 0.2} style={{font: `italic 400 ${Math.round(sz * 0.32)}px Lora`, color: BRANCO}}>{v.unidade}</Revela>}
          </div>
        </React.Fragment>;
      })}
    </div>
  </>);
};
const Painel = ({t, cenas, blocos, fps, P, lay, motionMode = false}) => {
  const bl = blocos.find(([a, b]) => t >= a - 0.1 && t <= b + 0.7);
  if (!bl) return null;
  const abre = p(t, bl[0], lay === 'C' ? 0.6 : 0.75, IO), fecha = p(t, bl[1] - 0.1, 0.55, IO);
  const ativas = cenas.filter((c) => c.layout === lay && t >= c.ini - 0.4 && t <= c.fim + 0.6);
  if (motionMode && !ativas.length) return null;
  const est = lay === 'C'
    ? {opacity: abre * (1 - fecha), transform: `scale(${1.04 - 0.04 * abre})`, filter: `blur(${(1 - abre) * 10 + fecha * 8}px)`}
    : {clipPath: `inset(0 0 ${(1 - abre) * 100 + fecha * 100}% 0 round ${P.r}px)`, transform: `translateY(${(1 - abre) * -30 + fecha * -20}px)`};
  return (
    <div style={{position: 'absolute', left: P.x, top: P.y, width: P.w, height: P.h, borderRadius: P.r, overflow: 'hidden', background: GRAFITE, ...est}}>
      {ativas.map((c) => {
        const op = p(t, c.ini - 0.15, 0.35, IO) * (1 - p(t, c.fim - 0.05, 0.35, IO));
        return <div key={c.id} style={{position: 'absolute', inset: 0, opacity: op}}>
          {c.tipo === 'broll' && <TimedBroll t={t} c={c} fps={fps} P={P} motionMode={motionMode} />}
          {c.tipo === 'cartao' && <Cartao t={t} c={c} P={P} />}
          {c.tipo === 'numero' && <Numero t={t} c={c} />}
        </div>;
      })}
      {P.r > 0 && <div style={{position: 'absolute', inset: 0, borderRadius: P.r, boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,0.10)'}} />}
    </div>
  );
};

// ---------- legendas ----------
const Legendas = ({t, legendas, y, G, xc, larg}) => {
  const l = legendas.find((x) => t >= x.ini && t < x.fim);
  if (!l) return null;
  const k = p(t, l.ini, ESTILO.caption.entrySeconds);
  return (
    <div style={{position: 'absolute', top: y, left: xc - larg / 2, width: larg, textAlign: 'center', opacity: k, lineHeight: ESTILO.caption.lineHeight}}>
      {l.palavras.map((w, i) => <span key={i} style={{font: `700 ${G.leg.tam}px Poppins`, color: w.destaque ? AMBAR : BRANCO,
        WebkitTextStroke: `${ESTILO.caption.outline}px rgba(12,11,10,0.8)`, paintOrder: 'stroke fill', textShadow: ESTILO.caption.shadow}}>{w.w}{i < l.palavras.length - 1 ? (w.quebraDepois ? <br/> : ' ') : ''}</span>)}
    </div>
  );
};

export const Robo = (P) => {
  const f = useCurrentFrame(), t = f / P.fps, total = P.frames / P.fps;
  const G = GEO[P.formato || '9x16'], vertical = G.H > G.W;
  const planos = useMemo(() => planosCamera(P.cortesInternos, total), [P.cortesInternos, total]);
  const mB = P.layoutFixo === 'B' ? 1 : envelope(t, P.blocosB), mC = envelope(t, P.blocosC, 0.6);
  const R = mistura(G.RA, G.RB, mB);
  const e = enquadrar(R, P.fonte, lerp(G.alvoRosto[0], G.alvoRosto[1], mB), zoomDe(t, planos, total),
    P.layoutFixo === 'B' ? (ESTILO.presenter.scaleCaps[P.formato] || ESTILO.presenter.scaleCap) : Infinity);
  const ab = P.cenas.find((c) => c.tipo === 'abertura'), fe = P.cenas.find((c) => c.tipo === 'fechamento');
  const yLeg = vertical ? ESTILO.caption.top
    : (mB > 0.5 ? Math.min(G.leg.max, R.y + R.h - 140) : G.leg.max - 20);
  const xLeg = !vertical && mB > 0.5 ? R.x + R.w / 2 : G.leg.xc, lLeg = !vertical && mB > 0.5 ? R.w - 40 : G.leg.larg;
  const primeiroPainel = Math.min(...[...(P.blocosB || []), ...(P.blocosC || [])].map((b) => b[0]), total);
  const mostrarLeg = !P.semLegendas && P.legendas && P.legendas.length && (vertical || P.legendaHorizontal !== false);
  const mostrarMotion = P.captionMode === 'motion_orange_v1' && P.captionCues && P.captionCues.length;
  return (
    <AbsoluteFill style={{background: '#0B0B0D'}}>
      <FundoDesfocado fonte={P.fonte} G={G} fundo={P.fundo} />
      {vertical && <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 20%, rgba(0,0,0,0) 70%, rgba(0,0,0,0.6) 100%)'}} />}
      <NatinhaFrame fonte={P.fonte} R={R} e={e} m={mB} vertical={vertical} />
      {P.cenas.filter((c) => c.tipo === 'enfase').map((c) => <Enfase key={c.id} t={t} c={c} G={G} />)}
      {ab && <Abertura t={t} c={ab} G={G} kickerAte={Math.min(primeiroPainel, ab.fim + 8)} />}
      <Painel t={t} cenas={mostrarMotion ? P.cenas.filter(c => c.tipo !== "cartao") : P.cenas} blocos={P.blocosB || []} fps={P.fps} P={G.PB} lay="B" motionMode={mostrarMotion} />
      <Painel t={t} cenas={mostrarMotion ? P.cenas.filter(c => c.tipo !== "cartao") : P.cenas} blocos={P.blocosC || []} fps={P.fps} P={G.PC} lay="C" motionMode={mostrarMotion} />
      {fe && <Fechamento t={t} c={fe} G={G} />}
      {mostrarLeg && <Legendas t={t} legendas={P.legendas} y={yLeg} G={G} xc={xLeg} larg={lLeg} />}
      {mostrarMotion && <MotionCaption t={t} cues={P.captionCues} formato={P.formato} />}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.35) 100%)'}} />
      <Grao f={f} W={G.W} H={G.H} />
      <AbsoluteFill style={{background: '#000', opacity: p(t, total - 0.45, 0.45, IO)}} />
      {!P.semAudio && <Audio src={staticFile(P.audio)} />}
    </AbsoluteFill>
  );
};
