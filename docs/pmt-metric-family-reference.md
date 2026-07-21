# avc01 Intel PMT Metric Family 详细参考

> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 生成，并由 `pmt_metric_guides.py` 提供人工审核的运营语义。它按 family 解释当前全部 metric names；每个准确名称的 HELP、family、单位、推荐查询和注意事项见 `pmt-metrics-catalog.csv`。

## 0. 覆盖范围与阅读顺序

- 当前 metric names：**5285**
- 当前人工解释 families：**38**
- 当前 time series：**65420**（Redfish 32710 + Local 32710）
- 未归类名称：**0**

推荐阅读顺序：

1. 先读本文件第1–4节，理解类型、时间层次、标签和正常/异常边界；
2. 按业务域查找后面的family章节；
3. 最后到 `pmt-metrics-catalog.csv` 搜索准确metric name；
4. 若HELP仍未定义单位、枚举或物理映射，必须回到匹配XML或咨询platform owner，不能猜。

## 1. 一个metric必须回答的七个问题

阅读任何PMT metric时，都应依次确认：

1. **它来自哪个aggregator？** 看 `PMTGuid`、`DeviceId`、`AccessId`、`SourceId`；
2. **它是gauge还是counter？** gauge通常直接看，counter通常看rate/increase；
3. **单位是否权威？** `unit_source=unspecified`时禁止自行补单位；
4. **编号是局部还是全局？** `c22`通常是aggregator local Core slot，不是Linux CPU 22；
5. **0是什么含义？** 可能是Idle、disabled、有效状态码，也可能没有业务流量；
6. **多久真正更新一次？** PMT内部cycle、20秒Collector读取和15秒Prometheus scrape不是同一层；
7. **它能否代表硬件健康？** data loss、poison、enable和性能counter的风险边界完全不同。

## 2. Gauge、Counter与“名称看起来像Counter”

- **Gauge**：当前值或当前导出的状态，通常直接查询；但部分XML累计字段当前仍被导出为gauge，必须结合HELP和单调性判断。
- **Counter**：累计值。绝对值通常没有当前健康意义；`rate(metric[5m])`看每秒变化，`increase(metric[5m])`看窗口新增量。
- **Histogram buckets**：这里不是Prometheus原生histogram，而是12条独立累计驻留counter；应先对每个bucket求rate，再归一化。
- **Timestamp counter**：`*_timestamp_total`可能是25MHz内部ticks，不是事件数量，也不是Unix时间。

不要只根据 `_total`、`counter`、`seconds` 等名称片段做结论；本项目以XML SampleType、HELP、转换公式和实测变化共同判断。

## 3. 三层采样时间

```text
硬件/firmware内部更新周期（未公开，可能远快于20秒）
  → PMT Collector每20秒读取aggregator region
    → Prometheus约每15秒抓取exporter，期间可能重复保存同一PMT值
```

因此短于PMT原生更新周期的rate窗口可能看到重复值；一条20秒PMT窗口内的data-loss delta也不是“丢了一个20秒snapshot”。

## 4. Data loss必须怎样解释

`agg_data_loss_count_total`是CPU/firmware直接提供的64-bit raw cumulative counter。它统计aggregator未能在一个内部processing cycle更新全部samples的累计周期数。

```text
相邻真实PMT更新：8000 → 8000，delta=0
含义：这段窗口没有新增被记录的未完成周期。

相邻真实PMT更新：8000 → 8003，delta=3
含义：窗口内有3个processing cycles未完整更新；不是丢了3个字段，也不是丢了3个20秒snapshot。
```

风险分级：

- 绝对值很高但保持不变：历史累计，不代表当前有问题；
- 负载期间偶尔增加、后续连续窗口delta=0：短暂质量告警；
- 连续多个真实PMT窗口增长：持续telemetry质量问题；
- workload停止后仍快速增长，并伴随freshness、series、RAS或计算校验异常：需要升级调查。

Data loss本身不证明CPU硬件故障。公开XML没有总processing-cycle分母、失败字段bitmap或内部scheduler信息，因此不能计算准确loss百分比，也不能指出哪一个sample失败。

## 5. Core Frequency/Temperature/Voltage Residency区间

| Bucket | Frequency | Temperature | Voltage |
|---:|---|---|---|
| R0 | Core in C6 | <20°C | <602mV |
| R1 | ≤800MHz | 20.5–27.5°C | 602.5–657mV |
| R2 | 900–1200MHz | 28–35°C | 657.5–712mV |
| R3 | 1300–1600MHz | 35.5–42.5°C | 712.5–767mV |
| R4 | 1700–2000MHz | 43–50°C | 767.5–822mV |
| R5 | 2100–2400MHz | 50.5–57.5°C | 822.5–877mV |
| R6 | 2500–2800MHz | 58–65°C | 877.5–932mV |
| R7 | 2900–3200MHz | 65.5–72.5°C | 932.5–987mV |
| R8 | 3300–3600MHz | 73–80°C | 987.5–1042mV |
| R9 | 3700–4000MHz | 80.5–87.5°C | 1042.5–1097mV |
| R10 | 4100–4400MHz | 88–95°C | 1097.5–1152mV |
| R11 | >4400MHz | >95°C | >1152mV |

正确驻留百分比计算：同一Core、同一维度的每个bucket先求rate，然后除以12个bucket rate之和。不要把累计seconds直接当百分比。

## 6. 当前全部Metric Families

### 6.1 Aggregator未完整更新周期计数 / Data-loss cycle count

- Family ID：`data-loss-count`
- 当前名称数：**1**
- 类别：采集质量/Data loss
- Prometheus类型：counter
- 单位：count
- 名称模式：`agg_data_loss_count_total`
- 示例：`agg_data_loss_count_total`

**含义：** CPU/firmware telemetry aggregator 未能在一个内部 processing cycle 更新全部 samples 的累计周期数。

**数值语义：** 64-bit raw cumulative counter；一次失败周期加1，与该周期漏了多少字段无关。绝对值不会在恢复后归零。

**推荐查询/展示：** 比较相邻真实PMT更新的差值，或使用 increase(metric[5m])；按 DeviceId/AccessId 分开观察。

**重要边界：** 20秒是Collector读取周期，不是内部cycle。delta=0表示窗口内没有新增失败；不能据此计算loss百分比，因为没有总cycle分母。

**代表性官方HELP：**

- Running count of processing cycles when the telemetry aggregator was unable to update all samples. Estimated maximum rate of change is 10000 per second. If the actual rate of change is zero, there is no data loss. Otherwise, other samples in this aggregator may report incorrect values for the duration of the data loss.

### 6.2 最近Data-loss内部时间戳 / Last data-loss timestamp

- Family ID：`data-loss-timestamp`
- 当前名称数：**1**
- 类别：采集质量/Data loss
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`agg_data_loss_timestamp_total`
- 示例：`agg_data_loss_timestamp_total`

**含义：** 最近一次 aggregator processing cycle 未能更新全部 samples 的内部时间戳。

**数值语义：** 25MHz crystal TSC ticks；是内部时钟计数，不是Unix时间。

**推荐查询/展示：** 与data-loss count配对，用changes()判断最近失败时间戳是否更新。

**重要边界：** 没有经过时钟域标定时不能直接转换成墙钟时间；名称虽以_total结尾，但业务语义是最近一次事件时间。

**代表性官方HELP：**

- Timestamp of last processing cycle when the telemetry aggregator was unable to update all samples. Reported in crystal clock TSC ticks (25MHz).

### 6.3 Aggregator最近更新时间戳 / Last-update timestamp

- Family ID：`last-update-timestamp`
- 当前名称数：**1**
- 类别：频率/Frequency
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`last_update_timestamp_total`
- 示例：`last_update_timestamp_total`

**含义：** Aggregator最近一次sample更新的内部时间戳。

**数值语义：** 25MHz crystal TSC ticks，随内部更新推进。

**推荐查询/展示：** 使用changes()或相邻样本差值检查内部更新是否继续，不要直接显示为日期。

**重要边界：** 它不是Collector抓取时间；与Prometheus timestamp、Redfish CollectionTimestamp是不同时间域。

**代表性官方HELP：**

- Timestamp of the last sample update in this aggregator. Reported in crystal clock TSC ticks (25MHz).

### 6.4 Core当前温度 / Per-core temperature

- Family ID：`core-temperature`
- 当前名称数：**64**
- 类别：温度/Temperature
- Prometheus类型：gauge
- 单位：celsius
- 名称模式：`cN_cN_cN_cN_temp_cN_temp_celsius`
- 示例：`c0_c1_c2_c3_temp_c0_temp_celsius`, `c0_c1_c2_c3_temp_c1_temp_celsius`, `c0_c1_c2_c3_temp_c2_temp_celsius`

**含义：** CORE aggregator中某个local Core slot的当前温度。

**数值语义：** Gauge，单位°C；当前平台local Core0–31有效，32–63通常为disabled的0°C占位。

**推荐查询/展示：** 直接查询并过滤 > 0；按DeviceId/AccessId保留来源标签，可用max()做最高温摘要。

**重要边界：** local Core编号不是Linux CPU编号；0°C不能解释为真实硅温。

**代表性官方HELP：**

- Current temperature for core 0
- Current temperature for core 1

### 6.5 Core频率驻留分布 / Frequency residency

- Family ID：`core-frequency-histogram`
- 当前名称数：**768**
- 类别：频率/Frequency
- Prometheus类型：counter
- 单位：second
- 名称模式：`cN_freq_hist_rN_second_total`
- 示例：`c0_freq_hist_r0_second_total`, `c0_freq_hist_r10_second_total`, `c0_freq_hist_r11_second_total`

**含义：** Core在12个频率区间中的累计驻留时间，R0为C6，R1–R11为不同MHz范围。

**数值语义：** Counter，单位seconds；每个bucket累计增长，不是瞬时频率。

**推荐查询/展示：** 先对每个bucket做rate([5m])，再除以同一Core所有bucket rate之和得到驻留百分比。

**重要边界：** 不能把bucket值直接当MHz；短于PMT原生更新周期的rate窗口会重复旧值并产生噪声。

**代表性官方HELP：**

- Frequency histogram range 0 (core in C6) counter for core 0
- Frequency histogram range 10 (4100-4400MHz) counter for core 0

### 6.6 Core温度驻留分布 / Temperature residency

- Family ID：`core-temperature-histogram`
- 当前名称数：**768**
- 类别：温度/Temperature
- Prometheus类型：counter
- 单位：second
- 名称模式：`cN_temp_hist_rN_second_total`
- 示例：`c0_temp_hist_r0_second_total`, `c0_temp_hist_r10_second_total`, `c0_temp_hist_r11_second_total`

**含义：** Core在12个温度区间中的累计驻留时间。

**数值语义：** Counter，单位seconds；表示落入区间的累计时间，不是当前温度。

**推荐查询/展示：** 对bucket做rate([5m])并归一化为百分比；当前温度应查询core-temperature family。

**重要边界：** 区间边界来自HELP；不要把R编号当温度值。

**代表性官方HELP：**

- Temperature histogram range 0 (less then 20C) counter for core 0
- Temperature histogram range 10 (88-95C) counter for core 0

### 6.7 Core电压驻留分布 / Voltage residency

- Family ID：`core-voltage-histogram`
- 当前名称数：**768**
- 类别：电压/Voltage
- Prometheus类型：counter
- 单位：second
- 名称模式：`cN_volt_hist_rN_second_total`
- 示例：`c0_volt_hist_r0_second_total`, `c0_volt_hist_r10_second_total`, `c0_volt_hist_r11_second_total`

**含义：** Core在12个电压区间中的累计驻留时间。

**数值语义：** Counter，单位seconds；HELP中的区间单位为mV。

**推荐查询/展示：** 对bucket做rate([5m])并按同一Core归一化。

**重要边界：** 它不是瞬时Vcore，也不能直接推导功耗；R编号只是bucket索引。

**代表性官方HELP：**

- Voltage histogram range 0 (less then 602mV) counter for core 0
- Voltage histogram range 10 (1097.5-1152mV) counter for core 0

### 6.8 Core Cdyn等级驻留 / Cdyn residency

- Family ID：`core-cdyn-residency`
- 当前名称数：**384**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：counter
- 单位：microsecond
- 名称模式：`cN_cdyn_level_N_res_microsecond_total`
- 示例：`c0_cdyn_level_0_res_microsecond_total`, `c0_cdyn_level_1_res_microsecond_total`, `c0_cdyn_level_2_res_microsecond_total`

**含义：** 最近2ms测量语义下，各Core在Cdyn level 0–5中的驻留累计。

**数值语义：** Counter，XML转换后单位microseconds。

**推荐查询/展示：** 比较各level的rate或increase，并按Core、Access分组。

**重要边界：** Cdyn level是平台内部动态状态等级，公开HELP未提供面向业务的频率/电压枚举。

**代表性官方HELP：**

- Cdyn level 0 residency for core 0 during last 2ms measurement
- Cdyn level 1 residency for core 0 during last 2ms measurement

### 6.9 实验性Core相对使用量 / Relative usage

- Family ID：`core-relative-usage`
- 当前名称数：**64**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`cN_usage_meter_core_usage_total`
- 示例：`c0_usage_meter_core_usage_total`, `c10_usage_meter_core_usage_total`, `c11_usage_meter_core_usage_total`

**含义：** Core的实验性累计relative usage level。

**数值语义：** U64.38.26定点counter；值经2^26缩放，处理器reset后不保留。

**推荐查询/展示：** 使用rate([5m])比较local Core slots的相对活动；显示至少6位小数或换算为micro-relative-units/s。

**重要边界：** 不是Linux CPU utilization百分比，Intel未公开换算为CPU%的公式；local Core编号也不是Linux CPU号。

**代表性官方HELP：**

- Accumulated relative usage level for core 0 (experimental). This counter is not retained on processor reset
- Accumulated relative usage level for core 10 (experimental). This counter is not retained on processor reset

### 6.10 Core PVP节流计数 / Throttle count

- Family ID：`core-throttle`
- 当前名称数：**128**
- 类别：节流/Throttle
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`cN_pvp_throttle_N_total`
- 示例：`c0_pvp_throttle_1024_total`, `c0_pvp_throttle_64_total`, `c10_pvp_throttle_1024_total`

**含义：** Core在64-cycle或1024-cycle观察窗口中记录的throttle累计次数。

**数值语义：** Counter，无公开物理单位；后缀64/1024是观察窗口尺度。

**推荐查询/展示：** 使用rate或increase比较负载前后变化，并分别观察两个window family。

**重要边界：** 它不是温度、功率或throttle百分比；事件原因需要结合thermal/power/RAS数据。

**代表性官方HELP：**

- Counter indicating number of times core 0 was throttled in last 1024 cycles window
- Counter indicating number of times core 0 was throttled in last 64 cycles window

### 6.11 聚合Core C-state驻留 / Aggregate C-state

- Family ID：`aggregate-cstate-residency`
- 当前名称数：**1**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：gauge
- 单位：seconds
- 名称模式：`aggregate_core_cstate_residency_cN_aggregate_core_cstate_residency_cN_seconds`
- 示例：`aggregate_core_cstate_residency_c0_aggregate_core_cstate_residency_c0_seconds`

**含义：** C-Die aggregator提供的aggregate Core C-state residency。

**数值语义：** 当前作为gauge输出，名称带seconds，但HELP仍写“units of ?”。

**推荐查询/展示：** 用于相同平台、相同采集链路下的相对比较；先确认值随时间的行为再决定是否求差。

**重要边界：** XML单位说明不完整，不能仅凭_seconds名称断言它是标准累计秒counter。

**代表性官方HELP：**

- Aggregate Core C0 Residency in units of ?

### 6.12 逐Core C-state驻留 / Per-core C-state

- Family ID：`per-core-cstate-residency`
- 当前名称数：**128**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：gauge
- 单位：seconds
- 名称模式：`core_N_cstate_residency_cN_N_core_N_cstate_residency_cN_seconds`
- 示例：`core_0_cstate_residency_c0_0_core_0_cstate_residency_c0_seconds`, `core_0_cstate_residency_c1_0_core_0_cstate_residency_c1_seconds`, `core_10_cstate_residency_c0_10_core_10_cstate_residency_c0_seconds`

**含义：** C-Die aggregator中的per-core C0/C1/C6 residency字段。

**数值语义：** 当前作为gauge输出，名称带seconds；HELP的物理单位仍标记为未知。

**推荐查询/展示：** 按同一Access和local core进行相对比较；在确认是否单调前不要机械使用rate。

**重要边界：** 该core编号属于C-Die XML局部字段，且公开XML没有给出到Linux CPU的映射。

**代表性官方HELP：**

- Core  0 C0 Residency in units of ?
- Core  0 C1 Residency in units of ?

### 6.13 Die级C-state驻留 / Die C-state

- Family ID：`die-cstate-residency`
- 当前名称数：**1**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：gauge
- 单位：seconds
- 名称模式：`die_cstate_residency_cNe_die_cstate_residency_cNe_seconds`
- 示例：`die_cstate_residency_c1e_die_cstate_residency_c1e_seconds`

**含义：** Die级C-state residency状态/累计量。

**数值语义：** 当前作为gauge输出；名称可能带seconds，但HELP仍未完成单位定义。

**推荐查询/展示：** 直接观察趋势并与package/core C-state对照。

**重要边界：** 不要在缺少平台codebook时解释为严格百分比。

**代表性官方HELP：**

- Die C1E Residency in units of ?

### 6.14 Package C-state驻留 / Package C-state

- Family ID：`package-cstate-residency`
- 当前名称数：**2**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`package_cstate_residency_cN_package_cstate_residency_cN`
- 示例：`package_cstate_residency_c2_package_cstate_residency_c2`, `package_cstate_residency_c6_package_cstate_residency_c6`

**含义：** Socket/package级C-state residency。

**数值语义：** Gauge，公开HELP没有明确单位或累计/瞬时边界。

**推荐查询/展示：** 用于同一平台内的相对趋势；需要百分比时必须先获得平台定义。

**重要边界：** 不能仅凭名称套用Linux turbostat的C-state百分比语义。

**代表性官方HELP：**

- Package C2 Cstate Residency
- Package C6 Cstate Residency

### 6.15 RDT CMT缓存占用计数 / Cache occupancy

- Family ID：`rdt-cmt`
- 当前名称数：**512**
- 类别：使用量与驻留/Usage & Residency
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`chaN_rmidN_rdt_cmt_total`
- 示例：`cha0_rmid0_rdt_cmt_total`, `cha0_rmid1_rdt_cmt_total`, `cha0_rmid2_rdt_cmt_total`

**含义：** 指定CHA和RMID的LLC cache line usage/CMT计数。

**数值语义：** Counter；公开HELP未给cache-line到bytes的可靠换算。

**推荐查询/展示：** 使用rate或increase观察相对cache activity，并按CHA/RMID聚合。

**重要边界：** RMID是RDT监控标识，不是进程ID；没有RMID分配上下文时不要映射到具体应用。

**代表性官方HELP：**

- CHA 0 RMID 0 LLC cache line usage counter
- CHA 0 RMID 1 LLC cache line usage counter

### 6.16 RDT MBM本地内存事务 / Local memory

- Family ID：`rdt-mbm-local`
- 当前名称数：**512**
- 类别：内存/Memory
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`chaN_rmidN_rdt_mbm_local_total`
- 示例：`cha0_rmid0_rdt_mbm_local_total`, `cha0_rmid1_rdt_mbm_local_total`, `cha0_rmid2_rdt_mbm_local_total`

**含义：** 指定CHA/RMID的local memory transaction累计计数。

**数值语义：** Counter，单位未公开。

**推荐查询/展示：** 使用rate得到transactions/s形式的相对速率，并与total MBM对照。

**重要边界：** 不能擅自标成bytes/s或GB/s；local的精确NUMA语义需要平台/RMID配置。

**代表性官方HELP：**

- CHA 0 RMID 0 local memory transactions counter
- CHA 0 RMID 1 local memory transactions counter

### 6.17 RDT MBM总内存事务 / Total memory

- Family ID：`rdt-mbm-total`
- 当前名称数：**512**
- 类别：内存/Memory
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`chaN_rmidN_rdt_mbm_total`
- 示例：`cha0_rmid0_rdt_mbm_total`, `cha0_rmid1_rdt_mbm_total`, `cha0_rmid2_rdt_mbm_total`

**含义：** 指定CHA/RMID的total memory transaction累计计数。

**数值语义：** Counter，单位未公开。

**推荐查询/展示：** 使用rate观察相对内存活动；可计算total与local的差异趋势。

**重要边界：** 不是已校准内存带宽；没有事务大小定义时不要转换成bytes。

**代表性官方HELP：**

- CHA 0 RMID 0 total memory transactions counter
- CHA 0 RMID 1 total memory transactions counter

### 6.18 CHA启用状态 / Enabled mask

- Family ID：`cha-enable`
- 当前名称数：**64**
- 类别：缓存与CHA/Cache & CHA
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`cha_enabled_mask_cha_N_en`
- 示例：`cha_enabled_mask_cha_0_en`, `cha_enabled_mask_cha_10_en`, `cha_enabled_mask_cha_11_en`

**含义：** 某个Caching/Home Agent实例是否启用。

**数值语义：** Gauge，通常0/1。

**推荐查询/展示：** 直接查询；用于过滤disabled CHA并解释CMT/MBM series。

**重要边界：** 它是拓扑配置状态，不是CHA利用率。

**代表性官方HELP：**

- CHA instance 0 is enabled
- CHA instance 10 is enabled

### 6.19 内存通道带宽原始计数 / Memory bandwidth counter

- Family ID：`memory-bandwidth-counter`
- 当前名称数：**16**
- 类别：内存/Memory
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`memory_read_bw_counter_chN_N_memory_read_bw_counter_chN`, `memory_write_bw_counter_chN_N_memory_write_bw_counter_chN`
- 示例：`memory_read_bw_counter_ch0_0_memory_read_bw_counter_ch0`, `memory_read_bw_counter_ch1_1_memory_read_bw_counter_ch1`, `memory_read_bw_counter_ch2_2_memory_read_bw_counter_ch2`

**含义：** 内存channel的read/write bandwidth counter原始字段。

**数值语义：** 当前作为gauge输出，公开HELP未提供单位和缩放。

**推荐查询/展示：** 只做同平台相对比较或相邻差值实验；获得平台转换公式前不要标GB/s。

**重要边界：** 名称含Bandwidth不代表当前输出已经是bytes/s；需Intel平台codebook确认。

**代表性官方HELP：**

- Memory Read Bandwidth Counter
- Memory Write Bandwidth Counter

### 6.20 当前OOBMSM域与链路掩码 / Domain identity

- Family ID：`topology-current-domain`
- 当前名称数：**27**
- 类别：内存/Memory
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`curr_die_ids_enabled_upi_ddr_mem_mask_curr_die_domain_id`, `curr_die_ids_enabled_upi_ddr_mem_mask_curr_die_eid`, `curr_die_ids_enabled_upi_ddr_mem_mask_curr_socket_id`, `curr_die_ids_enabled_upi_ddr_mem_mask_ddr_mem_N_en`, `curr_die_ids_enabled_upi_ddr_mem_mask_upi_N_en`
- 示例：`curr_die_ids_enabled_upi_ddr_mem_mask_curr_die_domain_id`, `curr_die_ids_enabled_upi_ddr_mem_mask_curr_die_eid`, `curr_die_ids_enabled_upi_ddr_mem_mask_curr_socket_id`

**含义：** 当前OOBMSM实例的socket/domain/EID，以及DDR memory和UPI link enable mask。

**数值语义：** Gauge；ID字段为枚举，*_en通常为0/1。

**推荐查询/展示：** 直接查询，用于构建拓扑和过滤未启用memory/link实例。

**重要边界：** EID、DomainID和AccessId是不同编号；不能据此自行推导物理die坐标。

**代表性官方HELP：**

- DomainID of this OOBMSM instance
- MCTP EID of this OOBMSM instance

### 6.21 OOBMSM Domain到EID映射 / Domain map

- Family ID：`topology-domain-map`
- 当前名称数：**24**
- 类别：其他计数器/Other, 状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`domain_eids_N_N_domain_N_eid`, `domain_mask_eids_N_N_domain_N_eid`, `domain_mask_eids_N_N_domain_N_en`
- 示例：`domain_eids_6_11_domain_10_eid`, `domain_eids_6_11_domain_11_eid`, `domain_eids_6_11_domain_6_eid`

**含义：** TOPO aggregator中的DomainID enable状态及其MCTP EID映射。

**数值语义：** Gauge；*_en通常为0/1，*_eid是MCTP Endpoint ID。

**推荐查询/展示：** 直接查询并按DeviceId/AccessId保留标签。

**重要边界：** EID是管理总线地址，不是Core、NUMA或Linux CPU编号。

**代表性官方HELP：**

- MCTP EID of OOBMSM instance with DomainID of 10
- MCTP EID of OOBMSM instance with DomainID of 11

### 6.22 Core/FIVR累积能量原始值 / Accumulated energy

- Family ID：`energy-accumulator`
- 当前名称数：**80**
- 类别：功率与能量/Power & Energy
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`energy_accumulator_core_N_N_accumulated_energy_core_N`, `energy_accumulator_fivr_N_N_accumulated_energy_fivr_N`
- 示例：`energy_accumulator_core_0_0_accumulated_energy_core_0`, `energy_accumulator_core_10_10_accumulated_energy_core_10`, `energy_accumulator_core_11_11_accumulated_energy_core_11`

**含义：** Core或FIVR实例的累积能量原始字段。

**数值语义：** Gauge；公开XML/HELP没有给出可靠joule缩放。

**推荐查询/展示：** 与配套energy timestamp做相邻差值，当前仅用于相对比较。

**重要边界：** 不能仅凭energy名称标成J或W；功率=能量差/时间差也必须先获得能量单位。

**代表性官方HELP：**

- Accumulated Energy Core  0
- Accumulated Energy Core  10

### 6.23 Core/FIVR能量时间戳 / Energy timestamp

- Family ID：`energy-timestamp`
- 当前名称数：**80**
- 类别：功率与能量/Power & Energy
- Prometheus类型：gauge
- 单位：seconds
- 名称模式：`energy_accumulator_core_N_N_energy_timestamp_core_N_seconds`, `energy_accumulator_fivr_N_N_energy_timestamp_fivr_N_seconds`
- 示例：`energy_accumulator_core_0_0_energy_timestamp_core_0_seconds`, `energy_accumulator_core_10_10_energy_timestamp_core_10_seconds`, `energy_accumulator_core_11_11_energy_timestamp_core_11_seconds`

**含义：** 配套energy accumulator的采样时间戳。

**数值语义：** Gauge，名称后缀为seconds；用于对齐能量读数。

**推荐查询/展示：** 与同一Core/FIVR的energy accumulator配对做差。

**重要边界：** 不要跨Access或跨实例配对；energy单位未知仍限制功率换算。

**代表性官方HELP：**

- Timestamp

### 6.24 QAT PCIe流量 / Throughput

- Family ID：`qat-pcie-throughput`
- 当前名称数：**4**
- 类别：互连与I/O/Interconnect & I/O
- Prometheus类型：counter
- 单位：megabytes
- 名称模式：`qatN_tl_bw_in_megabytes_total`, `qatN_tl_bw_out_megabytes_total`
- 示例：`qat0_tl_bw_in_megabytes_total`, `qat0_tl_bw_out_megabytes_total`, `qat1_tl_bw_in_megabytes_total`

**含义：** QAT设备跨所有rings的PCIe inbound(write)或outbound(read)累计MB。

**数值语义：** Counter，单位megabytes；rate后为MB/s。

**推荐查询/展示：** 使用rate([5m])；in+out可做总QAT PCIe吞吐。

**重要边界：** CPU-only workload不会调用QAT，0表示Idle而不是采集失败。

**代表性官方HELP：**

- PCIe write bandwidth across all rings for QAT device 0
- PCIe read bandwidth across all rings for QAT device 0

### 6.25 QAT平均延迟 / Average latency

- Family ID：`qat-average-latency`
- 当前名称数：**8**
- 类别：延迟/Latency
- Prometheus类型：gauge
- 单位：nanoseconds
- 名称模式：`qatN_avg_page_req_lat_trans_lat_qatN_avg_page_req_lat_nanoseconds`, `qatN_avg_page_req_lat_trans_lat_qatN_avg_trans_lat_nanoseconds`, `qatN_avg_rd_lat_gp_lat_qatN_avg_gp_lat_nanoseconds`, `qatN_avg_rd_lat_gp_lat_qatN_avg_rd_lat_nanoseconds`
- 示例：`qat0_avg_page_req_lat_trans_lat_qat0_avg_page_req_lat_nanoseconds`, `qat0_avg_page_req_lat_trans_lat_qat0_avg_trans_lat_nanoseconds`, `qat0_avg_rd_lat_gp_lat_qat0_avg_gp_lat_nanoseconds`

**含义：** QAT跨所有rings的page request、translation、read或get-to-put平均延迟。

**数值语义：** Gauge，单位ns。

**推荐查询/展示：** 仅在QAT throughput或transaction count大于0时直接读取。

**重要边界：** 无QAT流量时0ns没有业务意义，应显示Idle/N/A。

**代表性官方HELP：**

- Average page request latency across all rings for QAT device 0
- Average translation latency across all rings for QAT device 0

### 6.26 QAT延迟累加器与计数 / Latency accumulators

- Family ID：`qat-latency-accumulator`
- 当前名称数：**10**
- 类别：延迟/Latency
- Prometheus类型：counter
- 单位：nanosecond, unspecified
- 名称模式：`qatN_tl_at_page_req_lat_acc_nanosecond_total`, `qatN_tl_at_trans_lat_acc_nanosecond_total`, `qatN_tl_at_trans_lat_cnt_total`, `qatN_tl_gp_lat_acc_nanosecond_total`, `qatN_tl_rd_lat_acc_nanosecond_total`
- 示例：`qat0_tl_at_page_req_lat_acc_nanosecond_total`, `qat0_tl_at_trans_lat_acc_nanosecond_total`, `qat0_tl_at_trans_lat_cnt_total`

**含义：** QAT延迟累计值或对应事件计数，用于构造平均延迟。

**数值语义：** Accumulator通常为nanoseconds counter，count为无单位counter。

**推荐查询/展示：** 平均延迟使用rate(accumulator)/rate(count)，并要求count rate > 0。

**重要边界：** 不要只对accumulator做rate后标成平均ns；必须与正确的count配对。

**代表性官方HELP：**

- Page request latency accumulator value across all rings for QAT device 0
- Translation latency accumulator value across all rings for QAT device 0

### 6.27 QAT最大延迟 / Maximum latency

- Family ID：`qat-maximum-latency`
- 当前名称数：**4**
- 类别：延迟/Latency
- Prometheus类型：counter
- 单位：nanoseconds
- 名称模式：`qatN_tl_max_gp_lat_nanoseconds_total`, `qatN_tl_max_rd_lat_nanoseconds_total`
- 示例：`qat0_tl_max_gp_lat_nanoseconds_total`, `qat0_tl_max_rd_lat_nanoseconds_total`, `qat1_tl_max_gp_lat_nanoseconds_total`

**含义：** QAT read或get-to-put路径记录的最大延迟字段。

**数值语义：** XML将其标为counter并带nanoseconds名称，具体reset窗口未公开。

**推荐查询/展示：** 观察当前值和changes()；结合QAT流量确认样本有效。

**重要边界：** 不能把rate(max)解释成延迟；无流量时应显示N/A。

**代表性官方HELP：**

- Maximum get to put latency across all rings for QAT device 0
- Maximum read latency across all rings for QAT device 0

### 6.28 QAT活动与转换计数 / Activity counters

- Family ID：`qat-activity-counter`
- 当前名称数：**10**
- 类别：其他计数器/Other
- Prometheus类型：counter
- 单位：unspecified
- 名称模式：`qatN_tl_at_max_utlb_used_total`, `qatN_tl_at_page_req_cnt_total`, `qatN_tl_me_put_cnt_total`, `qatN_tl_prt_trans_cnt_total`, `qatN_tl_rd_cmpl_cnt_total`
- 示例：`qat0_tl_at_max_utlb_used_total`, `qat0_tl_at_page_req_cnt_total`, `qat0_tl_me_put_cnt_total`

**含义：** QAT page request、translation、ME put、read completion、partial transaction及uTLB使用计数。

**数值语义：** 大多为counter；max_uTLB字段表示上下文最大占用，最大可能值32。

**推荐查询/展示：** 事件counter使用rate/increase；max字段直接观察并结合QAT throughput。

**重要边界：** CPU benchmark不会激励QAT；长期0通常表示没有QAT workload。

**代表性官方HELP：**

- Maximum uTLB consumed by a context for QAT device 0. Maximum possible value is 32.
- Page request count across all rings for QAT device 0

### 6.29 FIVR Monitor数据可用性 / Availability

- Family ID：`fivr-availability`
- 当前名称数：**3**
- 类别：其他计数器/Other
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`fivr_health_monitor_N_N_fivr_health_monitor_N_available`
- 示例：`fivr_health_monitor_0_0_fivr_health_monitor_0_available`, `fivr_health_monitor_1_1_fivr_health_monitor_1_available`, `fivr_health_monitor_2_2_fivr_health_monitor_2_available`

**含义：** Receiver派生的FIVR monitor数据可用性。

**数值语义：** Gauge：1=原始word有效，0=检测到DEADBEEF firmware poison。

**推荐查询/展示：** 直接查询；先判断available，再解释raw/status。

**重要边界：** available=0表示数据不可用，不代表FIVR硬件故障。

**代表性官方HELP：**

- FIVR Health monitor data availability (1=packed word present, 0=DEADBEEF sentinel)

### 6.30 FIVR非零Slot数量 / Non-zero count

- Family ID：`fivr-nonzero-count`
- 当前名称数：**3**
- 类别：状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：count
- 名称模式：`fivr_health_monitor_N_N_fivr_health_monitor_N_nonzero_status_count`
- 示例：`fivr_health_monitor_0_0_fivr_health_monitor_0_nonzero_status_count`, `fivr_health_monitor_1_1_fivr_health_monitor_1_nonzero_status_count`, `fivr_health_monitor_2_2_fivr_health_monitor_2_nonzero_status_count`

**含义：** Receiver把64-bit monitor拆成32个2-bit slots后，非零slot的数量。

**数值语义：** Gauge，范围0–32。

**推荐查询/展示：** 直接查询；非零时下钻status_N family定位monitor和slot。

**重要边界：** 这是项目派生指标；公开XML没有slot到rail/core映射，也没有0–3官方枚举。

**代表性官方HELP：**

- Number of non-zero two-bit FIVR Health status codes in this monitor word

### 6.31 FIVR两位状态Slot / Status slot

- Family ID：`fivr-status-slot`
- 当前名称数：**96**
- 类别：状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`fivr_health_monitor_N_N_fivr_health_monitor_N_status_N`
- 示例：`fivr_health_monitor_0_0_fivr_health_monitor_0_status_00`, `fivr_health_monitor_0_0_fivr_health_monitor_0_status_01`, `fivr_health_monitor_0_0_fivr_health_monitor_0_status_02`

**含义：** FIVR 64-bit monitor word中某个2-bit slot的code。

**数值语义：** Gauge，取值0–3。

**推荐查询/展示：** 直接查询；仅在available=1时解释，按DeviceId/AccessId/monitor/slot定位。

**重要边界：** 0=Healthy是当前项目运营约定，不是Intel公开codebook；不能把slot翻译成具体rail或Core。

**代表性官方HELP：**

- Two-bit FIVR Health status code at packed index 0
- Two-bit FIVR Health status code at packed index 1

### 6.32 FIVR打包Health Monitor原始值 / Packed word

- Family ID：`fivr-packed-word`
- 当前名称数：**3**
- 类别：状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`fivr_health_monitor_N_N_fivr_health_monitor_N`
- 示例：`fivr_health_monitor_0_0_fivr_health_monitor_0`, `fivr_health_monitor_1_1_fivr_health_monitor_1`, `fivr_health_monitor_2_2_fivr_health_monitor_2`

**含义：** XML提供的原始64-bit FIVR Health Indicator packed word。

**数值语义：** Gauge；每2 bits一个slot。DEADBEEF/DEADBEEFDEADBEEF由receiver识别为poison并抑制raw输出。

**推荐查询/展示：** 技术诊断时查看；日常使用available、nonzero count和status slots。

**重要边界：** 缺少Intel公开slot/code映射，不能依据非零word直接声明具体硬件故障。

**代表性官方HELP：**

- FIVR Health Indicator Status - 2bits per FIVR

### 6.33 Core启用掩码 / Enable masks

- Family ID：`core-enable`
- 当前名称数：**128**
- 类别：状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`core_en_cN_en`, `core_enabled_mask_cN_en`
- 示例：`core_en_c0_en`, `core_en_c10_en`, `core_en_c11_en`

**含义：** CORE或TOPO/C-Die视角下的local Core enable状态。

**数值语义：** Gauge，通常0/1。

**推荐查询/展示：** 直接查询；用于过滤温度0°C和disabled local slots。

**重要边界：** 两个family来自不同aggregator视角；local Core编号不能直接映射Linux CPU。

**代表性官方HELP：**

- Core 0 is enabled
- Core 10 is enabled

### 6.34 处理器CPUID与平台标识 / Processor identity

- Family ID：`processor-identity`
- 当前名称数：**8**
- 类别：其他计数器/Other, 状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`cpuid_platform_id_cpuid_ext_family`, `cpuid_platform_id_cpuid_ext_model`, `cpuid_platform_id_cpuid_family`, `cpuid_platform_id_cpuid_model`, `cpuid_platform_id_cpuid_stepping`, `cpuid_platform_id_cpuid_type`, `cpuid_platform_id_minor_steping_id`, `cpuid_platform_id_platform_id`
- 示例：`cpuid_platform_id_cpuid_ext_family`, `cpuid_platform_id_cpuid_ext_model`, `cpuid_platform_id_cpuid_family`

**含义：** 处理器family、model、extended model/family、stepping、minor stepping、type和platform ID。

**数值语义：** Gauge形式的静态枚举/数值。

**推荐查询/展示：** 直接查询，主要用于inventory、schema选择和跨机器分组。

**重要边界：** 不是性能指标；数值应按CPUID规范组合解释，engineering sample还需结合QDF。

**代表性官方HELP：**

- Processor extended family per CPUID
- Processor extended model per CPUID

### 6.35 Core/Socket能效偏好策略 / EPB

- Family ID：`energy-performance-bias`
- 当前名称数：**65**
- 类别：其他计数器/Other
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`core_epb_N_N_core_input_eepolicy_N`, `socket_epb_resolved_socket_epb`
- 示例：`core_epb_0_0_core_input_eepolicy_0`, `core_epb_10_10_core_input_eepolicy_10`, `core_epb_11_11_core_input_eepolicy_11`

**含义：** Core输入EPB policy及socket最终resolved EPB policy。

**数值语义：** Gauge，策略枚举。

**推荐查询/展示：** 直接查询并比较input与resolved值。

**重要边界：** 不是功耗或性能百分比；策略编码的业务含义需平台codebook。

**代表性官方HELP：**

- Core EPB Policy
- Resolved socket EPB Policy

### 6.36 功率事件监控字段 / PEM

- Family ID：`pem-event-status`
- 当前名称数：**23**
- 类别：其他计数器/Other, 状态与配置/Status & Configuration
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`pem_control_and_status_pem_control`, `pem_control_and_status_pem_status`, `pem_counter_N_N_pem_any`, `pem_counter_N_N_pem_fast_rapl`, `pem_counter_N_N_pem_fct`, `pem_counter_N_N_pem_hot_vr`, `pem_counter_N_N_pem_mt_pmax`, `pem_counter_N_N_pem_pcs_pstate`, `pem_counter_N_N_pem_per_core_thermal`, `pem_counter_N_N_pem_pkg_plN_mmio`, `pem_counter_N_N_pem_pkg_plN_msr_tpmi`, `pem_counter_N_N_pem_pkg_plN_pcs`, `pem_counter_N_N_pem_platform_plN_mmio`, `pem_counter_N_N_pem_platform_plN_msr_tpmi`, `pem_counter_N_N_pem_platform_plN_pcs`, `pem_counter_N_N_pem_sst_pp`, `pem_counter_N_N_pem_xxprochot`
- 示例：`pem_control_and_status_pem_control`, `pem_control_and_status_pem_status`, `pem_counter_0_1_pem_any`

**含义：** PEM control/status以及Fast RAPL、thermal、VR、power-limit、SST等事件源字段。

**数值语义：** 当前多作为gauge输出；名称中的counter不保证Prometheus类型为counter。

**推荐查询/展示：** 直接观察状态和变化；按具体HELP区分PL1/PL2、MMIO/MSR/TPMI/PCS来源。

**重要边界：** 缺少公开位级codebook时不能把非零统一解释成故障；多个来源可能同时报告同一限制。

**代表性官方HELP：**

- PEM Control
- PEM Status

### 6.37 Mesh频率与GV Telemetry

- Family ID：`mesh-telemetry`
- 当前名称数：**13**
- 类别：其他计数器/Other, 频率/Frequency
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`mesh_freq_histogram_bins_N_N_mesh_freq_histogram_bin_N`, `mesh_gv_counter_mesh_gv_counter`
- 示例：`mesh_freq_histogram_bins_0_1_mesh_freq_histogram_bin_0`, `mesh_freq_histogram_bins_0_1_mesh_freq_histogram_bin_1`, `mesh_freq_histogram_bins_10_11_mesh_freq_histogram_bin_10`

**含义：** Mesh GV counter及mesh frequency histogram bins。

**数值语义：** 当前作为gauge输出，公开HELP未给完整单位和bin边界。

**推荐查询/展示：** 用于同平台相对趋势和bin变化；不要转换为MHz或百分比。

**重要边界：** 缺少bin codebook与采样语义，不能用于精确mesh频率计算。

**代表性官方HELP：**

- Mesh frequency histogram bin 0
- Mesh frequency histogram bin 1

### 6.38 Firmware镜像版本 / Image version

- Family ID：`firmware-version`
- 当前名称数：**1**
- 类别：其他计数器/Other
- Prometheus类型：gauge
- 单位：unspecified
- 名称模式：`global_info_firmware_version`
- 示例：`global_info_firmware_version`

**含义：** Aggregator暴露的firmware image version。

**数值语义：** 静态gauge/编码值。

**推荐查询/展示：** 直接查询，用于实验provenance和版本变化检测。

**重要边界：** 数值编码格式未在HELP中展开，不应当作性能或健康指标。

**代表性官方HELP：**

- Version of Firmware Image

## 7. 如何确认每个准确名称都已覆盖

`pmt-metrics-catalog.csv`中的每一行都包含：

- `metric_name`：准确Prometheus名称；
- `family_id` / `family_title`：本文件对应章节；
- `value_semantics`：值本身表示什么；
- `recommended_query`：直接看、rate、increase或配对计算；
- `caveat`：最容易误读的边界；
- `help`：Collector/XML暴露的官方说明。

生成器会统计 `unclassified` family。当前值必须为0；升级XML或firmware后如果出现未分类名称，应先补充 `pmt_metric_guides.py`，再发布新catalog。

## 8. 标签与拓扑

同一个metric name会因Redfish/Local、Socket、Access和aggregator实例产生多条series。读取时至少保留：

```text
CollectionMode + PMTGuid + DeviceId + AccessId
```

Redfish下定位单个aggregator还需要 `SourceId + PMTSizeBytes`。完整编号规则见 `pmt-platform-topology.md`。

## 9. 常用PromQL配方

以下示例只使用PMT数据。把 `CollectionMode="redfish"` 改为 `local` 可做带内交叉验证；不要同时求和两种来源，否则同一硬件值会重复计算。

```promql
# 每个aggregator最近5分钟新增data-loss cycles
sum by (DeviceId, AccessId, PMTGuid) (
  increase(agg_data_loss_count_total{PMTEndpoint="avc01",CollectionMode="redfish"}[5m])
)

# 当前有效Core最高温度；排除disabled slot的0°C
max(
  {__name__=~"c[0-9]+_c[0-9]+_c[0-9]+_c[0-9]+_temp_c[0-9]+_temp_celsius",PMTEndpoint="avc01",CollectionMode="redfish"} > 0
)

# 所有Core frequency residency bucket每秒新增seconds
rate({__name__=~"c[0-9]+_freq_hist_r[0-9]+_second_total",PMTEndpoint="avc01",CollectionMode="redfish"}[5m])

# 实验性PMT relative-usage变化率；不是CPU%
rate({__name__=~"c[0-9]+_usage_meter_core_usage_total",PMTEndpoint="avc01",CollectionMode="redfish"}[5m])

# QAT0/1 PCIe总吞吐；结果单位MB/s，0表示没有QAT traffic
sum(rate({__name__=~"qat[01]_tl_bw_(in|out)_megabytes_total",PMTEndpoint="avc01",CollectionMode="redfish"}[5m]))

# FIVR非零2-bit slots；必须同时检查available
sum({__name__=~"fivr_health_monitor_.*_nonzero_status_count",PMTEndpoint="avc01",CollectionMode="redfish"})
```

驻留百分比还需要按同一Core对12个bucket rate求和后归一化；QAT latency只有在throughput或transaction count大于0时才有意义；未知单位的energy、memory bandwidth和MBM不能在PromQL中擅自换算成W或GB/s。

## 10. 实验和机器学习使用规则

- 每条trace固定并保存firmware版本、PMT GUID/size、CollectionMode和CPU拓扑；
- Redfish与Local是同一硬件telemetry的两条采集路径，不能当作两份独立训练样本；
- 只在真实PMT值发生更新的边界提取rate/delta，避免Prometheus重复scrape旧值造成伪0；
- `agg_data_loss_count_total`的delta应作为数据质量特征或mask，同时可以保留为候选异常特征；不能直接把data loss当作attack标签；
- CPUID、firmware、enable mask等静态字段适合provenance/分组，不适合作为单机trace中的动态异常特征；
- FIVR poison、disabled Core的0°C和QAT Idle必须编码为状态/缺失语义，不能当作普通数值0训练。
