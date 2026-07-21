"""Human-maintained operational guidance for Intel PMT metric families."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FamilyGuide:
    family_id: str
    title: str
    pattern: str
    meaning: str
    value_semantics: str
    recommended_query: str
    caveat: str

    def matches(self, metric_name: str) -> bool:
        return re.search(self.pattern, metric_name) is not None


FAMILY_GUIDES = (
    FamilyGuide(
        "data-loss-count", "Aggregator未完整更新周期计数 / Data-loss cycle count",
        r"^agg_data_loss_count_total$",
        "CPU/firmware telemetry aggregator 未能在一个内部 processing cycle 更新全部 samples 的累计周期数。",
        "64-bit raw cumulative counter；一次失败周期加1，与该周期漏了多少字段无关。绝对值不会在恢复后归零。",
        "比较相邻真实PMT更新的差值，或使用 increase(metric[5m])；按 DeviceId/AccessId 分开观察。",
        "20秒是Collector读取周期，不是内部cycle。delta=0表示窗口内没有新增失败；不能据此计算loss百分比，因为没有总cycle分母。",
    ),
    FamilyGuide(
        "data-loss-timestamp", "最近Data-loss内部时间戳 / Last data-loss timestamp",
        r"^agg_data_loss_timestamp_total$",
        "最近一次 aggregator processing cycle 未能更新全部 samples 的内部时间戳。",
        "25MHz crystal TSC ticks；是内部时钟计数，不是Unix时间。",
        "与data-loss count配对，用changes()判断最近失败时间戳是否更新。",
        "没有经过时钟域标定时不能直接转换成墙钟时间；名称虽以_total结尾，但业务语义是最近一次事件时间。",
    ),
    FamilyGuide(
        "last-update-timestamp", "Aggregator最近更新时间戳 / Last-update timestamp",
        r"^last_update_timestamp_total$",
        "Aggregator最近一次sample更新的内部时间戳。",
        "25MHz crystal TSC ticks，随内部更新推进。",
        "使用changes()或相邻样本差值检查内部更新是否继续，不要直接显示为日期。",
        "它不是Collector抓取时间；与Prometheus timestamp、Redfish CollectionTimestamp是不同时间域。",
    ),
    FamilyGuide(
        "core-temperature", "Core当前温度 / Per-core temperature",
        r"^c\d+_c\d+_c\d+_c\d+_temp_c\d+_temp_celsius$",
        "CORE aggregator中某个local Core slot的当前温度。",
        "Gauge，单位°C；当前平台local Core0–31有效，32–63通常为disabled的0°C占位。",
        "直接查询并过滤 > 0；按DeviceId/AccessId保留来源标签，可用max()做最高温摘要。",
        "local Core编号不是Linux CPU编号；0°C不能解释为真实硅温。",
    ),
    FamilyGuide(
        "core-frequency-histogram", "Core频率驻留分布 / Frequency residency",
        r"^c\d+_freq_hist_r\d+_second_total$",
        "Core在12个频率区间中的累计驻留时间，R0为C6，R1–R11为不同MHz范围。",
        "Counter，单位seconds；每个bucket累计增长，不是瞬时频率。",
        "先对每个bucket做rate([5m])，再除以同一Core所有bucket rate之和得到驻留百分比。",
        "不能把bucket值直接当MHz；短于PMT原生更新周期的rate窗口会重复旧值并产生噪声。",
    ),
    FamilyGuide(
        "core-temperature-histogram", "Core温度驻留分布 / Temperature residency",
        r"^c\d+_temp_hist_r\d+_second_total$",
        "Core在12个温度区间中的累计驻留时间。",
        "Counter，单位seconds；表示落入区间的累计时间，不是当前温度。",
        "对bucket做rate([5m])并归一化为百分比；当前温度应查询core-temperature family。",
        "区间边界来自HELP；不要把R编号当温度值。",
    ),
    FamilyGuide(
        "core-voltage-histogram", "Core电压驻留分布 / Voltage residency",
        r"^c\d+_volt_hist_r\d+_second_total$",
        "Core在12个电压区间中的累计驻留时间。",
        "Counter，单位seconds；HELP中的区间单位为mV。",
        "对bucket做rate([5m])并按同一Core归一化。",
        "它不是瞬时Vcore，也不能直接推导功耗；R编号只是bucket索引。",
    ),
    FamilyGuide(
        "core-cdyn-residency", "Core Cdyn等级驻留 / Cdyn residency",
        r"^c\d+_cdyn_level_\d+_res_microsecond_total$",
        "最近2ms测量语义下，各Core在Cdyn level 0–5中的驻留累计。",
        "Counter，XML转换后单位microseconds。",
        "比较各level的rate或increase，并按Core、Access分组。",
        "Cdyn level是平台内部动态状态等级，公开HELP未提供面向业务的频率/电压枚举。",
    ),
    FamilyGuide(
        "core-relative-usage", "实验性Core相对使用量 / Relative usage",
        r"^c\d+_usage_meter_core_usage_total$",
        "Core的实验性累计relative usage level。",
        "U64.38.26定点counter；值经2^26缩放，处理器reset后不保留。",
        "使用rate([5m])比较local Core slots的相对活动；显示至少6位小数或换算为micro-relative-units/s。",
        "不是Linux CPU utilization百分比，Intel未公开换算为CPU%的公式；local Core编号也不是Linux CPU号。",
    ),
    FamilyGuide(
        "core-throttle", "Core PVP节流计数 / Throttle count",
        r"^c\d+_pvp_throttle_(?:64|1024)_total$",
        "Core在64-cycle或1024-cycle观察窗口中记录的throttle累计次数。",
        "Counter，无公开物理单位；后缀64/1024是观察窗口尺度。",
        "使用rate或increase比较负载前后变化，并分别观察两个window family。",
        "它不是温度、功率或throttle百分比；事件原因需要结合thermal/power/RAS数据。",
    ),
    FamilyGuide(
        "aggregate-cstate-residency", "聚合Core C-state驻留 / Aggregate C-state",
        r"^aggregate_core_cstate_residency_",
        "C-Die aggregator提供的aggregate Core C-state residency。",
        "当前作为gauge输出，名称带seconds，但HELP仍写“units of ?”。",
        "用于相同平台、相同采集链路下的相对比较；先确认值随时间的行为再决定是否求差。",
        "XML单位说明不完整，不能仅凭_seconds名称断言它是标准累计秒counter。",
    ),
    FamilyGuide(
        "per-core-cstate-residency", "逐Core C-state驻留 / Per-core C-state",
        r"^core_\d+_cstate_residency_",
        "C-Die aggregator中的per-core C0/C1/C6 residency字段。",
        "当前作为gauge输出，名称带seconds；HELP的物理单位仍标记为未知。",
        "按同一Access和local core进行相对比较；在确认是否单调前不要机械使用rate。",
        "该core编号属于C-Die XML局部字段，且公开XML没有给出到Linux CPU的映射。",
    ),
    FamilyGuide(
        "die-cstate-residency", "Die级C-state驻留 / Die C-state",
        r"^die_cstate_residency_",
        "Die级C-state residency状态/累计量。",
        "当前作为gauge输出；名称可能带seconds，但HELP仍未完成单位定义。",
        "直接观察趋势并与package/core C-state对照。",
        "不要在缺少平台codebook时解释为严格百分比。",
    ),
    FamilyGuide(
        "package-cstate-residency", "Package C-state驻留 / Package C-state",
        r"^package_cstate_residency_",
        "Socket/package级C-state residency。",
        "Gauge，公开HELP没有明确单位或累计/瞬时边界。",
        "用于同一平台内的相对趋势；需要百分比时必须先获得平台定义。",
        "不能仅凭名称套用Linux turbostat的C-state百分比语义。",
    ),
    FamilyGuide(
        "rdt-cmt", "RDT CMT缓存占用计数 / Cache occupancy",
        r"^cha\d+_rmid\d+_rdt_cmt_total$",
        "指定CHA和RMID的LLC cache line usage/CMT计数。",
        "Counter；公开HELP未给cache-line到bytes的可靠换算。",
        "使用rate或increase观察相对cache activity，并按CHA/RMID聚合。",
        "RMID是RDT监控标识，不是进程ID；没有RMID分配上下文时不要映射到具体应用。",
    ),
    FamilyGuide(
        "rdt-mbm-local", "RDT MBM本地内存事务 / Local memory",
        r"^cha\d+_rmid\d+_rdt_mbm_local_total$",
        "指定CHA/RMID的local memory transaction累计计数。",
        "Counter，单位未公开。",
        "使用rate得到transactions/s形式的相对速率，并与total MBM对照。",
        "不能擅自标成bytes/s或GB/s；local的精确NUMA语义需要平台/RMID配置。",
    ),
    FamilyGuide(
        "rdt-mbm-total", "RDT MBM总内存事务 / Total memory",
        r"^cha\d+_rmid\d+_rdt_mbm_total$",
        "指定CHA/RMID的total memory transaction累计计数。",
        "Counter，单位未公开。",
        "使用rate观察相对内存活动；可计算total与local的差异趋势。",
        "不是已校准内存带宽；没有事务大小定义时不要转换成bytes。",
    ),
    FamilyGuide(
        "cha-enable", "CHA启用状态 / Enabled mask",
        r"^cha_enabled_mask_cha_\d+_en$",
        "某个Caching/Home Agent实例是否启用。",
        "Gauge，通常0/1。",
        "直接查询；用于过滤disabled CHA并解释CMT/MBM series。",
        "它是拓扑配置状态，不是CHA利用率。",
    ),
    FamilyGuide(
        "memory-bandwidth-counter", "内存通道带宽原始计数 / Memory bandwidth counter",
        r"^memory_(?:read|write)_bw_counter_",
        "内存channel的read/write bandwidth counter原始字段。",
        "当前作为gauge输出，公开HELP未提供单位和缩放。",
        "只做同平台相对比较或相邻差值实验；获得平台转换公式前不要标GB/s。",
        "名称含Bandwidth不代表当前输出已经是bytes/s；需Intel平台codebook确认。",
    ),
    FamilyGuide(
        "topology-current-domain", "当前OOBMSM域与链路掩码 / Domain identity",
        r"^curr_die_ids_enabled_upi_ddr_mem_mask_",
        "当前OOBMSM实例的socket/domain/EID，以及DDR memory和UPI link enable mask。",
        "Gauge；ID字段为枚举，*_en通常为0/1。",
        "直接查询，用于构建拓扑和过滤未启用memory/link实例。",
        "EID、DomainID和AccessId是不同编号；不能据此自行推导物理die坐标。",
    ),
    FamilyGuide(
        "topology-domain-map", "OOBMSM Domain到EID映射 / Domain map",
        r"^domain_(?:mask_)?eids_",
        "TOPO aggregator中的DomainID enable状态及其MCTP EID映射。",
        "Gauge；*_en通常为0/1，*_eid是MCTP Endpoint ID。",
        "直接查询并按DeviceId/AccessId保留标签。",
        "EID是管理总线地址，不是Core、NUMA或Linux CPU编号。",
    ),
    FamilyGuide(
        "energy-accumulator", "Core/FIVR累积能量原始值 / Accumulated energy",
        r"^energy_accumulator_(?:core|fivr)_\d+_\d+_accumulated_energy_",
        "Core或FIVR实例的累积能量原始字段。",
        "Gauge；公开XML/HELP没有给出可靠joule缩放。",
        "与配套energy timestamp做相邻差值，当前仅用于相对比较。",
        "不能仅凭energy名称标成J或W；功率=能量差/时间差也必须先获得能量单位。",
    ),
    FamilyGuide(
        "energy-timestamp", "Core/FIVR能量时间戳 / Energy timestamp",
        r"^energy_accumulator_(?:core|fivr)_\d+_\d+_energy_timestamp_",
        "配套energy accumulator的采样时间戳。",
        "Gauge，名称后缀为seconds；用于对齐能量读数。",
        "与同一Core/FIVR的energy accumulator配对做差。",
        "不要跨Access或跨实例配对；energy单位未知仍限制功率换算。",
    ),
    FamilyGuide(
        "qat-pcie-throughput", "QAT PCIe流量 / Throughput",
        r"^qat\d+_tl_bw_(?:in|out)_megabytes_total$",
        "QAT设备跨所有rings的PCIe inbound(write)或outbound(read)累计MB。",
        "Counter，单位megabytes；rate后为MB/s。",
        "使用rate([5m])；in+out可做总QAT PCIe吞吐。",
        "CPU-only workload不会调用QAT，0表示Idle而不是采集失败。",
    ),
    FamilyGuide(
        "qat-average-latency", "QAT平均延迟 / Average latency",
        r"^qat\d+_avg_.*_nanoseconds$",
        "QAT跨所有rings的page request、translation、read或get-to-put平均延迟。",
        "Gauge，单位ns。",
        "仅在QAT throughput或transaction count大于0时直接读取。",
        "无QAT流量时0ns没有业务意义，应显示Idle/N/A。",
    ),
    FamilyGuide(
        "qat-latency-accumulator", "QAT延迟累加器与计数 / Latency accumulators",
        r"^qat\d+_tl_(?:at_|)(?:page_req|trans|rd|gp)_lat_(?:acc|cnt)",
        "QAT延迟累计值或对应事件计数，用于构造平均延迟。",
        "Accumulator通常为nanoseconds counter，count为无单位counter。",
        "平均延迟使用rate(accumulator)/rate(count)，并要求count rate > 0。",
        "不要只对accumulator做rate后标成平均ns；必须与正确的count配对。",
    ),
    FamilyGuide(
        "qat-maximum-latency", "QAT最大延迟 / Maximum latency",
        r"^qat\d+_tl_max_.*_nanoseconds_total$",
        "QAT read或get-to-put路径记录的最大延迟字段。",
        "XML将其标为counter并带nanoseconds名称，具体reset窗口未公开。",
        "观察当前值和changes()；结合QAT流量确认样本有效。",
        "不能把rate(max)解释成延迟；无流量时应显示N/A。",
    ),
    FamilyGuide(
        "qat-activity-counter", "QAT活动与转换计数 / Activity counters",
        r"^qat\d+_tl_",
        "QAT page request、translation、ME put、read completion、partial transaction及uTLB使用计数。",
        "大多为counter；max_uTLB字段表示上下文最大占用，最大可能值32。",
        "事件counter使用rate/increase；max字段直接观察并结合QAT throughput。",
        "CPU benchmark不会激励QAT；长期0通常表示没有QAT workload。",
    ),
    FamilyGuide(
        "fivr-availability", "FIVR Monitor数据可用性 / Availability",
        r"^fivr_health_monitor_.*_available$",
        "Receiver派生的FIVR monitor数据可用性。",
        "Gauge：1=原始word有效，0=检测到DEADBEEF firmware poison。",
        "直接查询；先判断available，再解释raw/status。",
        "available=0表示数据不可用，不代表FIVR硬件故障。",
    ),
    FamilyGuide(
        "fivr-nonzero-count", "FIVR非零Slot数量 / Non-zero count",
        r"^fivr_health_monitor_.*_nonzero_status_count$",
        "Receiver把64-bit monitor拆成32个2-bit slots后，非零slot的数量。",
        "Gauge，范围0–32。",
        "直接查询；非零时下钻status_N family定位monitor和slot。",
        "这是项目派生指标；公开XML没有slot到rail/core映射，也没有0–3官方枚举。",
    ),
    FamilyGuide(
        "fivr-status-slot", "FIVR两位状态Slot / Status slot",
        r"^fivr_health_monitor_.*_status_\d+$",
        "FIVR 64-bit monitor word中某个2-bit slot的code。",
        "Gauge，取值0–3。",
        "直接查询；仅在available=1时解释，按DeviceId/AccessId/monitor/slot定位。",
        "0=Healthy是当前项目运营约定，不是Intel公开codebook；不能把slot翻译成具体rail或Core。",
    ),
    FamilyGuide(
        "fivr-packed-word", "FIVR打包Health Monitor原始值 / Packed word",
        r"^fivr_health_monitor_\d+_\d+_fivr_health_monitor_\d+$",
        "XML提供的原始64-bit FIVR Health Indicator packed word。",
        "Gauge；每2 bits一个slot。DEADBEEF/DEADBEEFDEADBEEF由receiver识别为poison并抑制raw输出。",
        "技术诊断时查看；日常使用available、nonzero count和status slots。",
        "缺少Intel公开slot/code映射，不能依据非零word直接声明具体硬件故障。",
    ),
    FamilyGuide(
        "core-enable", "Core启用掩码 / Enable masks",
        r"^(?:core_en_c\d+_en|core_enabled_mask_c\d+_en)$",
        "CORE或TOPO/C-Die视角下的local Core enable状态。",
        "Gauge，通常0/1。",
        "直接查询；用于过滤温度0°C和disabled local slots。",
        "两个family来自不同aggregator视角；local Core编号不能直接映射Linux CPU。",
    ),
    FamilyGuide(
        "processor-identity", "处理器CPUID与平台标识 / Processor identity",
        r"^cpuid_platform_id_",
        "处理器family、model、extended model/family、stepping、minor stepping、type和platform ID。",
        "Gauge形式的静态枚举/数值。",
        "直接查询，主要用于inventory、schema选择和跨机器分组。",
        "不是性能指标；数值应按CPUID规范组合解释，engineering sample还需结合QDF。",
    ),
    FamilyGuide(
        "energy-performance-bias", "Core/Socket能效偏好策略 / EPB",
        r"^(?:core_epb_|socket_epb_)",
        "Core输入EPB policy及socket最终resolved EPB policy。",
        "Gauge，策略枚举。",
        "直接查询并比较input与resolved值。",
        "不是功耗或性能百分比；策略编码的业务含义需平台codebook。",
    ),
    FamilyGuide(
        "pem-event-status", "功率事件监控字段 / PEM",
        r"^pem_",
        "PEM control/status以及Fast RAPL、thermal、VR、power-limit、SST等事件源字段。",
        "当前多作为gauge输出；名称中的counter不保证Prometheus类型为counter。",
        "直接观察状态和变化；按具体HELP区分PL1/PL2、MMIO/MSR/TPMI/PCS来源。",
        "缺少公开位级codebook时不能把非零统一解释成故障；多个来源可能同时报告同一限制。",
    ),
    FamilyGuide(
        "mesh-telemetry", "Mesh频率与GV Telemetry",
        r"^mesh_",
        "Mesh GV counter及mesh frequency histogram bins。",
        "当前作为gauge输出，公开HELP未给完整单位和bin边界。",
        "用于同平台相对趋势和bin变化；不要转换为MHz或百分比。",
        "缺少bin codebook与采样语义，不能用于精确mesh频率计算。",
    ),
    FamilyGuide(
        "firmware-version", "Firmware镜像版本 / Image version",
        r"^global_info_firmware_version$",
        "Aggregator暴露的firmware image version。",
        "静态gauge/编码值。",
        "直接查询，用于实验provenance和版本变化检测。",
        "数值编码格式未在HELP中展开，不应当作性能或健康指标。",
    ),
)


UNKNOWN_FAMILY = FamilyGuide(
    "unclassified", "Unclassified XML metric",
    r"$^",
    "当前人工family规则尚未覆盖；使用该metric自己的官方HELP和匹配XML。",
    "由CSV中的Prometheus type、unit和HELP决定。",
    "先直接查询原值，再根据单调性决定是否使用rate/increase。",
    "不要仅根据metric名称猜测单位或硬件健康语义。",
)


def guide_for_metric(metric_name: str) -> FamilyGuide:
    for guide in FAMILY_GUIDES:
        if guide.matches(metric_name):
            return guide
    return UNKNOWN_FAMILY
