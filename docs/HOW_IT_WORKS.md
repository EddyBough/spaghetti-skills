# How SpaghettiSkills works

SpaghettiSkills separates deterministic scanning from semantic judgment.

## 1. Discovery

The bundled Python scanner recursively finds `SKILL.md` files under the requested root.

It reads only metadata needed for routing:

- `name`
- `description`
- path

The scanner is read-only.

## 2. Candidate selection

By default, SpaghettiSkills keeps **every possible pair** regardless of skill count. This prevents routing-induced false negatives, at the cost of potentially many semantic comparisons.

The scanner emits the first 100 candidate pairs by default. Continue using `--pair-offset` and `--pair-limit`; a page of scanner results is not the same as a finished audit. The host agent must account for all reviewed and unreviewed pairs.

Metadata-based routing is available only with explicit `--mode filtered`. It is experimental and can miss contradictions expressed with different vocabulary. Same-name pairs and pairs with missing descriptions are retained as precautionary cases.

This stage does **not** decide whether two skills collide.

Its only question is:

> Are these two skills worth a semantic comparison?

## 3. Semantic review by the user's existing agent

The active coding agent reads each selected `SKILL.md` once per review batch and reuses that content across pair judgments. A detected file is not proof that the skill is available to the same host as another file; the agent must distinguish potential cross-environment conflicts from active ones.

SpaghettiSkills does not create its own model session and does not require its own OpenAI, Anthropic, or other model API key.

The active agent evaluates:

- whether the two skills can apply to the same user task;
- whether their responsibilities are effectively identical;
- whether they share meaningful scope;
- whether instructions become incompatible in that shared scope;
- whether apparent differences are actually context-specific and therefore compatible.

## 4. Classification

Exactly one verdict is assigned:

- `DUPLICATE`
- `OVERLAP`
- `CONFLICT`
- `COMPATIBLE`

A shared keyword is never enough to prove a collision.

A `CONFLICT` requires both shared applicability and incompatible instructions.

## 5. Reporting

The agent reports concrete evidence from each skill and explains the classification.

Recommendations are advisory only.

SpaghettiSkills never performs the recommended modification itself.

## Design principle

**Python discovers and selects. The user's existing agent judges. SpaghettiSkills reports.**

This keeps the project provider-agnostic and read-only while still using semantic reasoning where static matching is insufficient.

## Coverage and failure handling

The scanner exposes the total theoretical and candidate pair counts, the current emitted page count, and the remaining candidate count. The agent must report separately:

- semantic pairs actually reviewed;
- routed-out pairs (experimental mode only);
- candidates not yet reviewed;
- unreadable files and other discovery warnings.

Only pairs actually reviewed may be marked `COMPATIBLE`. An incomplete audit must say so. Exhaustive routing does not guarantee accurate LLM classification; semantic recall and precision require independent evaluation.
