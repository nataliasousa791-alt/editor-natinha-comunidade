import React from 'react';
import {Figure, Rain, Desk, scene, STAND, walk, seated, mix, hash, clamp, seg, L, G, WH, PK, DK, LIME, GL, GROUND as G0, S as S0} from './Opcoes';
import {F} from './theme';

type Pose = Parameters<typeof Figure>[0]['p'];
export const SW = 9, GR = 790, SC = 1.5;
const pose = (o: Partial<Pose>): Pose => ({...STAND, ...o});
const fig = (kind: 'person' | 'robot', x: number, p: Pose, dir: number, f: number, o: {s?: number; col?: string; box?: number; y?: number} = {}) => (
  <g transform={`translate(${x},${o.y ?? GR}) scale(${(o.s ?? SC) * dir},${o.s ?? SC})`}>
    <Figure p={p} kind={kind} col={o.col ?? (kind === 'person' ? LIME : WH)} fill={DK} eye={PK} sw={SW / ((o.s ?? SC) > 1 ? 1 : (o.s ?? SC) * 1.1)} f={f} box={o.box ?? 0} />
  </g>
);
const Ground: React.FC<{col?: string}> = ({col = '#14B85A'}) => <line x1={0} x2={1080} y1={GR} y2={GR} stroke={col} strokeWidth={5} opacity={0.4} strokeLinecap="round" />;
const T: React.FC<{x: number; y: number; size: number; col?: string; anchor?: 'start' | 'middle' | 'end'; op?: number; bold?: boolean; children: React.ReactNode}> = ({x, y, size, col = LIME, anchor = 'middle', op = 1, bold, children}) => (
  <text x={x} y={y} fontSize={size} fontFamily={F.mono} fontWeight={bold ? 700 : 500} fill={col} textAnchor={anchor} opacity={op}>{children}</text>
);

// ---------- S1: IA monolith rising
const Monolito: React.FC<{f: number}> = ({f}) => {
  const h = 460 * seg(f, 14, 70);
  const shake = f > 70 ? Math.sin(f * 2.3) * 3 : 0;
  const pulse = 0.6 + 0.4 * Math.sin(f / 5);
  return (
    <g>
      <Ground />
      {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M${720 + i * 50},${GR} l${10 - i * 6},${-20 - i * 4} l${14},${-16}`} stroke={LIME} strokeWidth={3} fill="none" opacity={seg(f, 20, 50) * 0.7} />)}
      <g transform={`translate(${760 + shake},${GR - h})`}>
        <rect width={170} height={h} fill="#06120A" stroke={LIME} strokeWidth={5} />
        {h > 120 ? Array.from({length: 14}).map((_, r) => Array.from({length: 7}).map((__, c) => {
          const y = 20 + r * 30; if (y > h - 10) return null;
          return <text key={`${r}-${c}`} x={14 + c * 23} y={y} fontSize={20} fontFamily={F.mono} fill={G} opacity={0.25 + 0.6 * hash(r * 9 + c + Math.floor(f / 4))}>{GL[Math.floor(hash(r * 7 + c * 3 + Math.floor(f / 4)) * 40) % GL.length]}</text>;
        })) : null}
        <T x={85} y={h / 2 + 30} size={96} col={WH} bold op={seg(f, 60, 80)}>IA</T>
      </g>
      <g opacity={seg(f, 62, 78) * pulse}><rect x={745} y={GR - 480} width={200} height={480} fill="none" stroke={PK} strokeWidth={2} /></g>
      {fig('person', 330, pose({l: -6, hd: -16 + (f > 70 ? 4 * Math.sin(f / 3) : 0), uaL: f > 90 ? 120 : 8, faL: f > 90 ? 170 : 20}), 1, f)}
      {Array.from({length: 12}).map((_, i) => {
        const y = GR - ((f * 3 + i * 53) % 480); const x = 770 + hash(i) * 150;
        return f > 40 ? <text key={i} x={x} y={y} fontSize={22} fontFamily={F.mono} fill={G} opacity={0.5}>{GL[Math.floor(hash(i + f / 6) * 40) % GL.length]}</text> : null;
      })}
    </g>
  );
};

// ---------- S2a: music
const Musica: React.FC<{f: number}> = ({f}) => (
  <g>
    <Ground />
    {Array.from({length: 16}).map((_, i) => {
      const hgt = 40 + 150 * Math.abs(Math.sin(f / 5 + i * 0.7)) * (0.5 + hash(i));
      return <rect key={i} x={70 + i * 62} y={GR - hgt} width={36} height={hgt} fill={G} opacity={0.22} />;
    })}
    <rect x={340} y={GR - 170} width={400} height={26} fill={DK} stroke={LIME} strokeWidth={5} />
    {Array.from({length: 11}).map((_, i) => <line key={i} x1={356 + i * 35} y1={GR - 144} x2={356 + i * 35} y2={GR - 120} stroke={LIME} strokeWidth={3} opacity={0.6} />)}
    <line x1={380} y1={GR - 144} x2={380} y2={GR} stroke={LIME} strokeWidth={5} />
    <line x1={700} y1={GR - 144} x2={700} y2={GR} stroke={LIME} strokeWidth={5} />
    {fig('robot', 540, pose({l: 6, hd: 8, uaL: 52 + 10 * Math.sin(f / 3), faL: 96 + 14 * Math.sin(f / 3), uaR: 48 - 10 * Math.sin(f / 3 + 1), faR: 92 + 14 * Math.cos(f / 3)}), 1, f, {s: 1.5})}
    {Array.from({length: 7}).map((_, i) => {
      const t = ((f + i * 14) % 100) / 100; const x = 520 + 190 * (hash(i) - 0.35) + 40 * Math.sin(t * 8 + i);
      return <T key={i} x={x} y={GR - 420 - t * 230} size={54 + (i % 3) * 14} col={i % 3 === 0 ? PK : LIME} op={Math.sin(t * Math.PI)}>{i % 2 ? '♪' : '♫'}</T>;
    })}
  </g>
);

// ---------- S2b: photos / video
const Fotos: React.FC<{f: number}> = ({f}) => {
  const fl = Math.max(0, 1 - ((f % 36) / 8));
  const frames = [0, 1, 2, 3];
  return (
    <g>
      <Ground />
      {fig('robot', 300, pose({l: 4, uaL: 96, faL: 100, uaR: 90, faR: 96}), 1, f, {s: 1.5})}
      <rect x={430} y={GR - 330} width={34} height={56} rx={6} fill={DK} stroke={PK} strokeWidth={4} />
      <circle cx={447} cy={GR - 305} r={7} fill={PK} opacity={0.5 + 0.5 * Math.sin(f / 3)} />
      <circle cx={460} cy={GR - 300} r={260} fill="#fff" opacity={fl * 0.28} />
      {frames.map((i) => {
        const t = clamp(((f - i * 22) % 120) / 90); const live = f >= i * 22;
        if (!live) return null;
        const x = 560 + (i % 2) * 230 + t * 40; const y = GR - 120 - t * 300 - Math.floor(i / 2) * 20;
        const isVid = i % 2 === 1;
        return (
          <g key={i} transform={`translate(${x},${y}) rotate(${(i - 1.5) * 5})`} opacity={Math.min(1, t * 6) * (1 - clamp((t - 0.8) * 5))}>
            <rect width={190} height={150} fill={DK} stroke={isVid ? PK : LIME} strokeWidth={5} />
            {isVid ? <path d="M70,40 L70,110 L130,75 Z" fill={PK} /> : <><circle cx={140} cy={46} r={14} fill={LIME} /><path d="M18,130 L70,60 L110,110 L135,85 L172,130 Z" fill={G} opacity={0.8} /></>}
          </g>
        );
      })}
      <T x={540} y={170} size={42} col={WH} op={0.9}>feito por IA</T>
    </g>
  );
};

// ---------- S2c: audience
const Audiencia: React.FC<{f: number}> = ({f}) => {
  const n = Math.floor(L(0, 1200, seg(f, 6, 90)));
  const label = n >= 1000 ? `${(n / 1000).toFixed(1).replace('.', ',')} mi` : `${n} mil`;
  const xs = [120, 290, 460, 630, 800, 970, 205, 375, 545, 715, 885];
  return (
    <g>
      <Ground />
      <rect x={300} y={140} width={480} height={170} rx={20} fill={DK} stroke={LIME} strokeWidth={5} />
      <path d="M345,185 L345,265 L405,225 Z" fill={LIME} />
      <T x={600} y={260} size={84} col={WH} bold>{label}</T>
      {xs.map((x, i) => {
        const row = i < 6 ? 0 : 1; const jump = Math.abs(Math.sin(f / 4 + i * 1.3)) * (row ? 10 : 16);
        return <g key={i}>{fig('person', x, pose({uaL: 128 + 10 * Math.sin(f / 3 + i), faL: 172, uaR: -128 - 10 * Math.cos(f / 3 + i), faR: -172}), 1, f, {s: row ? 0.95 : 1.2, y: GR - (row ? 60 : 0) - jump, col: row ? '#9DB02A' : LIME})}</g>;
      })}
      {Array.from({length: 8}).map((_, i) => {
        const t = ((f * 1.2 + i * 17) % 100) / 100; const x = 160 + hash(i) * 760 + 20 * Math.sin(t * 7 + i);
        return <T key={i} x={x} y={GR - 260 - t * 360} size={48} col={PK} op={Math.sin(t * Math.PI)}>♥</T>;
      })}
    </g>
  );
};

// ---------- S3: post-apocalyptic
const Pos: React.FC<{f: number}> = ({f}) => {
  const bs = [[40, 260], [150, 380], [250, 300], [330, 460], [430, 280], [560, 420], [660, 330], [760, 500], [860, 290], [960, 400]];
  const px = L(120, 940, seg(f, 0, 110));
  return (
    <g>
      <circle cx={540} cy={330} r={150} fill={LIME} opacity={0.9} />
      {Array.from({length: 9}).map((_, i) => <rect key={i} x={380} y={300 + i * 20} width={320} height={4 + i} fill="#05080A" />)}
      {bs.map(([x, h], i) => {
        const w = 90; const broke = hash(i + 4);
        const top = GR - h;
        return <polygon key={i} points={`${x},${GR} ${x},${top} ${x + w * 0.35},${top - 30 * broke} ${x + w * 0.55},${top + 20} ${x + w * 0.8},${top - 14 * broke} ${x + w},${top + 10} ${x + w},${GR}`} fill="#05110A" stroke={G} strokeWidth={3} />;
      })}
      {Array.from({length: 14}).map((_, i) => <circle key={i} cx={(hash(i) * 1080 + f * (1 + hash(i + 3))) % 1080} cy={GR - 20 - hash(i + 8) * 200} r={2 + hash(i) * 3} fill={LIME} opacity={0.4} />)}
      <Ground />
      {fig('person', px, walk(f * 0.4, true), 1, f, {s: 1.3})}
    </g>
  );
};

// ---------- S4: futuristic movies
const Filme: React.FC<{f: number}> = ({f}) => (
  <g>
    <Ground />
    <rect x={330} y={150} width={680} height={380} fill="#02080A" stroke={LIME} strokeWidth={6} />
    <clipPath id="scr"><rect x={336} y={156} width={668} height={368} /></clipPath>
    <g clipPath="url(#scr)">
      <rect x={336} y={156} width={668} height={368} fill="#07200F" opacity={0.7} />
      {[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const h = 90 + hash(i + 1) * 170; const x = 346 + i * 96 - ((f * 0.8) % 96) + 96;
        return <rect key={i} x={x} y={524 - h} width={70} height={h} fill="#05110A" stroke={G} strokeWidth={2} />;
      })}
      {[0, 1, 2].map((i) => {
        const x = ((f * 4 + i * 230) % 780) + 300; return <g key={i} transform={`translate(${x},${480})`}><rect x={-14} y={-60} width={28} height={36} fill={WH} /><rect x={-9} y={-50} width={18} height={6} fill={PK} /><rect x={-10} y={-24} width={20} height={24} fill={WH} opacity={0.8} /></g>;
      })}
      {Array.from({length: 23}).map((_, i) => <rect key={i} x={336} y={156 + i * 16} width={668} height={2} fill="#000" opacity={0.35} />)}
    </g>
    {fig('person', 190, seated(f), 1, f, {s: 1.7, y: GR})}
    <path d={`M${190 + 30},${GR - 190} l-9,-40 l60,0 l-9,40 z`} fill={DK} stroke={PK} strokeWidth={4} />
    {[0, 1, 2].map((i) => {
      const t = ((f + i * 12) % 36) / 36; return <circle key={i} cx={230 + 16 * i + 10 * Math.sin(t * 6)} cy={GR - 240 - t * 60} r={7} fill={WH} opacity={1 - t} />;
    })}
  </g>
);

// ---------- S5: "vai acontecer" glitch punch
const Vai: React.FC<{f: number}> = ({f}) => {
  const j = (hash(f) - 0.5) * 30;
  return (
    <g transform={`translate(${f % 4 < 2 ? j : 0},0)`}>
      <g transform="translate(540,430) scale(2.6)" stroke={WH} strokeWidth={5} fill={DK}>
        <line x1={0} y1={-120} x2={0} y2={-90} /><circle cx={0} cy={-126} r={10} fill={PK} stroke="none" />
        <rect x={-110} y={-90} width={220} height={180} rx={24} />
        <rect x={-80} y={-34} width={160} height={36} rx={10} fill={PK} stroke="none" opacity={f % 10 < 8 ? 1 : 0.3} />
        <line x1={-50} y1={52} x2={50} y2={52} />
      </g>
      {Array.from({length: 7}).map((_, i) => <rect key={i} x={hash(i + f) * 700} y={hash(i * 3 + f) * 880} width={200 + hash(i) * 400} height={6 + hash(i + 2) * 18} fill={i % 2 ? LIME : PK} opacity={0.55} />)}
    </g>
  );
};

// ---------- S6a: robot takes job (reuses option A timeline, sped up)
const Emprego: React.FC<{f: number; dur: number}> = ({f, dur}) => {
  const ff = Math.min(149, Math.floor((f * 150) / dur));
  const s = scene(ff);
  return (
    <g transform="translate(0,-115)">
      <Desk col="#14B85A" f={ff} robotSeated={s.robotSeated} sw={SW} />
      {s.personVisible ? <g transform={`translate(${s.px},${G0}) scale(${S0},${S0})`}><Figure p={s.pp} kind="person" col={LIME} fill={DK} eye={PK} sw={SW} f={ff} box={s.box} /></g> : null}
      {ff >= 18 ? <g transform={`translate(${s.rx},${G0}) scale(${s.robotSeated ? S0 : -S0},${S0})`}><Figure p={s.rpose} kind="robot" col={WH} fill={DK} eye={PK} sw={SW} f={ff} /></g> : null}
      {ff > 134 ? <T x={540} y={290} size={104} col={PK} bold>−1 EMPREGO</T> : null}
    </g>
  );
};

// ---------- S6b: robot policing
const Policia: React.FC<{f: number}> = ({f}) => {
  const sweep = Math.sin(f / 18);
  const ang = -8 + 18 * sweep;
  const targets = [660, 790, 920];
  return (
    <g>
      <Ground />
      <g transform={`translate(380,${GR - 215}) rotate(${ang})`}>
        <polygon points="0,0 700,-130 700,150" fill={LIME} opacity={0.16} />
        <polygon points="0,0 700,-130 700,150" fill="none" stroke={LIME} strokeWidth={2} opacity={0.5} />
      </g>
      {fig('robot', 300, pose({l: 3, uaL: 100, faL: 96, uaR: -4, faR: 8}), 1, f, {s: 1.55})}
      <g transform={`translate(${300 + 8},${GR - 320})`}><path d="M-34,0 L34,0 L26,-20 L-26,-20 Z" fill={DK} stroke={PK} strokeWidth={4} /><circle cx={0} cy={-34} r={9} fill={f % 16 < 8 ? PK : LIME} /></g>
      {targets.map((x, i) => {
        const hit = Math.abs((Math.atan2(-105, x - 380) * 180) / Math.PI - ang) < 7;
        return (
          <g key={i}>
            {fig('person', x, pose({uaL: 135, faL: 172, uaR: -135, faR: -172, taL: 4, taR: -4}), 1, f, {s: 1.15, col: hit ? PK : LIME})}
            {hit ? <T x={x} y={GR - 330} size={62} col={PK} bold>!</T> : null}
          </g>
        );
      })}
    </g>
  );
};

// ---------- S6c: robot security
const Seguranca: React.FC<{f: number}> = ({f}) => {
  const walkers = [0, 1, 2].map((i) => {
    const t0 = i * 36; const x = L(-60, 1140, clamp((f - t0) / 150));
    const stop = i === 2 ? Math.min(x, 640) : x;
    return {x: stop, i, blocked: i === 2 && x >= 640};
  });
  return (
    <g>
      <Ground />
      <g>
        <rect x={720} y={GR - 330} width={24} height={330} fill={DK} stroke={LIME} strokeWidth={5} />
        <rect x={900} y={GR - 330} width={24} height={330} fill={DK} stroke={LIME} strokeWidth={5} />
        <rect x={720} y={GR - 360} width={204} height={34} fill={DK} stroke={LIME} strokeWidth={5} />
        <circle cx={822} cy={GR - 343} r={10} fill={walkers[2].blocked ? PK : LIME} opacity={0.6 + 0.4 * Math.sin(f / 3)} />
      </g>
      {walkers.map(({x, i, blocked}) => {
        const wp = blocked ? pose({uaL: 90, faL: 95}) : walk(f * 0.4 + i, true);
        const ok = !blocked && x > 770 && x < 960;
        return <g key={i}>{fig('person', x, wp, 1, f, {s: 1.1, col: blocked ? PK : LIME})}{ok ? <T x={822} y={GR - 400} size={60} col={LIME} bold>✓</T> : null}{blocked ? <T x={x} y={GR - 300} size={60} col={PK} bold>✕</T> : null}</g>;
      })}
      {fig('robot', 470, pose({l: 2, uaL: 70, faL: 40, uaR: -10, faR: 5}), 1, f, {s: 1.6})}
      <g transform={`translate(${470 + 70},${GR - 180})`}>
        <path d="M0,-60 L50,-40 L50,20 Q50,60 0,80 Q-50,60 -50,20 L-50,-40 Z" fill={DK} stroke={WH} strokeWidth={5} />
        <rect x={-14} y={-6} width={28} height={24} fill={WH} /><path d="M-9,-6 v-10 a9,9 0 0 1 18,0 v10" fill="none" stroke={WH} strokeWidth={5} />
      </g>
    </g>
  );
};

export const CENAS: Record<string, React.FC<{f: number; dur: number}>> = {
  monolito: ({f}) => <Monolito f={f} />, musica: ({f}) => <Musica f={f} />, fotos: ({f}) => <Fotos f={f} />, audiencia: ({f}) => <Audiencia f={f} />,
  pos: ({f}) => <Pos f={f} />, filme: ({f}) => <Filme f={f} />, vai: ({f}) => <Vai f={f} />, emprego: Emprego, policia: ({f}) => <Policia f={f} />, seguranca: ({f}) => <Seguranca f={f} />,
};

export const CenaPanel: React.FC<{id: string; f: number; dur: number; gf: number}> = ({id, f, dur, gf}) => {
  const C = CENAS[id]; if (!C) return null;
  const inn = clamp(f / 8), out = clamp((dur - f) / 8);
  return (
    <svg width={1080} height={800} viewBox="0 100 1080 800" style={{position: 'absolute', left: 0, top: 0}}>
      <defs><filter id="glw" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
      <Rain f={gf} op={0.16} />
      <g filter="url(#glw)" opacity={Math.min(inn, out)}><C f={f} dur={dur} /></g>
    </svg>
  );
};
