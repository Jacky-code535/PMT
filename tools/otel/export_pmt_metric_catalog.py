#!/usr/bin/env python3
"""Export the currently exposed Intel PMT metrics into a searchable catalog."""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

from pmt_metric_guides import FAMILY_GUIDES, guide_for_metric

METRICS_URLS = {
    "redfish": "http://localhost:8889/metrics",
    "local": "http://10.239.89.3:8889/metrics",
}
METADATA_URL = "http://localhost:9090/api/v1/metadata"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs"
CSV_PATH = OUTPUT_DIR / "pmt-metrics-catalog.csv"
SUMMARY_PATH = OUTPUT_DIR / "pmt-metrics-summary.md"
FAMILY_REFERENCE_PATH = OUTPUT_DIR / "pmt-metric-family-reference.md"

DIRECTIVE_RE = re.compile(r"^# (HELP|TYPE) ([A-Za-z_:][A-Za-z0-9_:]*)\s+(.*)$")
SAMPLE_RE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*)(?:\{([^}]*)\})?\s+[-+0-9NnIi.]")
LABEL_NAME_RE = re.compile(r'(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*)=')

UNIT_SUFFIXES = (
    "nanoseconds", "nanosecond", "microseconds", "microsecond",
    "milliseconds", "millisecond", "gigahertz", "megahertz", "kilohertz",
    "fahrenheit", "celsius", "celcius", "seconds", "second",
    "millivolts", "millivolt", "volts", "volt", "watts", "watt",
    "joules", "joule", "amperes", "ampere", "amps", "gigabytes",
    "megabytes", "kilobytes", "bytes", "byte", "percent", "ratio",
    "hertz", "ticks", "count",
)

CATEGORY_GUIDE = {
    "使用量与驻留/Usage & Residency": "Core 活跃度、C-state、频率/温度/电压区间驻留时间；counter 通常看 rate/increase。",
    "内存/Memory": "RDT MBM local/total 等内存事务累计计数；没有官方字节换算时使用 counts/s，不写成带宽。",
    "温度/Temperature": "Core 当前温度和温度 histogram；即时温度为 °C，histogram 的 `_second_total` 是区间累计时间。",
    "频率/Frequency": "频率区间 histogram；数值是各频率区间累计秒数，不是瞬时 MHz。",
    "电压/Voltage": "电压区间 histogram；数值是各电压区间累计秒数，mV 范围写在 HELP 中。",
    "状态与配置/Status & Configuration": "enable 位、socket/拓扑状态、FIVR 拆分码等；通常为无量纲枚举或 0/1。",
    "功率与能量/Power & Energy": "能量累加器及其时间戳；若 XML 未给换算单位，不根据名称猜测 joule/watt。",
    "节流/Throttle": "Core 在指定 cycle window 中发生 throttle 的累计次数。",
    "其他计数器/Other": "无法仅靠关键词可靠归入其他类别的策略、计数和配置字段；以 HELP/XML 为准。",
    "缓存与CHA/Cache & CHA": "CHA enable、LLC/RDT CMT 等缓存与 Home Agent 信息。",
    "延迟/Latency": "QAT page request、translation、read、get-to-put 等平均或最大延迟，通常为 ns。",
    "互连与I/O/Interconnect & I/O": "QAT PCIe inbound/outbound 累计 MB；使用 rate() 后才是 MB/s。",
    "采集质量/Data loss": "Aggregator 未能在内部周期更新全部 sample 的累计次数和最后时间戳；不等于网络丢包。",
    "错误与故障/Error & Fault": "XML 明确命名为 error/fault/failure 的状态；是否代表硬件故障仍以平台 codebook 为准。",
}


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"Accept": "*/*", "User-Agent": "curl/8.0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
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


def resolve_unit(metric_name: str, metadata_unit: str) -> tuple[str, str]:
    if metadata_unit:
        return metadata_unit, "prometheus_metadata"
    name_without_total = metric_name.removesuffix("_total")
    for unit in UNIT_SUFFIXES:
        if name_without_total.endswith(f"_{unit}"):
            return unit, "metric_name_suffix"
    return "", "unspecified"


def normalized_metric_pattern(metric_name: str) -> str:
    """Collapse numeric array indexes so repeated XML fields form one readable pattern."""
    return re.sub(r"\d+", "N", metric_name)


def markdown_code(value: str) -> str:
    return f"`{value.replace('`', '')}`"


def build_family_reference(
    rows: list[dict],
    total_series: int,
    redfish_series: int,
    inband_series: int,
) -> str:
    family_rows: dict[str, list[dict]] = {}
    for row in rows:
        family_rows.setdefault(row["family_id"], []).append(row)

    lines = [
        "# avc01 Intel PMT Metric Family 详细参考",
        "",
        "> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 生成，并由 `pmt_metric_guides.py` 提供人工审核的运营语义。它按 family 解释当前全部 metric names；每个准确名称的 HELP、family、单位、推荐查询和注意事项见 `pmt-metrics-catalog.csv`。",
        "",
        "## 0. 覆盖范围与阅读顺序",
        "",
        f"- 当前 metric names：**{len(rows)}**",
        f"- 当前人工解释 families：**{len(family_rows)}**",
        f"- 当前 time series：**{total_series}**（Redfish {redfish_series} + Local {inband_series}）",
        f"- 未归类名称：**{len(family_rows.get('unclassified', []))}**",
        "",
        "推荐阅读顺序：",
        "",
        "1. 先读本文件第1–4节，理解类型、时间层次、标签和正常/异常边界；",
        "2. 按业务域查找后面的family章节；",
        "3. 最后到 `pmt-metrics-catalog.csv` 搜索准确metric name；",
        "4. 若HELP仍未定义单位、枚举或物理映射，必须回到匹配XML或咨询platform owner，不能猜。",
        "",
        "## 1. 一个metric必须回答的七个问题",
        "",
        "阅读任何PMT metric时，都应依次确认：",
        "",
        "1. **它来自哪个aggregator？** 看 `PMTGuid`、`DeviceId`、`AccessId`、`SourceId`；",
        "2. **它是gauge还是counter？** gauge通常直接看，counter通常看rate/increase；",
        "3. **单位是否权威？** `unit_source=unspecified`时禁止自行补单位；",
        "4. **编号是局部还是全局？** `c22`通常是aggregator local Core slot，不是Linux CPU 22；",
        "5. **0是什么含义？** 可能是Idle、disabled、有效状态码，也可能没有业务流量；",
        "6. **多久真正更新一次？** PMT内部cycle、20秒Collector读取和15秒Prometheus scrape不是同一层；",
        "7. **它能否代表硬件健康？** data loss、poison、enable和性能counter的风险边界完全不同。",
        "",
        "## 2. Gauge、Counter与“名称看起来像Counter”",
        "",
        "- **Gauge**：当前值或当前导出的状态，通常直接查询；但部分XML累计字段当前仍被导出为gauge，必须结合HELP和单调性判断。",
        "- **Counter**：累计值。绝对值通常没有当前健康意义；`rate(metric[5m])`看每秒变化，`increase(metric[5m])`看窗口新增量。",
        "- **Histogram buckets**：这里不是Prometheus原生histogram，而是12条独立累计驻留counter；应先对每个bucket求rate，再归一化。",
        "- **Timestamp counter**：`*_timestamp_total`可能是25MHz内部ticks，不是事件数量，也不是Unix时间。",
        "",
        "不要只根据 `_total`、`counter`、`seconds` 等名称片段做结论；本项目以XML SampleType、HELP、转换公式和实测变化共同判断。",
        "",
        "## 3. 三层采样时间",
        "",
        "```text",
        "硬件/firmware内部更新周期（未公开，可能远快于20秒）",
        "  → PMT Collector每20秒读取aggregator region",
        "    → Prometheus约每15秒抓取exporter，期间可能重复保存同一PMT值",
        "```",
        "",
        "因此短于PMT原生更新周期的rate窗口可能看到重复值；一条20秒PMT窗口内的data-loss delta也不是“丢了一个20秒snapshot”。",
        "",
        "## 4. Data loss必须怎样解释",
        "",
        "`agg_data_loss_count_total`是CPU/firmware直接提供的64-bit raw cumulative counter。它统计aggregator未能在一个内部processing cycle更新全部samples的累计周期数。",
        "",
        "```text",
        "相邻真实PMT更新：8000 → 8000，delta=0",
        "含义：这段窗口没有新增被记录的未完成周期。",
        "",
        "相邻真实PMT更新：8000 → 8003，delta=3",
        "含义：窗口内有3个processing cycles未完整更新；不是丢了3个字段，也不是丢了3个20秒snapshot。",
        "```",
        "",
        "风险分级：",
        "",
        "- 绝对值很高但保持不变：历史累计，不代表当前有问题；",
        "- 负载期间偶尔增加、后续连续窗口delta=0：短暂质量告警；",
        "- 连续多个真实PMT窗口增长：持续telemetry质量问题；",
        "- workload停止后仍快速增长，并伴随freshness、series、RAS或计算校验异常：需要升级调查。",
        "",
        "Data loss本身不证明CPU硬件故障。公开XML没有总processing-cycle分母、失败字段bitmap或内部scheduler信息，因此不能计算准确loss百分比，也不能指出哪一个sample失败。",
        "",
        "## 5. Core Frequency/Temperature/Voltage Residency区间",
        "",
        "| Bucket | Frequency | Temperature | Voltage |",
        "|---:|---|---|---|",
        "| R0 | Core in C6 | <20°C | <602mV |",
        "| R1 | ≤800MHz | 20.5–27.5°C | 602.5–657mV |",
        "| R2 | 900–1200MHz | 28–35°C | 657.5–712mV |",
        "| R3 | 1300–1600MHz | 35.5–42.5°C | 712.5–767mV |",
        "| R4 | 1700–2000MHz | 43–50°C | 767.5–822mV |",
        "| R5 | 2100–2400MHz | 50.5–57.5°C | 822.5–877mV |",
        "| R6 | 2500–2800MHz | 58–65°C | 877.5–932mV |",
        "| R7 | 2900–3200MHz | 65.5–72.5°C | 932.5–987mV |",
        "| R8 | 3300–3600MHz | 73–80°C | 987.5–1042mV |",
        "| R9 | 3700–4000MHz | 80.5–87.5°C | 1042.5–1097mV |",
        "| R10 | 4100–4400MHz | 88–95°C | 1097.5–1152mV |",
        "| R11 | >4400MHz | >95°C | >1152mV |",
        "",
        "正确驻留百分比计算：同一Core、同一维度的每个bucket先求rate，然后除以12个bucket rate之和。不要把累计seconds直接当百分比。",
        "",
        "## 6. 当前全部Metric Families",
        "",
    ]

    for guide in FAMILY_GUIDES:
        current = family_rows.get(guide.family_id, [])
        if not current:
            continue
        patterns = sorted({normalized_metric_pattern(row["metric_name"]) for row in current})
        examples = [row["metric_name"] for row in current[:3]]
        types = ", ".join(sorted({row["type"] for row in current}))
        units = ", ".join(sorted({row["unit"] or "unspecified" for row in current}))
        categories = ", ".join(sorted({row["category"] for row in current}))
        helps = []
        for row in current:
            if row["help"] not in helps:
                helps.append(row["help"])
            if len(helps) == 2:
                break

        lines.extend([
            f"### 6.{len([line for line in lines if line.startswith('### 6.')]) + 1} {guide.title}",
            "",
            f"- Family ID：`{guide.family_id}`",
            f"- 当前名称数：**{len(current)}**",
            f"- 类别：{categories}",
            f"- Prometheus类型：{types}",
            f"- 单位：{units}",
            f"- 名称模式：{', '.join(markdown_code(pattern) for pattern in patterns)}",
            f"- 示例：{', '.join(markdown_code(example) for example in examples)}",
            "",
            f"**含义：** {guide.meaning}",
            "",
            f"**数值语义：** {guide.value_semantics}",
            "",
            f"**推荐查询/展示：** {guide.recommended_query}",
            "",
            f"**重要边界：** {guide.caveat}",
            "",
            "**代表性官方HELP：**",
            "",
        ])
        lines.extend(f"- {help_text}" for help_text in helps)
        lines.append("")

    lines.extend([
        "## 7. 如何确认每个准确名称都已覆盖",
        "",
        "`pmt-metrics-catalog.csv`中的每一行都包含：",
        "",
        "- `metric_name`：准确Prometheus名称；",
        "- `family_id` / `family_title`：本文件对应章节；",
        "- `value_semantics`：值本身表示什么；",
        "- `recommended_query`：直接看、rate、increase或配对计算；",
        "- `caveat`：最容易误读的边界；",
        "- `help`：Collector/XML暴露的官方说明。",
        "",
        "生成器会统计 `unclassified` family。当前值必须为0；升级XML或firmware后如果出现未分类名称，应先补充 `pmt_metric_guides.py`，再发布新catalog。",
        "",
        "## 8. 标签与拓扑",
        "",
        "同一个metric name会因Redfish/Local、Socket、Access和aggregator实例产生多条series。读取时至少保留：",
        "",
        "```text",
        "CollectionMode + PMTGuid + DeviceId + AccessId",
        "```",
        "",
        "Redfish下定位单个aggregator还需要 `SourceId + PMTSizeBytes`。完整编号规则见 `pmt-platform-topology.md`。",
        "",
        "## 9. 常用PromQL配方",
        "",
        "以下示例只使用PMT数据。把 `CollectionMode=\"redfish\"` 改为 `local` 可做带内交叉验证；不要同时求和两种来源，否则同一硬件值会重复计算。",
        "",
        "```promql",
        "# 每个aggregator最近5分钟新增data-loss cycles",
        "sum by (DeviceId, AccessId, PMTGuid) (",
        "  increase(agg_data_loss_count_total{PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"}[5m])",
        ")",
        "",
        "# 当前有效Core最高温度；排除disabled slot的0°C",
        "max(",
        "  {__name__=~\"c[0-9]+_c[0-9]+_c[0-9]+_c[0-9]+_temp_c[0-9]+_temp_celsius\",PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"} > 0",
        ")",
        "",
        "# 所有Core frequency residency bucket每秒新增seconds",
        "rate({__name__=~\"c[0-9]+_freq_hist_r[0-9]+_second_total\",PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"}[5m])",
        "",
        "# 实验性PMT relative-usage变化率；不是CPU%",
        "rate({__name__=~\"c[0-9]+_usage_meter_core_usage_total\",PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"}[5m])",
        "",
        "# QAT0/1 PCIe总吞吐；结果单位MB/s，0表示没有QAT traffic",
        "sum(rate({__name__=~\"qat[01]_tl_bw_(in|out)_megabytes_total\",PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"}[5m]))",
        "",
        "# FIVR非零2-bit slots；必须同时检查available",
        "sum({__name__=~\"fivr_health_monitor_.*_nonzero_status_count\",PMTEndpoint=\"avc01\",CollectionMode=\"redfish\"})",
        "```",
        "",
        "驻留百分比还需要按同一Core对12个bucket rate求和后归一化；QAT latency只有在throughput或transaction count大于0时才有意义；未知单位的energy、memory bandwidth和MBM不能在PromQL中擅自换算成W或GB/s。",
        "",
        "## 10. 实验和机器学习使用规则",
        "",
        "- 每条trace固定并保存firmware版本、PMT GUID/size、CollectionMode和CPU拓扑；",
        "- Redfish与Local是同一硬件telemetry的两条采集路径，不能当作两份独立训练样本；",
        "- 只在真实PMT值发生更新的边界提取rate/delta，避免Prometheus重复scrape旧值造成伪0；",
        "- `agg_data_loss_count_total`的delta应作为数据质量特征或mask，同时可以保留为候选异常特征；不能直接把data loss当作attack标签；",
        "- CPUID、firmware、enable mask等静态字段适合provenance/分组，不适合作为单机trace中的动态异常特征；",
        "- FIVR poison、disabled Core的0°C和QAT Idle必须编码为状态/缺失语义，不能当作普通数值0训练。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    metadata_payload = json.loads(fetch_text(METADATA_URL))
    metadata = metadata_payload.get("data", {})

    helps: dict[str, str] = {}
    types: dict[str, str] = {}
    series_counts: Counter[str] = Counter()
    source_series_counts: dict[str, Counter[str]] = {
        source: Counter() for source in METRICS_URLS
    }
    label_names: dict[str, set[str]] = {}
    avc01_metrics: set[str] = set()

    for source, metrics_url in METRICS_URLS.items():
        exposition = fetch_text(metrics_url)
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
            if not labels_text or 'PMTEndpoint="avc01"' not in labels_text:
                continue
            avc01_metrics.add(name)
            series_counts[name] += 1
            source_series_counts[source][name] += 1
            label_names.setdefault(name, set()).update(LABEL_NAME_RE.findall(labels_text))

    rows = []
    for name in sorted(avc01_metrics):
        metric_metadata = metadata.get(name, [{}])
        first_metadata = metric_metadata[0] if metric_metadata else {}
        help_text = helps.get(name) or first_metadata.get("help", "")
        metric_type = types.get(name) or first_metadata.get("type", "unknown")
        unit, unit_source = resolve_unit(name, first_metadata.get("unit", ""))
        guide = guide_for_metric(name)
        rows.append(
            {
                "metric_name": name,
                "category": classify(name, help_text),
                "family_id": guide.family_id,
                "family_title": guide.title,
                "type": metric_type,
                "unit": unit,
                "unit_source": unit_source,
                "value_semantics": guide.value_semantics,
                "recommended_query": guide.recommended_query,
                "caveat": guide.caveat,
                "series_count": series_counts[name],
                "redfish_series_count": source_series_counts["redfish"][name],
                "inband_series_count": source_series_counts["local"][name],
                "label_names": ",".join(sorted(label_names.get(name, set()))),
                "help": help_text or "No HELP text exposed; inspect the matching PMT XML definition.",
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    categories = Counter(row["category"] for row in rows)
    metric_types = Counter(row["type"] for row in rows)
    missing_help = sum(row["help"].startswith("No HELP") for row in rows)
    unit_sources = Counter(row["unit_source"] for row in rows)
    total_series = sum(row["series_count"] for row in rows)
    redfish_series = sum(row["redfish_series_count"] for row in rows)
    inband_series = sum(row["inband_series_count"] for row in rows)
    families = Counter(row["family_id"] for row in rows)

    summary_lines = [
        "# avc01 Intel PMT Metrics 完整清单摘要",
        "",
        f"> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 从当前运行的 Collector 与 Prometheus 自动生成。它是初学者入口；{len(rows):,} 个名称的逐条HELP、family、数值语义、查询建议、单位和labels在 `pmt-metrics-catalog.csv`，完整family解释在 `pmt-metric-family-reference.md`。",
        "",
        "## 0. 初学者先理解三个词",
        "",
        "- **Metric name**：一种测量项目，例如某个 core 的当前温度。",
        "- **Time series**：同一个名称加上一组 labels 后形成的独立数据流。同一温度名称会因 socket、aggregator 和采集来源产生多条 series。",
        "- **Sample/data point**：某条 time series 在某一时刻的值。Prometheus 每次抓取都会增加新的 sample，而不是增加新的 metric name。",
        "",
        f"`{len(rows):,} names` 与 `{total_series:,} series` 并不矛盾：后者包含 Redfish/local、DeviceId、AccessId、GUID 等不同标签组合。当前 CPU 与 36 个 aggregator 的完整结构见 `pmt-platform-topology.md`。",
        "",
        "## 1. 当前规模",
        "",
        f"- PMT metric 名称数：**{len(rows)}**",
        f"- 当前 PMT time series 数：**{total_series}**",
        f"  - BMC Redfish：**{redfish_series}**",
        f"  - OS 带内：**{inband_series}**",
        f"- 缺少 HELP 说明的 metric 数：**{missing_help}**",
        f"- 单位来自 Prometheus metadata：**{unit_sources['prometheus_metadata']}**",
        f"- 单位可从 OpenTelemetry metric 后缀推断：**{unit_sources['metric_name_suffix']}**",
        f"- 单位无法可靠确定：**{unit_sources['unspecified']}**",
        f"- 当前人工解释的metric families：**{len(families)}**",
        f"- 未归类metric names：**{families['unclassified']}**",
        "- 完整family参考：`docs/pmt-metric-family-reference.md`",
        "- 完整逐条目录：`docs/pmt-metrics-catalog.csv`",
        "",
        "## 2. 完整指标类别",
        "",
        f"下面覆盖当前全部 {len(rows):,} 个名称。分类由名称和HELP关键词自动生成，便于导航；最终物理语义仍以每行HELP、family guide和匹配XML为准。",
        "",
        "| 类别 | 名称数 | 主要内容与正确读法 |",
        "|---|---:|---|",
    ]
    summary_lines.extend(
        f"| {name} | {count} | {CATEGORY_GUIDE.get(name, '以 HELP/XML 为准。')} |"
        for name, count in categories.most_common()
    )
    summary_lines.extend([
        "",
        "## 3. Prometheus 类型与查询方式",
        "",
        "| 类型 | metric 名称数 |",
        "|---|---:|",
    ])
    summary_lines.extend(f"| `{name}` | {count} |" for name, count in metric_types.most_common())
    summary_lines.extend([
        "",
        "- **gauge**：当前状态或测量值，例如温度、enable、FIVR code；通常直接查询。",
        "- **counter**：从启动或复位起累计，只会上升或归零重启；通常用 `rate(metric[5m])` 看每秒变化，用 `increase(metric[5m])` 看五分钟新增量。",
        "- 名称以 `_second_total` 结尾的 frequency/temperature/voltage histogram 是“落在该区间的累计秒数”，不是瞬时值。",
        "",
        "## 4. 单位为什么有时为空",
        "",
        "当前 Prometheus metadata 没有提供任何 PMT unit。生成器只在名称含标准 OpenTelemetry 后缀时推断单位，并在 `unit_source` 中标记来源：",
        "",
        "| `unit_source` | 含义 | 是否可直接使用 |",
        "|---|---|---|",
        "| `prometheus_metadata` | exporter 明确提供的单位 | 是；当前数量为 0 |",
        "| `metric_name_suffix` | 从 `_celsius`、`_nanoseconds`、`_megabytes_total`、`_second_total` 等后缀推断 | 可以，但必须结合 HELP 理解累计量还是瞬时量 |",
        "| `unspecified` | metadata、名称后缀都不能可靠确定 | 不要猜；查 HELP、XML 或平台 owner |",
        "",
        "重要例外：`agg_data_loss_timestamp_total` 的 HELP 指明它是 25 MHz crystal TSC tick，但名称没有标准 tick 后缀；能量累加器也不能仅凭 `energy` 猜成 joule。完整当前值和每条 series 的 labels 见 `pmt-bmc-snapshot.csv`。",
        "",
        "## 5. 先看代表性指标族，再进入完整Family参考",
        "",
        "`pmt-metric-family-reference.md`覆盖当前所有名称所属的family，并对每个family说明：含义、值的语义、推荐查询、正常/异常边界、代表性HELP和准确名称示例。下面只保留最常用入口：",
        "",
        "| 指标/模式 | 含义 | 类型 | 单位/读法 |",
        "|---|---|---|---|",
        "| `c0_c1_c2_c3_temp_c0_temp_celsius` | Aggregator 局部 Core 0 当前温度 | gauge | °C；0°C 是 disabled 占位值 |",
        "| `c0_freq_hist_r0_second_total` | Core 0 在 frequency range 0/C6 的累计驻留 | counter | seconds；对 12 个 bucket 的 rate 求占比 |",
        "| `c0_temp_hist_r*_second_total` | Core 0 在各温度区间的累计驻留 | counter | seconds；区间范围见 HELP |",
        "| `c0_volt_hist_r*_second_total` | Core 0 在各电压区间的累计驻留 | counter | seconds；mV 范围见 HELP |",
        "| `c0_pvp_throttle_64_total` | 最近 64-cycle window 的 throttle 累计计数 | counter | count；观察 rate/increase |",
        "| `cha0_rmid0_rdt_mbm_total` | CHA 0/RMID 0 memory transaction 累计值 | counter | 单位未定义；应显示 counts/s，不应擅自写 ops/s 或 bytes/s |",
        "| `cha_enabled_mask_cha_0_en` | CHA 0 是否 enable | gauge | 无量纲 0/1 |",
        "| `qat0_tl_bw_in_megabytes_total` | QAT0 PCIe inbound 累计 MB | counter | `rate(...[5m])` 后为 MB/s |",
        "| `qat0_avg_*_nanoseconds` | QAT 平均延迟 | gauge | ns |",
        "| `agg_data_loss_count_total` | Aggregator 未完整更新全部 sample 的累计周期数 | counter | count；只看 increase，不看绝对值是否非零 |",
        "| `fivr_health_monitor_*_status_00`…`31` | 64-bit FIVR word 拆出的 2-bit slot | gauge | code 0–3；slot/枚举无官方映射 |",
        "",
        "Data loss最重要的快速判断：绝对累计值非零不代表当前危险；相邻真实PMT更新的delta=0表示该窗口没有新增未完成周期；持续多个窗口增长、停止workload后仍增长，才是需要升级的数据质量问题。完整解释见family参考的 `data-loss-count` 章节。",
        "",
        "## 6. 如何阅读完整 CSV",
        "",
        "| 列 | 含义 |",
        "|---|---|",
        "| `metric_name` | Prometheus 查询时使用的准确名称 |",
        "| `category` | 由名称和 HELP 自动归类，便于搜索；最终物理含义仍以 XML/HELP 为准 |",
        "| `family_id` | 人工审核的metric family稳定标识；用于跳转family参考 |",
        "| `family_title` | family的人读名称 |",
        "| `type` | Prometheus metric 类型，例如 gauge/counter |",
        "| `unit` | 明确或按标准 metric 后缀推断的单位；为空表示不能可靠确定 |",
        "| `unit_source` | `prometheus_metadata`、`metric_name_suffix` 或 `unspecified` |",
        "| `value_semantics` | 当前值、累计值、时间戳、状态码或驻留bucket应怎样理解 |",
        "| `recommended_query` | 建议直接查询、使用rate/increase、归一化或与配对counter计算 |",
        "| `caveat` | disabled、Idle、poison、未知单位、局部编号等关键误读边界 |",
        "| `series_count` | 当前这个名称因为不同 labels 产生的 time series 数量 |",
        "| `redfish_series_count` | BMC Redfish exporter 中的 time series 数量 |",
        "| `inband_series_count` | OS 带内 exporter 中的 time series 数量 |",
        "| `label_names` | 当前 exporter 中观察到的标签名 |",
        "| `help` | PMT XML/receiver 暴露的官方说明，即每条 metric 的主要含义 |",
        "",
        "查询示例：",
        "",
        "```bash",
        "# 查所有温度指标",
        "rg ',温度/Temperature,' docs/pmt-metrics-catalog.csv",
        "",
        "# 查某个准确名称、HELP 和单位",
        "rg '^c0_c1_c2_c3_temp_c0_temp_celsius,' docs/pmt-metrics-catalog.csv",
        "",
        "# 查单位尚未确定的指标",
        "rg ',unspecified,' docs/pmt-metrics-catalog.csv",
        "```",
        "",
        f"也可以用 LibreOffice/Excel 打开 CSV，按 `family_id`、`category`、`type`、`unit_source` 筛选。不要从头通读 {len(rows):,} 行。",
        "",
        "## 7. 进一步阅读",
        "",
        "- 当前全部metric family的详细语义：`pmt-metric-family-reference.md`",
        "- CPU、Core、36 个 aggregator 和标签：`pmt-platform-topology.md`",
        "- 当前完整采集链路：`complete-pmt-collection-workflow.md`",
        "- FIVR slot、poison 和语义边界：`gnr-fivr-health-collection-workflow.md`",
        "- 单次 BMC 数值、label 与 magnitude：`pmt-bmc-snapshot.csv`",
        "",
        "## 8. 重新生成",
        "",
        "```bash",
        "cd /root/projects/Intel-PMT",
        "/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py",
        "```",
        "",
        "每次更新 PMT XML、切换 BMC 或升级 receiver 后，应重新生成。",
    ])
    SUMMARY_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    FAMILY_REFERENCE_PATH.write_text(
        build_family_reference(rows, total_series, redfish_series, inband_series),
        encoding="utf-8",
    )

    print(f"Wrote {len(rows)} metric definitions and {total_series} series")
    print(CSV_PATH)
    print(SUMMARY_PATH)
    print(FAMILY_REFERENCE_PATH)


if __name__ == "__main__":
    main()
