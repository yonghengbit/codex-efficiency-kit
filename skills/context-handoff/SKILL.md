---
name: context-handoff
description: Move an unfinished task from a degraded root context into a genuinely fresh root/thread using the same primary model. Use when Context Guardian requests a handoff after repeated compaction or drift.
---

# Context Handoff

This skill manages context lifecycle only. It is not delegation.

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

```text
HANDOFF_GENERATION:
PRIMARY_MODEL:
PRIMARY_REASONING_EFFORT:
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

For the default workflow, `PRIMARY_MODEL` is `gpt-5.6-sol`. Record reasoning
effort when the host exposes it; otherwise use `unknown` rather than guessing.

## Create the replacement root

At a stable boundary:

1. create a brand-new same-directory root/thread with no copied history;
2. explicitly request `PRIMARY_MODEL` for that thread;
3. preserve `PRIMARY_REASONING_EFFORT` when the API exposes it;
4. disallow provider/model fallback when that control is available;
5. verify the target thread's effective model before repository work.

If the target model is not exactly `PRIMARY_MODEL`, do not proceed. Correct it
once with a first-party settings control if available; otherwise report
`MODEL_MISMATCH` and fail closed.

## Start the new root immediately

Creating the thread is not enough. The new root must receive and start a real
turn before the old root may stop.

Use this continuation prompt:

```text
You are the new PRIMARY ROOT for the same unfinished task, not a subagent.

Continue the task now. Do not merely acknowledge the handoff, summarize it,
report back to the old root, or wait for the user.

First verify that your effective model matches PRIMARY_MODEL in
.codex/CODEX_HANDOFF.md. If it does not match, stop with MODEL_MISMATCH and do
not delegate to Terra/Luna.

Read the applicable AGENTS.md and .codex/CODEX_HANDOFF.md, then execute
NEXT_ACTION immediately. Preserve CONFIRMED_FACTS, REJECTED_PATHS, and
DO_NOT_REPEAT. Inspect only files directly required by NEXT_ACTION.

Own the task until STOP_CONDITION is satisfied. If your own Context Guardian
later requires another handoff, repeat this same same-model NEW-ROOT procedure
to create the next generation. Do not use fork_thread or $sub-agent as a
handoff substitute.
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
2. its effective model equals `PRIMARY_MODEL`;
3. the continuation prompt was delivered;
4. the destination turn actually entered running/started state or completed;
5. it was told to execute `NEXT_ACTION`, not just acknowledge.

If the target remains idle, perform at most one bounded retry with the
first-party turn/message control. If it still does not start, report
`HANDOFF_START_FAILED` and fail closed.

## Relationship to `$sub-agent`

`$sub-agent` remains explicit and separate:

```text
Sol root → explicit $sub-agent → Terra High worker → Sol root verifies
```

Compaction or handoff never activates it implicitly.

## Stop rule

The old root may stop only after the replacement root is verified live, or
after clearly reporting a blocked handoff. Writing the checkpoint alone is not
successful handoff.
