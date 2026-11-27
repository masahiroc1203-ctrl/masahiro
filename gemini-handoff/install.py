#!/usr/bin/env python3
"""gemini-handoff を ~/.claude にインストール / アンインストールする。

    python3 install.py             # インストール (何度実行しても安全)
    python3 install.py --uninstall # 元に戻す
    python3 install.py --threshold 10   # しきい値 (残り%) を変えてインストール
"""
import argparse
import datetime as _dt
import json
import os
import shutil
import stat
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
DEST = os.path.join(CLAUDE_DIR, "gemini-handoff")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
COMMAND = os.path.join(CLAUDE_DIR, "commands", "handoff.md")
MARK = "gemini-handoff"  # 自分が追加した設定を見分ける目印 (コマンド文字列に含まれる)


def python_cmd():
    return "python3" if shutil.which("python3") else sys.executable


def q(path):
    return '"' + path.replace('"', '\\"') + '"'


def load_settings():
    if not os.path.exists(SETTINGS):
        return {}
    with open(SETTINGS, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except ValueError as e:
        sys.exit(f"エラー: {SETTINGS} が正しい JSON ではありません ({e})。直してから再実行してください。")


def save_settings(s):
    if os.path.exists(SETTINGS):
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(SETTINGS, f"{SETTINGS}.bak-{stamp}")
        print(f"  バックアップ: {SETTINGS}.bak-{stamp}")
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, SETTINGS)


def strip_our_hooks(hooks):
    """hooks から自分のエントリだけを取り除く。"""
    for event in list(hooks):
        groups = []
        for g in hooks[event] or []:
            hs = [h for h in g.get("hooks", []) if MARK not in str(h.get("command", ""))]
            if hs:
                groups.append({**g, "hooks": hs})
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    return hooks


def install(args):
    print(f"インストール先: {DEST}")
    os.makedirs(os.path.join(DEST, "state"), exist_ok=True)
    for name in ("handoff.py", "statusline.py", "hook.py"):
        shutil.copy2(os.path.join(SRC, "lib", name), os.path.join(DEST, name))
    resume = os.path.join(DEST, "gemini-resume")
    shutil.copy2(os.path.join(SRC, "bin", "gemini-resume"), resume)
    os.chmod(resume, os.stat(resume).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # スラッシュコマンド /handoff
    os.makedirs(os.path.dirname(COMMAND), exist_ok=True)
    with open(os.path.join(SRC, "commands", "handoff.md"), encoding="utf-8") as f:
        body = f.read().replace("__HANDOFF_HOME__", DEST)
    if os.path.exists(COMMAND):
        with open(COMMAND, encoding="utf-8") as f:
            if MARK not in f.read():
                shutil.copy2(COMMAND, COMMAND + ".bak")
                print(f"  既存の {COMMAND} を .bak に退避しました")
    with open(COMMAND, "w", encoding="utf-8") as f:
        f.write(body)

    settings = load_settings()
    py = python_cmd()
    status_cmd = f"{py} {q(os.path.join(DEST, 'statusline.py'))}"
    hook_cmd = f"{py} {q(os.path.join(DEST, 'hook.py'))}"

    # config.json (既存の設定は残す)
    cfg_path = os.path.join(DEST, "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        sys.path.insert(0, os.path.join(SRC, "lib"))
        import handoff
        cfg = dict(handoff.DEFAULT_CONFIG)
    old = settings.get("statusLine") or {}
    old_cmd = old.get("command", "") if isinstance(old, dict) else ""
    if old_cmd and MARK not in old_cmd:
        cfg["wrapped_statusline"] = old_cmd
        print(f"  既存の statusLine を引き継ぎます: {old_cmd}")
    if args.threshold is not None:
        cfg["threshold_remaining"] = args.threshold
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # settings.json
    new_status = {"type": "command", "command": status_cmd}
    if isinstance(old, dict) and old.get("padding") is not None:
        new_status["padding"] = old["padding"]
    settings["statusLine"] = new_status
    hooks = strip_our_hooks(settings.get("hooks") or {})
    entry = {"type": "command", "command": hook_cmd, "timeout": 30}
    hooks.setdefault("Stop", []).append({"hooks": [entry]})
    hooks.setdefault("UserPromptSubmit", []).append({"hooks": [entry]})
    hooks.setdefault("StopFailure", []).append({"matcher": "rate_limit", "hooks": [dict(entry)]})
    settings["hooks"] = hooks
    save_settings(settings)

    # gemini-resume を PATH へ
    linked = None
    for d in (os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin")):
        if os.path.isdir(d) and d in os.environ.get("PATH", "").split(os.pathsep):
            link = os.path.join(d, "gemini-resume")
            if os.path.islink(link) or not os.path.exists(link):
                if os.path.islink(link):
                    os.remove(link)
                os.symlink(resume, link)
                linked = link
            break

    print("\n✅ インストール完了")
    print(f"  - 残り {cfg['threshold_remaining']}% 以下で自動的に引き継ぎを保存します"
          f" (設定: {cfg_path})")
    print("  - Claude Code を再起動するか、/hooks を一度開くと有効になります")
    print("  - 手動で保存: Claude Code で /handoff")
    if linked:
        print(f"  - Gemini で再開: gemini-resume   ({linked} にリンクしました)")
    else:
        print(f"  - Gemini で再開: {resume}")
        print(f"      (PATH に置くなら: ln -s {q(resume)} ~/.local/bin/gemini-resume)")


def uninstall(_args):
    settings = load_settings()
    cfg = {}
    try:
        with open(os.path.join(DEST, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        pass
    sl = settings.get("statusLine") or {}
    if isinstance(sl, dict) and MARK in sl.get("command", ""):
        if cfg.get("wrapped_statusline"):
            restored = {"type": "command", "command": cfg["wrapped_statusline"]}
            if sl.get("padding") is not None:
                restored["padding"] = sl["padding"]
            settings["statusLine"] = restored
            print(f"  statusLine を元に戻しました: {cfg['wrapped_statusline']}")
        else:
            del settings["statusLine"]
    if "hooks" in settings:
        settings["hooks"] = strip_our_hooks(settings["hooks"])
        if not settings["hooks"]:
            del settings["hooks"]
    save_settings(settings)
    if os.path.exists(COMMAND):
        with open(COMMAND, encoding="utf-8") as f:
            ours = MARK in f.read()
        if ours:
            os.remove(COMMAND)
            if os.path.exists(COMMAND + ".bak"):
                os.replace(COMMAND + ".bak", COMMAND)
    for d in (os.path.expanduser("~/.local/bin"), os.path.expanduser("~/bin")):
        link = os.path.join(d, "gemini-resume")
        if os.path.islink(link) and MARK in os.readlink(link):
            os.remove(link)
    shutil.rmtree(DEST, ignore_errors=True)
    print("✅ アンインストールしました (各プロジェクトの .handoff/ は残しています)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--threshold", type=float, help="引き継ぎを作る残り%% (既定 8)")
    args = ap.parse_args()
    (uninstall if args.uninstall else install)(args)


if __name__ == "__main__":
    main()
