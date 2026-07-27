# Intel PMT Telemetry Platform — Low-Level Design

> **Intel Internal Only**
>
> Status: Current implementation baseline

## 1. Purpose

This document defines the implemented software interfaces and processing rules
of the Intel PMT telemetry platform. It follows one sample from source discovery
through XML decoding, OpenTelemetry construction, Prometheus storage, and
Grafana presentation.

It provides enough detail for a team with no prior knowledge of the system to
understand and reproduce the current implementation.

## 2. Source Layout

The primary implementation files are:

```text
tools/otel/
├── intelpmtreceiver/
│   ├── aggregator.go
│   ├── common_processor.go
│   ├── config.go
│   ├── constants.go
│   ├── factory.go
│   ├── local_aggregator.go
│   ├── receiver.go
│   ├── redfish_aggregator.go
│   └── xml-parser.go
├── configs/
│   ├── config-avc01-pmt-redfish.yaml
│   └── config-avc01-pmt-local.yaml
├── generate_gnr_telemetry_overview.py
├── test_gnr_telemetry_overview.py
├── pmt_metric_guides.py
├── export_pmt_metric_catalog.py
└── dashboards/
    ├── pmt-gnr-redfish-overview.json
    ├── pmt-gnr-local-overview.json
    └── pmt-gnr-metric-explorer.json
```

The logical implementation layers are:

```text
transport discovery
  → XML lookup and cache
  → binary extraction
  → transformation evaluation
  → MetricValue model
  → OpenTelemetry pdata
  → Prometheus exposition and storage
  → generated Grafana PromQL
```

`intelpmtreceiver` is a separate Go module targeting Go 1.24.4. Its direct
OpenTelemetry dependencies are not textually the same versions as every
component in the generated Collector Builder output; a release build must
therefore validate the resolved module graph rather than assuming version
compatibility from the YAML manifests alone.

## 3. Receiver Component Contract



### 3.1 Factory

`NewFactory()` registers an OpenTelemetry receiver with component type:

```text
intelpmtreceiver
```

The receiver:

- supports metrics only;
- is marked Alpha stability;
- has a default five-second interval;
- receives an OpenTelemetry `consumer.Metrics`;
- creates one receiver-local HTTP client cache and one XML cache.



### 3.2 Configuration model

The implemented Go configuration is:

```go
type RedfishEndpointConfig struct {
    confighttp.ClientConfig `mapstructure:",squash"`
    TriggerAction    string `mapstructure:"trigger_action"`
    TriggerParameter string `mapstructure:"trigger_param"`
}

type Config struct {
    Interval     string
    Metadata     string
    Mode         string
    Path         string
    RemoteConfig map[string]RedfishEndpointConfig
}
```

YAML keys are:


| Key              | Required                        | Meaning                                                               |
| ---------------- | ------------------------------- | --------------------------------------------------------------------- |
| `interval`       | Yes in production configuration | Receiver collection interval                                          |
| `metadata`       | Yes                             | Root PMT metadata XML path                                            |
| `mode`           | Yes                             | `redfish` or `local`                                                  |
| `path`           | Local only                      | Linux PMT sysfs root; defaults to `/sys/class/intel_pmt` when empty   |
| `endpoints`      | Redfish only                    | Map of logical endpoint label to HTTP client and action configuration |
| `endpoint`       | Redfish endpoint entry          | PMT snapshot URL                                                      |
| `trigger_action` | Optional                        | URL invoked before snapshot GET                                       |
| `trigger_param`  | Optional                        | JSON object encoded as a YAML string                                  |
| `headers`        | Deployment-specific             | HTTP headers such as runtime-injected authorization                   |
| `tls`            | Deployment-specific             | HTTP TLS client policy                                                |


Validation rules:

1. interval must parse to at least five seconds;
2. mode must be exactly `local` or `redfish`;
3. empty Local path is replaced by the default sysfs root.

The current production configurations use a 20-second interval.

Current validation limitations:

- the first interval parse error is discarded, so malformed text can initially
produce the same message as an interval below five seconds;
- metadata presence is checked at receiver startup, not in `Validate()`;
- Redfish endpoint count, URL syntax, and trigger settings are not validated by
`Config.Validate()`.



### 3.3 Receiver lifecycle

`Start()` executes:

```text
load root metadata
  → build GUID/size lookup
  → create cancellable context
  → launch scrape goroutine
  → scrape immediately
  → scrape on every ticker interval
```

`Shutdown()`:

- cancels the receiver context;
- stops future scrape cycles through the goroutine select;
- closes idle connections for every cached Redfish HTTP client.

There is no source-sample replay queue. A failed collection cycle creates a
time-series gap.

### 3.4 Runtime receiver state

The receiver maintains:

```go
type intelpmtreceiver struct {
    host        component.Host
    cancel      context.CancelFunc
    ctx         context.Context
    logger      *zap.Logger
    consumer    consumer.Metrics
    config      *Config
    httpClients map[string]*http.Client
    cache       *pmtCache
    lookupMap   PMTLookupMap
}
```

`httpClients` is keyed by configured Redfish endpoint label. `lookupMap` is
immutable after initialization. XML cache entries are populated on first use.

## 4. Transport-Neutral Aggregator Interface

Both transport implementations satisfy:

```go
type MetricAggregator interface {
    Process(logger *zap.Logger) map[string]MetricValue
    GetAttributes() map[string]interface{}
    GetCollectionTimestamp() (uint64, error)
}
```

The common processed value is:

```go
type MetricValue struct {
    Name        string
    Type        string
    Value       interface{}
    Description string
    Unit        string
}
```

Transport-specific structs carry source data plus the selected XML set:

```go
type RedfishMetricAggregator struct {
    GUID                string
    CollectionTimestamp string
    Size                uint64
    Attributes          map[string]interface{}
    Data                string
    XMLSet              XMLSet
    Common              DataTypes
    DataTypeMap         map[string]DataType
    Aggregator          Aggregator
    AggregatorInterface AggregatorInterface
}

type LocalMetricAggregator struct {
    GUID                string
    CollectionTimestamp string
    Size                uint64
    Path                string
    Attributes          map[string]interface{}
    Data                string
    XMLSet              XMLSet
    Common              DataTypes
    DataTypeMap         map[string]DataType
    Aggregator          Aggregator
    AggregatorInterface AggregatorInterface
}
```

Both `Process()` methods call the same `processAggregatorData()` function.

## 5. Redfish Source Interface



### 5.1 Input contract

The receiver expects the configured snapshot GET response to decode as:

```go
type RedfishTelemetryData struct {
    TelemetryData []RedfishMetricAggregator `json:"TelemetryData"`
}
```

Each entry uses the JSON fields:


| JSON field            | Go field              | Requirement                             |
| --------------------- | --------------------- | --------------------------------------- |
| `Guid`                | `GUID`                | Layout GUID; normalized to lowercase    |
| `CollectionTimestamp` | `CollectionTimestamp` | Base-10 unsigned seconds                |
| `Size`                | `Size`                | Binary payload size in bytes            |
| `attributes`          | `Attributes`          | Redfish locator and provider attributes |
| `Data`                | `Data`                | Base64 telemetry payload                |




### 5.2 Collection action

If `trigger_action` is configured, the receiver sends:

```http
POST <trigger_action>
Content-Type: application/json
```

The body is:

- the JSON object from `trigger_param`, when provided and valid; or
- the receiver's default bulk telemetry snapshot request when no parameter is
configured.

Any non-2xx response fails discovery for that endpoint and cycle.

The receiver performs the snapshot GET immediately after a successful POST. It
does not poll action completion or apply a trigger-to-GET delay.

### 5.3 Snapshot GET

After a successful action, or immediately when no action is configured, the
receiver sends:

```http
GET <endpoint>
```

Requirements:

- the configured OpenTelemetry HTTP client applies headers and TLS settings;
- response status must be 2xx;
- the body must be valid `RedfishTelemetryData` JSON.



### 5.4 Redfish discovery output

The receiver creates an internal map entry `telem<index>` for each returned
array element. That index is an internal enumeration key, not the external
physical Aggregator identity.

The receiver does not enumerate MCTP endpoints and does not traverse a Redfish
Entries collection. It calls the configured trigger and snapshot URLs and
treats the returned `TelemetryData[]` as the current Aggregator set.

Before export, Redfish attributes include:


| Label             | Value source                                |
| ----------------- | ------------------------------------------- |
| `RedfishEndpoint` | Configured endpoint label                   |
| `PMTEndpoint`     | Configured endpoint label                   |
| `CollectionMode`  | Literal `redfish`                           |
| `PMTGuid`         | Entry GUID                                  |
| `PMTSizeBytes`    | Entry size                                  |
| `DeviceId`        | Redfish entry attribute                     |
| `AccessId`        | Redfish entry attribute                     |
| `SourceId`        | Redfish entry attribute                     |
| Other attributes  | String or `int64` values from Redfish entry |


Redfish entry attributes are copied as `int64` when already typed as `int64`;
other values are converted with formatted string representation.

### 5.5 Error behavior

The following errors fail only the configured endpoint's current discovery:

- HTTP client construction;
- trigger JSON parsing;
- trigger request construction or transport;
- trigger non-2xx status;
- GET request construction or transport;
- GET non-2xx status;
- body read;
- JSON decode.

Other configured Redfish endpoints continue independently.

The current JSON decode error includes the complete response body. Operators
shall treat that log content as potentially large or sensitive.

## 6. Local sysfs Source Interface



### 6.1 Discovery root

The receiver enumerates the configured path and considers only directory
entries whose names begin with:

```text
telem
```



### 6.2 Required files

For each `telemN`, the receiver reads:

```text
<root>/telemN/guid
<root>/telemN/size
<root>/telemN/telem
```

The entry is skipped when any required file cannot be read.

### 6.3 GUID parsing

The GUID file contract is:

- non-empty text;
- optional trailing newline;
- required `0x` prefix;
- hexadecimal content parseable as unsigned 64-bit;
- normalized output formatted as lowercase `0x%08x`.

Malformed GUID entries are skipped.

### 6.4 Size parsing

The size file is trimmed of one trailing newline and parsed with base
autodetection as an unsigned 64-bit integer. Malformed sizes are skipped.

### 6.5 Payload handling

The `telem` file is read as binary. The Local adapter Base64-encodes it so that
both transports enter the common processor through the same string payload
contract.

### 6.6 Collection timestamp

Local collection uses the current host Unix time in seconds immediately before
reading the device files. This is a Collector read timestamp, not a hardware
internal Aggregator timestamp.

### 6.7 Local attributes

The Local adapter exports:


| Label            | Value                          |
| ---------------- | ------------------------------ |
| `telem`          | Full sysfs telemetry file path |
| `device`         | `telemN`                       |
| `CollectionMode` | Literal `local`                |
| `PMTGuid`        | Normalized sysfs GUID          |
| `PMTSizeBytes`   | Parsed sysfs size              |
| `PMTEndpoint`    | Hostname                       |
| `DeviceId`       | Hostname                       |
| `AccessId`       | `telemN`                       |
| `DeviceType`     | `LocalPMT`                     |
| `AccessType`     | `sysfs`                        |
| `SourceId`       | Literal `0`                    |
| `SourceType`     | `Aggregator`                   |
| `hostname`       | Hostname                       |


These labels provide a consistent query surface but do not make Local
`DeviceId/AccessId/SourceId` physically equivalent to Redfish labels.

### 6.8 Error behavior

Failure to read the sysfs root returns an empty Local discovery result for the
cycle. Failure within one `telemN` skips that entry and continues.
Individual Local-device failures are currently skipped without a per-device
warning from `discoverLocalAggregator()`.

## 7. Metadata and XML Interfaces



### 7.1 Root metadata model

The root metadata XML maps layouts to XML sets:

```go
type PMTMapping struct {
    GUID        string
    Size        string
    LastUpdated DateOnly
    Status      string
    Description string
    XMLSet      XMLSet
}

type XMLSet struct {
    Basedir             string
    Common              string
    Aggregator          string
    AggregatorInterface string
}
```

The lookup key is:

```go
type PMTAggKey struct {
    GUID string
    Size uint64
}
```



### 7.2 Metadata initialization

`initPMT()` requires the configured metadata file to exist. It parses the XML,
records the metadata file's absolute parent directory, then calls
`BuildLookupMap()`.

`BuildLookupMap()`:

1. rejects metadata with no mappings;
2. trims and lowercases each GUID;
3. requires a `0x`-prefixed hexadecimal GUID;
4. parses decimal size;
5. rejects duplicate `GUID + Size` keys after logging a warning;
6. resolves the XML-set base directory relative to the root metadata file.

Invalid individual mappings are skipped. Initialization succeeds when the
resulting operation does not return an error; required platform coverage must
therefore be validated separately.

The current GNR PUNIT production mappings are supplied through a separately
installed Intel PMT metadata tree. The older repository-root `xml/pmt.xml`
contains incompatible PUNIT payload sizes for the current firmware and shall
not be used to decode those production Aggregators.

### 7.3 Exact lookup

The only normal lookup API is:

```go
FindXMLSetForGUIDSize(lookupMap, guid, size)
```

It returns an error when:

- the map is nil; or
- the exact pair is absent.

No GUID-only fallback is used by the production receiver path.

### 7.4 Common datatype XML

The common XML defines:

```go
type DataType struct {
    Name       string
    DataTypeID string
    DataClass  string
    Unit       Unit
    Enums      []Enum
}
```

The receiver builds a `DataTypeMap` keyed by datatype name. The exported unit is
the XML unit `name`; an absent definition produces an empty unit.
XML enums are parsed into the model but are not converted into textual metric
values by the current decode path.

### 7.5 Aggregator layout XML

The Aggregator layout contains sample groups and bit fields:

```go
type SampleGroup struct {
    SampleID uint64
    Sample   []Sample
}

type Sample struct {
    SampleName    string
    DatatypeIDRef string
    SampleID      string
    SubGroup      string
    SampleType    string
    Lsb           uint64
    Msb           uint64
}
```

During parsing:

```text
byte offset = SampleGroup.SampleID × 8
mask        = bits [lsb, msb]
```

The implementation assumes one 64-bit little-endian container per sample-group
ID.

### 7.6 Aggregator interface XML

The interface XML defines:

- transformations keyed by `transformID`;
- exported Aggregator samples;
- sample description;
- sample type;
- datatype reference;
- transform input variable to raw sample ID references;
- transformation reference.

The parser removes `$` from equations, unescapes XML entities, resolves each
sample's transform reference, and stores the resulting formula in
`TransformFormula`.

### 7.7 XML cache

The receiver caches three parsed objects by XML base directory:

```go
type pmtCache struct {
    commonCache              map[string]DataTypes
    aggregatorCache          map[string]Aggregator
    aggregatorInterfaceCache map[string]AggregatorInterface
}
```

The cache lasts for the process lifetime. XML changes require Collector restart
to guarantee reload.

Cache identity is the XML base directory, not the three individual filenames.
Mappings that share one base directory are therefore expected to reference the
same common, Aggregator, and interface files.

## 8. Binary Decode Algorithm



### 8.1 Common input

`processAggregatorData()` receives:

```text
Base64 payload
Aggregator layout
Aggregator interface
datatype map
logger
```

It returns:

```text
map[metric-name]MetricValue
```



### 8.2 Base64 decode

The payload is decoded with standard Base64. Failure returns an empty metric
map for that Aggregator.

### 8.3 Raw field extraction

For each XML sample:

1. verify that `CalculatedByteOffset + 8` is within the payload;
2. read an unsigned 64-bit little-endian container;
3. apply `CalculatedMask`;
4. right-shift by `lsb`;
5. store by XML `sampleID`.

Formula:

```text
raw_sample = (little_endian_u64(container) & mask) >> lsb
```

If the payload is too short, a warning includes sample ID, actual length, and
required offset.

### 8.4 Reserved fields

Aggregator-interface samples whose names contain `RESERVED` or `RSVD` are not
exported.

### 8.5 Transform input resolution

For each non-reserved interface sample:

1. create a parameter map;
2. resolve every `sampleIDREF` from extracted raw values;
3. bind it to the XML `varName`;
4. skip the sample if any input is missing.



### 8.6 Expression evaluation

The transformation evaluator:

- rejects an empty equation;
- removes only a full-width unsigned 64-bit identity mask before evaluation;
- converts hexadecimal literals to decimal because the expression engine does
not support hexadecimal syntax;
- evaluates the expression with `gval`;
- returns evaluation errors to the caller, which logs and skips the sample.

Narrower masks are retained because they may change the value.

Example for Core usage:

```text
XML: (parameter_0 & 0xffffffffffffffff) / (2**26)
Evaluator normalization: parameter_0 / (2**26)
Exported value: transformed cumulative core_usage
```

The Dashboard must not divide the exported value by `2^26` again.

### 8.7 Metric naming before OTel export

Default gauge name:

```text
<sampleGroup>.<sampleName>
```

Counter name:

```text
<sampleName>
```

Array notation is normalized:

```text
"[" → "."
"]" → ""
```

The final OpenTelemetry metric name is lowercased. Prometheus exporter
normalization subsequently produces the exposed Prometheus-compatible name and
the `_total` suffix for cumulative sums where applicable.

Processed values are held in a map keyed by generated metric name. If two XML
samples generate the same name, the later value overwrites the earlier value.

### 8.8 Metric type

When XML interface `SampleType` is exactly `Counter`:

```text
MetricValue.Type = "counter"
```

All other values are emitted as:

```text
MetricValue.Type = "gauge"
```

Metric-family guidance may still be necessary where XML acquisition wording,
HELP text, exported type, and observed lifecycle require engineering review.

## 9. FIVR Post-Processing

After normal XML sample processing, `expandFIVRHealthMetrics()` examines names
containing `FIVR_HEALTH_MONITOR`.

### 9.1 Availability

For each supported unsigned 64-bit packed word:

```text
<raw-name>.available = 1
```

When the value is a known poison:

```text
0xDEADBEEF
0xDEADBEEFDEADBEEF
```

the raw word is removed and:

```text
<raw-name>.available = 0
```

No status slots are emitted for poisoned data.

### 9.2 Slot expansion

For an available packed word, 32 two-bit fields are emitted:

```text
status[index] = (raw >> (2 × index)) & 0x3
```

Names use:

```text
<raw-name>.status_00
...
<raw-name>.status_31
```

The processor also emits:

```text
<raw-name>.nonzero_status_count
```

The implementation does not assign rail or physical-Core names and does not
define official meanings for status codes 0 through 3.

## 10. OpenTelemetry Metric Construction



### 10.1 Resource and scope

`scrapeMetrics()` creates one `ResourceMetrics`/`ScopeMetrics` container per
non-empty endpoint map entry, then appends one OTel metric for every processed
`MetricValue`.

### 10.2 Gauge mapping

For `MetricValue.Type == "gauge"`:

- create an OTel Gauge;
- append one datapoint;
- set datapoint timestamp to collection timestamp.



### 10.3 Counter mapping

For every other type:

- create an OTel Sum;
- set monotonic to true;
- set cumulative aggregation temporality;
- set start timestamp and datapoint timestamp to the collection timestamp.

This describes the current implementation. Consumers shall use observed
Prometheus behavior and family guidance for reset-sensitive analysis.

### 10.4 Numeric mapping

Supported values are:


| Go value            | OTel datapoint |
| ------------------- | -------------- |
| `int64`             | integer        |
| `uint64 ≤ MaxInt64` | integer        |
| `uint64 > MaxInt64` | double         |
| `float64`           | double         |
| `int`               | integer        |
| `uint ≤ MaxInt64`   | integer        |
| larger `uint`       | double         |


Unsupported types are logged and skipped. Converting very large unsigned
integers to double preserves range but may not preserve exact integer precision
above the IEEE-754 exact-integer boundary.

### 10.5 Attributes

The transport adapter's complete attribute map is copied to every datapoint.
Attribute-copy failure skips that metric.

## 11. Collector Pipeline and Prometheus Interface



### 11.1 Redfish pipeline

The current logical Redfish metrics pipeline is:

```yaml
receivers: [intelpmtreceiver, optional auxiliary otlp]
processors: [batch]
exporters: [prometheus, optional debug]
```



### 11.2 Local pipeline

The current logical Local pipeline is:

```yaml
receivers: [intelpmtreceiver]
processors: [batch]
exporters: [prometheus]
```



### 11.3 Prometheus exposition

The Collector Prometheus exporter listens on the configured exporter endpoint.
Prometheus scrapes it using deployment-owned target configuration.

The exposition contract includes:

- normalized metric name;
- HELP text from XML description;
- TYPE derived from OTel gauge or sum;
- numeric sample;
- complete provenance label set.

The documented current timing relationship is:

```text
PMT source collection: 20 seconds
Prometheus scrape: approximately 15 seconds
Grafana refresh: 20 seconds
```

Prometheus can therefore store repeated exported values between PMT collection
updates. A faster Grafana refresh does not create new source samples.

### 11.4 Prometheus time-series key

The unique time-series key is:

```text
metric name + complete label set
```

Different Aggregators can emit the same metric name. Removing identity labels
without aggregation can produce duplicate label sets.

### 11.5 Multi-name range functions

PromQL range functions commonly remove `__name__`. Before applying `rate`,
`increase`, `delta`, `changes`, or `timestamp` across a metric-name regex, the
Dashboard generator copies name to a normal label:

```promql
label_replace(
  {__name__=~"<pattern>", ...},
  "metric", "$1", "__name__", "(.+)"
)
```

This preserves distinct output label sets.

### 11.6 Counter policy

Use `increase(metric[5m])` when the product requirement is a fixed five-minute
amount and the family is a cumulative counter. Current examples:

- transformed Core usage;
- PVP throttle counters;
- RDT MBM total and local memory transactions;
- incomplete Aggregator update cycles.

Use `rate()` when a calibrated per-second result is the required semantic.
Current proven example:

- QAT cumulative megabytes to MB/s.



### 11.7 Gauge policy

Read a current gauge directly unless a before/after raw comparison is explicitly
required. Current direct examples include:

- temperature;
- RDT CMT LLC cache-line usage;
- enable and topology states;
- latency gauges.

Unknown lifecycle or unit remains visible as raw.

## 12. Dashboard Generator Design



### 12.1 Source and outputs

Source:

```text
tools/otel/generate_gnr_telemetry_overview.py
```

Repository outputs:

```text
tools/otel/dashboards/pmt-gnr-redfish-overview.json
tools/otel/dashboards/pmt-gnr-local-overview.json
tools/otel/dashboards/pmt-gnr-metric-explorer.json
```

The generator also writes deployment-provisioned copies when the configured
system path is available.

### 12.2 Stable UIDs

```text
pmt-gnr-redfish-overview
pmt-gnr-local-overview
pmt-gnr-metric-explorer
```

The legacy Dashboard UID remains separate.

### 12.3 Redfish variables

Variable order:

```text
endpoint
device
access
source
core
```

Core panel scope includes:

```text
PMTEndpoint
CollectionMode="redfish"
DeviceId
AccessId
SourceId
Core layout GUID
```



### 12.4 Local variables

Variable order:

```text
endpoint
telemetry
core
```

Core panel scope includes:

```text
PMTEndpoint
CollectionMode="local"
AccessId=telemN
Core layout GUID
```



### 12.5 Path-aware display locator

The generator creates a synthetic `agg_display` query label:

```text
Redfish: AGG[D<device>/A<access>/S<source>]
Local:   AGG[telemN]
```

This label is for display. It is not written back into Prometheus and does not
create a canonical physical identity.

### 12.6 Overview layout contract

Each path Overview contains:

```text
3 navigation cards
7 row panels
25 metric panels
33 PromQL targets
```

All telemetry panels below the navigation cards are shifted together so the
cards occupy one dedicated top row.

### 12.7 Current semantic query contracts


| Panel family       | Query contract                                                 |
| ------------------ | -------------------------------------------------------------- |
| Temperature        | Current positive valid values                                  |
| Core usage         | `increase(...[5m])` on transformed cumulative counter          |
| PVP throttle       | `increase(...[5m])`, with 64/1024 extracted as detection label |
| RDT MBM            | `increase(...[5m])`, with CHA/RMID extracted from name         |
| RDT CMT            | Current raw value, with CHA/RMID extracted from name           |
| Memory channel     | Raw window change only                                         |
| Energy accumulator | Raw five-minute movement only                                  |
| QAT throughput     | Rate of cumulative megabyte counters in MB/s                   |
| QAT latency        | Average ns only when traffic is present                        |
| Data loss          | Five-minute incomplete-cycle increase                          |
| Internal update    | `changes()` rather than wall-clock conversion                  |




### 12.8 Navigation

The top cards link to:

- the opposite path Overview;
- Metric Explorer with current endpoint/path context;
- Dashboard Guide.

Dashboard header links are intentionally empty for the two Overviews.

### 12.9 Time defaults

Both Overviews default to the last 30 minutes and refresh every 20 seconds.
These are presentation defaults and do not alter Prometheus retention.

## 13. Metric Explorer Design

Metric Explorer uses an exact metric-name variable rather than the curated
Overview list. Its responsibilities are:

- exact name selection;
- current value display;
- raw labels table;
- raw history;
- engineering rate/delta comparison;
- return link to Redfish Overview.

Explorer transformations are investigative aids. The family reference remains
the authority on whether a rate or delta is meaningful.

## 14. Metric Catalog Design



### 14.1 Inputs

`export_pmt_metric_catalog.py` reads:

- exposed Collector metric text for configured collection paths;
- Prometheus metadata;
- `FAMILY_GUIDES` from `pmt_metric_guides.py`.



### 14.2 Family guide model

Each family guide provides:

- family ID and readable title;
- exact-name regular expression;
- meaning;
- numeric semantics;
- recommended query;
- caveat.



### 14.3 Outputs

```text
docs/pmt-metrics-catalog.csv
docs/pmt-metrics-summary.md
docs/pmt-metric-family-reference.md
```

The exact-name CSV includes current type, unit and unit source, semantic guide,
observed series counts, observed labels, and HELP text.

### 14.4 Unit resolution

Unit priority is:

1. Prometheus metadata unit, when present;
2. recognized metric-name suffix;
3. unspecified.

`unspecified` is an explicit result. The generator must not infer a physical
unit from a descriptive word alone.

## 15. Detailed Error and Logging Contract


| Layer     | Condition                            | Current action                                        |
| --------- | ------------------------------------ | ----------------------------------------------------- |
| Config    | Interval below minimum               | Validation error                                      |
| Config    | Unknown mode                         | Validation error                                      |
| Metadata  | File absent                          | Startup error                                         |
| Metadata  | No mappings                          | Startup error                                         |
| Metadata  | Invalid mapping GUID or size         | Warn and skip mapping                                 |
| Metadata  | Duplicate GUID/size                  | Warn and keep first mapping                           |
| Redfish   | Trigger or GET failure               | Return endpoint discovery error                       |
| Redfish   | Non-2xx response                     | Return endpoint discovery error                       |
| Redfish   | Invalid JSON                         | Return endpoint discovery error with response context |
| Local     | Root unreadable                      | Return empty cycle result                             |
| Local     | Device field unreadable or malformed | Skip device                                           |
| Schema    | GUID/size absent                     | Warn and skip Aggregator                              |
| Schema    | XML file parse failure               | Warn and skip Aggregator                              |
| Decode    | Invalid Base64                       | Warn and return no metrics for Aggregator             |
| Decode    | Payload too short                    | Warn and stop remaining samples in affected group     |
| Transform | Missing input                        | Warn and skip sample                                  |
| Transform | Expression error                     | Warn and skip sample                                  |
| Metric    | Unsupported number type              | Warn and skip metric                                  |
| Metric    | Attribute conversion failure         | Warn and skip metric                                  |
| OTel      | Downstream consume failure           | Log error; no replay                                  |


Logs shall not include BMC credentials.

## 16. Timestamp and Reset Semantics

The system contains several different clocks:


| Timestamp                            | Source                                | Use                          |
| ------------------------------------ | ------------------------------------- | ---------------------------- |
| Redfish collection timestamp         | BMC response                          | OTel datapoint time          |
| Local collection timestamp           | Collector wall clock                  | OTel datapoint time          |
| Internal Aggregator update timestamp | PMT metric, often crystal-clock ticks | Detect update movement       |
| Energy timestamp                     | Paired PMT field, seconds where named | Correlate energy accumulator |
| Prometheus scrape timestamp          | Prometheus                            | Storage/query timing         |


An internal hardware timestamp shall not be rendered as wall-clock time without
an approved conversion.

Counter reset handling belongs in PromQL counter functions or a family-specific
implementation. Gauge `delta()` does not automatically provide counter-reset
semantics. Raw accumulator panels must document reset and wrap uncertainty.

The receiver does not retain a previous value, calculate deltas, detect modulo
wrap, or repair monotonicity.

## 17. Identity and Label Rules



### 17.1 Required distinctions

The following identifiers are different namespaces:

- PMT endpoint;
- Redfish Device ID;
- Redfish Access ID;
- Redfish Source ID;
- Local `telemN`;
- MCTP EID;
- management Domain ID;
- PCI BDF;
- XML Core field number;
- Linux logical CPU;
- PMT GUID.

No equality shall be inferred from similar numeric values.

### 17.2 GUID

GUID selects an XML data layout. Multiple Aggregator instances can share it.
GUID is not a unique instance serial number.

### 17.3 Size

Size is part of schema compatibility and is stored in bytes. It is not a
cardinality count.

### 17.4 Access

Access identifies a path-specific mechanism or context used to read a source.
It is not automatically a physical coordinate.

### 17.5 Source

Source identifies an Aggregator source within a Redfish access context. Local
currently uses literal `SourceId=0` as a normalized label.

## 18. Build and Generation Interfaces



### 18.1 Collector build

The minimal OpenTelemetry Collector Builder manifest registers the custom PMT
receiver and produces the `otelcol-pmt` distribution.

The receiver package and selected standard Collector components must compile
against the versions declared by the repository's Go module and builder
manifest.

### 18.2 Dashboard generation

```bash
python3 tools/otel/generate_gnr_telemetry_overview.py
```

Expected result:

- both Overview JSON files written;
- Metric Explorer JSON written;
- stable UIDs retained;
- provisioned copies updated when permitted.



### 18.3 Catalog generation

```bash
python3 tools/otel/export_pmt_metric_catalog.py
```

Expected result:

- exact-name CSV written;
- summary written;
- family reference written;
- counts printed for metric definitions and observed series.

The required Collector and Prometheus endpoints must be reachable to regenerate
an observed catalog.

## 19. Verification and Test Design



### 19.1 Static Dashboard regression

```bash
python3 -m unittest tools/otel/test_gnr_telemetry_overview.py
```

The suite verifies:

- stable independent UIDs;
- row, panel, and target counts;
- path-specific selectors;
- no artificial temperature warning threshold;
- no unsupported physical units on raw panels;
- five-minute Core usage increase;
- MBM increase and CMT current-value semantics;
- five-minute throttle increase and detector wording;
- legacy UID isolation;
- path-aware legends;
- dedicated navigation row;
- concise descriptions;
- Explorer return link.



### 19.2 Metric-guide regression

```bash
python3 -m unittest tools/otel/test_pmt_metric_guides.py
```

The suite shall verify exact-name family classification and semantic coverage.

### 19.3 Go tests

Receiver tests cover at least:

- full-width unsigned identity-mask handling;
- large unsigned fixed-point evaluation;
- FIVR packed-slot expansion;
- known poison suppression and availability;
- fallback decode diagnostics.

Run the receiver package tests with the repository Go toolchain.

Current Go coverage does not yet exercise configuration validation, malformed
metadata, sysfs discovery, Redfish trigger/GET behavior, receiver lifecycle,
OTel datapoint construction, exact exporter exposition, truncated payload
behavior, counter reset/wrap, or cache identity. These are required additions
before treating the Alpha receiver as a hardened integration component.

### 19.4 Live PromQL validation

For every generated Overview target:

1. substitute valid current Dashboard variables;
2. call Prometheus query API;
3. require `status=success`;
4. distinguish valid empty results from parser or execution errors;
5. verify critical identity labels on non-empty top results.

Critical current checks include:

- Redfish and Local Core locators;
- CHA and RMID extraction;
- Core usage increase;
- throttle detection-window label;
- MBM total/local distinction;
- CMT current raw value;
- QAT Idle gating;
- data-loss and heartbeat separation.



### 19.5 End-to-end acceptance matrix


| Test                   | Stimulus                           | Expected result                                              |
| ---------------------- | ---------------------------------- | ------------------------------------------------------------ |
| Redfish normal cycle   | Reachable BMC with valid snapshot  | Required Aggregators decoded and exported                    |
| Local normal cycle     | Readable PMT sysfs                 | Required `telemN` devices decoded and exported               |
| Unsupported layout     | Unknown GUID/size                  | Warning; affected Aggregator absent; cycle continues         |
| Short payload          | Payload below XML-required offset  | Warning; no panic; unaffected data continues                 |
| Bad transform          | Invalid or missing transform input | Sample skipped; Aggregator processing continues              |
| Poisoned FIVR          | DEADBEEF packed word               | Availability=0; raw and slot metrics suppressed              |
| Counter workload       | Counter increases                  | Five-minute increase panel becomes non-zero                  |
| Idle QAT               | No QAT traffic                     | Idle state; average latency not shown as valid 0 ns          |
| Stale source           | Stop one Collector                 | Freshness ages on that path; other path remains queryable    |
| Internal update issue  | Incomplete-cycle counter grows     | Update Quality and incomplete-cycle panels change            |
| Dashboard regeneration | Run generator                      | Stable structure and UIDs; tests pass                        |
| Catalog regeneration   | Reachable exporters and Prometheus | 5,285-name catalog baseline regenerated for current platform |




## 20. Change Procedure

For a change to an existing supported metric or panel:

1. identify the exact metric name, XML HELP, GUID, and size;
2. confirm gauge/counter/snapshot lifecycle;
3. confirm unit and transformation source;
4. modify the receiver only when XML-driven processing is insufficient;
5. modify `pmt_metric_guides.py` when family semantics change;
6. modify the Dashboard generator, never generated JSON directly;
7. regenerate Dashboard and catalog artifacts;
8. update PRD/HLD/LLD or Dashboard Guide when the public contract changes;
9. run Python and Go regression tests;
10. validate generated PromQL against Prometheus;
11. review the diff for credentials, invented units, and identity claims;
12. deploy through the owning environment's normal change process.



