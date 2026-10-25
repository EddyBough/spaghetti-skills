---
name: spaghetti-skills
description: >-
  Audits installed Agent Skills for duplicate scope, overlapping responsibility,
  or conflicting instructions. Use when the user wants to check whether multiple
  SKILL.md files may interfere with each other, degrade an agent's behavior, or
  duplicate the same job. Read-only: never modify skills or agent configuration.
---

# SpaghettiSkills

SpaghettiSkills is a read-only audit skill for detecting relationships between other Agent Skills.

## Core contract

SpaghettiSkills may read and compare skills, but must never modify, move, delete, disable, install, or rewrite them.

It must not change global or project harness configuration.

## Audit workflow

1. Run the bundled scanner to discover skills and produce candidate pairs.
2. For each candidate pair, read both complete `SKILL.md` files.
3. Determine whether both skills could reasonably influence the same user task.
4. Compare their goals, activation scope, instructions, exceptions, and constraints.
5. Assign exactly one relationship:
   - `DUPLICATE`
   - `OVERLAP`
   - `CONFLICT`
   - `COMPATIBLE`
6. Support the verdict with concrete evidence from both skills.
7. Report only. Do not apply any suggested change.

## Classification rules

### DUPLICATE
Use when the skills have substantially the same purpose and substantially the same guidance, so keeping both adds little distinct value.

### OVERLAP
Use when the skills share meaningful scope and could both influence the same task, but their guidance is not directly incompatible.

### CONFLICT
Use only when both conditions are true:

1. the skills can reasonably apply to the same situation; and
2. their instructions are incompatible in that shared situation.

Different recommendations in different contexts are not a conflict.

### COMPATIBLE
Use when the skills are related but have sufficiently distinct scope, or when their guidance is complementary rather than interfering.

## Evidence requirement

Never report a collision from names or shared keywords alone.

For each non-compatible finding, include:

- the two skill names;
- the shared scope;
- one relevant instruction or passage from each skill;
- a concise explanation of why the relationship was classified that way;
- a confidence level: `LOW`, `MEDIUM`, or `HIGH`;
- an advisory recommendation, if useful.

## Output format

Use this compact terminal-friendly structure:

```text
CONFLICT — HIGH
skill-a ↔ skill-b

Shared scope:
<shared task/context>

Skill A:
<evidence>

Skill B:
<evidence>

Why:
<short explanation>

Suggestion:
<advisory only>
```

Finish with a summary count for `DUPLICATE`, `OVERLAP`, `CONFLICT`, and `COMPATIBLE`.

## Scanner

Run:

```bash
python3 scripts/scan.py --root . --json
```

The scanner only discovers skills and selects candidate pairs. It does not make the final semantic judgment.
