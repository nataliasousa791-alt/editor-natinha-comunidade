// Piloto V6 (Remotion) — base V5 (Natinha proporcional, legendas por palavra) + B-roll REAL em movimento,
// cada plano ancorado na palavra que o justifica. Sem caixas/setas; texto editorial minimo.
import React from 'react';
import {Video as MV} from '@remotion/media';
import {AbsoluteFill, Audio, Sequence, Easing, continueRender, delayRender,
  staticFile, useCurrentFrame} from 'remotion';
import tl from './timeline.json';

const fh = delayRender('fontes');
Promise.all([
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Bold.ttf')})`, {weight: '700'}).load(),
  new FontFace('Poppins', `url(${staticFile('fonts/Poppins-Medium.ttf')})`, {weight: '500'}).load(),
  new FontFace('Lora', `url(${staticFile('fonts/Lora-Variable.ttf')})`, {weight: '400 700'}).load(),
]).then((fs) => { fs.forEach((f) => document.fonts.add(f)); continueRender(fh); });

const FPS = tl.fps, A = tl.a;
const SW = 1024, SH = 576, FACE_X = 660, FACE_Y = 380;
const AMBAR = '#E8833A', BRANCO = '#F5F3EE', CINZA = '#B9BCC2';
const GRADE = 'saturate(0.80) contrast(1.08) sepia(0.14) brightness(0.90)';   // cor unica para todo B-roll
const cl = (x) => Math.min(1, Math.max(0, x));
const OUT = Easing.bezier(0.16, 1, 0.3, 1);
const IO = Easing.bezier(0.65, 0, 0.35, 1);
const p = (t, s, d, e = OUT) => e(cl((t - s) / d));
const lerp = (a, b, k) => a + (b - a) * k;
const F = (s) => Math.round(s * FPS);

// tempos ancorados na fala (s, timeline.json)
const FB_IN = 3.55, FB_OUT = 5.95;          // "num sistema diferente" -> volta na Natinha antes de "escravidao"
const T_SPARK = A.AB0, T_FAZ = A.P2, T_ALTO = A.S0 - 0.08;

// ---------- Natinha ----------
const mB = (t) => p(t, A.AB0 - 0.05, 0.6, IO) * (1 - p(t, A.BA0 - 0.05, 0.6, IO));
const RA = {x: 0, y: 400, w: 1080, h: 1060, r: 0}, RB = {x: 36, y: 930, w: 1008, h: 720, r: 44};
const zoomDe = (t) => {
  const cuts = [0, ...A.CUTS, tl.total];
  for (let k = 0; k < cuts.length - 1; k++) if (t >= cuts[k] && t < cuts[k + 1]) {
    const base = {2: 1.06, 5: 1.07}[k] || 1.0;
    return base + 0.03 * IO(cl((t - cuts[k]) / (cuts[k + 1] - cuts[k])));
  }
  return 1;
};
const Natinha = ({t}) => {
  const m = mB(t);
  const R = Object.fromEntries(Object.keys(RA).map((k) => [k, lerp(RA[k], RB[k], m)]));
  const s = (R.h / SH) * lerp(1.25, 1.30, m) * zoomDe(t);          // UMA escala para x e y
  const vw = SW * s, vh = SH * s;
  const left = Math.min(0, Math.max(R.w - vw, R.w / 2 - FACE_X * s));
  const top = Math.min(0, Math.max(R.h - vh, R.h / 2 - FACE_Y * s));
  const fe = 11 * (1 - m);
  const mask = `linear-gradient(to bottom, transparent 0%, #000 ${fe}%, #000 ${100 - fe}%, transparent 100%)`;
  return (
    <div style={{position: 'absolute', left: R.x, top: R.y, width: R.w, height: R.h, borderRadius: R.r, overflow: 'hidden',
      WebkitMaskImage: m < 0.98 ? mask : undefined, boxShadow: `0 40px 90px rgba(0,0,0,${0.6 * m})`,
      outline: `1.5px solid rgba(255,255,255,${0.12 * m})`, outlineOffset: -1.5}}>
      <MV src={staticFile('natinha.mp4')} muted style={{position: 'absolute', left, top, width: vw, height: vh}} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,0) 55%, rgba(8,7,6,0.5) 100%)'}} />
    </div>
  );
};
const Fundo = () => (
  <div style={{position: 'absolute', left: 0, top: 0, width: 270, height: 480, overflow: 'hidden',
    transform: 'scale(4)', transformOrigin: '0 0', filter: 'blur(7px) brightness(0.30) saturate(0.75)'}}>
    <MV src={staticFile('natinha.mp4')} muted
      style={{position: 'absolute', height: 480, width: 480 * SW / SH, left: 135 - FACE_X * 480 / SH, top: 0}} />
  </div>
);

// ---------- tipografia ----------
const Linha = ({children, t, s, d = 0.55, style}) => {
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
      <div style={{font: '500 25px Poppins', letterSpacing: 5, color: CINZA, textShadow: '0 2px 10px rgba(0,0,0,0.6)'}}>{children}</div>
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

// ---------- B-roll em tela cheia: "a gente vive num sistema" -> Sao Paulo real ----------
const Clip = ({src, from, dur, pos = '50% 50%', z0 = 1.04, z1 = 1.12, origin = '50% 50%'}) => {
  const f = useCurrentFrame(), k = cl(f / (dur * FPS));
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, transform: `scale(${lerp(z0, z1, k)})`, transformOrigin: origin}}>
        <MV src={staticFile(src)} muted objectFit="cover" style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: pos, filter: GRADE}} />
      </div>
    </div>
  );
};
const TelaCheia = ({t}) => {
  if (t < FB_IN - 0.05 || t > FB_OUT + 0.4) return null;
  const op = p(t, FB_IN, 0.28, IO) * (1 - p(t, FB_OUT, 0.35, IO));
  return (
    <AbsoluteFill style={{opacity: op}}>
      <Sequence from={F(FB_IN - 0.05)} durationInFrames={F(FB_OUT - FB_IN + 0.5)} layout="none">
        <Clip src="sp_centro.mp4" dur={FB_OUT - FB_IN + 0.5} pos="60% 50%" z0={1.02} z1={1.10} />
      </Sequence>
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(8,7,6,0.55) 0%, rgba(8,7,6,0) 26%, rgba(8,7,6,0) 60%, rgba(8,7,6,0.75) 100%)'}} />
      <Kicker t={t} s={FB_IN + 0.25} style={{position: 'absolute', left: 64, bottom: 330}}>SÃO PAULO</Kicker>
    </AbsoluteFill>
  );
};

// ---------- painel superior: o trabalho real que vira "horas" vendidas ----------
const CARD = {x: 36, y: 150, w: 1008, h: 730};
const Painel = ({t}) => {
  if (t < A.AB0 - 0.1 || t > A.BA0 + 0.7) return null;
  const abre = p(t, A.AB0, 0.75, IO), fecha = p(t, A.BA0 - 0.05, 0.55, IO);
  const clip = `inset(0 0 ${(1 - abre) * 100 + fecha * 100}% 0 round 44px)`;
  const f2 = p(t, T_FAZ - 0.1, 0.4, IO), f3 = p(t, T_ALTO - 0.1, 0.4, IO);
  const horas = Array.from({length: 10}, (_, i) => p(t, A.P1_INI + i * (A.P1_FIM - A.P1_INI) / 9, 0.3));
  const sombra = 'linear-gradient(to bottom, rgba(8,7,6,0.6) 0%, rgba(8,7,6,0) 24%, rgba(8,7,6,0) 48%, rgba(8,7,6,0.9) 100%)';
  return (
    <div style={{position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, clipPath: clip,
      borderRadius: 44, overflow: 'hidden', background: '#111', transform: `translateY(${(1 - abre) * -30 + fecha * -20}px)`}}>
      {/* 1 — "a gente vende, vende, ne, as nossas horas": maos de um trabalhador real cortando ferro */}
      {f2 < 1 && (
        <AbsoluteFill>
          <Sequence from={F(T_SPARK - 0.1)} durationInFrames={F(T_FAZ - T_SPARK + 0.6)} layout="none">
            <Clip src="faisca.mp4" dur={T_FAZ - T_SPARK + 0.6} pos="45% 60%" z0={1.10} z1={1.02} origin="40% 70%" />
          </Sequence>
          <AbsoluteFill style={{background: sombra}} />
          <Kicker t={t} s={A.AB0 + 0.35} style={{position: 'absolute', left: 44, top: 40}}>O QUE A GENTE VENDE</Kicker>
          <div style={{position: 'absolute', left: 0, right: 0, top: 470, display: 'flex', justifyContent: 'center', gap: 26}}>
            <Linha t={t} s={A.HORAS - 0.05} style={{font: '400 118px Lora', color: BRANCO, textShadow: '0 6px 30px rgba(0,0,0,0.6)'}}>nossas</Linha>
            <Linha t={t} s={A.HORAS + 0.12} style={{font: 'italic 700 118px Lora', color: AMBAR, textShadow: '0 6px 30px rgba(0,0,0,0.6)'}}>horas</Linha>
          </div>
          <div style={{position: 'absolute', left: 64, right: 64, top: 655, display: 'flex', gap: 10}}>
            {horas.map((k, i) => (
              <div key={i} style={{flex: 1, height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.18)', overflow: 'hidden'}}>
                <div style={{height: '100%', width: `${k * 100}%`, background: AMBAR}} />
              </div>
            ))}
          </div>
        </AbsoluteFill>
      )}
      {/* 2 — "...uma pessoa que nao quer fazer o que a gente faz": o trabalho bracal acontecendo */}
      {f2 > 0 && f3 < 1 && (
        <AbsoluteFill style={{opacity: f2}}>
          <Sequence from={F(T_FAZ - 0.15)} durationInFrames={F(T_ALTO - T_FAZ + 0.5)} layout="none">
            <Clip src="carrinho.mp4" dur={T_ALTO - T_FAZ + 0.6} pos="62% 45%" z0={1.04} z1={1.11} origin="65% 50%" />
          </Sequence>
          <AbsoluteFill style={{background: sombra}} />
          <Kicker t={t} s={T_FAZ + 0.1} style={{position: 'absolute', left: 44, top: 40}}>QUEM FAZ O TRABALHO</Kicker>
        </AbsoluteFill>
      )}
      {/* 3 — "ele ja chegou em outro patamar": a cidade vista de cima */}
      {f3 > 0 && (
        <AbsoluteFill style={{opacity: f3}}>
          <Sequence from={F(T_ALTO - 0.15)} durationInFrames={F(A.BA0 - T_ALTO + 0.9)} layout="none">
            <Clip src="transito.mp4" dur={A.BA0 - T_ALTO + 0.9} pos="50% 70%" z0={1.16} z1={1.04} origin="50% 80%" />
          </Sequence>
          <AbsoluteFill style={{background: sombra}} />
          <Kicker t={t} s={T_ALTO + 0.1} style={{position: 'absolute', left: 44, top: 40}}>VISTO DE CIMA</Kicker>
          <div style={{position: 'absolute', left: 0, right: 0, top: 520, textAlign: 'center'}}>
            <Linha t={t} s={A.S1 - 0.2} style={{font: 'italic 700 104px Lora', color: AMBAR, textShadow: '0 6px 30px rgba(0,0,0,0.7)'}}>outro patamar</Linha>
          </div>
        </AbsoluteFill>
      )}
    </div>
  );
};

// ---------- fechamento ----------
const TituloFinal = ({t}) => {
  if (t < A.SEM - 0.05) return null;
  const pal = A.FIM, W1 = pal.slice(0, 4), W2 = pal.slice(4);
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

// ---------- legendas (palavra a palavra, timestamps revisados do V5) ----------
const CHAVE = new Set(['escravidão', 'horas', 'patamar']);
const Legenda = ({t}) => {
  if (t >= A.SEM - 0.05) return null;                        // o fechamento ja esta escrito na tela
  const c = tl.chunks.find((c) => t >= c.ini && t < c.fim);
  if (!c) return null;
  const k = p(t, c.ini, 0.14);
  const y = lerp(1330, 1585, mB(t));
  return (
    <div style={{position: 'absolute', top: y, width: '100%', textAlign: 'center', opacity: k, transform: `translateY(${(1 - k) * 10}px)`}}>
      {c.words.map((w, i) => {
        const limpo = w.w.toLowerCase().replace(/[^\wà-ú]/g, '');
        const dita = t >= w.s - 0.02;
        return <span key={i} style={{font: '700 62px Poppins', color: CHAVE.has(limpo) ? AMBAR : BRANCO, opacity: dita ? 1 : 0.55,
          WebkitTextStroke: '7px rgba(12,11,10,0.8)', paintOrder: 'stroke fill', textShadow: '0 6px 22px rgba(0,0,0,0.55)'}}>{w.w}{i < c.words.length - 1 ? ' ' : ''}</span>;
      })}
    </div>
  );
};

export const PilotoV6 = () => {
  const f = useCurrentFrame(), t = f / FPS;
  const fadeOut = p(t, tl.total - 0.45, 0.45, IO);
  return (
    <AbsoluteFill style={{background: '#0B0B0D'}}>
      <Fundo />
      <AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 20%, rgba(0,0,0,0) 70%, rgba(0,0,0,0.6) 100%)'}} />
      <Natinha t={t} />
      <TelaCheia t={t} />
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
