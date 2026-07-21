#!/usr/bin/env python3
"""Regression tests for the generated PMT metric-family documentation."""

from __future__ import annotations

import csv
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pmt_metric_guides import FAMILY_GUIDES, guide_for_metric


REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "docs" / "pmt-metrics-catalog.csv"


class MetricGuideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CATALOG.open(encoding="utf-8") as source:
            cls.rows = list(csv.DictReader(source))

    def test_family_ids_are_unique(self) -> None:
        ids = [guide.family_id for guide in FAMILY_GUIDES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_current_metric_has_operational_guidance(self) -> None:
        self.assertTrue(self.rows)
        for row in self.rows:
            with self.subTest(metric=row["metric_name"]):
                guide = guide_for_metric(row["metric_name"])
                self.assertNotEqual(guide.family_id, "unclassified")
                self.assertEqual(row["family_id"], guide.family_id)
                self.assertTrue(row["value_semantics"])
                self.assertTrue(row["recommended_query"])
                self.assertTrue(row["caveat"])

    def test_every_declared_family_is_present(self) -> None:
        present = {row["family_id"] for row in self.rows}
        self.assertEqual(present, {guide.family_id for guide in FAMILY_GUIDES})

    def test_data_loss_guidance_preserves_internal_cycle_boundary(self) -> None:
        row = next(
            row for row in self.rows
            if row["metric_name"] == "agg_data_loss_count_total"
        )
        self.assertIn("processing cycle", row["help"])
        self.assertIn("20秒", row["caveat"])
        self.assertIn("delta=0", row["caveat"])


if __name__ == "__main__":
    unittest.main()
