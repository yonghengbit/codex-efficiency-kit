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

## Delegation

Do not spawn subagents unless the user explicitly requests delegation.

Context handoff is never delegation. Never use `spawn_agent`, multi-agent
workers, side chats, Terra, or Luna as a substitute for a fresh root/thread.
If first-party thread creation/continuation controls are unavailable, fail
closed and report the handoff as blocked.

When delegation is explicitly active, keep critical decisions and final
acceptance in the parent, give workers bounded scopes, and do not duplicate
the worker's task in the parent.

## Validation

Use the smallest validation that directly demonstrates the changed behavior.
Prefer targeted tests and relevant lint/type checks over full builds or suites.

Do not rerun a successful check unless relevant code, configuration,
dependencies, runtime state, or environment changed.

Do not add tests, retries, compatibility layers, or validation infrastructure
solely to gain more confidence when the requested behavior is already adequately
verified.

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
