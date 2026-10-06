// お手本の人物の骨格計算（DOM非依存・Nodeでテスト可能）
//
// 角度の約束: 0 = 真下, 90 = 右(前), 180 = 真上, -90 = 左(後ろ)。
// 方向ベクトルは (sin θ, cos θ)（SVG座標なので y は下向きが正）。
// 手足は [上側の角度, 下側の角度] の順運動学、または { p: [x, y], b } の
// 逆運動学（手先・足先の位置を指定し、b で肘・膝の曲がる向きを決める）で指定する。

export const VIEW = { w: 120, h: 100, ground: 94 };

export const BODY = {
  torso: 22,
  neck: 2,
  head: 5.5,
  upperArm: 13,
  foreArm: 12,
  thigh: 17,
  shin: 17,
  shoulderW: 5.5, // 正面ビューでの肩幅(片側)
  hipW: 3.5, // 正面ビューでの腰幅(片側)
  foot: 5.5, // かかと(手足の末端)からつま先まで
  hand: 1.6, // 手首から手の中心まで
};

const LIMBS = {
  a1: { len: [BODY.upperArm, BODY.foreArm], bend: -1, root: 'shoulder' },
  a2: { len: [BODY.upperArm, BODY.foreArm], bend: -1, root: 'shoulder' },
  l1: { len: [BODY.thigh, BODY.shin], bend: 1, root: 'hip' },
  l2: { len: [BODY.thigh, BODY.shin], bend: 1, root: 'hip' },
};
export const LIMB_KEYS = Object.keys(LIMBS);

const RAD = Math.PI / 180;
export const dir = (deg) => [Math.sin(deg * RAD), Math.cos(deg * RAD)];
export const angleOf = (dx, dy) => Math.atan2(dx, dy) / RAD;
const lerp = (a, b, e) => a + (b - a) * e;
const ease = (x) => -(Math.cos(Math.PI * x) - 1) / 2;

// 首の角度を省略したときの既定値。立った姿勢で上体を前に倒しても、人は顔を前に向けたままにするので、
// 頭は胴体ほど倒さない。寝た姿勢・深く倒した姿勢（真上から60度以上）は胴体にそろえる
export function defaultNeck(t) {
  const lean = Math.abs(t - 180);
  const w = Math.min(1, Math.max(0, (60 - lean) / 30)) * 0.45;
  return t + (180 - t) * w;
}

const FLOOR = VIEW.ground - 2; // 床に接する関節の高さ（data/exercises.js の G と同じ）

// つま先の位置。足はすねに直角で、膝が出ている側（体の前）を向く。床より下には行かず、床の上では床に沿う
function toeOf([root, knee, ankle], view, outward) {
  const sx = ankle[0] - knee[0];
  const sy = ankle[1] - knee[1];
  const sl = Math.hypot(sx, sy) || 1;
  let nx;
  let ny;
  let len = BODY.foot;
  if (view === 'front') {
    // 正面ではつま先が手前を向くので、短く外向きに描く
    nx = outward * 0.6;
    ny = 0.8;
    len *= 0.6;
  } else {
    const cross = (knee[0] - root[0]) * sy - (knee[1] - root[1]) * sx;
    const s = cross < -1 ? -1 : 1;
    nx = (sy / sl) * s;
    ny = (-sx / sl) * s;
    if (ankle[1] < FLOOR - 3) {
      // 浮いている足は力が抜けてつま先が少し下がる
      nx += (0.35 * sx) / sl;
      ny += (0.35 * sy) / sl;
      const nl = Math.hypot(nx, ny);
      nx /= nl;
      ny /= nl;
    }
  }
  const toe = [ankle[0] + nx * len, ankle[1] + ny * len];
  if (toe[1] <= FLOOR) return toe;
  const dy = Math.max(0, FLOOR - ankle[1]);
  const dx = Math.sqrt(Math.max(0, len * len - dy * dy));
  return [ankle[0] + (nx >= 0 ? dx : -dx), ankle[1] + dy];
}

function handOf([, elbow, wrist]) {
  const dx = wrist[0] - elbow[0];
  const dy = wrist[1] - elbow[1];
  const l = Math.hypot(dx, dy) || 1;
  return [wrist[0] + (dx / l) * BODY.hand, wrist[1] + (dy / l) * BODY.hand];
}

// 2リンクIK。b の絶対値は横方向のふくらみ倍率（正面ビューの短縮表現に使う）
export function solveIK(root, target, l1, l2, b) {
  let dx = target[0] - root[0];
  let dy = target[1] - root[1];
  let d = Math.hypot(dx, dy);
  if (d < 1e-6) {
    dx = 0;
    dy = 1;
    d = 1;
  }
  const ux = dx / d;
  const uy = dy / d;
  const dc = Math.min(Math.max(d, Math.abs(l1 - l2) + 1e-3), l1 + l2 - 1e-3);
  const a = (l1 * l1 - l2 * l2 + dc * dc) / (2 * dc);
  const h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  const nx = uy;
  const ny = -ux;
  return {
    mid: [root[0] + a * ux + b * h * nx, root[1] + a * uy + b * h * ny],
    end: [root[0] + dc * ux, root[1] + dc * uy],
  };
}

function limbJoints(root, spec, def) {
  if (Array.isArray(spec)) {
    const d1 = dir(spec[0]);
    const mid = [root[0] + d1[0] * def.len[0], root[1] + d1[1] * def.len[0]];
    const d2 = dir(spec[1]);
    const end = [mid[0] + d2[0] * def.len[1], mid[1] + d2[1] * def.len[1]];
    return [root, mid, end];
  }
  const { mid, end } = solveIK(root, spec.p, def.len[0], def.len[1], spec.b ?? def.bend);
  return [root, mid, end];
}

// ポーズ仕様 → 関節座標
export function computeJoints(pose, view = 'side') {
  const hip = pose.hip;
  const td = dir(pose.t);
  const shoulder = [hip[0] + td[0] * BODY.torso, hip[1] + td[1] * BODY.torso];
  const nd = dir(pose.nk ?? pose.t);
  const hr = BODY.neck + BODY.head;
  const head = [shoulder[0] + nd[0] * hr, shoulder[1] + nd[1] * hr];
  const roots = { shoulder: [shoulder, shoulder], hip: [hip, hip] };
  if (view === 'front') {
    const p = [-td[1], td[0]]; // 胴体に垂直な「画面右」方向
    const off = (pt, w, s) => [pt[0] + p[0] * w * s, pt[1] + p[1] * w * s];
    roots.shoulder = [off(shoulder, BODY.shoulderW, 1), off(shoulder, BODY.shoulderW, -1)];
    roots.hip = [off(hip, BODY.hipW, 1), off(hip, BODY.hipW, -1)];
  }
  const out = { hip, shoulder, head };
  for (const key of LIMB_KEYS) {
    const def = LIMBS[key];
    const root = roots[def.root][key.endsWith('1') ? 0 : 1];
    out[key] = limbJoints(root, pose[key], def);
  }
  return out;
}

function limbAngles(joints) {
  const [r, m, e] = joints;
  return [angleOf(m[0] - r[0], m[1] - r[1]), angleOf(e[0] - m[0], e[1] - m[1])];
}

const unwrapNear = (a, ref) => {
  while (a - ref > 180) a -= 360;
  while (ref - a > 180) a += 360;
  return a;
};

// キーフレームを前処理（首の角度の既定値、IK指定の手足の角度換算）
const prepared = new WeakMap();
export function prepare(anim) {
  let p = prepared.get(anim);
  if (p) return p;
  const frames = anim.k.map((src) => {
    const pose = { ...src, nk: src.nk ?? defaultNeck(src.t) };
    const joints = computeJoints(pose, anim.view);
    const ang = {};
    for (const key of LIMB_KEYS) ang[key] = limbAngles(joints[key]);
    return {
      pose,
      ang,
      hold: src.h ?? 0,
      dur: src.d ?? 1,
      jump: src.j ?? 0,
    };
  });
  const weight = frames.reduce((s, f) => s + f.hold + f.dur, 0);
  p = { frames, weight };
  prepared.set(anim, p);
  return p;
}

const NEAR_GROUND = VIEW.ground - 10;

function lerpLimb(A, B, key, e, arcOK) {
  const sa = A.pose[key];
  const sb = B.pose[key];
  const fa = Array.isArray(sa);
  const fb = Array.isArray(sb);
  if (fa && fb) return [lerp(sa[0], sb[0], e), lerp(sa[1], sb[1], e)];
  if (!fa && !fb) {
    const def = LIMBS[key].bend;
    const x = lerp(sa.p[0], sb.p[0], e);
    let y = lerp(sa.p[1], sb.p[1], e);
    const dx = Math.abs(sb.p[0] - sa.p[0]);
    // 床に着いた手足が大きく移動するときは弧を描いて持ち上げる（歩く・跳ぶ表現）
    if (arcOK && dx > 6 && sa.p[1] > NEAR_GROUND && sb.p[1] > NEAR_GROUND) {
      y -= Math.min(8, dx * 0.25) * Math.sin(Math.PI * e);
    }
    return { p: [x, y], b: lerp(sa.b ?? def, sb.b ?? def, e) };
  }
  // 順運動学とIKが混在 → IK側を角度に換算して補間
  let [a0, a1] = fa ? sa : A.ang[key];
  let [b0, b1] = fb ? sb : B.ang[key];
  if (!fa) {
    a0 = unwrapNear(a0, b0);
    a1 = unwrapNear(a1, b1);
  } else {
    b0 = unwrapNear(b0, a0);
    b1 = unwrapNear(b1, a1);
  }
  return [lerp(a0, b0, e), lerp(a1, b1, e)];
}

export function interpolate(A, B, x) {
  const e = ease(x);
  const pa = A.pose;
  const pb = B.pose;
  const pose = {
    hip: [lerp(pa.hip[0], pb.hip[0], e), lerp(pa.hip[1], pb.hip[1], e)],
    t: lerp(pa.t, pb.t, e),
    nk: lerp(pa.nk, pb.nk, e),
  };
  const arcOK = !A.jump;
  for (const key of LIMB_KEYS) pose[key] = lerpLimb(A, B, key, e, arcOK);
  const lift = A.jump ? A.jump * Math.sin(Math.PI * x) : 0;
  return { pose, lift };
}

// 時刻 tMs における補間済みポーズ
export function samplePose(anim, tMs) {
  const { frames, weight } = prepare(anim);
  if (frames.length === 1) return { pose: frames[0].pose, lift: 0 };
  const cycle = anim.ms || 2000;
  let w = (((tMs % cycle) + cycle) % cycle) / cycle * weight;
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    if (w < f.hold) return { pose: f.pose, lift: 0 };
    w -= f.hold;
    if (w < f.dur || i === frames.length - 1) {
      const next = frames[(i + 1) % frames.length];
      return interpolate(f, next, Math.min(1, w / f.dur));
    }
    w -= f.dur;
  }
  return { pose: frames[0].pose, lift: 0 };
}

// 描画用：時刻 tMs の関節座標（ジャンプの持ち上げ込み）と、手・つま先の位置
export function frameAt(anim, tMs) {
  const { pose, lift } = samplePose(anim, tMs);
  const j = computeJoints(pose, anim.view);
  if (lift) {
    const up = (pt) => [pt[0], pt[1] - lift];
    j.hip = up(j.hip);
    j.shoulder = up(j.shoulder);
    j.head = up(j.head);
    for (const key of LIMB_KEYS) j[key] = j[key].map(up);
  }
  j.lift = lift;
  j.hands = { a1: handOf(j.a1), a2: handOf(j.a2) };
  j.toes = { l1: toeOf(j.l1, anim.view, 1), l2: toeOf(j.l2, anim.view, -1) };
  return j;
}
