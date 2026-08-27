# Codex Efficiency Kit

一个可独立安装的 Codex 本地效率配置包，用于减少无关重构、重复探索和长任务中的上下文漂移。

> 版本：3.2.1。该项目是个人配置包，不是 OpenAI 官方产品或官方推荐配置。

## 功能

- 全局工程规则：优先最小完整改动、复用既有模式、限制无关重构，并使用最小相关验证。
- 定向工作流 skills：
  - `repo-explore`：追踪大型代码库中的调用链、状态流或生命周期；
  - `targeted-debug`：以可证伪假设定位具体故障；
  - `minimal-review`：对当前 diff 做有界、可执行的审查；
  - `sub-agent`：仅在用户显式要求时使用 Sol 规划/验收与 Terra 执行；
  - `context-handoff`：在上下文退化时创建同模型的新根任务继续工作。
- Context Guardian：通过 Codex hooks 记录 compaction、检测 compaction 后的重复工具操作，并在任务准备结束时提示必要的上下文交接。

## 独立性与边界

本仓库可单独安装：安装脚本和 Guardian 仅使用 Python 标准库，不需要任何旧版 Kit、第三方 Python 包或项目依赖。

它会修改当前 Codex home（默认 `~/.codex`）中的：

- `AGENTS.md`：只替换 `CODEX EFFICIENCY KIT` 标记区间；
- `skills/`：安装或更新本仓库提供的五个 skills；
- `context-guardian/`：安装 Guardian 脚本和默认配置；
- `hooks.json`：合并 Guardian 的 hooks，不删除非 Guardian hooks。

安装器在覆盖已有规则、skills 或 hooks 前会创建带时间戳的 `.bak-*` 备份；已有 Guardian `config.json` 不会被覆盖。

## 要求

- 已安装 Codex；
- Python 3（Windows 可使用 Python Launcher 的 `py -3`）；
- Codex hooks 已启用，并允许在 `/hooks` 中审核和信任本仓库新增的 hooks。

`context-handoff` 还需要运行环境提供第一方的“创建新任务 / 发送继续消息 / 查看任务状态”能力。没有这些能力时，它会明确报告 handoff blocked；不会用 fork、子智能体、Terra 或 Luna 冒充新的同模型根上下文。

## 安装

克隆仓库后运行安装器：

```bash
git clone https://github.com/yonghengbit/codex-efficiency-kit.git
cd codex-efficiency-kit
python3 install.py
```

Windows PowerShell：

```powershell
git clone https://github.com/yonghengbit/codex-efficiency-kit.git
cd codex-efficiency-kit
py -3 .\install.py
```

若 Codex home 不在默认位置：

```bash
python3 install.py --codex-home /path/to/.codex
```

安装完成后，打开 Codex 的 `/hooks`，审核并信任新增的 `PostCompact`、`Stop` 和 `PostToolUse` Guardian hooks，然后开始一个新任务。

## 使用

日常编码不需要显式调用 skill。全局规则会默认约束范围、探索和验证成本。

在需要特定流程时显式调用：

```text
@repo-explore
从 handle_request 开始，追踪请求进入 prefill batch 的最小调用链。
```

```text
@targeted-debug
这个请求在并发时首 token 变成 EOS。请从实际计算路径找 root cause。
```

```text
@minimal-review
review 当前 diff。
```

```text
$sub-agent
实现这个有边界的改动，完成 targeted validation。
```

`$sub-agent` 是显式委派；普通任务不会自动创建子智能体。

## Context Guardian 与 handoff

默认阈值位于 `~/.codex/context-guardian/config.json`：

```json
{
  "soft_compactions": 2,
  "hard_compactions": 3,
  "repeat_threshold": 3,
  "track_repetition_after_compaction": true
}
```

- `PostCompact` 记录当前会话的 compaction 次数；
- `PostToolUse` 在 compaction 后检测相同工具动作或路径是否反复出现；
- `Stop` 会在 soft/hard 阈值时阻止未完成任务直接结束，并要求执行 `context-handoff`。

交接仅在以下条件全部满足时才成功：

1. 已写入简洁的 `.codex/CODEX_HANDOFF.md`；
2. 已创建无历史复制的、同主模型的新根任务；
3. 新任务收到并开始执行 `NEXT_ACTION`；
4. 已通过任务状态确认新任务实际启动。

`fork_thread` 会复制已完成历史，因此不属于 fresh context。Context handoff 绝不会隐式改用 Terra、Luna、`$sub-agent` 或其他 worker。

## 查看状态

```bash
python3 ~/.codex/context-guardian/context_guardian.py --status
```

## 升级

在新版本目录再次运行同一安装命令即可。安装器会更新 Kit 自己管理的规则区间、skills、Guardian 和 hooks，并保留已有 Guardian 阈值配置。

## 许可证

当前仓库尚未指定开源许可证。公开可见不等于授予复制、修改或再发布许可；如需开源分发，请在后续添加明确的 `LICENSE` 文件。
