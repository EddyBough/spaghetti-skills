import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCAN_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scan.py"
spec = importlib.util.spec_from_file_location("spaghetti_scan", SCAN_PATH)
scan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan
assert spec.loader is not None
spec.loader.exec_module(scan)


class ScanTests(unittest.TestCase):
    def skill(self, name: str, description: str, path: str):
        return scan.Skill(name, description, path, "test", scan.tokenize(f"{name} {description}"))

    def test_parse_folded_frontmatter(self):
        text = "---\nname: demo\ndescription: >-\n  React performance review\n  and bundle optimization.\n---\n# Demo\n"
        self.assertEqual(scan.parse_frontmatter(text), ("demo", "React performance review and bundle optimization."))

    def test_default_exhaustive_even_above_15(self):
        skills = [self.skill(f"skill-{i}", f"unique-{i}", f"/{i}") for i in range(16)]
        pairs = scan.candidate_pairs(skills)
        self.assertEqual(len(pairs), 120)
        self.assertTrue(all(p["selection_reason"] == "exhaustive" for p in pairs))

    def test_default_exhaustive_preserves_zero_similarity(self):
        a = self.skill("banana", "fruit tropical", "/a")
        b = self.skill("database", "postgres migration", "/b")
        pairs = scan.candidate_pairs([a, b])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["lexical_similarity"], 0.0)

    def test_filter_mode_requires_explicit_opt_in(self):
        a = self.skill("banana", "fruit tropical", "/a")
        b = self.skill("database", "postgres migration", "/b")
        self.assertEqual(scan.candidate_pairs([a, b], mode="filtered"), [])

    def test_filtered_same_name_retained_with_different_descriptions(self):
        a = self.skill("schema-audit", "database migrations", "/a")
        b = self.skill("schema audit", "unrelated network interfaces", "/b")
        result = scan.candidate_pairs([a, b], mode="filtered", threshold=1.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["selection_reason"], "same-name")

    def test_missing_description_retained_in_filtered(self):
        a = self.skill("legacy", "", "/a")
        b = self.skill("new", "postgres migrations", "/b")
        result = scan.candidate_pairs([a, b], mode="filtered")
        self.assertEqual(result[0]["selection_reason"], "missing-description-fallback")

    def test_threshold_is_effective(self):
        a = self.skill("alpha", "shared aaaa bbbb cccc", "/a")
        b = self.skill("beta", "shared xxxx yyyy zzzz", "/b")
        low = scan.candidate_pairs([a, b], mode="filtered", threshold=0.01)
        high = scan.candidate_pairs([a, b], mode="filtered", threshold=0.99)
        self.assertEqual(len(low), 1)
        self.assertEqual(high, [])

    def test_pagination_covers_every_pair_once(self):
        skills = [self.skill(f"skill-{i}", f"desc-{i}", f"/{i}") for i in range(16)]
        pairs = scan.candidate_pairs(skills)
        pages = [scan.page_pairs(pairs, offset=i, limit=17) for i in range(0, len(pairs), 17)]
        combined = [p for page in pages for p in page]
        self.assertEqual(combined, pairs)
        self.assertEqual(len({(p["path_a"], p["path_b"]) for p in combined}), 120)

    def test_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):
            scan.candidate_pairs([], mode="unknown")
        with self.assertRaises(ValueError):
            scan.candidate_pairs([], mode="filtered", threshold=1.5)
        with self.assertRaises(ValueError):
            scan.page_pairs([], offset=-1)
        with self.assertRaises(ValueError):
            scan.page_pairs([], limit=0)

    def test_discovery_reports_unreadable_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid = root / "valid" / "SKILL.md"
            invalid = root / "invalid" / "SKILL.md"
            valid.parent.mkdir()
            invalid.parent.mkdir()
            valid.write_text("---\nname: good\ndescription: useful\n---\n", encoding="utf-8")
            invalid.write_bytes(b"\xff\xfe\xfa")
            warnings = []
            found = scan.discover_in(root, "test", set(), warnings)
            self.assertEqual([x.name for x in found], ["good"])
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["error"], "UnicodeDecodeError")

    def test_ignored_directories_are_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / ".cursor" / "skills" / "good"
            bad = root / "node_modules" / "pkg"
            good.mkdir(parents=True)
            bad.mkdir(parents=True)
            (good / "SKILL.md").write_text("---\nname: good\ndescription: useful\n---\n", encoding="utf-8")
            (bad / "SKILL.md").write_text("---\nname: bad\ndescription: ignored\n---\n", encoding="utf-8")
            self.assertEqual(list(scan.iter_skill_files(root)), [good / "SKILL.md"])

    def test_metrics(self):
        m = scan.pair_metrics(11, 55)
        self.assertEqual(m["theoretical_pair_count"], 55)
        self.assertEqual(m["routing_reduction_percent"], 0.0)


if __name__ == "__main__":
    unittest.main()
