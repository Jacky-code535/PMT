#!/usr/bin/env python3
"""Generate the provisioned Grafana dashboard for BMC and in-band Intel PMT metrics."""

from __future__ import annotations

import json
from pathlib import Path

DATASOURCE = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}
REPO_OUTPUT = Path(__file__).parent / "dashboards" / "pmt-redfish-comprehensive.json"
SYSTEM_OUTPUT = Path("/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json")
REPO_EXPLORER_OUTPUT = Path(__file__).parent / "dashboards" / "pmt-metric-explorer.json"
SYSTEM_EXPLORER_OUTPUT = Path("/var/lib/grafana/dashboards/pmt-backend-test/pmt-metric-explorer.json")

panels: list[dict] = []
panel_id = 0
y = 0
BAR_LABEL_SIZE = 10
BAR_VALUE_SIZE = 10


def next_id() -> int:
    global panel_id
    panel_id += 1
    return panel_id


def target(expr: str, legend: str = "", ref: str = "A", instant: bool = False, fmt: str = "time_series") -> dict:
    result = {"expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        result.update({"instant": True, "range": False, "format": fmt})
    return result


def row(title: str, description: str) -> None:
    global y
    panels.append({
        "id": next_id(), "type": "row", "title": title, "description": description,
        "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": [],
    })
    y += 1


def base_panel(title: str, description: str, x: int, w: int, h: int, panel_type: str) -> dict:
    return {
        "id": next_id(), "type": panel_type, "title": title, "description": description,
        "datasource": DATASOURCE, "gridPos": {"h": h, "w": w, "x": x, "y": y},
    }


def add_stat(title: str, description: str, x: int, w: int, expr: str, unit: str = "short",
             thresholds: list[dict] | None = None, color_mode: str = "value", legend: str = "",
             mappings: list[dict] | None = None, height: int = 4,
             no_value: str | None = None) -> None:
    panel = base_panel(title, description, x, w, height, "stat")
    defaults = {
        "color": {"mode": "thresholds"}, "unit": unit,
        "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]},
        "mappings": mappings or [],
    }
    if no_value is not None:
        defaults["noValue"] = no_value
    panel.update({
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "colorMode": color_mode, "graphMode": "area", "justifyMode": "center", "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "textMode": "auto",
        },
        "targets": [target(expr, legend)],
    })
    panels.append(panel)


def add_timeseries(title: str, description: str, x: int, w: int, h: int, targets: list[dict],
                   unit: str = "short", minimum: float | None = None, maximum: float | None = None,
                   stacking: str = "none", legend_place: str = "bottom",
                   no_value: str | None = None, decimals: int | None = None) -> None:
    global y
    defaults: dict = {"color": {"mode": "palette-classic"}, "unit": unit,
                      "custom": {"drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
                                 "fillOpacity": 12 if stacking == "none" else 35, "gradientMode": "opacity",
                                 "showPoints": "never", "spanNulls": True,
                                 "stacking": {"mode": stacking, "group": "A"},
                                 "axisPlacement": "auto", "axisLabel": "", "scaleDistribution": {"type": "linear"}}}
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    if no_value is not None:
        defaults["noValue"] = no_value
    if decimals is not None:
        defaults["decimals"] = decimals
    panel = base_panel(title, description, x, w, h, "timeseries")
    panel.update({
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "legend": {"calcs": ["lastNotNull", "max"], "displayMode": "table",
                       "placement": legend_place, "showLegend": True, "width": 360},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
    })
    panels.append(panel)


def add_bar_gauge(title: str, description: str, x: int, w: int, h: int, expr: str, legend: str,
                  unit: str = "short", minimum: float | None = None, maximum: float | None = None,
                  thresholds: list[dict] | None = None) -> None:
    defaults: dict = {
        "color": {"mode": "thresholds"}, "unit": unit,
        "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "blue", "value": None}]},
    }
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    panel = base_panel(title, description, x, w, h, "bargauge")
    panel.update({
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"displayMode": "gradient", "minVizHeight": 10, "minVizWidth": 0,
                    "namePlacement": "left", "orientation": "horizontal", "reduceOptions": {
                        "calcs": ["lastNotNull"], "fields": "", "values": False}, "showUnfilled": True,
                    "sizing": "auto", "valueMode": "color",
                    "text": {"titleSize": BAR_LABEL_SIZE, "valueSize": BAR_VALUE_SIZE}},
        "targets": [target(expr, legend, instant=True)],
    })
    panels.append(panel)


def add_residency_bar(title: str, description: str, x: int, w: int, h: int, expr: str) -> None:
    panel = base_panel(title, description, x, w, h, "bargauge")
    panel.update({
        "fieldConfig": {"defaults": {
            "color": {"mode": "fixed", "fixedColor": "blue"}, "unit": "percent",
            "decimals": 1, "min": 0, "max": 100,
            "displayName": "${__field.labels.range}",
        }, "overrides": []},
        "options": {
            "displayMode": "gradient", "minVizHeight": 22, "maxVizHeight": 22, "minVizWidth": 0,
            "namePlacement": "left", "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showUnfilled": True, "sizing": "manual", "valueMode": "text",
            "text": {"titleSize": BAR_LABEL_SIZE, "valueSize": BAR_VALUE_SIZE},
        },
        "targets": [target(expr, "{{range}}", instant=True)],
    })
    panels.append(panel)


def add_table(title: str, description: str, x: int, w: int, h: int, queries: list[dict]) -> None:
    panel = base_panel(title, description, x, w, h, "table")
    panel.update({
        "fieldConfig": {"defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"},
                                                   "inspect": False}, "mappings": [], "thresholds": {
                                                       "mode": "absolute", "steps": [{"color": "blue", "value": None}]}},
                        "overrides": []},
        "options": {"cellHeight": "sm", "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False},
                    "showHeader": True, "sortBy": [{"desc": True, "displayName": "Value"}]},
        "targets": queries,
        "transformations": [{"id": "labelsToFields", "options": {"mode": "columns"}}],
    })
    panels.append(panel)


def add_fivr_detail_table(title: str, description: str, x: int, w: int, h: int, expr: str) -> None:
    panel = base_panel(title, description, x, w, h, "table")
    panel.update({
        "fieldConfig": {"defaults": {
            "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
            "mappings": [], "noValue": "No non-zero slots",
            "thresholds": {"mode": "absolute", "steps": [
                {"color": "green", "value": None},
                {"color": "yellow", "value": 1},
                {"color": "red", "value": 2},
            ]},
        }, "overrides": [{
            "matcher": {"id": "byName", "options": "Code"},
            "properties": [{"id": "custom.cellOptions", "value": {"type": "color-background"}}],
        }]},
        "options": {
            "cellHeight": "sm",
            "footer": {"countRows": True, "fields": "", "reducer": ["count"], "show": True},
            "showHeader": True,
            "sortBy": [
                {"desc": False, "displayName": "C-Die Instance"},
                {"desc": False, "displayName": "Monitor"},
                {"desc": False, "displayName": "Slot"},
            ],
        },
        "targets": [target(expr, "", instant=True, fmt="table")],
        "transformations": [
            {"id": "labelsToFields", "options": {"mode": "columns"}},
            {"id": "organize", "options": {
                "excludeByName": {
                    "AccessType": True, "DeviceType": True, "PMTEndpoint": True, "PMTGuid": True,
                    "PMTSizeBytes": True, "RedfishEndpoint": True, "SourceId": True, "SourceType": True,
                    "Time": True, "__name__": True, "device": True, "hostname": True,
                    "otel_scope_name": True, "otel_scope_schema_url": True, "otel_scope_version": True,
                    "telem": True,
                },
                "indexByName": {
                    "DeviceId": 0, "AccessId": 1, "monitor": 2, "slot": 3,
                    "Value": 4, "CollectionMode": 5,
                },
                "renameByName": {
                    "DeviceId": "C-Die Instance", "AccessId": "Access", "monitor": "Monitor",
                    "slot": "Slot", "Value": "Code", "CollectionMode": "Source",
                },
            }},
        ],
    })
    panels.append(panel)


def add_text(title: str, content: str, x: int, w: int, h: int = 5) -> None:
    panel = base_panel(title, "", x, w, h, "text")
    panel.update({"options": {"content": content, "mode": "markdown"}})
    panels.append(panel)


def advance(height: int) -> None:
    global y
    y += height


sel = 'PMTEndpoint="$endpoint",CollectionMode=~"$mode",DeviceId=~"$device",AccessId=~"$access",PMTGuid=~"$die"'
temp = f'{{__name__=~".*_temp_c[0-9]+_temp_celsius",{sel}}}'
valid_temp = f'({temp} > 0)'
usage = f'{{__name__=~"c[0-9]+_usage_meter_core_usage_total",{sel}}}'
throttle64 = f'{{__name__=~"c[0-9]+_pvp_throttle_64_.*",{sel}}}'
throttle1024 = f'{{__name__=~"c[0-9]+_pvp_throttle_1024_.*",{sel}}}'
freshness_age = f'time() - min(timestamp(label_replace({{{sel}}},"metric","$1","__name__","(.+)")))'
fivr_scope = 'PMTEndpoint="$endpoint",CollectionMode=~"$mode",DeviceId=~"$device",AccessId=~"$access"'
c_fivr_raw = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]",PMTGuid="0x22806802",{fivr_scope}}}'
c_fivr_available = f'{{__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22806802",{fivr_scope}}}'
c_fivr_status = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]_status_[0-9]{{2}}",PMTGuid="0x22806802",{fivr_scope}}}'
io_fivr_available = f'{{__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22491753",{fivr_scope}}}'
c_fivr_healthy = (
    f'(count({c_fivr_raw}) > bool 0) * '
    f'(count({c_fivr_raw} == 0) == bool count({c_fivr_raw})) * '
    f'(min({c_fivr_available}) == bool 1)'
    f' or vector(-1)'
)
c_fivr_nonzero_count = f'count({c_fivr_status} != 0) or vector(0)'
c_fivr_nonzero_detail = (
    f'label_replace(label_replace(({c_fivr_status} != 0),'
    f'"slot","$1","__name__",".*_status_([0-9]{{2}})"),'
    f'"monitor","$1","__name__",".*_fivr_health_monitor_([0-2])_status_.*")'
)
io_deadbeef_percent = f'(100 * count({io_fivr_available} == 0) / count({io_fivr_available})) or vector(-1)'
demo_ready = f'(min(up{{job=~"otel-pmt.*"}}) == bool 1) * ({freshness_age} < bool 45)'
healthy_mapping = [{"type": "value", "options": {
    "-1": {"color": "gray", "index": 0, "text": "No Data"},
    "0": {"color": "red", "index": 1, "text": "Unhealthy"},
    "1": {"color": "green", "index": 2, "text": "Healthy"},
}}]
demo_ready_mapping = [{"type": "value", "options": {
    "0": {"color": "red", "index": 0, "text": "Attention"},
    "1": {"color": "green", "index": 1, "text": "Ready"},
}}]
deadbeef_mapping = [{"type": "value", "options": {
    "-1": {"color": "gray", "index": 0, "text": "No Data"},
    "0": {"color": "green", "index": 1, "text": "Available"},
    "100": {"color": "orange", "index": 2, "text": "DEADBEEF"},
}}]
qat_throughput_mapping = [{"type": "value", "options": {
    "0": {"color": "gray", "index": 0, "text": "Idle · No QAT Workload"},
}}]
qat_latency_mapping = [{"type": "value", "options": {
    "-2": {"color": "gray", "index": 0, "text": "No Data"},
    "-1": {"color": "gray", "index": 1, "text": "Idle · No QAT Traffic"},
}}]

row("01 · Customer Demo Overview / 客户演示总览", "只回答三个问题：PMT数据是否可用、CPU当前最高温度、C-Die FIVR monitor是否出现非零状态。技术质量细节下沉到第07栏。")
add_stat("PMT Demo Status", "Collector全部在线且当前筛选范围内最旧活跃样本不超过45秒时显示Ready；这是演示数据就绪状态，不是整机健康认证。", 0, 8,
         demo_ready, unit="none",
         thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}],
         color_mode="background", mappings=demo_ready_mapping, height=5, no_value="No PMT Data")
add_stat("Highest Core Temperature", "当前所有有效Core中最高的温度；disabled Core的0°C占位值已排除。", 8, 8,
         f'max({valid_temp})', unit="celsius",
         thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 95}],
         color_mode="background", height=5, no_value="No Temperature Data")
add_stat("C-Die FIVR Monitor", "全部公开2-bit slots为0且数据可用时显示Healthy；这是PMT项目运营约定，详细定位见第02栏。", 16, 8,
         c_fivr_healthy, unit="none",
         thresholds=[{"color": "gray", "value": None}, {"color": "red", "value": 0}, {"color": "green", "value": 1}],
         color_mode="background", mappings=healthy_mapping, height=5, no_value="No FIVR Data")
advance(5)

add_text(
    "How to Read This Demo / 如何阅读",
    "这三个卡片分别表示 **PMT采集是否就绪**、**当前最高Core温度** 和 **C-Die FIVR monitor结果**。"
    "绿色不等于完整服务器健康认证；data loss、来源清单和内部时间戳属于技术诊断信息，统一放在第07栏。",
    0, 24, 3,
)
advance(3)

add_timeseries("CPU Core Temperature Trend", "有效Core的最高与平均温度趋势；客户演示优先关注是否接近80°C/95°C阈值。", 0, 24, 7, [
    target(f'max by(CollectionMode) ({valid_temp})', "{{CollectionMode}} · Max", "A"),
    target(f'avg by(CollectionMode) ({valid_temp})', "{{CollectionMode}} · Average", "B"),
], unit="celsius", minimum=0, maximum=110)
advance(7)

row("02 · FIVR Health & Diagnostics / FIVR 健康与定位", "C-Die 非零码按项目运营约定显示 Unhealthy，并定位到实例、monitor 与 slot；该约定不是 XML 官方状态枚举。")
add_stat("C-Die Overall Status", "数据可用且 576 个公开 2-bit slots 全为 0 时显示 Healthy；任一非零码按项目运营约定显示 Unhealthy。", 0, 8,
         c_fivr_healthy, unit="none",
         thresholds=[{"color": "gray", "value": None}, {"color": "red", "value": 0}, {"color": "green", "value": 1}],
         color_mode="background", mappings=healthy_mapping)
add_stat("C-Die Non-Zero Slots", "当前筛选范围中值为 1、2 或 3 的 C-Die 2-bit slot 数量。", 8, 8,
         c_fivr_nonzero_count, unit="short",
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}],
         color_mode="background")
add_stat("IO-Die FIVR Data", "IO-Die 当前返回 0xDEADBEEFDEADBEEF；这是数据不可用 sentinel，不代表硬件故障。", 16, 8,
         io_deadbeef_percent, unit="none",
         thresholds=[{"color": "gray", "value": None}, {"color": "green", "value": 0}, {"color": "orange", "value": 100}],
         color_mode="background", mappings=deadbeef_mapping)
advance(4)
add_fivr_detail_table(
    "C-Die Non-Zero Slot Locator",
    "仅列出非零状态码；空表表示未检测到非零 slot。位置可定位到 C-Die 实例、monitor 和 slot，但 XML 未提供对应 rail/core 或 code 1/2/3 的官方含义。",
    0, 24, 9, c_fivr_nonzero_detail,
)
advance(9)

row("03 · Thermal / 温度状态", "0°C 样本全部来自 disabled core，已从所有温度统计和曲线中排除。")
core_labeled_temp = f'label_replace({valid_temp},"core","$1","__name__",".*_temp_c([0-9]+)_temp_celsius")'
add_bar_gauge("Hottest Cores Now", "当前温度最高的 16 条有效 core series。", 0, 9, 10,
              f'topk(16,{core_labeled_temp})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "celsius", 0, 110,
              [{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 95}])
add_timeseries("Hottest Core History", "选定时间范围内当前最热的 12 条有效 core 曲线。", 9, 15, 10, [
    target(f'topk(12,{core_labeled_temp})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}")
], unit="celsius", minimum=0, maximum=110)
advance(10)
add_timeseries("Thermal Envelope by Source", "有效 core 的最高、平均、最低温度；不包含 disabled core 的 0°C 占位值。", 0, 12, 7, [
    target(f'max by(CollectionMode) ({valid_temp})', "{{CollectionMode}} · Max", "A"),
    target(f'avg by(CollectionMode) ({valid_temp})', "{{CollectionMode}} · Average", "B"),
    target(f'min by(CollectionMode) ({valid_temp})', "{{CollectionMode}} · Min", "C"),
], unit="celsius", minimum=0, maximum=110)
add_timeseries("Selected Core $core", "所选 core 的有效温度；disabled core 不显示 0°C。", 12, 12, 7, [
    target(f'({{__name__=~".*_temp_c${{core}}_temp_celsius",{sel}}} > 0)', "{{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="celsius", minimum=0, maximum=110)
advance(7)

row("04 · Core Activity / Core 活动", "PMT experimental usage meter 显示 XML 定义的累计 relative-usage level 变化率；它不是 Linux CPU utilization 百分比。")
core_usage = f'label_replace({usage},"core","$1","__name__","c([0-9]+)_usage_meter_core_usage_total")'
add_timeseries("PMT Core Relative Usage Rate", "experimental accumulated relative-usage level 的每秒变化率；用于比较 PMT local-core slots 的相对活动，不可解释为 Linux CPU%。", 0, 14, 9, [
    target(f'topk(16,clamp_min(rate({core_usage}[5m:]),0))', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}")
], unit="short", minimum=0, no_value="No PMT Data", decimals=6)
add_timeseries("Selected PMT Core $core Usage Rate", "所选编号是 PMT aggregator local core slot，不是 Linux CPU 编号；曲线是 experimental usage counter 的每秒变化率。", 14, 10, 9, [
    target(f'clamp_min(rate(c${{core}}_usage_meter_core_usage_total{{{sel}}}[5m]),0)', "D{{DeviceId}}/A{{AccessId}}")
], unit="short", minimum=0, no_value="No PMT Data", decimals=6)
advance(9)
core_throttle64 = f'label_replace({throttle64},"core","$1","__name__","c([0-9]+)_pvp_throttle_64_.*")'
core_throttle1024 = f'label_replace({throttle1024},"core","$1","__name__","c([0-9]+)_pvp_throttle_1024_.*")'
add_bar_gauge("Throttle · 64-Cycle Window", "最近 64 cycles 窗口内 throttle 值最高的 16 条。", 0, 12, 8,
              f'topk(16,{core_throttle64})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "short", 0)
add_bar_gauge("Throttle · 1024-Cycle Window", "最近 1024 cycles 窗口内 throttle 值最高的 16 条。", 12, 12, 8,
              f'topk(16,{core_throttle1024})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "short", 0)
advance(8)

row("05 · Core $core Operating Residency / 运行驻留分布", "使用页面顶部“05 Residency window”选择统计窗口；显示该窗口内的频率、温度和电压驻留占比，不代表瞬时值。低于0.1%的区间隐藏。")
histogram_ranges = {
    "freq": ["C6 sleep", "≤800 MHz", "900–1200 MHz", "1300–1600 MHz", "1700–2000 MHz", "2100–2400 MHz", "2500–2800 MHz", "2900–3200 MHz", "3300–3600 MHz", "3700–4000 MHz", "4100–4400 MHz", ">4400 MHz"],
    "temp": ["<20 °C", "20.5–27.5 °C", "28–35 °C", "35.5–42.5 °C", "43–50 °C", "50.5–57.5 °C", "58–65 °C", "65.5–72.5 °C", "73–80 °C", "80.5–87.5 °C", "88–95 °C", ">95 °C"],
    "volt": ["<602 mV", "602.5–657 mV", "657.5–712 mV", "712.5–767 mV", "767.5–822 mV", "822.5–877 mV", "877.5–932 mV", "932.5–987 mV", "987.5–1042 mV", "1042.5–1097 mV", "1097.5–1152 mV", ">1152 mV"],
}
for kind, title_text, height in [
    ("freq", "Frequency Residency", 7),
    ("temp", "Temperature Residency", 5),
    ("volt", "Voltage Residency", 8),
]:
    total_rate = " + ".join(
        f'sum(rate(c${{core}}_{kind}_hist_r{bucket}_second_total{{{sel}}}[${{residency_window}}]))'
        for bucket in range(12)
    )
    range_expr = " or ".join(
        f'label_replace((100 * sum(rate(c${{core}}_{kind}_hist_r{bucket}_second_total{{{sel}}}[${{residency_window}}])) '
        f'/ clamp_min({total_rate}, 1e-12)) > 0.1,'
        f'"range","{histogram_ranges[kind][bucket]}","__name__",".*")'
        for bucket in range(12)
    )
    add_residency_bar(title_text, "所选 $residency_window 窗口的加权驻留占比；低于0.1%的区间隐藏。",
                      0, 24, height, range_expr)
    advance(height)

row("06 · Memory & Accelerator / 内存与加速器", "只展示具有明确语义且对平台状态有直接价值的指标。")
mbm_total = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_mbm_total",{sel}}}'
qat_throughput = (
    f'sum(rate(label_replace({{__name__=~"qat[01]_tl_bw_(in|out)_megabytes_total",{sel}}},'
    f'"metric","$1","__name__","(.+)")[5m:]))'
)
qat_average_latency = f'max({{__name__=~"qat[01]_avg_.*_nanoseconds",{sel}}})'
qat_latency_state = (
    f'({qat_average_latency} and on() ({qat_throughput} > 0))'
    f' or (vector(-1) and on() ({qat_throughput} == 0))'
    f' or (vector(-2) unless on() {qat_throughput})'
)
add_timeseries("RDT Memory Transaction Rate", "MBM total counter 的 5 分钟平均每秒变化率。", 0, 12, 9, [
    target(f'topk(16,clamp_min(rate(label_replace({mbm_total},"channel","$1","__name__","(cha[0-9]+_rmid[0-9]+)_rdt_mbm_total")[5m:]),0))', "{{channel}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ops", minimum=0)
add_stat("QAT PCIe Throughput", "QAT0/QAT1 inbound 与 outbound throughput 总和；0 MB/s 明确显示为 Idle，表示当前 workload 未向 QAT 提交任务。", 12, 6,
         qat_throughput, unit="MBs",
         thresholds=[{"color": "gray", "value": None}, {"color": "blue", "value": 0.000001}],
         color_mode="value", mappings=qat_throughput_mapping, height=9, no_value="No Data")
add_stat("QAT Average Latency", "有 QAT traffic 时显示所有 average-latency gauge 的最大值；无 traffic 时显示 Idle，而不是误导性的 0 ns。", 18, 6,
         qat_latency_state, unit="ns",
         thresholds=[{"color": "gray", "value": None}, {"color": "blue", "value": 0}],
         color_mode="value", mappings=qat_latency_mapping, height=9, no_value="No Data")
advance(9)

row("07 · Technical Diagnostics / 技术诊断", "客户演示通常无需展开。Data loss绝对值是历史累计；只有多个PMT更新窗口持续增长，或workload停止后仍增长，才需要升级调查。")
add_table("PMT Source Inventory", "每个 Device/Access/Source 当前拥有的 series 数。", 0, 12, 9, [
    target(f'count by (DeviceId,AccessId,SourceId,DeviceType,AccessType) ({{{sel}}})', "", instant=True, fmt="table")
])
add_table("Aggregator Update Exceptions", "技术质量明细：历史累计count、最近15分钟新增量和最近事件的25MHz内部timestamp。短暂非零不等于CPU故障。", 12, 12, 9, [
    target(f'agg_data_loss_count_total{{{sel}}}', "Historical count", "A", True, "table"),
    target(f'agg_data_loss_timestamp_total{{{sel}}}', "Last event · 25MHz ticks", "B", True, "table"),
    target(f'clamp_min(increase(agg_data_loss_count_total{{{sel}}}[15m]),0)', "Increase · last 15m", "C", True, "table"),
])
advance(9)

row("08 · Advanced Metric Explorer / 高级指标搜索", "Grafana原生变量只能位于页面顶部，无法嵌入某个row；因此高级搜索已拆分为独立页面，让搜索框和结果紧邻显示。")
add_text(
    "Open Advanced Metric Explorer / 打开高级指标搜索",
    "主Dashboard不再显示面向技术人员的全局Metric搜索框。"
    "请打开 **[Intel PMT · Advanced Metric Explorer](/d/pmt-avc01-metric-explorer"
    "?var-endpoint=$endpoint&var-mode=$mode&var-device=$device&var-access=$access&var-die=$die)**；"
    "新页面顶部选择Metric，结果立即显示在下方。",
    0, 24, 5,
)
advance(5)

variables = [
    {"name": "endpoint", "label": "Endpoint", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=~\".+\"},PMTEndpoint)", "refId": "PrometheusVariableQueryEditor-Endpoint"},
    "definition": "label_values({PMTEndpoint=~\".+\"},PMTEndpoint)", "refresh": 1, "sort": 1,
     "current": {"selected": True, "text": "avc01", "value": "avc01"}},
    {"name": "mode", "label": "Collection mode", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\"},CollectionMode)", "refId": "PrometheusVariableQueryEditor-Mode"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\"},CollectionMode)", "refresh": 1, "sort": 1,
    "includeAll": True, "allValue": ".*", "multi": True,
    "current": {"selected": True, "text": ["redfish"], "value": ["redfish"]}},
    {"name": "device", "label": "Device", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\"},DeviceId)", "refId": "PrometheusVariableQueryEditor-Device"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\"},DeviceId)", "refresh": 1, "sort": 3,
     "includeAll": True, "allValue": ".*", "multi": True,
     "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    {"name": "access", "label": "Access", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\"},AccessId)", "refId": "PrometheusVariableQueryEditor-Access"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\"},AccessId)", "refresh": 1, "sort": 3,
     "includeAll": True, "allValue": ".*", "multi": True,
     "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    {"name": "die", "label": "PMT GUID / Die", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\",AccessId=~\"$access\"},PMTGuid)", "refId": "PrometheusVariableQueryEditor-Die"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\",AccessId=~\"$access\"},PMTGuid)", "refresh": 1, "sort": 1,
     "includeAll": True, "allValue": ".*", "multi": True,
     "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
    {"name": "core", "label": "Core", "type": "custom",
     "query": ",".join(str(index) for index in range(128)), "options": [],
     "current": {"selected": True, "text": "0", "value": "0"}},
    {"name": "residency_window", "label": "05 Residency window", "type": "custom",
     "query": "2m,5m,10m,15m,30m,1h", "options": [],
     "current": {"selected": True, "text": "5m", "value": "5m"}},
]

metric_variable = {
    "name": "metric", "label": "Search metric", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\",AccessId=~\"$access\",PMTGuid=~\"$die\"},__name__)", "refId": "PrometheusVariableQueryEditor-Metric"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\",DeviceId=~\"$device\",AccessId=~\"$access\",PMTGuid=~\"$die\"},__name__)", "refresh": 1, "sort": 1,
    "current": {"selected": True, "text": "c0_c1_c2_c3_temp_c0_temp_celsius", "value": "c0_c1_c2_c3_temp_c0_temp_celsius"},
}

dashboard = {
    "annotations": {"list": [{
        "builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True,
        "hide": True, "iconColor": "rgba(255, 96, 96, 1)", "name": "Annotations & Alerts", "type": "dashboard",
    }]},
    "description": "Customer-facing Intel PMT demo: collection readiness, CPU temperature, FIVR status, operating residency, and clearly separated technical diagnostics.",
    "editable": True, "fiscalYearStartMonth": 0, "graphTooltip": 1,
    "links": [
        {"asDropdown": False, "icon": "search", "includeVars": True, "keepTime": True,
         "tags": [], "targetBlank": False, "title": "Advanced Metric Explorer",
         "tooltip": "Open metric search with results directly below the controls", "type": "link",
         "url": "/d/pmt-avc01-metric-explorer"},
        {"asDropdown": False, "icon": "doc", "includeVars": False, "keepTime": False,
         "tags": [], "targetBlank": True, "title": "Metric catalog (repository)",
         "tooltip": "See docs/pmt-metrics-catalog.csv for HELP and TYPE", "type": "link",
         "url": "https://github.com/Jacky-code535/PMT/blob/pmt-redfish-dashboard/docs/pmt-metrics-catalog.csv"},
    ],
    "liveNow": True, "panels": panels, "refresh": "20s", "schemaVersion": 41,
    "tags": ["Intel PMT", "Redfish", "in-band", "GNR", "FIVR", "hardware telemetry", "comprehensive"],
    "templating": {"list": variables}, "time": {"from": "now-30m", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "20s", "30s", "1m", "5m"],
                   "time_options": ["5m", "15m", "30m", "1h", "6h", "12h", "24h", "7d"]},
    "timezone": "browser", "title": "Intel PMT · Customer Telemetry Demo", "uid": "pmt-avc01-redfish", "version": 29,
}

serialized = json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"
REPO_OUTPUT.write_text(serialized, encoding="utf-8")
SYSTEM_OUTPUT.write_text(serialized, encoding="utf-8")
main_panel_count = len(panels)
main_row_count = sum(panel["type"] == "row" for panel in panels)

# Grafana dashboard variables are always rendered at page level and cannot be
# placed inside row 08. Keep the customer dashboard uncluttered and generate a
# dedicated explorer where the metric search control sits directly above the
# result panels.
panels = []
panel_id = 0
y = 0
row("Metric Search Results / 指标搜索结果", "先在页面顶部的Search metric中选择名称；下方立即显示历史、当前series与变化率。")
add_text(
    "How to Use / 使用方法",
    "1. 在顶部 **Search metric** 输入关键词并选择准确名称；"
    "2. Raw History适合gauge/current value；"
    "3. 5-Minute Change同时提供counter rate和gauge delta，必须结合Metric catalog中的type与HELP解释。",
    0, 24, 3,
)
advance(3)
explorer_selector = f'{{__name__="$metric",{sel}}}'
add_timeseries("$metric · Raw History", "所选metric的原始历史值；counter绝对值通常不表示当前强度。", 0, 16, 10, [
    target(explorer_selector, "{{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}/S{{SourceId}}")
], unit="short", legend_place="right")
add_table("$metric · Current Series", "当前值及其完整来源标签。", 16, 8, 10, [
    target(explorer_selector, "", instant=True, fmt="table")
])
advance(10)
add_timeseries("$metric · 5-Minute Change", "Counter查看rate/s；gauge查看窗口首尾平均变化率。只解释与该metric type匹配的曲线。", 0, 24, 8, [
    target(f'rate({explorer_selector}[5m])', "counter rate/s · D{{DeviceId}}/A{{AccessId}}", "A"),
    target(f'delta({explorer_selector}[5m])/300', "gauge delta/s · D{{DeviceId}}/A{{AccessId}}", "B"),
], unit="short")
advance(8)

explorer_variables = [
    variable for variable in variables
    if variable["name"] not in {"core", "residency_window"}
] + [metric_variable]
explorer_dashboard = {
    "annotations": {"list": [{
        "builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True,
        "hide": True, "iconColor": "rgba(255, 96, 96, 1)", "name": "Annotations & Alerts", "type": "dashboard",
    }]},
    "description": "Technical Intel PMT metric search with controls and results kept together.",
    "editable": True, "fiscalYearStartMonth": 0, "graphTooltip": 1,
    "links": [
        {"asDropdown": False, "icon": "arrow-left", "includeVars": True, "keepTime": True,
         "tags": [], "targetBlank": False, "title": "Back to Customer Demo",
         "tooltip": "Return to the customer-facing PMT dashboard", "type": "link",
         "url": "/d/pmt-avc01-redfish"},
        {"asDropdown": False, "icon": "doc", "includeVars": False, "keepTime": False,
         "tags": [], "targetBlank": True, "title": "Metric family reference",
         "tooltip": "Read the value semantics, query guidance, and caveats", "type": "link",
         "url": "https://github.com/Jacky-code535/PMT/blob/pmt-redfish-dashboard/docs/pmt-metric-family-reference.md"},
    ],
    "liveNow": True, "panels": panels, "refresh": "20s", "schemaVersion": 41,
    "tags": ["Intel PMT", "metric explorer", "technical diagnostics"],
    "templating": {"list": explorer_variables}, "time": {"from": "now-30m", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "20s", "30s", "1m", "5m"],
                   "time_options": ["5m", "15m", "30m", "1h", "6h", "12h", "24h", "7d"]},
    "timezone": "browser", "title": "Intel PMT · Advanced Metric Explorer",
    "uid": "pmt-avc01-metric-explorer", "version": 1,
}
explorer_serialized = json.dumps(explorer_dashboard, indent=2, ensure_ascii=False) + "\n"
REPO_EXPLORER_OUTPUT.write_text(explorer_serialized, encoding="utf-8")
SYSTEM_EXPLORER_OUTPUT.write_text(explorer_serialized, encoding="utf-8")

print(f"Generated main dashboard: {main_panel_count} panels ({main_row_count} rows)")
print(REPO_OUTPUT)
print(SYSTEM_OUTPUT)
print(f"Generated metric explorer: {len(panels)} panels")
print(REPO_EXPLORER_OUTPUT)
print(SYSTEM_EXPLORER_OUTPUT)
