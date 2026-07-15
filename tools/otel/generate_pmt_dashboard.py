#!/usr/bin/env python3
"""Generate the provisioned Grafana dashboard for BMC and in-band Intel PMT metrics."""

from __future__ import annotations

import json
from pathlib import Path

DATASOURCE = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}
REPO_OUTPUT = Path(__file__).parent / "dashboards" / "pmt-redfish-comprehensive.json"
SYSTEM_OUTPUT = Path("/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json")

panels: list[dict] = []
panel_id = 0
y = 0


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
             thresholds: list[dict] | None = None, color_mode: str = "value", legend: str = "") -> None:
    panel = base_panel(title, description, x, w, 4, "stat")
    panel.update({
        "fieldConfig": {"defaults": {
            "color": {"mode": "thresholds"}, "unit": unit,
            "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "green", "value": None}]},
        }, "overrides": []},
        "options": {
            "colorMode": color_mode, "graphMode": "area", "justifyMode": "center", "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "textMode": "auto",
        },
        "targets": [target(expr, legend)],
    })
    panels.append(panel)


def add_timeseries(title: str, description: str, x: int, w: int, h: int, targets: list[dict],
                   unit: str = "short", minimum: float | None = None, maximum: float | None = None,
                   stacking: str = "none", legend_place: str = "bottom") -> None:
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
                    "sizing": "auto", "valueMode": "color"},
        "targets": [target(expr, legend, instant=True)],
    })
    panels.append(panel)


def add_table(title: str, description: str, x: int, w: int, h: int, queries: list[dict]) -> None:
    panel = base_panel(title, description, x, w, h, "table")
    panel.update({
        "fieldConfig": {"defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"},
                                                   "inspect": False}, "mappings": [], "thresholds": {
                                                       "mode": "absolute", "steps": [{"color": "green", "value": None},
                                                                                     {"color": "red", "value": 1}]}},
                        "overrides": []},
        "options": {"cellHeight": "sm", "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False},
                    "showHeader": True, "sortBy": [{"desc": True, "displayName": "Value"}]},
        "targets": queries,
        "transformations": [{"id": "labelsToFields", "options": {"mode": "columns"}}],
    })
    panels.append(panel)


def advance(height: int) -> None:
    global y
    y += height


sel = 'PMTEndpoint="$endpoint",CollectionMode=~"$mode",DeviceId=~"$device",AccessId=~"$access",PMTGuid=~"$die"'
temp = f'{{__name__=~".*_temp_c[0-9]+_temp_celsius",{sel}}}'
usage = f'{{__name__=~"c[0-9]+_usage_meter_core_usage_total",{sel}}}'
throttle64 = f'{{__name__=~"c[0-9]+_pvp_throttle_64_.*",{sel}}}'
throttle1024 = f'{{__name__=~"c[0-9]+_pvp_throttle_1024_.*",{sel}}}'

row("01 · Fleet health / 采集总览", "先判断链路是否健康，再解释硬件指标。所有卡片都受顶部 Endpoint/Device/Access 筛选器控制。")
add_stat("Collector", "Prometheus 是否能抓取 PMT Collector。1=UP，0=DOWN。", 0, 4,
         'min(up{job=~"otel-pmt.*"})', thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}], color_mode="background")
add_stat("PMT series", "当前筛选范围内的 time series 数。", 4, 4, f'count({{{sel}}})', unit="locale")
add_stat("Metric names", "当前筛选范围内不同 metric 名称数。", 8, 4, f'count(count by (__name__) ({{{sel}}}))', unit="locale")
add_stat("Scrape age", "最新 PMT Prometheus 样本年龄；超过 45 秒说明 scrape 可能停止。", 12, 4,
         f'time() - max(timestamp(label_replace({temp},"metric","$1","__name__","(.+)")))', unit="s",
         thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 25}, {"color": "red", "value": 45}], color_mode="background")
add_stat("Max core temp", "筛选范围内所有 core 的当前最高温度。", 16, 4, f'max({temp})', unit="celsius",
         thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 95}], color_mode="background")
add_stat("Data loss Δ (5m)", "最近五分钟 aggregator data-loss gauge 的正向增量。", 20, 4,
         f'sum(clamp_min(increase(agg_data_loss_count_total{{{sel}}}[5m]),0))', unit="locale",
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 0.000001}], color_mode="background")
advance(4)

add_timeseries("PMT series stability", "Series 数骤降常表示 XML、筛选范围或数据源发生变化。", 0, 8, 7, [
    target(f'count({{{sel}}})', "PMT series", "A"),
], unit="short")
add_timeseries("Prometheus scrape duration", "Exporter scrape 耗时持续升高表示 Collector/Prometheus 压力或 series 增长。", 8, 8, 7, [
    target('scrape_duration_seconds{job=~"otel-pmt.*"}', "{{job}} · {{instance}}", "A"),
], unit="s", minimum=0)
add_timeseries("Data-loss trend by source", "累计值非零不一定是当前故障；重点观察曲线是否继续增加。", 16, 8, 7, [
    target(f'agg_data_loss_count_total{{{sel}}}', "{{CollectionMode}} · dev{{DeviceId}} / access{{AccessId}}", "A")
], unit="locale", minimum=0)
advance(7)

row("02 · Thermal / 全 Core 热状态", "显示所有 core，而不是只固定 core 0。使用 Device/Access 变量缩小范围。")
core_labeled_temp = f'label_replace({temp},"core","$1","__name__",".*_temp_c([0-9]+)_temp_celsius")'
add_bar_gauge("Hottest cores now", "当前最热的 32 条 core series；温度阈值 80°C/95°C。", 0, 9, 10,
              f'topk(32,{core_labeled_temp})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "celsius", 0, 110,
              [{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 95}])
add_timeseries("Top 20 core temperature history", "选定时间范围内当前最热 20 条 core 曲线。", 9, 15, 10, [
    target(f'topk(20,{core_labeled_temp})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}")
], unit="celsius", minimum=0, maximum=110)
advance(10)
add_timeseries("Thermal envelope", "最高、平均、最低温度形成平台热包络，便于识别整体升温与局部热点。", 0, 12, 7, [
    target(f'max({temp})', "Maximum", "A"), target(f'avg({temp})', "Average", "B"), target(f'min({temp})', "Minimum", "C")
], unit="celsius", minimum=0, maximum=110)
add_timeseries("Selected Core $core temperature", "由顶部 Core 变量选择逻辑 core；可能因多个 Device/Access 产生多条曲线。", 12, 12, 7, [
    target(f'{{__name__=~".*_temp_c${{core}}_temp_celsius",{sel}}}', "{{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="celsius", minimum=0, maximum=110)
advance(7)

row("03 · Core activity & throttling / 活动与节流", "Usage 是累计相对使用量的变化率，不是直接百分比；Throttle 是最近窗口内的节流计数。")
core_usage = f'label_replace({usage},"core","$1","__name__","c([0-9]+)_usage_meter_core_usage_total")'
add_timeseries("Top core usage change rates", "累计 usage gauge 的 5 分钟正向变化率，显示最高 20 条。", 0, 12, 9, [
    target(f'topk(20,clamp_min(delta({core_usage}[5m:])/300,0))', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ops", minimum=0)
add_timeseries("Selected Core $core usage rate", "选定 core 的 usage 5 分钟变化率。", 12, 12, 9, [
    target(f'clamp_min(delta(c${{core}}_usage_meter_core_usage_total{{{sel}}}[5m])/300,0)', "D{{DeviceId}}/A{{AccessId}}")
], unit="ops", minimum=0)
advance(9)
core_throttle64 = f'label_replace({throttle64},"core","$1","__name__","c([0-9]+)_pvp_throttle_64_.*")'
core_throttle1024 = f'label_replace({throttle1024},"core","$1","__name__","c([0-9]+)_pvp_throttle_1024_.*")'
add_bar_gauge("Throttle · 64-cycle window", "最近 64 cycles 窗口内 throttle 计数最高的 24 条。", 0, 12, 9,
              f'topk(24,{core_throttle64})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "locale", 0)
add_bar_gauge("Throttle · 1024-cycle window", "最近 1024 cycles 窗口内 throttle 计数最高的 24 条。", 12, 12, 9,
              f'topk(24,{core_throttle1024})', "Core {{core}} · D{{DeviceId}}/A{{AccessId}}", "locale", 0)
advance(9)

row("04 · Selected Core histograms / 频率·温度·电压驻留", "使用顶部 Core 变量查看任意 core。图中为各硬件 bucket 累计 counter 的 5 分钟变化率；采用堆叠面积显示分布。")
for x, kind, title_text in [(0, "freq", "Frequency residency"), (8, "temp", "Temperature residency"), (16, "volt", "Voltage residency")]:
    add_timeseries(f"{title_text} · Core $core", "Bucket 的准确物理范围见 metric catalog 中对应 HELP。", x, 8, 9,
                   [
                       target(
                           f'sum(rate(c${{core}}_{kind}_hist_r{bucket}_second_total{{{sel}}}[5m]))',
                           f"r{bucket}", chr(ord("A") + bucket),
                       )
                       for bucket in range(12)
                   ], unit="ops", minimum=0, stacking="normal", legend_place="right")
advance(9)

row("05 · Memory, CHA & accelerator / 内存·缓存代理·QAT", "RDT MBM/CMT、CHA enable mask 与 QAT telemetry。大量同类 metrics 采用 Top-K，避免一次绘制数千条曲线。")
mbm_total = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_mbm_total",{sel}}}'
mbm_local = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_mbm_local_total",{sel}}}'
cmt = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_cmt_total",{sel}}}'
add_timeseries("Top RDT MBM total activity", "CHA/RMID total memory transaction gauge 的 5 分钟正向变化率。", 0, 12, 9, [
    target(f'topk(20,clamp_min(rate(label_replace({mbm_total},"channel","$1","__name__","(cha[0-9]+_rmid[0-9]+)_rdt_mbm_total")[5m:]),0))', "{{channel}} · {{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ops", minimum=0)
add_timeseries("Top RDT MBM local activity", "CHA/RMID local memory transaction gauge 的 5 分钟正向变化率。", 12, 12, 9, [
    target(f'topk(20,clamp_min(rate(label_replace({mbm_local},"channel","$1","__name__","(cha[0-9]+_rmid[0-9]+)_rdt_mbm_local_total")[5m:]),0))', "{{channel}} · {{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ops", minimum=0)
advance(9)
add_bar_gauge("Top RDT CMT occupancy", "当前 CHA/RMID cache monitoring technology 值最高的 24 条。", 0, 8, 10,
              f'topk(24,label_replace({cmt},"channel","$1","__name__","(cha[0-9]+_rmid[0-9]+)_rdt_cmt_total"))', "{{channel}} · {{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}", "locale", 0)
add_bar_gauge("CHA enabled state", "当前 CHA enable mask。1 表示 enabled，0 表示 disabled。", 8, 8, 10,
              f'max by(cha,DeviceId)(label_replace({{__name__=~"cha_enabled_mask_cha_[0-9]+_en",{sel}}},"cha","$1","__name__","cha_enabled_mask_cha_([0-9]+)_en"))', "CHA {{cha}} · D{{DeviceId}}", "short", 0, 1,
              [{"color": "red", "value": None}, {"color": "green", "value": 1}])
add_timeseries("QAT bandwidth", "QAT0/QAT1 telemetry 的 in/out megabytes 当前值。", 16, 8, 10, [
    target(f'{{__name__=~"qat[01]_tl_bw_(in|out)_megabytes_total",{sel}}}', "{{__name__}} · {{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="MBs", minimum=0, legend_place="right")
advance(10)
add_timeseries("QAT average latency", "QAT 平均 page request、translation、read 和 GP latency。", 0, 12, 8, [
    target(f'{{__name__=~"qat[01]_avg_.*_nanoseconds",{sel}}}', "{{__name__}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ns", minimum=0, legend_place="right")
add_timeseries("QAT maximum latency", "QAT max read/general-purpose latency。", 12, 12, 8, [
    target(f'{{__name__=~"qat[01]_tl_max_(gp|rd)_lat_nanoseconds_total",{sel}}}', "{{__name__}} · {{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}")
], unit="ns", minimum=0, legend_place="right")
advance(8)

row("06 · Inventory & collection quality / 拓扑与采集质量", "展示当前设备/Access 来源、core enable 状态和 data-loss 明细。")
add_table("PMT source inventory", "每个 DeviceId/AccessId/SourceId 当前拥有的 series 数。", 0, 12, 10, [
    target(f'count by (DeviceId,AccessId,SourceId,DeviceType,AccessType) ({{{sel}}})', "", instant=True, fmt="table")
])
add_table("Data-loss detail", "当前 data-loss count 与 timestamp；timestamp 单位为 25MHz crystal-clock TSC ticks。", 12, 12, 10, [
    target(f'agg_data_loss_count_total{{{sel}}}', "", "A", True, "table"),
    target(f'agg_data_loss_timestamp_total{{{sel}}}', "", "B", True, "table"),
])
advance(10)
add_bar_gauge("Core enabled state", "所有 core enable flags。1=enabled，0=disabled。", 0, 12, 10,
              f'max by(core,DeviceId)(label_replace({{__name__=~"core_en_c[0-9]+_en",{sel}}},"core","$1","__name__","core_en_c([0-9]+)_en"))', "Core {{core}} · D{{DeviceId}}", "short", 0, 1,
              [{"color": "red", "value": None}, {"color": "green", "value": 1}])
add_timeseries("Data-loss positive delta by source", "最近五分钟新增 data loss；持续大于 0 时，期间同 aggregator 的其他 samples 可能不可靠。", 12, 12, 10, [
    target(f'clamp_min(increase(agg_data_loss_count_total{{{sel}}}[5m]),0)', "{{CollectionMode}} · D{{DeviceId}}/A{{AccessId}}/S{{SourceId}}")
], unit="locale", minimum=0)
advance(10)

row("07 · GNR FIVR Health / 两位状态解码", "使用精确 GUID+Size XML（CDIE 0x22806802/6784、IODIE 0x22491753/6272）。每个 64-bit monitor 拆为 32 个两位状态码；DEADBEEF 固件 poison 不作为健康值输出。")
fivr_available = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]_available",{sel}}}'
fivr_nonzero = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]_nonzero_status_count",{sel}}}'
fivr_status = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]_status_[0-9]+",{sel}}}'
fivr_raw = f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_[0-2]",{sel}}}'
add_stat("C-Die FIVR data", "0x22806802/6784：所有 monitor 均有效时为 1。", 0, 4,
         f'min({{__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22806802",PMTEndpoint="$endpoint",CollectionMode=~"$mode",DeviceId=~"$device",AccessId=~"$access"}})',
         thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}], color_mode="background")
add_stat("IO-Die FIVR data", "0x22491753/6272：0 表示 XML 匹配成功但 payload 为 DEADBEEF poison，不能解释为硬件故障。", 4, 4,
         f'min({{__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22491753",PMTEndpoint="$endpoint",CollectionMode=~"$mode",DeviceId=~"$device",AccessId=~"$access"}})',
         thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}], color_mode="background")
add_stat("Unavailable monitor words", "当前筛选范围内被固件 poison 标记为不可用的 FIVR monitor word 数。", 8, 4,
         f'count({fivr_available}) - sum({fivr_available})', unit="locale",
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}], color_mode="background")
add_stat("Non-zero status codes", "有效 monitor 中所有非零两位状态码总数；具体含义需结合平台 FIVR 状态编码规范。", 12, 4,
         f'sum({fivr_nonzero})', unit="locale",
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}], color_mode="background")
add_stat("Exact PUNIT instances", "精确 XML 成功解码并产生 FIVR availability 的 PUNIT instance 数。", 16, 4,
         f'count(count by (PMTGuid,DeviceId,AccessId) ({fivr_available}))', unit="locale")
add_stat("Exact schema mappings", "当前后端要求精确匹配两组 GNR PUNIT GUID+Size，不使用 GUID-only fallback。", 20, 4,
         f'count(count by (PMTGuid,PMTSizeBytes) ({fivr_available}))', unit="locale")
advance(4)

add_bar_gauge("FIVR monitor availability", "每个 die instance、monitor word 的数据有效性。1=有效；0=DEADBEEF poison。", 0, 8, 10,
              fivr_available, "{{PMTGuid}} · D{{DeviceId}}/A{{AccessId}} · {{__name__}}", "short", 0, 1,
              [{"color": "red", "value": None}, {"color": "green", "value": 1}])
add_bar_gauge("Non-zero codes per monitor", "每个有效 64-bit monitor word 内非零两位状态码数量（0..32）。", 8, 8, 10,
              fivr_nonzero, "{{PMTGuid}} · D{{DeviceId}}/A{{AccessId}} · {{__name__}}", "locale", 0, 32,
              [{"color": "green", "value": None}, {"color": "red", "value": 1}])
add_bar_gauge("Packed two-bit status codes", "各 packed index 的原始两位码（0..3）；只显示有效 monitor。", 16, 8, 10,
              f'topk(96,{fivr_status})', "{{PMTGuid}} · D{{DeviceId}}/A{{AccessId}} · {{__name__}}", "short", 0, 3,
              [{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 2}])
advance(10)
add_timeseries("FIVR non-zero status history", "每个 monitor word 的非零两位状态码数量历史。", 0, 12, 8, [
    target(fivr_nonzero, "{{PMTGuid}} · D{{DeviceId}}/A{{AccessId}} · {{__name__}}")
], unit="locale", minimum=0, maximum=32, legend_place="right")
add_timeseries("FIVR raw monitor words", "仅展示有效的 packed 64-bit 原始值；DEADBEEF 已在 receiver 中抑制。", 12, 12, 8, [
    target(fivr_raw, "{{PMTGuid}} · D{{DeviceId}}/A{{AccessId}} · {{__name__}}")
], unit="short", minimum=0, legend_place="right")
advance(8)

row("08 · Metric Explorer / 全量 metrics 探索", "顶部 Metric 下拉框支持搜索任意 metric 名称。专用面板覆盖关键语义；Explorer 覆盖全部长尾 metrics。")
add_timeseries("$metric · history", "选择任意 PMT metric 绘制历史。单位和语义请查 docs/pmt-metrics-catalog.csv 的 HELP；counter/gauge 不能一概而论。", 0, 16, 11, [
    target(f'$metric{{{sel}}}', "D{{DeviceId}}/A{{AccessId}}/S{{SourceId}}")
], unit="short", legend_place="right")
add_table("$metric · current series & labels", "显示选中 metric 当前每条 series 的完整来源标签和值。", 16, 8, 11, [
    target(f'$metric{{{sel}}}', "", instant=True, fmt="table")
])
advance(11)
add_timeseries("$metric · 5m change", "对选中 metric 同时给出 rate（适合 counter）和 delta/300（适合累计 gauge）；根据 catalog 中 TYPE/HELP 选择正确解释。", 0, 24, 8, [
    target(f'rate($metric{{{sel}}}[5m])', "rate · D{{DeviceId}}/A{{AccessId}}", "A"),
    target(f'delta($metric{{{sel}}}[5m])/300', "delta/300 · D{{DeviceId}}/A{{AccessId}}", "B"),
], unit="ops")
advance(8)

variables = [
    {"name": "endpoint", "label": "Endpoint", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=~\".+\"},PMTEndpoint)", "refId": "PrometheusVariableQueryEditor-Endpoint"},
    "definition": "label_values({PMTEndpoint=~\".+\"},PMTEndpoint)", "refresh": 1, "sort": 1,
     "current": {"selected": True, "text": "avc01", "value": "avc01"}},
    {"name": "mode", "label": "Collection mode", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\"},CollectionMode)", "refId": "PrometheusVariableQueryEditor-Mode"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\"},CollectionMode)", "refresh": 1, "sort": 1,
    "includeAll": True, "allValue": ".*", "multi": True,
    "current": {"selected": True, "text": ["All"], "value": ["$__all"]}},
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
    {"name": "metric", "label": "Metric (search all)", "type": "query", "datasource": DATASOURCE,
    "query": {"query": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\"},__name__)", "refId": "PrometheusVariableQueryEditor-Metric"},
    "definition": "label_values({PMTEndpoint=\"$endpoint\",CollectionMode=~\"$mode\"},__name__)", "refresh": 1, "sort": 1,
    "current": {"selected": True, "text": "c0_c1_c2_c3_temp_c0_temp_celsius", "value": "c0_c1_c2_c3_temp_c0_temp_celsius"}},
]

dashboard = {
    "annotations": {"list": [{
        "builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True,
        "hide": True, "iconColor": "rgba(255, 96, 96, 1)", "name": "Annotations & Alerts", "type": "dashboard",
    }]},
    "description": "Unified BMC Redfish and in-band Intel PMT observability with exact-schema GNR PUNIT/FIVR decoding and all-metric exploration.",
    "editable": True, "fiscalYearStartMonth": 0, "graphTooltip": 1,
    "links": [{"asDropdown": False, "icon": "doc", "includeVars": False, "keepTime": False,
               "tags": [], "targetBlank": True, "title": "Metric catalog (repository)",
               "tooltip": "See docs/pmt-metrics-catalog.csv for HELP and TYPE", "type": "link",
               "url": "https://github.com/Jacky-code535/PMT/blob/pmt-redfish-dashboard/docs/pmt-metrics-catalog.csv"}],
    "liveNow": True, "panels": panels, "refresh": "20s", "schemaVersion": 41,
    "tags": ["Intel PMT", "Redfish", "in-band", "GNR", "FIVR", "hardware telemetry", "comprehensive"],
    "templating": {"list": variables}, "time": {"from": "now-30m", "to": "now"},
    "timepicker": {"refresh_intervals": ["5s", "10s", "20s", "30s", "1m", "5m"],
                   "time_options": ["5m", "15m", "30m", "1h", "6h", "12h", "24h", "7d"]},
    "timezone": "browser", "title": "Intel PMT · BMC + In-band Telemetry", "uid": "pmt-avc01-redfish", "version": 15,
}

serialized = json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"
REPO_OUTPUT.write_text(serialized, encoding="utf-8")
SYSTEM_OUTPUT.write_text(serialized, encoding="utf-8")
print(f"Generated {len(panels)} panels ({sum(p['type'] == 'row' for p in panels)} rows)")
print(REPO_OUTPUT)
print(SYSTEM_OUTPUT)
