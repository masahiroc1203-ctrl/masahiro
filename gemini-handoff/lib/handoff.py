#!/usr/bin/env python3
"""Claude Code -> Gemini 引き継ぎファイル生成器。

会話ログ (transcript JSONL) と git の状態から、Gemini CLI がそのまま読める
Markdown (<project>/.handoff/HANDOFF.md) を作る。LLM は使わないので、
Claude の使用上限に達していても動く。

CLI として使う場合:
    python3 handoff.py [--session ID] [--transcript PATH] [--cwd DIR] [--reason TEXT]
"""
import argparse
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULT_CONFIG = {
    # Claude の使用上限の「残り%」がこれ以下になったら引き継ぎを作り、Claude に要約を書かせる
    "threshold_remaining": 8,
    # 残り%がこれ以下になったらスナップショットをもう一度更新する (Claude には頼まない)
    "final_threshold_remaining": 3,
    # 監視する枠: five_hour (5時間枠) / seven_day (週枠) / spend_limit (gateway)
    "windows": ["five_hour", "seven_day"],
    # しきい値到達時に Claude 自身に要約セクションを書かせるか
    "ask_claude_summary": True,
    # プロジェクトの GEMINI.md に引き継ぎファイルの import 行 (@./.handoff/HANDOFF.md) を足すか。
    # true にすると素の `gemini` 起動でも自動で読み込まれる (古い引き継ぎも読まれ続ける点に注意)
    "update_gemini_md": False,
    # 引き継ぎファイルの置き場所 (プロジェクトルートからの相対パス)
    "handoff_dir": ".handoff",
    # .handoff/history に残す世代数
    "history_keep": 20,
    # インストール前に使っていた statusLine コマンド (あればその出力を表示する)
    "wrapped_statusline": "",
}

SUMMARY_BEGIN = "<!-- CLAUDE_SUMMARY:BEGIN -->"
SUMMARY_END = "<!-- CLAUDE_SUMMARY:END -->"
GEMINI_LOG_BEGIN = "<!-- GEMINI_LOG:BEGIN -->"
GEMINI_LOG_END = "<!-- GEMINI_LOG:END -->"
GEMINI_MD_BEGIN = "<!-- claude-handoff:begin (自動生成。不要なら削除可) -->"
GEMINI_MD_END = "<!-- claude-handoff:end -->"

SUMMARY_PLACEHOLDER = "_(まだ書かれていません。下の「自動スナップショット」を参照してください)_"
GEMINI_LOG_PLACEHOLDER = "_(Gemini はここに、やったこと・残っていることを追記してください)_"

WINDOW_LABELS = {"five_hour": "5時間枠", "seven_day": "週枠", "spend_limit": "利用額上限"}

MAX_DIFF_CHARS = 20000
MAX_PROMPT_CHARS = 1500
MAX_REPLY_CHARS = 3000


# ---------------------------------------------------------------- utilities

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    env = os.environ.get("GEMINI_HANDOFF_THRESHOLD")
    if env:
        try:
            cfg["threshold_remaining"] = float(env)
        except ValueError:
            pass
    return cfg


def claude_config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_text_atomic(path, text):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json(path, obj):
    write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2))


def run(cmd, cwd, timeout=10):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        return p.stdout.rstrip() if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def clip(text, limit, keep="head"):
    text = text.strip()
    if len(text) <= limit:
        return text
    if keep == "tail":
        return "…(前略)…\n" + text[-limit:]
    return text[:limit] + "\n…(以下略)…"


def fence(text, lang=""):
    """Markdown コードブロック。中身に ``` があっても壊れないようにする。"""
    ticks = "```"
    while ticks in text:
        ticks += "`"
    return f"{ticks}{lang}\n{text}\n{ticks}"


def quote(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def fmt_time(epoch):
    try:
        return _dt.datetime.fromtimestamp(float(epoch)).strftime("%m/%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "?"


def project_root(cwd):
    cwd = cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top = run(["git", "rev-parse", "--show-toplevel"], cwd)
    return top or cwd


# ---------------------------------------------------------------- transcript

def find_transcript(session_id=None, cwd=None):
    base = os.path.join(claude_config_dir(), "projects")
    if session_id:
        hits = glob.glob(os.path.join(base, "*", f"{session_id}.jsonl"))
        if hits:
            return hits[0]
    # セッション ID が分からないときは、cwd から親へたどって最新の transcript を使う
    d = os.path.abspath(cwd) if cwd else None
    while d:
        slug = re.sub(r"[^A-Za-z0-9]", "-", d)
        hits = glob.glob(os.path.join(base, slug, "*.jsonl"))
        if hits:
            return max(hits, key=os.path.getmtime)
        parent = os.path.dirname(d)
        d = parent if parent != d else None
    return None


_TAG_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def _user_text(content):
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_result":
                return ""
            if b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif b.get("type") == "image":
                parts.append("[画像]")
    else:
        return ""
    text = _TAG_RE.sub("", "\n".join(parts)).strip()
    if not text or text.startswith(("<local-command-stdout>", "<local-command-caveat>",
                                    "<local-command-stderr>")):
        return ""
    m = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
    if m:
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        return f"(スラッシュコマンド) {m.group(1).strip()} {args.group(1).strip() if args else ''}".strip()
    return text


def parse_transcript(path):
    res = {
        "first_prompt": None,
        "prompts": [],          # human prompts (text)
        "turn_replies": [],     # list of [assistant text...] per human turn
        "files": {},            # path -> last tool name (insertion ordered)
        "commands": [],
        "todos": None,
        "tasks": {},            # id -> {"subject", "status"}
        "compact_summary": None,
    }
    if not path or not os.path.exists(path):
        return res
    pending_task_create = {}    # tool_use_id -> subject
    current_turn = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if not isinstance(o, dict) or o.get("isSidechain"):
                continue
            typ = o.get("type")
            msg = o.get("message") if isinstance(o.get("message"), dict) else {}
            content = msg.get("content")

            if typ == "user":
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            tid = b.get("tool_use_id")
                            if tid in pending_task_create:
                                txt = json.dumps(b.get("content"), ensure_ascii=False)
                                m = re.search(r"#(\d+)", txt)
                                if m:
                                    res["tasks"][m.group(1)] = {
                                        "subject": pending_task_create.pop(tid), "status": "pending"}
                if o.get("isCompactSummary"):
                    res["compact_summary"] = _user_text(content)
                    continue
                if o.get("isMeta") or "toolUseResult" in o:
                    continue
                text = _user_text(content)
                if not text:
                    continue
                if res["first_prompt"] is None:
                    res["first_prompt"] = text
                res["prompts"].append(text)
                current_turn = []
                res["turn_replies"].append(current_turn)

            elif typ == "assistant" and isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text" and b.get("text", "").strip():
                        if current_turn is None:
                            current_turn = []
                            res["turn_replies"].append(current_turn)
                        current_turn.append(b["text"].strip())
                    elif bt == "tool_use":
                        _tool(b, res, pending_task_create)
    return res


def _tool(b, res, pending_task_create):
    name = b.get("name") or ""
    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
    if name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        p = inp.get("file_path") or inp.get("notebook_path")
        if p:
            res["files"].pop(p, None)
            res["files"][p] = name
    elif name == "Bash" and inp.get("command"):
        res["commands"].append(inp["command"])
    elif name == "TodoWrite" and isinstance(inp.get("todos"), list):
        res["todos"] = inp["todos"]
    elif name == "TaskCreate" and inp.get("subject"):
        pending_task_create[b.get("id")] = inp["subject"]
    elif name == "TaskUpdate" and inp.get("taskId"):
        t = res["tasks"].setdefault(str(inp["taskId"]), {"subject": f"#{inp['taskId']}", "status": "pending"})
        if inp.get("subject"):
            t["subject"] = inp["subject"]
        if inp.get("status"):
            t["status"] = inp["status"]


# ---------------------------------------------------------------- git

def git_snapshot(root):
    if not run(["git", "rev-parse", "--is-inside-work-tree"], root):
        return None
    diff = run(["git", "diff", "HEAD", "--no-color"], root, timeout=20)
    if not diff:
        diff = run(["git", "diff", "--no-color"], root, timeout=20)
    return {
        "branch": run(["git", "branch", "--show-current"], root) or "(detached)",
        "status": run(["git", "status", "--short"], root),
        "stat": run(["git", "diff", "HEAD", "--stat", "--no-color"], root),
        "log": run(["git", "log", "--oneline", "-8", "--no-color"], root),
        "diff": diff,
    }


# ---------------------------------------------------------------- render

def _extract_block(text, begin, end):
    if not text:
        return None
    i, j = text.find(begin), text.find(end)
    if i == -1 or j == -1 or j < i:
        return None
    return text[i + len(begin):j].strip()


def render(root, transcript, session_id, reason, cfg, prev_text=None):
    data = parse_transcript(transcript)
    git = git_snapshot(root)
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hdir = cfg["handoff_dir"]

    prev_session = None
    if prev_text:
        m = re.search(r"gemini-handoff session=(\S+)", prev_text)
        prev_session = m.group(1) if m else None
    summary = None
    if prev_text and prev_session == (session_id or prev_session):
        summary = _extract_block(prev_text, SUMMARY_BEGIN, SUMMARY_END)
    gemini_log = _extract_block(prev_text, GEMINI_LOG_BEGIN, GEMINI_LOG_END) if prev_text else None

    out = []
    w = out.append
    w("# Claude Code → Gemini 引き継ぎ")
    w("")
    w(f"<!-- gemini-handoff session={session_id or 'unknown'} generated={now} -->")
    w("")
    w(f"- 生成日時: {now}")
    w(f"- 理由: {reason}")
    w(f"- プロジェクト: `{root}`")
    if git:
        w(f"- ブランチ: `{git['branch']}`")
    if session_id:
        w(f"- Claude セッション ID: `{session_id}` (Claude に戻るときは `claude --resume {session_id}`)")
    w("")
    w("## Gemini への指示")
    w("")
    w("あなた (Gemini) は、Claude Code が使用上限で止まる直前まで進めていた作業を引き継ぎます。")
    w("")
    w("1. 下の「1. Claude による要約」と「2. 自動スナップショット」を読んで現状を把握する。")
    w("2. `git status` / `git diff` で実際のファイルを確認する。**この文書と実ファイルが食い違う場合は実ファイルが正しい。**")
    w("3. 「次にやること」から作業を再開する。目的や方針が曖昧な点はユーザーに確認してから進める。")
    w(f"4. 作業の区切りごとに、この文書 (`{hdir}/HANDOFF.md`) 末尾の「3. Gemini 作業ログ」に、やったこと・残っていることを追記する"
      " (Claude に戻すときに使います)。")
    w("")
    w("## 1. Claude による要約")
    w("")
    w(SUMMARY_BEGIN)
    w(summary if summary else SUMMARY_PLACEHOLDER)
    w(SUMMARY_END)
    w("")
    w("## 2. 自動スナップショット (会話ログと git から機械的に抽出)")
    w("")

    if data["first_prompt"]:
        w("### 最初の依頼")
        w("")
        w(quote(clip(data["first_prompt"], MAX_PROMPT_CHARS * 2)))
        w("")
    if data["compact_summary"]:
        w("### 会話の圧縮サマリー (Claude Code の自動 compact より)")
        w("")
        w("<details><summary>開く</summary>")
        w("")
        w(clip(data["compact_summary"], 6000))
        w("")
        w("</details>")
        w("")
    recent = data["prompts"][-8:]
    if len(data["prompts"]) > 1:
        w(f"### 最近のユーザーの発言 (古い順、全 {len(data['prompts'])} 件中 直近 {len(recent)} 件)")
        w("")
        for i, p in enumerate(recent, 1):
            w(f"**{i}.**")
            w(quote(clip(p, MAX_PROMPT_CHARS)))
            w("")
    replies = [t for t in data["turn_replies"] if t]
    if replies:
        w("### Claude の最後の応答")
        w("")
        w(quote(clip("\n\n".join(replies[-1]), MAX_REPLY_CHARS, keep="tail")))
        w("")

    tasks = data["tasks"]
    todos = data["todos"]
    mark = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}
    if tasks:
        w("### タスクリスト (最新状態。[~] = 作業中)")
        w("")
        for tid, t in tasks.items():
            if t.get("status") == "deleted":
                continue
            w(f"- {mark.get(t.get('status'), '[ ]')} #{tid} {t.get('subject')}")
        w("")
    elif todos:
        w("### TODO リスト (最新状態。[~] = 作業中)")
        w("")
        for t in todos:
            if isinstance(t, dict):
                w(f"- {mark.get(t.get('status'), '[ ]')} {t.get('content') or t.get('subject') or ''}")
        w("")

    if data["files"]:
        w("### Claude が編集・作成したファイル")
        w("")
        for p, tool in list(data["files"].items())[-40:]:
            rel = os.path.relpath(p, root) if os.path.isabs(p) else p
            if rel.startswith(".."):
                rel = p  # プロジェクト外のファイルは絶対パスで
            w(f"- `{rel}` ({tool})")
        w("")
    if data["commands"]:
        w("### 最近実行したコマンド (直近 15 件)")
        w("")
        w(fence("\n".join(clip(c, 300).replace("\n", " ⏎ ") for c in data["commands"][-15:]), "bash"))
        w("")

    if git:
        w("### Git の状態")
        w("")
        w("**git status --short**")
        w("")
        w(fence(git["status"] or "(変更なし)"))
        w("")
        if git["stat"]:
            w("**git diff HEAD --stat**")
            w("")
            w(fence(git["stat"]))
            w("")
        if git["log"]:
            w("**直近のコミット**")
            w("")
            w(fence(git["log"]))
            w("")
        if git["diff"]:
            w(f"<details><summary>未コミットの差分 (最大 {MAX_DIFF_CHARS} 文字)</summary>")
            w("")
            w(fence(clip(git["diff"], MAX_DIFF_CHARS), "diff"))
            w("")
            w("</details>")
            w("")
    else:
        w("_(git リポジトリではないため、ファイルの差分は含まれていません)_")
        w("")

    w("## 3. Gemini 作業ログ")
    w("")
    w(GEMINI_LOG_BEGIN)
    w(gemini_log if gemini_log else GEMINI_LOG_PLACEHOLDER)
    w(GEMINI_LOG_END)
    w("")
    return "\n".join(out)


def update_gemini_md(root, cfg):
    path = os.path.join(root, "GEMINI.md")
    rel = cfg["handoff_dir"].strip("/")
    block = (f"{GEMINI_MD_BEGIN}\n"
             f"## Claude Code からの引き継ぎ\n"
             f"Claude Code が使用上限の直前に保存した引き継ぎ資料です。作業を再開する前に必ず読むこと。\n\n"
             f"@./{rel}/HANDOFF.md\n"
             f"{GEMINI_MD_END}\n")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    if GEMINI_MD_BEGIN in text and GEMINI_MD_END in text:
        return
    new = (text.rstrip() + "\n\n" + block) if text.strip() else block
    write_text_atomic(path, new)


def _prune_history(hist_dir, keep):
    files = sorted(glob.glob(os.path.join(hist_dir, "HANDOFF-*.md")))
    for p in files[:-keep] if keep > 0 else []:
        try:
            os.remove(p)
        except OSError:
            pass


def create_handoff(cwd=None, transcript=None, session_id=None, reason="手動で作成",
                   archive=True, cfg=None):
    """引き継ぎファイルを書き出してパスを返す。"""
    cfg = cfg or load_config()
    root = project_root(cwd)
    transcript = transcript or find_transcript(session_id, cwd or root)
    hdir = os.path.join(root, cfg["handoff_dir"])
    path = os.path.join(hdir, "HANDOFF.md")
    try:
        with open(path, encoding="utf-8") as f:
            prev = f.read()
    except OSError:
        prev = None
    text = render(root, transcript, session_id, reason, cfg, prev)
    write_text_atomic(path, text)
    if archive:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        hist = os.path.join(hdir, "history")
        write_text_atomic(os.path.join(hist, f"HANDOFF-{stamp}.md"), text)
        _prune_history(hist, int(cfg.get("history_keep", 20)))
    if cfg.get("update_gemini_md"):
        try:
            update_gemini_md(root, cfg)
        except OSError:
            pass
    return path


# ---------------------------------------------------------------- usage helpers (statusline / hooks)

def usage_windows(status_input, cfg):
    """[(name, used_pct, resets_at)] を返す。"""
    rl = status_input.get("rate_limits") or {}
    out = []
    for name in cfg.get("windows", []):
        w = rl.get(name)
        if isinstance(w, dict) and isinstance(w.get("used_percentage"), (int, float)):
            out.append((name, float(w["used_percentage"]), w.get("resets_at")))
    return out


def pending_path(session_id):
    return os.path.join(STATE_DIR, "pending", f"{session_id or 'unknown'}.json")


def summary_instruction(path, root, headline=""):
    """Claude に要約セクションを書かせるための指示文。"""
    rel = os.path.relpath(path, root)
    return (
        (headline + "\n\n" if headline else "")
        + f"Gemini に作業を引き継げるよう、`{rel}` の `{SUMMARY_BEGIN}` と `{SUMMARY_END}` の間"
        " (今は仮の一文が入っています) だけを Edit ツールで書き換えてください。"
        "それ以外の部分は自動生成なので変更しないこと。\n"
        "書く内容 (Markdown、合計 60 行以内。会話を読んでいない人でも分かるよう具体的に):\n"
        "### 目的\n- ユーザーが最終的に達成したいこと\n"
        "### 完了したこと\n"
        "### 進行中の作業と現在の状態\n- どのファイルのどこまで進んだか、テスト・動作確認の状況\n"
        "### 次にやること\n- 再開してすぐ実行できる具体的な手順 (番号付き)\n"
        "### 注意点・決定事項\n- 採用/却下した方針とその理由、ハマった点、ユーザーの好み\n\n"
        "書き終えたら新しい作業は始めず、ユーザーに"
        f"「Gemini 用の引き継ぎを保存しました: {rel} (`gemini-resume` で Gemini を起動できます)」"
        "と一言伝えて終了してください。"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude Code の作業を Gemini 用に引き継ぎファイル化する")
    ap.add_argument("--session", help="Claude のセッション ID")
    ap.add_argument("--transcript", help="transcript JSONL のパス (省略時は自動検出)")
    ap.add_argument("--cwd", help="プロジェクトのディレクトリ (省略時はカレント)")
    ap.add_argument("--reason", default="手動で作成 (/handoff)")
    ap.add_argument("--no-archive", action="store_true")
    a = ap.parse_args(argv)
    session = a.session if a.session and not a.session.startswith("${") else None
    path = create_handoff(a.cwd, a.transcript, session, a.reason, archive=not a.no_archive)
    print(path)


if __name__ == "__main__":
    main()
