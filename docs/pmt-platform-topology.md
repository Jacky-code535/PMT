# avc01 CPU、Core 与 PMT Aggregator 完整拓扑

本文回答四个常见问题：

1. 当前服务器有几颗 CPU、多少 Core 和 Thread；
2. PMT 中的 aggregator 是什么；
3. 36 个 aggregator 分别采集什么；
4. Dashboard 中 `Core17 · D0/A27` 之类的标签如何解释。

本文只描述 avc01 当前实测平台。CPU/firmware/XML 变化后必须重新发现，不能把这些编号当作所有 GNR 平台的固定拓扑。

## 1. 当前服务器硬件

2026-07-16 已通过目标 OS 的 `lscpu` 和 BMC Redfish 交叉确认：


| 项目              | 当前值                                                         |
| --------------- | ----------------------------------------------------------- |
| 平台              | Intel AvenueCity                                            |
| CPU 架构          | Intel Granite Rapids Xeon engineering sample                |
| CPU/QDF         | `Q4G7`；brand string 为 `GENUINE INTEL(R) XEON(R)`，不是正式零售 SKU |
| CPUID           | Family 6, Model 173 (`0xAD`), Stepping 1                    |
| CPU socket      | 2                                                           |
| 每 socket Core   | 96                                                          |
| 每 Core Thread   | 2                                                           |
| 每 socket Thread | 192                                                         |
| 整机合计            | 192 physical cores / 384 logical CPUs                       |
| NUMA nodes      | 6                                                           |
| 标称/最大频率         | 2.5 GHz / 3.9 GHz                                           |
| L3 cache        | 1008 MiB                                                    |


这里的 OS logical CPU 编号、CORE XML 中的 `Core N` 字段编号、BMC
`DeviceId/AccessId/SourceId` 是不同编号，不能直接互换。XML使用
`C0_TEMP`、`C0_EN`和“Current temperature for core 0”这样的正式名称；
`local slot`不是XML术语，Dashboard不再使用该名称。

## 2. 一页看懂 Socket、Access、Aggregator 和 Core

先记住最重要的结论：

```text
2 个 Socket
  → 每个 Socket 96 个物理 Core
  → 每个 Socket 有 3 个计算侧 Access 分组
  → 每个计算侧 Access 的 Source 2 是 CORE aggregator
  → 每个 CORE XML定义 Core 0–63 字段
  → 当前每个实例的 Core 0–31 enabled，Core 32–63 disabled
```

只看 CORE telemetry 时，当前结构可以简化为：

```text
Socket 0（DeviceId 0）
├── AGG[D0/A25/S2]：CORE XML字段 Core 0–63，当前0–31 enabled
├── AGG[D0/A26/S2]：CORE XML字段 Core 0–63，当前0–31 enabled
└── AGG[D0/A27/S2]：CORE XML字段 Core 0–63，当前0–31 enabled

Socket 1（DeviceId 1）
├── AGG[D1/A248/S2]：CORE XML字段 Core 0–63，当前0–31 enabled
├── AGG[D1/A249/S2]：CORE XML字段 Core 0–63，当前0–31 enabled
└── AGG[D1/A250/S2]：CORE XML字段 Core 0–63，当前0–31 enabled
```

因此：

```text
每个 Socket：3 个 CORE aggregator × 32 个当前enabled Core字段 = 96
整机：2 个 Socket × 3 = 6 个 CORE aggregator
```

`AGG[D/A/S]`是Dashboard采用的Aggregator定位符号：

```text
AGG[D<DeviceId>/A<AccessId>/S<SourceId>]
```

方括号内全部来自BMC原始labels。`AGG`只是明确告诉读者“这一段用于定位
Aggregator”，不是Intel硬件字段。Aggregator布局仍需结合GUID和Size确认。

定位到CORE aggregator后，Dashboard直接使用XML HELP中的Core编号。例如：

```text
AGG[D0/A25/S2] · Core 22
AGG[D0/A26/S2] · Core 22
AGG[D0/A27/S2] · Core 22
```

这三项分别表示三个CORE aggregator中的`C22_*` XML字段，不是同一个Core，也
不能直接解释为Linux CPU 22。以`AGG[D0/A27/S2] · Core 22`为例，完整展开是：

```text
DeviceId 0（当前对应 Socket 0）
  → AccessId 27
    → SourceId 2：定位到一个Aggregator实例
      → GUID 0x22473996 / Size 14496：确认使用CORE XML布局
        → XML字段 C22_*；HELP称为 core 22
```

当前没有Intel官方的
`DeviceId + AccessId + SourceId + XML Core N → physical core / Linux CPU`
对照表。

还要注意：`A25` 是 BMC 暴露的 telemetry AccessId 分组，不是一个 aggregator。A25 下面实际有 4 个 aggregator：

```text
D0/A25
├── Source 0：C-Die aggregator
├── Source 1：TOPO Leaf aggregator
├── Source 2：CORE aggregator（Core 0–63字段，当前0–31 enabled）
└── Source 3：RMID aggregator
```

所以正确层级是：

```text
Socket / DeviceId
  → AccessId 分组
    → SourceId + GUID 标识的 aggregator
      → aggregator 内部 metric 字段
```

36 是**所有类型的 aggregator 实例总数**，不是 36 个 CORE aggregators：

```text
6 CORE + 6 C-Die + 6 RMID + 8 TOPO Leaf
+ 2 TOPO Root + 4 IO-Die + 4 QAT = 36
```

## 3. Aggregator 是什么，以及它和 Access 的区别

Aggregator 是 CPU/firmware 内部的一块 telemetry 数据区域。它周期性汇集一组相关硬件字段，例如 Core 温度，或者 QAT 延迟，再以一个二进制快照对外提供。

```text
硬件寄存器/计数器
        ↓
PMT Aggregator（二进制 telemetry region）
        ↓ GUID + Size
对应 XML 定义字段偏移、类型和转换
        ↓
Collector 生成 Prometheus metrics
```

每个 aggregator 由 `(GUID, Size)` 精确识别：

- `GUID` 表示数据布局类型；
- `Size` 表示当前 firmware 暴露的字节数；
- 同一个 GUID 可以在不同 socket/access 上出现多个实例；
- 只有 GUID 和 Size 都与 XML 匹配时才允许解码。

一个 `AccessId` 下可以出现多个 `SourceId`，每个 Source 对应一个独立 aggregator。定位一个 Redfish aggregator 时，应使用：

```text
DeviceId + AccessId + SourceId + GUID + Size
```

avc01 的 Redfish 和 Local 各发现 36 个 aggregator。它们是同一硬件 telemetry 的两条观察路径，不是 72 个不同硬件单元。

## 4. 36 个实例由哪七种 Aggregator 组成

36 个实例来自 7 种 `(GUID, Size)` 布局：


| 数据域          | GUID         | Size  | 实例数/来源 | 每个实例主要采集什么                                                                                                     |
| ------------ | ------------ | ----- | ------ | -------------------------------------------------------------------------------------------------------------- |
| OOBMSM CORE  | `0x22473996` | 14496 | 6      | 局部 Core 0–63 的温度、frequency/temperature/voltage histogram、usage、64/1024-cycle throttle；还包含 aggregator data-loss |
| PUNIT C-Die  | `0x22806802` | 6784  | 6      | Aggregate Core C-state、per-core C0、energy/policy 以及 3 个 64-bit FIVR Health monitor                             |
| OOBMSM RMID  | `0x477e9373` | 6160  | 6      | CHA × RMID 的 RDT MBM local/total memory transactions 和 CMT/cache monitoring                                    |
| TOPO Leaf    | `0x3d4bb41a` | 24    | 8      | MCTP EID、Domain ID、UPI link enable、当前 socket ID 等拓扑字段                                                          |
| TOPO Root    | `0x3d4bb40a` | 48    | 2      | CHA 0–63 enable mask 等 root topology                                                                           |
| PUNIT IO-Die | `0x22491753` | 6272  | 4      | IO PUNIT、socket EPB 和 3 个 FIVR monitor；当前 FIVR raw 为 `DEADBEEF` unavailable sentinel                           |
| OOBMSM QAT   | `0x6e94ffa0` | 176   | 4      | QAT0/QAT1 PCIe inbound/outbound 累计 MB，以及 page/translation/read/get-to-put latency                              |


实例数合计：

```text
6 + 6 + 6 + 8 + 2 + 4 + 4 = 36
```

生产 metadata 使用 Intel PMT support repository 中的 GNR XML。仓库内旧 `xml/pmt.xml` 的 PUNIT size 不是 avc01 当前 firmware 的 6784/6272，不能用于生产解释。

## 5. 36 个 Redfish Aggregator 完整清单

标签含义：

- `DeviceId=0/1`：BMC 中的两颗 CPU，通常可读作 Socket 0/1；
- `AccessId`：BMC 暴露的 MCTP over PCIe telemetry access，不是温度传感器坐标；
- `SourceId`：同一个 Access 下的数据域编号；
- 数据域必须结合 GUID 判断，不能只看 SourceId。


| #   | Device | Access | Source | GUID         | 数据域       |
| --- | ------ | ------ | ------ | ------------ | --------- |
| 1   | 0      | 25     | 2      | `0x22473996` | CORE      |
| 2   | 0      | 25     | 0      | `0x22806802` | C-Die     |
| 3   | 0      | 25     | 1      | `0x3d4bb41a` | TOPO Leaf |
| 4   | 0      | 25     | 3      | `0x477e9373` | RMID      |
| 5   | 0      | 26     | 2      | `0x22473996` | CORE      |
| 6   | 0      | 26     | 0      | `0x22806802` | C-Die     |
| 7   | 0      | 26     | 1      | `0x3d4bb41a` | TOPO Leaf |
| 8   | 0      | 26     | 3      | `0x477e9373` | RMID      |
| 9   | 0      | 27     | 2      | `0x22473996` | CORE      |
| 10  | 0      | 27     | 0      | `0x22806802` | C-Die     |
| 11  | 0      | 27     | 1      | `0x3d4bb41a` | TOPO Leaf |
| 12  | 0      | 27     | 3      | `0x477e9373` | RMID      |
| 13  | 0      | 28     | 0      | `0x22491753` | IO-Die    |
| 14  | 0      | 28     | 1      | `0x3d4bb41a` | TOPO Leaf |
| 15  | 0      | 28     | 2      | `0x6e94ffa0` | QAT       |
| 16  | 0      | 29     | 0      | `0x22491753` | IO-Die    |
| 17  | 0      | 29     | 1      | `0x3d4bb40a` | TOPO Root |
| 18  | 0      | 29     | 2      | `0x6e94ffa0` | QAT       |
| 19  | 1      | 157    | 0      | `0x22491753` | IO-Die    |
| 20  | 1      | 157    | 1      | `0x3d4bb40a` | TOPO Root |
| 21  | 1      | 157    | 2      | `0x6e94ffa0` | QAT       |
| 22  | 1      | 248    | 2      | `0x22473996` | CORE      |
| 23  | 1      | 248    | 0      | `0x22806802` | C-Die     |
| 24  | 1      | 248    | 1      | `0x3d4bb41a` | TOPO Leaf |
| 25  | 1      | 248    | 3      | `0x477e9373` | RMID      |
| 26  | 1      | 249    | 2      | `0x22473996` | CORE      |
| 27  | 1      | 249    | 0      | `0x22806802` | C-Die     |
| 28  | 1      | 249    | 1      | `0x3d4bb41a` | TOPO Leaf |
| 29  | 1      | 249    | 3      | `0x477e9373` | RMID      |
| 30  | 1      | 250    | 2      | `0x22473996` | CORE      |
| 31  | 1      | 250    | 0      | `0x22806802` | C-Die     |
| 32  | 1      | 250    | 1      | `0x3d4bb41a` | TOPO Leaf |
| 33  | 1      | 250    | 3      | `0x477e9373` | RMID      |
| 34  | 1      | 251    | 0      | `0x22491753` | IO-Die    |
| 35  | 1      | 251    | 1      | `0x3d4bb41a` | TOPO Leaf |
| 36  | 1      | 251    | 2      | `0x6e94ffa0` | QAT       |


按 Access 可以更直观地理解：


| Socket | Access      | 其中包含的数据域                                     |
| ------ | ----------- | -------------------------------------------- |
| 0      | 25、26、27    | 每个 Access 都有 CORE + C-Die + TOPO Leaf + RMID |
| 0      | 28          | IO-Die + TOPO Leaf + QAT                     |
| 0      | 29          | IO-Die + TOPO Root + QAT                     |
| 1      | 248、249、250 | 每个 Access 都有 CORE + C-Die + TOPO Leaf + RMID |
| 1      | 157         | IO-Die + TOPO Root + QAT                     |
| 1      | 251         | IO-Die + TOPO Leaf + QAT                     |


这些组合是 BMC 当前暴露的访问拓扑。仓库没有 Intel 官方的 `AccessId → physical compute die/rail` 对照表，因此文档不会把 Access 25、26、27 擅自命名成具体 die 编号。

## 6. Core 编号为什么重复

OOBMSM CORE XML为每个实例定义`Core 0–63`相关字段，例如`C0_TEMP`和
`C0_EN`。当前快照中，每个实例的Core 0–31温度有效，Core 32–63为0°C
disabled占位值。`Core N`来自XML字段和HELP，不是本文自行创建的slot名称。

同一个XML Core编号会在不同Aggregator中重复，例如：

```text
AGG[D0/A25/S2] · Core 17
AGG[D0/A26/S2] · Core 17
AGG[D0/A27/S2] · Core 17
```

它们是三条不同 time series，当前值也可能不同。因此：

- `AGG[D0/A27/S2]`先用`DeviceId + AccessId + SourceId`定位Aggregator；
- GUID `0x22473996`和Size 14496确认它采用CORE XML；
- `Core 17`直接对应XML中的`C17_*`字段和HELP描述；
- 完整逻辑定位键是
  `DeviceId + AccessId + SourceId + GUID/Size + XML field`；
- 不能只凭名称把它等同于 Linux global CPU 17；
- `AccessId` 不是温度传感器的物理坐标。

当前硬件有96 physical cores/socket；每个Socket的3个CORE aggregator各有32个
当前enabled的Core字段，因此数量上正好是`3 × 32 = 96`。这是当前实测数据
支持的覆盖数量，但在没有平台owner正式映射表前，不能把这些XML Core字段强行
换算成OS Core 0–95。

## 7. C-Die FIVR 的 96 个 Slot

每个 C-Die aggregator 有 3 个 64-bit monitor，每 2 bits 是一个状态码：

```text
3 monitors × 32 slots = 96 logical FIVR slots / C-Die aggregator
```

当前 6 个 C-Die 实例共输出 576 个 slot code，每个采集来源均为 0。Slot 不是 Core：XML 没有 `slot → core/rail` 映射，也没有 code 0/1/2/3 的官方枚举。

如果未来出现非零，Dashboard 可以定位到：

```text
DeviceId + AccessId + monitor + slot + code + CollectionMode
```

但不能仅凭公开 XML指出具体供电 rail 或物理 Core。

## 8. Local 与 Redfish 如何对应


| 维度               | Redfish          | Local            |
| ---------------- | ---------------- | ---------------- |
| `CollectionMode` | `redfish`        | `local`          |
| `PMTEndpoint`    | `avc01`          | `avc01`          |
| `DeviceId`       | BMC CPU ID 0/1   | hostname `avc01` |
| `AccessId`       | MCTP Access ID   | sysfs `telemX`   |
| `AccessType`     | `MCTP over PCIe` | `sysfs`          |
| `SourceId`       | BMC 0/1/2/3      | receiver 当前固定为 0 |
| 实例数              | 36               | 36               |
| Metric names     | 5,285            | 5,285            |
| Time series      | 32,710           | 32,710           |


两侧使用同一 `(GUID, Size)` XML 解码，并已对 FIVR raw word 验证一致。但仓库当前没有静态的 `Redfish AccessId ↔ Local telemX` 对照表，所以不能靠 AccessId 字符串直接一一配对。

可靠的交叉验证顺序是：

1. 相同 metric name；
2. 相同 `PMTGuid` 和 `PMTSizeBytes`；
3. 分别选择 Redfish 的 `DeviceId/AccessId` 与 Local 的 `telemX`；
4. 对齐采样时间后比较值。



## 9. 指标数量为什么远大于 Aggregator 数

一个 aggregator 会按 XML 解码出很多 metric names；每个名称又会因为 labels 形成多条 time series。

```text
36 aggregators
  → 5,285 unique metric names
  → 32,710 Redfish series
  + 32,710 Local series
  = 65,420 current series
```

因此：

- aggregator 数不是 metric 数；
- metric name 数不是 series 数；
- Prometheus 每 15 秒保存的新 sample 也不是新的 series。

完整逐 metric 定义见 `pmt-metrics-catalog.csv`；类别、类型、单位和正确查询方式见 `pmt-metrics-summary.md`。

## 10. 这些结论来自哪里

本文把三类证据交叉使用：

1. `lscpu` 和 `numactl --hardware`：确认 2 个 Socket、每 Socket 96 个物理 Core、整机 6 个 NUMA nodes；
2. BMC Redfish `TelemetryData`：确认每条记录的 `DeviceId`、`AccessId`、`SourceId`、`GUID`、`Size` 和 Access 类型，并得到36个实例清单；
3. 生产 metadata `/opt/intel-pmt/xml/pmt.xml` 及 GNR XML：用 `GUID + Size` 确认 aggregator 类型、字段布局、转换公式和 `C0_*`到`C63_*` Core字段定义。

当前快照进一步显示，每个CORE XML实例虽然定义Core 0–63字段，但只有Core
0–31 enabled，Core 32–63是disabled占位。因此“每个CORE aggregator当前有
32个enabled Core字段”是实测结论。

证据边界：

- 可以确认 `D0/D1` 在当前 BMC inventory 中分别是两颗 CPU，通常读作 Socket 0/1；
- 可以确认 A25/A26/A27 与 A248/A249/A250 各自包含一个 CORE aggregator；
- 可以确认每个 CORE aggregator 当前有32个enabled XML Core字段；
- 不能从公开 XML确认某个Aggregator的Core N字段对应哪个Linux CPU；
- `AccessId` 是 BMC telemetry access 标识，不应擅自解释成具体 compute die、rail 或物理通道编号。

## 11. 常用拓扑查询

```promql
# 两条来源各有多少 metric names
count(count by (__name__) ({PMTEndpoint="avc01",CollectionMode="redfish"}))
count(count by (__name__) ({PMTEndpoint="avc01",CollectionMode="local"}))

# Redfish 当前有哪些 aggregator 实例
count by (DeviceId,AccessId,SourceId,PMTGuid,PMTSizeBytes) (
  {PMTEndpoint="avc01",CollectionMode="redfish"}
)

# 查看某个逻辑 Core 温度的所有来源
{__name__=~".*_temp_c17_temp_celsius",
 PMTEndpoint="avc01",CollectionMode="redfish"}
```

读取结果时始终保留 `DeviceId`、`AccessId`、`PMTGuid` 和 `CollectionMode`，避免把不同 aggregator 或两条采集来源重复聚合。