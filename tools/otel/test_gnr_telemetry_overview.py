"""Static regression tests for the independent GNR telemetry overview."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


OTEL_DIR = Path(__file__).resolve().parent
DASHBOARD = OTEL_DIR / "dashboards" / "pmt-gnr-telemetry-overview.json"
EXPLORER = OTEL_DIR / "dashboards" / "pmt-gnr-metric-explorer.json"
LEGACY_DASHBOARD = OTEL_DIR / "dashboards" / "pmt-redfish-comprehensive.json"


class GnrTelemetryOverviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        cls.panels = cls.dashboard["panels"]
        cls.by_title = {panel["title"]: panel for panel in cls.panels}

    def test_independent_uid_and_balanced_structure(self) -> None:
        self.assertEqual(
            self.dashboard["uid"], "pmt-gnr-telemetry-overview"
        )
        self.assertEqual(
            sum(panel["type"] == "row" for panel in self.panels), 8
        )
        self.assertEqual(
            sum(panel["type"] != "row" for panel in self.panels), 29
        )
        self.assertEqual(
            sum(len(panel.get("targets", [])) for panel in self.panels), 37
        )

    def test_filters_are_simplified_and_oob_is_default(self) -> None:
        variables = self.dashboard["templating"]["list"]
        self.assertEqual(
            [variable["name"] for variable in variables],
            [
                "endpoint",
                "path",
                "socket",
                "core_group",
                "local_core",
            ],
        )
        path = next(variable for variable in variables if variable["name"] == "path")
        self.assertEqual(path["current"]["value"], "redfish")

    def test_temperature_has_no_artificial_warning_threshold(self) -> None:
        highest = self.by_title["Peak Core Temperature"]
        steps = highest["fieldConfig"]["defaults"]["thresholds"]["steps"]
        self.assertEqual(steps, [{"color": "blue", "value": None}])

        hotspots = self.by_title["Current Thermal Hotspots"]
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

    def test_customer_rows_come_before_technical_inventory(self) -> None:
        rows = [panel["title"] for panel in self.panels if panel["type"] == "row"]
        self.assertEqual(rows[0], "00 · Customer Overview")
        self.assertEqual(rows[1], "01 · Core Environment & Activity")
        self.assertEqual(rows[-1], "07 · Technical Inventory & Topology")

    def test_dedicated_explorer_returns_to_new_overview(self) -> None:
        explorer = json.loads(EXPLORER.read_text(encoding="utf-8"))
        self.assertEqual(explorer["uid"], "pmt-gnr-metric-explorer")
        links = {link["title"]: link["url"] for link in explorer["links"]}
        self.assertEqual(
            links["Back to GNR Overview"], "/d/pmt-gnr-telemetry-overview"
        )


if __name__ == "__main__":
    unittest.main()
