# Codex Bounty Autopilot

Codex Bounty Autopilot 是一个可复用的 Codex 赏金工作流：自动扫描公开 bounty，筛选低风险任务，运行验证，准备或提交小型 PR，跟踪 review / merge / payout，并提供中文 Web 面板监工。

默认发布版是安全模式：下载后可以扫描、监控、恢复状态和安装 Codex 自动化；只有用户完成 GitHub 登录、配置公开收款 ID，并显式开启自动提交后，才会自动开 PR 或发 claim 评论。钱包注册、提现、转账、交易所、银行卡和税务设置永远不自动执行。

## 一句安装

```bash
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

这条命令会：

- 克隆或更新 `~/codex-bounty-autopilot`
- 创建本机 `config.json` 和 `runtime/`
- 检查 Python、GitHub CLI、curl 和 GitHub 登录状态
- 引导用户完成 GitHub 登录
- 尝试从私有状态仓库恢复同账号历史进度
- 安装本机 Codex 自动化

安装副作用：

- 本机项目目录：`~/codex-bounty-autopilot`
- 本机配置和运行状态：`config.json`、`runtime/`
- 本机 Codex 自动化：`~/.codex/automations/bounty-autopilot-*`
- 同账号状态同步仓库：`codex-bounty-autopilot-state`，默认 private

自定义安装目录：

```bash
export CODEX_BOUNTY_HOME="$HOME/tools/codex-bounty-autopilot"
curl -fsSL https://raw.githubusercontent.com/galanime/codex-bounty-autopilot/main/bootstrap.sh | bash
```

给 Codex 的一句话：

```text
安装并初始化 codex-bounty-autopilot：自动下载仓库、检查环境、引导我完成 GitHub 登录、如果有历史状态就 sync-pull 恢复、安装 Codex 自动化；不要自动注册钱包、提现、连接交易所、配置银行卡或税务。
```

## 手动安装

```bash
git clone https://github.com/galanime/codex-bounty-autopilot.git
cd codex-bounty-autopilot
python3 scripts/bountyctl.py setup
```

如果提示 GitHub 未登录：

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py setup
```

## 常用命令

```bash
python3 scripts/bountyctl.py setup
python3 scripts/bountyctl.py doctor
python3 scripts/bountyctl.py once
python3 scripts/bountyctl.py loop
python3 scripts/bountyctl.py web --port 8787
python3 scripts/bountyctl.py status
python3 scripts/bountyctl.py install-automation
python3 scripts/bountyctl.py sync-push
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py sync-status
```

Web 面板：

```text
http://127.0.0.1:8787
```

不要把 Web 面板绑定到公网地址。面板会展示本机工作流状态、公开收款 ID、PR 进度和金额估算。默认命令只监听 `127.0.0.1`。

## 自动化边界

允许自动化：

- 扫描候选 bounty
- 刷新 GitHub issue / PR / wallet 状态
- 选择低风险断链修复
- 修改小范围文档或链接问题
- 运行验证
- 在显式配置允许后 push 分支、打开 PR、发 claim 评论
- 更新本地 dashboard 状态
- 安装本机 Codex 自动化

不会自动化：

- 注册钱包
- 提现、转账、跨链桥、交易所操作
- 银行卡、支付账户、税务设置
- 输入账号密码、验证码、私钥、助记词、keystore
- 高风险安全、资金或账号动作

## 跨电脑同步

代码仓库只放通用代码。个人运行状态会同步到同一 GitHub 账号下的私有仓库：

```text
codex-bounty-autopilot-state
```

旧电脑推送状态：

```bash
python3 scripts/bountyctl.py sync-push
```

新电脑恢复状态：

```bash
python3 scripts/bountyctl.py login
python3 scripts/bountyctl.py sync-pull
python3 scripts/bountyctl.py once --no-scan
```

同步内容包括：

- 公开收款 ID
- 已跟踪 PR
- PR 状态
- 已提交 / 已通过 / 已合并 / 已拒绝数量
- 待到账和已到账金额
- 下一步动作

请保持状态仓库为 private。

状态仓库可能包含公开收款 ID、GitHub 登录名、跟踪 PR、进度、金额估算和下一步动作。它不会保存密码、私钥、助记词、验证码或 API token。

## 隐私与发布安全

公开仓库不会提交这些本机文件：

- `config.json`
- `runtime/`
- `outputs/`
- `candidate_review.md`
- `earnings_ledger.md`
- `ops_status.md`
- `.env`
- Python 缓存和本机临时文件

`config.example.json` 是脱敏模板，默认没有钱包 ID、PR 历史或收益状态。

## Codex Skill 入口

仓库包含 [SKILL.md](SKILL.md)，Codex 可以把它当作安装和运行说明读取。关键规则是：

- 优先使用一键 bootstrap
- 缺 GitHub 登录时引导用户登录
- 同账号换电脑时自动尝试 `sync-pull`
- 默认安装 Codex 自动化
- 严格禁止钱包、提现、交易所、银行卡、税务和密钥类自动化

## 文件结构

- `bootstrap.sh`: 一句命令安装入口。
- `SKILL.md`: Codex 可读的安装和安全边界说明。
- `scripts/bountyctl.py`: 统一 CLI。
- `scripts/autopilot.py`: 扫描、刷新、自动提交、记账主循环。
- `scripts/auto_link_submitter.py`: 低风险断链修复自动提交器。
- `scripts/account_sync.py`: 同 GitHub 账号跨电脑状态同步。
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
