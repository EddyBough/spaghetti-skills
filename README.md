# 🍝 SpaghettiSkills

**Find AI agent skills that duplicate, overlap, or conflict before they turn your agent into spaghetti.**

SpaghettiSkills is a read-only, provider-agnostic Agent Skill that audits other installed skills.

It does **not** modify, delete, disable, rewrite, or move any skill. It only reads, compares, and reports.

## What it detects

- `DUPLICATE` — two skills largely do the same job.
- `OVERLAP` — two skills cover part of the same scope and may both influence the same task.
- `CONFLICT` — two skills can apply to the same situation but give incompatible instructions.
- `COMPATIBLE` — related skills that can coexist without meaningful interference.

## What it scans

By default, SpaghettiSkills combines the skills visible from the current project with known global skill directories when they exist.

That allows it to inspect:

- project ↔ project skills;
- global ↔ global skills;
- project ↔ global skills;
- extra skill directories supplied explicitly.

The scanner is read-only and de-duplicates skills by resolved file path.

## Installation

SpaghettiSkills is designed to be installed like any other Agent Skill.

Clone or copy this repository into a skill directory supported by your coding agent. The repository contains its own `SKILL.md` and local Python scanner.

No Python package, API key, background service, or global dependency is required.

> Installation paths differ between coding agents. SpaghettiSkills intentionally does not modify your global harness or install itself automatically.

## Usage

From a coding agent that supports Agent Skills, ask it to audit your installed skills with SpaghettiSkills.

For example:

```text
Use SpaghettiSkills to audit the skills available in this project and my global agent skills.
```

or:

```text
Check whether my installed skills duplicate, overlap, or conflict with each other.
```

The agent loads SpaghettiSkills, runs the bundled read-only Python scanner, reads the candidate `SKILL.md` pairs, and returns a report.

Example output:

```text
🍝 SpaghettiSkills

12 skills found

1 CONFLICT
2 OVERLAPS
1 DUPLICATE

CONFLICT — HIGH
react-performance ↔ dashboard-ui
global ↔ project

Shared scope:
React dashboard rendering

Evidence A:
"Prefer Server Components whenever possible."

Evidence B:
"Dashboard pages should default to Client Components."

Why:
Both skills may govern the same task while recommending opposing defaults.

Recommendation:
Review the scope of one of the skills. No files were changed.
```

### Run the scanner directly

Default scan (project + known global locations):

```bash
python3 scripts/scan.py --root . --json
```

Add another skill directory:

```bash
python3 scripts/scan.py --root . --source /path/to/skills --json
```

Project-only scan:

```bash
python3 scripts/scan.py --root . --no-global --json
```

The scanner does **not** decide whether two skills truly conflict. It only discovers skills and selects candidate pairs. The user's existing coding agent performs the semantic comparison according to the rules in `SKILL.md`.

**Python filters. Your existing agent judges. SpaghettiSkills reports.**

## How it works

SpaghettiSkills deliberately separates deterministic work from semantic judgment:

1. A local Python scanner discovers `SKILL.md` files and extracts routing metadata.
2. The scanner merges project, global, and explicitly supplied sources.
3. The scanner removes obviously unrelated pairs when the skill set is large.
4. The user's existing coding agent reads the full candidate skill pair.
5. The agent classifies the relationship using SpaghettiSkills' strict audit protocol.
6. The result is shown as a read-only terminal report with evidence.

No model API key is required by SpaghettiSkills itself.

## Safety / scope

SpaghettiSkills is **read-only by design**.

A scan must never:

- edit a `SKILL.md`;
- remove or disable a skill;
- modify `AGENTS.md`, `CLAUDE.md`, Cursor rules, hooks, MCP configuration, or other harness files;
- install dependencies globally;
- change the user's project or global agent configuration.

Audited skill contents are treated as **untrusted data**. Their instructions are evidence to inspect, not commands to execute during the audit.

Recommendations are advisory only. The user decides what to change.

## Status

Early development / benchmark phase.

The current goal is intentionally narrow: **audit collisions between Agent Skills only**.

## License

MIT
