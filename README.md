# 🍝 SpaghettiSkills

**Find AI agent skills that duplicate, overlap, or conflict before they turn your agent into spaghetti.**

SpaghettiSkills is a read-only, provider-agnostic Agent Skill that audits other installed skills.

It does **not** modify, delete, disable, rewrite, or move any skill. It only reads, compares, and reports.

## What it detects

- `DUPLICATE` — two skills largely do the same job.
- `OVERLAP` — two skills cover part of the same scope and may both influence the same task.
- `CONFLICT` — two skills can apply to the same situation but give incompatible instructions.
- `COMPATIBLE` — related skills that can coexist without meaningful interference.

## How it works

SpaghettiSkills deliberately separates deterministic work from semantic judgment:

1. A local Python scanner discovers `SKILL.md` files and extracts routing metadata.
2. The scanner removes obviously unrelated pairs when the skill set is large.
3. The user's existing coding agent reads the full candidate skill pair.
4. The agent classifies the relationship using SpaghettiSkills' strict audit protocol.
5. The result is shown as a read-only terminal report with evidence.

**Python filters. Your existing agent judges. SpaghettiSkills reports.**

No model API key is required by SpaghettiSkills itself.

## Safety / scope

SpaghettiSkills is **read-only by design**.

A scan must never:

- edit a `SKILL.md`;
- remove or disable a skill;
- modify `AGENTS.md`, `CLAUDE.md`, Cursor rules, hooks, MCP configuration, or other harness files;
- install dependencies globally;
- change the user's project or global agent configuration.

Recommendations are advisory only. The user decides what to change.

## Status

Early development / benchmark phase.

The current goal is intentionally narrow: **audit collisions between Agent Skills only**.

## License

MIT
