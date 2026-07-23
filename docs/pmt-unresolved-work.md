# PMT待完成事项 / PMT Open Work

> **Intel Internal Only**
> 记录当前尚未闭环的功能和语义问题。

## 当前状态

- Redfish OOB和Local in-band均已完成采集；
- 两条路径各发现36个Aggregator实例；
- 两侧均使用`GUID + Size`选择XML；
- 两侧的Aggregator类型和数量一致；
- 目前缺少物理发现路径，不能权威地把`D/A/S`映射到`telemN`；
- 5,285个metric names中有2,295个尚无可靠物理单位。

## 待完成事项

| 优先级 | 事项 | 当前情况 | 完成条件 |
|---|---|---|---|
| P0 | 统一OOB、in-band和Core身份语义 | OOB使用`DeviceId/AccessId/SourceId`，Local使用`host/telemN`；`Core 0–31`是XML字段，不是Linux CPU。当前没有物理实例和Core映射 | 建立`D/A/S ↔ EID/Domain/BDF ↔ telemN`以及`Aggregator Core N ↔ APIC/Linux CPU`映射，并定义Canonical ID和namespaced labels |
| P1 | 完成FIVR可用性和状态语义 | C-Die当前为0且available；IO-Die持续返回`DEADBEEF`；缺少slot到rail/core及code 0–3定义 | 明确IO-Die支持状态和`DEADBEEF`原因，并补齐slot/code映射 |
| P1 | 补齐Metric单位 | relative usage、MBM/CMT、memory、energy、C-state、PEM等只能显示Raw | 为适用GUID/firmware补齐scale、公式、time base、unit及reset/wrap规则 |
| P1 | 补齐Data-loss定义 | 已读取不完整更新周期累计值，但不知道总processing cycles和单次影响范围 | 明确counter定义、更新周期、分母、loss ratio和严重性判定 |

## OOB与in-band目前是什么样

| 项目 | Redfish OOB | Local in-band |
|---|---|---|
| Dashboard定位 | `AGG[D1/A248/S2] · Core 0` | `AGG[telem13] · Core 0` |
| 设备身份 | `DeviceId` | hostname/endpoint |
| 访问身份 | `AccessId + SourceId` | `telemN` |
| 访问方式 | MCTP over PCIe | Linux sysfs |
| 布局识别 | `GUID + Size` | `GUID + Size` |
| 当前缺失 | EID/Domain/BDF关系 | sysfs parent/BDF关系 |

不能只根据`GUID+Size`、枚举顺序或数值相似，就宣布两侧是同一个物理Aggregator。
第一优先级必须使用physical discovery path：

```text
OOB D/A/S
↔ MCTP EID / Domain / Provider
↔ PCI BDF
↔ Local sysfs parent / telemN
```

## FIVR当前准确结论

这里需要纠正：当前不是C-Die持续返回`DEADBEEF`。

| Die | 实测结果 | 当前解释 |
|---|---|---|
| C-Die | 三个64-bit words均为`0x0000000000000000` | available；Dashboard按项目约定显示Healthy |
| IO-Die | 三个64-bit words均为`0xDEADBEEFDEADBEEF` | firmware sentinel；数据unavailable |

待确认：

1. IO-Die字段是否在当前firmware中未实现；
2. 是否需要BIOS/firmware开关；
3. 当前provider/source和offset是否正确；
4. `DEADBEEF`的正式定义；
5. code 0–3及slot到rail/core的映射。

## 最需要确认单位的Metrics

| Family | 当前展示 | 需要确认 |
|---|---|---|
| Core relative usage | raw rate/s | 是否可转换为利用率/% |
| RDT MBM | raw transactions/s | transaction size及local/total定义 |
| RDT CMT | raw rate | cache-line到bytes转换 |
| Memory channel | raw delta | scale、time base及带宽公式 |
| Accumulated energy | raw delta | joule scale及wrap/reset |
| C-state | raw | 单位和counter/gauge生命周期 |
| EPB/PEM | raw enumeration | bit/code定义 |
| FIVR | availability/raw slot | code和rail/core映射 |

单位说明至少需要包含：适用GUID、CPU stepping、firmware版本、raw type、转换公式、
物理单位、counter/gauge类型和reset/wrap规则。
