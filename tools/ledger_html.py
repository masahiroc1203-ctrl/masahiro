"""HTML ダッシュボードのレンダラ (claude_ledger.py から呼ばれる)。

デザイン方針「帳簿」: 角丸カードではなく罫線の台帳、真鍮色のアクセント、
数値はすべて等幅・桁揃え。ステータス色はアクセントと分離した意味色。
"""

from __future__ import annotations

import html
from datetime import datetime, date, timedelta

# ステータス -> 意味色トークン名
STATUS_TOKEN = {
    "進行中": "active",
    "レビュー中": "review",
    "未着手": "todo",
    "保留": "hold",
    "完了": "done",
    "アーカイブ": "archived",
}

# モデル系統ごとの色トークン (シェアバー用)
MODEL_TOKENS = ["m1", "m2", "m3", "m4", "m5", "m6"]


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_cost(v: float) -> str:
    if v >= 0.01:
        return f"${v:,.2f}"
    if v > 0:
        return f"${v:.4f}"
    return "—"


def fmt_duration(sec: int) -> str:
    if sec >= 3600:
        return f"{sec // 3600}h {(sec % 3600) // 60}m"
    if sec >= 60:
        return f"{sec // 60}m"
    return f"{sec}s"


def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return "—"


def short_model(name: str) -> str:
    return name.replace("claude-", "").replace("-", " ")


CSS = """
:root {
  color-scheme: light dark;
  --paper:    #f6f7f9;
  --sheet:    #ffffff;
  --ink:      #131b26;
  --slate:    #5c6879;
  --faint:    #8b97a6;
  --rule:     #dfe3e9;
  --rule-strong: #c3cad4;
  --brass:    #a97514;
  --brass-dim:#f0e2c4;
  --active:   #2563a8;
  --review:   #0e7c7b;
  --todo:     #6b7684;
  --hold:     #a14a5a;
  --done:     #2f7a4e;
  --archived: #929caa;
  --m1: #a97514; --m2: #2563a8; --m3: #0e7c7b;
  --m4: #7a4fa3; --m5: #a14a5a; --m6: #6b7684;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper:    #12161d;
    --sheet:    #191f28;
    --ink:      #e7ecf2;
    --slate:    #9aa6b6;
    --faint:    #6d7987;
    --rule:     #2a323d;
    --rule-strong: #3b4553;
    --brass:    #e0a93c;
    --brass-dim:#4a3c1e;
    --active:   #6ba6e8;
    --review:   #4fbdbb;
    --todo:     #8e99a8;
    --hold:     #d78a97;
    --done:     #63c48e;
    --archived: #6d7987;
    --m1: #e0a93c; --m2: #6ba6e8; --m3: #4fbdbb;
    --m4: #b18ad6; --m5: #d78a97; --m6: #8e99a8;
  }
}
:root[data-theme="dark"] {
  --paper: #12161d; --sheet: #191f28; --ink: #e7ecf2; --slate: #9aa6b6;
  --faint: #6d7987; --rule: #2a323d; --rule-strong: #3b4553;
  --brass: #e0a93c; --brass-dim: #4a3c1e;
  --active: #6ba6e8; --review: #4fbdbb; --todo: #8e99a8;
  --hold: #d78a97; --done: #63c48e; --archived: #6d7987;
  --m1: #e0a93c; --m2: #6ba6e8; --m3: #4fbdbb;
  --m4: #b18ad6; --m5: #d78a97; --m6: #8e99a8;
}
:root[data-theme="light"] {
  --paper: #f6f7f9; --sheet: #ffffff; --ink: #131b26; --slate: #5c6879;
  --faint: #8b97a6; --rule: #dfe3e9; --rule-strong: #c3cad4;
  --brass: #a97514; --brass-dim: #f0e2c4;
  --active: #2563a8; --review: #0e7c7b; --todo: #6b7684;
  --hold: #a14a5a; --done: #2f7a4e; --archived: #929caa;
  --m1: #a97514; --m2: #2563a8; --m3: #0e7c7b;
  --m4: #7a4fa3; --m5: #a14a5a; --m6: #6b7684;
}

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic Medium",
               "Noto Sans JP", "Segoe UI", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.wrap {
  max-width: 1080px;
  margin: 0 auto;
  padding: 3rem 1.5rem 5rem;
  display: flex;
  flex-direction: column;
  gap: 3.25rem;
}
.num, code, .mono {
  font-family: ui-monospace, "SF Mono", "Cascadia Mono", "Roboto Mono", Menlo, monospace;
  font-variant-numeric: tabular-nums;
}

/* --- ヘッダ --- */
.masthead { display: flex; flex-direction: column; gap: .5rem; }
.eyebrow {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: .7rem; letter-spacing: .18em; text-transform: uppercase;
  color: var(--brass); margin: 0;
}
.masthead h1 {
  margin: 0; font-size: clamp(1.9rem, 4vw, 2.6rem); font-weight: 700;
  letter-spacing: -.02em; text-wrap: balance;
}
.masthead p { margin: 0; color: var(--slate); max-width: 62ch; }
.stamp {
  margin-top: .35rem; padding-top: .75rem; border-top: 2px solid var(--ink);
  font-size: .8rem; color: var(--faint);
  display: flex; flex-wrap: wrap; gap: 1.25rem;
}

/* --- KPI --- */
.kpis {
  display: grid; gap: 1px; background: var(--rule);
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  border: 1px solid var(--rule);
}
.kpi { background: var(--sheet); padding: 1.15rem 1.25rem; display: flex; flex-direction: column; gap: .3rem; }
.kpi .label {
  font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: var(--faint);
}
.kpi .value { font-size: 1.75rem; font-weight: 600; letter-spacing: -.02em; line-height: 1.15; }
.kpi .sub { font-size: .78rem; color: var(--slate); }
.kpi.accent .value { color: var(--brass); }

/* --- セクション --- */
section { display: flex; flex-direction: column; gap: 1rem; }
.section-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap;
  border-bottom: 2px solid var(--ink); padding-bottom: .5rem;
}
.section-head h2 { margin: 0; font-size: 1.1rem; font-weight: 700; letter-spacing: .01em; }
.section-head .meta { font-size: .8rem; color: var(--faint); }

/* --- シェアバー --- */
.sharebar {
  display: flex; height: 12px; width: 100%; overflow: hidden;
  border: 1px solid var(--rule-strong);
}
.sharebar span { display: block; height: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: .35rem 1.1rem; font-size: .8rem; color: var(--slate); }
.legend .item { display: flex; align-items: center; gap: .4rem; }
.swatch { width: 10px; height: 10px; flex: none; }

/* --- 台帳テーブル --- */
.sheet { overflow-x: auto; border: 1px solid var(--rule); background: var(--sheet); }
table { width: 100%; border-collapse: collapse; font-size: .875rem; min-width: 620px; }
thead th {
  text-align: left; font-weight: 600; font-size: .72rem; letter-spacing: .09em;
  text-transform: uppercase; color: var(--faint);
  padding: .7rem .85rem; border-bottom: 1px solid var(--rule-strong); white-space: nowrap;
}
tbody td { padding: .7rem .85rem; border-bottom: 1px solid var(--rule); vertical-align: top; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: color-mix(in srgb, var(--brass) 6%, transparent); }
.right { text-align: right; }
.nowrap { white-space: nowrap; }
.dim { color: var(--faint); }
.title-cell { min-width: 18rem; }
.title-cell .name { font-weight: 600; }
.title-cell .desc { font-size: .8rem; color: var(--slate); }

/* --- ステータス pill --- */
.pill {
  display: inline-block; padding: .1rem .55rem; font-size: .74rem; font-weight: 600;
  border: 1px solid currentColor; border-radius: 999px; white-space: nowrap;
}
.pill.s-active { color: var(--active); }
.pill.s-review { color: var(--review); }
.pill.s-todo { color: var(--todo); }
.pill.s-hold { color: var(--hold); }
.pill.s-done { color: var(--done); }
.pill.s-archived { color: var(--archived); }

/* --- 進捗メータ --- */
.meter { display: block; width: 100%; height: 5px; background: var(--rule); margin-top: .4rem; }
.meter i { display: block; height: 100%; background: var(--brass); }

/* --- 日次チャート --- */
.chart {
  display: flex; align-items: flex-end; gap: 2px; height: 190px;
  padding: 0 .1rem; border-bottom: 1px solid var(--rule-strong);
}
.chart .col {
  flex: 1 1 0; min-width: 4px; height: 100%;
  display: flex; flex-direction: column; justify-content: flex-end;
}
.chart .col .seg { display: block; width: 100%; }
.chart .col .seg.k-out { background: var(--brass); }
.chart .col .seg.k-in { background: var(--active); }
.chart .col .seg.k-write { background: var(--review); }
.chart .col .seg.k-read { background: var(--archived); }
.chart .col.zero { border-bottom: 2px solid var(--rule-strong); }
.axis {
  display: flex; gap: 2px; padding: .4rem .1rem 0;
  font-size: .68rem; color: var(--faint);
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.axis span { flex: 1 1 0; min-width: 4px; text-align: center; overflow: visible; white-space: nowrap; }
.peak {
  display: flex; justify-content: space-between; font-size: .72rem;
  color: var(--faint); padding-bottom: .3rem;
}
.tagrow { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .35rem; }
.tag {
  font-size: .72rem; padding: .05rem .45rem; color: var(--slate);
  background: var(--brass-dim); border-radius: 2px;
}
a { color: var(--brass); text-underline-offset: 2px; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--brass); outline-offset: 2px; }
details summary { cursor: pointer; font-size: .8rem; color: var(--slate); }
details[open] summary { margin-bottom: .4rem; }
.subsessions { font-size: .8rem; color: var(--slate); display: flex; flex-direction: column; gap: .2rem; }
.empty { padding: 1.5rem; color: var(--faint); font-size: .9rem; }
footer { border-top: 1px solid var(--rule); padding-top: 1rem; font-size: .8rem; color: var(--faint); }
footer p { margin: .25rem 0; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""


class DayUsage:
    """日次集計の器 (claude_ledger.Usage と同じフィールドを持つ軽量版)。"""

    __slots__ = ("requests", "input", "output", "cache_write_5m",
                 "cache_write_1h", "cache_read", "cost_usd")

    def __init__(self) -> None:
        self.requests = self.input = self.output = 0
        self.cache_write_5m = self.cache_write_1h = self.cache_read = 0
        self.cost_usd = 0.0

    def add(self, d: dict) -> None:
        self.requests += d["requests"]
        self.input += d["input"]
        self.output += d["output"]
        self.cache_write_5m += d["cache_write_5m"]
        self.cache_write_1h += d["cache_write_1h"]
        self.cache_read += d["cache_read"]
        self.cost_usd += d["cost_usd"]

    @property
    def cache_write(self) -> int:
        return self.cache_write_5m + self.cache_write_1h

    @property
    def total_tokens(self) -> int:
        return self.input + self.output + self.cache_write + self.cache_read


def aggregate_daily(sessions: list[dict]) -> list[dict]:
    """全セッションを日付で束ね、活動のない日も 0 埋めした連続した日次配列を返す。"""
    buckets: dict[str, DayUsage] = {}
    session_days: dict[str, set[str]] = {}
    for s in sessions:
        for day, usage in (s.get("daily") or {}).items():
            buckets.setdefault(day, DayUsage()).add(usage)
            session_days.setdefault(day, set()).add(s["session_id"])
    if not buckets:
        return []

    first = date.fromisoformat(min(buckets))
    last = date.fromisoformat(max(buckets))
    rows = []
    cursor = first
    while cursor <= last:
        key = cursor.isoformat()
        rows.append({
            "date": key,
            "usage": buckets.get(key, DayUsage()),
            "sessions": len(session_days.get(key, ())),
        })
        cursor += timedelta(days=1)
    return rows


def status_pill(status: str) -> str:
    token = STATUS_TOKEN.get(status, "todo")
    return f'<span class="pill s-{token}">{esc(status)}</span>'


def render_dashboard(data: dict, items: list[dict], orphans: list[dict]) -> str:
    sessions = data["sessions"]

    # ---- 全体集計 ----
    grand = {"input": 0, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0,
             "cache_read": 0, "cost_usd": 0.0, "requests": 0}
    per_model: dict[str, dict] = {}
    for s in sessions:
        for key in grand:
            grand[key] += s["totals"][key]
        for name, mu in s["models"].items():
            acc = per_model.setdefault(name, dict.fromkeys(grand, 0))
            for key in grand:
                acc[key] += mu[key]
    grand_tokens = (grand["input"] + grand["output"] + grand["cache_write_5m"]
                    + grand["cache_write_1h"] + grand["cache_read"])

    model_rows = sorted(per_model.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True)
    model_color = {name: MODEL_TOKENS[i % len(MODEL_TOKENS)] for i, (name, _) in enumerate(model_rows)}

    active_count = sum(1 for it in items if it["status"] in ("進行中", "レビュー中"))
    unpriced = sorted({m for s in sessions for m in s["unpriced_models"]})

    out: list[str] = []
    add = out.append

    add("<title>Claude 成果物ダッシュボード</title>")
    add(f"<style>{CSS}</style>")
    add('<div class="wrap">')

    # ---- masthead ----
    add('<header class="masthead">')
    add('<p class="eyebrow">Claude Work Ledger</p>')
    add("<h1>Claude 成果物ダッシュボード</h1>")
    add("<p>Claude Code のセッションログから使用モデル・トークン・推定コストを自動集計し、"
        "手動登録した成果物レジストリと突き合わせた台帳です。</p>")
    add('<div class="stamp">')
    add(f'<span>生成 <span class="num">{esc(fmt_dt(data["generated_at"]))}</span></span>')
    add(f'<span>ログ元 <code>{esc(data["log_root"])}</code></span>')
    add("</div></header>")

    # ---- KPI ----
    add('<div class="kpis">')
    add(f'<div class="kpi"><span class="label">成果物</span>'
        f'<span class="value num">{len(items)}</span>'
        f'<span class="sub">うち進行中 {active_count} 件</span></div>')
    add(f'<div class="kpi"><span class="label">セッション</span>'
        f'<span class="value num">{len(sessions)}</span>'
        f'<span class="sub">未紐付け {len(orphans)} 件</span></div>')
    add(f'<div class="kpi"><span class="label">総トークン</span>'
        f'<span class="value num">{fmt_tokens(grand_tokens)}</span>'
        f'<span class="sub">API リクエスト {fmt_int(grand["requests"])} 回</span></div>')
    add(f'<div class="kpi accent"><span class="label">推定コスト</span>'
        f'<span class="value num">{fmt_cost(grand["cost_usd"])}</span>'
        f'<span class="sub">公開価格ベースの概算</span></div>')
    add("</div>")

    # ---- モデル内訳 ----
    add("<section>")
    add('<div class="section-head"><h2>モデル別内訳</h2>'
        f'<span class="meta">コスト構成比 / {len(model_rows)} モデル</span></div>')
    if model_rows:
        total_cost = grand["cost_usd"] or 1.0
        add('<div class="sharebar">')
        for name, mu in model_rows:
            pct = max(mu["cost_usd"] / total_cost * 100, 0.4)
            add(f'<span style="width:{pct:.2f}%;background:var(--{model_color[name]})" '
                f'title="{esc(short_model(name))} {fmt_cost(mu["cost_usd"])}"></span>')
        add("</div>")
        add('<div class="legend">')
        for name, mu in model_rows:
            share = mu["cost_usd"] / total_cost * 100
            add(f'<span class="item"><i class="swatch" style="background:var(--{model_color[name]})"></i>'
                f'{esc(short_model(name))} <span class="num dim">{share:.0f}%</span></span>')
        add("</div>")

        add('<div class="sheet"><table>')
        add("<thead><tr><th>モデル</th><th class='right'>リクエスト</th><th class='right'>入力</th>"
            "<th class='right'>出力</th><th class='right'>キャッシュ書込</th>"
            "<th class='right'>キャッシュ読込</th><th class='right'>推定コスト</th></tr></thead><tbody>")
        for name, mu in model_rows:
            writes = mu["cache_write_5m"] + mu["cache_write_1h"]
            add("<tr>"
                f'<td class="nowrap"><i class="swatch" style="background:var(--{model_color[name]});'
                'display:inline-block;margin-right:.5rem"></i>'
                f'<code>{esc(name)}</code></td>'
                f'<td class="right num">{fmt_int(mu["requests"])}</td>'
                f'<td class="right num">{fmt_int(mu["input"])}</td>'
                f'<td class="right num">{fmt_int(mu["output"])}</td>'
                f'<td class="right num">{fmt_int(writes)}</td>'
                f'<td class="right num">{fmt_int(mu["cache_read"])}</td>'
                f'<td class="right num">{fmt_cost(mu["cost_usd"])}</td></tr>')
        add("</tbody></table></div>")
    else:
        add('<div class="sheet"><p class="empty">集計対象のモデル利用がありません。</p></div>')
    add("</section>")

    # ---- 日次トークン使用量 ----
    daily = aggregate_daily(sessions)
    tzname = data.get("timezone", "UTC")
    add("<section>")
    add('<div class="section-head"><h2>日次トークン使用量</h2>'
        f'<span class="meta">{esc(tzname)} 基準 / {len(daily)} 日間</span></div>')
    if daily:
        active = [r for r in daily if r["usage"].total_tokens > 0]
        peak_row = max(daily, key=lambda r: r["usage"].total_tokens)
        peak = peak_row["usage"].total_tokens or 1
        avg = sum(r["usage"].total_tokens for r in active) / max(len(active), 1)

        add('<div class="peak">'
            f'<span>ピーク <span class="num">{fmt_tokens(peak)}</span> '
            f'({esc(peak_row["date"])})</span>'
            f'<span>稼働 {len(active)} 日 / 稼働日平均 '
            f'<span class="num">{fmt_tokens(int(avg))}</span></span></div>')

        add('<div class="chart">')
        for r in daily:
            u = r["usage"]
            if u.total_tokens == 0:
                add(f'<div class="col zero" title="{esc(r["date"])} 稼働なし"></div>')
                continue
            tip = (f'{r["date"]} · 合計 {fmt_tokens(u.total_tokens)} · {fmt_cost(u.cost_usd)}'
                   f' / 入力 {fmt_int(u.input)} 出力 {fmt_int(u.output)}'
                   f' 書込 {fmt_int(u.cache_write)} 読込 {fmt_int(u.cache_read)}')
            add(f'<div class="col" title="{esc(tip)}">')
            for cls, value in (("k-out", u.output), ("k-in", u.input),
                               ("k-write", u.cache_write), ("k-read", u.cache_read)):
                if value <= 0:
                    continue
                height = max(value / peak * 100, 0.6)
                add(f'<span class="seg {cls}" style="height:{height:.2f}%"></span>')
            add("</div>")
        add("</div>")

        # ラベルは等間隔 + 末尾。末尾が直前のラベルと近すぎる場合は重なるので落とす。
        step = max(1, -(-len(daily) // 8))
        last = len(daily) - 1
        marks = set(range(0, len(daily), step))
        if last - max(marks) >= step / 2:
            marks.add(last)
        add('<div class="axis">')
        for i, r in enumerate(daily):
            label = date.fromisoformat(r["date"]).strftime("%m/%d") if i in marks else ""
            add(f"<span>{esc(label)}</span>")
        add("</div>")

        add('<div class="legend">'
            '<span class="item"><i class="swatch" style="background:var(--brass)"></i>出力</span>'
            '<span class="item"><i class="swatch" style="background:var(--active)"></i>入力</span>'
            '<span class="item"><i class="swatch" style="background:var(--review)"></i>キャッシュ書込</span>'
            '<span class="item"><i class="swatch" style="background:var(--archived)"></i>キャッシュ読込</span>'
            "</div>")

        add('<div class="sheet"><table>')
        add("<thead><tr><th>日付</th><th class='right'>セッション</th><th class='right'>リクエスト</th>"
            "<th class='right'>入力</th><th class='right'>出力</th>"
            "<th class='right'>キャッシュ書込</th><th class='right'>キャッシュ読込</th>"
            "<th class='right'>合計</th><th class='right'>推定コスト</th></tr></thead><tbody>")
        for r in reversed(active):
            u = r["usage"]
            weekday = "月火水木金土日"[date.fromisoformat(r["date"]).weekday()]
            add("<tr>"
                f'<td class="nowrap num">{esc(r["date"])} <span class="dim">({weekday})</span></td>'
                f'<td class="right num">{r["sessions"]}</td>'
                f'<td class="right num">{fmt_int(u.requests)}</td>'
                f'<td class="right num">{fmt_int(u.input)}</td>'
                f'<td class="right num">{fmt_int(u.output)}</td>'
                f'<td class="right num">{fmt_int(u.cache_write)}</td>'
                f'<td class="right num">{fmt_int(u.cache_read)}</td>'
                f'<td class="right num">{fmt_tokens(u.total_tokens)}</td>'
                f'<td class="right num">{fmt_cost(u.cost_usd)}</td></tr>')
        add("</tbody></table></div>")
    else:
        add('<div class="sheet"><p class="empty">日次データがありません。</p></div>')
    add("</section>")

    # ---- 成果物台帳 ----
    add("<section>")
    add('<div class="section-head"><h2>成果物台帳</h2>'
        '<span class="meta">deliverables.yaml で管理</span></div>')
    if items:
        max_cost = max((it["totals"]["cost_usd"] for it in items), default=0) or 1.0
        order = {s: i for i, s in enumerate(STATUS_TOKEN)}
        add('<div class="sheet"><table>')
        add("<thead><tr><th>成果物</th><th>進捗</th><th>使用モデル</th>"
            "<th class='right'>セッション</th><th class='right'>トークン</th>"
            "<th class='right'>推定コスト</th></tr></thead><tbody>")
        for it in sorted(items, key=lambda x: order.get(x["status"], 99)):
            t = it["totals"]
            tokens = (t["input"] + t["output"] + t["cache_write_5m"]
                      + t["cache_write_1h"] + t["cache_read"])
            title = it.get("title") or it.get("id", "(無題)")
            link = it.get("link")
            name_html = (f'<a href="{esc(link)}">{esc(title)}</a>' if link else esc(title))
            add("<tr>")
            add('<td class="title-cell">')
            add(f'<div class="name">{name_html}</div>')
            if it.get("notes"):
                add(f'<div class="desc">{esc(it["notes"])}</div>')
            if it.get("tags"):
                add('<div class="tagrow">'
                    + "".join(f'<span class="tag">{esc(tag)}</span>' for tag in it["tags"])
                    + "</div>")
            pct = t["cost_usd"] / max_cost * 100
            add(f'<span class="meter"><i style="width:{pct:.1f}%"></i></span>')
            if it["matched_sessions"]:
                add("<details><summary>セッション内訳</summary><div class='subsessions'>")
                for s in it["matched_sessions"]:
                    add(f'<span><code>{esc(s["session_id"][:8])}</code> '
                        f'{esc(fmt_dt(s["started_at"]))} · '
                        f'<span class="num">{fmt_cost(s["totals"]["cost_usd"])}</span> · '
                        f'{esc(s["title"][:60])}</span>')
                add("</div></details>")
            add("</td>")
            add(f"<td>{status_pill(it['status'])}</td>")
            models = ", ".join(short_model(m) for m in it["models_used"]) or "—"
            add(f'<td class="dim">{esc(models)}</td>')
            add(f'<td class="right num">{len(it["matched_sessions"])}</td>')
            add(f'<td class="right num">{fmt_tokens(tokens)}</td>')
            add(f'<td class="right num">{fmt_cost(t["cost_usd"])}</td>')
            add("</tr>")
        add("</tbody></table></div>")
    else:
        add('<div class="sheet"><p class="empty">まだ成果物が登録されていません。'
            '<code>python3 tools/claude_ledger.py add "タイトル"</code> で追加できます。</p></div>')
    add("</section>")

    # ---- 未紐付けセッション ----
    add("<section>")
    add('<div class="section-head"><h2>未紐付けセッション</h2>'
        f'<span class="meta">{len(orphans)} 件 — 成果物に割り当てると台帳へ集計されます</span></div>')
    if orphans:
        add('<div class="sheet"><table>')
        add("<thead><tr><th>ID</th><th>開始</th><th>プロジェクト / ブランチ</th><th>概要</th>"
            "<th class='right'>往復</th><th class='right'>時間</th>"
            "<th class='right'>トークン</th><th class='right'>推定コスト</th></tr></thead><tbody>")
        for s in orphans:
            t = s["totals"]
            tokens = (t["input"] + t["output"] + t["cache_write_5m"]
                      + t["cache_write_1h"] + t["cache_read"])
            branch = f'{s["project"]} / {s["git_branch"]}' if s["git_branch"] else s["project"]
            add("<tr>"
                f'<td><code>{esc(s["session_id"][:8])}</code></td>'
                f'<td class="nowrap num dim">{esc(fmt_dt(s["started_at"]))}</td>'
                f'<td class="dim">{esc(branch)}</td>'
                f'<td class="title-cell">{esc(s["title"] or "(無題)")}</td>'
                f'<td class="right num">{s["user_turns"]}</td>'
                f'<td class="right num dim">{esc(fmt_duration(s["duration_sec"]))}</td>'
                f'<td class="right num">{fmt_tokens(tokens)}</td>'
                f'<td class="right num">{fmt_cost(t["cost_usd"])}</td></tr>')
        add("</tbody></table></div>")
    else:
        add('<div class="sheet"><p class="empty">未紐付けのセッションはありません。</p></div>')
    add("</section>")

    # ---- footer ----
    add("<footer>")
    add("<p>コストは Anthropic 公開価格に基づく概算です（キャッシュ書込 5分 = 入力単価 ×1.25 / "
        "1時間 = ×2.0、キャッシュ読込 = ×0.1）。実際の請求額とは一致しません。</p>")
    if unpriced:
        add('<p>価格表に無いモデル（コスト未計上）: <code>'
            + esc(", ".join(unpriced)) + "</code></p>")
    add("<p>再生成: <code>python3 tools/claude_ledger.py all</code></p>")
    add("</footer>")

    add("</div>")
    return "\n".join(out)
