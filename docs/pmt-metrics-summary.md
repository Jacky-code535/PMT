# avc01 Intel PMT Metrics 完整清单摘要

> 本文件由 `tools/otel/export_pmt_metric_catalog.py` 从当前运行的 Collector 与 Prometheus 自动生成。

## 总数

- PMT metric 名称数：**5285**
- 当前 PMT time series 数：**65420**
  - BMC Redfish：**32710**
  - OS 带内：**32710**
- 缺少 HELP 说明的 metric 数：**0**
- 完整逐条说明：`docs/pmt-metrics-catalog.csv`

## 按类别统计

| 类别 | metric 名称数 |
|---|---:|
| 使用量与驻留/Usage & Residency | 1092 |
| 内存/Memory | 1067 |
| 温度/Temperature | 832 |
| 频率/Frequency | 781 |
| 电压/Voltage | 768 |
| 状态与配置/Status & Configuration | 247 |
| 功率与能量/Power & Energy | 160 |
| 节流/Throttle | 128 |
| 其他计数器/Other | 118 |
| 缓存与CHA/Cache & CHA | 64 |
| 延迟/Latency | 22 |
| 互连与I/O/Interconnect & I/O | 4 |
| 采集质量/Data loss | 2 |

## 按 Prometheus 类型统计

| 类型 | metric 名称数 |
|---|---:|
| `counter` | 4447 |
| `gauge` | 838 |

## 如何阅读完整 CSV

| 列 | 含义 |
|---|---|
| `metric_name` | Prometheus 查询时使用的准确名称 |
| `category` | 由名称和 HELP 自动归类，便于搜索；最终物理含义仍以 XML/HELP 为准 |
| `type` | Prometheus metric 类型，例如 gauge/counter |
| `unit` | Prometheus metadata 暴露的单位；为空时查 HELP/XML |
| `series_count` | 当前这个名称因为不同 labels 产生的 time series 数量 |
| `redfish_series_count` | BMC Redfish exporter 中的 time series 数量 |
| `inband_series_count` | OS 带内 exporter 中的 time series 数量 |
| `label_names` | 当前 exporter 中观察到的标签名 |
| `help` | PMT XML/receiver 暴露的官方说明，即每条 metric 的主要含义 |

## 重新生成

```bash
cd /root/projects/Intel-PMT
/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py
```

每次更新 PMT XML、切换 BMC 或升级 receiver 后，应重新生成。
