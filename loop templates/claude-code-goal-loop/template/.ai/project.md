# Project: {{TITLE}}

## Goal

{{GOAL_PARAGRAPH: what is being built, for whom, what "finished" looks like}}

## Required contents

| Element | What "good" means |
|---|---|
| {{element}} | {{concrete, checkable description}} |

## Interfaces / test contract

{{How the verification tool observes the result: CLI output, a JSON file, `window.__diag`, an API endpoint,
test suite. Name the exact fields the tool reads.}}

## Acceptance checks (all must pass for goal-complete)

1. `{{VERIFY_ALL}}` exits 0.
2. {{measurable check with a number}}
3. {{...}}

## Quality rubric (score each 1-5; all must reach >= {{N}})

- **{{Dimension}}**: {{what a 5 looks like}}

Write the scores into `.ai/handoff.md` each time you review.

## Reference

{{Prior art, docs, example files, links. Everything an agent needs without asking.}}
