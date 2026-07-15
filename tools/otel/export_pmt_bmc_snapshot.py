#!/usr/bin/env python3
"""Export one BMC PMT Prometheus scrape as an analysis-friendly CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_METRICS_URL = "http://localhost:8889/metrics"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "docs" / "pmt-bmc-snapshot.csv"

DIRECTIVE_RE = re.compile(r"^# (HELP|TYPE) ([A-Za-z_:][A-Za-z0-9_:]*)\s+(.*)$")
SAMPLE_RE = re.compile(
    r"^(?P<name>[A-Za-z_:][A-Za-z0-9_:]*)"
    r"(?:\{(?P<labels>.*)\})?\s+"
    r"(?P<value>[^\s]+)(?:\s+[^\s]+)?$"
)
LABEL_RE = re.compile(r'(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*)=("(?:\\.|[^"\\])*")')

# The OpenTelemetry Prometheus exporter appends a normalized unit to metric names,
# but Prometheus metadata currently leaves its unit field empty. Keep this list
# explicit so inferred units are distinguishable from authoritative XML metadata.
UNIT_SUFFIXES = (
    "nanoseconds",
    "nanosecond",
    "microseconds",
    "microsecond",
    "milliseconds",
    "millisecond",
    "gigahertz",
    "megahertz",
    "kilohertz",
    "fahrenheit",
    "celsius",
    "celcius",
    "seconds",
    "second",
    "millivolts",
    "millivolt",
    "volts",
    "volt",
    "watts",
    "watt",
    "joules",
    "joule",
    "amperes",
    "ampere",
    "amps",
    "gigabytes",
    "megabytes",
    "kilobytes",
    "bytes",
    "byte",
    "percent",
    "ratio",
    "hertz",
    "ticks",
    "count",
)


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def parse_labels(labels_text: str | None) -> dict[str, str]:
    if not labels_text:
        return {}
    labels: dict[str, str] = {}
    for match in LABEL_RE.finditer(labels_text):
        name, quoted_value = match.groups()
        labels[name] = json.loads(quoted_value)
    return labels


def infer_unit(metric_name: str) -> tuple[str, str]:
    name_without_total = metric_name.removesuffix("_total")
    for unit in UNIT_SUFFIXES:
        if name_without_total.endswith(f"_{unit}"):
            return unit, "metric_name_suffix"
    return "", "unspecified"


def parse_exposition(exposition: str, scraped_at: str) -> tuple[list[dict[str, str]], set[str]]:
    helps: dict[str, str] = {}
    types: dict[str, str] = {}
    samples: list[dict[str, str]] = []
    label_names: set[str] = set()

    for line in exposition.splitlines():
        directive = DIRECTIVE_RE.match(line)
        if directive:
            kind, name, value = directive.groups()
            if kind == "HELP":
                helps[name] = value
            else:
                types[name] = value
            continue

        sample = SAMPLE_RE.match(line)
        if not sample:
            continue

        labels = parse_labels(sample.group("labels"))
        if labels.get("PMTEndpoint") != "avc01" or labels.get("CollectionMode") != "redfish":
            continue

        name = sample.group("name")
        unit, unit_source = infer_unit(name)
        label_names.update(labels)
        samples.append(
            {
                "scraped_at_utc": scraped_at,
                "metric_name": name,
                "value": sample.group("value"),
                "unit": unit,
                "unit_source": unit_source,
                "type": types.get(name, "unknown"),
                "help": helps.get(name, ""),
                "labels_json": json.dumps(labels, ensure_ascii=False, sort_keys=True),
                "_labels": labels,
            }
        )

    return samples, label_names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-url", default=DEFAULT_METRICS_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    exposition = fetch_text(args.metrics_url)
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    samples, label_names = parse_exposition(exposition, scraped_at)
    if not samples:
        raise RuntimeError("No avc01 redfish PMT samples found in the exporter response")

    base_fields = [
        "scraped_at_utc",
        "metric_name",
        "value",
        "unit",
        "unit_source",
        "type",
        "help",
    ]
    label_fields = [f"label_{name}" for name in sorted(label_names)]
    fieldnames = base_fields + label_fields + ["labels_json"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for sample in samples:
            labels = sample.pop("_labels")
            row = {**sample, **{f"label_{name}": labels.get(name, "") for name in label_names}}
            writer.writerow(row)

    metric_count = len({sample["metric_name"] for sample in samples})
    print(f"Wrote {len(samples)} BMC PMT series across {metric_count} metric names")
    print(f"Scraped at {scraped_at}")
    print(args.output)


if __name__ == "__main__":
    main()
