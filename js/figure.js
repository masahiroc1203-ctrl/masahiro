// 棒人間デモのSVG描画とアニメーション管理
import { VIEW, BODY, frameAt } from './pose.js';

const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}) => {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};
const f = (n) => n.toFixed(1);
const path = (pts) => `M${pts.map((p) => `${f(p[0])} ${f(p[1])}`).join('L')}`;

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
    const pts = [j.hip, j.shoulder, ...j.a1, ...j.a2, ...j.l1, ...j.l2];
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

  const mk = (cls) => el('path', { class: cls });
  const parts = {
    a2: mk(side ? 'fig-limb fig-far' : 'fig-limb'),
    l2: mk(side ? 'fig-limb fig-far' : 'fig-limb'),
    l1: mk('fig-limb'),
    torso: mk('fig-limb fig-torso'),
    a1: mk('fig-limb'),
  };
  const head = el('circle', { class: 'fig-head', r: BODY.head });
  if (side) svg.append(parts.a2, parts.l2, parts.l1, parts.torso, head, parts.a1);
  else svg.append(parts.l1, parts.l2, parts.torso, parts.a1, parts.a2, head);

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
      parts.torso.setAttribute('d', path([j.hip, j.shoulder]));
      for (const key of ['a1', 'a2', 'l1', 'l2']) parts[key].setAttribute('d', path(j[key]));
      head.setAttribute('cx', f(j.head[0]));
      head.setAttribute('cy', f(j.head[1]));
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
