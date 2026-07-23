# Intel PMT Customer Dashboard 五栏方案（已归档）

> **状态：已否决的五栏极简方案草案，不代表当前Dashboard。**
> 该方案因过度删除技术内容、增加文字面板且未解决实际视觉层级而被否决。
> 当前8栏技术演示版继续保留；新的架构化 GNR Overview 已独立实现。
>
> **当前设计、Panel解释、单位规则和未解决语义请阅读
> `gnr-telemetry-dashboard-guide.md`。本文仅保留为被否决方案的历史记录。**

## 0. 文档目的

本文是 avc01 Intel PMT 客户演示 Dashboard 的设计依据，不是某个 panel 的操作说明。它回答四类问题：

1. 为什么客户主页只展示少量指标；
2. 每个分区要向客户讲述什么；
3. 为什么 usage、QAT、data loss 等指标没有放在主页；
4. Dashboard 如何从 PMT、Collector、Prometheus 和 Grafana 获得并解释数据。

当前实现：

| 项目 | 当前值 |
|---|---|
| 客户 Dashboard UID | `pmt-avc01-redfish` |
| 客户 Dashboard 标题 | `Intel PMT · Customer Telemetry Story` |
| 客户 Dashboard 结构 | 5 rows、20 entries、15 个内容 panels |
| 高级搜索 UID | `pmt-avc01-metric-explorer` |
| 高级搜索结构 | 1 row、5 entries、4 个内容 panels |
| 默认来源 | Redfish |
| Dashboard refresh | 20 秒 |
| 源生成器 | `tools/otel/generate_pmt_dashboard.py` |

生成后的 JSON 不是主要维护入口。所有布局、PromQL、变量、文字和链接都应在生成器中修改。

## 1. 目标用户与使用场景

### 1.1 主要用户

主要用户是第一次看到 Intel PMT 的客户、领导、合作伙伴和售前演示参与者。他们通常：

- 不知道 aggregator、AccessId、SourceId、RMID 或 crystal TSC；
- 不会区分 Prometheus gauge 与 counter；
- 不应先理解 5,285 个 metric names 才能看懂演示；
- 需要在几十秒内理解 PMT 能提供什么价值；
- 会把红色、`Unhealthy`、`data loss` 等文字直接理解为服务器故障。

### 1.2 次要用户

工程师和 PMT 开发人员仍需要：

- 查任意 metric；
- 查看原始 labels；
- 区分 Redfish 与 Local；
- 检查 counter rate、gauge delta、FIVR packed fields 和 data loss。

这两类用户的需求冲突。把全部功能放在同一个 Dashboard 会产生信息噪声，所以设计采用：

```text
客户主页：讲清楚价值和当前现象
    ↓ 明确跳转
Advanced Metric Explorer：执行底层技术查询
    ↓ 文档链接
Metric family reference / CSV catalog：解释语义和边界
```

## 2. 核心设计原则

### 2.1 一屏只回答一个问题

每个 row 只回答一个客户问题：

1. PMT 演示是否就绪；
2. CPU 当前温度表现如何；
3. CPU 在什么频率、温度和电压区间运行；
4. FIVR monitor 是否提供可解释信号；
5. 工程人员去哪里下钻。

不再按照“Collector有哪些metric families”组织页面。硬件或XML的数据结构适合工程文档，不适合作为客户故事。

### 2.2 状态、趋势和分布不能混在同一视觉层

- **状态卡**回答“现在是什么状态”；
- **时间序列**回答“随时间怎样变化”；
- **驻留分布**回答“统计窗口内时间主要花在哪里”；
- **技术表格**回答“具体是哪条series或label”。

客户主页不把这四种语义混在同一 panel，也不把 counter 绝对值伪装成状态。

### 2.3 绿色不是整机健康认证

`Ready` 只表示 PMT 采集链路当前可用于演示。

`Healthy` 只表示本项目定义的 C-Die FIVR 运营条件成立：

- FIVR 数据可用；
- 公开的 2-bit status slots 全部为 0。

它们都不等于：

- 完整服务器健康；
- Intel 官方硬件诊断结论；
- RAS、BMC SEL、MCA 和全部电源轨均无错误。

### 2.4 不让低优先级质量计数制造客户焦虑

`agg_data_loss_count_total` 是技术质量 counter，不是服务器故障灯。它可能包含历史累计值。真正需要调查的是持续新增行为，而不是绝对值非零。

因此客户主页：

- 不展示 data-loss 卡片；
- 不展示 data-loss trend；
- 不把短暂新增映射为整机 `Unhealthy`；
- 只在技术文档和高级诊断中解释。

### 2.5 未知语义不能包装成精确业务指标

当前PMT XML没有为所有字段提供完整单位或codebook。以下内容不能为了“看起来完整”而猜测：

- MBM transaction 到 bytes 的换算；
- accumulated energy 到 joules 的换算；
- usage meter 到 Linux CPU% 的换算；
- FIVR slot 到具体 rail/Core 的映射；
- FIVR code 1/2/3 的官方含义；
- mesh histogram bin 到 MHz 的换算。

## 3. 客户故事与页面信息架构

## 3.1 Row 01：Customer Demo Overview

客户进入页面后先回答：

> 数据能不能看？CPU热不热？FIVR monitor有没有需要进一步检查的信号？

### PMT Demo Status

`Ready` 必须同时满足：

1. 所有目标 PMT Collector 的 Prometheus `up` 为 1；
2. 当前筛选范围内最旧的活跃 PMT sample 不超过 45 秒。

它是“演示就绪”状态，而不是硬件健康状态。

### Highest Core Temperature

显示当前全部有效 Core series 的最高温度：

- 单位为 °C；
- 0°C disabled slots 被排除；
- 80°C 进入黄色；
- 95°C 进入红色。

阈值用于演示视觉分级，不替代平台正式 thermal specification。

### C-Die FIVR Monitor

显示 `Healthy`、`Check Required` 或 `No Data`：

- `Healthy`：数据可用且全部公开 slots 为 0；
- `Check Required`：至少一个公开 slot 非零；
- `No Data`：无法获得可解释数据。

### CPU Core Temperature Trend

只显示最大值和平均值，不在总览里同时绘制几十条 Core：

- Max 用于观察热点；
- Average 用于观察整体温度水平；
- Redfish 与 Local 同时选择时按 `CollectionMode` 分开。

## 3.2 Row 02：CPU Thermal Behavior

这一栏从总览的一个温度数字，下钻到热点位置与历史。

### Current Hotspots

显示当前最热的 12 条有效 Core series。客户可看到热点是否集中，而不是只看到一个全局最大值。

展示名称使用：

```text
Socket <DeviceId> · Group <AccessId> · Core <local core>
```

这里的 Core 是 aggregator local Core slot，不是 Linux CPU 编号。`Group` 是面向客户的简化显示词，底层仍是 AccessId。

### Hotspot History

显示当前最热 Core 在所选 Dashboard 时间范围内的温度曲线。它回答：

- 热点是持续存在还是短暂尖峰；
- 多个Core是否同时升温；
- workload开始与停止时温度怎样变化。

不再保留重复的 Thermal Envelope 和 Selected Core panels，避免同一温度事实被四种相似图重复表达。

## 3.3 Row 03：Core Operating Profile

这一栏展示 PMT 相比普通瞬时监控更有价值的“驻留画像”：

- Frequency Residency；
- Temperature Residency；
- Voltage Residency。

顶部两个变量只服务这一栏：

| 变量 | 含义 |
|---|---|
| `03 Local Core` | 选择 aggregator XML 中的 local Core slot |
| `03 Profile window` | 选择 2m、5m、10m、15m、30m 或 1h |

每个图表示：

> 在所选窗口内，这个 Core 有多少比例的有效驻留增量落在每个 bucket。

它们不是：

- 当前瞬时频率；
- 当前瞬时电压；
- Linux CPU utilization；
- Prometheus 原生 histogram。

低于 0.1% 的 bucket 被隐藏，以降低视觉噪声。

## 3.4 Row 04：Voltage Regulator Signals

FIVR 是 PMT 的差异化能力，但底层 packed word 对客户不可读。本栏只显示三个结果。

### C-Die Monitor Result

将 packed word、availability 和 2-bit slots 汇总成 `Healthy`、`Check Required` 或 `No Data`。

### Non-Zero Signals

显示当前非零 2-bit slots 数量，范围 0–576（取决于当前筛选范围）。

这个数量用于表达“是否存在需要下钻的信号”，不能解释为故障 Core 数量或故障 rail 数量。

### IO-Die Data Status

显示 `Available`、`DEADBEEF` 或 `No Data`。

`DEADBEEF` 是 firmware data-unavailable sentinel，不是硬件错误码。使用橙色而不是红色，避免与确认故障混淆。

### 解释文字

状态卡下方固定说明：

- `Healthy` 是项目运营约定；
- `DEADBEEF` 是数据不可用；
- 公开 XML 没有 slot/rail 和 codebook；
- 需要底层定位时进入 Explorer 和 FIVR 专项文档。

## 3.5 Row 05：Advanced Tools

客户故事到第04栏结束。第05栏只有一个明确动作：

> 打开 Advanced Metric Explorer。

主Dashboard不再显示全量metric搜索框、data-loss表格、inventory、usage、throttle、QAT或MBM。

## 4. 为什么采用独立Metric Explorer

Grafana原生dashboard variable只能显示在页面顶部，不能嵌入某个row。因此无法把`Search metric`输入框真正移动到第05栏内部。

如果搜索框仍留在客户主页顶部，会产生三个问题：

1. 客户会误以为必须先选metric才能使用页面；
2. 搜索框与底部结果相距很远；
3. 5,285个技术名称破坏客户演示的第一印象。

独立Explorer页面解决这些问题：

- 搜索框位于页面顶部；
- 使用说明紧随搜索框；
- Raw History、Current Series和5-Minute Change直接位于下方；
- 提供返回客户主页和打开Metric family reference的链接。

## 5. 视觉设计规范

### 5.1 页面密度

- 客户主页最多5个rows；
- 同一行最多3张状态卡；
- 不在客户主页展示大规模技术表格；
- 不使用超过12条Core曲线；
- 同一事实不以多个近似panel重复展示。

### 5.2 颜色语义

| 颜色 | 语义 |
|---|---|
| 绿色 | 当前条件满足、数据可解释或处于正常展示范围 |
| 黄色 | 温度升高，需要关注趋势 |
| 橙色 | 数据不可用或能力未被激励，不等于硬件故障 |
| 红色 | 明确超出当前展示阈值或需要进一步检查 |
| 灰色 | No Data、未知或不适用 |
| 蓝色 | 中性的趋势与分布 |

状态卡只给文字/数值着色，不使用大面积整卡背景色，避免页面像告警墙。

### 5.3 标题

客户panel标题使用业务问题，而不是原始metric名称：

- `Highest Core Temperature`，而不是温度metric正则；
- `Current Hotspots`，而不是 `topk(12, ...)`；
- `C-Die Monitor Result`，而不是 packed word字段名。

底层metric名称只出现在Explorer、catalog和技术文档。

### 5.4 描述

每个panel description必须同时说明：

1. 这个panel展示什么；
2. 0或No Data怎样解释；
3. 最常见的误读是什么。

## 6. PMT采集技术背景

## 6.1 数据路径

```text
CPU内部硬件/firmware telemetry
  → PMT aggregator region
    → Redfish BMC Collector 或 OS Local Collector
      → OpenTelemetry/Prometheus exporter
        → Prometheus TSDB
          → Grafana
```

当前平台同时有Redfish和Local两条链路。它们观察的是同一硬件telemetry，不是两份独立物理测量。

## 6.2 三层时间

必须区分：

1. CPU/firmware内部更新周期；
2. PMT Collector约20秒读取周期；
3. Prometheus约15秒scrape周期。

Prometheus可能在两个PMT真实更新之间保存重复值。因此：

- 短窗口rate可能出现阶梯；
- Dashboard refresh 20秒不等于每个metric内部20秒更新；
- data loss的processing cycle不等于Collector的20秒。

## 6.3 公共筛选标签

客户Dashboard查询统一保留：

```promql
PMTEndpoint="$endpoint",
CollectionMode=~"$mode",
DeviceId=~"$device",
AccessId=~"$access",
PMTGuid=~"$die"
```

默认只选择Redfish，防止Redfish与Local被重复求和。

## 6.4 温度

温度metric是gauge，直接查询当前值。当前平台的0°C全部对应disabled local Core slots，所以客户查询统一使用：

```promql
temperature_metric > 0
```

这不是通用规则；迁移到其他CPU时必须重新验证0值语义。

## 6.5 驻留分布

Frequency、Temperature和Voltage residency分别由12条独立counter构成。

对每个bucket：

```text
bucket_rate = rate(bucket_counter[window])
```

驻留占比：

```text
100 × bucket_rate / sum(all_12_bucket_rates)
```

分母使用极小正数保护，避免无增量窗口除零。只展示大于0.1%的结果。

## 6.6 FIVR

原始FIVR monitor是64-bit packed word，每2 bits一个slot。Receiver派生：

- `.available`；
- `.status_00`到`.status_31`；
- `.nonzero_status_count`。

`0xDEADBEEF`或`0xDEADBEEFDEADBEEF`被识别为firmware poison/data-unavailable。

公开XML只说明“2 bits per FIVR”，没有公开：

- slot到rail/Core的映射；
- code 0/1/2/3的正式枚举。

所以Dashboard必须保留“项目运营约定”提示。

## 7. 从客户主页移除的指标

### 7.1 Data loss

移除原因：

- 绝对值包含历史累计；
- 短暂新增只说明telemetry质量窗口；
- 不等于网络丢包；
- 不直接证明CPU硬件故障；
- 放在首页容易制造错误恐慌。

工程分析时应观察相邻真实PMT更新的delta，以及workload结束后是否仍持续增长。

### 7.2 Experimental usage meter

移除原因：

- 是U64.38.26累计relative-usage level；
- rate数值很小；
- 不是Linux CPU%；
- Intel没有公开到利用率百分比的换算。

### 7.3 64/1024-cycle throttle

移除原因：

- cycle是硬件节流观察窗口，不是aggregator更新周期；
- 单独非零不能解释thermal、power或VR根因；
- 客户需要额外技术背景才能正确阅读。

### 7.4 QAT throughput与latency

移除原因：

- NPB/PAMPAR CPU workload不会调用QAT；
- 0表示Idle，不代表QAT不可用；
- 在没有QAT workload的客户Demo中没有叙事价值。

### 7.5 RDT MBM与memory counter

移除原因：

- 当前HELP未提供可靠transaction到bytes换算；
- 不能标成GB/s；
- RMID到具体应用的映射不在当前Dashboard中。

这些metric仍可通过Explorer和catalog访问。

## 8. PromQL与显示规则

### 8.1 Counter

Counter通常使用：

```promql
rate(metric[window])
increase(metric[window])
```

不把绝对值解释为当前事件强度。

### 8.2 Gauge

Gauge通常直接显示当前值。只有明确需要窗口变化时才使用`delta()`。

### 8.3 No Data

No Data必须与数值0分开：

- 0可能是合法状态；
- 0可能是Idle；
- No Data表示查询没有有效series；
- FIVR poison使用独立availability语义。

### 8.4 Redfish与Local

选择两种CollectionMode时：

- 趋势按CollectionMode分组；
- 不直接把两种来源求和；
- 对同一硬件字段做交叉验证，而不是增加样本量。

## 9. 维护流程

修改Dashboard时：

1. 编辑`tools/otel/generate_pmt_dashboard.py`；
2. 运行生成器；
3. 检查生成JSON；
4. 对所有PromQL替换变量后调用Prometheus API；
5. 确认Grafana API已加载两个UID；
6. 验证主页面没有`metric`搜索变量；
7. 验证Explorer具有`Search metric`；
8. 更新本文和工作流文档中的panel/target数量。

运行：

```bash
cd /root/projects/Intel-PMT
python3 tools/otel/generate_pmt_dashboard.py
```

生成：

```text
tools/otel/dashboards/pmt-redfish-comprehensive.json
tools/otel/dashboards/pmt-metric-explorer.json
```

部署：

```text
/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json
/var/lib/grafana/dashboards/pmt-backend-test/pmt-metric-explorer.json
```

## 10. 验收标准

客户主页必须满足：

- 不需要理解metric名称即可完成演示；
- 前30秒可以解释三个总览卡；
- 页面最多5个rows；
- data loss不在首页；
- QAT Idle不占据客户视线；
- usage meter不被描述成CPU%；
- 0°C disabled slots不参与温度；
- Residency window可调；
- FIVR Healthy与DEADBEEF均有边界说明；
- 主页面没有全量metric搜索框；
- Explorer搜索框和结果相邻；
- 所有PromQL通过当前Prometheus API验证；
- Redfish默认值不会与Local重复聚合。

## 11. 非目标

本Dashboard不是：

- 完整BMC硬件健康页面；
- Linux CPU性能Dashboard；
- RAS/MCA/SEL故障诊断工具；
- 功耗、内存带宽或QAT benchmark评分工具；
- Intel官方FIVR codebook的替代品；
- 用于训练ML模型的最终特征数据集。

实验导出、异常注入和ML特征工程应使用完整trace、metric catalog和质量mask，而不是从客户Dashboard截图或读取视觉聚合值。
