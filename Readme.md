# Intel Platform Monitoring Technology Telemetry (Intel PMT)

## What is Intel PMT

Intel PMT is a standardized way of exposing telemetry through host-based and out-of-band access across client, server and companion products.
It consists of five key components:
* Discovery: A common discovery mechanism
* Aggregator: Responsible for collecting the information
* Watcher: Provides a control to take action on telemetry (e.g. stream)
* Schema: Describes the telemetry and provides a standardized approach to transforming telemetry
* Access: A standardized driver model and standardized OOB API

Each Intel PMT provider is identified by unique ID and each unique ID is associated with a set of XML specification files.

## What is specified in Intel PMT XML files?

Each set of Intel PMT XML files define:
* Common data types
* Low level samples specification (container index, offset, LSB, MSB)
* High level samples specification (derivation of samples and counters value through application of transformation on one or more low level samples)

## Intel PMT Linux kernel modules

Intel PMT support on Linux has been added to mainline Linux kernel under platform driver (_drivers/platform/x86/intel/pmt_). This driver exposes Intel PMT telemetry space as _sysfs_ entry under folder _/sys/class/intel_pmt/_. This driver will expose each discovered Intel PMT telemetry aggregator under a folder with prefix _telem_. Inside this folder, there will be files named:
- guid: the unique id of the Intel PMT space
- size: the size of the Intel PMT space
- telem: the Intel PMT space

Using _guid_ and _size_ information, the associated Intel PMT XML files set can be identified using repository metadata at _xml/pmt.xml_.

## How Intel PMT XMLs are used with telemetry agent

Intel PMT kernel driver is typically loaded to discover and manage Intel PMT providers on a platform. Once the kernel driver is loaded, telemetry agent shall scan the discovered PMT unique IDs. For every known unique ID, telemetry agent shall load the matching set of XML files. Using the specification in the XML files, telemetry agent then reads low level samples/counters followed up by evaluation of high level samples/counters as defined by each high level transformation formula. Telemetry agent may also furnish the result of the evaluation with appropriate unit. Telemetry agent then can report out the collected data to designated data collectors for further processing (i.e. observability visualization, machine learning, inference).

---

## Maintainers & Ownership

Lead Maintainer: **@jwasiuki (Jedrzej Wasiukiewicz)**
Contact: **jedrzej.wasiukiewicz@intel.com**

## Quick Start
> The commands below are the upstream generic examples. For the current avc01 dual-source Redfish + local deployment, start with `docs/README.md` and `docs/complete-pmt-collection-workflow.md`; do not use the generic Python example to infer the production architecture.

Collect local aggregators with python script
```bash
git clone https://github.com/intel/Intel-PMT.git
cd Intel-PMT
sudo python tools/collectd-agent/pmt.py -s file://$(pwd)/xml/pmt.xml -r
```

Build and run custom OpenTelemetry collector:
```bash
cd tools/otel
# Build via ocb (see tools/otel/Readme.md)
./build/otelcol-pmt --config configs/config-example-pmt-local.yaml
```

## Repository Layout

| Path | Purpose |
|------|---------|
| `xml/` | Platform telemetry XML schemas + GUID registry |
| `tools/collectd-agent/` | Reference Python telemetry reader |
| `tools/inventory-converter/` | XML -> Avro conversion tooling |
| `tools/otel/` | Custom OpenTelemetry Collector receiver |
| `tools/docker/` | Containerised environment |
| `docs/` | FAQ, guides |

## Documentation
Additional documentation lives under `docs/`:
- **Documentation map for beginners and developers:** `docs/README.md`
- **Start here — complete avc01 BMC + in-band workflow:** `docs/complete-pmt-collection-workflow.md`
- Intel-internal readable Telemetry/TPAS architecture guide: `docs/internal-telemetry-architecture-readable.md`
- Unresolved physical mapping, metric semantics, ownership, and acceptance criteria: `docs/pmt-unresolved-work.md`
- CPU, Core, label, and all 36 aggregator topology: `docs/pmt-platform-topology.md`
- Human-readable guide to all metric categories, types, and units: `docs/pmt-metrics-summary.md`
- Detailed reference for all 38 current metric families, including data semantics, queries, and caveats: `docs/pmt-metric-family-reference.md`
- Intel-internal bilingual guide to the architecture-based GNR Telemetry Overview, panel semantics, units, and open semantic gaps: `docs/gnr-telemetry-dashboard-guide.md`
- Complete searchable 5,285-metric catalog with family, HELP, units, query guidance, caveats, and labels: `docs/pmt-metrics-catalog.csv`
- GNR FIVR exact-schema workflow: `docs/gnr-fivr-health-collection-workflow.md`
- Backend reproduction guide: `docs/pmt-telemetry-backend-reproduction.md`
- FAQ: `docs/FAQ.md`
- Getting Started Guide: `docs/getting-started.md`
- Use cases: `docs/use-cases.md`
