"""Static regression tests for the independent GNR telemetry overview."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


OTEL_DIR = Path(__file__).resolve().parent
REDFISH = OTEL_DIR / "dashboards" / "pmt-gnr-redfish-overview.json"
LOCAL = OTEL_DIR / "dashboards" / "pmt-gnr-local-overview.json"
EXPLORER = OTEL_DIR / "dashboards" / "pmt-gnr-metric-explorer.json"
LEGACY_DASHBOARD = OTEL_DIR / "dashboards" / "pmt-redfish-comprehensive.json"


class GnrTelemetryOverviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads(REDFISH.read_text(encoding="utf-8"))
        cls.local = json.loads(LOCAL.read_text(encoding="utf-8"))
        cls.panels = cls.dashboard["panels"]
        cls.by_title = {panel["title"]: panel for panel in cls.panels}

    def test_independent_uid_and_balanced_structure(self) -> None:
        self.assertEqual(
            self.dashboard["uid"], "pmt-gnr-redfish-overview"
        )
        self.assertEqual(self.local["uid"], "pmt-gnr-local-overview")
        for dashboard in (self.dashboard, self.local):
            panels = dashboard["panels"]
            self.assertEqual(sum(p["type"] == "row" for p in panels), 7)
            self.assertEqual(sum(p["type"] != "row" for p in panels), 25)
            self.assertEqual(
                sum(len(p.get("targets", [])) for p in panels), 32
            )

    def test_each_overview_has_one_global_filter_and_fixed_path(self) -> None:
        for dashboard, mode in (
            (self.dashboard, "redfish"),
            (self.local, "local"),
        ):
            variables = dashboard["templating"]["list"]
            self.assertEqual(
                [variable["name"] for variable in variables], ["endpoint"]
            )
            expressions = [
                target["expr"]
                for panel in dashboard["panels"]
                for target in panel.get("targets", [])
            ]
            self.assertTrue(all("$path" not in expr for expr in expressions))
            self.assertTrue(
                any(f'CollectionMode="{mode}"' in expr for expr in expressions)
            )

    def test_temperature_has_no_artificial_warning_threshold(self) -> None:
        highest = self.by_title["Peak Core Temperature"]
        steps = highest["fieldConfig"]["defaults"]["thresholds"]["steps"]
        self.assertEqual(steps, [{"color": "blue", "value": None}])

        hotspots = self.by_title["Top 12 Core Temperatures"]
        steps = hotspots["fieldConfig"]["defaults"]["thresholds"]["steps"]
        self.assertEqual(steps, [{"color": "blue", "value": None}])

    def test_raw_panels_do_not_claim_physical_units(self) -> None:
        for title, panel in self.by_title.items():
            if "· Raw" not in title:
                continue
            unit = panel.get("fieldConfig", {}).get("defaults", {}).get("unit")
            self.assertNotIn(unit, {"percent", "watt", "joule", "Bps", "GBs"})

    def test_legacy_dashboard_keeps_its_uid(self) -> None:
        legacy = json.loads(LEGACY_DASHBOARD.read_text(encoding="utf-8"))
        self.assertEqual(legacy["uid"], "pmt-avc01-redfish")
        self.assertNotEqual(legacy["uid"], self.dashboard["uid"])

    def test_overview_rows_come_before_technical_inventory(self) -> None:
        rows = [panel["title"] for panel in self.panels if panel["type"] == "row"]
        self.assertEqual(rows[0], "00 · Overview")
        self.assertEqual(rows[1], "01 · Core Environment & Activity")
        self.assertEqual(rows[-1], "06 · Technical Inventory & Topology")

    def test_aggregator_legends_are_path_aware(self) -> None:
        hotspots = self.by_title["Top 12 Core Temperatures"]
        expr = hotspots["targets"][0]["expr"]
        self.assertNotIn("OOB AGG", expr)
        self.assertNotIn("LOCAL AGG", expr)
        self.assertEqual(expr.count("AGG[$1]"), 2)
        self.assertEqual(
            hotspots["targets"][0]["legendFormat"],
            "{{agg_display}} · Core {{core}}",
        )
        self.assertEqual(hotspots["gridPos"]["w"], 24)
        peak = self.by_title["Maximum Core Temperature Trend"]
        self.assertEqual(peak["gridPos"]["x"], 0)
        self.assertEqual(peak["gridPos"]["w"], 24)

    def test_overviews_link_to_each_other(self) -> None:
        redfish_links = {
            link["title"]: link["url"] for link in self.dashboard["links"]
        }
        local_links = {
            link["title"]: link["url"] for link in self.local["links"]
        }
        self.assertEqual(
            redfish_links["Open Local Overview"],
            "/d/pmt-gnr-local-overview?var-endpoint=$endpoint",
        )
        self.assertEqual(
            local_links["Open Redfish Overview"],
            "/d/pmt-gnr-redfish-overview?var-endpoint=$endpoint",
        )

    def test_dashboard_descriptions_are_concise(self) -> None:
        forbidden = ("No artificial", "does not mean", "must not", "not a ")
        for dashboard in (self.dashboard, self.local):
            for panel in dashboard["panels"]:
                description = panel.get("description", "")
                self.assertFalse(
                    any(token in description for token in forbidden),
                    f"{panel['title']}: {description}",
                )

    def test_dedicated_explorer_returns_to_new_overview(self) -> None:
        explorer = json.loads(EXPLORER.read_text(encoding="utf-8"))
        self.assertEqual(explorer["uid"], "pmt-gnr-metric-explorer")
        links = {link["title"]: link["url"] for link in explorer["links"]}
        self.assertEqual(
            links["Back to Redfish Overview"],
            "/d/pmt-gnr-redfish-overview",
        )


if __name__ == "__main__":
    unittest.main()
