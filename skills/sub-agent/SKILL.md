---
name: sub-agent
description: 使用当前主智能体规划和验收，并在当前任务内优先拉起 Luna Max 子智能体执行；运行时不支持时按有界规则回退。用户调用 `$sub-agent`、要求使用默认子智能体工作流、明确要求委派，或同一未完成任务的有效 handoff checkpoint 记录了原始用户的显式委派授权时使用。若没有具体任务，先询问任务；不要自行猜测或主动委派。
---

# Sub-agent

把当前主智能体作为规划者和验收者，优先把一个 `gpt-5.6-luna`、`max` 推理强度的子智能体作为执行者；运行时不支持该组合时，按下文的兼容规则有界回退。此工作流假设用户已在界面选择 Sol High 作为当前主智能体；不要声称 Skill 能切换已经运行的主模型。

这个 Skill 是**显式编排工作流**，不是全局自动路由器。普通任务不要因为 Luna 更便宜就主动拉起子智能体。

Context handoff must never create delegation authority. It may preserve this
Skill as the active workflow when the same unfinished task's checkpoint records
that the original user explicitly authorized it. Fresh-root lifecycle switching
and worker delegation remain separate mechanisms.

## 启动条件

- 仅在用户显式调用 `$sub-agent`、要求使用默认 Sol–worker 工作流，或明确要求拉起/委派子智能体时启动。
- 同一未完成任务发生 context handoff 时，若 checkpoint 同时记录
  `WORKFLOW_MODE: sub-agent`、`DELEGATION_ORIGIN: explicit-user` 和明确的
  `DELEGATION_SCOPE`，新主智能体应继承本 Skill。该授权在原任务完成、用户
  开始新任务、用户取消委派或 checkpoint 无法证明原始授权时失效。
- 若用户没有给出可执行的具体任务，只问：“要让子智能体完成什么任务？”不要拉起智能体，也不要猜测任务、模型或目标。
- 若任务已经明确，直接开始，不要再次询问模型；默认优先执行者是 Luna Max，兼容回退不需要额外询问。
- 用户明确指定的模型、推理强度、并发方式或执行边界优先于本 Skill 的默认值。

## Sol–worker 路由原则

本 Skill 启动后，按以下职责划分工作，而不是把所有思考都转交 Luna。

主智能体保留：
- 需求解释、范围边界和验收标准；
- 架构取舍与关键路径决策；
- root-cause 综合判断和跨模块 invariant；
- 对子智能体结果的最终核验与集成判断。

优先交给执行 worker：
- 边界明确的实现和机械性代码修改；
- 独立的 symbol/caller/reference 搜索与证据收集；
- 有明确输入输出的局部调试或验证；
- targeted tests、lint/typecheck 等约定好的验证；
- 彼此独立、文件/模块不冲突且并行收益明显的工作单元。

不要为了“使用子智能体”而制造子任务。若一个步骤明显比“描述任务 → 委派 → 等待 → 集成”更便宜地由主智能体直接完成，主智能体应保留该步骤；但用户明确要求由子智能体完成的执行工作除外。

## 模型兼容

- 首选 `gpt-5.6-luna`、`max`。若当前拉起工具明确列出该模型与推理组合，直接使用；不要额外访问网络或模型目录做探测。
- 若当前工具未列出 Luna Max，使用它明确支持的 `gpt-5.6-terra`、`high`；若 Terra High 也未列出，则省略 model 和 reasoning override，使用运行时默认值。
- 若 Luna Max 拉起请求明确返回 model 或 reasoning combination unsupported/unavailable，且没有返回任何 worker 标识，只允许重试一次：优先 Terra High，否则省略 override。
- 鉴权、网络、额度、超时或含糊错误不得触发模型回退。响应一旦返回 worker 标识，即使后续失败也不得通过回退创建重复 worker。
- 发生回退或运行时无法保证实际模型时，简短告知用户实际选择或限制；不得声称执行者一定是 Luna Max。
- 用户明确指定的模型与推理强度始终优先；其指定组合不受本节的自动回退规则替换。

## 工作流

1. 主智能体先理解任务，形成简洁的执行计划、范围边界和可验证的验收标准。只澄清会实质改变结果且无法从项目中查明的信息。
2. 在当前任务中拉起一个子智能体，不创建新的顶层任务或独立对话。按照“模型兼容”选择 model 和 reasoning override；不重复探测，不在结果不明确时创建第二个 worker。
3. 如果拉起接口支持控制继承上下文，优先不继承完整对话。向子智能体发送一份自包含的执行简报，其中包括：
   - 目标与非目标；
   - 主智能体的执行计划；
   - 相关项目路径、现有约束和已知事实；
   - 必须完成的验证与验收标准；
   - 明确的 write scope / read scope（若适用）；
   - 要求返回的改动摘要、测试证据、剩余风险和阻塞项。
4. 子智能体负责被委派范围内的实现、测试、调试和必要修复。主智能体在它执行期间不重复实现或重复调查同一工作。
5. 主智能体可以继续执行**不重叠且不依赖子智能体立即返回**的关键路径工作；不要为了等待结果停掉所有可推进工作。需要等待时使用一个有界 wait；状态未变化时不输出新的进度消息，也不立即执行相同 poll。工具支持 cursor 时复用 cursor，只有状态变化、需要纠偏或 worker 完成时再更新用户。
6. 需要补充信息或纠偏时，优先继续指导同一个子智能体，不重复拉起新的执行者。
7. 子智能体返回后，主智能体检查实际改动、测试结果和验收标准；不要未经核验直接转述其结论。
8. 若验收失败，把具体缺陷和期望结果发回同一个子智能体修正，然后再次检查。默认只做与失败证据直接相关的 bounded correction，不进入无限 review/fix 循环。若缺少只有用户能决定的信息，再向用户询问。
9. 验收通过后，由主智能体给出简洁的最终结果，包括完成内容、验证证据和仍需用户注意的真实风险。

## 编排边界

- 默认只拉起一个执行者。只有用户明确要求并行，或任务存在多个真正独立且并行收益明显的子任务时，才增加子智能体。
- 不把当前下一步立即依赖的 critical-path reasoning 委派出去后原地等待；这类判断优先留在主智能体。
- 不使用线程 Handoff 来监督普通 `$sub-agent` 工作流；通过等待、跟进指令和验收完成监督。
- worker 属于创建它的当前任务。worker 仍在运行时，主智能体不得先 handoff
  再在新任务中拉起重复 worker；应先收集稳定结果，或有意识地终止并记录
  partial result，然后才能进行 fresh-root handoff。
- 不主动新建 `AGENTS.md`、`PLAN.md`、`HANDOFF.md` 或其他过程文档。仅在用户明确要求、现有项目规则把它列为交付物，或 `context-handoff` 生命周期工作流明确要求 checkpoint 时创建。
- 不因调用本 Skill 而扩大文件、服务器、账户或外部系统的授权范围。
- 破坏性操作、生产环境变更、凭据使用和对外发布仍遵循当前任务的批准与安全边界。

## 与 Context Guardian 的关系

- `$sub-agent`：解决“谁来执行”，只在显式请求时启动 Sol–worker 编排；Luna Max 是首选而不是无条件假设。
- `context-handoff`：解决“当前主上下文是否应该继续承载任务”。
- Guardian 触发 handoff 本身不会创造 `$sub-agent` 授权；但同一任务中由用户
  显式开启的授权会通过有效 checkpoint 继承。
- 对 Sol 主对话，context handoff 始终表示 `old Sol root → fresh Sol root`。
- 新 root 先恢复主智能体职责并读取 worker 状态：已有完成结果则先验收；
   没有活跃 worker 且授权范围内仍有适合执行者的工作时，才拉起一个 worker。
- 执行 worker 只会因为原始用户的显式 delegation 条件而出现，不会仅因为
  compaction 自动出现。
