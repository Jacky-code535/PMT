# Intel Telemetry Architecture — Readable Internal Guide

> **Intel Internal Only / Not approved for external distribution**
>
> 本文将用户提供的《Telemetry Platform Architecture Specification (TPAS)
> v1.8+》内容重新组织为一份面向软件、验证、性能和客户演示团队的高可读参考。
> 它不是TPAS的替代品，不覆盖原文的法律声明、全部HSD追踪记录和所有未来规划细节。
> 发生冲突时，以受控发布的TPAS、平台HAS、匹配CPU/firmware的PMT schema以及实际
> 硬件发现结果为准。

## 1. 一页摘要

Intel PMT（Platform Monitoring Technology）的核心目的不是发明一套新的性能
counter，而是让不同来源的Telemetry可以被软件：

1. 统一发现；
2. 统一识别；
3. 通过in-band与out-of-band路径访问；
4. 使用机器可读schema解码；
5. 同时被多个消费者读取；
6. 扩展到服务器、加速器、IPU、GPU和未来分离式Die架构。

最重要的数据流是：

```text
Hardware/IP counters, sensors and status
  → Provider
    → Aggregator / Watcher / PMON / CrashLog
      → Telemetry Semantic Space (TSS)
        → In-band MMIO or OOB PMT commands
          → Collector / BMC
            → Prometheus, database, analytics or orchestration
```

必须先区分三类问题：

| 问题 | 由什么回答 |
|---|---|
| 具体访问哪个硬件实例 | Provider、transport topology、Device/Access/Source、PCI BDF、MCTP EID、Domain |
| 数据采用什么布局 | GUID/UID + Size + platform/schema version |
| 布局中的字段表示什么 | XML/JSON schema中的sample name、HELP、type、unit和transformation |

GUID不是每个Aggregator实例的硬件序列号。多个实例可以共享同一GUID和Size，因为
它们使用相同的数据布局。

## 2. 为什么需要PMT

### 2.1 传统PerfMon的价值

Intel Core和Uncore PerfMon长期提供：

- instructions retired；
- actual/reference cycles；
- cache hit/miss；
- memory、UPI、PCIe活动；
- PMON fixed-function和programmable events；
- PEBS、PMI和Top-down Microarchitecture Analysis所需事件。

这些能力适合软件调优和深度性能分析，但传统访问模型存在限制。

### 2.2 传统监控的主要问题

#### Shareability

可编程counter和event select registers可能被多个工具争用。一个工具重新配置event，
会改变另一个工具正在观察的内容。

#### Accessibility

大量接口依赖MSR、PCI config、MMIO或IP私有寄存器。不同CPU代际、不同IP和
不同操作系统需要不同访问代码。

#### Discovery

Architectural PerfMon可以通过CPUID发现，但很多free-running counter、环境数据和
IP私有Telemetry缺少统一枚举方式。

#### Idempotency

部分传统寄存器可能clear-on-read或存在读取副作用，不适合多消费者共享。

#### Granularity versus cost

软件调优可能要求微秒或更细粒度；电源管理通常是毫秒；计费和容量管理可能是秒。
采样越快，带宽、存储、控制器资源和性能开销越大。

#### Out-of-band availability

PerfMon主要面向in-band软件。云、Telco、裸机管理、故障恢复和agentless监控需要
即使Host OS不可用，也能通过BMC获得Telemetry。

### 2.3 PMT解决的核心问题

PMT提供：

- 可枚举的Telemetry endpoints；
- GUID/schema驱动的数据布局；
- read-only Aggregator以支持多消费者；
- in-band MMIO和OOB命令访问；
- Watcher用于timer/threshold-triggered动作；
- CrashLog和部分PMON数据的统一发现；
- 面向多Die、加速器和异构平台的扩展框架。

## 3. 目标使用场景

### Service Assurance

- 判断服务依赖的硬件资源是否持续可用；
- 观察SLA相关吞吐、延迟、资源和环境信号；
- 支持Telco/NFV的独立管理路径。

### Capacity Optimization

- 发现过度配置和隐藏容量；
- 分析CPU、cache、memory和accelerator活动；
- 支持集群容量规划。

### Orchestration

- workload fingerprinting；
- workload placement；
- NUMA和资源亲和性；
- scale-out节点状态；
- VM、container、RMID或PASID级别的未来归因。

### RAS and Predictive Maintenance

- 温度、功率、节流和corrected-error趋势；
- 故障预测；
- 更快的break-fix和fault isolation；
- CrashLog提取。

### Security and Anomaly Detection

- 使用运行状态和资源行为识别异常；
- 与Processor Trace、PerfMon或软件事件结合；
- 受安全策略控制，避免Telemetry造成side-channel暴露。

## 4. 平台范围

Telemetry架构需要适用于：

- Xeon Scalable Performance（-SP）；
- Advanced Performance（-AP/HPC）；
- Rich I/O；
- Xeon-D和Atom-D；
- Entry server；
- 单Socket和多Socket；
- 单Die、split-die和disaggregated-die；
- CPU、GPU、IPU、XPU、FPGA和fixed-function accelerator。

不同segment的重点不同：

- Cloud：SLA、容量、orchestration、安全；
- Telco：OOB、低延迟、计费、可靠性；
- HPC：node/cluster-level power、thermal和performance；
- Storage/Network：PCIe、CXL、QAT、HQM和data movement；
- Edge/IoT：低功耗、实时性、扩展温度和单Socket。

## 5. PMT核心对象

### 5.1 Provider

Provider是对外提供PMT能力的逻辑实体。一个支持PMT的设备至少有一个Provider。

Provider可以包含：

- 一个或多个Aggregator；
- 一个或多个Watcher；
- CrashLog；
- PMON view；
- Streaming Agent能力。

Provider可能位于：

- CPU SoC中的OOBMSM；
- GPU本地管理控制器；
- IPU/SmartNIC管理处理器；
- discrete PCIe/CXL accelerator。

### 5.2 Aggregator

Aggregator是read-only Telemetry数据区域。它可以：

- 收集IP push来的数据；
- 通过sideband/MMIO on-demand pull数据；
- 保存free-running counters；
- 保存当前sensor/status；
- 派生histogram或其他secondary telemetry。

从软件角度看，Aggregator是连续的Telemetry Semantic Space。每个字段由offset、
bit width、type和transformation定义。

一个Aggregator实例需要两类身份：

```text
实例身份：在哪个Provider/Access/Source/BDF/EID/Domain
布局身份：GUID + Size + schema version
```

### 5.3 Watcher

Watcher允许软件配置：

- 观察哪些Telemetry items；
- timer或threshold触发条件；
- snapshot目的地；
- interrupt或MCTP notification；
- one-shot或periodic操作。

Watcher需要配置，所以与read-only Aggregator不同，存在owner和仲裁问题。架构通常
为in-band和OOB提供独立实例，避免相互抢占。

### 5.4 Watcher Sampler

Sampler根据timer或threshold，把选定Telemetry形成带timestamp的snapshot，并写入
指定buffer/TSS。

它可以是：

- vector-based；
- Sample-ID-based。

### 5.5 Watcher Streamer / Tracer

Streamer把Telemetry snapshot发送到：

- BMC；
- MCTP streaming endpoint；
- local memory/trace hub；
- IPU/network streaming agent。

Server平台主要关注Streamer/Sampler。连续Tracer在不同产品上的支持范围不同，不能
仅根据架构概念假设当前GNR链路已实现。

### 5.6 CrashLog

CrashLog是在catastrophic event后保留的诊断数据。PMT负责发现、配置和提取路径，
但CrashLog不等同于持续性能Telemetry。

典型流程：

```text
Crash event
  → hardware/OOBMSM/PCU preserves volatile debug state
    → reset/recovery
      → BMC or BIOS extracts CrashLog
```

### 5.7 PMON Aggregator

PMON Aggregator可以暴露Uncore PMON free-running或event counter view。需要注意：

- 数据读取可以OOB；
- programmable event通常仍需in-band配置；
- PMT不自动解决所有PMON owner和event programming问题；
- DMR及后续平台对MMIO和PMON domain的组织与SPR/GNR不同。

### 5.8 Telemetry Semantic Space

TSS是软件看到的逻辑Telemetry空间。微架构上它可能来自：

- IP本地SRAM；
- OOBMSM SRAM；
- LTM映射；
- sideband pull；
- IP定期push；
- firmware/state machine动态维护。

“看起来是连续MMIO”不代表底层所有字段位于同一物理memory block。

## 6. 标识符与Schema

### 6.1 GUID / UID

GUID用于选择Aggregator或Watcher的数据布局。当前实现中同一GUID可以有多个实例。

正确理解：

```text
GUID ≈ schema/layout type
```

错误理解：

```text
GUID = 每个物理Aggregator的唯一serial number
```

布局发生不兼容变化时，标准Aggregator原则上需要新的GUID。生产软件仍应同时匹配
GUID和Size，防止firmware/schema版本错误。

### 6.2 Size

Size是Telemetry空间大小。Collector应使用：

```text
GUID + Size
```

共同选择schema，不能只看GUID。

### 6.3 Sample ID

Sample ID是Aggregator TSS中的sample/container索引。它属于数据布局，不是
physical core ID，也不是Linux CPU编号。

### 6.4 Sample Group

Sample Group表示一组Telemetry items，用于bulk access或逻辑组织。具体声明和支持
程度必须以匹配平台schema和命令实现为准。

### 6.5 Stream GUID

Stream GUID由软件配置给Watcher Streamer，用于标识生成的stream。它不等同于
Aggregator schema GUID。

## 7. Discovery与访问

### 7.1 In-band discovery

典型流程：

```text
PCIe enumeration
  → PMT DVSEC/VSEC capability
    → Discovery Record
      → GUID, Size, Access Type, Counter Base
        → TSS MMIO mapping
          → kernel intel_pmt device
            → /sys/class/intel_pmt/telemN
```

Linux `telemN`是当前kernel枚举对象，不是跨启动稳定的硬件身份。

### 7.2 Out-of-band discovery

典型流程：

```text
BMC enumerates MCTP endpoints
  → Is Telemetry Supported
    → Get number of Aggregators/Watchers
      → Get Aggregator details
        → Device/Access/Source + GUID + Size
          → Get sample or bulk sample
```

MCTP可以运行在PCIe或I3C之上。旧平台还可能存在PECI服务，但不能把不同transport的
编号当成相同物理坐标。

### 7.3 Discovery Record类型

架构定义不同DVSEC/discovery records，例如：

- PMON；
- Telemetry Aggregator；
- Watcher；
- CrashLog Watcher；
- Capability Discovery。

实际平台是否实现、是否in-band/OOB可见，必须运行时枚举。

## 8. OOBMSM的作用

OOBMSM（Out-of-Band Management Services Module）是服务器SoC中的管理和Telemetry
基础设施。它通常负责：

- MCTP协议；
- in-band PCIe/MMIO入口；
- OOB命令服务；
- Telemetry aggregation；
- CrashLog；
- security/access policy；
- LTM translation；
- 与Punit和其他IP的sideband访问。

LTM（Local Translation Module）维护：

- endpoint访问路径；
- primary-to-secondary地址转换；
- MMIO到sideband的映射；
- allowlist和security policy；
- PMT/PMON/DFD等窗口映射。

因此TSS中的字段可能是OOBMSM通过LTM从其他IP读取后呈现的，不一定物理存储在
OOBMSM附近。

## 9. GNR分离式Die与分层OOBMSM

GNR使用Compute Die与IO Die分离架构。不同Die可以有本地OOBMSM/Punit管理实体，
并通过层级结构连接到平台可访问的root endpoint。

关键概念：

- Root OOBMSM：提供平台入口并桥接leaf；
- Leaf OOBMSM：管理本地Die的Telemetry/CrashLog/register access；
- Domain ID：管理/PECI domain；
- MCTP EID：MCTP transport endpoint；
- AccessId：当前BMC/Redfish暴露的访问标识；
- DeviceId：当前BMC对CPU设备的标识。

这些编号不能互换：

```text
DeviceId ≠ AccessId ≠ SourceId ≠ DomainId ≠ EID ≠ Linux CPU
```

当前avc01中的`D0/D1`可以读作Socket 0/1，是平台实测映射，不是所有PMT平台的
通用规则。

## 10. GNR主要Telemetry域

### 10.1 CORE Telemetry

CORE schema包括：

- current temperature；
- frequency residency histogram；
- temperature residency histogram；
- voltage residency histogram；
- Cdyn levels；
- relative usage；
- 64/1024-cycle throttle；
- core enable fields；
- internal update/data-loss fields。

XML字段使用`C0_*`到`C63_*`命名。当前avc01每个CORE Aggregator中Core 0–31
enabled，Core 32–63 disabled。

这些Core编号属于该Aggregator XML布局，当前没有到Linux CPU的权威映射。

### 10.2 RDT / RMID Telemetry

包括：

- per-CHA/per-RMID CMT；
- MBM total；
- MBM local；
- CHA enable；
- internal timestamp。

RMID是resource-monitoring identity，不是PID。没有Host RMID allocation context时，
不能把RMID直接翻译成某个进程、VM或container。

### 10.3 PCU / Punit Telemetry

可能包括：

- Core/Package C-state；
- energy accumulators；
- memory channel read/write；
- IO/UPI activity；
- EPB policy；
- Program Excursion Monitor；
- power-limit、thermal、VR和RAPL相关字段；
- FIVR monitor。

字段的单位和reset/window语义必须以schema/codebook为准，不能仅根据名称猜测W、
J、GB/s或百分比。

### 10.4 FIVR

当前schema将64-bit monitor拆分为2-bit fields。项目Receiver还派生：

- availability；
- non-zero count；
- status fields。

`DEADBEEF`表示firmware data-unavailable poison，不是确认的硬件故障码。当前缺少：

- slot到rail/core的映射；
- code 0–3的正式枚举。

### 10.5 QAT / HCx

QAT/CPM类Telemetry可以包括：

- PCIe inbound/outbound megabytes；
- page request；
- translation；
- read completion；
- average/maximum latency；
- activity accumulators。

CPU-only workload不会自动使用QAT。QAT throughput为0通常表示Idle，不代表采集失败。

### 10.6 Topology

Topology Aggregator可以暴露：

- current socket/domain identity；
- EID；
- domain mask；
- UPI/DDR enable；
- core/CHA enable；
- root/leaf关系。

它是建立in-band/OOB物理映射的关键证据，但不能在缺少正式关系时从AccessId数值
自行推导物理Die坐标。

## 11. Watcher、Streaming与当前Collector的边界

架构支持Watcher、Sampler、Streamer和notification，但当前avc01链路主要读取
Aggregator snapshot。

当前Dashboard出现某个metric不代表：

- Watcher已经配置；
- threshold event已经启用；
- Streaming Agent正在发送；
- CrashLog已经采集；
- PMON programmable event已经设置。

软件必须把“架构定义能力”和“当前pipeline已启用能力”分开记录。

## 12. Accelerator Telemetry

Accelerator可以是single-node或multi-node IPU、GPU、XPU或integrated accelerator。
PMT方向要求：

- Provider discovery；
- in-band与OOB访问；
- optional Watcher；
- optional CrashLog；
- multi-host isolation；
- per-node/per-VM/PASID/RMID isolation；
- Streaming Agent；
- power、voltage、current、temperature、firmware和power-state基础Telemetry。

共享加速器特别需要防止一个Host读取另一个Host的Telemetry空间。

## 13. Security与Trusted Telemetry

Telemetry可能泄露workload特征，因此需要：

- endpoint authentication；
- SPDM attestation/session；
- access policy；
- TDX/SGX/SEAM等trusted environment过滤；
- per-tenant/RMID/TSS isolation；
- integrity和可选encryption；
- identity-based access level。

不能因为OOBMSM可以内部读取，就假设所有字段都允许暴露给BMC或外部客户。

## 14. 代际演进

### SPR / EMR

- PMT v1时代；
- active OOBMSM per package；
- Core、RDT、PCU Aggregator；
- limited Watcher/Streamer；
- split-die但平台可见管理实例较少。

### GNR / Birch Stream

- disaggregated Compute/IO Die；
- hierarchical OOBMSM；
- topology discovery；
- MCTP/I3C能力增强；
- 多Domain、多EID；
- 当前项目平台。

### DMR及后续

- CBB + iMH hub-and-spoke；
- CBB与Client共享，管理实体重新分布；
-更多MMIO；
- PMON domain变化；
- Trusted Telemetry；
- 更强的并发和scalability要求。

不能把DMR规划或后续平台能力当成当前GNR已经实现的功能。

## 15. 当前avc01软件链路

```text
OOB:
GNR Aggregator
  → BMC MCTP/Redfish
    → Redfish Collector

In-band:
GNR Aggregator
  → PCIe PMT discovery
    → Linux intel_pmt sysfs telemN
      → Local Collector

Both:
Collector
  → XML decode by GUID + Size
    → OpenTelemetry metrics
      → Prometheus
        → Grafana / experiments / ML export
```

当前规模：

- 36 OOB Aggregator instances；
- 36 Local Aggregator instances；
- 7种GUID/Size布局；
- 5,285 metric names；
- 每条路径32,710 series。

## 16. 当前最重要的未闭环问题

### Physical-instance mapping

尚未建立：

```text
OOB D/A/S
↔ Canonical Aggregator Instance
↔ Local host/telemN/sysfs/PCI BDF
↔ Socket/Domain/physical provider
```

因此当前可以解码和比较Telemetry，但不能对所有实例稳定回答：

> 这个Local telemN与哪个OOB D/A/S是同一个硬件Aggregator？

### Core-to-OS mapping

尚未建立：

```text
Aggregator Core N field
↔ physical core/APIC
↔ Linux logical CPU
```

### Semantic codebooks

仍缺少部分：

- energy scale；
- MBM transaction size；
- memory bandwidth conversion；
- FIVR code/rail mapping；
- PEM bit/reset semantics；
- mesh bin definitions；
- C-state unit/lifecycle。

完整任务、证据要求和owner需求见`pmt-unresolved-work.md`。

## 17. 推荐的软件身份模型

不要强迫Local使用OOB D/A/S，也不要让OOB使用Local telemN。推荐：

```text
PMTInstanceId        # transport-neutral canonical ID
PMTAggregatorType
PMTGuid
PMTSizeBytes
CollectionMode

OOBDeviceId
OOBAccessId
OOBSourceId

LocalHost
LocalTelemDevice
LocalSysfsPath
LocalPCIBDF

PMTSocket            # only when authoritative
PMTDomain            # only when authoritative
MappingConfidence
```

Dashboard主标签使用Canonical ID；OOB和Local locator保留在tooltip/技术表格中。

## 18. 正确的排障顺序

```text
1. 确认Provider/transport可发现
2. 确认Aggregator实例locator
3. 确认GUID + Size匹配schema
4. 确认内部last-update推进
5. 确认Collector读取与Prometheus freshness
6. 确认metric type/unit/transformation
7. 映射到physical provider/socket/domain
8. 再关联workload、Linux CPU、VM或RMID
```

如果第7步没有完成，只能报告“哪个Telemetry实例异常”，不能声称已经定位到具体
physical die/core。

## 19. 术语速查

| Term | 简明含义 |
|---|---|
| Provider | 对外提供PMT能力的设备/逻辑实体 |
| Aggregator | read-only Telemetry数据空间 |
| Watcher | timer/threshold触发、snapshot或event配置实体 |
| TSS | 软件看到的Telemetry Semantic Space |
| GUID | 数据布局/schema标识，不是实例serial number |
| Size | TSS大小，与GUID共同选择schema |
| Sample ID | TSS中的sample/container索引 |
| DeviceId | 当前访问层的设备标签；语义依路径而异 |
| AccessId | 当前BMC/Collector访问上下文，不是物理坐标 |
| SourceId | Access下的Aggregator source编号 |
| MCTP EID | MCTP transport endpoint address |
| Domain ID | 管理/PECI domain identity |
| BDF | PCI Segment/Bus/Device/Function地址 |
| OOBMSM | SoC中的管理与OOB Telemetry服务模块 |
| LTM | OOBMSM地址转换和访问策略数据库 |
| RMID | Resource Monitoring ID，不是PID |
| PMON | Core/Uncore performance monitoring infrastructure |
| CrashLog | crash后保留并提取的诊断数据 |

## 20. 相关项目文档

- `pmt-platform-topology.md`：avc01当前36个Aggregator和标签；
- `pmt-unresolved-work.md`：物理映射和语义缺口；
- `gnr-telemetry-dashboard-guide.md`：Dashboard指标、单位和误读边界；
- `pmt-metric-family-reference.md`：38个metric families；
- `pmt-metrics-catalog.csv`：5,285个准确metric names；
- `complete-pmt-collection-workflow.md`：当前部署链路；
- `gnr-fivr-health-collection-workflow.md`：FIVR专项实现。
