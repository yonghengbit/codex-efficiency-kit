---
name: context-handoff
description: Move an unfinished task from a degraded root context into a genuinely fresh root/thread using the same primary model. Use when Context Guardian requests a handoff after repeated compaction or drift.
---

# Context Handoff

This skill manages context lifecycle. It does not create delegation authority,
but it preserves an explicitly user-authorized `$sub-agent` workflow for the
same unfinished task.

For a Sol root:

```text
old Sol root
→ .codex/CODEX_HANDOFF.md
→ BRAND-NEW Sol root with empty conversation history
→ continue the same task
```

Do not use Terra or Luna for context handoff.

## Create, do not fork

A fresh context must be a brand-new root/thread. Use first-party
`create_thread` / `thread/start` style controls.

Do **not** use:

- `fork_thread` / `thread/fork`;
- `spawn_agent` or multi-agent workers;
- side chats or `/btw`;
- `$sub-agent`.

`thread/fork` copies conversation history, so it is not a context reset.

If real thread-creation controls are unavailable, handoff is blocked. Never
silently fall back to Terra/Luna or a subagent.

## Write the checkpoint

Create or refresh `.codex/CODEX_HANDOFF.md` from already-known state only:
`PRIMARY_REASONING_EFFORT` 是必填字段：保存源 root 由 host/first-party control 暴露的精确 reasoning 值（例如 `high`、`xhigh` 或 `max`）；只有源 effort 确实不可观测时才写 `unknown`，不能因为 replacement 创建时想省略参数就回填 `unknown`。

```text
HANDOFF_GENERATION:
SOURCE_SESSION_ID:
PRIMARY_MODEL:
PRIMARY_REASONING_EFFORT:
WORKFLOW_MODE: direct | sub-agent
DELEGATION_ORIGIN: none | explicit-user
DELEGATION_SCOPE:
DELEGATION_EXPIRES_AT:
ACTIVE_WORKER_STATE: none | running | completed | failed
ACTIVE_WORKER_SCOPE:
WORKER_RESULT:
GOAL:
CURRENT_PHASE:
PROGRESS:
CONFIRMED_FACTS:
REJECTED_PATHS:
CHANGED_FILES:
VALIDATION:
NEXT_ACTION:
DO_NOT_REPEAT:
STOP_CONDITION:
```

Never write passwords, tokens, private keys, or complete credentials into the
checkpoint. Reference their approved secure location instead.

## Preserve an authorized `$sub-agent` workflow

Handoff must not invent delegation authorization. Set `WORKFLOW_MODE: sub-agent`
only when the original user explicitly invoked `$sub-agent` or explicitly asked
for delegation for this same unfinished task. Record the bounded authorized
scope and its task-level expiry.

Delegation authorization expires when the original `STOP_CONDITION` is met, the
user starts a different task, the user cancels delegation, or the checkpoint
cannot establish the original explicit authorization.

Do not hand off while a worker is still running. The old root owns workers
created inside its task and must first collect a stable result or deliberately
stop the worker and record the partial result. A fresh root must never create a
duplicate worker for an `ACTIVE_WORKER_STATE: running` entry.

For the default workflow, record `PRIMARY_MODEL` as the exact model id exposed by the
host/first-party control (for example, `gpt-5.6-sol-plus` when that is the reported
id); do not hardcode or invent a shorthand alias. Always save
`PRIMARY_REASONING_EFFORT` as the exact known value; use `unknown` only when the
source effort is genuinely unavailable.

## Create the replacement root

At a stable boundary:

1. create a brand-new same-directory root/thread with no copied history;
2. explicitly request the exact `PRIMARY_MODEL` for that thread;
3. when `PRIMARY_REASONING_EFFORT` is not `unknown`, explicitly pass that exact
   value as the API's `thinking`/`reasoning` override to `create_thread`/
   `thread/start`; never omit it and rely on a runtime default;
4. if a known effort cannot be set because the API lacks or rejects the reasoning
   override, report `REASONING_MISMATCH` and fail closed; do not silently
   substitute another effort or the default;
5. disallow provider/model fallback when that control is available;
6. verify the target thread's effective model and, when observable, effective
   reasoning before repository work.

If the target model is not exactly `PRIMARY_MODEL`, do not proceed. Correct it
once with a first-party settings control if available; otherwise report
`MODEL_MISMATCH` and fail closed. If `PRIMARY_REASONING_EFFORT` is known, the
replacement request must carry that exact override; if it was omitted or the
target's effective reasoning is observable but differs, report
`REASONING_MISMATCH` and fail closed. Only a genuinely unknown source effort
permits omitting the reasoning override.

## Start the new root immediately

Creating the thread is not enough. The new root must receive and start a real
turn before the old root may stop.

Use this continuation prompt:

```text
You are the new PRIMARY ROOT for the same unfinished task, not a subagent.

Continue the task now. Do not merely acknowledge the handoff, summarize it,
report back to the old root, or wait for the user.

First verify that your effective model exactly matches PRIMARY_MODEL in
.codex/CODEX_HANDOFF.md. If it does not match, stop with MODEL_MISMATCH and do
not execute work or delegate to Terra/Luna.

If PRIMARY_REASONING_EFFORT is not unknown, verify that the replacement request
used that exact value as its thinking/reasoning override. If the override was
omitted, or the effective reasoning is observable and differs, stop with
REASONING_MISMATCH and do not execute work. Only a genuinely unknown source
effort permits omission; do not infer it from a runtime default. If reasoning
is not observable, retain the explicit-request evidence and report that
limitation.

Read the applicable AGENTS.md and .codex/CODEX_HANDOFF.md, then execute
NEXT_ACTION immediately. Preserve CONFIRMED_FACTS, REJECTED_PATHS, and
DO_NOT_REPEAT. Inspect only files directly required by NEXT_ACTION.

If WORKFLOW_MODE is sub-agent and DELEGATION_ORIGIN is explicit-user, read and
apply the sub-agent Skill within DELEGATION_SCOPE. This is inherited explicit
authorization for the same task, not implicit delegation created by handoff.
Do not automatically spawn a new worker when WORKER_RESULT already covers the
next step; the new primary root should validate that result first.

Own the task until STOP_CONDITION is satisfied. If your own Context Guardian
later requires another handoff, repeat this exact same-model NEW-ROOT procedure,
including the reasoning check above, to create the next generation. Do not use
fork_thread or $sub-agent as a handoff substitute.
```

When possible, start the target turn atomically with thread creation. Otherwise
send the continuation immediately after creation. Do not attach Terra/Luna
worker model overrides to the continuation message.

## Verify liveness before success

A successful message dispatch is not sufficient. Before the old root stops,
verify via first-party status/read/wait controls that the destination turn
actually started (or already completed after starting).

Successful handoff requires all of:

1. a brand-new root/thread exists;
2. its effective model exactly equals `PRIMARY_MODEL`;
3. when `PRIMARY_REASONING_EFFORT` is known, the replacement request carried
   that exact override and, when effective reasoning is observable, it equals
   the checkpoint value; if the source effort is `unknown`, omission is allowed
   and no reasoning value may be claimed;
4. the continuation prompt was delivered;
5. the destination turn actually entered running/started state or completed;
6. it was told to execute `NEXT_ACTION`, not just acknowledge.

If the target remains idle, perform at most one bounded retry with the
first-party turn/message control. If it still does not start, report
`HANDOFF_START_FAILED` and fail closed.

## Acknowledge the Guardian gate

After model, reasoning, and liveness verification, the old root must acknowledge success in
Guardian state before stopping. Use the installed Guardian script with the
`SOURCE_SESSION_ID` and destination task id:

```text
context_guardian.py --mark-handoff verified \
  --session-id SOURCE_SESSION_ID --target-thread-id TARGET_THREAD_ID
```

On Windows invoke it with `py -3`; on POSIX use `python3`. If handoff is
genuinely unavailable or still fails after the bounded retry, acknowledge
`--mark-handoff blocked --session-id SOURCE_SESSION_ID` and report the concrete
blocker. Never mark `verified` before all success conditions above are true.

## Relationship to `$sub-agent`

`$sub-agent` remains explicit and separate:

```text
Sol root → explicit $sub-agent → Luna worker (`max`, or same Luna `xhigh` when `max` is unavailable) → Sol root verifies
```

Handoff never creates new delegation authority. It may carry forward an
already-active, explicitly user-authorized `$sub-agent` workflow for the same
unfinished task and scope.

## Stop rule

The old root may stop only after the replacement root is verified live, or
after clearly reporting a blocked handoff. Writing the checkpoint alone is not
successful handoff.
