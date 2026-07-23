#!/usr/bin/env python3
"""Generate the internal GNR PMT overview without changing the legacy dashboard."""

from __future__ import annotations

import copy
import json
from pathlib import Path


DATASOURCE = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}
REPO_OUTPUT = Path(__file__).parent / "dashboards" / "pmt-gnr-redfish-overview.json"
SYSTEM_OUTPUT = Path(
    "/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-redfish-overview.json"
)
REPO_LOCAL_OUTPUT = (
    Path(__file__).parent / "dashboards" / "pmt-gnr-local-overview.json"
)
SYSTEM_LOCAL_OUTPUT = Path(
    "/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-local-overview.json"
)
REPO_EXPLORER_OUTPUT = (
    Path(__file__).parent / "dashboards" / "pmt-gnr-metric-explorer.json"
)
SYSTEM_EXPLORER_OUTPUT = Path(
    "/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-metric-explorer.json"
)
panels: list[dict] = []
panel_id = 0
y = 0


def next_id() -> int:
    global panel_id
    panel_id += 1
    return panel_id


def target(
    expr: str,
    legend: str = "",
    ref: str = "A",
    instant: bool = False,
    fmt: str = "time_series",
) -> dict:
    result = {"expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        result.update({"instant": True, "range": False, "format": fmt})
    return result


def row(title: str, description: str) -> None:
    global y
    panels.append(
        {
            "id": next_id(),
            "type": "row",
            "title": title,
            "description": description,
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "panels": [],
        }
    )
    y += 1


def base_panel(
    title: str, description: str, x: int, w: int, h: int, panel_type: str
) -> dict:
    return {
        "id": next_id(),
        "type": panel_type,
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
    }


def advance(height: int) -> None:
    global y
    y += height


def add_text(title: str, content: str, x: int, w: int, h: int) -> None:
    panel = base_panel(title, "", x, w, h, "text")
    panel["options"] = {"content": content, "mode": "markdown"}
    panels.append(panel)


def add_stat(
    title: str,
    description: str,
    x: int,
    w: int,
    expr: str,
    *,
    unit: str = "none",
    mappings: list[dict] | None = None,
    thresholds: list[dict] | None = None,
    no_value: str = "No Data",
    decimals: int | None = None,
    h: int = 4,
) -> None:
    defaults: dict = {
        "color": {"mode": "thresholds"},
        "unit": unit,
        "mappings": mappings or [],
        "noValue": no_value,
        "thresholds": {
            "mode": "absolute",
            "steps": thresholds or [{"color": "blue", "value": None}],
        },
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    panel = base_panel(title, description, x, w, h, "stat")
    panel.update(
        {
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {
                "colorMode": "value",
                "graphMode": "none",
                "justifyMode": "center",
                "orientation": "horizontal",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "textMode": "value",
            },
            "targets": [target(expr)],
        }
    )
    panels.append(panel)


def add_stat_group(
    title: str,
    description: str,
    x: int,
    w: int,
    h: int,
    queries: list[dict],
    *,
    unit: str = "none",
    no_value: str = "No Data",
) -> None:
    panel = base_panel(title, description, x, w, h, "stat")
    panel.update(
        {
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "fixed", "fixedColor": "blue"},
                    "unit": unit,
                    "noValue": no_value,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "blue", "value": None}],
                    },
                },
                "overrides": [],
            },
            "options": {
                "colorMode": "value",
                "graphMode": "none",
                "justifyMode": "center",
                "orientation": "horizontal",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "textMode": "value_and_name",
                "wideLayout": True,
            },
            "targets": queries,
        }
    )
    panels.append(panel)


def add_timeseries(
    title: str,
    description: str,
    x: int,
    w: int,
    h: int,
    queries: list[dict],
    *,
    unit: str = "short",
    minimum: float | None = None,
    maximum: float | None = None,
    decimals: int | None = None,
    legend: str = "bottom",
) -> None:
    defaults: dict = {
        "color": {"mode": "palette-classic"},
        "unit": unit,
        "custom": {
            "drawStyle": "line",
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "fillOpacity": 10,
            "gradientMode": "opacity",
            "showPoints": "never",
            "spanNulls": True,
            "stacking": {"mode": "none", "group": "A"},
            "axisPlacement": "auto",
            "axisLabel": "",
            "scaleDistribution": {"type": "linear"},
        },
    }
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    if decimals is not None:
        defaults["decimals"] = decimals
    panel = base_panel(title, description, x, w, h, "timeseries")
    panel.update(
        {
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {
                "legend": {
                    "calcs": ["lastNotNull", "max"],
                    "displayMode": "table",
                    "placement": legend,
                    "showLegend": True,
                    "width": 340,
                },
                "tooltip": {"mode": "multi", "sort": "desc"},
            },
            "targets": queries,
        }
    )
    panels.append(panel)


def add_bar_gauge(
    title: str,
    description: str,
    x: int,
    w: int,
    h: int,
    expr: str,
    legend: str,
    *,
    unit: str = "short",
    minimum: float | None = None,
    maximum: float | None = None,
    decimals: int | None = None,
) -> None:
    defaults: dict = {
        "color": {"mode": "fixed", "fixedColor": "blue"},
        "unit": unit,
        "thresholds": {
            "mode": "absolute",
            "steps": [{"color": "blue", "value": None}],
        },
    }
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    if decimals is not None:
        defaults["decimals"] = decimals
    panel = base_panel(title, description, x, w, h, "bargauge")
    panel.update(
        {
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {
                "displayMode": "gradient",
                "minVizHeight": 18,
                "minVizWidth": 0,
                "namePlacement": "left",
                "orientation": "horizontal",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "showUnfilled": True,
                "sizing": "auto",
                "valueMode": "text",
                "text": {"titleSize": 11, "valueSize": 11},
            },
            "targets": [target(expr, legend, instant=True)],
        }
    )
    panels.append(panel)


def add_residency(
    title: str, description: str, x: int, w: int, h: int, expr: str
) -> None:
    panel = base_panel(title, description, x, w, h, "bargauge")
    panel.update(
        {
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "fixed", "fixedColor": "blue"},
                    "unit": "percent",
                    "decimals": 1,
                    "min": 0,
                    "max": 100,
                    "displayName": "${__field.labels.range}",
                },
                "overrides": [],
            },
            "options": {
                "displayMode": "gradient",
                "minVizHeight": 22,
                "maxVizHeight": 22,
                "namePlacement": "left",
                "orientation": "horizontal",
                "reduceOptions": {
                    "calcs": ["lastNotNull"],
                    "fields": "",
                    "values": False,
                },
                "showUnfilled": True,
                "sizing": "manual",
                "valueMode": "text",
                "text": {"titleSize": 11, "valueSize": 11},
            },
            "targets": [target(expr, "{{range}}", instant=True)],
        }
    )
    panels.append(panel)


def add_table(
    title: str,
    description: str,
    x: int,
    w: int,
    h: int,
    queries: list[dict],
) -> None:
    panel = base_panel(title, description, x, w, h, "table")
    panel.update(
        {
            "fieldConfig": {
                "defaults": {
                    "custom": {
                        "align": "auto",
                        "cellOptions": {"type": "auto"},
                        "inspect": False,
                    },
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "blue", "value": None}],
                    },
                },
                "overrides": [],
            },
            "options": {
                "cellHeight": "sm",
                "footer": {
                    "countRows": False,
                    "fields": "",
                    "reducer": ["sum"],
                    "show": False,
                },
                "showHeader": True,
                "sortBy": [],
            },
            "targets": queries,
            "transformations": [
                {"id": "labelsToFields", "options": {"mode": "columns"}}
            ],
        }
    )
    panels.append(panel)


def status_mapping(options: dict[str, tuple[str, str]]) -> list[dict]:
    return [
        {
            "type": "value",
            "options": {
                value: {"color": color, "index": index, "text": text}
                for index, (value, (text, color)) in enumerate(options.items())
            },
        }
    ]


def with_aggregator_display(expr: str) -> str:
    """Attach a path-aware agg_display label to an expression result."""
    oob = (
        f"({expr}) and on(CollectionMode) "
        f'count by (CollectionMode) ({{PMTEndpoint="$endpoint",'
        f'CollectionMode="redfish"}})'
    )
    oob = (
        f'label_replace(label_replace(label_replace({oob},'
        f'"agg_d","D$1","DeviceId","(.+)"),'
        f'"agg_a","A$1","AccessId","(.+)"),'
        f'"agg_s","S$1","SourceId","(.+)")'
    )
    oob = (
        f'label_join({oob},"agg_locator","/","agg_d","agg_a","agg_s")'
    )
    oob = (
        f'label_replace({oob},"agg_display","AGG[$1]",'
        f'"agg_locator","(.+)")'
    )

    local = (
        f"({expr}) and on(CollectionMode) "
        f'count by (CollectionMode) ({{PMTEndpoint="$endpoint",'
        f'CollectionMode="local"}})'
    )
    local = (
        f'label_replace({local},"agg_display","AGG[$1]",'
        f'"AccessId","(.+)")'
    )
    return f"({oob}) or ({local})"


scope = 'PMTEndpoint="$endpoint",CollectionMode="$path"'
core_scope = f'{scope},PMTGuid="0x22473996"'
all_paths_scope = 'PMTEndpoint="$endpoint"'

temperature = f'{{__name__=~".*_temp_c[0-9]+_temp_celsius",{core_scope}}}'
valid_temperature = f"({temperature} > 0)"
core_temperature = (
    f'label_replace({valid_temperature},"core","$1","__name__",'
    '".*_temp_c([0-9]+)_temp_celsius")'
)
usage = f'{{__name__=~"c[0-9]+_usage_meter_core_usage_total",{core_scope}}}'
core_usage = (
    f'label_replace({usage},"core","$1","__name__",'
    '"c([0-9]+)_usage_meter_core_usage_total")'
)

loss = f"agg_data_loss_count_total{{{scope}}}"
loss_current = f"sum(clamp_min(increase({loss}[5m]),0))"
loss_previous = f"sum(clamp_min(increase({loss}[5m] offset 5m),0))"
loss_previous_2 = f"sum(clamp_min(increase({loss}[5m] offset 10m),0))"
heartbeat_stalled = (
    f'(count(last_update_timestamp_total{{{scope}}}) > 0) '
    f'and (min(changes(last_update_timestamp_total{{{scope}}}[5m])) == 0)'
)
loss_state = (
    f'(vector(2) and on() ({loss_current} > 0) and on() '
    f'({loss_previous} > 0) and on() ({loss_previous_2} > 0))'
    f' or (vector(2) and on() {heartbeat_stalled})'
    f' or (vector(1) and on() ({loss_current} > 0))'
    f" or vector(0)"
)

fivr_scope = f'{scope}'
c_fivr_available = (
    f'{{__name__=~"fivr_health_monitor_.*_available",'
    f'PMTGuid="0x22806802",{fivr_scope}}}'
)
c_fivr_status = (
    f'{{__name__=~"fivr_health_monitor_[0-2]_[0-2]_fivr_health_monitor_'
    f'[0-2]_status_[0-9]{{2}}",PMTGuid="0x22806802",{fivr_scope}}}'
)
c_fivr_state = (
    f'(vector(1) and on() (count({c_fivr_available}) > 0) '
    f'and on() (min({c_fivr_available}) == 1) '
    f'and on() ((count({c_fivr_status} != 0) or vector(0)) == 0))'
    f' or (vector(0) and on() (count({c_fivr_status} != 0) > 0))'
    f" or vector(-1)"
)
c_fivr_nonzero = f"count({c_fivr_status} != 0) or vector(0)"
io_fivr_available = (
    f'{{__name__=~"fivr_health_monitor_.*_available",'
    f'PMTGuid="0x22491753",{fivr_scope}}}'
)
io_fivr_state = (
    f'(vector(1) and on() (count({io_fivr_available}) > 0) '
    f'and on() (min({io_fivr_available}) == 1))'
    f' or (vector(0) and on() (count({io_fivr_available} == 0) > 0))'
    f" or vector(-1)"
)
fivr_locator = (
    f'label_replace(label_replace(({c_fivr_status} != 0),'
    f'"slot","$1","__name__",".*_status_([0-9]{{2}})"),'
    f'"monitor","$1","__name__",".*_fivr_health_monitor_([0-2])_status_.*")'
)

qat_throughput = (
    f'sum(rate(label_replace({{__name__=~"qat[01]_tl_bw_(in|out)_megabytes_total",'
    f'{scope}}},"metric","$1","__name__","(.+)")[5m:]))'
)
qat_state = (
    f'(vector(1) and on() ({qat_throughput} > 0))'
    f' or (vector(0) and on() ({qat_throughput} == 0))'
    f" or vector(-1)"
)

available_mapping = status_mapping(
    {"0": ("Unavailable", "red"), "1": ("Available", "green")}
)
freshness_mapping = status_mapping(
    {"0": ("Stale", "orange"), "1": ("Fresh", "green")}
)
quality_mapping = status_mapping(
    {
        "0": ("Stable", "green"),
        "1": ("Intermittent", "yellow"),
        "2": ("Sustained", "red"),
    }
)
fivr_mapping = status_mapping(
    {
        "-1": ("No Data", "gray"),
        "0": ("Unhealthy", "red"),
        "1": ("Healthy", "green"),
    }
)
qat_mapping = status_mapping(
    {
        "-1": ("No Data", "gray"),
        "0": ("Idle", "gray"),
        "1": ("Active", "blue"),
    }
)
io_fivr_mapping = status_mapping(
    {
        "-1": ("No Data", "gray"),
        "0": ("DEADBEEF", "orange"),
        "1": ("Available", "green"),
    }
)


# 00 — Customer-focused current state
row(
    "00 · Customer Overview",
    "Four immediately readable signals. Technical collection quality, topology and provenance are kept in the final sections.",
)

add_stat(
    "PMT Data",
    "Ready means the selected OOB or in-band path has PMT series and its newest sample is no older than 45 seconds.",
    0,
    6,
    f'(count({{{scope}}}) > bool 0) * '
    f'((time() - max(timestamp(label_replace({{{scope}}},'
    f'"metric","$1","__name__","(.+)")))) < bool 45)',
    mappings=status_mapping(
        {"0": ("Attention", "orange"), "1": ("Ready", "green")}
    ),
)
add_stat(
    "Peak Core Temperature",
    "Maximum valid current core temperature. Disabled 0°C placeholders are excluded. No artificial warning or fault threshold is applied.",
    6,
    6,
    f"max({valid_temperature})",
    unit="celsius",
    thresholds=[{"color": "blue", "value": None}],
)
add_stat(
    "C-Die FIVR",
    "Project convention: Healthy means all exposed two-bit slots are zero and available; any non-zero slot is Unhealthy.",
    12,
    6,
    c_fivr_state,
    mappings=fivr_mapping,
)
add_stat(
    "QAT Activity",
    "Active requires measured QAT PCIe traffic. Idle is expected for CPU-only workloads and does not mean collection failed.",
    18,
    6,
    qat_state,
    mappings=qat_mapping,
)
advance(4)


# 01 — Service and topology
row(
    "01 · PMT Service & Topology",
    "Provider and Aggregator coverage, platform identity and enabled topology signals from the current pipeline.",
)
add_table(
    "Aggregator & Series Inventory",
    "Series count for each discovered Device/Access/Source/GUID instance. One Access group can contain several Aggregators.",
    0,
    24,
    10,
    [
        target(
            f"count by (DeviceId,AccessId,SourceId,PMTGuid,PMTSizeBytes) "
            f"({{{scope}}})",
            "",
            instant=True,
            fmt="table",
        )
    ],
)
advance(10)
add_table(
    "Platform Identity & Firmware",
    "Static CPUID fields and firmware image values used for provenance and schema selection; raw enumerations are not performance values.",
    0,
    12,
    8,
    [
        target(
            f'{{__name__=~"cpuid_platform_id_.*|global_info_firmware_version",'
            f"{scope}}}",
            "",
            instant=True,
            fmt="table",
        )
    ],
)
add_table(
    "Enabled Topology Signals",
    "Enabled domain, UPI, DDR, core and CHA fields. EID, DomainId and AccessId are distinct identifier spaces.",
    12,
    12,
    8,
    [
        target(
            f'topk(64,{{__name__=~"curr_die_ids_enabled_.*|domain_(mask_)?eids_.*|'
            f'core_enabled_mask_.*|cha_enabled_mask_.*",{scope}}} == 1)',
            "",
            instant=True,
            fmt="table",
        )
    ],
)
advance(8)


# 02 — Core environment and activity
row(
    "02 · Core Environment & Activity",
    "Core temperatures, relative activity and throttle events.",
)
add_bar_gauge(
    "Top 12 Core Temperatures",
    "Current valid temperatures by Core.",
    0,
    24,
    9,
    with_aggregator_display(f"topk(12,{core_temperature})"),
    "{{agg_display}} · Core {{core}}",
    unit="celsius",
    minimum=0,
)
advance(9)
add_timeseries(
    "Maximum Core Temperature Trend",
    "Highest valid Core temperature over time.",
    0,
    24,
    9,
    [
        target(
            f"max({core_temperature})",
            "Maximum Core Temperature",
        )
    ],
    unit="celsius",
    minimum=0,
)
advance(9)
add_timeseries(
    "PMT Relative Activity",
    "Top per-Core rates of the experimental U64.38.26 relative-usage counter. Six decimal places are retained; this is not CPU utilization percent.",
    0,
    24,
    9,
    [
        target(
            with_aggregator_display(
                f"topk(12,clamp_min(rate({core_usage}[5m:]),0))"
            ),
            "Top · {{agg_display}} · Core {{core}}",
        ),
    ],
    unit="short",
    minimum=0,
    decimals=6,
)
advance(9)
throttle = (
    f'label_replace(clamp_min(increase(label_replace('
    f'{{__name__=~"c[0-9]+_pvp_throttle_(64|1024)_total",{core_scope}}},'
    f'"metric","$1","__name__","(.+)")[5m:]),0),'
    f'"window","$1","metric",".*_throttle_(64|1024)_total")'
)
throttle = (
    f'label_replace({throttle},"core","$1","metric",'
    '"c([0-9]+)_pvp_throttle_.*")'
)
add_bar_gauge(
    "Throttle Events · Last 5 Minutes",
    "Top five-minute event-count increases for the 64-cycle and 1024-cycle observation families. A non-zero value does not identify thermal, power or VR root cause.",
    0,
    24,
    9,
    with_aggregator_display(f"topk(16,{throttle})"),
    "{{agg_display}} · Core {{core}} · {{window}} cycles",
    unit="short",
    minimum=0,
)
advance(9)
add_text(
    "Open Exact Per-Core Analysis",
    "For one Core's temperature, relative activity, throttle and all residency "
    "profiles, open **[GNR Core Analysis]"
    "(/d/pmt-gnr-core-analysis?var-endpoint=$endpoint&var-path=$path)**. "
    "Its Core target selector is path-local and controls every panel there.",
    0,
    24,
    3,
)
advance(3)


# 03 — Core operating profile
row(
    "03 · Core Operating Profile",
    "Five-minute residency distributions for the selected XML Core field in the selected CORE Aggregator scope; these are not instantaneous readings.",
)
histogram_ranges = {
    "freq": [
        "C6 sleep",
        "≤800 MHz",
        "900–1200 MHz",
        "1300–1600 MHz",
        "1700–2000 MHz",
        "2100–2400 MHz",
        "2500–2800 MHz",
        "2900–3200 MHz",
        "3300–3600 MHz",
        "3700–4000 MHz",
        "4100–4400 MHz",
        ">4400 MHz",
    ],
    "temp": [
        "<20 °C",
        "20.5–27.5 °C",
        "28–35 °C",
        "35.5–42.5 °C",
        "43–50 °C",
        "50.5–57.5 °C",
        "58–65 °C",
        "65.5–72.5 °C",
        "73–80 °C",
        "80.5–87.5 °C",
        "88–95 °C",
        ">95 °C",
    ],
    "volt": [
        "<602 mV",
        "602.5–657 mV",
        "657.5–712 mV",
        "712.5–767 mV",
        "767.5–822 mV",
        "822.5–877 mV",
        "877.5–932 mV",
        "932.5–987 mV",
        "987.5–1042 mV",
        "1042.5–1097 mV",
        "1097.5–1152 mV",
        ">1152 mV",
    ],
}
for kind, title_text, x_pos, width in [
    ("freq", "Frequency Residency", 0, 12),
    ("temp", "Temperature Residency", 12, 12),
    ("volt", "Voltage Residency", 0, 12),
]:
    total_rate = " + ".join(
        f'sum(rate(c${{local_core}}_{kind}_hist_r{bucket}_second_total'
        f"{{{core_scope}}}[5m]))"
        for bucket in range(12)
    )
    ranges = " or ".join(
        f'label_replace((100 * sum(rate(c${{local_core}}_{kind}_hist_r{bucket}_'
        f"second_total{{{core_scope}}}[5m])) / "
        f'clamp_min({total_rate},1e-12)) > 0.1,'
        f'"range","{histogram_ranges[kind][bucket]}","__name__",".*")'
        for bucket in range(12)
    )
    add_residency(
        title_text,
        "Share of valid residency-counter growth in the last five minutes; buckets below 0.1% are hidden.",
        x_pos,
        width,
        8,
        ranges,
    )
    if kind == "temp":
        advance(8)

cdyn_total = " + ".join(
    f'sum(rate(c${{local_core}}_cdyn_level_{level}_res_microsecond_total'
    f"{{{core_scope}}}[5m]))"
    for level in range(6)
)
cdyn_ranges = " or ".join(
    f'label_replace((100 * sum(rate(c${{local_core}}_cdyn_level_{level}_'
    f"res_microsecond_total{{{core_scope}}}[5m])) / "
    f'clamp_min({cdyn_total},1e-12)) > 0.1,'
    f'"range","Cdyn level {level}","__name__",".*")'
    for level in range(6)
)
add_residency(
    "Cdyn Level Residency",
    "Relative distribution across internal Cdyn levels 0–5. The levels have no published business-facing frequency or voltage mapping.",
    12,
    12,
    8,
    cdyn_ranges,
)
advance(8)


# 04 — Uncore, RDT and memory
row(
    "04 · Uncore, RDT & Memory",
    "RMID/CHA and memory signals. Uncalibrated fields remain raw and are never relabeled as bytes/s or GB/s.",
)
mbm_total = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_mbm_total",{scope}}}'
mbm_local = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_mbm_local_total",{scope}}}'
cmt = f'{{__name__=~"cha[0-9]+_rmid[0-9]+_rdt_cmt_total",{scope}}}'
add_timeseries(
    "RDT Memory Transaction Rates · Raw",
    "Top total and local MBM counter rates. Transaction size and exact RMID-to-workload mapping are not available, so the unit is raw/s.",
    0,
    12,
    9,
    [
        target(
            with_aggregator_display(
                f'topk(12,clamp_min(rate(label_replace({mbm_total},'
                f'"metric","$1","__name__","(.+)")[5m:]),0))'
            ),
            "Total · {{agg_display}}",
            "A",
        ),
        target(
            with_aggregator_display(
                f'topk(12,clamp_min(rate(label_replace({mbm_local},'
                f'"metric","$1","__name__","(.+)")[5m:]),0))'
            ),
            "Local · {{agg_display}}",
            "B",
        ),
    ],
    unit="short",
    minimum=0,
)
add_timeseries(
    "RDT Cache Occupancy Activity · Raw",
    "Rate of CMT/cache-line-usage counters by CHA and RMID. Cache-line-to-byte conversion and application identity are unresolved.",
    12,
    12,
    9,
    [
        target(
            with_aggregator_display(
                f'topk(12,clamp_min(rate(label_replace({cmt},'
                f'"metric","$1","__name__","(.+)")[5m:]),0))'
            ),
            "{{agg_display}}",
        )
    ],
    unit="short",
    minimum=0,
)
advance(9)
memory_raw = (
    f'{{__name__=~"memory_(read|write)_bw_counter_.*",{scope}}}'
)
add_timeseries(
    "Memory Channel Counter Change · Raw",
    "Window delta of raw read/write channel fields. The current schema does not prove a byte or bandwidth conversion.",
    0,
    16,
    9,
    [
        target(
            with_aggregator_display(
                f'topk(16,abs(delta(label_replace({memory_raw},'
                f'"metric","$1","__name__","(.+)")[5m:])))'
            ),
            "{{agg_display}} · {{metric}}",
        )
    ],
    unit="short",
    minimum=0,
)
add_stat(
    "Enabled CHA Instances",
    "Count of enabled CHA flags in the selected scope. This is topology configuration, not cache utilization.",
    16,
    8,
    f'sum({{__name__=~"cha_enabled_mask_cha_[0-9]+_en",{scope}}})',
    unit="short",
    no_value="No CHA Mask",
    h=9,
)
advance(9)


# 05 — Power policy and FIVR
row(
    "05 · Power Policy & FIVR",
    "Operational FIVR interpretation plus raw energy, policy and excursion-monitor fields whose codebooks are incomplete.",
)
add_stat_group(
    "FIVR Operational Signals",
    "C-Die 0=Healthy is a project convention. IO-Die DEADBEEF means data unavailable, not hardware failure.",
    0,
    24,
    5,
    [
        target(c_fivr_state, "C-Die state", "A"),
        target(c_fivr_nonzero, "C-Die non-zero slots", "B"),
        target(io_fivr_state, "IO-Die availability", "C"),
    ],
)
advance(5)
add_table(
    "C-Die Non-Zero Slot Locator",
    "Only non-zero slots are listed. The schema does not provide slot-to-rail/core mapping or official meanings for codes 1–3.",
    0,
    24,
    8,
    [target(fivr_locator, "", instant=True, fmt="table")],
)
advance(8)
energy = (
    f'{{__name__=~"energy_accumulator_(core|fivr)_.*_accumulated_energy_.*",'
    f"{scope}}}"
)
add_timeseries(
    "Accumulated Energy Change · Raw",
    "Absolute window delta of accumulated-energy fields. No joule scaling is proven, so the result must not be interpreted as energy or power.",
    0,
    14,
    9,
    [
        target(
            with_aggregator_display(
                f'topk(16,abs(delta(label_replace({energy},'
                f'"metric","$1","__name__","(.+)")[5m:])))'
            ),
            "{{agg_display}} · {{metric}}",
        )
    ],
    unit="short",
    minimum=0,
)
add_table(
    "EPB & PEM Policy Fields · Raw",
    "Current Energy Performance Bias and Program Excursion Monitor fields. Values are raw policy/status enumerations, not percentages or fault flags.",
    14,
    10,
    9,
    [
        target(
            f'topk(32,{{__name__=~"core_epb_.*|socket_epb_.*|pem_.*",{scope}}})',
            "",
            instant=True,
            fmt="table",
        )
    ],
)
advance(9)


# 06 — Accelerator and I/O
row(
    "06 · Accelerator & I/O",
    "QAT signals are meaningful only when a workload submits accelerator jobs. CPU-only workloads should remain Idle.",
)
qat_in = f'{{__name__=~"qat[01]_tl_bw_in_megabytes_total",{scope}}}'
qat_out = f'{{__name__=~"qat[01]_tl_bw_out_megabytes_total",{scope}}}'
add_timeseries(
    "QAT PCIe Throughput",
    "Rate of proven cumulative megabyte counters. Zero MB/s means no QAT workload is generating traffic.",
    0,
    12,
    9,
    [
        target(
            f'sum(rate(label_replace({qat_in},"metric","$1",'
            f'"__name__","(.+)")[5m:]))',
            "Inbound",
            "A",
        ),
        target(
            f'sum(rate(label_replace({qat_out},"metric","$1",'
            f'"__name__","(.+)")[5m:]))',
            "Outbound",
            "B",
        ),
    ],
    unit="MBs",
    minimum=0,
)
qat_average = f'{{__name__=~"qat[01]_avg_.*_nanoseconds",{scope}}}'
qat_activity = (
    f'{{__name__=~"qat[01]_tl_(at_page_req_cnt|me_put_cnt|'
    f'prt_trans_cnt|rd_cmpl_cnt)_total",{scope}}}'
)
add_table(
    "QAT Latency & Activity",
    "Average latency is valid only with traffic. The table pairs current ns gauges with raw activity-counter rates; Idle zero-latency values are not performance results.",
    12,
    12,
    9,
    [
        target(
            f"({qat_average} and on() ({qat_throughput} > 0))",
            "Average latency · ns",
            "A",
            True,
            "table",
        ),
        target(
            f'topk(16,clamp_min(rate(label_replace({qat_activity},'
            f'"metric","$1","__name__","(.+)")[5m:]),0))',
            "Activity · raw/s",
            "B",
            True,
            "table",
        ),
    ],
)
advance(9)


# 07 — Data trust and provenance
row(
    "07 · Data Trust & Provenance",
    "Technical evidence for update behavior and OOB/in-band parity. Data loss is telemetry quality, not a CPU hardware fault counter.",
)
add_stat(
    "Data Freshness",
    "Fresh means the newest selected PMT sample is no older than 45 seconds. This is pipeline freshness, not hardware health.",
    0,
    12,
    f'(time() - max(timestamp(label_replace({{{scope}}},'
    f'"metric","$1","__name__","(.+)")))) < bool 45',
    mappings=freshness_mapping,
)
add_stat(
    "Update Quality",
    "Stable: no new incomplete cycles in 5m. Intermittent: a recent increase. Sustained: three consecutive windows increase or a heartbeat stalls.",
    12,
    12,
    loss_state,
    mappings=quality_mapping,
)
advance(4)
loss_labeled = (
    f'label_replace(clamp_min(increase({loss}[5m]),0),'
    f'"source","$1","CollectionMode","(.*)")'
)
add_timeseries(
    "Incomplete Aggregator Update Cycles",
    "Five-minute count increase by Aggregator. Zero means no newly observed incomplete cycle in the window; no total-cycle denominator exists for a loss percentage.",
    0,
    14,
    9,
    [
        target(
            with_aggregator_display(loss_labeled),
            "{{source}} · {{agg_display}}",
        )
    ],
    unit="short",
    minimum=0,
)
add_table(
    "Path Parity & Update Heartbeat",
    "Compares current series inventory and internal last-update movement across OOB and in-band paths. Repeated Prometheus samples do not imply repeated hardware updates.",
    14,
    10,
    9,
    [
        target(
            f"count by (CollectionMode,PMTGuid) ({{{all_paths_scope}}})",
            "Series coverage",
            "A",
            True,
            "table",
        ),
        target(
            f"changes(last_update_timestamp_total{{{all_paths_scope}}}[5m])",
            "Heartbeat changes",
            "B",
            True,
            "table",
        ),
        target(
            f"clamp_min(increase(agg_data_loss_count_total"
            f"{{{all_paths_scope}}}[5m]),0)",
            "Incomplete cycles",
            "C",
            True,
            "table",
        ),
    ],
)
advance(9)


# Put customer questions first and move provider/topology inventory to the end.
# Rows remain collapsible in Grafana; recompute absolute grid positions after
# reordering so no panel overlaps are introduced.
row_chunks: list[list[dict]] = []
for panel in panels:
    if panel["type"] == "row":
        row_chunks.append([panel])
    else:
        row_chunks[-1].append(panel)
row_chunks[2] = [
    panel
    for panel in row_chunks[2]
    if panel["title"] != "Open Exact Per-Core Analysis"
]

ordered_chunks = [
    row_chunks[0],  # Customer overview
    row_chunks[2],  # Core environment
    row_chunks[4],  # Uncore/RDT/memory
    row_chunks[5],  # Power/FIVR
    row_chunks[6],  # Accelerator
    row_chunks[7],  # Data trust
    row_chunks[1],  # Technical inventory/topology
]
ordered_titles = [
    "00 · Overview",
    "01 · Core Environment & Activity",
    "02 · Uncore, RDT & Memory",
    "03 · Power Policy & FIVR",
    "04 · Accelerator & I/O",
    "05 · Data Trust & Provenance",
    "06 · Technical Inventory & Topology",
]
panels = []
new_y = 0
for chunk, title_text in zip(ordered_chunks, ordered_titles, strict=True):
    old_y = chunk[0]["gridPos"]["y"]
    chunk_height = max(
        panel["gridPos"]["y"] + panel["gridPos"]["h"] for panel in chunk
    ) - old_y
    for panel in chunk:
        panel["gridPos"]["y"] += new_y - old_y
    chunk[0]["title"] = title_text
    panels.extend(chunk)
    new_y += chunk_height

description_overrides = {
    "00 · Overview": "PMT status, temperature, FIVR and QAT activity.",
    "PMT Data": "Current PMT data availability and freshness.",
    "Peak Core Temperature": "Highest current valid Core temperature.",
    "C-Die FIVR": "Current C-Die FIVR operational status.",
    "QAT Activity": "Current QAT traffic state.",
    "01 · Core Environment & Activity": (
        "Core temperatures, relative activity and throttle events."
    ),
    "Top 12 Core Temperatures": "Current valid temperatures by Core.",
    "Maximum Core Temperature Trend": (
        "Highest valid Core temperature over time."
    ),
    "PMT Relative Activity": "Highest current per-Core activity rates.",
    "Throttle Events · Last 5 Minutes": (
        "Highest five-minute throttle-event increases."
    ),
    "02 · Uncore, RDT & Memory": "RDT and memory telemetry.",
    "RDT Memory Transaction Rates · Raw": (
        "Total and local MBM counter rates by CHA and RMID."
    ),
    "RDT Cache Occupancy Activity · Raw": (
        "CMT counter rates by CHA and RMID."
    ),
    "Memory Channel Counter Change · Raw": (
        "Five-minute changes in memory-channel counters."
    ),
    "Enabled CHA Instances": "Current enabled CHA count.",
    "03 · Power Policy & FIVR": "FIVR, energy and policy telemetry.",
    "FIVR Operational Signals": "Current C-Die and IO-Die FIVR signals.",
    "C-Die Non-Zero Slot Locator": "Current non-zero C-Die FIVR slots.",
    "Accumulated Energy Change · Raw": (
        "Five-minute changes in accumulated-energy fields."
    ),
    "EPB & PEM Policy Fields · Raw": "Current EPB and PEM fields.",
    "04 · Accelerator & I/O": "QAT throughput, latency and activity.",
    "QAT PCIe Throughput": "Current QAT PCIe throughput.",
    "QAT Latency & Activity": "Current QAT latency and activity fields.",
    "05 · Data Trust & Provenance": (
        "Data freshness, update quality and path comparison."
    ),
    "Data Freshness": "Age of the newest PMT sample.",
    "Update Quality": "Recent Aggregator update quality.",
    "Incomplete Aggregator Update Cycles": (
        "Five-minute increase by Aggregator."
    ),
    "Path Parity & Update Heartbeat": (
        "Redfish and Local inventory and update comparison."
    ),
    "06 · Technical Inventory & Topology": (
        "Aggregator inventory, platform identity and topology."
    ),
    "Aggregator & Series Inventory": (
        "Current series count by Aggregator instance."
    ),
    "Platform Identity & Firmware": "Current platform identity fields.",
    "Enabled Topology Signals": "Current enabled topology fields.",
}
for panel in panels:
    if panel["title"] in description_overrides:
        panel["description"] = description_overrides[panel["title"]]


variables = [
    {
        "name": "endpoint",
        "label": "Platform endpoint",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": 'label_values({PMTEndpoint=~".+"},PMTEndpoint)',
            "refId": "PrometheusVariableQueryEditor-Endpoint",
        },
        "definition": 'label_values({PMTEndpoint=~".+"},PMTEndpoint)',
        "refresh": 1,
        "sort": 1,
        "current": {"selected": True, "text": "avc01", "value": "avc01"},
    },
    {
        "name": "path",
        "label": "Collection path",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": 'label_values({PMTEndpoint="$endpoint"},CollectionMode)',
            "refId": "PrometheusVariableQueryEditor-Path",
        },
        "definition": 'label_values({PMTEndpoint="$endpoint"},CollectionMode)',
        "refresh": 1,
        "sort": 1,
        "current": {"selected": True, "text": "redfish", "value": "redfish"},
    },
]

dashboard = {
    "annotations": {
        "list": [
            {
                "builtIn": 1,
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "enable": True,
                "hide": True,
                "iconColor": "rgba(255, 96, 96, 1)",
                "name": "Annotations & Alerts",
                "type": "dashboard",
            }
        ]
    },
    "description": (
        "Intel-internal GNR PMT telemetry overview organized by use case and "
        "architecture domain, with strict units and full Explorer drill-down."
    ),
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "links": [
        {
            "asDropdown": False,
            "icon": "search",
            "includeVars": False,
            "keepTime": True,
            "tags": [],
            "targetBlank": False,
            "title": "Metric Explorer",
            "tooltip": "Search all 5,285 PMT metric names",
            "type": "link",
            "url": "/d/pmt-gnr-metric-explorer",
        },
        {
            "asDropdown": False,
            "icon": "doc",
            "includeVars": False,
            "keepTime": False,
            "tags": [],
            "targetBlank": True,
            "title": "Bilingual Dashboard Guide",
            "tooltip": "Panel semantics, units, caveats and unresolved items",
            "type": "link",
            "url": (
                "https://github.com/Jacky-code535/PMT/blob/"
                "pmt-redfish-dashboard/docs/gnr-telemetry-dashboard-guide.md"
            ),
        },
    ],
    "liveNow": True,
    "panels": panels,
    "refresh": "20s",
    "schemaVersion": 41,
    "tags": [
        "Intel Internal",
        "GNR",
        "Intel PMT",
        "Redfish",
        "in-band",
        "telemetry overview",
    ],
    "templating": {"list": variables},
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": {
        "refresh_intervals": ["20s", "30s", "1m", "5m"],
        "time_options": ["15m", "30m", "1h", "6h", "12h", "24h", "7d"],
    },
    "timezone": "browser",
    "title": "Intel PMT · GNR Telemetry Overview · Internal",
    "uid": "pmt-gnr-telemetry-overview",
    "version": 1,
}

def replace_template(value: object, old: str, new: str) -> object:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_template(item, old, new) for item in value]
    if isinstance(value, dict):
        return {
            key: replace_template(item, old, new)
            for key, item in value.items()
        }
    return value


def build_path_overview(
    mode: str,
    title: str,
    uid: str,
    other_title: str,
    other_uid: str,
) -> dict:
    result = replace_template(copy.deepcopy(dashboard), "$path", mode)
    assert isinstance(result, dict)
    result["title"] = title
    result["uid"] = uid
    result["description"] = f"Intel-internal GNR PMT {mode} overview."
    result["templating"]["list"] = [result["templating"]["list"][0]]
    result["links"].insert(
        0,
        {
            "asDropdown": False,
            "icon": "exchange-alt",
            "includeVars": False,
            "keepTime": True,
            "tags": [],
            "targetBlank": False,
            "title": other_title,
            "tooltip": f"Switch to {other_title}",
            "type": "link",
            "url": f"/d/{other_uid}?var-endpoint=$endpoint",
        },
    )
    return result


redfish_dashboard = build_path_overview(
    "redfish",
    "Intel PMT · GNR Redfish Overview · Internal",
    "pmt-gnr-redfish-overview",
    "Open Local Overview",
    "pmt-gnr-local-overview",
)
local_dashboard = build_path_overview(
    "local",
    "Intel PMT · GNR Local Overview · Internal",
    "pmt-gnr-local-overview",
    "Open Redfish Overview",
    "pmt-gnr-redfish-overview",
)

serialized = json.dumps(redfish_dashboard, indent=2, ensure_ascii=False) + "\n"
local_serialized = json.dumps(local_dashboard, indent=2, ensure_ascii=False) + "\n"
REPO_OUTPUT.write_text(serialized, encoding="utf-8")
REPO_LOCAL_OUTPUT.write_text(local_serialized, encoding="utf-8")
SYSTEM_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
SYSTEM_OUTPUT.write_text(serialized, encoding="utf-8")
SYSTEM_LOCAL_OUTPUT.write_text(local_serialized, encoding="utf-8")

content_panels = sum(panel["type"] != "row" for panel in panels)
rows = sum(panel["type"] == "row" for panel in panels)
targets = sum(len(panel.get("targets", [])) for panel in panels)
print(
    f"Generated GNR Redfish/Local overviews: {rows} rows, "
    f"{content_panels} content panels each, {targets} PromQL targets each"
)
print(REPO_OUTPUT)
print(SYSTEM_OUTPUT)
print(REPO_LOCAL_OUTPUT)
print(SYSTEM_LOCAL_OUTPUT)


_ROLLED_BACK_CORE_DETAIL_SOURCE = r"""
# Generate a Core Detail dashboard. Overview matrix links pass one exact
# path-local core_target; no Redfish-to-Local physical mapping is implied.
panels = []
panel_id = 0
y = 0


def selected_core(expr: str) -> str:
    selector = (
        'label_replace(vector(0),"core_target","$target",'
        '"__name__",".*")'
    )
    return f"({expr}) and on (core_target) ({selector})"


row(
    "00 · Selected Core",
    "The target is passed from an Overview matrix row and remains within one collection path.",
)
add_text(
    "How This Target Is Selected",
    "This page does not reuse a Redfish selector for Local data. The Overview "
    "passes the exact path-local locator shown below. **$target** is an "
    "Aggregator XML Core field, not a Linux CPU number or a proven cross-path "
    "physical-Core identity.",
    0,
    24,
    4,
)
advance(4)
add_stat(
    "$target · Current Temperature",
    "Latest valid temperature for this exact Aggregator XML Core field.",
    0,
    8,
    selected_core(with_core_target(core_temperature)),
    unit="celsius",
    no_value="No enabled Core data",
)
add_stat(
    "$target · Activity Rate",
    "Experimental U64.38.26 relative-usage rate; not CPU utilization percent.",
    8,
    8,
    selected_core(
        with_core_target(
            enabled_cores(f"clamp_min(rate({core_usage}[5m:]),0)")
        )
    ),
    unit="short",
    no_value="No enabled Core data",
    decimals=6,
)
detail_throttle = f"({throttle_64}) or ({throttle_1024})"
add_stat(
    "$target · Throttle Δ",
    "Combined 64-cycle and 1024-cycle event-count increase in the last five minutes.",
    16,
    8,
    f"sum({selected_core(with_core_target(enabled_cores(detail_throttle)))})",
    unit="short",
    no_value="No events",
    decimals=0,
)
advance(4)

row(
    "01 · Temperature & Activity History",
    "Time histories for one exact path-local Core target.",
)
add_timeseries(
    "$target · Temperature History",
    "Raw valid temperature history for the selected XML Core field.",
    0,
    12,
    9,
    [
        target(
            selected_core(with_core_target(core_temperature)),
            "$target",
        )
    ],
    unit="celsius",
    minimum=0,
)
add_timeseries(
    "$target · Relative Activity History",
    "Five-minute rate of the experimental relative-usage counter.",
    12,
    12,
    9,
    [
        target(
            selected_core(
                with_core_target(
                    enabled_cores(
                        f"clamp_min(rate({core_usage}[5m:]),0)"
                    )
                )
            ),
            "$target",
        )
    ],
    unit="short",
    minimum=0,
    decimals=6,
)
advance(9)
add_timeseries(
    "$target · Throttle Event History",
    "Rolling five-minute increases for the 64-cycle and 1024-cycle observation families.",
    0,
    24,
    8,
    [
        target(
            selected_core(
                with_core_target(enabled_cores(throttle_64))
            ),
            "64 cycles",
            "A",
        ),
        target(
            selected_core(
                with_core_target(enabled_cores(throttle_1024))
            ),
            "1024 cycles",
            "B",
        ),
    ],
    unit="short",
    minimum=0,
)
advance(8)

row(
    "02 · Per-Core Operating Profile",
    "Five-minute residency percentages calculated only from this Core's own counters.",
)
detail_profiles = [
    (
        "Frequency Residency",
        per_core_residency(
            "freq_hist_r", "second_total", histogram_ranges["freq"]
        ),
        0,
    ),
    (
        "Temperature Residency",
        per_core_residency(
            "temp_hist_r", "second_total", histogram_ranges["temp"]
        ),
        12,
    ),
    (
        "Voltage Residency",
        per_core_residency(
            "volt_hist_r", "second_total", histogram_ranges["volt"]
        ),
        0,
    ),
    (
        "Cdyn Level Residency",
        per_core_residency(
            "cdyn_level_",
            "res_microsecond_total",
            [f"Cdyn level {level}" for level in range(6)],
        ),
        12,
    ),
]
for index, (title_text, expr, x_pos) in enumerate(detail_profiles):
    add_residency(
        f"$target · {title_text}",
        "This distribution retains the selected Core's own counters; no cross-Core aggregation is applied.",
        x_pos,
        12,
        8,
        selected_core(expr),
    )
    if index in {1, 3}:
        advance(8)

core_detail_variables = [
    {
        "name": "endpoint",
        "label": "Platform endpoint",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": 'label_values({PMTEndpoint=~".+"},PMTEndpoint)',
            "refId": "PrometheusVariableQueryEditor-Endpoint",
        },
        "definition": 'label_values({PMTEndpoint=~".+"},PMTEndpoint)',
        "refresh": 1,
        "hide": 2,
        "current": {"selected": True, "text": "avc01", "value": "avc01"},
    },
    {
        "name": "path",
        "label": "Collection path",
        "type": "custom",
        "query": "redfish,local",
        "options": [],
        "hide": 2,
        "current": {"selected": True, "text": "redfish", "value": "redfish"},
    },
    {
        "name": "target",
        "label": "Core target",
        "type": "textbox",
        "query": "AGG[D0/A25/S2] · Core 0",
        "hide": 2,
        "current": {
            "selected": True,
            "text": "AGG[D0/A25/S2] · Core 0",
            "value": "AGG[D0/A25/S2] · Core 0",
        },
    },
]

core_detail_dashboard = {
    "annotations": dashboard["annotations"],
    "description": (
        "Complete per-Core PMT detail reached from a GNR Overview matrix row; "
        "the path-local locator is preserved without claiming cross-path mapping."
    ),
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "links": [
        {
            "asDropdown": False,
            "icon": "arrow-left",
            "includeVars": False,
            "keepTime": True,
            "tags": [],
            "targetBlank": False,
            "title": "Back to GNR Overview",
            "tooltip": "Return to all-Core matrices",
            "type": "link",
            "url": (
                "/d/pmt-gnr-telemetry-overview"
                "?var-endpoint=$endpoint&var-path=$path"
            ),
        }
    ],
    "liveNow": True,
    "panels": panels,
    "refresh": "20s",
    "schemaVersion": 41,
    "tags": ["Intel Internal", "GNR", "Intel PMT", "Core detail"],
    "templating": {"list": core_detail_variables},
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": dashboard["timepicker"],
    "timezone": "browser",
    "title": "Intel PMT · GNR Core Detail · Internal",
    "uid": "pmt-gnr-core-detail",
    "version": 1,
}
core_detail_serialized = (
    json.dumps(core_detail_dashboard, indent=2, ensure_ascii=False) + "\n"
)
REPO_CORE_DETAIL_OUTPUT.write_text(
    core_detail_serialized, encoding="utf-8"
)
SYSTEM_CORE_DETAIL_OUTPUT.write_text(
    core_detail_serialized, encoding="utf-8"
)
print(
    f"Generated GNR Core Detail: "
    f"{sum(panel['type'] != 'row' for panel in panels)} content panels"
)
print(REPO_CORE_DETAIL_OUTPUT)
print(SYSTEM_CORE_DETAIL_OUTPUT)
"""


_ARCHIVED_CORE_ANALYSIS_SOURCE = r"""
# Generate a focused Core Analysis dashboard. Every visible variable controls
# every metric panel, and the target remains local to the selected path.
panels = []
panel_id = 0
y = 0
core_identity = (
    "PMTEndpoint,CollectionMode,DeviceId,AccessId,SourceId,core"
)


def analysis_core_target(expr: str) -> str:
    displayed = with_aggregator_display(expr)
    return (
        f'label_join({displayed},"core_target"," · Core ",'
        f'"agg_display","core")'
    )


def selected_analysis_core(expr: str) -> str:
    selector = (
        'label_replace(vector(0),"core_target","$core_target",'
        '"__name__",".*")'
    )
    return (
        f"({analysis_core_target(expr)}) "
        f"and on (core_target) ({selector})"
    )


def analysis_residency(
    metric_stem: str,
    suffix: str,
    labels: list[str],
) -> str:
    selector = (
        f'{{__name__=~"c[0-9]+_{metric_stem}[0-9]+_{suffix}",'
        f"{core_scope}}}"
    )
    all_labeled = (
        f'label_replace({selector},"core","$1","__name__",'
        f'"c([0-9]+)_{metric_stem}[0-9]+_{suffix}")'
    )
    all_labeled = (
        f'label_replace({all_labeled},"bucket","$1","__name__",'
        f'"c[0-9]+_{metric_stem}([0-9]+)_{suffix}")'
    )
    denominator = (
        f"sum by ({core_identity}) (rate({all_labeled}[5m:]))"
    )
    buckets = []
    for index, label in enumerate(labels):
        bucket = (
            f'{{__name__=~"c[0-9]+_{metric_stem}{index}_{suffix}",'
            f"{core_scope}}}"
        )
        numerator = (
            f'label_replace({bucket},"core","$1","__name__",'
            f'"c([0-9]+)_{metric_stem}{index}_{suffix}")'
        )
        percentage = (
            f"(100 * rate({numerator}[5m:]) / "
            f"on ({core_identity}) group_left "
            f"clamp_min({denominator},1e-12))"
        )
        buckets.append(
            f'label_replace({percentage},"range","{label}",'
            f'"core",".+")'
        )
    return selected_analysis_core(" or ".join(buckets))


analysis_throttle_64 = (
    f'clamp_min(increase(label_replace({{__name__=~"c[0-9]+_pvp_'
    f'throttle_64_total",{core_scope}}},"core","$1","__name__",'
    f'"c([0-9]+)_pvp_throttle_64_total")[5m:]),0)'
)
analysis_throttle_1024 = (
    f'clamp_min(increase(label_replace({{__name__=~"c[0-9]+_pvp_'
    f'throttle_1024_total",{core_scope}}},"core","$1","__name__",'
    f'"c([0-9]+)_pvp_throttle_1024_total")[5m:]),0)'
)

row(
    "00 · Exact Core Target",
    "All controls on this dashboard apply to every panel. The target is path-local and does not imply OOB-to-Local physical mapping.",
)
add_text(
    "How to Read This Dashboard",
    "Select **Platform endpoint**, **Collection path**, then one **Core target**. "
    "Redfish targets use `AGG[D/A/S] · Core N`; Local targets use "
    "`AGG[telemN] · Core N`. Every panel below uses that exact target.",
    0,
    24,
    3,
)
advance(3)
add_stat(
    "$core_target · Current Temperature",
    "Latest valid temperature for this exact Aggregator XML Core field.",
    0,
    8,
    selected_analysis_core(core_temperature),
    unit="celsius",
    no_value="No enabled Core data",
)
add_stat(
    "$core_target · Activity Rate",
    "Experimental U64.38.26 relative-usage rate; not CPU utilization percent.",
    8,
    8,
    selected_analysis_core(
        f"clamp_min(rate({core_usage}[5m:]),0)"
    ),
    unit="short",
    no_value="No enabled Core data",
    decimals=6,
)
add_stat(
    "$core_target · Throttle Δ",
    "Combined 64-cycle and 1024-cycle event-count increase over five minutes.",
    16,
    8,
    f"sum({selected_analysis_core(f'({analysis_throttle_64}) or ({analysis_throttle_1024})')})",
    unit="short",
    no_value="No events",
    decimals=0,
)
advance(4)

row(
    "01 · Core History",
    "Temperature, relative activity and throttle history for the exact selected target.",
)
add_timeseries(
    "$core_target · Temperature",
    "Valid temperature history for this Aggregator XML Core field.",
    0,
    12,
    9,
    [target(selected_analysis_core(core_temperature), "$core_target")],
    unit="celsius",
    minimum=0,
)
add_timeseries(
    "$core_target · Relative Activity",
    "Five-minute rate of the experimental relative-usage counter.",
    12,
    12,
    9,
    [
        target(
            selected_analysis_core(
                f"clamp_min(rate({core_usage}[5m:]),0)"
            ),
            "$core_target",
        )
    ],
    unit="short",
    minimum=0,
    decimals=6,
)
advance(9)
add_timeseries(
    "$core_target · Throttle Events",
    "Rolling five-minute increases for both throttle observation families.",
    0,
    24,
    8,
    [
        target(
            selected_analysis_core(analysis_throttle_64),
            "64 cycles",
            "A",
        ),
        target(
            selected_analysis_core(analysis_throttle_1024),
            "1024 cycles",
            "B",
        ),
    ],
    unit="short",
    minimum=0,
)
advance(8)

row(
    "02 · Core Operating Profile",
    "Each percentage uses only the selected Core's own five-minute counter growth.",
)
analysis_profiles = [
    (
        "Frequency Residency",
        analysis_residency(
            "freq_hist_r", "second_total", histogram_ranges["freq"]
        ),
        0,
    ),
    (
        "Temperature Residency",
        analysis_residency(
            "temp_hist_r", "second_total", histogram_ranges["temp"]
        ),
        12,
    ),
    (
        "Voltage Residency",
        analysis_residency(
            "volt_hist_r", "second_total", histogram_ranges["volt"]
        ),
        0,
    ),
    (
        "Cdyn Level Residency",
        analysis_residency(
            "cdyn_level_",
            "res_microsecond_total",
            [f"Cdyn level {level}" for level in range(6)],
        ),
        12,
    ),
]
for index, (title_text, expr, x_pos) in enumerate(analysis_profiles):
    add_residency(
        f"$core_target · {title_text}",
        "No counter from another Core is included in this distribution.",
        x_pos,
        12,
        8,
        expr,
    )
    if index in {1, 3}:
        advance(8)

target_inventory = analysis_core_target(core_temperature)
target_inventory = (
    f'label_replace({target_inventory},"core_value","$1",'
    f'"core_target","(.+)")'
)
target_variable_query = (
    f"query_result(count by (core_target,core_value) "
    f"({target_inventory}))"
)
core_analysis_variables = [
    variables[0],
    variables[1],
    {
        "name": "core_target",
        "label": "Core target",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": target_variable_query,
            "refId": "PrometheusVariableQueryEditor-CoreTarget",
        },
        "definition": target_variable_query,
        "regex": (
            '/core_target="(?<text>[^"]+)",'
            'core_value="(?<value>[^"]+)"/'
        ),
        "refresh": 1,
        "sort": 1,
        "current": {
            "selected": True,
            "text": "AGG[D0/A25/S2] · Core 0",
            "value": "AGG[D0/A25/S2] · Core 0",
        },
    },
]
core_analysis_dashboard = {
    "annotations": dashboard["annotations"],
    "description": (
        "Focused path-local Core analysis. Endpoint, path and Core target "
        "control every metric panel."
    ),
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "links": [
        {
            "asDropdown": False,
            "icon": "arrow-left",
            "includeVars": False,
            "keepTime": True,
            "tags": [],
            "targetBlank": False,
            "title": "Back to Customer Overview",
            "tooltip": "Return to the concise GNR overview",
            "type": "link",
            "url": (
                "/d/pmt-gnr-telemetry-overview"
                "?var-endpoint=$endpoint&var-path=$path"
            ),
        }
    ],
    "liveNow": True,
    "panels": panels,
    "refresh": "20s",
    "schemaVersion": 41,
    "tags": ["Intel Internal", "GNR", "Intel PMT", "Core analysis"],
    "templating": {"list": core_analysis_variables},
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": dashboard["timepicker"],
    "timezone": "browser",
    "title": "Intel PMT · GNR Core Analysis · Internal",
    "uid": "pmt-gnr-core-analysis",
    "version": 1,
}
core_analysis_serialized = (
    json.dumps(core_analysis_dashboard, indent=2, ensure_ascii=False) + "\n"
)
REPO_CORE_ANALYSIS_OUTPUT.write_text(
    core_analysis_serialized, encoding="utf-8"
)
SYSTEM_CORE_ANALYSIS_OUTPUT.write_text(
    core_analysis_serialized, encoding="utf-8"
)
print(
    f"Generated GNR Core Analysis: "
    f"{sum(panel['type'] != 'row' for panel in panels)} content panels"
)
print(REPO_CORE_ANALYSIS_OUTPUT)
print(SYSTEM_CORE_ANALYSIS_OUTPUT)
"""


# Generate a dedicated Explorer for this Overview. The preserved legacy
# Explorer continues to return to the preserved legacy dashboard.
panels = []
panel_id = 0
y = 0
explorer_scope = (
    'PMTEndpoint="$endpoint",CollectionMode="$path",DeviceId=~"$device",'
    'AccessId=~"$access",PMTGuid=~"$die"'
)
row(
    "Metric Search Results",
    "Search all current PMT names. Interpret each result with its catalog type, unit and family guidance.",
)
add_text(
    "How to Use",
    "Select **Metric** at the top. Use **Raw History** for current gauges and "
    "historical counters. In **Five-Minute Change**, read only the calculation "
    "that matches the metric type. Raw and No Data are not interchangeable.",
    0,
    24,
    3,
)
advance(3)
explorer_selector = f'{{__name__="$metric",{explorer_scope}}}'
add_timeseries(
    "$metric · Raw History",
    "Raw history for the selected metric. Counter absolute values normally do not represent current intensity.",
    0,
    16,
    10,
    [
        target(
            with_aggregator_display(explorer_selector),
            "{{agg_display}}",
        )
    ],
    unit="short",
    legend="right",
)
add_table(
    "$metric · Current Series",
    "Current values with complete source labels.",
    16,
    8,
    10,
    [target(explorer_selector, "", instant=True, fmt="table")],
)
advance(10)
add_timeseries(
    "$metric · Five-Minute Change",
    "Counter rate and gauge delta are both shown for technical inspection; only one normally matches the selected family semantics.",
    0,
    24,
    8,
    [
        target(
            with_aggregator_display(f"rate({explorer_selector}[5m])"),
            "Counter rate/s · {{agg_display}}",
            "A",
        ),
        target(
            with_aggregator_display(
                f"delta({explorer_selector}[5m])/300"
            ),
            "Gauge delta/s · {{agg_display}}",
            "B",
        ),
    ],
    unit="short",
)
advance(8)

explorer_variables = [
    variables[0],
    variables[1],
    {
        "name": "device",
        "label": "Device / Host",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": (
                'label_values({PMTEndpoint="$endpoint",'
                'CollectionMode="$path"},DeviceId)'
            ),
            "refId": "PrometheusVariableQueryEditor-Device",
        },
        "definition": (
            'label_values({PMTEndpoint="$endpoint",'
            'CollectionMode="$path"},DeviceId)'
        ),
        "refresh": 1,
        "sort": 3,
        "includeAll": True,
        "allValue": ".*",
        "multi": True,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
    },
    {
        "name": "access",
        "label": "Access",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": (
                'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
                'DeviceId=~"$device"},AccessId)'
            ),
            "refId": "PrometheusVariableQueryEditor-Access",
        },
        "definition": (
            'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
            'DeviceId=~"$device"},AccessId)'
        ),
        "refresh": 1,
        "sort": 3,
        "includeAll": True,
        "allValue": ".*",
        "multi": True,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
    },
    {
        "name": "die",
        "label": "PMT GUID / Die",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": (
                'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
                'DeviceId=~"$device",AccessId=~"$access"},PMTGuid)'
            ),
            "refId": "PrometheusVariableQueryEditor-Die",
        },
        "definition": (
            'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
            'DeviceId=~"$device",AccessId=~"$access"},PMTGuid)'
        ),
        "refresh": 1,
        "sort": 1,
        "includeAll": True,
        "allValue": ".*",
        "multi": True,
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
    },
    {
        "name": "metric",
        "label": "Metric",
        "type": "query",
        "datasource": DATASOURCE,
        "query": {
            "query": (
                'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
                'DeviceId=~"$device",AccessId=~"$access",PMTGuid=~"$die"},'
                "__name__)"
            ),
            "refId": "PrometheusVariableQueryEditor-Metric",
        },
        "definition": (
            'label_values({PMTEndpoint="$endpoint",CollectionMode="$path",'
            'DeviceId=~"$device",AccessId=~"$access",PMTGuid=~"$die"},'
            "__name__)"
        ),
        "refresh": 1,
        "sort": 1,
        "current": {
            "selected": True,
            "text": "c0_c1_c2_c3_temp_c0_temp_celsius",
            "value": "c0_c1_c2_c3_temp_c0_temp_celsius",
        },
    },
]

explorer_dashboard = {
    "annotations": dashboard["annotations"],
    "description": (
        "Intel-internal full PMT metric search paired with the GNR Telemetry "
        "Overview."
    ),
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 1,
    "links": [
        {
            "asDropdown": False,
            "icon": "arrow-left",
            "includeVars": False,
            "keepTime": True,
            "tags": [],
            "targetBlank": False,
            "title": "Back to Redfish Overview",
            "tooltip": "Return to the GNR Redfish overview",
            "type": "link",
            "url": "/d/pmt-gnr-redfish-overview",
        },
        {
            "asDropdown": False,
            "icon": "doc",
            "includeVars": False,
            "keepTime": False,
            "tags": [],
            "targetBlank": True,
            "title": "Bilingual Dashboard Guide",
            "tooltip": "Metric semantics, units and unresolved items",
            "type": "link",
            "url": (
                "https://github.com/Jacky-code535/PMT/blob/"
                "pmt-redfish-dashboard/docs/gnr-telemetry-dashboard-guide.md"
            ),
        },
    ],
    "liveNow": True,
    "panels": panels,
    "refresh": "20s",
    "schemaVersion": 41,
    "tags": ["Intel Internal", "GNR", "Intel PMT", "metric explorer"],
    "templating": {"list": explorer_variables},
    "time": {"from": "now-30m", "to": "now"},
    "timepicker": dashboard["timepicker"],
    "timezone": "browser",
    "title": "Intel PMT · GNR Metric Explorer · Internal",
    "uid": "pmt-gnr-metric-explorer",
    "version": 1,
}
explorer_serialized = (
    json.dumps(explorer_dashboard, indent=2, ensure_ascii=False) + "\n"
)
REPO_EXPLORER_OUTPUT.write_text(explorer_serialized, encoding="utf-8")
SYSTEM_EXPLORER_OUTPUT.write_text(explorer_serialized, encoding="utf-8")
print(
    f"Generated GNR Explorer: {sum(panel['type'] != 'row' for panel in panels)} "
    "content panels"
)
print(REPO_EXPLORER_OUTPUT)
print(SYSTEM_EXPLORER_OUTPUT)
