---
name: minimal-review
description: Review a diff or patch for concrete actionable defects and over-engineering without repeatedly widening the review. Use for "review this diff", "check my changes", or a final bounded review.
---

# Minimal Review

Review the requested change, not the whole repository.

## Procedure

1. Inspect the complete requested diff and only enough surrounding code/call
   sites to establish whether a finding is real.
2. Report concrete regressions, correctness problems, unsafe behavior, or
   unnecessary complexity introduced by the change.
3. Classify each finding as:
   - BLOCKER
   - REAL BUG
   - LIKELY RISK
   - THEORETICAL EDGE CASE
   - STYLE
4. BLOCKER and REAL BUG are actionable by default. LIKELY RISK needs evidence
   proportional to the proposed fix. Do not expand code solely for THEORETICAL
   or STYLE findings.
5. Perform one review pass. If fixes are later made, re-check only the affected
   findings and changed regions unless new evidence justifies broader review.

## Over-engineering checks

Ask whether new abstractions, states, helpers, dependencies, compatibility
layers, retries, tests, or infrastructure are actually required by the task.
Prefer deletion or reuse when behavior remains correct.

## Efficiency rules

- Do not audit unrelated files.
- Do not search git history unless needed to establish a regression.
- Do not invent additional requirements.
- Do not keep finding new issues merely because another review pass was
  requested; new findings require new evidence or newly changed code.

Return file/line references where possible.
