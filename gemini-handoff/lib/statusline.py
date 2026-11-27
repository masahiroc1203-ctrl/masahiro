#!/usr/bin/env python3
"""Claude Code の statusLine コマンド。

1. 使用上限 (rate_limits) の残り%を表示する。
2. 残りが threshold_remaining 以下になったら、Gemini 用の引き継ぎファイルを
   バックグラウンドで作り、Stop / UserPromptSubmit hook が Claude に要約を
   書かせられるよう「保留中」の印を置く。
3. final_threshold_remaining 以下になったら、スナップショットをもう一度更新する。

既存の statusLine を使っていた場合 (config.json の wrapped_statusline) は、
その出力をそのまま表示し、警告だけを 2 行目に足す。
"""
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff as H  # noqa: E402

RED, YELLOW, DIM, RESET = "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _fire_once(key):
    """key ごとに一度だけ True を返す (並行して呼ばれても安全)。"""
    d = os.path.join(H.STATE_DIR, "fired")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, hashlib.sha1(key.encode()).hexdigest())
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(key)
    return True


def _already_fired(key):
    d = os.path.join(H.STATE_DIR, "fired")
    return os.path.exists(os.path.join(d, hashlib.sha1(key.encode()).hexdigest()))


def _prune_state():
    now = time.time()
    for sub, age in (("fired", 8 * 86400), ("pending", 2 * 86400)):
        d = os.path.join(H.STATE_DIR, sub)
        try:
            for name in os.listdir(d):
                p = os.path.join(d, name)
                if now - os.path.getmtime(p) > age:
                    os.remove(p)
        except OSError:
            pass


def _spawn_handoff(cwd, transcript, session_id, reason):
    log_dir = os.path.join(H.STATE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    cmd = [sys.executable, os.path.join(H.HERE, "handoff.py"), "--reason", reason]
    if cwd:
        cmd += ["--cwd", cwd]
    if transcript:
        cmd += ["--transcript", transcript]
    if session_id:
        cmd += ["--session", session_id]
    with open(os.path.join(log_dir, "handoff.log"), "a") as log:
        log.write(f"\n[{time.strftime('%F %T')}] {reason}\n")
        log.flush()
        kwargs = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
        if os.name == "posix":
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)


def check_usage(data, cfg):
    """しきい値の判定と引き継ぎの起動。表示用の警告文を返す。"""
    windows = H.usage_windows(data, cfg)
    if not windows:
        return ""
    name, used, resets_at = max(windows, key=lambda w: w[1])
    remaining = max(0.0, 100.0 - used)
    session_id = data.get("session_id")
    transcript = data.get("transcript_path")
    ws = data.get("workspace") or {}
    cwd = ws.get("project_dir") or ws.get("current_dir") or data.get("cwd")
    root = H.project_root(cwd)
    label = H.WINDOW_LABELS.get(name, name)
    # resets_at が数秒揺れても同じ枠とみなす (10 分単位に丸める)
    try:
        bucket = int(round(float(resets_at) / 600.0))
    except (TypeError, ValueError):
        bucket = resets_at
    key = f"{root}|{name}|{bucket}"
    rel = os.path.join(cfg["handoff_dir"], "HANDOFF.md")

    th = float(cfg.get("threshold_remaining", 8))
    final_th = float(cfg.get("final_threshold_remaining", 3))

    if remaining <= th and _fire_once(key + "|warn"):
        _prune_state()
        reason = (f"Claude の使用上限 ({label}) が残り {remaining:.0f}% "
                  f"(リセット {H.fmt_time(resets_at)})")
        _spawn_handoff(cwd, transcript, session_id, reason)
        if cfg.get("ask_claude_summary", True) and session_id:
            H.write_json(H.pending_path(session_id), {
                "created": time.time(),
                "handoff_path": os.path.join(root, rel),
                "root": root,
                "remaining": round(remaining, 1),
                "window": label,
                "resets_at": resets_at,
                "transcript": transcript,
                "cwd": cwd,
            })
    elif remaining <= final_th and _fire_once(key + "|final"):
        reason = (f"Claude の使用上限 ({label}) が残り {remaining:.0f}% — 最終スナップショット "
                  f"(リセット {H.fmt_time(resets_at)})")
        _spawn_handoff(cwd, transcript, session_id, reason)

    if _already_fired(key + "|warn"):
        return f"{RED}⚠ 上限間近: Gemini 用の引き継ぎを保存済み → {rel}{RESET}"
    return ""


def default_line(data, cfg, note):
    parts = []
    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(model)
    ws = data.get("workspace") or {}
    d = ws.get("current_dir") or data.get("cwd")
    if d:
        parts.append(os.path.basename(d.rstrip("/")) or d)
    ctx = (data.get("context_window") or {}).get("used_percentage")
    if isinstance(ctx, (int, float)):
        parts.append(f"ctx {ctx:.0f}%")
    th = float(cfg.get("threshold_remaining", 8))
    for name, used, resets_at in H.usage_windows(data, cfg):
        remaining = max(0.0, 100.0 - used)
        color = RED if remaining <= th else YELLOW if remaining <= 25 else ""
        short = {"five_hour": "5h", "seven_day": "週", "spend_limit": "$"}.get(name, name)
        parts.append(f"{color}{short} 残{remaining:.0f}%{RESET if color else ''}"
                     f"{DIM}({H.fmt_time(resets_at)}){RESET}")
    line = " · ".join(parts)
    return line + ("\n" + note if note else "")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    cfg = H.load_config()
    try:
        note = check_usage(data, cfg)
    except Exception as e:  # status line は絶対に落とさない
        note = f"{DIM}(gemini-handoff error: {e}){RESET}"

    wrapped = (cfg.get("wrapped_statusline") or "").strip()
    if wrapped:
        try:
            p = subprocess.run(wrapped, shell=True, input=raw, capture_output=True,
                               text=True, timeout=10)
            out = p.stdout.rstrip("\n")
        except (OSError, subprocess.SubprocessError):
            out = ""
        print(out + ("\n" + note if note else ""))
    else:
        print(default_line(data, cfg, note))


if __name__ == "__main__":
    main()
