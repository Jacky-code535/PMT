#!/usr/bin/env python3
"""Export the currently exposed Intel PMT metrics into a searchable catalog."""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

METRICS_URL = "http://localhost:8889/metrics"
METADATA_URL = "http://localhost:9090/api/v1/metadata"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs"
CSV_PATH = OUTPUT_DIR / "pmt-metrics-catalog.csv"
SUMMARY_PATH = OUTPUT_DIR / "pmt-metrics-summary.md"

DIRECTIVE_RE = re.compile(r"^# (HELP|TYPE) ([A-Za-z_:][A-Za-z0-9_:]*)\s+(.*)$")
SAMPLE_RE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*)(?:\{([^}]*)\})?\s+[-+0-9NnIi.]")
LABEL_NAME_RE = re.compile(r'(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*)=')


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


def classify(name: str, help_text: str) -> str:
    text = f"{name} {help_text}".lower()
    rules = [
        ("采集质量/Data loss", ("data_loss", "data loss", "unable to update all samples")),
        ("温度/Temperature", ("temp", "temperature", "celcius", "celsius")),
        ("频率/Frequency", ("freq", "frequency", "mhz", "clock")),
        ("电压/Voltage", ("volt", "voltage", "mv")),
        ("节流/Throttle", ("throttle", "throttled")),
        ("功率与能量/Power & Energy", ("power", "energy", "watt", "joule")),
        ("使用量与驻留/Usage & Residency", ("usage", "utilization", "residency", "idle")),
        ("错误与故障/Error & Fault", ("error", "fault", "fail", "fatal", "correctable", "uncorrectable")),
        ("内存/Memory", ("memory", "dram", "ddr", "hbm")),
        ("互连与I/O/Interconnect & I/O", ("pcie", "upi", "cxl", "link", "bandwidth", "traffic")),
        ("缓存与CHA/Cache & CHA", ("cache", "cha", "llc")),
        ("延迟/Latency", ("latency",)),
        ("状态与配置/Status & Configuration", ("status", "state", "mode", "enable", "limit")),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "其他计数器/Other"


def main() -> None:
    exposition = fetch_text(METRICS_URL)
    metadata_payload = json.loads(fetch_text(METADATA_URL))
    metadata = metadata_payload.get("data", {})

    helps: dict[str, str] = {}
    types: dict[str, str] = {}
    series_counts: Counter[str] = Counter()
    label_names: dict[str, set[str]] = {}
    avc01_metrics: set[str] = set()

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
        name, labels_text = sample.groups()
        if not labels_text or 'RedfishEndpoint="avc01"' not in labels_text:
            continue
        avc01_metrics.add(name)
        series_counts[name] += 1
        label_names.setdefault(name, set()).update(LABEL_NAME_RE.findall(labels_text))

    rows = []
    for name in sorted(avc01_metrics):
        metric_metadata = metadata.get(name, [{}])
        first_metadata = metric_metadata[0] if metric_metadata else {}
        help_text = helps.get(name) or first_metadata.get("help", "")
        metric_type = types.get(name) or first_metadata.get("type", "unknown")
        unit = first_metadata.get("unit", "")
        rows.append(
            {
                "metric_name": name,
                "category": classify(name, help_text),
                "type": metric_type,
                "unit": unit,
                "series_count": series_counts[name],
                "label_names": ",".join(sorted(label_names.get(name, set()))),
                "help": help_text or "No HELP text exposed; inspect the matching PMT XML definition.",
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    categories = Counter(row["category"] for row in rows)
    metric_types = Counter(row["type"] for row in rows)
    missing_help = sum(row["help"].startswith("No HELP") for row in rows)
    total_series = sum(row["series_count"] for row in rows)

    summary_lines = [
        "# avc01 Intel PMT Metrics 完整清单摘要",
        "",
        "> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 从当前运行的 Collector 与 Prometheus 自动生成。",
        "",
        "## 总数",
        "",
        f"- PMT metric 名称数：**{len(rows)}**",
        f"- 当前 PMT time series 数：**{total_series}**",
        f"- 缺少 HELP 说明的 metric 数：**{missing_help}**",
        "- 完整逐条说明：`docs/pmt-metrics-catalog.csv`",
        "",
        "## 按类别统计",
        "",
        "| 类别 | metric 名称数 |",
        "|---|---:|",
    ]
    summary_lines.extend(f"| {name} | {count} |" for name, count in categories.most_common())
    summary_lines.extend([
        "",
        "## 按 Prometheus 类型统计",
        "",
        "| 类型 | metric 名称数 |",
        "|---|---:|",
    ])
    summary_lines.extend(f"| `{name}` | {count} |" for name, count in metric_types.most_common())
    summary_lines.extend([
        "",
        "## 如何阅读完整 CSV",
        "",
        "| 列 | 含义 |",
        "|---|---|",
        "| `metric_name` | Prometheus 查询时使用的准确名称 |",
        "| `category` | 由名称和 HELP 自动归类，便于搜索；最终物理含义仍以 XML/HELP 为准 |",
        "| `type` | Prometheus metric 类型，例如 gauge/counter |",
        "| `unit` | Prometheus metadata 暴露的单位；为空时查 HELP/XML |",
        "| `series_count` | 当前这个名称因为不同 labels 产生的 time series 数量 |",
        "| `label_names` | 当前 exporter 中观察到的标签名 |",
        "| `help` | PMT XML/receiver 暴露的官方说明，即每条 metric 的主要含义 |",
        "",
        "## 重新生成",
        "",
        "```bash",
        "cd /root/projects/Intel-PMT",
        "/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py",
        "```",
        "",
        "每次更新 PMT XML、切换 BMC 或升级 receiver 后，应重新生成。",
    ])
    SUMMARY_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(rows)} metric definitions and {total_series} series")
    print(CSV_PATH)
    print(SUMMARY_PATH)


if __name__ == "__main__":
    main()
