#!/usr/bin/env python3
"""Read-only Agent Skill discovery and candidate-pair scanner for SpaghettiSkills."""

from __future__ import annotations

import argparse
import itertools
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "use",
    "user", "when", "with", "your", "you", "asks", "asked", "build", "building",
    "skill", "agent", "agents",
}


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: str
    terms: tuple[str, ...]


def parse_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", ""
    end = text.find("\n---", 3)
    if end == -1:
        return "", ""
    block = text[3:end]
    name = ""
    description_lines: list[str] = []
    in_description = False

    for raw in block.splitlines():
        line = raw.rstrip()
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"\'')
            in_description = False
            continue
        if line.startswith("description:"):
            value = line.split(":", 1)[1].strip()
            in_description = True
            if value not in {">", ">-", "|", "|-"}:
                description_lines.append(value.strip('"\''))
            continue
        if in_description:
            if line and not line.startswith(" "):
                in_description = False
            elif line.strip():
                description_lines.append(line.strip())

    return name, " ".join(description_lines).strip()


def tokenize(text: str) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9][a-z0-9+.#_-]*", text.lower())
    return tuple(sorted({t for t in tokens if len(t) > 2 and t not in STOPWORDS}))


def discover(root: Path) -> list[Skill]:
    skills: list[Skill] = []
    this_skill = (root / "SKILL.md").resolve()
    for path in sorted(root.rglob("SKILL.md")):
        try:
            if path.resolve() == this_skill:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        name, description = parse_frontmatter(text)
        if not name:
            name = path.parent.name
        terms = tokenize(f"{name} {description}")
        skills.append(Skill(name=name, description=description, path=str(path), terms=terms))
    return skills


def similarity(a: Skill, b: Skill) -> float:
    sa, sb = set(a.terms), set(b.terms)
    if not sa or not sb:
        return 0.0
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / union if union else 0.0


def candidate_pairs(skills: list[Skill], all_pairs_limit: int, threshold: float) -> list[dict]:
    pairs = []
    keep_all = len(skills) <= all_pairs_limit
    for a, b in itertools.combinations(skills, 2):
        shared = sorted(set(a.terms) & set(b.terms))
        score = similarity(a, b)
        if keep_all or shared or score >= threshold:
            pairs.append({
                "skill_a": a.name,
                "skill_b": b.name,
                "path_a": a.path,
                "path_b": b.path,
                "shared_terms": shared,
                "lexical_similarity": round(score, 4),
                "selection_reason": "all-pairs-small-set" if keep_all else "routing-metadata-overlap",
            })
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Agent Skills and select pairs for semantic review.")
    parser.add_argument("--root", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--all-pairs-limit", type=int, default=15, help="Keep all pairs when <= N skills")
    parser.add_argument("--threshold", type=float, default=0.08, help="Lexical Jaccard threshold for larger sets")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    skills = discover(root)
    pairs = candidate_pairs(skills, args.all_pairs_limit, args.threshold)
    result = {
        "root": str(root),
        "read_only": True,
        "skills_found": len(skills),
        "skills": [asdict(s) for s in skills],
        "candidate_pairs": pairs,
        "candidate_pair_count": len(pairs),
        "note": "Candidate selection only. Semantic classification must be performed by the active agent using SKILL.md.",
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"SpaghettiSkills scanner — {len(skills)} skills, {len(pairs)} candidate pairs")
        for p in pairs:
            shared = ", ".join(p["shared_terms"][:6]) or "all-pairs mode"
            print(f"- {p['skill_a']} ↔ {p['skill_b']}  [{shared}]")


if __name__ == "__main__":
    main()
