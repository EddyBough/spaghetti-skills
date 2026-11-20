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


def discover_in(
    root: Path, source: str, excluded: set[str], warnings: list[dict] | None = None
) -> list[Skill]:
    skills: list[Skill] = []
    if not root.exists():
        return skills

    for path in sorted(iter_skill_files(root)):
        try:
            resolved = str(path.resolve())
            if resolved in excluded:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            if warnings is not None:
                warnings.append({"path": str(path), "error": type(exc).__name__})
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


def discover(
    roots: list[tuple[str, Path]], excluded: set[str], warnings: list[dict] | None = None
) -> list[Skill]:
    by_path: dict[str, Skill] = {}
    for source, root in roots:
        for skill in discover_in(root, source, excluded, warnings):
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


def candidate_pairs(
    skills: list[Skill], mode: str = "exhaustive", threshold: float = 0.08
) -> list[dict]:
    """Select pairs only. Filtered mode is opt-in and can miss real collisions."""
    if mode not in {"exhaustive", "filtered"}:
        raise ValueError(f"Unsupported routing mode: {mode}")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    pairs: list[dict] = []
    for a, b in itertools.combinations(skills, 2):
        shared = sorted(set(a.terms) & set(b.terms))
        score = similarity(a, b)

        if mode == "exhaustive":
            reason = "exhaustive"
        elif normalized_name(a.name) == normalized_name(b.name):
            reason = "same-name"
        elif not a.description.strip() or not b.description.strip():
            # Missing metadata is uncertainty, not evidence of compatibility.
            reason = "missing-description-fallback"
        elif score >= threshold:
            reason = "metadata-similarity"
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
            "lexical_similarity": round(score, 4),
            "selection_reason": reason,
        })
    return pairs


def page_pairs(pairs: list[dict], offset: int = 0, limit: int | None = None) -> list[dict]:
    """Return a deterministic page without marking other candidates compatible."""
    if offset < 0 or (limit is not None and limit <= 0):
        raise ValueError("offset must be non-negative and limit must be positive")
    return pairs[offset:] if limit is None else pairs[offset:offset + limit]


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
    parser.add_argument("--mode", choices=("exhaustive", "filtered"), default="exhaustive", help="Exhaustive by default; filtered is experimental and can miss collisions")
    parser.add_argument("--pair-offset", type=int, default=0, help="First candidate pair to emit (default: 0)")
    parser.add_argument("--pair-limit", type=int, default=100, help="Maximum pairs per output page (default: 100)")
    parser.add_argument("--threshold", type=float, default=0.08, help="Metadata Jaccard threshold for larger sets")
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    if args.pair_offset < 0 or (args.pair_limit is not None and args.pair_limit <= 0):
        parser.error("--pair-offset must be >= 0 and --pair-limit must be > 0")

    project_root = Path(args.root).expanduser().resolve()
    if not project_root.is_dir():
        parser.error(f"Project directory not found: {project_root}")
    roots = source_roots(project_root, args.source, include_global=not args.no_global)

    self_skill = Path(__file__).resolve().parent.parent / "SKILL.md"
    excluded = {str(self_skill.resolve())}

    warnings: list[dict] = []
    skills = discover(roots, excluded, warnings)
    pairs = candidate_pairs(skills, mode=args.mode, threshold=args.threshold)
    emitted = page_pairs(pairs, args.pair_offset, args.pair_limit)
    metrics = pair_metrics(len(skills), len(pairs))
    paths_to_read = sorted({p["path_a"] for p in emitted} | {p["path_b"] for p in emitted})

    result = {
        "project_root": str(project_root),
        "read_only": True,
        "routing_mode": args.mode,
        "routing_exhaustive": args.mode == "exhaustive",
        "discovery_warnings": warnings,
        "scope_note": "Discovered files are not proof that two skills activate together in a specific host.",
        "sources_scanned": [{"label": label, "path": str(path)} for label, path in roots],
        "skills_found": len(skills),
        "skills": [asdict(s) for s in skills],
        **metrics,
        "pairs_routed_out": metrics["theoretical_pair_count"] - len(pairs),
        "pair_offset": args.pair_offset,
        "emitted_pair_count": len(emitted),
        "remaining_pair_count": max(0, len(pairs) - args.pair_offset - len(emitted)),
        "skills_requiring_semantic_read": len(paths_to_read),
        "semantic_read_paths": paths_to_read,
        "candidate_pairs": emitted,
        "note": "Scanner output is not a semantic verdict. Review every candidate page. Never count filtered-out or unreviewed pairs as COMPATIBLE.",
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "SpaghettiSkills scanner — "
            f"{len(skills)} skills, {len(pairs)}/{metrics['theoretical_pair_count']} candidate pairs "
            f"({metrics['routing_reduction_percent']}% routed out)"
        )
        print(f"Mode: {args.mode}. Emitted {len(emitted)}; remaining {result['remaining_pair_count']}.")
        if warnings:
            print(f"Warning: {len(warnings)} unreadable skill file(s).")
        for p in emitted:
            shared = ", ".join(p["shared_terms"][:6]) or p["selection_reason"]
            print(f"- {p['skill_a']} ↔ {p['skill_b']}  [{shared}]")


if __name__ == "__main__":
    main()
