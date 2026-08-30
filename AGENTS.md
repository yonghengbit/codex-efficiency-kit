# Codex Global Engineering Rules

## Scope

Prefer the smallest coherent change that fully satisfies the request.

Reuse existing code, project patterns, standard-library features, and existing
dependencies before introducing new abstractions or infrastructure.

Do not perform unrelated refactors, cleanup, renaming, compatibility work, or
future-proofing unless required by the requested behavior.

Do not modify files outside the necessary scope without a concrete reason.

## Execution

Inspect only the code needed for the current task. Do not rediscover the whole
repository when the relevant area is already known.

Batch independent read-only operations when possible. Avoid separate
reasoning/tool turns for mechanically determined steps that can run together.

Do not inspect git history, perform broad repository audits, or explore sibling
implementations unless the task requires them.

For long-running tasks with multiple phases, handoffs, or remote runs, maintain
one canonical status ledger. Prefer an existing plan, status, or handoff
artifact; do not duplicate the same state across multiple process documents.
Keep the hard acceptance gates, established evidence, blockers, untested items,
and next concrete action current in that ledger.

## Delegation

Do not spawn subagents unless the user explicitly requests delegation. A fresh
root may continue that authorization only when a same-task handoff checkpoint
records `WORKFLOW_MODE: sub-agent`, `DELEGATION_ORIGIN: explicit-user`, and a
bounded `DELEGATION_SCOPE`. The inherited authorization expires with the
original task or when the user changes or cancels it.

Context handoff is never delegation. Never use `spawn_agent`, multi-agent
workers, side chats, Terra, or Luna as a substitute for a fresh root/thread.
If first-party thread creation/continuation controls are unavailable, fail
closed and report the handoff as blocked.

When delegation is explicitly active, keep critical decisions and final
acceptance in the parent, give workers bounded scopes, and do not duplicate
the worker's task in the parent.

Do not hand off a root while one of its workers is still running. Collect a
stable result or deliberately stop it and record the partial result before
creating the replacement root; never create a duplicate worker after handoff.

## Validation

Use the smallest validation that directly demonstrates the changed behavior.
Prefer targeted tests and relevant lint/type checks over full builds or suites.

Do not rerun a successful check unless relevant code, configuration,
dependencies, runtime state, or environment changed.

Do not add tests, retries, compatibility layers, or validation infrastructure
solely to gain more confidence when the requested behavior is already adequately
verified.

Classify material validation conclusions as `VERIFIED`, `INFERRED`, `BLOCKED`,
or `UNTESTED`: direct evidence, reasoned but untested expectation, validation
prevented by a concrete blocker, or validation not attempted. Do not describe
behavior as passed, supported, complete, or issue-free beyond the scope directly
established by the available evidence.

## Decision Discipline

Distinguish required work from optional improvement. Hypothetical edge cases,
style preferences, speculative future requirements, and unrelated cleanup do
not expand the task.

When several solutions are valid, prefer fewer new concepts, files, states,
dependencies, and abstractions.

After context compaction, preserve confirmed conclusions and rejected paths;
do not rediscover them without new contradictory evidence. Follow a
context-handoff request from the context guardian before starting a new broad
phase.

## Stop Condition

Stop when the requested behavior is implemented or the question is answered,
the smallest relevant validation has passed when applicable, and no known
blocker caused by the current change remains.

Do not continue merely to gain additional confidence, perform another review
pass, or improve unrelated code.
