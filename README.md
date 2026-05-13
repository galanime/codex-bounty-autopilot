# Codex Bounty Autopilot

一个可复用的 Codex 赏金工作流：扫描公开 bounty，筛选低风险任务，运行验证，提交小型 PR，跟踪 review / merge / payout，并用中文 Web 面板监工。

默认发布版是安全模式：下载即可扫描、监控和准备材料；只有用户配置 GitHub 登录、钱包 ID，并显式开启自动提交后，才会自动开 PR / 发 claim。钱包注册、提现、银行卡、税务、交易所操作永远不自动执行。

## 30 秒开始

一句命令安装、更新、检查环境、引导 GitHub 登录、恢复同账号历史状态，并安装 Codex 自动化：

```bash
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

如果你想把项目放到自定义目录：

```bash
export CODEX_BOUNTY_HOME="$HOME/tools/codex-bounty-autopilot"
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

给 Codex 的一句话：

```text
安装并初始化 codex-bounty-autopilot：自动下载仓库、检查环境、引导我完成 GitHub 登录、如果有历史状态就 sync-pull 恢复、安装 Codex 自动化；不要自动注册钱包、提现、连接交易所、配置银行卡或税务。
```

手动安装方式：

```bash
git clone https://github.com/galanime/codex-bounty-autopilot.git
cd codex-bounty-autopilot
python3 scripts/bountyctl.py setup
```

如果提示 GitHub 未登录：

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py doctor
```

运行一次：

```bash
python3 scripts/bountyctl.py once
```

启动长期循环：

```bash
python3 scripts/bountyctl.py loop
```

打开中文监工面板：

```bash
python3 scripts/bountyctl.py web --port 8787
```

访问：

```text
http://127.0.0.1:8787
```

## 复用到别人的 Codex

1. Clone 仓库。
2. 运行 `python3 scripts/bountyctl.py setup`。
3. 如果 setup 提示 GitHub 未登录，按提示完成 `python3 scripts/bountyctl.py login`，然后重新运行 setup。
4. 编辑本机 `config.json`：
   - `wallet_id`: 自己的公开收款 ID。
   - `automation.external_actions`: 默认 `manual_confirm`。
   - 若确认要自动提交低风险断链修复，改为 `auto_submit_except_wallet_withdrawal`，并把 `auto_submit_low_risk_link_fixes` 设为 `true`。
5. setup 默认会安装本机 Codex 自动化；如需重装可运行 `python3 scripts/bountyctl.py install-automation`。

`config.json`、`runtime/`、`outputs/` 都被 `.gitignore` 排除，不会把个人钱包、运行记录、候选报告发布出去。

## 同仓库同步规则

如果 GitHub 上已经存在同名仓库，后续发布必须同步到同一个仓库，不要新建重复仓库。

推荐仓库名：

```text
codex-bounty-autopilot
```

同步策略：

- 已存在 `origin`：直接 `git pull --rebase` 后提交并 `git push`。
- 本地没有仓库但 GitHub 已存在：先 `gh repo clone OWNER/codex-bounty-autopilot`，再覆盖同步项目文件。
- GitHub 不存在：才创建新仓库。

发布时不要提交：

- `config.json`
- `runtime/`
- `outputs/`
- 本机钱包、收益账本、候选报告、缓存文件

## 同一 GitHub 账号跨电脑同步进度

项目代码仓库只放通用代码；你的完成记录、跟踪 PR、到账状态会同步到另一个**私有**状态仓库：

```text
codex-bounty-autopilot-state
```

旧电脑推送状态：

```bash
python3 scripts/bountyctl.py sync-push
```

新电脑登录同一个 GitHub 账号后拉回状态：

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py once --no-scan
```

查看云端状态：

```bash
python3 scripts/bountyctl.py sync-status
```

同步内容包括：

- `wallet_id`
- 已跟踪 PR
- PR 状态
- 已提交 / 已通过 / 已合并 / 已拒绝数量
- 待到账和已到账金额
- 下一步动作

这个状态仓库默认是 private。不要把它改成 public。

## 自动添加 Codex 自动化

```bash
python3 scripts/bountyctl.py install-automation --interval-hours 1
```

这会写入：

- `~/.codex/automations/bounty-autopilot-run/automation.toml`
- `~/.codex/automations/bounty-autopilot-monitor/automation.toml`

如果 Codex UI 没立即显示，重启 Codex 桌面应用即可。

## 登录引导

这个项目需要 GitHub CLI 来读 PR、创建分支、打开 PR、发 claim 评论。

检查：

```bash
python3 scripts/bountyctl.py doctor
```

如果未登录，系统会提示：

```bash
python3 scripts/bountyctl.py login
```

登录完成后会运行 `gh auth setup-git`，让 `git push` 可用。

## 自动化边界

允许自动化：

- 扫描候选 bounty
- 刷新 PR / issue / wallet 状态
- 选择低风险断链修复
- 修改单文件小 diff
- 运行验证
- push 分支
- 打开 PR
- 发 bounty claim 评论
- 更新本地 dashboard 状态

永远不自动化：

- 注册钱包
- 提现
- 转账
- 连接交易所
- 配置银行卡、税务、支付账户
- 输入账号密码、验证码、私钥、助记词

## 主要命令

```bash
python3 scripts/bountyctl.py init
python3 scripts/bountyctl.py doctor
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py once
python3 scripts/bountyctl.py loop
python3 scripts/bountyctl.py web --port 8787
python3 scripts/bountyctl.py status
python3 scripts/bountyctl.py install-automation
python3 scripts/bountyctl.py sync-push
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py sync-status
```

## 文件结构

- `scripts/bountyctl.py`: 统一 CLI。
- `scripts/autopilot.py`: 扫描、刷新、自动提交、记账主循环。
- `scripts/auto_link_submitter.py`: 低风险断链修复自动提交器。
- `scripts/install_codex_automation.py`: 安装 Codex 桌面自动化。
- `scripts/web_dashboard.py`: 本地中文监工面板服务。
- `web/`: dashboard 前端。
- `config.example.json`: 可复制的默认配置。
- `PORTABLE_RUNBOOK.md`: 迁移到其他电脑的步骤。
- `TECHNICAL_STANDARD.md`: 不可降低的技术标准。

## 验证

```bash
python3 scripts/validate_system.py
python3 -m py_compile scripts/*.py
```

## 收钱说明

面板里的金额分三类：

- `已到账`: 钱包接口确认收到的 RTC。
- `已通过待到账`: PR 已获认可/通过，但还没 merge 或发放。
- `已提交待审核`: 已开 PR / claim，尚未通过。

不要把 pending 当成已到账。通常要等 PR 被 maintainer merge / accept 后，才适合在 bounty issue 下礼貌跟进付款。
