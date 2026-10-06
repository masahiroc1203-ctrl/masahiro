// ホーム：今週の強化部位・今週の進み具合・おすすめメニュー
import { PARTS, PART_BY_ID } from '../data/parts.js';
import { EXERCISES } from '../data/exercises.js';
import { formatMinutes } from '../engine.js';
import {
  state,
  allMenus,
  weekKey,
  dayKey,
  addDays,
  WEEKDAYS,
  formatWeekRange,
  weekParts,
  setWeekParts,
  logsInWeek,
  suggestParts,
} from '../store.js';
import { $, $$, esc, icon, mountFigures, openSheet, toast } from '../ui.js';
import { menuCardHtml } from './menus.js';

const PART_NOTE = {
  full: '心拍を上げて脂肪燃焼・体力アップ',
  lower: 'スクワット・ランジなど脚とお尻',
  core: 'お腹まわり・体幹の安定',
  upper: '腕立て系で胸・二の腕・肩',
  back: '背中・もも裏、姿勢の改善',
};

export function openPartsSheet(wk, onSaved) {
  const selected = new Set(weekParts(wk));
  const suggest = suggestParts(state, wk)[0];
  const exCount = (id) => EXERCISES.filter((e) => e.parts.includes(id)).length;
  openSheet(
    `<h2>今週の強化部位</h2>
     <p class="muted small" style="margin:0">${esc(formatWeekRange(wk))}　複数えらべます</p>
     <div class="part-options">
       ${PARTS.map(
         (p) => `<button class="part-option" data-part="${p.id}" style="--c:${p.color}" aria-pressed="${selected.has(p.id)}">
           <span class="emoji" aria-hidden="true">${p.icon}</span>
           <span class="txt"><b>${esc(p.name)}${p.id === suggest ? ' <span class="tag" style="--c:var(--accent)">おすすめ</span>' : ''}</b><small>${esc(PART_NOTE[p.id])}・${exCount(p.id)}種目</small></span>
           <span class="check">${icon('check')}</span>
         </button>`,
       ).join('')}
     </div>
     <button class="btn btn-primary btn-big btn-block" data-save>この部位で1週間がんばる</button>`,
    (sheet, close) => {
      for (const b of $$('[data-part]', sheet)) {
        b.addEventListener('click', () => {
          const id = b.dataset.part;
          if (selected.has(id)) selected.delete(id);
          else selected.add(id);
          b.setAttribute('aria-pressed', String(selected.has(id)));
        });
      }
      $('[data-save]', sheet).addEventListener('click', () => {
        const parts = PARTS.map((p) => p.id).filter((id) => selected.has(id));
        setWeekParts(wk, parts);
        close();
        toast(parts.length ? `今週は「${parts.map((id) => PART_BY_ID[id].short).join('・')}」を強化！` : '強化部位をクリアしました');
        onSaved?.();
      });
    },
  );
}

export function homeView() {
  const wk = weekKey();
  const today = dayKey();
  const parts = weekParts(wk);
  const logs = logsInWeek(state.logs, wk);
  const goal = state.settings.goal;
  const sec = logs.reduce((s, l) => s + (l.sec || 0), 0);
  const suggest = suggestParts(state, wk);
  const lastWeekParts = weekParts(addDays(wk, -7));
  const menus = allMenus().filter((m) => parts.includes(m.part));

  const days = WEEKDAYS.map((label, i) => {
    const key = addDays(wk, i);
    const n = logs.filter((l) => l.day === key).length;
    return `<div class="day ${n ? 'done' : ''} ${key === today ? 'today' : ''}">
      <span>${label}</span><span class="ring">${n ? icon('check') : ''}</span>
    </div>`;
  }).join('');

  const focusHtml = parts.length
    ? `<div class="focus-parts">${parts
        .map((id) => {
          const p = PART_BY_ID[id];
          return `<span class="focus-part" style="--c:${p.color}"><span class="emoji" aria-hidden="true">${p.icon}</span>${esc(p.name)}</span>`;
        })
        .join('')}</div>
       <button class="btn" data-act="parts">${icon('edit')}部位を変更</button>`
    : `<p class="muted" style="margin:0 0 12px">今週はどこを鍛えますか？ タップで決めましょう。</p>
       <div class="part-options" style="margin:0">
         ${suggest
           .map((id) => {
             const p = PART_BY_ID[id];
             return `<button class="part-option" data-quick="${id}" style="--c:${p.color}">
               <span class="emoji" aria-hidden="true">${p.icon}</span>
               <span class="txt"><b>${esc(p.name)}${id === suggest[0] ? ' <span class="tag" style="--c:var(--accent)">おすすめ</span>' : ''}</b><small>${esc(PART_NOTE[id])}</small></span>
             </button>`;
           })
           .join('')}
       </div>
       ${lastWeekParts.length ? `<p class="muted small" style="margin:10px 0 0">先週：${lastWeekParts.map((id) => esc(PART_BY_ID[id].short)).join('・')}</p>` : ''}
       <button class="btn btn-ghost" style="margin-top:6px" data-act="parts">複数えらぶ</button>`;

  return {
    title: 'HIIT Weekly',
    sub: '週替わり・部位別HIIT',
    actions: `<a class="icon-btn" href="#/settings" aria-label="設定">${icon('sliders')}</a>`,
    html: `
      <section class="card week-card">
        <div class="range">今週　${esc(formatWeekRange(wk))}</div>
        <h2>${parts.length ? '今週の強化部位' : '今週の強化部位を決めよう'}</h2>
        ${focusHtml}
        <div class="days" aria-label="今週の実施日">${days}</div>
        <div class="progress-line"><span>今週 <b class="num">${logs.length}</b> / ${goal} 回</span><span>運動 <b class="num">${formatMinutes(sec)}</b></span></div>
        <div class="bar" style="margin-top:6px"><i style="width:${Math.min(100, (logs.length / goal) * 100)}%"></i></div>
      </section>

      ${
        parts.length
          ? `<section class="section">
              <div class="section-head"><h2>今週のメニュー</h2><a class="small" href="#/menus">すべて見る</a></div>
              <div class="menu-list">${menus.map(menuCardHtml).join('') || `<div class="empty card">この部位のメニューがありません。<a href="#/edit/new">作る</a></div>`}</div>
            </section>`
          : `<section class="section">
              <div class="section-head"><h2>まずはこちら</h2><a class="small" href="#/menus">すべて見る</a></div>
              <div class="menu-list">${allMenus().filter((m) => m.id === 'full-beginner' || m.id === 'full-tabata').map(menuCardHtml).join('')}</div>
            </section>`
      }

      ${
        logs.length
          ? `<section class="section">
              <div class="section-head"><h2>今週の記録</h2><a class="small" href="#/history">記録へ</a></div>
              <div class="card" style="padding:8px 14px">
                <ul class="log-list">${logs
                  .slice()
                  .reverse()
                  .map((l) => `<li><span>${esc(l.day.slice(5).replace('-', '/'))}　<b>${esc(l.menuName)}</b></span><span class="num">${formatMinutes(l.sec)}${l.completed ? '' : '（途中）'}</span></li>`)
                  .join('')}</ul>
              </div>
            </section>`
          : ''
      }`,
    mount(root, ctx) {
      mountFigures(root);
      root.addEventListener('click', (e) => {
        const t = e.target.closest('[data-act],[data-quick]');
        if (!t) return;
        if (t.dataset.act === 'parts') openPartsSheet(wk, ctx.rerender);
        else if (t.dataset.quick) {
          setWeekParts(wk, [t.dataset.quick]);
          toast(`今週は「${PART_BY_ID[t.dataset.quick].short}」を強化！`);
          ctx.rerender();
        }
      });
    },
  };
}
