#!/usr/bin/env python3
"""Read-only Agent Skill discovery and candidate-pair scanner for SpaghettiSkills."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "use",
    "user", "when", "with", "your", "you", "asks", "asked", "build", "building",
    "skill", "agent", "agents",
}

DEFAULT_PROJECT_DIRS = (".agents/skills", ".codex/skills", ".claude/skills", ".cursor/skills")
DEFAULT_GLOBAL_DIRS = (
    "~/.agents/skills",
    "${CODEX_HOME:-$HOME/.codex}/skills",
    "~/.claude/skills",
    "~/.cursor/skills",
)
IGNORED_DIR_NAMES = {
    ".git", ".next", ".turbo", ".venv", "__pycache__", "build", "coverage",
    "dist", "node_modules", "out", "vendor", "venv",
}

# Conservative routing domains. These are not classifications; they only prevent
# plausible semantic collisions from being discarded before LLM review.
ROUTING_DOMAINS: dict[str, frozenset[str]] = {
    "frontend-ui": frozenset({
        "a11y", "accessibility", "component", "components", "design", "frontend",
        "interface", "layout", "palette", "style", "styles", "typography", "ui",
        "ux", "visual", "web",
    }),
    "react": frozenset({
        "bundle", "client-components", "next", "next.js", "nextjs", "react", "rerender",
        "rerenders", "rsc", "server-components", "suspense", "waterfall", "waterfalls",
    }),
    "security": frozenset({
        "auth", "csrf", "injection", "jwt", "oauth", "security", "ssrf", "threat",
        "trust", "vulnerability", "vulnerabilities", "xss",
    }),
    "code-review": frozenset({
        "audit", "defect", "defects", "finding", "findings", "review", "reviewing",
    }),
    "documentation": frozenset({
        "docs", "documentation", "reference", "references",
    }),
    "image": frozenset({
        "image", "images", "illustration", "photo", "visuals",
    }),
}


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: str
    source: str
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


def expand_default_path(raw: str) -> Path:
    if raw.startswith("${CODEX_HOME:-"):
        codex_home = os.environ.get("CODEX_HOME")
        base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
        return base / "skills"
    return Path(os.path.expandvars(raw)).expanduser()


def source_roots(project_root: Path, extra_sources: Iterable[str], include_global: bool) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = [("project", project_root)]

    for rel in DEFAULT_PROJECT_DIRS:
        path = project_root / rel
        if path.exists():
            roots.append((f"project:{rel}", path))

    if include_global:
        for raw in DEFAULT_GLOBAL_DIRS:
            path = expand_default_path(raw)
            if path.exists():
                roots.append((f"global:{path}", path))

    for raw in extra_sources:
        path = Path(os.path.expandvars(raw)).expanduser().resolve()
        if path.exists():
            roots.append((f"extra:{path}", path))

    seen: set[str] = set()
    unique: list[tuple[str, Path]] = []
    for label, path in roots:
        try:
            resolved = str(path.resolve())
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique.append((label, Path(resolved)))
    return unique


def iter_skill_files(root: Path) -> Iterator[Path]:
    """Yield SKILL.md files while pruning common dependency/build directories."""
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIR_NAMES)
        if "SKILL.md" in files:
            yield Path(current) / "SKILL.md"


def discover_in(root: Path, source: str, excluded: set[str]) -> list[Skill]:
    skills: list[Skill] = []
    if not root.exists():
        return skills

    for path in sorted(iter_skill_files(root)):
        try:
            resolved = str(path.resolve())
            if resolved in excluded:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        name, description = parse_frontmatter(text)
        if not name:
            name = path.parent.name
        terms = tokenize(f"{name} {description}")
        skills.append(
            Skill(
                name=name,
                description=description,
                path=resolved,
                source=source,
                terms=terms,
            )
        )
    return skills


def discover(roots: list[tuple[str, Path]], excluded: set[str]) -> list[Skill]:
    by_path: dict[str, Skill] = {}
    for source, root in roots:
        for skill in discover_in(root, source, excluded):
            by_path.setdefault(skill.path, skill)
    return sorted(by_path.values(), key=lambda s: (s.name.lower(), s.path))


def similarity(a: Skill, b: Skill) -> float:
    sa, sb = set(a.terms), set(b.terms)
    if not sa or not sb:
        return 0.0
    intersection = len(sa & sb)
    union = len(sa | sb)
    return intersection / union if union else 0.0


def normalized_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def routing_domains(skill: Skill) -> tuple[str, ...]:
    terms = set(skill.terms)
    return tuple(sorted(
        domain for domain, indicators in ROUTING_DOMAINS.items()
        if terms & indicators
    ))


def candidate_pairs(skills: list[Skill], all_pairs_limit: int, threshold: float) -> list[dict]:
    pairs: list[dict] = []
    keep_all = len(skills) <= all_pairs_limit

    for a, b in itertools.combinations(skills, 2):
        shared = sorted(set(a.terms) & set(b.terms))
        score = similarity(a, b)
        same_name = normalized_name(a.name) == normalized_name(b.name)
        shared_domains = sorted(set(routing_domains(a)) & set(routing_domains(b)))

        if keep_all:
            reason = "all-pairs-small-set"
        elif same_name:
            reason = "same-skill-name"
        elif shared_domains:
            reason = "shared-routing-domain"
        elif score >= threshold:
            reason = "routing-metadata-similarity"
        else:
            continue

        pairs.append({
            "skill_a": a.name,
            "skill_b": b.name,
            "path_a": a.path,
            "path_b": b.path,
            "source_a": a.source,
            "source_b": b.source,
            "shared_terms": shared,
            "shared_routing_domains": shared_domains,
            "lexical_similarity": round(score, 4),
            "selection_reason": reason,
        })
    return pairs


def pair_metrics(skill_count: int, candidate_count: int) -> dict[str, float | int]:
    theoretical = skill_count * (skill_count - 1) // 2
    reduction = 0.0 if theoretical == 0 else (1 - candidate_count / theoretical) * 100
    return {
        "theoretical_pair_count": theoretical,
        "candidate_pair_count": candidate_count,
        "routing_reduction_percent": round(reduction, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Agent Skills and select pairs for semantic review.")
    parser.add_argument("--root", default=".", help="Project directory to scan (default: current directory)")
    parser.add_argument("--source", action="append", default=[], help="Additional skill directory to scan; repeatable")
    parser.add_argument("--no-global", action="store_true", help="Do not scan known global skill directories")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--all-pairs-limit", type=int, default=6, help="Keep all pairs when <= N skills")
    parser.add_argument("--threshold", type=float, default=0.08, help="Metadata Jaccard threshold for larger sets")
    args = parser.parse_args()

    project_root = Path(args.root).expanduser().resolve()
    roots = source_roots(project_root, args.source, include_global=not args.no_global)

    self_skill = Path(__file__).resolve().parent.parent / "SKILL.md"
    excluded = {str(self_skill.resolve())}

    skills = discover(roots, excluded)
    pairs = candidate_pairs(skills, args.all_pairs_limit, args.threshold)
    metrics = pair_metrics(len(skills), len(pairs))
    paths_to_read = sorted({p["path_a"] for p in pairs} | {p["path_b"] for p in pairs})

    result = {
        "project_root": str(project_root),
        "read_only": True,
        "sources_scanned": [{"label": label, "path": str(path)} for label, path in roots],
        "skills_found": len(skills),
        "skills": [asdict(s) for s in skills],
        **metrics,
        "skills_requiring_semantic_read": len(paths_to_read),
        "semantic_read_paths": paths_to_read,
        "candidate_pairs": pairs,
        "note": "Routing only. Read each semantic candidate skill once, then classify candidate pairs using SKILL.md.",
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "SpaghettiSkills scanner — "
            f"{len(skills)} skills, {len(pairs)}/{metrics['theoretical_pair_count']} candidate pairs "
            f"({metrics['routing_reduction_percent']}% routed out)"
        )
        for p in pairs:
            routing_hint = ", ".join(p["shared_routing_domains"] or p["shared_terms"][:6])
            routing_hint = routing_hint or p["selection_reason"]
            print(f"- {p['skill_a']} ↔ {p['skill_b']}  [{routing_hint}]")


if __name__ == "__main__":
    main()
