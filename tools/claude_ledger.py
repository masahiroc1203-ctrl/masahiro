#!/usr/bin/env python3
"""Claude 成果物台帳 (claude-ledger).

Claude Code のセッションログ (~/.claude/projects/**/*.jsonl) から
モデル・トークン・推定コストを自動集計し、手動登録した成果物レジストリ
(deliverables.yaml) と突き合わせて HTML ダッシュボードを生成する。

使い方:
    python3 tools/claude_ledger.py scan                # ログ集計 -> data/sessions.json
    python3 tools/claude_ledger.py report              # ターミナルに要約表示
    python3 tools/claude_ledger.py add "タイトル"       # 成果物を台帳に追加
    python3 tools/claude_ledger.py build               # docs/dashboard.html を生成
    python3 tools/claude_ledger.py all                 # scan -> build をまとめて実行
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML が必要です:  pip install pyyaml")

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "deliverables.yaml"
DATA_PATH = REPO_ROOT / "data" / "sessions.json"
DASHBOARD_PATH = REPO_ROOT / "docs" / "dashboard.html"
DEFAULT_LOG_ROOT = Path.home() / ".claude" / "projects"

# --------------------------------------------------------------------------
# 料金表 (USD / 100万トークン)。出典: Anthropic 公開価格 (2026-06 時点)。
# promo は期間限定の導入価格。セッションの実行日で自動的に切り替わる。
# --------------------------------------------------------------------------
PRICING: dict[str, dict] = {
    "claude-fable-5":    {"in": 10.00, "out": 50.00},
    "claude-mythos-5":   {"in": 10.00, "out": 50.00},
    "claude-opus-5":     {"in": 5.00,  "out": 25.00, "fast": {"in": 10.00, "out": 50.00}},
    "claude-opus-4-8":   {"in": 5.00,  "out": 25.00, "fast": {"in": 10.00, "out": 50.00}},
    "claude-opus-4-7":   {"in": 5.00,  "out": 25.00},
    "claude-opus-4-6":   {"in": 5.00,  "out": 25.00},
    "claude-opus-4-5":   {"in": 5.00,  "out": 25.00},
    "claude-opus-4-1":   {"in": 15.00, "out": 75.00},
    "claude-sonnet-5":   {"in": 3.00,  "out": 15.00,
                          "promo": {"until": "2026-08-31", "in": 2.00, "out": 10.00}},
    "claude-sonnet-4-6": {"in": 3.00,  "out": 15.00},
    "claude-sonnet-4-5": {"in": 3.00,  "out": 15.00},
    "claude-haiku-4-5":  {"in": 1.00,  "out": 5.00},
}
# キャッシュ倍率 (base input 比)
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.00
CACHE_READ = 0.10

STATUS_ORDER = ["進行中", "レビュー中", "未着手", "保留", "完了", "アーカイブ"]
DEFAULT_STATUS = "進行中"


# --------------------------------------------------------------------------
# 集計
# --------------------------------------------------------------------------
@dataclass
class Usage:
    requests: int = 0
    input: int = 0
    output: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> None:
        self.requests += other.requests
        self.input += other.input
        self.output += other.output
        self.cache_write_5m += other.cache_write_5m
        self.cache_write_1h += other.cache_write_1h
        self.cache_read += other.cache_read
        self.cost_usd += other.cost_usd

    @property
    def total_tokens(self) -> int:
        return (self.input + self.output + self.cache_write_5m
                + self.cache_write_1h + self.cache_read)


def rates_for(model: str, when: datetime | None, speed: str | None) -> tuple[float, float] | None:
    """モデル・日付・速度モードから (入力単価, 出力単価) を返す。未知モデルは None。"""
    entry = PRICING.get(model)
    if entry is None:
        # 日付サフィックス付き ID (claude-haiku-4-5-20251001 など) の前方一致
        for key, val in PRICING.items():
            if model.startswith(key):
                entry = val
                break
    if entry is None:
        return None
    if speed == "fast" and "fast" in entry:
        return entry["fast"]["in"], entry["fast"]["out"]
    promo = entry.get("promo")
    if promo and when is not None:
        until = datetime.fromisoformat(promo["until"]).replace(tzinfo=timezone.utc)
        if when.date() <= until.date():
            return promo["in"], promo["out"]
    return entry["in"], entry["out"]


def usage_from_record(usage: dict, model: str, when: datetime | None,
                      speed: str | None) -> Usage:
    cache_creation = usage.get("cache_creation") or {}
    write_1h = int(cache_creation.get("ephemeral_1h_input_tokens", 0) or 0)
    write_5m = int(cache_creation.get("ephemeral_5m_input_tokens", 0) or 0)
    if not (write_1h or write_5m):
        # cache_creation の内訳が無いログは 5m 扱いにフォールバック
        write_5m = int(usage.get("cache_creation_input_tokens", 0) or 0)

    u = Usage(
        requests=1,
        input=int(usage.get("input_tokens", 0) or 0),
        output=int(usage.get("output_tokens", 0) or 0),
        cache_write_5m=write_5m,
        cache_write_1h=write_1h,
        cache_read=int(usage.get("cache_read_input_tokens", 0) or 0),
    )
    rates = rates_for(model, when, speed)
    if rates:
        rin, rout = rates
        u.cost_usd = (
            u.input * rin
            + u.cache_write_5m * rin * CACHE_WRITE_5M
            + u.cache_write_1h * rin * CACHE_WRITE_1H
            + u.cache_read * rin * CACHE_READ
            + u.output * rout
        ) / 1_000_000
    return u


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def is_real_user_prompt(record: dict) -> bool:
    """人間が打ったプロンプトか (ツール結果・コマンド展開・system 注入を除外)。"""
    if record.get("isMeta") or record.get("isSidechain"):
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
    text = extract_text(content).strip()
    if not text or text.startswith("<"):
        return False
    return True


def scan_session(path: Path) -> dict | None:
    """1 セッション分の JSONL を集計して dict を返す。"""
    per_model: dict[str, Usage] = defaultdict(Usage)
    tools = Counter()
    seen_message_ids: set[str] = set()
    timestamps: list[datetime] = []
    user_turns = 0
    assistant_turns = 0
    sidechain_requests = 0
    title = ""
    cwd = git_branch = entrypoint = version = ""

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = parse_ts(rec.get("timestamp"))
            if ts:
                timestamps.append(ts)

            rtype = rec.get("type")
            if rtype == "user":
                cwd = cwd or rec.get("cwd", "")
                git_branch = git_branch or rec.get("gitBranch", "")
                entrypoint = entrypoint or rec.get("entrypoint", "")
                version = version or rec.get("version", "")
                if is_real_user_prompt(rec):
                    user_turns += 1
                    if not title:
                        title = extract_text(rec["message"]["content"]).strip()

            elif rtype == "assistant":
                msg = rec.get("message", {})
                model = msg.get("model") or "unknown"
                for block in msg.get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tools[block.get("name", "unknown")] += 1
                # 1 応答が複数行に分割され usage が重複するため message.id で排除
                mid = msg.get("id")
                if not mid or mid in seen_message_ids:
                    continue
                seen_message_ids.add(mid)
                assistant_turns += 1
                if rec.get("isSidechain"):
                    sidechain_requests += 1
                usage = msg.get("usage") or {}
                if not usage or model == "<synthetic>":
                    continue
                per_model[model].add(
                    usage_from_record(usage, model, ts, usage.get("speed"))
                )

    if not per_model and not user_turns:
        return None

    totals = Usage()
    for u in per_model.values():
        totals.add(u)

    started = min(timestamps) if timestamps else None
    ended = max(timestamps) if timestamps else None
    unknown = sorted(m for m in per_model if rates_for(m, started, None) is None)

    first_line = (title.splitlines() or [""])[0]
    return {
        "session_id": path.stem,
        "project": Path(cwd).name if cwd else path.parent.name.lstrip("-").replace("-", "/"),
        "project_path": cwd,
        "git_branch": git_branch,
        "entrypoint": entrypoint,
        "cli_version": version,
        "title": first_line[:160],
        "started_at": started.isoformat() if started else None,
        "ended_at": ended.isoformat() if ended else None,
        "duration_sec": int((ended - started).total_seconds()) if started and ended else 0,
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "sidechain_requests": sidechain_requests,
        "tool_calls": dict(tools.most_common()),
        "models": {m: asdict(u) for m, u in sorted(per_model.items())},
        "totals": asdict(totals),
        "unpriced_models": unknown,
    }


def scan(log_root: Path) -> dict:
    if not log_root.exists():
        sys.exit(f"ログディレクトリが見つかりません: {log_root}")
    sessions = []
    for path in sorted(log_root.glob("**/*.jsonl")):
        try:
            data = scan_session(path)
        except Exception as exc:  # 壊れたログでも全体は止めない
            print(f"  ! スキップ {path.name}: {exc}", file=sys.stderr)
            continue
        if data:
            sessions.append(data)
    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "log_root": str(log_root),
        "sessions": sessions,
    }


# --------------------------------------------------------------------------
# レジストリ (手動登録の成果物)
# --------------------------------------------------------------------------
def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"deliverables": []}
    with REGISTRY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("deliverables", [])
    return data


def save_registry(data: dict) -> None:
    with REGISTRY_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False, width=100)


def load_sessions() -> dict:
    if not DATA_PATH.exists():
        sys.exit("data/sessions.json がありません。先に `scan` を実行してください。")
    with DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def link_sessions(registry: dict, sessions: list[dict]) -> tuple[list[dict], list[dict]]:
    """成果物にセッションを紐付け、未紐付けセッションと合わせて返す。"""
    by_id = {s["session_id"]: s for s in sessions}
    used: set[str] = set()
    items = []

    for entry in registry.get("deliverables", []):
        matched = []
        for ref in entry.get("sessions", []) or []:
            ref = str(ref)
            hits = [sid for sid in by_id if sid == ref or sid.startswith(ref)]
            for sid in hits:
                if sid not in {m["session_id"] for m in matched}:
                    matched.append(by_id[sid])
                    used.add(sid)
        totals = Usage()
        models = Counter()
        for s in matched:
            t = s["totals"]
            totals.add(Usage(**t))
            for name, mu in s["models"].items():
                models[name] += mu["requests"]
        item = dict(entry)
        item["status"] = entry.get("status") or DEFAULT_STATUS
        item["matched_sessions"] = matched
        item["totals"] = asdict(totals)
        item["models_used"] = dict(models.most_common())
        items.append(item)

    orphans = [s for s in sessions if s["session_id"] not in used]
    return items, orphans


# --------------------------------------------------------------------------
# 表示ヘルパ
# --------------------------------------------------------------------------
def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_cost(v: float) -> str:
    return f"${v:,.2f}" if v >= 0.01 else f"${v:.4f}"


def fmt_duration(sec: int) -> str:
    if sec >= 3600:
        return f"{sec // 3600}時間{(sec % 3600) // 60}分"
    if sec >= 60:
        return f"{sec // 60}分"
    return f"{sec}秒"


def fmt_date(iso: str | None) -> str:
    dt = parse_ts(iso)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


# --------------------------------------------------------------------------
# コマンド
# --------------------------------------------------------------------------
def cmd_scan(args) -> None:
    result = scan(Path(args.log_root).expanduser())
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    total = Usage()
    for s in result["sessions"]:
        total.add(Usage(**s["totals"]))
    print(f"✓ {len(result['sessions'])} セッションを集計 -> {DATA_PATH.relative_to(REPO_ROOT)}")
    print(f"  合計 {fmt_tokens(total.total_tokens)} トークン / 推定 {fmt_cost(total.cost_usd)}")


def cmd_report(args) -> None:
    data = load_sessions()
    registry = load_registry()
    items, orphans = link_sessions(registry, data["sessions"])

    print(f"\n=== 成果物 ({len(items)}件) ===")
    for item in items:
        t = Usage(**item["totals"])
        print(f"  [{item['status']}] {item.get('title', item.get('id', '?'))}")
        print(f"      セッション {len(item['matched_sessions'])}件 / "
              f"{fmt_tokens(t.total_tokens)} トークン / {fmt_cost(t.cost_usd)}")
        if item.get("models_used"):
            print(f"      モデル: {', '.join(item['models_used'])}")

    print(f"\n=== 未紐付けセッション ({len(orphans)}件) ===")
    for s in orphans[: args.limit]:
        t = Usage(**s["totals"])
        print(f"  {s['session_id'][:8]}  {fmt_date(s['started_at'])}  "
              f"{fmt_tokens(t.total_tokens):>8}  {fmt_cost(t.cost_usd):>9}  {s['title'][:50]}")
    if len(orphans) > args.limit:
        print(f"  ... 他 {len(orphans) - args.limit} 件")
    print()


def cmd_add(args) -> None:
    registry = load_registry()
    entry = {
        "id": args.id or args.title.lower().replace(" ", "-")[:40],
        "title": args.title,
        "status": args.status,
        "tags": args.tags.split(",") if args.tags else [],
        "link": args.link or "",
        "notes": args.notes or "",
        "updated": datetime.now(timezone.utc).date().isoformat(),
        "sessions": args.sessions.split(",") if args.sessions else [],
    }
    registry["deliverables"].append(entry)
    save_registry(registry)
    print(f"✓ 追加: [{entry['status']}] {entry['title']}  (id: {entry['id']})")


def cmd_build(args) -> None:
    from ledger_html import render_dashboard  # noqa: F401  (同ディレクトリ)

    data = load_sessions()
    registry = load_registry()
    items, orphans = link_sessions(registry, data["sessions"])
    html = render_dashboard(data, items, orphans)
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    print(f"✓ ダッシュボード生成 -> {DASHBOARD_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude 成果物台帳")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="セッションログを集計")
    p_scan.add_argument("--log-root", default=str(DEFAULT_LOG_ROOT))
    p_scan.set_defaults(func=cmd_scan)

    p_report = sub.add_parser("report", help="ターミナルに要約表示")
    p_report.add_argument("--limit", type=int, default=20)
    p_report.set_defaults(func=cmd_report)

    p_add = sub.add_parser("add", help="成果物を台帳に追加")
    p_add.add_argument("title")
    p_add.add_argument("--id")
    p_add.add_argument("--status", default=DEFAULT_STATUS, choices=STATUS_ORDER)
    p_add.add_argument("--tags", help="カンマ区切り")
    p_add.add_argument("--link")
    p_add.add_argument("--notes")
    p_add.add_argument("--sessions", help="セッションID(前方一致可)をカンマ区切り")
    p_add.set_defaults(func=cmd_add)

    p_build = sub.add_parser("build", help="HTML ダッシュボードを生成")
    p_build.set_defaults(func=cmd_build)

    p_all = sub.add_parser("all", help="scan と build をまとめて実行")
    p_all.add_argument("--log-root", default=str(DEFAULT_LOG_ROOT))
    p_all.set_defaults(func=lambda a: (cmd_scan(a), cmd_build(a)))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
