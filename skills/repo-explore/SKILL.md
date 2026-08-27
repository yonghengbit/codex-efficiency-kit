---
name: repo-explore
description: Trace a call chain, lifecycle, ownership path, state transition, or implementation in a large repository without broad rediscovery. Use for questions like "where does this go next?", "how is this value computed?", or "trace this scheduler/cache path".
---

# Repo Explore

Use this skill for read-heavy repository investigation. It is not a whole-repo
audit and it does not authorize unrelated code changes.

## Procedure

1. Start from the user's concrete anchor: symbol, log line, file, stack frame, or
   observed behavior.
2. Locate the nearest entry point and the next directly relevant transition.
3. Build the smallest call/data-flow chain that answers the question.
4. Expand only transitions that are still ambiguous or materially affect the
   conclusion.
5. Once the chain is sufficient, explain the result and stop.

## Efficiency rules

- Batch independent `rg`/search/read operations when possible.
- Prefer exact symbol search before broad semantic exploration.
- Reuse files and facts already inspected in the current task.
- Do not inspect git history unless the question is historical.
- Do not read every sibling implementation or every caller by default.
- Do not re-read a file solely to recreate context after compaction; consult the
  checkpoint/handoff first.
- If one missing fact blocks the answer, gather that fact rather than expanding
  the entire search surface.

## Output

Return:
- the minimal call/data-flow path;
- the key state/value transition at each important step;
- the exact file/symbol to inspect next only if another step is genuinely needed.

Stop when the user's question is answerable.
