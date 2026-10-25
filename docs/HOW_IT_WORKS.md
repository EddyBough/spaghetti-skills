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

For small skill sets (15 or fewer by default), SpaghettiSkills keeps every possible pair. This intentionally favors recall over speed during early usage.

For larger sets, it uses lightweight lexical overlap on routing metadata to remove obviously unrelated pairs.

This stage does **not** decide whether two skills collide.

Its only question is:

> Are these two skills worth a semantic comparison?

## 3. Semantic review by the user's existing agent

The active coding agent reads the complete contents of the two candidate `SKILL.md` files.

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

**Python filters. The user's existing agent judges. SpaghettiSkills reports.**

This keeps the project provider-agnostic and read-only while still using semantic reasoning where static matching is insufficient.
