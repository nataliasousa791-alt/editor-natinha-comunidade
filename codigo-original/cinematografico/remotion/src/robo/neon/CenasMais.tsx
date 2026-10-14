// Mais cenas no mesmo rig: tempo, dinheiro/salário, hierarquia, herança, celular. CENAS_TODAS = base + novas.
import React from 'react';
import {Figure, STAND, walk, seated, hash, clamp, seg, WH, PK, DK, LIME} from './Opcoes';
import {CENAS} from './CenasNatinha';
import {F} from './theme';

type Pose = Parameters<typeof Figure>[0]['p'];
const GR = 790, SW = 9;
const pose = (o: Partial<Pose>): Pose => ({...STAND, ...o});
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
const Coin: React.FC<{x: number; y: number; r?: number; op?: number}> = ({x, y, r = 24, op = 1}) => (
  <g opacity={op}><circle cx={x} cy={y} r={r} fill={DK} stroke={LIME} strokeWidth={5} /><T x={x} y={y + r * 0.36} size={r * 1.1}>$</T></g>
);

// tempo: pessoa trabalhando, relógio girando rápido
const Tempo: React.FC<{f: number}> = ({f}) => {
  const a = (f * 7) % 360, b = (f * 7) / 12;
  return (
    <g>
      <Ground />
      {fig('person', 290, seated(f), 1, f, {s: 1.7})}
      <rect x={150} y={GR - 150} width={200} height={14} fill={DK} stroke={WH} strokeWidth={4} />
      <g transform="translate(700,430)">
        <circle r={190} fill={DK} stroke={LIME} strokeWidth={8} />
        {Array.from({length: 12}).map((_, i) => <line key={i} x1={0} y1={-170} x2={0} y2={-150} stroke={LIME} strokeWidth={6} transform={`rotate(${i * 30})`} />)}
        <line x1={0} y1={0} x2={0} y2={-150} stroke={WH} strokeWidth={7} strokeLinecap="round" transform={`rotate(${a})`} />
        <line x1={0} y1={0} x2={0} y2={-100} stroke={PK} strokeWidth={10} strokeLinecap="round" transform={`rotate(${b})`} />
        <circle r={12} fill={PK} />
      </g>
      {[0, 1, 2].map((i) => { const t = ((f + i * 20) % 60) / 60; return <Coin key={i} x={380 + t * 220} y={GR - 260 - Math.sin(t * Math.PI) * 120} r={20} op={1 - t * 0.6} />; })}
    </g>
  );
};

// dinheiro: o salário entra e se divide em contas
const Dinheiro: React.FC<{f: number}> = ({f}) => {
  const box = [['ALUGUEL', 330], ['MERCADO', 500], ['CONTAS', 670]] as const;
  return (
    <g>
      <Ground />
      {fig('person', 230, pose({uaL: 60, faL: 100}), 1, f, {s: 1.5})}
      <T x={230} y={GR + 56} size={34} col={PK}>SALÁRIO</T>
      {box.map(([nome, y], i) => {
        const fill = clamp(((f * 0.7 + i * 25) % 90) / 90);
        return (
          <g key={nome}>
            <rect x={570} y={y - 62} width={380} height={104} rx={14} fill={DK} stroke={WH} strokeWidth={5} />
            <rect x={582} y={y - 50} width={356 * (1 - fill * 0.9)} height={80} rx={8} fill={LIME} opacity={0.28} />
            <T x={760} y={y + 8} size={40} col={WH}>{nome}</T>
          </g>
        );
      })}
      {box.map(([, y], i) => [0, 1, 2].map((k) => {
        const t = ((f * 0.035 + i * 0.31 + k * 0.33) % 1);
        return <Coin key={`${i}${k}`} x={330 + t * 240} y={520 + (y - 520) * t - Math.sin(t * Math.PI) * 60} r={20} op={1 - t * t} />;
      }))}
    </g>
  );
};

// hierarquia: robô/dono no topo, pessoas na base
const Piramide: React.FC<{f: number}> = ({f}) => {
  const niv = [[540, 150, 1], [540, 330, 2], [540, 510, 3], [540, 690, 5]] as const;
  return (
    <g>
      {niv.map(([cx, y, n], i) => (
        <rect key={i} x={cx - 90 - i * 85} y={GR - 90 - (3 - i) * 160 + 160 * 0} width={180 + i * 170} height={150} rx={10} fill={DK} stroke={i === 0 ? PK : LIME} strokeWidth={5} opacity={0.9}
          transform={`translate(0,${-(3 - i) * 0})`} />
      ))}
      {fig('robot', 540, pose({}), 1, f, {s: 0.85, y: GR - 90 - 3 * 160 - 6 + 0})}
      {[0, 1].map((k) => fig('person', 540 + (k ? 70 : -70), walk(f * 0.1 + k, false), 1, f, {s: 0.62, y: GR - 90 - 2 * 160 + 16}))}
      {[0, 1, 2].map((k) => fig('person', 540 + (k - 1) * 120, pose({uaL: 40, faL: 80}), 1, f, {s: 0.62, y: GR - 90 - 160 + 16}))}
      {[0, 1, 2, 3, 4].map((k) => fig('person', 540 + (k - 2) * 150, pose({hd: 12}), 1, f, {s: 0.62, y: GR - 74, op: 0.9}))}
      <T x={830} y={250} size={34} col={PK} op={seg(f, 10, 30)}>QUEM FICA NO TOPO</T>
      {[0, 1, 2].map((i) => { const t = ((f + i * 22) % 66) / 66; return <Coin key={i} x={760 + i * 30} y={GR - 100 - t * 450} r={16} op={t < 0.8 ? 1 : (1 - t) * 5} />; })}
    </g>
  );
};

// herança: a casa/patrimônio passa de geração em geração
const Heranca: React.FC<{f: number}> = ({f}) => {
  const k = (f % 150) / 150;
  const xs = [240, 540, 840], ss = [1.75, 1.45, 1.05];
  const pos = k < 0.5 ? 0 : 1, kk = k < 0.5 ? seg(k * 150, 20, 70) : seg((k - 0.5) * 150, 20, 70);
  const hx = xs[pos] + (xs[pos + 1] - xs[pos]) * kk, hy = GR - 520 - Math.sin(kk * Math.PI) * 90;
  return (
    <g>
      <Ground />
      {xs.map((x, i) => fig('person', x, pose({hd: i === 2 ? 0 : 6}), 1, f, {s: ss[i]}))}
      <g transform={`translate(${hx},${hy})`}>
        <path d="M-50,10 L0,-40 L50,10 L38,10 L38,52 L-38,52 L-38,10 Z" fill={DK} stroke={PK} strokeWidth={7} strokeLinejoin="round" />
        <rect x={-10} y={22} width={20} height={30} fill={LIME} opacity={0.8} />
      </g>
      {['GERAÇÃO 1', 'GERAÇÃO 2', 'GERAÇÃO 3'].map((t, i) => <T key={t} x={xs[i]} y={GR + 52} size={30} col={WH}>{t}</T>)}
    </g>
  );
};

// celular: pessoa rolando perfis; corações e cartões passando
const Celular: React.FC<{f: number}> = ({f}) => (
  <g>
    <Ground />
    {fig('person', 230, {...walk(f * 0.2, false), l: 6, hd: 22, uaL: 42, faL: 84, uaR: 40, faR: 88}, 1, f, {s: 1.7})}
    <rect x={296} y={GR - 305} width={26} height={44} rx={5} fill={WH} />
    {[0, 1, 2].map((i) => {
      const t = ((f * 0.02 + i * 0.34) % 1), x = 780 - t * 380;
      return (
        <g key={i} opacity={clamp(1 - Math.abs(t - 0.5) * 2.2)}>
          <rect x={x - 130} y={300 + i * 8} width={260} height={400} rx={22} fill={DK} stroke={LIME} strokeWidth={6} />
          <circle cx={x} cy={420 + i * 8} r={58} fill="none" stroke={WH} strokeWidth={6} />
          <line x1={x - 80} x2={x + 80} y1={560 + i * 8} y2={560 + i * 8} stroke={WH} strokeWidth={6} strokeLinecap="round" />
          <line x1={x - 50} x2={x + 50} y1={600 + i * 8} y2={600 + i * 8} stroke={WH} strokeWidth={5} opacity={0.6} strokeLinecap="round" />
        </g>
      );
    })}
    {[0, 1, 2, 3].map((i) => { const t = ((f + i * 16) % 64) / 64; return <path key={i} d="M0,6 C-18,-12 -34,6 0,32 C34,6 18,-12 0,6 Z" transform={`translate(${340 + i * 40},${GR - 330 - t * 160}) scale(0.7)`} fill={PK} opacity={1 - t} />; })}
  </g>
);

export const CENAS_TODAS: Record<string, React.FC<{f: number; dur: number}>> = {
  ...CENAS,
  tempo: ({f}) => <Tempo f={f} />,
  dinheiro: ({f}) => <Dinheiro f={f} />,
  piramide: ({f}) => <Piramide f={f} />,
  heranca: ({f}) => <Heranca f={f} />,
  celular: ({f}) => <Celular f={f} />,
};

// catálogo para a IA escolher (nome → quando usar)
export const CATALOGO: Record<string, string> = {
  vazio: 'multidão no celular, ninguém se vê; solidão urbana, desconexão, pessoas ocupadas',
  solidao: 'pessoa sozinha sentada; solidão, ansiedade, falta de propósito',
  projeto: 'robô manipulando pessoas como marionetes; sistema controlando, manipulação, projeto',
  fabrica: 'esteira transformando corações em dinheiro; industrialização, lucro, mercantilização',
  tempo: 'pessoa trabalhando e relógio girando; tempo, horas, jornada',
  dinheiro: 'salário dividido em aluguel, mercado e contas; renda, despesas, custo de vida',
  piramide: 'pirâmide social com robô/dono no topo; poder, hierarquia, desigualdade, concentração',
  heranca: 'casa passando de geração em geração; herança, patrimônio, famílias ricas',
  celular: 'pessoa rolando perfis e corações; redes sociais, aplicativos, relacionamentos online',
  emprego: 'robô tomando o lugar de uma pessoa; automação, perder emprego, IA no trabalho',
  policia: 'robô vigiando pessoas; vigilância, controle',
  seguranca: 'robô guardando cofre; segurança, proteção, dados',
  monolito: 'monolito surgindo; tecnologia nova, algo grande chegando',
  musica: 'música/arte feita por IA',
  filme: 'cinema, ficção científica',
  pos: 'mundo pós-apocalíptico',
  vai: 'glitch de impacto: frase de choque curta (use só 1x, com modo over)',
};
