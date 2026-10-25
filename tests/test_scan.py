import importlib.util
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
        return scan.Skill(
            name,
            description,
            path,
            "test",
            scan.tokenize(f"{name} {description}"),
        )

    def test_parse_folded_frontmatter(self):
        text = (
            "---\n"
            "name: demo\n"
            "description: >-\n"
            "  React performance review\n"
            "  and bundle optimization.\n"
            "---\n"
            "# Demo\n"
        )
        self.assertEqual(
            scan.parse_frontmatter(text),
            ("demo", "React performance review and bundle optimization."),
        )

    def test_same_name_is_always_candidate(self):
        a = self.skill("ui-ux-pro-max", "visual design", "/a")
        b = self.skill("ui ux pro max", "totally different metadata", "/b")
        pairs = scan.candidate_pairs([a, b], all_pairs_limit=0, threshold=0.99)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["selection_reason"], "same-skill-name")

    def test_unrelated_pair_is_filtered_for_larger_sets(self):
        a = self.skill("frontend-design", "typography layout visual identity", "/a")
        b = self.skill("security-audit", "auth csrf trust boundary vulnerability", "/b")
        pairs = scan.candidate_pairs([a, b], all_pairs_limit=0, threshold=0.08)
        self.assertEqual(pairs, [])

    def test_related_metadata_pair_is_kept(self):
        a = self.skill("ui-review", "react performance bundle rerender", "/a")
        b = self.skill("react-performance", "react performance waterfalls bundle", "/b")
        pairs = scan.candidate_pairs([a, b], all_pairs_limit=0, threshold=0.08)
        self.assertEqual(len(pairs), 1)
        self.assertIn(
            pairs[0]["selection_reason"],
            {"shared-routing-domain", "routing-metadata-similarity"},
        )

    def test_frontend_design_and_ui_ux_are_preserved_by_domain_routing(self):
        frontend = self.skill(
            "frontend-design",
            "Distinctive frontend interfaces with strong visual identity, typography and layout.",
            "/frontend",
        )
        uiux = self.skill(
            "ui-ux-pro-max",
            "UI UX design systems, palettes, accessibility, components and web styles.",
            "/uiux",
        )
        pairs = scan.candidate_pairs([frontend, uiux], all_pairs_limit=0, threshold=0.99)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["selection_reason"], "shared-routing-domain")
        self.assertIn("frontend-ui", pairs[0]["shared_routing_domains"])

    def test_distinct_domains_can_still_be_filtered(self):
        design = self.skill(
            "frontend-design",
            "Visual interface typography layout palette",
            "/design",
        )
        security = self.skill(
            "security-audit",
            "Authentication CSRF SSRF vulnerability trust boundary",
            "/security",
        )
        pairs = scan.candidate_pairs([design, security], all_pairs_limit=0, threshold=0.99)
        self.assertEqual(pairs, [])

    def test_ignored_directories_are_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / ".cursor" / "skills" / "good"
            bad = root / "node_modules" / "pkg"
            good.mkdir(parents=True)
            bad.mkdir(parents=True)
            (good / "SKILL.md").write_text(
                "---\nname: good\ndescription: useful\n---\n",
                encoding="utf-8",
            )
            (bad / "SKILL.md").write_text(
                "---\nname: bad\ndescription: ignored\n---\n",
                encoding="utf-8",
            )
            found = list(scan.iter_skill_files(root))
            self.assertEqual(found, [good / "SKILL.md"])

    def test_pair_metrics(self):
        metrics = scan.pair_metrics(11, 6)
        self.assertEqual(metrics["theoretical_pair_count"], 55)
        self.assertEqual(metrics["candidate_pair_count"], 6)
        self.assertEqual(metrics["routing_reduction_percent"], 89.1)


if __name__ == "__main__":
    unittest.main()
