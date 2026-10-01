// メニュー一覧・詳細・作成
import { EXERCISES, EXERCISE_BY_ID, LR_LABEL } from '../data/exercises.js';
import { PARTS, PART_BY_ID, LEVELS } from '../data/parts.js';
import { PRESET_MENUS } from '../data/menus.js';
import { menuSeconds, formatClock, formatMinutes } from '../engine.js';
import {
  allMenus,
  getMenu,
  isCustom,
  setTiming,
  resetTiming,
  saveCustomMenu,
  deleteCustomMenu,
  weekParts,
  weekKey,
  uid,
} from '../store.js';
import { $, $$, esc, icon, partTag, levelDots, figSlot, mountFigures, stepperHtml, bindSteppers, toast, confirmSheet } from '../ui.js';

const intervals = (m) => m.exercises.length * m.laps;
export const timingText = (m) => `${m.work}秒運動・${m.rest}秒休憩 × ${intervals(m)}本`;

export function menuCardHtml(m) {
  const sec = menuSeconds(m);
  const uniq = [...new Set(m.exercises)].slice(0, 6);
  return `<a class="card menu-card" href="#/menu/${esc(m.id)}">
    <div class="title-row">
      <div>
        <h3>${esc(m.name)}</h3>
        <div class="meta">${partTag(m.part)}${m.level ? levelDots(m.level) : '<span class="tag">マイメニュー</span>'}<span>${esc(timingText(m))}</span></div>
      </div>
      <div class="time num">${Math.round(sec / 60) || '<1'}<small>分</small></div>
    </div>
    <div class="minis">${uniq.map((id) => figSlot(id, 'thumb', 'mini')).join('')}</div>
  </a>`;
}

// ───── 一覧 ─────
let filter = 'week';

export function menusView() {
  const wk = weekKey();
  const focus = weekParts(wk);
  if (filter === 'week' && !focus.length) filter = 'all';
  const chips = [
    ...(focus.length ? [{ id: 'week', label: '今週の部位' }] : []),
    { id: 'all', label: 'すべて' },
    ...PARTS.map((p) => ({ id: p.id, label: p.short, color: p.color })),
    { id: 'mine', label: 'マイメニュー' },
  ];
  const list = allMenus().filter((m) => {
    if (filter === 'all') return true;
    if (filter === 'week') return focus.includes(m.part);
    if (filter === 'mine') return isCustom(m.id);
    return m.part === filter;
  });
  return {
    title: 'メニュー',
    actions: `<a class="icon-btn" href="#/edit/new" aria-label="メニューを作る">${icon('plus')}</a>`,
    html: `
      <div class="chip-row" role="toolbar" aria-label="部位で絞り込み">
        ${chips
          .map(
            (c) =>
              `<button class="chip" data-filter="${c.id}" aria-pressed="${filter === c.id}">${c.color ? `<span class="dot" style="--c:${c.color}"></span>` : ''}${esc(c.label)}</button>`,
          )
          .join('')}
      </div>
      <div class="menu-list section">
        ${list.map(menuCardHtml).join('') || `<div class="empty">まだありません。<br><a href="#/edit/new">メニューを作る</a></div>`}
      </div>
      <div class="section">
        <a class="btn btn-block" href="#/edit/new">${icon('plus')}自分でメニューを作る</a>
      </div>`,
    mount(root, ctx) {
      mountFigures(root);
      for (const b of $$('[data-filter]', root)) {
        b.addEventListener('click', () => {
          filter = b.dataset.filter;
          ctx.rerender();
        });
      }
    },
  };
}

// ───── 詳細 ─────
const TIMING_SPEC = {
  work: { min: 5, max: 180, step: 5, fmt: (v) => `${v}秒` },
  rest: { min: 0, max: 120, step: 5, fmt: (v) => (v ? `${v}秒` : 'なし') },
  laps: { min: 1, max: 10, step: 1, fmt: (v) => `${v}周` },
  lapRest: { min: 0, max: 180, step: 10, fmt: (v) => (v ? `${v}秒` : 'なし') },
};

function timingHtml(m) {
  const row = (key, label, note) => `
    <div class="setting">
      <div class="label"><b>${label}</b>${note ? `<small>${note}</small>` : ''}</div>
      ${stepperHtml(key, m[key], TIMING_SPEC[key].fmt)}
    </div>`;
  return `<div class="settings-list">
    ${row('work', '運動', '1種目あたり')}
    ${row('rest', '休憩', '種目と種目の間')}
    ${row('laps', '周回', `${m.exercises.length}種目を何周するか`)}
    ${m.laps > 1 ? row('lapRest', '周の間の休憩', 'なし＝通常の休憩') : ''}
  </div>`;
}

export function menuView({ id }) {
  const m = getMenu(id);
  if (!m) return { title: 'メニュー', back: '#/menus', html: `<div class="empty">メニューが見つかりません</div>` };
  const custom = isCustom(id);
  const sec = menuSeconds(m);
  return {
    title: m.name,
    back: '#/menus',
    actions: custom ? `<a class="icon-btn" href="#/edit/${esc(id)}" aria-label="編集">${icon('edit')}</a>` : '',
    cls: 'has-cta',
    html: `
      <div class="detail-hero">
        <div class="meta">${partTag(m.part)}${m.level ? `${levelDots(m.level)}<span>${LEVELS[m.level].label}</span>` : '<span class="tag">マイメニュー</span>'}</div>
        <h2>${esc(m.name)}</h2>
        ${m.desc ? `<p class="muted" style="margin:0">${esc(m.desc)}</p>` : ''}
        <div class="total-time section" style="margin-top:12px"><span class="big num" data-total>${formatClock(sec)}</span><span class="muted small" data-count>${esc(timingText(m))}</span></div>
      </div>

      <div class="section card">
        <div class="section-head" style="margin-bottom:0"><h2>時間設定</h2>${m.edited ? `<button class="btn btn-ghost small" data-act="reset">初期値に戻す</button>` : ''}</div>
        <div data-timing>${timingHtml(m)}</div>
      </div>

      <div class="section">
        <div class="section-head"><h2>種目（${m.exercises.length}）</h2><span class="muted small">タップでやり方</span></div>
        <div class="card" style="padding:4px 12px">
          ${m.exercises
            .map((exId, i) => {
              const ex = EXERCISE_BY_ID[exId];
              if (!ex) return '';
              return `<a class="ex-row" href="#/exercise/${ex.id}">
                <span class="order">${i + 1}</span>
                ${figSlot(ex.id, 'anim', 'mini')}
                <div class="body"><h4>${esc(ex.name)}</h4><p>${ex.lr ? `【${LR_LABEL[ex.lr]}】` : ''}${esc(ex.cue)}</p></div>
              </a>`;
            })
            .join('')}
        </div>
      </div>

      <div class="section btn-row">
        ${
          custom
            ? `<a class="btn" href="#/edit/${esc(id)}">${icon('edit')}編集</a><button class="btn btn-danger" data-act="delete">${icon('trash')}削除</button>`
            : `<a class="btn" href="#/edit/new?from=${esc(id)}">${icon('copy')}コピーして自分用に編集</a>`
        }
      </div>

      <div class="sticky-cta">
        <button class="btn btn-primary btn-big btn-block" data-act="start">${icon('play')}スタート <span class="num" data-cta-time>${formatClock(sec)}</span></button>
      </div>`,
    mount(root, ctx) {
      mountFigures(root);
      const values = { work: m.work, rest: m.rest, laps: m.laps, lapRest: m.lapRest };
      const box = $('[data-timing]', root);
      let shownLapRest = m.laps > 1;
      const bind = () =>
        bindSteppers(box, values, TIMING_SPEC, () => {
          setTiming(id, values);
          const updated = { ...m, ...values };
          const s = menuSeconds(updated);
          $('[data-total]', root).textContent = formatClock(s);
          $('[data-cta-time]', root).textContent = formatClock(s);
          $('[data-count]', root).textContent = timingText(updated);
          // 周回が1⇔2以上に変わったら「周の間の休憩」の行を出し入れする
          if (values.laps > 1 !== shownLapRest) {
            shownLapRest = values.laps > 1;
            box.innerHTML = timingHtml(updated);
            bind();
          }
        });
      bind();
      root.addEventListener('click', async (e) => {
        const act = e.target.closest('[data-act]')?.dataset.act;
        if (act === 'start') ctx.startWorkout(getMenu(id));
        else if (act === 'reset') {
          resetTiming(id);
          ctx.rerender();
        } else if (act === 'delete' && (await confirmSheet(`「${m.name}」を削除しますか？`, { ok: '削除する', danger: true }))) {
          deleteCustomMenu(id);
          toast('削除しました');
          ctx.navigate('#/menus', { replace: true });
        }
      });
    },
  };
}

// ───── 作成・編集 ─────
let draft = null;
let pickFilter = 'all';

export function editView({ id }, query) {
  if (!draft || draft.key !== `${id}:${query.get('from') || ''}`) {
    const from = id === 'new' ? getMenu(query.get('from') || '') : getMenu(id);
    const focus = weekParts(weekKey());
    draft = {
      key: `${id}:${query.get('from') || ''}`,
      menu:
        id !== 'new' && from
          ? structuredClone(from)
          : {
              id: uid('my-'),
              name: from ? `${from.name}（マイ）` : '',
              part: from?.part || focus[0] || 'full',
              work: from?.work ?? 20,
              rest: from?.rest ?? 10,
              laps: from?.laps ?? 2,
              lapRest: from?.lapRest ?? 0,
              exercises: from ? [...from.exercises] : [],
            },
    };
    pickFilter = draft.menu.part;
  }
  const m = draft.menu;
  const count = (exId) => m.exercises.filter((x) => x === exId).length;
  const pickList = EXERCISES.filter((ex) => pickFilter === 'all' || ex.parts.includes(pickFilter));
  return {
    title: id === 'new' ? 'メニューを作る' : 'メニューを編集',
    back: id === 'new' ? (query.get('from') ? `#/menu/${query.get('from')}` : '#/menus') : `#/menu/${id}`,
    cls: 'has-cta',
    html: `
      <label class="field"><span>メニュー名</span><input class="input" data-name maxlength="30" placeholder="例：朝の下半身タバタ" value="${esc(m.name)}"></label>
      <div class="field"><span>強化する部位</span>
        <div class="chip-wrap">${PARTS.map((p) => `<button class="chip" data-part="${p.id}" aria-pressed="${m.part === p.id}"><span class="dot" style="--c:${p.color}"></span>${esc(p.short)}</button>`).join('')}</div>
      </div>

      <div class="card section">
        <div class="section-head" style="margin-bottom:0"><h2>時間設定</h2><span class="muted small num" data-total>${formatMinutes(menuSeconds(m))}</span></div>
        <div data-timing>${timingHtml(m)}</div>
      </div>

      <div class="section">
        <div class="section-head"><h2>選んだ種目（${m.exercises.length}）</h2><span class="muted small">この順番で行います</span></div>
        <div class="picked">
          ${
            m.exercises
              .map(
                (exId, i) => `<div class="picked-item">
                <span class="order muted" style="width:18px;text-align:center;font-weight:800">${i + 1}</span>
                ${figSlot(exId, 'thumb', 'mini')}
                <span class="name">${esc(EXERCISE_BY_ID[exId]?.name || exId)}</span>
                <button class="icon-btn" data-move="${i}:-1" aria-label="上へ" ${i === 0 ? 'disabled' : ''}>${icon('up')}</button>
                <button class="icon-btn" data-move="${i}:1" aria-label="下へ" ${i === m.exercises.length - 1 ? 'disabled' : ''}>${icon('down')}</button>
                <button class="icon-btn" data-remove="${i}" aria-label="外す">${icon('close')}</button>
              </div>`,
              )
              .join('') || '<div class="empty card">下の一覧から種目をタップして追加してください</div>'
          }
        </div>
      </div>

      <div class="section">
        <div class="section-head"><h2>種目を追加</h2></div>
        <div class="chip-row" style="margin-bottom:10px">
          <button class="chip" data-pick-filter="all" aria-pressed="${pickFilter === 'all'}">すべて</button>
          ${PARTS.map((p) => `<button class="chip" data-pick-filter="${p.id}" aria-pressed="${pickFilter === p.id}"><span class="dot" style="--c:${p.color}"></span>${esc(p.short)}</button>`).join('')}
        </div>
        <div class="pick-grid">
          ${pickList
            .map(
              (ex) => `<button class="pick" data-add="${ex.id}">
              ${count(ex.id) ? `<span class="count">${count(ex.id)}</span>` : ''}
              ${figSlot(ex.id, 'thumb', 'fig-box')}
              ${esc(ex.name)}
            </button>`,
            )
            .join('')}
        </div>
      </div>

      <div class="sticky-cta"><button class="btn btn-primary btn-big btn-block" data-act="save">${icon('check')}保存する</button></div>`,
    mount(root, ctx) {
      mountFigures(root);
      const keepScroll = (fn) => {
        const y = window.scrollY;
        fn();
        ctx.rerender();
        window.scrollTo(0, y);
      };
      $('[data-name]', root).addEventListener('input', (e) => (m.name = e.target.value));
      bindSteppers($('[data-timing]', root), m, TIMING_SPEC, (name) => {
        $('[data-total]', root).textContent = formatMinutes(menuSeconds(m));
        if (name === 'laps') keepScroll(() => {});
      });
      root.addEventListener('click', (e) => {
        const t = e.target.closest('button');
        if (!t) return;
        const d = t.dataset;
        if (d.part)
          keepScroll(() => {
            m.part = d.part;
            pickFilter = d.part;
          });
        else if (d.pickFilter) keepScroll(() => (pickFilter = d.pickFilter));
        else if (d.add) {
          keepScroll(() => m.exercises.push(d.add));
          toast(`${EXERCISE_BY_ID[d.add].name} を追加しました`);
        } else if (d.remove) keepScroll(() => m.exercises.splice(Number(d.remove), 1));
        else if (d.move) {
          const [i, dir] = d.move.split(':').map(Number);
          keepScroll(() => {
            const [x] = m.exercises.splice(i, 1);
            m.exercises.splice(i + dir, 0, x);
          });
        } else if (d.act === 'save') {
          if (!m.exercises.length) return toast('種目を1つ以上追加してください');
          const name = m.name.trim() || `マイメニュー（${PART_BY_ID[m.part].short}）`;
          const saved = { ...m, name };
          delete saved.level;
          delete saved.desc;
          delete saved.edited;
          if (PRESET_MENUS.some((p) => p.id === saved.id)) saved.id = uid('my-');
          saveCustomMenu(saved);
          draft = null;
          toast('保存しました');
          ctx.navigate(`#/menu/${saved.id}`, { replace: true });
        }
      });
    },
  };
}

export function clearDraft() {
  draft = null;
}

