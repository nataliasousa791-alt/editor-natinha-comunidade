// Cena GERADA sob medida: a IA descreve (JSON) quem está na cena, o que fazem, objetos, fluxos e textos.
// Nada de cena pré-pronta: este motor só sabe desenhar peças (bonequinhos em poses, objetos neon, fluxos, textos).
import React from 'react';
import {Figure, STAND, walk, seated, carry, hash, clamp, seg, L, G, WH, PK, DK, LIME, GL} from './Opcoes';
import {F} from './theme';

const GR = 790;
const COL: Record<string, string> = {lime: LIME, rosa: PK, branco: WH, verde: G};
const num = (v: any, d: number) => (typeof v === 'number' && isFinite(v) ? v : d);
const X = (p: any) => 130 + (clamp(num(p, 50), 0, 100) / 100) * 820;
const Y = (p: any) => 170 + (clamp(num(p, 50), 0, 100) / 100) * 620;
const cor = (c: any, d: string) => COL[String(c)] || d;

const POSES: Record<string, (f: number, i: number) => any> = {
  parado: (f) => ({...STAND, hd: 2 * Math.sin(f / 14), hipH: 112 + Math.sin(f / 14)}),
  andar: (f, i) => walk(f * 0.4 + i, true),
  correr: (f, i) => walk(f * 0.75 + i, true),
  trabalhar: (f) => ({...STAND, l: 5, hd: 8, uaL: 52 + 10 * Math.sin(f / 3), faL: 96 + 14 * Math.sin(f / 3), uaR: 48 - 10 * Math.sin(f / 3 + 1), faR: 92 + 14 * Math.cos(f / 3)}),
  sentado: (f) => seated(f),
  comemorar: (f) => ({...STAND, uaL: 128 + 10 * Math.sin(f / 3), faL: 172, uaR: -128 - 10 * Math.cos(f / 3), faR: -172}),
  apontar: () => ({...STAND, l: 3, uaL: 100, faL: 96, uaR: -6, faR: 8, hd: 4}),
  cabisbaixo: (f) => ({...STAND, l: 10, hd: 24, uaL: 4, faL: 10, uaR: -4, faR: 6, hipH: 108 + Math.sin(f / 18)}),
  carregar: () => carry,
  pedir: (f) => ({...STAND, uaL: 70 + 8 * Math.sin(f / 5), faL: 120, uaR: -4, faR: 8, hd: 6}),
};

const fig = (kind: 'person' | 'robot', x: number, y: number, p: any, dir: number, f: number, s: number, col: string, box = 0) => (
  <g transform={`translate(${x},${y}) scale(${s * dir},${s})`}>
    <Figure p={p} kind={kind} col={col} fill={DK} eye={PK} sw={9 / (s > 1 ? 1 : s * 1.1)} f={f} box={box} />
  </g>
);

// ---- objetos neon (cabem em ~ -60..60)
const st = (c: string, w = 5) => ({fill: DK, stroke: c, strokeWidth: w, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const});
const GLIFOS: Record<string, (c: string, f: number) => React.ReactNode> = {
  casa: (c) => <g><path d="M-55,5 L0,-50 L55,5 Z" {...st(c)} /><rect x={-40} y={5} width={80} height={55} {...st(c)} /><rect x={-10} y={25} width={22} height={35} {...st(c, 4)} /></g>,
  moeda: (c) => <g><circle r={44} {...st(c)} /><circle r={30} fill="none" stroke={c} strokeWidth={3} opacity={0.6} /><text y={16} fontSize={48} fontFamily={F.mono} fontWeight={700} fill={c} textAnchor="middle">$</text></g>,
  nota: (c) => <g><rect x={-62} y={-34} width={124} height={68} rx={8} {...st(c)} /><circle r={18} fill="none" stroke={c} strokeWidth={4} /><text y={9} fontSize={26} fontFamily={F.mono} fontWeight={700} fill={c} textAnchor="middle">$</text></g>,
  coracao: (c) => <path d="M0,42 C-70,-8 -40,-58 0,-24 C40,-58 70,-8 0,42 Z" {...st(c)} />,
  celular: (c, f) => <g><rect x={-28} y={-54} width={56} height={108} rx={10} {...st(c)} /><rect x={-20} y={-40} width={40} height={74} fill={c} opacity={0.12 + 0.1 * Math.sin(f / 6)} /><circle cy={44} r={4} fill={c} /></g>,
  relogio: (c, f) => <g><circle r={50} {...st(c)} /><line x1={0} y1={0} x2={0} y2={-34} stroke={c} strokeWidth={5} strokeLinecap="round" transform={`rotate(${f * 6})`} /><line x1={0} y1={0} x2={24} y2={0} stroke={c} strokeWidth={5} strokeLinecap="round" transform={`rotate(${f * 0.5})`} />{[0, 90, 180, 270].map((a) => <line key={a} x1={0} y1={-44} x2={0} y2={-38} stroke={c} strokeWidth={3} transform={`rotate(${a})`} />)}</g>,
  predio: (c) => <g><rect x={-34} y={-62} width={68} height={124} {...st(c)} />{[0, 1, 2, 3].map((r) => [0, 1].map((k) => <rect key={`${r}${k}`} x={-22 + k * 24} y={-48 + r * 26} width={14} height={14} fill={c} opacity={0.5} />))}</g>,
  caixa: (c) => <g><rect x={-46} y={-36} width={92} height={72} {...st(c)} /><line x1={-46} y1={-12} x2={46} y2={-12} stroke={c} strokeWidth={4} /><line x1={0} y1={-36} x2={0} y2={-12} stroke={c} strokeWidth={4} /></g>,
  cofre: (c) => <g><rect x={-52} y={-48} width={104} height={96} rx={8} {...st(c)} /><circle r={22} fill="none" stroke={c} strokeWidth={5} /><line x1={0} y1={0} x2={0} y2={-16} stroke={c} strokeWidth={4} /><line x1={-30} y1={48} x2={-30} y2={60} stroke={c} strokeWidth={6} /><line x1={30} y1={48} x2={30} y2={60} stroke={c} strokeWidth={6} /></g>,
  grafico: (c, f) => <g><line x1={-56} y1={50} x2={56} y2={50} stroke={c} strokeWidth={4} /><line x1={-56} y1={50} x2={-56} y2={-52} stroke={c} strokeWidth={4} />{[0, 1, 2, 3].map((i) => { const h = (24 + i * 20) * (0.75 + 0.25 * Math.sin(f / 8 + i)); return <rect key={i} x={-44 + i * 26} y={50 - h} width={16} height={h} fill={c} opacity={0.75} />; })}</g>,
  documento: (c) => <g><path d="M-36,-56 L20,-56 L40,-36 L40,56 L-36,56 Z" {...st(c)} />{[-26, -10, 6, 22].map((y) => <line key={y} x1={-22} y1={y} x2={26} y2={y} stroke={c} strokeWidth={3} opacity={0.7} />)}</g>,
  carrinho: (c) => <g><path d="M-60,-40 L-40,-40 L-24,24 L38,24 L50,-24 L-34,-24" {...st(c, 5)} fill="none" /><circle cx={-14} cy={44} r={9} {...st(c, 4)} /><circle cx={30} cy={44} r={9} {...st(c, 4)} /></g>,
  cadeado: (c) => <g><path d="M-22,-8 v-20 a22,22 0 0 1 44,0 v20" fill="none" stroke={c} strokeWidth={6} strokeLinecap="round" /><rect x={-36} y={-8} width={72} height={58} rx={8} {...st(c)} /><circle cy={20} r={7} fill={c} /></g>,
  engrenagem: (c, f) => <g transform={`rotate(${f * 1.2})`}><circle r={30} {...st(c)} />{Array.from({length: 8}).map((_, i) => <rect key={i} x={-8} y={-50} width={16} height={20} {...st(c, 4)} transform={`rotate(${i * 45})`} />)}<circle r={10} fill="none" stroke={c} strokeWidth={4} /></g>,
  olho: (c, f) => <g><path d="M-62,0 Q0,-56 62,0 Q0,56 -62,0 Z" {...st(c)} /><circle r={20} fill="none" stroke={c} strokeWidth={5} /><circle cx={4 * Math.sin(f / 20)} r={8} fill={c} /></g>,
  balanca: (c) => <g><line y1={-56} y2={50} stroke={c} strokeWidth={5} /><line x1={-54} y1={-40} x2={54} y2={-40} stroke={c} strokeWidth={5} /><path d="M-54,-40 l-20,44 h40 z M54,-40 l-20,44 h40 z" {...st(c, 4)} /><line x1={-30} y1={52} x2={30} y2={52} stroke={c} strokeWidth={6} /></g>,
  lampada: (c, f) => <g><path d="M-26,-6 a34,34 0 1 1 52,0 q-10,14 -10,28 h-32 q0,-14 -10,-28 Z" {...st(c)} opacity={0.8 + 0.2 * Math.sin(f / 5)} /><line x1={-14} y1={34} x2={14} y2={34} stroke={c} strokeWidth={5} /><line x1={-10} y1={46} x2={10} y2={46} stroke={c} strokeWidth={5} /></g>,
  seta: (c) => <g><line x1={-52} y1={0} x2={44} y2={0} stroke={c} strokeWidth={8} strokeLinecap="round" /><path d="M20,-26 L52,0 L20,26" fill="none" stroke={c} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" /></g>,
  estrela: (c) => <path d="M0,-50 L14,-16 L50,-14 L22,8 L32,44 L0,24 L-32,44 L-22,8 L-50,-14 L-14,-16 Z" {...st(c)} />,
  sacola: (c) => <g><path d="M-40,-24 h80 l-8,76 h-64 Z" {...st(c)} /><path d="M-18,-24 v-14 a18,18 0 0 1 36,0 v14" fill="none" stroke={c} strokeWidth={5} /></g>,
};
export const TIPOS_OBJ = Object.keys(GLIFOS);

const fmt = (n: number) => Math.round(n).toLocaleString('pt-BR');

export const CenaGen: React.FC<{spec: any; f: number; dur: number}> = ({spec, f, dur}) => {
  const sp = spec || {};
  const prog = (ini: number, fim: number) => seg(f / Math.max(1, dur), ini, fim);
  const atores: any[] = Array.isArray(sp.atores) ? sp.atores.slice(0, 5) : [];
  const objs: any[] = Array.isArray(sp.objetos) ? sp.objetos.slice(0, 8) : [];
  const fluxos: any[] = Array.isArray(sp.fluxos) ? sp.fluxos.slice(0, 2) : [];
  const linhas: any[] = Array.isArray(sp.linhas) ? sp.linhas.slice(0, 6) : [];
  const textos: any[] = Array.isArray(sp.textos) ? sp.textos.slice(0, 3) : [];
  return (
    <g>
      <line x1={0} x2={1080} y1={GR} y2={GR} stroke="#14B85A" strokeWidth={5} opacity={0.4} strokeLinecap="round" />
      {linhas.map((l, i) => {
        const a = prog(num(l.quando, 0.1), num(l.quando, 0.1) + 0.2);
        const x1 = X(l.de?.[0]), y1 = Y(l.de?.[1]), x2 = X(l.para?.[0]), y2 = Y(l.para?.[1]);
        return <line key={`l${i}`} x1={x1} y1={y1} x2={x1 + (x2 - x1) * a} y2={y1 + (y2 - y1) * a} stroke={cor(l.cor, G)} strokeWidth={4} opacity={0.75} strokeLinecap="round" strokeDasharray={l.tracejada ? '12 10' : undefined} />;
      })}
      {objs.map((o, i) => {
        const g = GLIFOS[o.tipo]; if (!g) return null;
        const q = num(o.quando, 0), pop = prog(q, q + 0.12); if (pop <= 0) return null;
        const mv = o.x2 != null ? prog(num(o.mov_ini, 0.2), num(o.mov_fim, 0.8)) : 0;
        const x = L(X(o.x), X(num(o.x2, o.x)), mv), y0 = L(Y(o.y), Y(num(o.y2, o.y)), mv);
        const an = o.anim; let dy = 0, rot = 0, sc = 1, op = 1;
        if (an === 'flutuar') dy = 10 * Math.sin(f / 12 + i);
        if (an === 'pulsar') sc = 1 + 0.08 * Math.sin(f / 5 + i);
        if (an === 'girar') rot = f * 2;
        if (an === 'tremer') { dy = 4 * Math.sin(f * 1.7 + i); rot = 3 * Math.sin(f * 1.3); }
        if (an === 'subir') { const t = ((f + i * 20) % 90) / 90; dy = -t * 140; op = Math.sin(t * Math.PI); }
        if (an === 'sumir') op = 1 - prog(num(o.sumir, 0.7), num(o.sumir, 0.7) + 0.15);
        const s = clamp(num(o.tam, 1), 0.5, 2.6) * (0.4 + 0.6 * pop) * sc;
        const c = cor(o.cor, LIME);
        return (
          <g key={`o${i}`} transform={`translate(${x},${y0 + dy}) rotate(${rot}) scale(${s})`} opacity={pop * op}>
            {g(c, f)}
            {o.rotulo ? <text y={86} fontSize={30} fontFamily={F.mono} fontWeight={700} fill={WH} textAnchor="middle" transform={`scale(${1 / s})`}>{String(o.rotulo).slice(0, 18)}</text> : null}
          </g>
        );
      })}
      {fluxos.map((fl, k) => {
        const g = GLIFOS[fl.item] || GLIFOS.moeda; const n = clamp(Math.round(num(fl.n, 4)), 2, 6);
        const c = cor(fl.cor, LIME);
        return (
          <g key={`f${k}`}>
            {Array.from({length: n}).map((_, i) => {
              const t = ((f * 1.3 + (i * 100) / n) % 100) / 100;
              const x = L(X(fl.de?.[0]), X(fl.para?.[0]), t), y = L(Y(fl.de?.[1]), Y(fl.para?.[1]), t) - 50 * Math.sin(t * Math.PI);
              return <g key={i} transform={`translate(${x},${y}) scale(0.42)`} opacity={Math.min(1, t * 6, (1 - t) * 6)}>{g(c, f)}</g>;
            })}
          </g>
        );
      })}
      {atores.map((a, i) => {
        const kind = a.tipo === 'robo' ? 'robot' : 'person';
        const mv = a.x2 != null ? prog(num(a.mov_ini, 0.1), num(a.mov_fim, 0.8)) : 0;
        const x = L(X(a.x), X(num(a.x2, a.x)), mv);
        const andando = a.x2 != null && mv > 0 && mv < 1;
        const acao = andando && (a.acao === 'parado' || !a.acao) ? 'andar' : a.acao;
        const pf = POSES[acao] || POSES.parado;
        const dir = a.x2 != null && num(a.x2, 0) < num(a.x, 0) ? -1 : a.olhar === 'esq' ? -1 : 1;
        const q = num(a.quando, 0), ap = prog(q, q + 0.08); if (ap <= 0) return null;
        const col = a.cor ? cor(a.cor, kind === 'robot' ? WH : LIME) : kind === 'robot' ? WH : LIME;
        const sz = clamp(num(a.tam, atores.length > 2 ? 1.15 : 1.4), 0.8, 1.8);
        return <g key={`a${i}`} opacity={ap}>{fig(kind, x, GR, pf(f, i), dir, f, sz, col, acao === 'carregar' ? 1 : 0)}</g>;
      })}
      {textos.map((t, i) => {
        const q = num(t.quando, 0.1), a = prog(q, q + 0.1); if (a <= 0) return null;
        let s = String(t.t ?? '').slice(0, 26);
        if (t.de != null && t.para != null) s = s.replace('{n}', fmt(L(num(t.de, 0), num(t.para, 0), prog(q, q + 0.5))));
        const size = clamp(num(t.tam, 56), 28, 100);
        const max = 820 / Math.max(1, s.length * 0.62);
        return <text key={`t${i}`} x={X(t.x)} y={Y(t.y) + (1 - a) * 18} fontSize={Math.min(size, max)} fontFamily={F.mono} fontWeight={700} fill={cor(t.cor, WH)} textAnchor="middle" opacity={a}>{s}</text>;
      })}
      {sp.matriz ? Array.from({length: 8}).map((_, i) => <text key={`m${i}`} x={140 + hash(i) * 800} y={170 + ((f * 3 + i * 97) % 600)} fontSize={22} fontFamily={F.mono} fill={G} opacity={0.35}>{GL[Math.floor(hash(i + f / 6) * 40) % GL.length]}</text>) : null}
    </g>
  );
};
