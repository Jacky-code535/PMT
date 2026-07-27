# Intel PMT Telemetry Platform — Product Requirements Document

> **Intel Internal Only**
>
> Status: Current implementation baseline

## 1. Purpose

This document defines the product behavior of the implemented Intel Platform  
Monitoring Technology (PMT) telemetry platform. It describes what the platform  
collects, stores, and presents; how users navigate and interpret the current  
dashboards; and how completion is verified.

## 2. Product Summary

The product gives internal users one continuous path from platform telemetry to
an inspectable user interface:

```text
Intel PMT hardware telemetry
  → Redfish OOB or Linux PMT in-band collection
  → GUID-and-size-selected XML decoding
  → OpenTelemetry metrics
  → Prometheus time-series storage
  → Grafana Overview and Metric Explorer dashboards
```

Two independent collection paths are supported:

1. **OOB / Redfish** reads PMT snapshots through the BMC.
2. **In-band / Local** reads Linux `intel_pmt` sysfs telemetry devices.

Both paths use the same metric naming and provenance model where the underlying
schema permits it. 

## 3. Product Goals

The implemented product shall:

1. collect PMT telemetry from Redfish and Local access paths;
2. identify each telemetry layout by exact `GUID + Size`;
3. decode binary samples using version-controlled Intel XML metadata;
4. preserve metric type, HELP text, unit, collection path, layout, and instance
  provenance;
5. store queryable time-series data in Prometheus;
6. provide readable Redfish and Local Overview dashboards;
7. provide full-name discovery for all exposed PMT metrics;
8. distinguish measured facts from unresolved units or codebooks;
9. expose collection freshness and internal Aggregator update quality;
10. provide repeatable generation and automated verification of dashboard
  artifacts.



## 4. Users and Primary Use Cases



### 4.1 Engineering viewer

An engineering viewer needs to:

- determine whether PMT data is available;
- inspect current temperatures, FIVR state, QAT activity, memory-related
counters, and update quality;
- select an exact path-local Core field;
- compare recent behavior with a chosen time range;
- understand a panel's unit and interpretation boundary.



### 4.2 Telemetry developer

A telemetry developer needs to:

- search all metric names and labels;
- inspect raw history and declared metric type;
- trace a metric to its PMT GUID, size, access path, and XML definition;
- verify whether a PromQL transformation is valid for the metric semantics;
- regenerate dashboards and catalogs after an approved implementation change.



### 4.3 Platform validation engineer

A validation engineer needs to:

- compare Redfish and Local coverage;
- confirm the internal update heartbeat advances;
- identify Aggregators with increasing incomplete-update counts;
- preserve platform and firmware provenance for a test interval.



### 4.4 Operator

An operator needs to:

- determine whether collection, storage, or presentation is stale;
- isolate a failure to source access, decoding, Collector export, Prometheus
storage, or Grafana query;
- restart or inspect the appropriate logical service without changing metric
semantics.



## 5. Product Assets and Systems of Record


| Information                              | Current system of record                                  |
| ---------------------------------------- | --------------------------------------------------------- |
| Time-series samples                      | Prometheus TSDB                                           |
| PMT field layout and transformations     | Intel PMT XML selected by `GUID + Size`                   |
| Collector behavior                       | `tools/otel/intelpmtreceiver/`                            |
| Collector deployment configuration       | `tools/otel/configs/`                                     |
| Overview and Explorer definitions        | Generated Grafana JSON in `tools/otel/dashboards/`        |
| Metric family semantics                  | `tools/otel/pmt_metric_guides.py` and generated reference |
| Exact metric-name catalog                | `docs/pmt-metrics-catalog.csv`                            |
| Platform topology evidence               | `docs/pmt-platform-topology.md`                           |
| Known semantic and physical-mapping gaps | `docs/pmt-unresolved-work.md`                             |


XML, configuration, dashboard JSON, and catalog files are version-controlled
assets. They are not records in Prometheus and are not a substitute for a
relational metadata database.

## 6. Functional Requirements



### FR-01 — Dual-path collection

The product shall collect PMT telemetry through both supported access paths.

- Redfish collection shall trigger and retrieve the configured BMC PMT
telemetry snapshot.
- Local collection shall enumerate `telem*` devices under the configured Linux
PMT sysfs path.
- Each path shall run as an independent Collector pipeline.
- A failure on one configured endpoint or Aggregator shall not prevent valid
Aggregators on the same cycle from being exported.
- The current configured collection interval is 20 seconds.



### FR-02 — Aggregator discovery and identity

For every discovered Aggregator, the product shall retain:

- logical platform endpoint;
- collection mode;
- access-path locator;
- PMT GUID;
- PMT payload size;
- collection timestamp;
- source attributes returned by Redfish or discovered from sysfs.

Redfish shall preserve `DeviceId`, `AccessId`, and `SourceId`. Local collection
shall preserve the `telemN` device and sysfs telemetry path. These locators shall
not be presented as a cross-path physical mapping.

### FR-03 — Schema selection

The product shall select a decode schema using both PMT GUID and payload size.

- GUID-only matching is insufficient.
- An Aggregator with no exact supported schema shall be skipped and logged.
- XML common types, Aggregator layout, and Aggregator interface definitions
shall be loaded from the selected schema set.
- Repeated schema files shall be cached within the Collector process.



### FR-04 — Decode and transform

The product shall:

- decode the binary payload according to XML offsets and widths;
- evaluate the XML transformation referenced by each sample;
- retain XML HELP text and declared unit;
- export numeric values supported by the OpenTelemetry number data model;
- expose XML `Counter` samples as cumulative monotonic sums;
- expose other supported samples as gauges;
- skip a field when required transform inputs are missing or evaluation fails.

The product shall not apply an additional Dashboard scale when the XML
transformation has already been evaluated by the Collector.

### FR-05 — Metric normalization and provenance

Exported metric names shall be lowercase. Every exported series shall retain
enough labels to identify its logical endpoint, collection path, schema, and
path-local Aggregator instance.

The common labels are:

- `PMTEndpoint`;
- `CollectionMode`;
- `PMTGuid`;
- `PMTSizeBytes`;
- `DeviceId`;
- `AccessId`;
- `SourceId`;
- `DeviceType`;
- `AccessType`;
- `SourceType`.

Path-specific labels such as `RedfishEndpoint`, `device`, `hostname`, and
`telem` may also be present. Metric names shall not be used as physical Core or
Socket identity without an approved mapping.

### FR-06 — Prometheus storage and query

The product shall expose Collector metrics through a Prometheus exporter and
shall configure Prometheus to scrape them.

Prometheus shall provide:

- current and historical samples;
- label-based filtering;
- range functions appropriate to metric type;
- metadata used by the metric catalog;
- a datasource consumed by Grafana.

Retention and capacity are deployment policies rather than fixed product
constants. The product shall not claim persistence beyond the configured
Prometheus retention policy.

### FR-07 — Dashboard set and navigation

The formal current UI consists of:

1. `Intel PMT · GNR OOB (Redfish) Overview · Internal`;
2. `Intel PMT · GNR In-band (Local) Overview · Internal`;
3. `Intel PMT · GNR Metric Explorer · Internal`.

Each Overview shall place three navigation cards in one top row:

- open the other Overview;
- open Metric Explorer;
- open Dashboard Guide.

The path-switch link shall preserve the endpoint and visible time range.

### FR-08 — Path-specific filters

The Redfish Overview shall provide:

- Platform endpoint;
- OOB Device;
- OOB Access;
- OOB Source;
- XML Core field.

The Local Overview shall provide:

- Platform endpoint;
- Local Telemetry device;
- XML Core field.

Redfish and Local Core selectors shall not share one inferred physical-core
selector. A Core number identifies a field in the selected Aggregator XML
layout, not a Linux CPU number.

### FR-09 — Overview panel inventory

Each Overview shall contain the same 25 metric panels organized into seven
telemetry rows. Queries are fixed to the Dashboard's collection path.

#### Row 00 — Path overview


| Panel                 | Required display                                                                      | Unit and interpretation                                      |
| --------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| PMT Data              | Current data availability and series presence                                         | Status, not a hardware-health verdict                        |
| Peak Core Temperature | Highest current valid Core temperature                                                | °C; zero-value disabled slots excluded                       |
| C-Die FIVR            | Project operational convention for C-Die monitor availability and exposed slot values | Healthy / Unhealthy / No Data; not an official FIVR codebook |
| QAT Activity          | Whether proven QAT PCIe counters are changing                                         | Active / Idle / No Data                                      |




#### Row 01 — Core environment and activity


| Panel                                         | Required display                                                                            | Unit and interpretation                                          |
| --------------------------------------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Top 12 Core Temperatures                      | Current hottest valid Core fields with Aggregator locator                                   | °C                                                               |
| Temperature for selected Core                 | Time history for the exact path-local Aggregator and XML Core field                         | °C                                                               |
| Core Usage · 5-Minute Increase                | Top and selected five-minute increases of the transformed experimental `core_usage` counter | Transformed raw `core_usage` amount; not CPU utilization %       |
| Core PVP Throttle Counter · 5-Minute Increase | Five-minute increases for 64-cycle and 1024-cycle detection counters                        | Raw count increase; cycle value identifies the hardware detector |




#### Row 02 — Uncore, RDT, and memory


| Panel                                           | Required display                                                          | Unit and interpretation                 |
| ----------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------- |
| RDT MBM Memory Transactions · 5-Minute Increase | Total and local five-minute transaction-counter increases by CHA and RMID | Raw transaction amount; not bytes       |
| RDT CMT LLC Cache Line Usage · Raw              | Current LLC cache-line-usage value by CHA and RMID                        | Raw value; RMID is not a process ID     |
| Memory Channel Counter Change · Raw             | Five-minute change in named read/write channel fields                     | Raw change; no unproven byte conversion |
| Enabled CHA Instances                           | Count of enabled CHA topology fields                                      | Instance count, not cache utilization   |




#### Row 03 — Power policy and FIVR


| Panel                           | Required display                                          | Unit and interpretation                               |
| ------------------------------- | --------------------------------------------------------- | ----------------------------------------------------- |
| FIVR Operational Signals        | C-Die state, non-zero slot count, and IO-Die availability | Project convention and availability                   |
| C-Die Non-Zero Slot Locator     | Locator for current non-zero monitor slots                | Raw slot/code; no inferred rail or Core name          |
| Accumulated Energy Change · Raw | Five-minute movement in accumulated-energy fields         | Raw change; not joules or watts                       |
| EPB & PEM Policy Fields · Raw   | Current policy and monitor values                         | Raw enumerations; non-zero is not universally a fault |




#### Row 04 — Accelerator and I/O


| Panel                  | Required display                                                    | Unit and interpretation                                   |
| ---------------------- | ------------------------------------------------------------------- | --------------------------------------------------------- |
| QAT PCIe Throughput    | Inbound and outbound rate from cumulative megabyte counters         | MB/s                                                      |
| QAT Latency & Activity | Average latency only when QAT traffic is present, plus raw activity | ns for proven latency gauges; raw/s for unscaled activity |


When QAT has no traffic, throughput shall show an Idle state and average
latency shall not present `0 ns` as a valid performance measurement.

#### Row 05 — Data trust and provenance


| Panel                               | Required display                                                                                    | Unit and interpretation                          |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Data Freshness                      | Age of the newest matching series                                                                   | Seconds and state                                |
| Update Quality                      | Stable / Intermittent / Sustained classification from incomplete-update growth and update heartbeat | Telemetry quality, not CPU health or packet loss |
| Incomplete Aggregator Update Cycles | Five-minute counter increases grouped by source and Aggregator locator                              | Incomplete internal processing cycles            |
| Path Parity & Update Heartbeat      | Cross-path series coverage, heartbeat movement, and incomplete-cycle movement                       | Comparative engineering signals                  |




#### Row 06 — Technical inventory and topology


| Panel                         | Required display                                | Unit and interpretation |
| ----------------------------- | ----------------------------------------------- | ----------------------- |
| Aggregator & Series Inventory | Series count grouped by locator, GUID, and size | Series count            |
| Platform Identity & Firmware  | Current raw identity and firmware fields        | Raw provenance values   |
| Enabled Topology Signals      | Enabled domain, UPI, DDR, Core, and CHA fields  | Raw topology state      |




### FR-10 — Metric Explorer

Metric Explorer shall allow an engineering user to:

- select endpoint and collection path;
- search or select an exact metric name;
- inspect current value and raw labels;
- inspect raw history;
- compare a counter rate or gauge delta when appropriate;
- return to the Redfish Overview.

The Explorer shall expose all currently cataloged PMT metric names. The current
catalog contains 5,285 exact names grouped into 38 semantic families. Availability
of a name does not imply that every platform instance emits a non-zero value.
The current observed inventory is 32,710 series per collection path and 65,420
across both paths. These counts are a platform/firmware/XML baseline, not fixed
product limits.

### FR-11 — Metric catalog and guidance

The product shall generate:

- a searchable CSV row for every exact metric name;
- an introductory metric summary;
- a family-level reference;
- HELP, type, unit source, recommended query, caveat, and observed-label
information where available.

An unspecified unit shall remain unspecified. A name containing words such as
`energy`, `bandwidth`, or `usage` shall not by itself authorize a physical unit.

### FR-12 — Data-quality behavior

The UI shall distinguish:

- no matching series;
- stale series;
- valid zero or Idle state;
- increasing incomplete-update count;
- stalled internal update heartbeat.

`agg_data_loss_count_total` shall be described as incomplete internal
Aggregator processing cycles. It shall not be described as network packet loss,
percentage data loss, or a count of individual missing fields.

### FR-13 — Generated artifact ownership

The two Overview JSON files and Metric Explorer JSON shall be generated from
`tools/otel/generate_gnr_telemetry_overview.py`.

- Generated JSON shall not be maintained manually.
- Generator changes shall regenerate repository and provisioned copies.
- The legacy Dashboard and generator shall remain independent.
- Semantic changes shall update the guide, family guidance, and tests.



## 7. User-Experience Requirements



### 7.1 Information hierarchy

The initial screen shall answer, in order:

1. Is PMT data present?
2. Are key thermal, FIVR, and QAT signals available?
3. Which Core fields are hottest or changing?
4. What do memory, power-policy, and accelerator signals show?
5. Is the telemetry current and internally updating?
6. What exact Aggregators and topology fields produced the data?

Technical inventory shall remain below operationally useful content.

The current dashboards shall default to a 30-minute visible range and a
20-second refresh. Refresh controls query presentation; it does not change the
20-second PMT source collection cadence or recover transients between snapshots.

### 7.2 Labels

Labels shall use terms supported by XML or the access-path model.

- Redfish locator: `AGG[D<device>/A<access>/S<source>]`.
- Local locator: `AGG[telemN]`.
- Core field: `Core N`.
- RDT identity: `CHA N · RMID N`.

The UI shall avoid invented Socket, physical Core, rail, workload, or Linux CPU
identity where no approved mapping exists.

### 7.3 Time-window wording

Panel titles shall state when they display a fixed five-minute increase.
Hardware windows such as 64-cycle and 1024-cycle throttle detectors shall be
identified separately from the Dashboard analysis window.

### 7.4 Units

The UI shall:

- use °C for proven temperature fields;
- use MB/s only for proven cumulative-megabyte QAT counters after rate
calculation;
- use ns only for latency gauges declared in nanoseconds;
- use raw or no physical unit when scale evidence is absent;
- avoid `%`, W, J, bytes/s, or GB/s without an approved conversion.



### 7.5 Empty and invalid states

Panels shall use explicit states such as `No Data`, `Idle`, `Unavailable`, or
`Unsupported` where a numeric zero would mislead. Firmware sentinel values such
as `DEADBEEF` shall be handled as unavailable data, not interpreted as a valid
health code.

## 8. Non-Functional Requirements



### NFR-01 — Maintainability

- One generator shall own the new Overview and Explorer JSON.
- One family-guide source shall own generated catalog semantics.
- Exact schema selection and transformations shall remain data-driven by XML.
- Generated artifacts shall be reproducible from version-controlled sources.



### NFR-02 — Reliability

- Collector startup shall fail when required metadata cannot be initialized.
- A malformed or unsupported Aggregator shall be logged and skipped without
discarding valid Aggregators.
- Collection shall start immediately and continue on the configured interval.
- Shutdown shall cancel collection and close idle HTTP connections.



### NFR-03 — Observability

- Collector logs shall expose discovery, schema, transform, scrape-duration,
metric-count, and downstream-consumption failures.
- Prometheus target state and query results shall distinguish export failure
from Grafana presentation failure.
- Data Freshness and update-heartbeat panels shall expose stale pipelines.



### NFR-04 — Security

- BMC credentials shall be supplied through environment or secret management,
never committed in configuration.
- Dashboards shall not expose credentials.
- Viewer access shall be read-only.
- Deployment-specific transport exceptions shall be documented and reviewed by
the deployment owner.



### NFR-05 — Performance and cardinality

- XML metadata shall be cached by schema base directory.
- Dashboard Overview queries shall use bounded `topk` results where the complete
set would impair readability.
- Full-cardinality investigation shall be delegated to Metric Explorer and the
generated catalog.
- A deployment shall capacity-plan Prometheus for its observed series count,
scrape interval, and retention.



### NFR-06 — Portability

The logical design shall not depend on one server address. Deployment-specific
hostnames, credentials, and service locations shall be configuration values.
Platform support still depends on compatible PMT discovery and an exact XML
schema for every required `GUID + Size`.

## 9. Acceptance Criteria


| ID    | Acceptance check                         | Expected evidence                                                                                              |
| ----- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| AC-01 | Both collection modes produce PMT series | Prometheus query returns `CollectionMode="redfish"` and `"local"`                                              |
| AC-02 | Exact schemas are used                   | Every exported Aggregator carries known `PMTGuid` and `PMTSizeBytes`; unsupported pairs are logged and skipped |
| AC-03 | Current platform discovery is complete   | Expected Aggregator inventory is present for each configured path                                              |
| AC-04 | Overview structure is stable             | Each Overview contains 7 telemetry rows, 25 metric panels, and 3 top navigation cards                          |
| AC-05 | Core selectors are path-correct          | Redfish has Device/Access/Source/Core; Local has Telemetry/Core                                                |
| AC-06 | PromQL is valid                          | All fixed-path Overview targets parse successfully against Prometheus                                          |
| AC-07 | Counter semantics are protected          | Core usage, MBM, and throttle panels use the documented five-minute increase; CMT uses current raw value       |
| AC-08 | Physical units are evidence-based        | Raw panels do not claim %, W, J, bytes/s, or GB/s without approved conversion                                  |
| AC-09 | QAT Idle is not misleading               | No-traffic state does not display valid-looking `0 ns` average latency                                         |
| AC-10 | Data quality is visible                  | Freshness, incomplete-cycle movement, and heartbeat are independently inspectable                              |
| AC-11 | Explorer covers the catalog              | Every generated exact metric name can be selected or searched                                                  |
| AC-12 | Artifacts are reproducible               | Generator and catalog commands complete without manual JSON edits                                              |
| AC-13 | Regression tests pass                    | Dashboard and metric-guide unit tests complete successfully                                                    |
| AC-14 | Legacy UI is isolated                    | Legacy Dashboard UID and generated file remain unchanged by new generator tests                                |




## 10. Future Scope

Possible future work, not committed by this PRD, includes:

- a reviewed physical identity model joining OOB, Local, PCI, and topology;
- approved unit and codebook registration;
- a versioned telemetry-definition service;
- a relational metadata store;
- controlled onboarding and preview of new platform schemas;
- customer-specific dashboards built from approved semantic definitions.

