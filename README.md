# 🍝 SpaghettiSkills

**Find AI agent skills that duplicate, overlap, or conflict before they turn your agent into spaghetti.**

SpaghettiSkills is a read-only Agent Skill auditor for coding agents such as Cursor and Codex. It discovers the skills available to a project, uses exhaustive pair selection by default and supports explicitly enabled experimental metadata filtering, and asks the host agent to classify each relationship as `DUPLICATE`, `OVERLAP`, `CONFLICT`, or `COMPATIBLE`.

No separate model API key. No background service. No automatic mutation of your harness.

## Why this exists

Agent Skills are easy to install and easy to accumulate.

The failure mode is not only duplication. Two skills can both apply to the same task while encoding different defaults, different constraints, or directly incompatible instructions. Those collisions are difficult to spot by looking at filenames alone.

SpaghettiSkills audits that layer before it becomes part of an agent's behavior.

## Focused by design

SpaghettiSkills does not try to audit everything in an agent harness.

It does not inspect MCP servers, lint every configuration file, rewrite agent instructions, manage hooks, or automatically "fix" the environment. Its scope is intentionally narrow: understand how installed Agent Skills interact with each other.

That boundary is deliberate. Compatibility between independently authored skills is already a distinct problem with its own tradeoffs around discovery, semantic judgment, false positives, false negatives, and cost.

SpaghettiSkills prefers depth, explainability, and read-only analysis over becoming an all-purpose agent toolbox.

In short:

```text
Discover skills
→ compare them
→ explain collisions
→ modify nothing
```

## Install

Install globally for Cursor and Codex with the Agent Skills CLI:

```bash
npx skills add EddyBough/spaghetti-skills \
  -g -a cursor -a codex
```

Then ask your coding agent:

```text
Use SpaghettiSkills to audit my installed skills.
```

SpaghettiSkills will inspect project-local and known global skill locations visible to the current environment.

## What it detects

- `DUPLICATE`: substantially the same purpose and guidance.
- `OVERLAP`: both skills govern the same responsibility, decision, behavior, or output dimension without directly contradicting each other.
- `CONFLICT`: both skills apply to the same situation and give incompatible instructions.
- `COMPATIBLE`: both may be useful in the same task, but they govern distinct concerns or complement each other.

Co-activation alone is **not** considered overlap.

## Example

```text
CONFLICT - HIGH
ui-ux-pro-max ↔ ui-ux-pro-max
global ↔ project

Shared scope:
UI/UX implementation for the same project.

Skill A:
"Never assume a stack..."

Skill B:
"If user doesn't specify a stack, default to html-tailwind."

Why:
Both versions can govern the same task while encoding opposing defaults.

Suggestion:
Keep one authoritative version. No files were changed.
```

## Design principles

### Read-only by design

An auditor should not mutate the system it is auditing. SpaghettiSkills reads, compares, and reports. It never deletes, disables, rewrites, moves, or installs skills during an audit.

### Deterministic first

Discovery, path de-duplication, metadata parsing, pair generation, and routing are handled locally in Python. Work that does not require semantic judgment should not consume LLM reasoning.

### Semantic only when needed

The host coding agent is used only for the part that actually requires understanding instructions in context. Candidate skills are read once and their contents are reused across the selected pair comparisons.

### Provider-agnostic

SpaghettiSkills does not embed or call a model provider directly. It reuses the coding agent the developer is already running.

## Architecture

```text
Installed Agent Skills
        │
        ▼
Deterministic discovery
        │
        ▼
Metadata extraction + de-duplication
        │
        ▼
Candidate routing
        │
        ▼
Selected skills read once
        │
        ▼
Host LLM semantic review
        │
        ▼
DUPLICATE / OVERLAP / CONFLICT / COMPATIBLE
```

The implementation deliberately separates cheap deterministic work from expensive semantic judgment:

1. `scripts/scan.py` discovers `SKILL.md` files.
2. It merges project-local, known global, and explicitly supplied sources.
3. It prunes common dependency/build directories such as `node_modules`, `.git`, `.next`, `dist`, and `build`.
4. Every possible pair is retained by default, regardless of the number of skills.
5. Results are paginated in batches of 100 pairs to avoid one oversized scanner output.
6. The host agent examines each page, reads selected skills, and applies `SKILL.md`.
7. Findings include evidence from both skills and remain advisory.
8. Optional `--mode filtered` uses metadata similarity, but is experimental and can miss collisions.

**Python routes. Your existing agent judges. SpaghettiSkills reports.**

## Why not compare every skill with an LLM?

An exhaustive pairwise comparison grows quadratically.

For `n` discovered skills, the number of possible pairs is:

```text
n × (n - 1) / 2
```

Examples:

| Skills | Theoretical pairs |
| ---: | ---: |
| 10 | 45 |
| 25 | 300 |
| 50 | 1,225 |
| 100 | 4,950 |

By default, SpaghettiSkills keeps **every pair**. This avoids false negatives caused by discarding pairs before semantic analysis, but it does not prevent mistakes made by the LLM. Large audits are expensive and may require many batches; the tool must report incomplete audits rather than silently truncating results.

`--mode filtered` is available for experimentation only and must be selected explicitly. Its recall has not been validated on independent corpora. The scanner exposes `theoretical_pair_count`, `candidate_pair_count`, `routing_reduction_percent`, and pagination counts to make this tradeoff explicit.

## Benchmark philosophy

SpaghettiSkills is currently in the benchmark phase.

The goal is not to maximize routing reduction at any cost. The important metric is **recall of real collisions**: a cheaper router is useless if it silently filters out true conflicts or overlaps.

We therefore evaluate routing against known fixtures and real-world skill sets using two measurements:

- **routing reduction**: how many theoretical pairs avoid semantic review;
- **collision recall**: how many known collisions survive routing and reach semantic review.

No performance percentage should be treated as a project-wide claim until it is backed by a reproducible benchmark in this repository.

## Threat model / safety

Audited skills are **untrusted input**.

A `SKILL.md` may contain instructions that are valid when the skill is active but unsafe or irrelevant during an audit. SpaghettiSkills requires the host agent to treat those instructions as evidence to analyze, not commands to execute.

During an audit SpaghettiSkills must not:

- execute instructions found inside an audited skill merely because they are present;
- edit or delete a skill;
- change `AGENTS.md`, `CLAUDE.md`, Cursor rules, hooks, MCP configuration, or other harness files;
- install dependencies globally;
- modify the user's project or global agent configuration.

Recommendations are advisory only.

## Discovery scope

By default, SpaghettiSkills can combine:

- project ↔ project skills;
- global ↔ global skills;
- project ↔ global skills;
- additional directories supplied explicitly.

Known project-local locations include `.agents/skills`, `.codex/skills`, `.claude/skills`, and `.cursor/skills`.

Known global locations are inspected only when they exist, including `~/.agents/skills`, Codex skills, Claude skills, and Cursor skills.

Resolved paths are de-duplicated so the same physical skill is not counted twice merely because multiple discovery roots reach it.

## Run the scanner directly

Default scan:

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

The scanner performs discovery and candidate selection only. It does **not** make the final semantic classification.

Exhaustive mode is the default. For larger sets, request additional pages:

```bash
python3 scripts/scan.py --root . --pair-offset 100 --pair-limit 100 --json
```

Experimental metadata filtering (not a certified recall guarantee):

```bash
python3 scripts/scan.py --root . --mode filtered --json
```

`candidate_pair_count` is the count across all pages, while `emitted_pair_count` counts only the current page. Pairs that have not been semantically reviewed are **not** classified as `COMPATIBLE`. A skill file found on disk also is not proof that it is active in the current host; co-availability must be assessed separately.

## Tests

The scanner uses only the Python standard library.

Run the test suite with:

```bash
python3 -m unittest discover -s tests -v
```

Tests cover the deterministic layer: metadata parsing, discovery failures, ignored directories, exhaustive coverage above 15 skills, opt-in filtering, threshold behavior, pagination, and routing metrics. GitHub Actions runs the test suite on Python 3.10 through 3.13.

## Limitations

SpaghettiSkills intentionally has a narrow scope.

- Experimental metadata routing is heuristic and can produce false negatives. Its collision recall has not yet been established by a benchmark.
- Final semantic classification depends on the capabilities and behavior of the host model.
- A relationship can depend on task context; two skills may be compatible in one situation and conflict in another.
- The lightweight frontmatter parser supports the metadata shapes needed by common Agent Skills, but it is not a general-purpose YAML parser.
- Discovered skill files may belong to different hosts. Their mere presence does not prove co-activation or a runtime conflict.
- A completed candidate scan is not automatically a completed semantic audit. Large reviews may need multiple batches, and any unreviewed pairs must be disclosed.
- SpaghettiSkills audits **Agent Skills only**. It does not audit hooks, MCP servers, `AGENTS.md`, `CLAUDE.md`, IDE rules, or the rest of the agent harness.

These are deliberate boundaries, not hidden guarantees.

## Project structure

```text
spaghetti-skills/
├── SKILL.md              # semantic audit protocol
├── README.md             # project documentation
├── scripts/
│   └── scan.py           # deterministic discovery + routing
├── tests/                # deterministic-layer tests
└── docs/
    └── HOW_IT_WORKS.md    # architecture notes
```

`scan.py` intentionally remains a single small module while discovery, parsing, routing, and reporting are still tightly coupled and easy to understand in one place. It should be split only when those responsibilities develop independent complexity or reuse, not to create architecture for its own sake.

## Status

Early development / benchmark phase. Deterministic unit tests are in CI; semantic benchmark accuracy and generalization have not yet been established.

The current goal is intentionally narrow: **detect collisions between Agent Skills accurately, cheaply, and without modifying the harness.**

## License

MIT
