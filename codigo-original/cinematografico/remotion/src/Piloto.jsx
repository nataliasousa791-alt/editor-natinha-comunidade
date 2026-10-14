// Piloto V5 (Remotion) — Natinha proporcional + B-roll real + motion editorial ancorado nas palavras.
import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, Easing, continueRender, delayRender,
  staticFile, useCurrentFrame} from 'remotion';
import tl from './timeline.json';

const fh = delayRender('fontes');
Promise.all([
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Bold.ttf')})`, {weight: '700'}).load(),
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Medium.ttf')})`, {weight: '500'}).load(),
  new FontFace('Lora', `url(${staticFile('fonts/Lora-Variable.ttf')})`, {weight: '400 700'}).load(),
]).then((fs) => { fs.forEach((f) => document.fonts.add(f)); continueRender(fh); });

const FPS = tl.fps, A = tl.a;
const SW = 1024, SH = 576, FACE_X = 660, FACE_Y = 380;          // quadro nativo da Natinha (medido)
const AMBAR = '#E8833A', BRANCO = '#F5F3EE', CINZA = '#A3A7AF', GRAFITE = '#121316';
const cl = (x) => Math.min(1, Math.max(0, x));
const OUT = Easing.bezier(0.16, 1, 0.3, 1);                       // desaceleracao longa (expo-out)
const IO = Easing.bezier(0.65, 0, 0.35, 1);                       // entrada/saida suave
const p = (t, s, d, e = OUT) => e(cl((t - s) / d));
const lerp = (a, b, k) => a + (b - a) * k;
const F = (s) => Math.round(s * FPS);

// ---------- layout: A (Natinha grande) <-> B (grafico em cima, Natinha em janela) ----------
const mB = (t) => p(t, A.AB0 - 0.05, 0.6, IO) * (1 - p(t, A.BA0 - 0.05, 0.6, IO));
const RA = {x: 0, y: 400, w: 1080, h: 1060, r: 0}, RB = {x: 36, y: 930, w: 1008, h: 720, r: 44};
const zoomDe = (t) => {                                            // respiracao de camera por plano, sempre uniforme
  const cuts = [0, ...A.CUTS, tl.total];
  for (let k = 0; k < cuts.length - 1; k++) if (t >= cuts[k] && t < cuts[k + 1]) {
    const base = {2: 1.05, 6: 1.07}[k] || 1.0;
    return base + 0.035 * IO(cl((t - cuts[k]) / (cuts[k + 1] - cuts[k])));
  }
  return 1;
};

const Natinha = ({t}) => {
  const m = mB(t);
  const R = Object.fromEntries(Object.keys(RA).map((k) => [k, lerp(RA[k], RB[k], m)]));
  const s = (R.h / SH) * lerp(1.25, 1.30, m) * zoomDe(t);                                 // UMA escala para x e y
  const vw = SW * s, vh = SH * s;
  const left = Math.min(0, Math.max(R.w - vw, R.w / 2 - FACE_X * s));
  const top = Math.min(0, Math.max(R.h - vh, R.h / 2 - FACE_Y * s));
  const fe = 11 * (1 - m);
  const mask = `linear-gradient(to bottom, transparent 0%, #000 ${fe}%, #000 ${100 - fe}%, transparent 100%)`;
  return (
    <div style={{position: 'absolute', left: R.x, top: R.y, width: R.w, height: R.h, borderRadius: R.r, overflow: 'hidden',
      WebkitMaskImage: m < 0.98 ? mask : undefined, boxShadow: `0 40px 90px rgba(0,0,0,${0.6 * m})`,
      outline: `1.5px solid rgba(255,255,255,${0.12 * m})`, outlineOffset: -1.5}}>
      <OffthreadVideo src={staticFile('natinha.mp4')} muted
        style={{position: 'absolute', left, top, width: vw, height: vh}} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,0) 55%, rgba(8,7,6,0.55) 100%)'}} />
    </div>
  );
};

const Fundo = () => (                                               // a propria Natinha, ampliada e desfocada
  <div style={{position: 'absolute', left: 0, top: 0, width: 270, height: 480, overflow: 'hidden',
    transform: 'scale(4)', transformOrigin: '0 0', filter: 'blur(7px) brightness(0.30) saturate(0.75)'}}>
    <OffthreadVideo src={staticFile('natinha.mp4')} muted
      style={{position: 'absolute', height: 480, width: 480 * SW / SH, left: 135 - FACE_X * 480 / SH, top: 0}} />
  </div>
);

// ---------- tipografia ----------
const Linha = ({children, t, s, d = 0.55, style}) => {             // revelacao por mascara + desfoque
  const k = p(t, s, d);
  return (
    <div style={{overflow: 'hidden', paddingBottom: 8}}>
      <div style={{transform: `translateY(${(1 - k) * 105}%)`, filter: `blur(${(1 - k) * 6}px)`, opacity: cl(k * 1.4), ...style}}>{children}</div>
    </div>
  );
};
const Kicker = ({t, s, children, op = 1, style}) => {
  const k = p(t, s, 0.5);
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 14, opacity: k * op, transform: `translateX(${(1 - k) * -18}px)`, ...style}}>
      <div style={{width: 10, height: 10, borderRadius: 5, background: AMBAR}} />
      <div style={{font: '500 25px Poppins', letterSpacing: 5, color: CINZA}}>{children}</div>
    </div>
  );
};

const TituloAbertura = ({t}) => {
  if (t > A.AB0 + 0.4) return null;
  const sai = p(t, 2.7, 0.4, IO);
  const kOut = 1 - p(t, A.AB0 - 0.3, 0.3, IO);
  return (
    <>
      {sai < 1 && (
        <div style={{position: 'absolute', top: 175, width: '100%', textAlign: 'center', opacity: 1 - sai, transform: `translateY(${-40 * sai}px)`}}>
          <Linha t={t} s={0.12} style={{font: '700 50px Poppins', letterSpacing: 10, color: BRANCO}}>QUEM LUCRA COM</Linha>
          <Linha t={t} s={0.30} d={0.7} style={{font: '700 112px Lora', color: AMBAR, lineHeight: 1.05}}>o seu tempo?</Linha>
          <div style={{margin: '18px auto 0', height: 3, width: 300, background: AMBAR, transform: `scaleX(${p(t, 0.7, 0.8)})`}} />
        </div>
      )}
      {t > 2.9 && <Kicker t={t} s={3.0} op={kOut} style={{position: 'absolute', left: 64, top: 300}}>QUEM LUCRA COM O SEU TEMPO?</Kicker>}
    </>
  );
};

// ---------- painel superior com B-roll real ----------
const CARD = {x: 36, y: 150, w: 1008, h: 730};
const Video = ({src, style, filter}) => (
  <OffthreadVideo src={staticFile(src)} muted style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', filter, ...style}} />
);
const Painel = ({t}) => {
  if (t < A.AB0 - 0.1 || t > A.BA0 + 0.7) return null;
  const abre = p(t, A.AB0, 0.75, IO), fecha = p(t, A.BA0 - 0.05, 0.55, IO);
  const clip = `inset(0 0 ${(1 - abre) * 100 + fecha * 100}% 0 round 44px)`;
  const f2 = p(t, A.P2, 0.4, IO);                                   // troca de fase em "para uma pessoa"
  const su = p(t, A.S0, A.S1 - A.S0, IO);                           // "outro patamar"
  const horas = Array.from({length: 10}, (_, i) => p(t, A.P1_INI + i * (A.P1_FIM - A.P1_INI) / 9, 0.3));
  const rev = p(t, A.REV, 0.7, IO);
  const passo = Math.max(0, su);
  return (
    <div style={{position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, clipPath: clip,
      borderRadius: 44, overflow: 'hidden', background: GRAFITE, transform: `translateY(${(1 - abre) * -30 + fecha * -20}px)`}}>
      {/* FASE 1 — relogio real: "a gente vende... as nossas horas" */}
      {f2 < 1 && (
        <div style={{position: 'absolute', inset: 0, opacity: 1 - f2}}>
          <Sequence from={F(A.AB0 - 0.1)} durationInFrames={F(A.P2 - A.AB0 + 0.8)} layout="none">
            <div style={{position: 'absolute', inset: 0, transform: `scale(${1.02 + 0.08 * p(t, A.AB0, A.P2 - A.AB0, IO)})`}}>
              <Video src="relogio.mp4" filter="grayscale(1) sepia(0.28) contrast(1.18) brightness(0.62)" />
            </div>
          </Sequence>
          <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.55) 100%), linear-gradient(to bottom, rgba(10,9,8,0.55) 0%, rgba(10,9,8,0) 22%, rgba(10,9,8,0) 45%, rgba(10,9,8,0.92) 100%)'}} />
          <Kicker t={t} s={A.AB0 + 0.35} style={{position: 'absolute', left: 44, top: 40}}>O QUE A GENTE VENDE</Kicker>
          <div style={{position: 'absolute', left: 0, right: 0, top: 455, display: 'flex', justifyContent: 'center', gap: 26}}>
            <Linha t={t} s={A.HORAS - 0.05} style={{font: '400 118px Lora', color: BRANCO}}>nossas</Linha>
            <Linha t={t} s={A.HORAS + 0.12} style={{font: 'italic 700 118px Lora', color: AMBAR}}>horas</Linha>
          </div>
          <div style={{position: 'absolute', left: 64, right: 64, top: 640, display: 'flex', gap: 10}}>
            {horas.map((k, i) => (
              <div key={i} style={{flex: 1, height: 10, borderRadius: 5, background: 'rgba(255,255,255,0.16)', overflow: 'hidden'}}>
                <div style={{height: '100%', width: `${k * 100}%`, background: AMBAR, boxShadow: `0 0 18px ${AMBAR}`}} />
              </div>
            ))}
          </div>
        </div>
      )}
      {/* FASE 2 — a troca: o trabalho real do nosso lado; do lado dele, nada para mostrar */}
      {f2 > 0 && (
        <div style={{position: 'absolute', inset: 0, opacity: f2}}>
          <div style={{position: 'absolute', left: 0, top: 0, width: 502, height: CARD.h, background: '#17181B', overflow: 'hidden'}}>
            {t >= A.REV - 0.05 && (
              <Sequence from={F(A.REV - 0.05)} durationInFrames={F(A.BA0 - A.REV + 1)} layout="none">
                <div style={{position: 'absolute', inset: 0, clipPath: `inset(0 ${(1 - rev) * 100}% 0 0)`,
                  transform: `scale(${1.12 - 0.08 * rev})`, transformOrigin: '85% 50%', filter: `brightness(${1 - 0.5 * su}) saturate(${1 - 0.6 * su})`}}>
                  <Video src="obra.mp4" style={{objectPosition: '97% 50%'}} filter="contrast(1.06) saturate(0.85) sepia(0.12)" />
                </div>
              </Sequence>
            )}
            <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 25%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.85) 100%)'}} />
          </div>
          <div style={{position: 'absolute', left: 502, top: 0, width: 506, height: CARD.h, background: 'linear-gradient(160deg, #1B1C20 0%, #0E0F11 100%)'}} />
          <div style={{position: 'absolute', left: 501, top: 0, width: 2, height: CARD.h * p(t, A.P2, 0.6), background: 'rgba(255,255,255,0.14)'}} />
          <Kicker t={t} s={A.P2} style={{position: 'absolute', left: 44, top: 36}}>A TROCA</Kicker>
          <div style={{position: 'absolute', left: 44, top: 92, font: '700 46px Poppins', letterSpacing: 4, color: BRANCO, opacity: p(t, A.P2 + 0.1, 0.4) * (1 - 0.4 * su)}}>A GENTE</div>
          <div style={{position: 'absolute', left: 546, top: 92, transform: `translateY(${-0 * su}px)`, font: '700 46px Poppins', letterSpacing: 4, color: BRANCO, opacity: p(t, A.P2 + 0.2, 0.4)}}>ELE</div>
          {[[A.FZ, 'faz o trabalho', 560], [A.RC, 'o que a gente recebe', 624]].map(([s, txt, y]) => {
            const k = p(t, s, 0.45);
            return <div key={txt} style={{position: 'absolute', left: 44, top: y, display: 'flex', alignItems: 'center', gap: 14, opacity: k * (1 - 0.45 * su), transform: `translateX(${(1 - k) * -16}px)`}}>
              <div style={{width: 12, height: 12, borderRadius: 6, background: AMBAR}} />
              <div style={{font: '700 38px Poppins', color: BRANCO}}>{txt}</div></div>;
          })}
          {[[A.R1, 'não quer fazer', 560], [A.R2, 'não quer receber', 624]].map(([s, txt, y]) => {
            const k = p(t, s, 0.45);
            return <div key={txt} style={{position: 'absolute', left: 546, top: y - 250 * su, opacity: k, transform: `translateX(${(1 - k) * 16}px)`,
              font: '500 38px Poppins', color: CINZA}}>{txt}</div>;
          })}
          {/* degrau: do nosso nivel ao "outro patamar" */}
          <svg width={CARD.w} height={CARD.h} style={{position: 'absolute', left: 0, top: 0}}>
            <path d={`M 44 700 L 502 700 L 502 ${700 - 250} L 964 ${700 - 250}`} fill="none" stroke={AMBAR} strokeWidth={4}
              strokeLinecap="round" strokeDasharray={1200} strokeDashoffset={1200 * (1 - passo)} style={{filter: `drop-shadow(0 0 10px ${AMBAR})`}} />
          </svg>
          <div style={{position: 'absolute', right: 44, top: 468, font: 'italic 600 46px Lora', color: AMBAR, opacity: p(t, A.S1 - 0.15, 0.45),
            transform: `translateY(${(1 - p(t, A.S1 - 0.15, 0.45)) * 14}px)`}}>outro patamar</div>
        </div>
      )}
    </div>
  );
};

// ---------- fechamento ----------
const TituloFinal = ({t}) => {
  if (t < A.SEM - 0.05) return null;
  const pal = A.FIM;
  const W1 = pal.slice(0, 4), W2 = pal.slice(4);
  const palavra = ([w, s], estilo) => {
    const k = p(t, s, 0.45);
    return <span key={w + s} style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'top', paddingBottom: 6}}>
      <span style={{display: 'inline-block', transform: `translateY(${(1 - k) * 100}%)`, filter: `blur(${(1 - k) * 5}px)`, opacity: cl(k * 1.5), ...estilo}}>{w}&nbsp;</span></span>;
  };
  return (
    <div style={{position: 'absolute', top: 170, width: '100%', textAlign: 'center'}}>
      <div>{W1.map((w) => palavra(w, {font: '400 76px Lora', color: BRANCO}))}</div>
      <div style={{marginTop: 4}}>{W2.map((w) => palavra(w, {font: '700 104px Poppins', color: AMBAR, letterSpacing: -1}))}</div>
      <div style={{margin: '22px auto 0', height: 3, width: 360, background: AMBAR, transform: `scaleX(${p(t, A.FIM[6][1] + 0.1, 0.7)})`}} />
    </div>
  );
};

// ---------- legendas ----------
const CHAVE = new Set(['escravidão', 'horas', 'patamar']);
const Legenda = ({t}) => {
  const c = tl.chunks.find((c) => t >= c.ini && t < c.fim);
  if (!c) return null;
  const k = p(t, c.ini, 0.14);
  const y = lerp(1330, 1585, mB(t));
  return (
    <div style={{position: 'absolute', top: y, width: '100%', textAlign: 'center', opacity: k, transform: `translateY(${(1 - k) * 10}px)`}}>
      {c.words.map((w, i) => {
        const limpo = w.w.toLowerCase().replace(/[^\wà-ú]/g, '');
        return <span key={i} style={{font: '700 62px Poppins', color: CHAVE.has(limpo) ? AMBAR : BRANCO, WebkitTextStroke: '7px rgba(12,11,10,0.8)',
          paintOrder: 'stroke fill', textShadow: '0 6px 22px rgba(0,0,0,0.55)'}}>{w.w}{i < c.words.length - 1 ? ' ' : ''}</span>;
      })}
    </div>
  );
};

export const Piloto = () => {
  const f = useCurrentFrame(), t = f / FPS;
  const fadeOut = p(t, tl.total - 0.45, 0.45, IO);
  return (
    <AbsoluteFill style={{background: '#0B0B0D'}}>
      <Fundo />
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 20%, rgba(0,0,0,0) 70%, rgba(0,0,0,0.6) 100%)'}} />
      <Natinha t={t} />
      <TituloAbertura t={t} />
      <Painel t={t} />
      <TituloFinal t={t} />
      <Legenda t={t} />
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.35) 100%)', pointerEvents: 'none'}} />
      <AbsoluteFill style={{background: '#000', opacity: fadeOut}} />
      <Audio src={staticFile('voz.m4a')} />
    </AbsoluteFill>
  );
};
