---
name: targeted-debug
description: Diagnose and fix a concrete bug, failure, crash, incorrect value, race, or regression using bounded hypotheses and targeted validation. Use when there is an observed failure to explain or repair.
---

# Targeted Debug

## Procedure

1. State the observed failure and the nearest reproducible symptom.
2. Choose the single most plausible current hypothesis that can explain the
   evidence.
3. Gather the cheapest discriminating evidence for or against that hypothesis.
4. If falsified, record why and move to the next best hypothesis. Do not keep
   several speculative branches active without need.
5. Once the root cause is supported, make the smallest coherent fix.
6. Run the smallest validation that directly exercises the failure.
7. If validation fails, allow one bounded correction based on the new evidence.
   If it still fails, reassess the root cause instead of layering patches.
8. Stop when the reproducer/targeted validation passes and no blocker introduced
   by the fix remains.

## Efficiency rules

- Reuse confirmed facts and rejected hypotheses.
- Do not repeatedly run the same successful command.
- Do not add defensive machinery for hypothetical failures unrelated to the
  reproducer.
- Do not run a full suite unless the change's blast radius justifies it or the
  user explicitly requests it.
- Do not convert debugging into a broad refactor.

## Report

Summarize the root cause, evidence, minimal fix, validation performed, and any
remaining real risk. Separate real risks from theoretical edge cases.
