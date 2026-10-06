// お手本の人物のSVG描画とアニメーション管理
import { VIEW, BODY, frameAt } from './pose.js';

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};
const f = (n) => n.toFixed(1);
const mix = (a, b, e) => [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e];

// 体の各部は「塗り」だけで描く。縁を丸めるために線（stroke）を重ねると塗りの手間が倍以上になり、
// 図が並ぶ画面でコマ落ちした（エミュレータで毎秒27→11コマ）。関節に丸を置き、胴体は曲線でつないで丸みを出す。
// 1つの <path> に重ねる形はすべて時計回りにそろえる（向きが混ざると重なった所が抜ける）

// 2点を結ぶ、付け根が太く先が細い帯
function taper(p, q, r1, r2) {
  const dx = q[0] - p[0];
  const dy = q[1] - p[1];
  const l = Math.hypot(dx, dy) || 1;
  const nx = -dy / l;
  const ny = dx / l;
  return (
    `M${f(p[0] - nx * r1)} ${f(p[1] - ny * r1)}L${f(q[0] - nx * r2)} ${f(q[1] - ny * r2)}` +
    `L${f(q[0] + nx * r2)} ${f(q[1] + ny * r2)}L${f(p[0] + nx * r1)} ${f(p[1] + ny * r1)}Z`
  );
}
const dot = (c, r) => `M${f(c[0] - r)} ${f(c[1])}a${r} ${r} 0 1 1 ${r * 2} 0a${r} ${r} 0 1 1 ${-r * 2} 0Z`;
// 関節を丸でつないだ帯。pts = [[点, 半径], ...]
const chain = (pts) => pts.map(([c, r], i) => dot(c, r) + (i ? taper(pts[i - 1][0], c, pts[i - 1][1], r) : '')).join('');

const arm = ([sh, elbow, wrist], hand) => chain([[sh, 2.7], [elbow, 2.2], [wrist, 1.7]]) + dot(hand, 2);
const leg = ([hip, knee, ankle]) => chain([[hip, 3.9], [knee, 2.9], [ankle, 1.9]]);
const shortsLeg = ([hip, knee]) => dot(hip, 4.2) + taper(hip, mix(hip, knee, 0.5), 4.2, 3.8);
const shoe = ([, , ankle], toe) => chain([[ankle, 2.1], [toe, 1.7]]);

// 多角形の角を丸めた形（各辺の中点を通り、頂点を制御点にした2次曲線）
function blob(pts) {
  let area = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    area += a[0] * b[1] - b[0] * a[1];
  }
  if (area < 0) pts = pts.slice().reverse();
  const mid = (a, b) => `${f((a[0] + b[0]) / 2)} ${f((a[1] + b[1]) / 2)}`;
  let d = `M${mid(pts[pts.length - 1], pts[0])}`;
  for (let i = 0; i < pts.length; i++) d += `Q${f(pts[i][0])} ${f(pts[i][1])} ${mid(pts[i], pts[(i + 1) % pts.length])}`;
  return `${d}Z`;
}

// 胴体の輪郭。腰(0)→肩(1) の位置 s ごとに、右側と左側の張り出しを [s, 右, 左] で並べる
function trunk(hip, shoulder, rows) {
  const ax = [shoulder[0] - hip[0], shoulder[1] - hip[1]];
  const l = Math.hypot(ax[0], ax[1]) || 1;
  const p = [-ax[1] / l, ax[0] / l]; // 横から見たときは体の前、正面から見たときは画面右
  const at = (s, w) => [hip[0] + ax[0] * s + p[0] * w, hip[1] + ax[1] * s + p[1] * w];
  return blob([...rows.map(([s, a]) => at(s, a)), ...rows.map(([s, , b]) => at(s, -b)).reverse()]);
}
// 横から：胸は前に、お尻は後ろに張り出す
const SIDE_SHIRT = [[0.04, 3.2, 3.9], [0.45, 2.7, 2.6], [0.78, 4.6, 3.6], [1.06, 3, 3.1]];
const SIDE_PELVIS = [[-0.2, 2.8, 3.6], [0.05, 3.2, 4.4], [0.3, 3, 3.6]];
// 正面から：肩幅が広く、腰でくびれる
const FRONT_SHIRT = [[0.04, 5.8, 5.8], [0.48, 4.6, 4.6], [0.86, 6.4, 6.4], [1.04, 6.8, 6.8], [1.14, 2.6, 2.6]];
const FRONT_PELVIS = [[-0.2, 5.4, 5.4], [0.06, 6, 6], [0.3, 5.6, 5.6]];

// 動きの1サイクル全体が収まる範囲（床を含む）。表示枠いっぱいに描くために使う
const boxCache = new WeakMap();
export function motionBox(anim, pad = 5) {
  let box = boxCache.get(anim);
  if (box) return box;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  const steps = 48;
  for (let i = 0; i < steps; i++) {
    const j = frameAt(anim, (anim.ms * i) / steps);
    const pts = [j.hip, j.shoulder, ...j.a1, ...j.a2, ...j.l1, ...j.l2, j.hands.a1, j.hands.a2, j.toes.l1, j.toes.l2];
    for (const [x, y] of pts) {
      x0 = Math.min(x0, x);
      x1 = Math.max(x1, x);
      y0 = Math.min(y0, y);
    }
    x0 = Math.min(x0, j.head[0] - BODY.head);
    x1 = Math.max(x1, j.head[0] + BODY.head);
    y0 = Math.min(y0, j.head[1] - BODY.head);
  }
  const y1 = VIEW.ground + 2;
  box = { x: x0 - pad, y: y0 - pad, w: x1 - x0 + pad * 2, h: y1 - y0 + pad };
  // 極端に細長くならないよう、短い辺を長い辺の6割以上にする
  const minW = box.h * 0.6;
  if (box.w < minW) {
    box.x -= (minW - box.w) / 2;
    box.w = minW;
  }
  const minH = box.w * 0.45;
  if (box.h < minH) {
    box.y -= minH - box.h;
    box.h = minH;
  }
  boxCache.set(anim, box);
  return box;
}

export function createFigure(exercise, { speed = 1, animate = true, at = 0 } = {}) {
  const anim = exercise.anim;
  const side = anim.view !== 'front';
  const box = motionBox(anim);
  const svg = el('svg', {
    viewBox: `${f(box.x)} ${f(box.y)} ${f(box.w)} ${f(box.h)}`,
    class: `fig ${side ? 'fig-side' : 'fig-front'}`,
    role: 'img',
    'aria-label': `${exercise.name}のお手本アニメーション`,
  });
  svg.append(el('line', { class: 'fig-ground', x1: f(box.x + 2), y1: VIEW.ground, x2: f(box.x + box.w - 2), y2: VIEW.ground }));
  const shadow = el('ellipse', { class: 'fig-shadow', cy: VIEW.ground, ry: 1.6 });
  svg.append(shadow);

  // 重ねる順（奥→手前）に、色のクラスと形を作る関数を並べる。1層が1つの <path>
  const layers = side
    ? [
        ['fig-skin-far', (j) => arm(j.a2, j.hands.a2) + leg(j.l2)],
        ['fig-shorts-far', (j) => shortsLeg(j.l2)],
        ['fig-shoe-far', (j) => shoe(j.l2, j.toes.l2)],
        ['fig-skin', (j) => taper(j.shoulder, j.head, 1.7, 1.7)],
        ['fig-shorts', (j) => trunk(j.hip, j.shoulder, SIDE_PELVIS)],
        ['fig-skin', (j) => leg(j.l1)],
        ['fig-shorts', (j) => shortsLeg(j.l1)],
        ['fig-shoe', (j) => shoe(j.l1, j.toes.l1)],
        ['fig-shirt', (j) => trunk(j.hip, j.shoulder, SIDE_SHIRT)],
        'head',
        ['fig-skin', (j) => arm(j.a1, j.hands.a1)],
      ]
    : [
        ['fig-skin', (j) => leg(j.l1) + leg(j.l2)],
        ['fig-shorts', (j) => trunk(j.hip, j.shoulder, FRONT_PELVIS) + shortsLeg(j.l1) + shortsLeg(j.l2)],
        ['fig-shoe', (j) => shoe(j.l1, j.toes.l1) + shoe(j.l2, j.toes.l2)],
        ['fig-skin', (j) => taper(j.shoulder, j.head, 1.9, 1.9)],
        ['fig-shirt', (j) => trunk(j.hip, j.shoulder, FRONT_SHIRT)],
        ['fig-skin', (j) => arm(j.a1, j.hands.a1) + arm(j.a2, j.hands.a2)],
        'head',
      ];
  // 髪は頭の後ろに少しずらして重ね、はみ出た分だけ見せる（横からは後頭部、正面からは頭頂）
  const hair = el('ellipse', { class: 'fig-hair', rx: side ? 4.5 : 4.7, ry: side ? 4.8 : 4.4 });
  const head = el('ellipse', { class: 'fig-part fig-skin', rx: 4.2, ry: 5 });
  const parts = [];
  for (const layer of layers) {
    if (layer === 'head') {
      svg.append(hair, head);
      continue;
    }
    const node = el('path', { class: `fig-part ${layer[0]}` });
    svg.append(node);
    parts.push([node, layer[1]]);
  }

  const fig = {
    el: svg,
    exercise,
    speed,
    clock: 0,
    last: null,
    mounted: false,
    paused: false,
    visible: true,
    render(tMs) {
      const j = frameAt(anim, tMs);
      for (const [node, shape] of parts) node.setAttribute('d', shape(j));
      // 頭は首の向きに合わせて傾ける
      const nx = j.head[0] - j.shoulder[0];
      const ny = j.head[1] - j.shoulder[1];
      const nl = Math.hypot(nx, ny) || 1;
      const tilt = f((Math.atan2(nx, -ny) * 180) / Math.PI);
      // 首が見えるよう、頭は関節の位置より少し上に描く
      const cx0 = j.head[0] + (nx / nl) * 0.9;
      const cy0 = j.head[1] + (ny / nl) * 0.9;
      const back = side ? 1.3 : 0; // 髪は横向きのときだけ後ろへずらす
      const up = side ? 1.2 : 2.4;
      const hx = cx0 + (nx / nl) * up + (ny / nl) * back;
      const hy = cy0 + (ny / nl) * up - (nx / nl) * back;
      for (const [node, cx, cy] of [[head, cx0, cy0], [hair, hx, hy]]) {
        node.setAttribute('cx', f(cx));
        node.setAttribute('cy', f(cy));
        node.setAttribute('transform', `rotate(${tilt} ${f(cx)} ${f(cy)})`);
      }
      const xs = [j.l1[2][0], j.l2[2][0], j.hip[0]];
      const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
      const rx = Math.max(4, 16 - j.lift * 0.8);
      shadow.setAttribute('cx', f(cx));
      shadow.setAttribute('rx', f(rx));
      shadow.style.opacity = j.lift ? String(Math.max(0.15, 0.5 - j.lift * 0.03)) : '';
    },
    tick(now) {
      if (fig.last == null) fig.last = now;
      const dt = now - fig.last;
      fig.last = now;
      if (!fig.paused) fig.clock += dt * fig.speed;
      fig.render(fig.clock);
    },
    setPaused(p) {
      fig.paused = p;
    },
    reset() {
      fig.clock = 0;
      fig.render(0);
    },
    destroy() {
      unregister(fig);
      svg.remove();
    },
  };
  fig.clock = at;
  fig.render(at);
  if (animate) register(fig);
  return fig;
}

// ── 共通のアニメーションループ（画面に見えている図だけ更新） ──
const figures = new Set();
const byEl = new WeakMap();
let raf = 0;
let io = null;

function loop(now) {
  raf = 0;
  for (const fig of figures) {
    if (!fig.el.isConnected) {
      // 一度表示された後にDOMから外れたものは自動で片付ける
      if (fig.mounted) unregister(fig);
      continue;
    }
    fig.mounted = true;
    if (!fig.visible) {
      fig.last = null;
      continue;
    }
    fig.tick(now);
  }
  if (figures.size) raf = requestAnimationFrame(loop);
}

function register(fig) {
  figures.add(fig);
  byEl.set(fig.el, fig);
  if (typeof IntersectionObserver !== 'undefined') {
    if (!io) {
      io = new IntersectionObserver((entries) => {
        for (const e of entries) {
          const f = byEl.get(e.target);
          if (f) f.visible = e.isIntersecting;
        }
      });
    }
    io.observe(fig.el);
  }
  if (!raf) raf = requestAnimationFrame(loop);
}

function unregister(fig) {
  figures.delete(fig);
  if (io) io.unobserve(fig.el);
  if (!figures.size && raf) {
    cancelAnimationFrame(raf);
    raf = 0;
  }
}
