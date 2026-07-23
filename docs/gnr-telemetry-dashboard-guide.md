# GNR Telemetry Dashboard Guide / GNR Telemetry Dashboard 阅读指南

> **Intel Internal Only / 仅限 Intel 内部使用**
>
> This guide is written in a customer-readable style, but it is not approved for
> external distribution. It describes the currently deployed `avc01` pipeline
> and uses internal architecture context. Do not forward it to customers without
> a separate content and confidentiality review.
>
> 本文采用便于客户理解的表达方式，但不是已经批准的外发材料。它描述当前
> `avc01` 实际链路，并使用了内部架构背景。未经独立内容和保密审查，不得直接
> 交付外部客户。

## 1. Purpose / 文档目的

The dashboard is an internal, customer-readable overview of the PMT telemetry
that is **actually available** on the current two-socket GNR server. It is not a
copy of the Telemetry Platform Architecture Specification, and it does not
pretend that every planned PMT capability is collected.

本 Dashboard 面向当前双路 GNR 服务器上**实际能够采集**的 PMT 数据。它不是
TPAS 目录的可视化副本，也不会把规划中的 PMT 能力误写成当前已经采集的能力。

It has four information layers:

1. **GNR Redfish Overview** — 25 selected panels on the fixed OOB path;
2. **GNR Local Overview** — the same 25 panels on the fixed in-band path;
3. **Metric Explorer** — search and inspect all 5,285 metric names;
4. **Metric references** — the 38-family reference and row-level CSV catalog.

对应四层信息结构：

1. **GNR Redfish Overview**：固定OOB路径的25个精选Panel；
2. **GNR Local Overview**：固定in-band路径的同一组25个Panel；
3. **Metric Explorer**：搜索全部 5,285 个准确 metric names；
4. **Metric references**：38 个 family 的详细参考和逐行 CSV catalog。

The previous dashboard (`pmt-avc01-redfish`) is preserved. The new dashboard is
independent:

- titles: `Intel PMT · GNR Redfish Overview · Internal` and
  `Intel PMT · GNR Local Overview · Internal`;
- UIDs: `pmt-gnr-redfish-overview` and `pmt-gnr-local-overview`;
- generator: `tools/otel/generate_gnr_telemetry_overview.py`;
- generated JSON: `tools/otel/dashboards/pmt-gnr-redfish-overview.json` and
  `tools/otel/dashboards/pmt-gnr-local-overview.json`;
- paired Explorer UID: `pmt-gnr-metric-explorer`;
- paired Explorer JSON: `tools/otel/dashboards/pmt-gnr-metric-explorer.json`.

## 2. Architecture and current capability / 架构与当前能力

### 2.1 Data path / 数据路径

```text
GNR hardware and firmware telemetry sources
  → PMT Aggregators / Telemetry Semantic Spaces
    → OOB: BMC Redfish                 → Redfish Collector
    → In-band: local PMT MMIO/sysfs    → Local Collector
      → OpenTelemetry Prometheus exporters
        → Prometheus TSDB
          → Grafana Overview and Metric Explorer
```

An **Aggregator** is a read-only telemetry region identified by GUID and size.
The Collector uses the matching XML schema to decode offsets, packed fields and
transformations into Prometheus metrics.

**Aggregator** 是由 GUID 和 size 标识的只读 telemetry region。Collector 使用
匹配的 XML schema，把二进制偏移、packed fields 和 transformation 解码成
Prometheus metrics。

The current pipeline exposes Aggregator data. The following architecture
capabilities are **not** represented as active dashboard data unless a real
source is added:

- Watcher configuration and threshold/timer notifications;
- Watcher Streamer or Sampler payloads;
- CrashLog harvesting;
- configurable PMON event programming;
- trusted-session state;
- future DMR, XPU or shared-IPU telemetry.

当前链路主要暴露 Aggregator 数据。Watcher 配置、Streamer/Sampler、CrashLog、
可编程 PMON event、trusted session，以及未来 DMR/XPU/IPU 能力没有真实数据源，
所以 Dashboard 不创建虚假的空 panel。

### 2.2 Current platform coverage / 当前平台覆盖

The current platform has two sockets, 192 physical cores, 36 Aggregator
instances per collection path, seven GUID/size layouts, 5,285 metric names and
32,710 series per path. Redfish and in-band observe the same hardware; they are
two access paths, not 72 independent Aggregators.

当前平台有 2 个 socket、192 个物理 core、每条采集路径 36 个 Aggregator
instances、7 种 GUID/size 布局、5,285 个 metric names，以及每条路径 32,710
条 series。Redfish 与 in-band 观察同一硬件，不是 72 个独立 Aggregator。

See `pmt-platform-topology.md` for the full Device/Access/Source/GUID map.

## 3. Reading sequence / 推荐阅读顺序

For a first-time viewer:

1. read the use-case strip and data path in row 00;
2. check the six current-state cards;
3. use row 01 to confirm source and topology coverage;
4. open one domain that matches the question being investigated;
5. use Metric Explorer only when the fixed panels are insufficient;
6. check the Open Semantics Register before assigning a physical unit to any
   value labelled `Raw`.

第一次使用时：

1. 先阅读第 00 栏的 use-case 和数据路径；
2. 再看六个当前状态卡；
3. 用第 01 栏确认采集来源和拓扑覆盖；
4. 按当前问题展开一个 telemetry domain；
5. 固定 panel 不足时再进入 Metric Explorer；
6. 对任何标记为 `Raw` 的值，先查本文末尾 Open Semantics Register，再决定能否
   赋予物理单位。

## 4. Dashboard filters / 顶部筛选器

| Filter | Meaning / 含义 | Default / 默认 |
|---|---|---|
| Platform endpoint | Logical monitored platform / 被监控平台 | `avc01` |

Each Overview has one global filter. Collection path is fixed by the Dashboard:
Redfish or Local. Use the header link to switch paths while preserving endpoint
and time range.

The legend deliberately uses different locators for the two access paths, then
uses the Core number exactly as the XML HELP describes it:

```text
Redfish: AGG[D<DeviceId>/A<AccessId>/S<SourceId>] · Core <XML number>
Local:   AGG[<telemN>] · Core <XML number>
```

For example, `AGG[D1/A248/S2] · Core 0` locates a Redfish Aggregator instance.
`AGG[telem0] · Core 0` locates a Local sysfs PMT device on the host already
selected by the `Platform endpoint` filter. Repeating `avc01` in every series
would consume legend width without adding identity. The locator shape already
identifies the path, so the legend also omits redundant `OOB` and `LOCAL`
prefixes. In both cases, `Core 0` is the `C0_*` field inside that XML layout.
It does not claim Linux CPU 0 or a globally numbered physical core. These two
locators must not be treated as the same hardware instance until physical
discovery mapping is complete.

## 5. Time model / 三层时间模型

Do not treat every Grafana sample as a new hardware sample. Three independent
time layers exist:

1. hardware/firmware internal update cycles;
2. Collector reads, currently approximately every 20 seconds;
3. Prometheus scrapes and stores exporter values.

不能把每一个 Grafana data point 都理解为新的硬件采样。必须区分：

1. hardware/firmware 内部更新周期；
2. Collector 当前约 20 秒一次的读取；
3. Prometheus 对 exporter 的 scrape 和存储。

Prometheus may store repeated values between two real PMT updates. A short
`rate()` window can therefore look stepped. Dashboard refresh controls screen
refresh only; it does not change the hardware update period.

## 6. Units and transformations / 单位与转换规则

### 6.1 Defined units / 已确认单位

- current core temperature: `°C`;
- frequency/temperature/voltage histogram counters: accumulated `seconds`;
- Cdyn residency: accumulated `microseconds`;
- QAT average latency: `nanoseconds`;
- QAT PCIe traffic counters: accumulated `megabytes`, converted by `rate()` to
  `MB/s`;
- data-loss count: processing-cycle count;
- data-loss and last-update internal timestamps: 25 MHz crystal TSC ticks.

### 6.2 Derived display values / Dashboard派生值

- histogram percentages are each bucket's `rate()` divided by the sum of all
  bucket rates for the same selection;
- counter intensity uses `rate()` or `increase()`, never the historical absolute
  value alone;
- raw gauge movement uses a window `delta()` only for relative comparison;
- FIVR availability and two-bit slots are Receiver-derived fields from packed
  monitor words.

### 6.3 Raw means unresolved / Raw表示尚未证明

`Raw` does not mean useless. It means the current evidence does not support a
physical conversion. Raw values may be used for:

- controlled before/after comparisons;
- workload fingerprints on the same platform and firmware;
- anomaly features with provenance and quality masks;
- discovering whether a signal changes at all.

Raw values must not be relabelled as `%`, `W`, `J`, `GB/s` or another physical
unit without an approved formula and source.

## 7. Row and panel reference / 分区与Panel说明

### 7.1 Row 00 — Overview

The first row deliberately contains only four immediately readable results.
Collection internals, topology and provenance are moved to the final sections.

第一栏只保留四个可以直接理解的结果；采集技术细节、拓扑和provenance移到页面
末尾。

#### PMT Data

`Ready` means the selected path exposes PMT series and its newest sample is less
than 45 seconds old. It does not certify all hardware or every Aggregator.

#### Peak Core Temperature

The panel shows the maximum current valid core temperature. Disabled local
slots that report 0°C are excluded. No yellow/red temperature threshold is
applied in this dashboard.

#### C-Die FIVR

Operational convention:

- `Healthy`: C-Die monitor data is available and every exposed two-bit slot is
  zero;
- `Unhealthy`: at least one exposed slot is non-zero;
- `No Data`: the data cannot be interpreted.

This convention is not an official public FIVR codebook and is not a complete
server-health verdict.

#### QAT Activity

- `Active`: measured QAT inbound/outbound PCIe counter rate is non-zero;
- `Idle`: valid counters exist but no QAT traffic is observed;
- `No Data`: no matching QAT traffic series exists.

CPU-only NPB or PAMPAR workloads should be `Idle`.

### 7.2 Row 01 — Core Environment & Activity

- **Top 12 Core Temperatures** shows the hottest current valid Core fields.
- **Maximum Core Temperature Trend** shows one platform maximum over time.
- **PMT Relative Activity** applies `rate()` to the experimental U64.38.26
  counter, shows the highest per-Core rates and retains six decimals. It is not
  Linux CPU utilization percent.
- **Throttle Events · Last 5 Minutes** shows the five-minute increase for both
  64-cycle and 1024-cycle throttle families. A non-zero result does not identify
  thermal, power or voltage-regulator root cause.

Detailed per-Core residency remains available through Metric Explorer and the
metric-family reference instead of crowding the two Overview dashboards.

### 7.3 Overview Row 02 — Uncore, RDT & Memory

- **RDT Memory Transaction Rates · Raw** compares MBM total and local counter
  rates. The transaction size is unresolved, so the panel does not use bytes/s.
- **RDT Cache Occupancy Activity · Raw** shows CMT counter rates. RMID is a
  monitoring identity, not a process ID.
- **Memory Channel Counter Change · Raw** shows absolute five-minute deltas of
  fields named read/write bandwidth counters. No byte scaling is proven.
- **Enabled CHA Instances** is topology state, not cache utilization.

### 7.4 Overview Row 03 — Power Policy & FIVR

- **FIVR Operational Signals** displays the C-Die operational state, C-Die
  non-zero slot count and IO-Die availability.
- **C-Die Non-Zero Slot Locator** identifies Socket, Access, monitor and slot.
  It cannot identify a rail or physical core without a codebook.
- **Accumulated Energy Change · Raw** shows relative five-minute movement only.
  It is not joules and must not be divided into watts.
- **EPB & PEM Policy Fields · Raw** exposes current policy/status values for
  engineering correlation. Non-zero does not universally mean a fault.

`DEADBEEF` is a firmware data-unavailable sentinel. It is not a FIVR failure
code.

### 7.5 Overview Row 04 — Accelerator & I/O

- **QAT PCIe Throughput** uses the proven cumulative megabyte counters and
  displays inbound/outbound `MB/s`.
- **QAT Latency & Activity** only treats average-nanosecond gauges as meaningful
  when traffic is present. Activity counter rates remain raw/s.

When QAT is Idle, an average latency of 0 ns is not a valid performance result.

### 7.6 Overview Row 05 — Data Trust & Provenance

- **Data Freshness** separates a recently scraped pipeline from stale/no data.
- **Update Quality** derives Stable/Intermittent/Sustained from
  `agg_data_loss_count_total` and the internal update heartbeat. It is telemetry
  quality, not CPU hardware health or network packet loss.

- **Incomplete Aggregator Update Cycles** shows five-minute increases, grouped
  by source, Socket and Access.
- **Path Parity & Update Heartbeat** compares Redfish and local series coverage,
  internal timestamp changes and incomplete-cycle increases.

An old non-zero absolute count is not dangerous by itself. Escalate when growth
is sustained across multiple windows, affects required Aggregators, persists
after the workload ends, or is accompanied by a stalled update heartbeat.

### 7.7 Overview Row 06 — Technical Inventory & Topology

This final engineering section is intentionally outside the customer-first
reading flow:

- **Aggregator & Series Inventory** groups current series by
  Device/Access/Source/GUID/size. The value is series count, not event count.
- **Platform Identity & Firmware** displays raw static CPUID and firmware
  enumerations for provenance.
- **Enabled Topology Signals** lists enabled domain, UPI, DDR, core and CHA
  fields. EID, DomainId and AccessId are separate identifier spaces.

## 8. Prometheus type rules / Prometheus类型规则

### Gauge

A gauge is normally read directly. `delta()` is used only where the guide
explicitly states that a raw before/after comparison is intended.

### Counter

A counter is historical accumulation. Use:

```promql
rate(metric[5m])
increase(metric[5m])
```

Do not interpret a large absolute counter value as high current activity.

### Multi-name query safety

Prometheus removes `__name__` during many range functions. The generator first
copies the metric name into a normal `metric` label before applying
`timestamp()`, `rate()`, `delta()` or `increase()` across multiple names. This
prevents distinct metrics with otherwise identical labels from colliding.

## 9. Open Semantics Register / 未解决语义清单

These gaps are deliberately visible. A row may be closed only when an approved
source provides the missing definition and the Collector/Dashboard conversion
is tested.

| Family / area | Confirmed today / 当前可确认 | Missing evidence / 尚缺证据 | Dashboard restriction / 当前限制 |
|---|---|---|---|
| Relative usage | U64.38.26 cumulative relative level | Conversion to CPU utilization % | Six-decimal raw rate only |
| RDT MBM | Per-CHA/per-RMID local and total transactions | Transaction size; precise local-NUMA and workload mapping | Raw/s, never bytes/s |
| RDT CMT | Cache-line-usage counter activity | Cache-line-to-byte conversion; RMID owner map | Raw/s only |
| Memory BW counters | Read/write channel fields change with activity | Counter/gauge lifecycle, scaling and time base | Raw window delta |
| Energy accumulators | Accumulated core/FIVR fields with timestamps | Unit scale to joules and reset behavior | Raw delta; no W/J |
| C-state fields | Aggregate, per-core, die and package fields exist | Authoritative unit and cumulative-vs-current semantics for each field | Explorer/raw comparison only |
| FIVR monitor | Availability, packed words and 2-bit slots | Slot-to-rail/core map; official code 0–3 meanings | Project 0=Healthy convention; no root-cause claim |
| EPB | Core input and socket resolved policy values | Approved enumeration-to-policy text | Raw enumeration |
| PEM | PL1/PL2, thermal, VR, RAPL and related fields exist | Bit definitions, reset/window behavior and cross-source precedence | Raw status; no universal fault mapping |
| Mesh telemetry | GV and histogram-bin fields exist | Bin boundaries, unit and sampling semantics | Explorer/raw only |
| Data-loss count | Incomplete internal processing-cycle counter and event timestamp | Total internal-cycle denominator and per-cycle missing-field count | No loss percentage |
| Last-update timestamp | 25 MHz internal update timestamp | Calibrated mapping to wall-clock time | Use `changes()`, never display as date |
| Core identity | Redfish D/A/S or selected endpoint + Local telemN locates one access-path instance; XML defines Core N fields | Approved OOB↔Local physical-instance mapping and mapping from each Aggregator Core N field to Linux logical CPU and physical core IDs | Use compact `AGG[D/A/S]` or `AGG[telemN]`; no Linux CPU claim |
| Firmware version | Raw image version field exists | Encoding format and release-name mapping | Provenance raw value |
| QAT maximum latency | Maximum-latency fields exist | Reset/measurement-window semantics | Explorer only; never `rate(max)` |

Recommended follow-up evidence sources:

1. exact GNR XML HELP and transformation equations;
2. approved platform telemetry schema/codebook for the matching GUID and size;
3. firmware owner confirmation for update/reset behavior;
4. controlled workload validation with raw-word cross-check;
5. explicit versioning by CPU stepping and firmware image.

建议每个缺口完成时记录：证据文档版本、适用 GUID/size、CPU stepping、firmware
version、转换公式、验证 workload 和回归查询。

## 10. Metric Explorer / 全量指标搜索

The Overview intentionally does not expose a metric-name variable. Open:

```text
/d/pmt-gnr-metric-explorer
```

Use the Explorer to:

- search all 5,285 names;
- inspect full raw labels;
- view raw history;
- compare counter rate and gauge delta;
- locate a family in `pmt-metric-family-reference.md`;
- confirm unit and HELP in `pmt-metrics-catalog.csv`.

Only interpret the rate or delta that matches the metric's declared type and
family guidance.

## 11. Maintenance and verification / 维护与验证

Generate the independent Overview:

```bash
cd /root/projects/Intel-PMT
python3 tools/otel/generate_gnr_telemetry_overview.py
```

Required acceptance checks:

1. the legacy generator and `pmt-avc01-redfish` dashboard are unchanged;
2. Redfish and Local Overviews each have 7 rows and 25 content panels;
3. each Overview has only the endpoint filter and a fixed collection path;
4. header links switch between the two UIDs while preserving endpoint and time;
5. all 64 fixed-path PromQL targets parse successfully against Prometheus;
6. empty FIVR locator is valid when all slots are zero;
7. an empty QAT average-latency target is valid when QAT has no traffic; raw
   activity counters should still remain discoverable;
8. generated JSON is loaded under UIDs `pmt-gnr-redfish-overview`,
   `pmt-gnr-local-overview` and `pmt-gnr-metric-explorer`;
9. no panel labels raw values as `%`, `W`, `J` or `GB/s` without evidence;
10. the Open Semantics Register is updated when a codebook or conversion is
    resolved.

## 12. Related documents / 相关文档

- `pmt-platform-topology.md` — Socket, Access, Source, GUID and local-core labels;
- `pmt-metrics-summary.md` — beginner summary of all current metrics;
- `pmt-metric-family-reference.md` — detailed guidance for all 38 families;
- `pmt-metrics-catalog.csv` — all 5,285 names, HELP, types, units and caveats;
- `gnr-fivr-health-collection-workflow.md` — packed words, poison and FIVR limits;
- `complete-pmt-collection-workflow.md` — current end-to-end deployment;
- `pmt-telemetry-backend-reproduction.md` — backend reproduction and operations.
