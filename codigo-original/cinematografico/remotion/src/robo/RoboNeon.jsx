// Camada visual "NEON MATRIX" do canal Natinha — 9:16 e 16:9. Mesmo contrato de props do Robo.jsx (plano.json) + P.segs.
// segs: [{s, e, m: 'full'|'take'|'split'|'over', cena: nome da cena | 'broll' | undefined}]
import React, {useMemo} from 'react';
import {Video} from '@remotion/media';
import {AbsoluteFill, Audio, Easing, Loop, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {Rain} from './neon/Opcoes';
import {CENAS_TODAS as CENAS} from './neon/CenasMais';
import {CenaGen} from './neon/CenaGen';

const fh = delayRender('fontes-neon');
Promise.all([
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-ExtraBold.ttf')})`, {weight: '800'}).load(),
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Bold.ttf')})`, {weight: '700'}).load(),
  new FontFace('Lora', `url(${staticFile('fonts/Lora-Italic-Variable.ttf')})`, {weight: '400 700', style: 'italic'}).load(),
]).then((fs) => { fs.forEach((f) => document.fonts.add(f)); continueRender(fh); });

const LIME = '#E8FC3B', BG = '#05080A';
const PF = '"Poppins", sans-serif';
const cl = (x) => Math.min(1, Math.max(0, x));
const IO = Easing.bezier(0.65, 0, 0.35, 1), OUT = Easing.bezier(0.16, 1, 0.3, 1);
const FADE = 6;

// geometria por formato. cena: transformação do SVG das cenas (viewBox nativo 1080x~800, chão em y=790)
const GEO = {
  '9x16': {W: 1080, H: 1920,
    full: {x: 0, y: 200, w: 1080, h: 1500, r: 0}, over: {x: 0, y: 0, w: 1080, h: 1500, r: 0}, alvoFull: 0.30,
    card: {x: 40, y: 185, w: 1000, h: 740, r: 36}, alvoCard: 0.42,
    circ: {x: 784, y: 64, d: 220}, takeT: 'translate(540,1010) scale(1.32) translate(-540,-500)',
    splitBox: {x: 0, y: 950, w: 1080, h: 800}, splitView: '0 100 1080 800', brollBox: {x: 36, y: 0, w: 1008, h: 760, r: 36},
    overT: 'translate(540,1810) scale(0.8) translate(-540,-790)',
    head: {left: 60, top: 52, w: 960, tk: 24, tt: 52, topTake: 80}, capY: {full: 1400, take: 1560, split: 185 + 740 - 150}, capX: 60, capW: 960, capMax: 70, capK: 900,
    cta: {top: 1440, k1: 26, k2: 80, pad: 100}, rain: [[0, 0], [0, 900]]},
  '16x9': {W: 1920, H: 1080,
    full: {x: 0, y: 0, w: 1920, h: 1080, r: 0}, over: {x: 0, y: 0, w: 1920, h: 1080, r: 0}, alvoFull: 0.40,
    card: {x: 60, y: 115, w: 940, h: 880, r: 40}, alvoCard: 0.46,
    circ: {x: 1580, y: 56, d: 260}, takeT: 'translate(960,900) scale(1.15) translate(-540,-790)',
    splitBox: {x: 1030, y: 115, w: 830, h: 880}, splitView: '120 80 840 880', brollBox: {x: 0, y: 0, w: 830, h: 880, r: 40},
    overT: 'translate(1480,1040) scale(0.62) translate(-540,-790)',
    head: {left: 90, top: 46, w: 1300, tk: 22, tt: 46, topTake: 56}, capY: {full: 905, take: 960, split: 115 + 880 - 120}, capX: 0, capW: 1920, capMax: 66, capK: 1300,
    cta: {top: 760, k1: 28, k2: 72, pad: 70}, rain: [[0, 0], [1080, 0], [0, 600], [1080, 600]]},
};

const enquadrar = (R, f, alvo) => {
  const fcx = f.rosto.cx * f.w, fcy = f.rosto.cy * f.h, fhp = Math.max(40, f.rosto.h * f.h);
  const sCover = Math.max(R.w / f.w, R.h / f.h);
  const s = Math.max(sCover, Math.min((alvo * R.h) / fhp, sCover * 2.4));
  const vw = f.w * s, vh = f.h * s;
  return {vw, vh, left: Math.min(0, Math.max(R.w - vw, R.w / 2 - fcx * s)), top: Math.min(0, Math.max(R.h - vh, R.h * 0.42 - fcy * s))};
};
const queixoY = (R, f, alvo) => { const e = enquadrar(R, f, alvo), s = e.vw / f.w; return Math.round(R.y + e.top + (f.rosto.cy * f.h + 0.62 * f.rosto.h * f.h) * s); };
const Cam = ({fonte, R, alvo, style, fade}) => {
  const e = enquadrar(R, fonte, alvo);
  return (
    <div style={{position: 'absolute', left: R.x, top: R.y, width: R.w, height: R.h, borderRadius: R.r || 0, overflow: 'hidden',
      WebkitMaskImage: fade ? `linear-gradient(to bottom, transparent 0%, #000 ${fade}%, #000 ${100 - fade}%, transparent 100%)` : undefined, ...style}}>
      <Video src={staticFile(fonte.arquivo)} muted objectFit="fill" style={{position: 'absolute', left: e.left, top: e.top, width: e.vw, height: e.vh}} />
    </div>
  );
};

const Glow = ({id, sd}) => (
  <defs><filter id={id} x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation={sd} result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
);
const Cena = ({seg, t}) => {
  const C = seg.cena === 'gen' ? (({f, dur}) => <CenaGen spec={seg.spec} f={f} dur={dur} />) : CENAS[seg.cena]; if (!C) return null;
  const sf = Math.max(0, Math.round((t - seg.s) * 30)), sd = Math.round((seg.e - seg.s) * 30);
  const o = Math.min(cl(sf / 8), cl((sd - sf) / 8));
  return <g opacity={o}><C f={sf} dur={sd} /></g>;
};
const Broll = ({P, t}) => {
  const c = (P.cenas || []).find((x) => x.tipo === 'broll' && t >= x.ini - 0.3 && t <= x.fim + 0.6);
  if (!c) return null;
  const v = <Video src={staticFile(c.asset.arquivo)} muted trimBefore={Math.round(c.asset.inicio * P.fps)} objectFit="cover" style={{position: 'absolute', width: '100%', height: '100%'}} />;
  if (!c.asset.laco) return v;
  return <Loop durationInFrames={Math.max(1, Math.floor((c.asset.duracao - c.asset.inicio - 0.05) * P.fps))} layout="none">{v}</Loop>;
};
const ChuvaMatrix = ({G, f, op = 0.2}) => (
  <>{G.rain.map(([x, y], i) => <g key={i} opacity={op} transform={`translate(${x},${y})`}><Rain f={f + i * 40} op={1} /></g>)}</>
);
const Fundo = ({G, f}) => (
  <AbsoluteFill style={{background: BG}}>
    <svg width={G.W} height={G.H} style={{position: 'absolute', inset: 0}}>
      <defs><radialGradient id="fg" cx="50%" cy="50%" r="75%"><stop offset="0%" stopColor="#0b2414" /><stop offset="100%" stopColor="#030605" /></radialGradient></defs>
      <rect width={G.W} height={G.H} fill="url(#fg)" />
      <ChuvaMatrix G={G} f={f} />
    </svg>
  </AbsoluteFill>
);

const Layer = ({seg, P, G, f, t}) => {
  const fonte = P.fonte, horiz = G.W > G.H;
  if (seg.m === 'take') {
    const c = G.circ;
    return (
      <AbsoluteFill>
        <Fundo G={G} f={f} />
        <svg width={G.W} height={G.H} style={{position: 'absolute', inset: 0}}>
          <Glow id="glt" sd={4} />
          <g transform={G.takeT} filter="url(#glt)"><Cena seg={seg} t={t} /></g>
        </svg>
        <div style={{position: 'absolute', left: c.x, top: c.y, width: c.d, height: c.d, borderRadius: c.d / 2, border: `6px solid ${LIME}`, boxShadow: '0 0 30px rgba(232,252,59,0.45)', boxSizing: 'border-box', overflow: 'hidden'}}>
          <Cam fonte={fonte} R={{x: -6, y: -6, w: c.d, h: c.d, r: 0}} alvo={0.62} />
        </div>
      </AbsoluteFill>
    );
  }
  if (seg.m === 'split') {
    const b = G.splitBox, bb = G.brollBox;
    return (
      <AbsoluteFill>
        <Fundo G={G} f={f} />
        <Cam fonte={fonte} R={G.card} alvo={G.alvoCard} style={{boxShadow: '0 30px 80px rgba(0,0,0,0.5)'}} />
        <div style={{position: 'absolute', left: b.x, top: b.y, width: b.w, height: b.h, overflow: 'hidden'}}>
          {seg.cena === 'broll' ? <div style={{position: 'absolute', left: bb.x, top: bb.y, width: bb.w, height: bb.h, borderRadius: bb.r, overflow: 'hidden'}}><Broll P={P} t={t} /></div> : (
            <svg width={b.w} height={b.h} viewBox={G.splitView} style={{position: 'absolute', left: 0, top: 0}}>
              <Glow id="gls" sd={5} />
              <g opacity={0.16}><Rain f={f} op={1} /></g>
              <g filter="url(#gls)"><Cena seg={seg} t={t} /></g>
            </svg>
          )}
        </div>
      </AbsoluteFill>
    );
  }
  const over = seg.m === 'over', R = over ? G.over : G.full;
  const overT = horiz ? `translate(${fonte.rosto.cx > 0.5 ? 360 : 1560},800) scale(0.62) translate(-540,-790)` : G.overT;
  return (
    <AbsoluteFill>
      <Fundo G={G} f={f} />
      <Cam fonte={fonte} R={R} alvo={G.alvoFull} fade={horiz ? 0 : 7} />
      {over ? (
        <>
          <AbsoluteFill style={{background: horiz ? 'linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0) 20%, rgba(0,0,0,0) 60%, rgba(3,6,5,0.55) 100%)' : 'linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0) 62%, rgba(3,6,5,0.72) 80%, rgba(3,6,5,0.88) 100%)'}} />
          <svg width={G.W} height={G.H} style={{position: 'absolute', inset: 0}}>
            <Glow id="glo" sd={4} />
            <g transform={overT} filter="url(#glo)"><Cena seg={seg} t={t} /></g>
          </svg>
        </>
      ) : <AbsoluteFill style={{background: horiz ? 'linear-gradient(180deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 18%, rgba(0,0,0,0) 72%, rgba(0,0,0,0.55) 100%)' : 'linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 20%, rgba(0,0,0,0) 66%, rgba(0,0,0,0.5) 100%)'}} />}
    </AbsoluteFill>
  );
};

const montarBlocos = (legendas) => {
  const out = [];
  (legendas || []).forEach((l) => {
    let cur = [];
    const ws = l.palavras;
    ws.forEach((w, i) => {
      cur.push(w);
      const chars = cur.map((x) => x.w).join(' ').length;
      if (cur.length >= 3 || chars > 18 || i === ws.length - 1) { out.push({ws: cur, fimL: l.fim}); cur = []; }
    });
  });
  out.forEach((b, i) => { b.ini = b.ws[0].s; b.fim = i + 1 < out.length ? Math.min(out[i + 1].ws[0].s, b.fimL + 0.05) : b.fimL; });
  return out;
};
const Legenda = ({t, blocos, y, G, x, w}) => {
  const b = blocos.find((q) => t >= q.ini - 0.02 && t < q.fim);
  if (!b) return null;
  const k = cl((t - b.ini) / 0.12);
  const len = b.ws.map((q) => q.w).join(' ').length;
  const size = Math.min(G.capMax, Math.floor(G.capK / (len * 0.66)));
  return (
    <div style={{position: 'absolute', left: x, width: w, top: y, textAlign: 'center', fontFamily: PF, fontWeight: 800, fontSize: size, whiteSpace: 'nowrap', lineHeight: 1.05,
      textTransform: 'uppercase', letterSpacing: '-0.01em', transform: `scale(${0.94 + 0.06 * k})`, opacity: Math.max(0.3, k), textShadow: '0 4px 24px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)'}}>
      {b.ws.map((q, i) => {
        const on = t >= q.s - 0.02 && (i === b.ws.length - 1 || t < b.ws[i + 1].s);
        return <span key={i} style={{color: on ? LIME : '#FFFFFF', marginRight: i < b.ws.length - 1 ? 16 : 0}}>{String(q.w).replace(/["“”]/g, '')}</span>;
      })}
    </div>
  );
};

export const RoboNeon = (P) => {
  const f = useCurrentFrame(), t = f / P.fps, total = P.frames / P.fps;
  const G = GEO[P.formato || '9x16'], horiz = G.W > G.H;
  const segs = P.segs && P.segs.length ? P.segs : [{s: 0, e: total + 1, m: 'full'}];
  const blocos = useMemo(() => montarBlocos(P.legendas), [P.legendas]);
  const cur = segs.find((x) => t >= x.s && t < x.e) || segs[segs.length - 1];
  const idxCur = segs.indexOf(cur);
  const layers = segs.filter((x, i) => t >= x.s && t < x.e + FADE / P.fps + 0.001 && !(i < idxCur && t >= x.e + FADE / P.fps));
  const ctaIni = total - 2.5;
  const cta = P.cta !== false && t >= ctaIni;
  const pin = OUT(cl(f / 14));
  const take = cur.m === 'take';
  const tit = P.vtitle || (() => { const w = String(P.corte?.tema || P.titulo || '').split(' ').filter(Boolean); return w.length ? {pre: w.slice(0, -1).join(' '), acc: w[w.length - 1]} : null; })();
  const H = G.head;
  let yLeg, xLeg = G.capX, wLeg = G.capW;
  if (cur.m === 'full') yLeg = G.capY.full;
  else if (cur.m === 'over') yLeg = horiz ? G.capY.full : queixoY(G.over, P.fonte, G.alvoFull) + 40;
  else if (take) yLeg = G.capY.take;
  else { yLeg = G.capY.split; if (horiz) { xLeg = G.card.x; wLeg = G.card.w; } }
  if (horiz && take) { xLeg = 0; wLeg = 1920; }
  const pc = OUT(cl((t - ctaIni) / 0.5));
  return (
    <AbsoluteFill style={{background: BG}}>
      {layers.map((sg) => {
        const o = sg.s <= 0 ? 1 : cl(((t - sg.s) * P.fps) / FADE);
        return <AbsoluteFill key={sg.s} style={{opacity: o}}><Layer seg={sg} P={P} G={G} f={f} t={t} /></AbsoluteFill>;
      })}
      <div style={{position: 'absolute', left: H.left, top: take ? H.topTake : H.top, width: take ? 700 : H.w, opacity: pin, transform: `translateY(${(1 - pin) * 14}px)`}}>
        <div style={{fontFamily: PF, fontWeight: 700, fontSize: H.tk, letterSpacing: '0.28em', color: LIME, textTransform: 'uppercase', textShadow: '0 2px 12px rgba(0,0,0,0.7)'}}>{P.canal || 'Natinha'}</div>
        {take || !tit ? null : (
          <div style={{fontFamily: PF, fontWeight: 800, fontSize: H.tt, color: '#fff', lineHeight: 1.08, marginTop: 10, textTransform: 'uppercase', letterSpacing: '-0.01em', textShadow: '0 3px 16px rgba(0,0,0,0.7)'}}>
            {tit.pre} <span style={{background: LIME, color: BG, padding: '0 14px', borderRadius: 6, textShadow: 'none'}}>{tit.acc}</span>
          </div>
        )}
      </div>
      {!cta && (!horiz || P.legendaHorizontal !== false) && <Legenda t={t} blocos={blocos} y={yLeg} G={G} x={xLeg} w={wLeg} />}
      {cta && (
        <div style={{position: 'absolute', left: 0, right: 0, top: G.cta.top, bottom: 0, textAlign: 'center', opacity: pc, background: 'linear-gradient(180deg, rgba(3,6,5,0) 0%, rgba(3,6,5,0.92) 30%)', paddingTop: G.cta.pad}}>
          <div style={{transform: `translateY(${(1 - pc) * 20}px)`}}>
            <div style={{fontFamily: PF, fontWeight: 700, fontSize: G.cta.k1, letterSpacing: '0.28em', color: LIME, textTransform: 'uppercase'}}>vídeo completo no canal</div>
            <div style={{fontFamily: PF, fontWeight: 800, fontSize: G.cta.k2, color: '#fff', marginTop: 20, textTransform: 'uppercase'}}>
              Siga a <span style={{background: LIME, color: BG, padding: '0 16px', borderRadius: 8}}>{P.canal || 'Natinha'}</span>
            </div>
          </div>
        </div>
      )}
      <AbsoluteFill style={{background: '#000', opacity: IO(cl((t - (total - 0.3)) / 0.3))}} />
      {!P.semAudio && P.audio && <Audio src={staticFile(P.audio)} />}
    </AbsoluteFill>
  );
};
