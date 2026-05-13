#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from runtime_state import STATE_PATH, read_state


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
CONFIG_EXAMPLE = ROOT / "config.example.json"


def run(args: list[str]) -> int:
    print("+", " ".join(args))
    return subprocess.call(args, cwd=ROOT.parent)


def check_gh_auth() -> tuple[bool, str]:
    if not shutil.which("gh"):
        return False, "GitHub CLI `gh` is not installed."
    proc = subprocess.run(
        ["gh", "auth", "status"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode == 0, proc.stdout.strip()


def cmd_init(_: argparse.Namespace) -> int:
    if not CONFIG.exists():
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG)
        print(f"Created {CONFIG}")
    else:
        print(f"Config already exists: {CONFIG}")
    (ROOT / "runtime").mkdir(parents=True, exist_ok=True)
    print(f"Runtime directory ready: {ROOT / 'runtime'}")
    return 0


def cmd_once(args: argparse.Namespace) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"), "--once"]
    if args.no_scan:
        command.append("--no-scan")
    return run(command)


def cmd_loop(args: argparse.Namespace) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"), "--loop"]
    if args.interval:
        command.extend(["--interval", str(args.interval)])
    if args.no_scan:
        command.append("--no-scan")
    return run(command)


def cmd_web(args: argparse.Namespace) -> int:
    return run(
        [
            sys.executable,
            str(ROOT / "scripts" / "web_dashboard.py"),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ]
    )


def cmd_status(_: argparse.Namespace) -> int:
    state = read_state(STATE_PATH)
    earnings = state.get("earnings", {})
    progress = state.get("progress", {})
    print(json.dumps(
        {
            "updated_at": state.get("updated_at"),
            "health": state.get("health"),
            "next_action": state.get("next_action"),
            "wallet": state.get("wallet"),
            "earnings": earnings,
            "progress": progress,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def cmd_guide(_: argparse.Namespace) -> int:
    print(
        """
Bounty Autopilot 新手引导

1. 先检查环境
   python3 scripts/bountyctl.py doctor

2. 初始化配置
   python3 scripts/bountyctl.py init

3. 如果提示 GitHub 未登录，按引导登录
   python3 scripts/bountyctl.py login

4. 运行一次完整自动化
   python3 scripts/bountyctl.py once

5. 开启 24 小时循环
   python3 scripts/bountyctl.py loop

6. 打开中文监工面板
   python3 scripts/bountyctl.py web --port 8787
   然后访问 http://127.0.0.1:8787

7. 给 Codex 桌面安装定时自动化
   python3 scripts/bountyctl.py install-automation

8. 同一个 GitHub 账号换电脑时同步历史
   旧电脑：python3 scripts/bountyctl.py sync-push
   新电脑：python3 scripts/bountyctl.py sync-pull

当前自动化边界：
- 会自动：扫描、选择低风险断链任务、修复、push 分支、开 PR、发 claim 评论、监控状态、刷新到账。
- 不会自动：注册钱包、配置收款、提现、转账、税务/银行卡/交易所操作。

如果环境不满足技术标准：
- 使用 environment-completion-engineer 补齐环境。
- 不允许降低验收标准或跳过必要测试。
""".strip()
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    state = read_state(STATE_PATH)
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported state to {out}")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    checks = []
    checks.append(("python", sys.version.split()[0]))
    for binary in ("gh", "curl"):
        path = shutil.which(binary)
        checks.append((binary, path or "missing"))
    checks.append(("config", str(CONFIG if CONFIG.exists() else CONFIG_EXAMPLE)))
    checks.append(("state", str(STATE_PATH if STATE_PATH.exists() else "not created yet")))
    gh_ok, gh_message = check_gh_auth()
    checks.append(("gh_auth", "ok" if gh_ok else "login required"))
    for name, value in checks:
        print(f"{name}: {value}")
    missing = [name for name, value in checks if value == "missing"]
    if missing:
        print(f"Missing required tools: {', '.join(missing)}")
        return 1
    if not gh_ok:
        print("\nGitHub login is required before this workflow can create branches, PRs, or comments.")
        print("Run:")
        print("  python3 scripts/bountyctl.py login")
        print("\nGitHub CLI output:")
        print(gh_message)
        return 1
    return 0


def cmd_login(_: argparse.Namespace) -> int:
    if not shutil.which("gh"):
        print("GitHub CLI `gh` is required.")
        print("macOS install:")
        print("  brew install gh")
        return 1
    ok, message = check_gh_auth()
    if ok:
        print("GitHub is already authenticated.")
        print(message)
        return 0
    print("GitHub login is required.")
    print("A browser/device-code flow may open. Follow GitHub's prompts, then rerun `doctor`.")
    code = subprocess.call(["gh", "auth", "login", "--web"], cwd=ROOT)
    if code == 0:
        subprocess.call(["gh", "auth", "setup-git"], cwd=ROOT)
    return code


def cmd_install_automation(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "install_codex_automation.py"),
        "--interval-hours",
        str(args.interval_hours),
    ]
    return run(command)


def cmd_sync(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "account_sync.py"),
        args.sync_command,
        "--repo",
        args.repo,
    ]
    if args.owner:
        command.extend(["--owner", args.owner])
    return run(command)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounty autopilot control CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.set_defaults(func=cmd_init)

    once = sub.add_parser("once")
    once.add_argument("--no-scan", action="store_true")
    once.set_defaults(func=cmd_once)

    loop = sub.add_parser("loop")
    loop.add_argument("--interval", type=int, default=0)
    loop.add_argument("--no-scan", action="store_true")
    loop.set_defaults(func=cmd_loop)

    web = sub.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8787)
    web.set_defaults(func=cmd_web)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    guide = sub.add_parser("guide")
    guide.set_defaults(func=cmd_guide)

    export = sub.add_parser("export")
    export.add_argument("--output", default=str(ROOT / "runtime" / "state-export.json"))
    export.set_defaults(func=cmd_export)

    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)

    login = sub.add_parser("login")
    login.set_defaults(func=cmd_login)

    install_automation = sub.add_parser("install-automation")
    install_automation.add_argument("--interval-hours", type=int, default=1)
    install_automation.set_defaults(func=cmd_install_automation)

    for name, sync_command in (
        ("sync-push", "push"),
        ("sync-pull", "pull"),
        ("sync-status", "status"),
    ):
        sync = sub.add_parser(name)
        sync.add_argument("--repo", default="codex-bounty-autopilot-state")
        sync.add_argument("--owner", default="")
        sync.set_defaults(func=cmd_sync, sync_command=sync_command)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
