# avc01 Intel PMT Metrics 完整清单摘要

> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 从当前运行的 Collector 与 Prometheus 自动生成。它是初学者入口；5,285 个名称的逐条HELP、family、数值语义、查询建议、单位和labels在 `pmt-metrics-catalog.csv`，完整family解释在 `pmt-metric-family-reference.md`。

## 0. 初学者先理解三个词

- **Metric name**：一种测量项目，例如某个 core 的当前温度。
- **Time series**：同一个名称加上一组 labels 后形成的独立数据流。同一温度名称会因 socket、aggregator 和采集来源产生多条 series。
- **Sample/data point**：某条 time series 在某一时刻的值。Prometheus 每次抓取都会增加新的 sample，而不是增加新的 metric name。

`5,285 names` 与 `65,420 series` 并不矛盾：后者包含 Redfish/local、DeviceId、AccessId、GUID 等不同标签组合。当前 CPU 与 36 个 aggregator 的完整结构见 `pmt-platform-topology.md`。

## 1. 当前规模

- PMT metric 名称数：**5285**
- 当前 PMT time series 数：**65420**
  - BMC Redfish：**32710**
  - OS 带内：**32710**
- 缺少 HELP 说明的 metric 数：**0**
- 单位来自 Prometheus metadata：**0**
- 单位可从 OpenTelemetry metric 后缀推断：**2990**
- 单位无法可靠确定：**2295**
- 当前人工解释的metric families：**38**
- 未归类metric names：**0**
- 完整family参考：`docs/pmt-metric-family-reference.md`
- 完整逐条目录：`docs/pmt-metrics-catalog.csv`

## 2. 完整指标类别

下面覆盖当前全部 5,285 个名称。分类由名称和HELP关键词自动生成，便于导航；最终物理语义仍以每行HELP、family guide和匹配XML为准。

| 类别 | 名称数 | 主要内容与正确读法 |
|---|---:|---|
| 使用量与驻留/Usage & Residency | 1092 | Core 活跃度、C-state、频率/温度/电压区间驻留时间；counter 通常看 rate/increase。 |
| 内存/Memory | 1067 | RDT MBM local/total 等内存事务累计计数；没有官方字节换算时使用 counts/s，不写成带宽。 |
| 温度/Temperature | 832 | Core 当前温度和温度 histogram；即时温度为 °C，histogram 的 `_second_total` 是区间累计时间。 |
| 频率/Frequency | 781 | 频率区间 histogram；数值是各频率区间累计秒数，不是瞬时 MHz。 |
| 电压/Voltage | 768 | 电压区间 histogram；数值是各电压区间累计秒数，mV 范围写在 HELP 中。 |
| 状态与配置/Status & Configuration | 247 | enable 位、socket/拓扑状态、FIVR 拆分码等；通常为无量纲枚举或 0/1。 |
| 功率与能量/Power & Energy | 160 | 能量累加器及其时间戳；若 XML 未给换算单位，不根据名称猜测 joule/watt。 |
| 节流/Throttle | 128 | Core 在指定 cycle window 中发生 throttle 的累计次数。 |
| 其他计数器/Other | 118 | 无法仅靠关键词可靠归入其他类别的策略、计数和配置字段；以 HELP/XML 为准。 |
| 缓存与CHA/Cache & CHA | 64 | CHA enable、LLC/RDT CMT 等缓存与 Home Agent 信息。 |
| 延迟/Latency | 22 | QAT page request、translation、read、get-to-put 等平均或最大延迟，通常为 ns。 |
| 互连与I/O/Interconnect & I/O | 4 | QAT PCIe inbound/outbound 累计 MB；使用 rate() 后才是 MB/s。 |
| 采集质量/Data loss | 2 | Aggregator 未能在内部周期更新全部 sample 的累计次数和最后时间戳；不等于网络丢包。 |

## 3. Prometheus 类型与查询方式

| 类型 | metric 名称数 |
|---|---:|
| `counter` | 4447 |
| `gauge` | 838 |

- **gauge**：当前状态或测量值，例如温度、enable、FIVR code；通常直接查询。
- **counter**：从启动或复位起累计，只会上升或归零重启；通常用 `rate(metric[5m])` 看每秒变化，用 `increase(metric[5m])` 看五分钟新增量。
- 名称以 `_second_total` 结尾的 frequency/temperature/voltage histogram 是“落在该区间的累计秒数”，不是瞬时值。

## 4. 单位为什么有时为空

当前 Prometheus metadata 没有提供任何 PMT unit。生成器只在名称含标准 OpenTelemetry 后缀时推断单位，并在 `unit_source` 中标记来源：

| `unit_source` | 含义 | 是否可直接使用 |
|---|---|---|
| `prometheus_metadata` | exporter 明确提供的单位 | 是；当前数量为 0 |
| `metric_name_suffix` | 从 `_celsius`、`_nanoseconds`、`_megabytes_total`、`_second_total` 等后缀推断 | 可以，但必须结合 HELP 理解累计量还是瞬时量 |
| `unspecified` | metadata、名称后缀都不能可靠确定 | 不要猜；查 HELP、XML 或平台 owner |

重要例外：`agg_data_loss_timestamp_total` 的 HELP 指明它是 25 MHz crystal TSC tick，但名称没有标准 tick 后缀；能量累加器也不能仅凭 `energy` 猜成 joule。完整当前值和每条 series 的 labels 见 `pmt-bmc-snapshot.csv`。

## 5. 先看代表性指标族，再进入完整Family参考

`pmt-metric-family-reference.md`覆盖当前所有名称所属的family，并对每个family说明：含义、值的语义、推荐查询、正常/异常边界、代表性HELP和准确名称示例。下面只保留最常用入口：

| 指标/模式 | 含义 | 类型 | 单位/读法 |
|---|---|---|---|
| `c0_c1_c2_c3_temp_c0_temp_celsius` | Aggregator 局部 Core 0 当前温度 | gauge | °C；0°C 是 disabled 占位值 |
| `c0_freq_hist_r0_second_total` | Core 0 在 frequency range 0/C6 的累计驻留 | counter | seconds；对 12 个 bucket 的 rate 求占比 |
| `c0_temp_hist_r*_second_total` | Core 0 在各温度区间的累计驻留 | counter | seconds；区间范围见 HELP |
| `c0_volt_hist_r*_second_total` | Core 0 在各电压区间的累计驻留 | counter | seconds；mV 范围见 HELP |
| `c0_pvp_throttle_64_total` | 最近 64-cycle window 的 throttle 累计计数 | counter | count；观察 rate/increase |
| `cha0_rmid0_rdt_mbm_total` | CHA 0/RMID 0 memory transaction 累计值 | counter | 单位未定义；应显示 counts/s，不应擅自写 ops/s 或 bytes/s |
| `cha_enabled_mask_cha_0_en` | CHA 0 是否 enable | gauge | 无量纲 0/1 |
| `qat0_tl_bw_in_megabytes_total` | QAT0 PCIe inbound 累计 MB | counter | `rate(...[5m])` 后为 MB/s |
| `qat0_avg_*_nanoseconds` | QAT 平均延迟 | gauge | ns |
| `agg_data_loss_count_total` | Aggregator 未完整更新全部 sample 的累计周期数 | counter | count；只看 increase，不看绝对值是否非零 |
| `fivr_health_monitor_*_status_00`…`31` | 64-bit FIVR word 拆出的 2-bit slot | gauge | code 0–3；slot/枚举无官方映射 |

Data loss最重要的快速判断：绝对累计值非零不代表当前危险；相邻真实PMT更新的delta=0表示该窗口没有新增未完成周期；持续多个窗口增长、停止workload后仍增长，才是需要升级的数据质量问题。完整解释见family参考的 `data-loss-count` 章节。

## 6. 如何阅读完整 CSV

| 列 | 含义 |
|---|---|
| `metric_name` | Prometheus 查询时使用的准确名称 |
| `category` | 由名称和 HELP 自动归类，便于搜索；最终物理含义仍以 XML/HELP 为准 |
| `family_id` | 人工审核的metric family稳定标识；用于跳转family参考 |
| `family_title` | family的人读名称 |
| `type` | Prometheus metric 类型，例如 gauge/counter |
| `unit` | 明确或按标准 metric 后缀推断的单位；为空表示不能可靠确定 |
| `unit_source` | `prometheus_metadata`、`metric_name_suffix` 或 `unspecified` |
| `value_semantics` | 当前值、累计值、时间戳、状态码或驻留bucket应怎样理解 |
| `recommended_query` | 建议直接查询、使用rate/increase、归一化或与配对counter计算 |
| `caveat` | disabled、Idle、poison、未知单位、局部编号等关键误读边界 |
| `series_count` | 当前这个名称因为不同 labels 产生的 time series 数量 |
| `redfish_series_count` | BMC Redfish exporter 中的 time series 数量 |
| `inband_series_count` | OS 带内 exporter 中的 time series 数量 |
| `label_names` | 当前 exporter 中观察到的标签名 |
| `help` | PMT XML/receiver 暴露的官方说明，即每条 metric 的主要含义 |

查询示例：

```bash
# 查所有温度指标
rg ',温度/Temperature,' docs/pmt-metrics-catalog.csv

# 查某个准确名称、HELP 和单位
rg '^c0_c1_c2_c3_temp_c0_temp_celsius,' docs/pmt-metrics-catalog.csv

# 查单位尚未确定的指标
rg ',unspecified,' docs/pmt-metrics-catalog.csv
```

也可以用 LibreOffice/Excel 打开 CSV，按 `family_id`、`category`、`type`、`unit_source` 筛选。不要从头通读 5,285 行。

## 7. 进一步阅读

- 当前全部metric family的详细语义：`pmt-metric-family-reference.md`
- CPU、Core、36 个 aggregator 和标签：`pmt-platform-topology.md`
- 当前完整采集链路：`complete-pmt-collection-workflow.md`
- FIVR slot、poison 和语义边界：`gnr-fivr-health-collection-workflow.md`
- 单次 BMC 数值、label 与 magnitude：`pmt-bmc-snapshot.csv`

## 8. 重新生成

```bash
cd /root/projects/Intel-PMT
/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py
```

每次更新 PMT XML、切换 BMC 或升级 receiver 后，应重新生成。
