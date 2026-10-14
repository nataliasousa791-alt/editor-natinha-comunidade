import React from 'react';
import {AbsoluteFill, useCurrentFrame, interpolate} from 'remotion';
import {C, F} from './theme';

export type Opt = 'A' | 'B' | 'C';
export const G = '#19FF7A', WH = '#EAFFF4', PK = '#FF3D81', DK = '#04090A';
export const LIME = '#E8FC3B';
export const GL = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾅﾆﾇﾈﾉ0123456789ABCDEF<>/{}=+*';
export const hash = (n: number) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
export const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
export const ease = (t: number) => t * t * (3 - 2 * t);
export const seg = (f: number, a: number, b: number) => ease(clamp((f - a) / (b - a)));
export const L = (a: number, b: number, t: number) => a + (b - a) * t;

// ---------------- rig
type Pose = {hipH: number; l: number; hd: number; uaL: number; faL: number; uaR: number; faR: number; taL: number; saL: number; taR: number; saR: number};
export const STAND: Pose = {hipH: 112, l: 0, hd: 0, uaL: 8, faL: 20, uaR: -8, faR: 10, taL: 0, saL: 0, taR: 0, saR: 0};
export const walk = (ph: number, arms = true): Pose => {
  const s = Math.sin(ph), c = Math.cos(ph);
  return {hipH: 110 + 3 * Math.abs(c), l: 4, hd: 0, uaL: arms ? -26 * s : 8, faL: arms ? -26 * s + 18 : 20, uaR: arms ? 26 * s : -8, faR: arms ? 26 * s + 18 : 10, taL: 30 * s, saL: 30 * s - 26 * Math.max(0, c), taR: -30 * s, saR: -30 * s - 26 * Math.max(0, -c)};
};
export const seated = (f: number): Pose => {
  const k = Math.sin(f * 1.7);
  return {hipH: 60, l: 6, hd: 6, uaL: 38, faL: 78 + 6 * k, uaR: 34, faR: 82 - 6 * k, taL: 84, saL: 2, taR: 80, saR: -2};
};
export const carry: Pose = {hipH: 112, l: 8, hd: 26, uaL: 42, faL: 84, uaR: 40, faR: 88, taL: 0, saL: 0, taR: 0, saR: 0};
export const mix = (a: Pose, b: Pose, t: number): Pose => { const o: any = {}; (Object.keys(a) as (keyof Pose)[]).forEach((k) => (o[k] = L(a[k], b[k], t))); return o; };
const P = (o: [number, number], a: number, len: number): [number, number] => [o[0] + len * Math.sin((a * Math.PI) / 180), o[1] + len * Math.cos((a * Math.PI) / 180)];
const limb = (o: [number, number], a1: number, l1: number, a2: number, l2: number) => { const m = P(o, a1, l1); const e = P(m, a2, l2); return `M${o[0]},${o[1]} L${m[0]},${m[1]} L${e[0]},${e[1]}`; };

export const body = (p: Pose) => {
  const hip: [number, number] = [0, -p.hipH];
  const neck: [number, number] = [95 * Math.sin((p.l * Math.PI) / 180), hip[1] - 95 * Math.cos((p.l * Math.PI) / 180)];
  const sh: [number, number] = [hip[0] + 0.88 * (neck[0] - hip[0]), hip[1] + 0.88 * (neck[1] - hip[1])];
  const ang = ((p.l + p.hd) * Math.PI) / 180;
  const head: [number, number] = [neck[0] + 32 * Math.sin(ang), neck[1] - 32 * Math.cos(ang)];
  return {hip, neck, sh, head, ang: p.l + p.hd,
    armL: limb(sh, p.uaL, 46, p.faL, 44), armR: limb(sh, p.uaR, 46, p.faR, 44),
    legL: limb(hip, p.taL, 56, p.saL, 56), legR: limb(hip, p.taR, 56, p.saR, 56),
    torso: `M${hip[0]},${hip[1]} L${neck[0]},${neck[1]}`};
};

// ---------------- figure renderers
export const Glow = ({id, r = 5}: {id: string; r?: number}) => (
  <filter id={id} x="-30%" y="-30%" width="160%" height="160%">
    <feGaussianBlur stdDeviation={r} result="b" />
    <feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
  </filter>
);

const Head: React.FC<{kind: 'person' | 'robot'; b: ReturnType<typeof body>; col: string; sw: number; fill: string; eye: string; f: number; solid?: boolean}> = ({kind, b, col, sw, fill, eye, f, solid}) => {
  const [hx, hy] = b.head;
  if (kind === 'person') return <circle cx={hx} cy={hy} r={27} fill={solid ? col : fill} stroke={col} strokeWidth={sw} />;
  const blink = f % 70 > 66 ? 0.2 : 1;
  return (
    <g transform={`translate(${hx},${hy}) rotate(${b.ang})`}>
      <line x1={0} y1={-26} x2={0} y2={-48} stroke={col} strokeWidth={sw * 0.7} strokeLinecap="round" />
      <circle cx={0} cy={-52} r={6} fill={eye} />
      <rect x={-31} y={-26} width={62} height={52} rx={10} fill={solid ? col : fill} stroke={col} strokeWidth={sw} />
      <rect x={-21} y={-10} width={42} height={12} rx={4} fill={eye} opacity={blink} />
      <line x1={-14} y1={14} x2={14} y2={14} stroke={solid ? DK : col} strokeWidth={sw * 0.5} strokeLinecap="round" />
    </g>
  );
};

export const Figure: React.FC<{p: Pose; kind: 'person' | 'robot'; col: string; fill: string; eye: string; sw: number; f: number; box?: number; solid?: boolean}> = ({p, kind, col, fill, eye, sw, f, box = 0, solid}) => {
  const b = body(p);
  const torsoW = kind === 'robot' ? sw * (solid ? 2.2 : 3.2) : sw;
  return (
    <g strokeLinecap="round" strokeLinejoin="round" fill="none">
      <path d={b.legR} stroke={col} strokeWidth={sw} opacity={0.65} />
      <path d={b.armR} stroke={col} strokeWidth={sw} opacity={0.65} />
      <path d={b.torso} stroke={col} strokeWidth={torsoW} />
      <path d={b.legL} stroke={col} strokeWidth={sw} />
      <Head kind={kind} b={b} col={col} sw={sw} fill={fill} eye={eye} f={f} solid={solid} />
      <path d={b.armL} stroke={col} strokeWidth={sw} />
      {box > 0 ? (
        <g opacity={box} transform={`translate(${b.sh[0] + 52},${b.sh[1] + 62})`}>
          <rect x={-34} y={-30} width={68} height={60} fill={fill} stroke={col} strokeWidth={sw * 0.8} />
          <line x1={-34} y1={-8} x2={34} y2={-8} stroke={col} strokeWidth={sw * 0.5} />
        </g>
      ) : null}
    </g>
  );
};

// ---------------- scene timeline
export const GROUND = 905, S = 1.62, DESK_X = 540;
export const scene = (f: number) => {
  // person
  const sitT = 1 - seg(f, 66, 84);
  const leave = seg(f, 88, 140);
  const px = L(380, -260, leave);
  const phase = f * 0.42;
  let pp: Pose;
  if (f < 66) pp = seated(f);
  else if (f < 88) pp = mix(seated(f), mix(STAND, carry, seg(f, 74, 88)), seg(f, 66, 82));
  else pp = mix(carry, walk(phase, false), 0.55 + 0.45 * Math.sin(phase) * 0 + 0.3);
  if (f >= 88) pp = {...mix(carry, walk(phase, false), 0.5), l: 9, hd: 28, uaL: 42, faL: 84, uaR: 40, faR: 88};
  const box = seg(f, 78, 86);
  // robot
  const arrive = seg(f, 18, 74);
  const slide = seg(f, 104, 134);
  const rx = f < 104 ? L(1380, 700, arrive) : L(700, 380, slide);
  const walking = (f > 18 && f < 76) || (f > 104 && f < 136);
  const rp = f < 104 ? (f < 76 ? walk(f * 0.45) : {...STAND, uaL: 20, faL: 60}) : f < 136 ? walk(f * 0.45) : mix(walk(f * 0.45), seated(f), seg(f, 134, 146));
  const rpose: Pose = f < 18 ? STAND : rp;
  return {px, pp, box, rx, rpose, personVisible: px > -200, robotSeated: f > 138, walking};
};

export const Rain: React.FC<{f: number; op: number}> = ({f, op}) => (
  <g fontFamily={F.mono} fontSize={30} opacity={op}>
    {Array.from({length: 27}).map((_, i) => {
      const sp = 5 + Math.floor(hash(i) * 6); const off = hash(i + 9) * 1400;
      const head = ((f * sp + off) % 1500) - 220;
      return Array.from({length: 16}).map((_, k) => {
        const y = head - k * 36; if (y < -30 || y > 1100) return null;
        const ch = GL[Math.floor(hash(i * 31 + k * 17 + Math.floor(f / 5 + k)) * GL.length)];
        return <text key={`${i}-${k}`} x={i * 41 + 6} y={y} fill={k === 0 ? WH : G} opacity={k === 0 ? 0.95 : Math.pow(1 - k / 16, 1.7) * 0.8}>{ch}</text>;
      });
    })}
  </g>
);

export const Desk: React.FC<{col: string; f: number; robotSeated: boolean; sw: number}> = ({col, f, robotSeated, sw}) => {
  const top = GROUND - 190;
  return (
    <g stroke={col} strokeWidth={sw * 0.8} strokeLinecap="round" fill="none">
      <line x1={DESK_X - 190} y1={top} x2={DESK_X + 210} y2={top} />
      <line x1={DESK_X - 170} y1={top} x2={DESK_X - 170} y2={GROUND} opacity={0.6} />
      <line x1={DESK_X + 190} y1={top} x2={DESK_X + 190} y2={GROUND} opacity={0.6} />
      <line x1={DESK_X - 330} y1={GROUND} x2={DESK_X + 330 + 480} y2={GROUND} opacity={0.35} />
      {/* chair */}
      <path d={`M${380 - 70},${GROUND - 120} L${380 - 40},${GROUND - 98} L${380 + 18},${GROUND - 98}`} opacity={0.8} />
      <line x1={380 - 8} y1={GROUND - 98} x2={380 - 8} y2={GROUND - 6} opacity={0.8} />
      {/* laptop */}
      <path d={`M${DESK_X - 30},${top} L${DESK_X + 20},${top - 78} L${DESK_X + 100},${top - 78} L${DESK_X + 80},${top} Z`} fill={DK} />
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={DESK_X + 28 + i * 3} y1={top - 62 + i * 14} x2={DESK_X + 28 + i * 3 + 20 + 30 * hash(i + Math.floor(f / 4)) * (robotSeated ? 1.3 : 0.7)} y2={top - 62 + i * 14} stroke={robotSeated ? PK : col} strokeWidth={sw * 0.6} />
      ))}
    </g>
  );
};

const Hud: React.FC<{f: number; mono: boolean}> = ({f, mono}) => {
  const label = '> ROBÔ.exe  //  PEGANDO_EMPREGO';
  const n = Math.floor(clamp((f - 28) / 1.4, 0, label.length));
  const showCount = f > 134;
  const gl = f > 134 && f < 142;
  return (
    <>
      <div style={{position: 'absolute', left: 54, top: 58, fontFamily: F.mono, fontSize: 32, letterSpacing: '0.06em', color: G, textShadow: `0 0 12px ${G}`}}>
        {label.slice(0, n)}<span style={{opacity: Math.floor(f / 8) % 2}}>█</span>
      </div>
      <div style={{position: 'absolute', left: 0, right: 0, top: 160, textAlign: 'center', fontFamily: F.mono, fontWeight: 600, fontSize: 112, letterSpacing: '-0.02em', color: PK, textShadow: `0 0 28px ${PK}, ${gl ? '8px 0 #19FF7A' : '0 0 0 transparent'}`, opacity: showCount ? 1 : 0, transform: `scale(${showCount ? 1 + 0.12 * Math.max(0, 1 - (f - 134) / 8) : 1}) translateX(${gl ? (hash(f) - 0.5) * 24 : 0}px)`}}>
        −1 EMPREGO
      </div>
    </>
  );
};

const GlyphFill: React.FC<{col: string; f: number; id: string}> = ({col, f, id}) => (
  <g fontFamily={F.mono} fontSize={17} fontWeight={600} fill={col}>
    {Array.from({length: 22}).map((_, r) => Array.from({length: 24}).map((__, c) => {
      const h = hash(r * 53 + c * 7 + Math.floor(f / 3) * 3 + id.length);
      return <text key={`${r}-${c}`} x={-170 + c * 14} y={-300 + r * 15} opacity={0.4 + 0.6 * h}>{GL[Math.floor(h * 997) % GL.length]}</text>;
    }))}
  </g>
);

export const Opcao: React.FC<{opt: Opt}> = ({opt}) => {
  const f = useCurrentFrame();
  const s = scene(f);
  const glitch = [30, 31, 88, 89, 134, 135, 136].includes(f) || f % 53 === 0;
  const jx = glitch ? (hash(f) - 0.5) * 26 : 0;
  const sw = opt === 'B' ? 16 : opt === 'C' ? 32 : 9;
  const bg = opt === 'B' ? '#031208' : DK;
  const personCol = G, robotCol = WH;
  const fig = (kind: 'person' | 'robot', x: number, pose: Pose, dir: number, box = 0) => {
    const col = kind === 'person' ? personCol : robotCol;
    const eye = PK;
    const fill = opt === 'B' ? '#06210F' : DK;
    const tr = `translate(${x},${GROUND}) scale(${S * dir},${S})`;
    if (opt !== 'C') return <g transform={tr}><Figure p={pose} kind={kind} col={col} fill={fill} eye={eye} sw={sw} f={f} box={box} /></g>;
    const id = `m_${kind}`;
    const b = body(pose);
    return (
      <g transform={tr}>
        <defs>
          <mask id={id} maskUnits="userSpaceOnUse" x={-300} y={-420} width={620} height={440}>
            <Figure p={pose} kind={kind} col="#fff" fill="#fff" eye="#000" sw={sw} f={f} box={box} solid />
          </mask>
        </defs>
        <g mask={`url(#${id})`}>
          <GlyphFill col={kind === 'person' ? G : '#CFFFE6'} f={f} id={id} />
        </g>
        {kind === 'robot' ? <rect x={b.head[0] - 22} y={b.head[1] - 10} width={44} height={11} rx={4} fill={PK} transform={`rotate(${b.ang} ${b.head[0]} ${b.head[1]})`} /> : null}
      </g>
    );
  };
  const pixelate = opt === 'B';
  return (
    <AbsoluteFill style={{background: bg, overflow: 'hidden'}}>
      <svg width={1080} height={1080} style={{position: 'absolute', inset: 0}}>
        <defs>
          <Glow id="glow" r={opt === 'A' ? 7 : 4} />
          <filter id="pix" filterUnits="userSpaceOnUse" x="0" y="0" width="1080" height="1080">
            <feFlood x="4" y="4" height="2" width="2" />
            <feComposite width="10" height="10" />
            <feTile result="a" />
            <feComposite in="SourceGraphic" in2="a" operator="in" />
            <feMorphology operator="dilate" radius="5" />
          </filter>
          <radialGradient id="vig" cx="50%" cy="50%" r="70%"><stop offset="55%" stopColor="#000" stopOpacity="0" /><stop offset="100%" stopColor="#000" stopOpacity="0.8" /></radialGradient>
        </defs>
        <g transform={`translate(${jx},0)`}>
          <Rain f={f} op={opt === 'A' ? 0.2 : opt === 'B' ? 0.28 : 0.12} />
          <g filter={pixelate ? 'url(#pix)' : opt === 'A' ? 'url(#glow)' : undefined}>
            <Desk col={opt === 'B' ? '#2BE37C' : '#14B85A'} f={f} robotSeated={s.robotSeated} sw={sw} />
            {s.personVisible ? fig('person', s.px, s.pp, 1, s.box) : null}
            {f >= 18 ? fig('robot', s.rx, s.rpose, s.robotSeated ? 1 : -1) : null}
          </g>
        </g>
        <rect width={1080} height={1080} fill="url(#vig)" />
        {Array.from({length: 135}).map((_, i) => <line key={i} x1={0} x2={1080} y1={i * 8 + 2} y2={i * 8 + 2} stroke="#000" strokeOpacity={0.22} strokeWidth={3} />)}
      </svg>
      <Hud f={f} mono />
      <div style={{position: 'absolute', right: 40, bottom: 34, fontFamily: F.mono, fontSize: 26, color: G, opacity: 0.8}}>OPÇÃO {opt}</div>
    </AbsoluteFill>
  );
};
