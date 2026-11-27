#!/usr/bin/env python3
"""Claude Code hook (Stop / UserPromptSubmit / StopFailure)。

- Stop / UserPromptSubmit: statusline.py が「残り8%」を検知して保留中の印を
  置いていたら、Claude に引き継ぎファイルの要約セクションを書かせる (1 回だけ)。
- StopFailure (matcher: rate_limit): 使用上限で止まった瞬間に、
  スナップショットを最新の状態で保存し直す (Claude の要約は保持される)。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff as H  # noqa: E402


def _ensure_handoff(pend, session_id):
    """statusline がバックグラウンドで作っている途中なら、ここで作り切る。"""
    path = pend.get("handoff_path")
    created = pend.get("created", 0)
    for _ in range(20):  # 最大 ~4 秒待つ
        if path and os.path.exists(path) and os.path.getmtime(path) >= created - 1:
            return path
        time.sleep(0.2)
    return H.create_handoff(pend.get("cwd"), pend.get("transcript"), session_id,
                            reason=f"Claude の使用上限 ({pend.get('window')}) が残り {pend.get('remaining')}%")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    event = data.get("hook_event_name")
    session_id = data.get("session_id")

    if event == "StopFailure":
        if data.get("error", "rate_limit") == "rate_limit":
            H.create_handoff(data.get("cwd"), data.get("transcript_path"), session_id,
                             reason="Claude の使用上限に到達して停止 (ロック)")
        return

    if event not in ("Stop", "UserPromptSubmit"):
        return
    if event == "Stop" and data.get("stop_hook_active"):
        return

    ppath = H.pending_path(session_id)
    pend = H.read_json(ppath)
    if not pend:
        return
    try:
        os.remove(ppath)  # 1 回だけ頼む
    except OSError:
        return  # 他の hook が先に処理した

    path = _ensure_handoff(pend, session_id)
    root = pend.get("root") or H.project_root(data.get("cwd"))
    headline = (f"⚠️ Claude の使用上限 ({pend.get('window')}) が残り約 {pend.get('remaining')}% です"
                f" (リセット {H.fmt_time(pend.get('resets_at'))})。"
                "上限でロックされる前に、作業をここで区切って Gemini への引き継ぎを仕上げます。"
                f"会話ログと git から自動スナップショットはすでに `{os.path.relpath(path, root)}` に保存済みです。")
    instruction = H.summary_instruction(path, root, headline)
    user_msg = (f"⚠ Claude の使用上限が残り約 {pend.get('remaining')}% — "
                f"Gemini 用の引き継ぎを {os.path.relpath(path, root)} に保存しました")

    if event == "Stop":
        out = {"decision": "block", "reason": instruction, "systemMessage": user_msg}
    else:
        out = {
            "systemMessage": user_msg,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": instruction
                + "\n(ユーザーの新しい依頼は、要約を書き終えてから、残り使用量に余裕があれば扱うこと)",
            },
        }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # hook の失敗で Claude Code を止めない
        print(f"gemini-handoff hook error: {e}", file=sys.stderr)
        sys.exit(0)
