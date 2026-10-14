// Cenas novas no MESMO rig de bonequinhos (Opcoes.tsx) para os assuntos dos vídeos da Natinha.
import React from 'react';
import {Figure, STAND, walk, seated, mix, hash, clamp, seg, WH, PK, DK, LIME} from './Opcoes';
import {CENAS as BASE} from './Cenas';
import {F} from './theme';

type Pose = Parameters<typeof Figure>[0]['p'];
const GR = 790, SW = 9;
const pose = (o: Partial<Pose>): Pose => ({...STAND, ...o});
const HOLD = {l: 6, hd: 20, uaL: 42, faL: 84, uaR: 40, faR: 88};
const fig = (kind: 'person' | 'robot', x: number, p: Pose, dir: number, f: number, o: {s?: number; col?: string; y?: number; op?: number} = {}) => {
  const s = o.s ?? 1.5;
  return (
    <g opacity={o.op ?? 1} transform={`translate(${x},${o.y ?? GR}) scale(${s * dir},${s})`}>
      <Figure p={p} kind={kind} col={o.col ?? (kind === 'person' ? LIME : WH)} fill={DK} eye={PK} sw={SW / (s > 1 ? 1 : s * 1.1)} f={f} />
    </g>
  );
};
const Ground = () => <line x1={0} x2={1080} y1={GR} y2={GR} stroke="#14B85A" strokeWidth={5} opacity={0.4} strokeLinecap="round" />;
const T: React.FC<{x: number; y: number; size: number; col?: string; anchor?: 'start' | 'middle' | 'end'; op?: number; children: React.ReactNode}> = ({x, y, size, col = LIME, anchor = 'middle', op = 1, children}) => (
  <text x={x} y={y} fontSize={size} fontFamily={F.mono} fontWeight={700} fill={col} textAnchor={anchor} opacity={op}>{children}</text>
);

// ---- "vazio": todo mundo no celular, ninguém se vê; VOCÊ parada no meio
const Vazio: React.FC<{f: number}> = ({f}) => {
  const W = [0, 1, 2, 3, 4, 5, 6].map((i) => {
    const sp = 2.5 + hash(i) * 2.5, dir = i % 2 ? 1 : -1, x0 = hash(i + 4) * 1500, k = (f * sp + x0) % 1500;
    return {i, dir, x: dir > 0 ? k - 200 : 1300 - k, s: 1.0 + hash(i + 8) * 0.35};
  });
  const pulse = 0.5 + 0.5 * Math.sin(f / 7);
  return (
    <g>
      <Ground />
      {W.map((w) => (
        <g key={w.i}>
          {fig('person', w.x, {...walk(f * 0.28 + w.i * 2, false), ...HOLD}, w.dir, f, {s: w.s, col: '#9EC9B0', op: 0.8})}
          <rect x={w.x + w.dir * 30 * w.s - 8} y={GR - 205 * w.s} width={16} height={26} rx={3} fill={WH} opacity={0.85} />
        </g>
      ))}
      <circle cx={540} cy={GR - 190} r={170 + 14 * pulse} fill="none" stroke={PK} strokeWidth={4} opacity={0.35 + 0.3 * pulse} />
      {fig('person', 540, pose({hd: 8}), 1, f, {s: 1.75})}
      <T x={540} y={GR + 70} size={46} col={PK} op={seg(f, 30, 50)}>VOCÊ</T>
    </g>
  );
};

// ---- "solidão": figura sentada sozinha; palavras surgem uma a uma
const Solidao: React.FC<{f: number; dur: number}> = ({f}) => {
  const itens = [['SOLIDÃO', 30], ['ANSIEDADE', 70], ['SEM PROPÓSITO', 110]] as const;
  const wob = Math.sin(f / 9) * 2;
  return (
    <g>
      <Ground />
      {fig('person', 300, seated(f), 1, f, {s: 1.9})}
      <rect x={338} y={GR - 175 + wob} width={20} height={32} rx={4} fill={WH} opacity={0.9} />
      {itens.map(([txt, t0], i) => {
        const k = seg(f, t0, t0 + 14);
        return <T key={txt} x={520} y={330 + i * 120 + (1 - k) * 24} size={i === 2 ? 52 : 62} anchor="start" col={i === 1 ? PK : LIME} op={k}>{txt}</T>;
      })}
    </g>
  );
};

// ---- "projeto": robô manipulando pessoas como marionetes
const Projeto: React.FC<{f: number}> = ({f}) => {
  const tilt = Math.sin(f / 12) * 4;
  const P: [number, number][] = [[150, 1], [340, -1], [760, 1], [940, -1]];
  return (
    <g>
      <Ground />
      <g transform={`rotate(${tilt} 540 340)`}>
        <line x1={110} y1={340} x2={970} y2={340} stroke={PK} strokeWidth={8} strokeLinecap="round" />
        {P.map(([x], i) => {
          const sw = Math.sin(f / 10 + i * 1.7) * 14;
          return (
            <g key={x}>
              <line x1={x} y1={340} x2={x + sw * 0.4} y2={470} stroke={WH} strokeWidth={3} opacity={0.8} />
              {fig('person', x + sw * 0.4, {...walk(f * 0.2 + i * 2, true), hd: 0}, P[i][1], f, {s: 0.9, y: 700 + Math.sin(f / 8 + i) * 8})}
            </g>
          );
        })}
      </g>
      {fig('robot', 540, pose({uaL: 150, faL: 175, uaR: -150, faR: -175, hipH: 112}), 1, f, {s: 1.5})}
    </g>
  );
};

// ---- "fabrica": o amor virando produto (corações na esteira → máquina → dinheiro)
const heart = 'M0,12 C-34,-22 -64,14 0,58 C64,14 34,-22 0,12 Z';
const Fabrica: React.FC<{f: number}> = ({f}) => (
  <g>
    <Ground />
    <line x1={20} x2={520} y1={GR - 90} y2={GR - 90} stroke={LIME} strokeWidth={6} opacity={0.7} strokeLinecap="round" />
    {Array.from({length: 24}).map((_, i) => <line key={i} x1={20 + ((i * 26 + f * 4) % 600)} x2={20 + ((i * 26 + f * 4) % 600)} y1={GR - 78} y2={GR - 64} stroke={LIME} strokeWidth={3} opacity={0.35} />)}
    {[0, 1, 2, 3].map((i) => {
      const x = ((f * 5 + i * 135) % 540);
      const op = x > 440 ? clamp((500 - x) / 60) : 1;
      return <g key={i} transform={`translate(${x + 20},${GR - 175}) scale(0.9)`} opacity={op}><path d={heart} fill={DK} stroke={PK} strokeWidth={8} strokeLinejoin="round" /></g>;
    })}
    <rect x={520} y={GR - 320} width={170} height={250} rx={14} fill={DK} stroke={WH} strokeWidth={6} />
    <rect x={545} y={GR - 270} width={120} height={26} rx={6} fill={PK} opacity={f % 24 < 18 ? 1 : 0.35} />
    <line x1={545} x2={665} y1={GR - 200} y2={GR - 200} stroke={WH} strokeWidth={4} opacity={0.7} />
    {[0, 1, 2].map((i) => {
      const t = ((f + i * 14) % 42) / 42;
      return <g key={i} opacity={1 - t}><circle cx={605 + (i - 1) * 46} cy={GR - 340 - t * 150} r={26} fill={DK} stroke={LIME} strokeWidth={5} /><T x={605 + (i - 1) * 46} y={GR - 330 - t * 150} size={30}>$</T></g>;
    })}
    {fig('robot', 790, pose({uaL: 40, faL: 70, uaR: -10, faR: 10}), -1, f, {s: 1.5})}
  </g>
);

export const CENAS: Record<string, React.FC<{f: number; dur: number}>> = {
  ...BASE,
  vazio: ({f}) => <Vazio f={f} />,
  solidao: Solidao,
  projeto: ({f}) => <Projeto f={f} />,
  fabrica: ({f}) => <Fabrica f={f} />,
};
