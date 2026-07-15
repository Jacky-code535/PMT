# Intel PMT 文档导航与阅读顺序

本页只负责回答三个问题：**先读什么、不同角色读什么、文档冲突时信什么**。avc01 当前运行事实以 `complete-pmt-collection-workflow.md` 为唯一总入口。

## 一、先看懂文档的四个层次

### L0：导航层（2 分钟）

当前页面。先确认自己的目标，再按下面的路线阅读，不需要从头读完所有文件。

### L1：全局层（15–30 分钟，所有人必读）

第一份阅读：`complete-pmt-collection-workflow.md`。

建议顺序：

1. 第 1–2 节：当前结果与总体架构；
2. 第 3–8 节：XML、BMC、OS、标签、FIVR、Prometheus/Grafana 各层职责；
3. 第 9 节：Dashboard 分享和日常验证；
4. 第 10 节：修改、测试、回滚顺序。

读完应能回答：数据从哪里来、如何解码、存在哪里、在哪里查看、服务坏了先查哪一层。

### L2：专题层（按职责选读）

| 目标/角色 | 阅读资料 | 重点 |
|---|---|---|
| 只看 Dashboard 的观看者 | `complete-pmt-collection-workflow.md` 第 1、2、9 节 | 分享链接、变量、数据是否正常 |
| 日常运维 | `complete-pmt-collection-workflow.md` 全文，再读 `pmt-telemetry-backend-reproduction.md` 第 8、11、12、16、17 节 | Collector、systemd、Prometheus、日志、故障定位 |
| 从零理解技术原理 | `pmt-telemetry-backend-reproduction.md` 第 0、3、7、8 节 | collect/decode/scrape/visualize、PMT、XML、Collector/OCB |
| Receiver/解码开发 | 主流程第 3–7、10 节，再读 `gnr-fivr-health-collection-workflow.md` | `(GUID, Size)`、XML 转换、公共标签、poison、安全语义 |
| FIVR 专项分析 | `gnr-fivr-health-collection-workflow.md` | 精确 XML、64-bit 展开、poison、带内交叉验证 |
| Dashboard/PromQL 开发 | 主流程第 6、8、9 节，再查指标摘要和 CSV | 标签模型、metric 类型、准确 metric 名称 |
| 新机器复现 | 主流程先确定当前事实，再读 `pmt-telemetry-backend-reproduction.md` 第 6–12、20 节 | 环境、构建、凭据、systemd、Prometheus |

### L3：参考层（需要时查询，不要顺序通读）

1. `pmt-metrics-summary.md`：先看指标规模、分类、类型；
2. `pmt-metrics-catalog.csv`：按准确 metric 名、HELP、unit、labels 查询 5,285 个指标；
3. Intel PMT support repository 的 `xml/pmt.xml`：字段布局和转换的最终 metadata 来源；
4. `FAQ.md`：通用概念、治理、安全和常见问答；
5. `use-cases.md`：上游项目的最小通用示例，不代表 avc01 生产配置；
6. `getting-started.md`：上游仓库最小入门，不代表当前双链路部署。

### L4：实现与部署源文件（修改系统时阅读）

| 系统层 | 可维护源 |
|---|---|
| BMC Collector 配置 | `tools/otel/configs/config-avc01-pmt-redfish.yaml` |
| OS 带内 Collector 配置 | `tools/otel/configs/config-avc01-pmt-local.yaml` |
| Receiver | `tools/otel/intelpmtreceiver/receiver.go`、`common_processor.go` |
| Dashboard 生成器 | `tools/otel/generate_pmt_dashboard.py` |
| Dashboard 生成结果 | `tools/otel/dashboards/pmt-redfish-comprehensive.json`（不要手工维护） |
| Catalog 生成器 | `tools/otel/export_pmt_metric_catalog.py` |
| Demo 分享 tunnel | `tools/otel/deploy/demo-server/grafana-demo-tunnel.service` |
| Demo nginx | `tools/otel/deploy/demo-server/grafana-demo.nginx` |

### L5：外部培训与历史验证材料（最后读）

工作区 `failure telemetry infra/` 下还有视频、PPT、PDF、Word、Excel 和独立验证程序。它们用于背景学习、寄存器参考或与旧验证流程对照，不是当前生产运行手册：

| 材料 | 定位 |
|---|---|
| `Intro to Intel PMT.pptx`、`757525_PMT_Linux_Telemetry_Collection_Rev1p0.mp4` | PMT 背景培训 |
| `Intel Platform Monitoring Technology Telemetry data collection on Linux -r1.1.docx` | Linux PMT 通用说明 |
| `PMT_In_Band_Validation_Guide_v1.2.docx`、`PMT_In_Band_Validation_Guide_to_alibaba.pdf` | 带内历史验证参考 |
| `PMT_Out_of_Band_Valiation_Guide_to_alibaba.pdf` | 带外历史验证参考 |
| `BHS_PMT_registers_list_Tencent_93828825.xlsx` | 特定平台寄存器参考，不能替代 GNR 精确 XML |
| `read_aet 1.c` | 独立 C 验证样例，不是 5,285 指标生产采集器 |
| `validate_bmc_pmt_redfish.sh` | BMC Redfish 独立验证脚本 |
| `send_backend_test_metric.py` | synthetic backend 测试，不是真实 PMT 数据源 |

这些材料与当前实现冲突时，仍以主流程、运行配置、精确 XML 和实测结果为准。

## 二、推荐的完整阅读路线

如果目标是“了解全流程工作以及所有说明文档”，按以下顺序：

1. **本导航**：先建立文档地图；
2. **完整工作流程**：掌握当前真实架构和运行状态；
3. **指标摘要**：了解系统到底采集了哪些类别；
4. **后端复现文档的原理章节**：补齐 PMT、XML、OTel、Prometheus、Grafana 原理；
5. **FIVR 专项文档**：理解本项目最特殊的数据安全与语义边界；
6. **后端复现文档的部署/运维章节**：理解如何重建与排障；
7. **指标 CSV**：实际查询或开发 panel 时按需检索；
8. **配置、Go、Python 和 systemd 源文件**：只有需要修改实现时再读；
9. **Getting Started、Use Cases、FAQ**：作为上游通用背景补充；
10. **外部培训与历史验证材料**：最后按需查看，不用于决定当前部署参数。

不建议先通读 CSV，也不建议从 Python agent 或某个配置文件倒推整套生产架构。

## 三、系统层次与故障定位

```text
L1 数据源       avc01 hardware / BMC Redfish / Linux intel_pmt sysfs
       ↓
L2 解码采集     intelpmtreceiver + exact (GUID, Size) + pmt.xml
       ↓
L3 指标出口     Collector Prometheus exporter :8889
       ↓
L4 存储查询     Prometheus :9090
       ↓
L5 展示         Grafana :3000
       ↓
L6 分享入口     Demo VM nginx :80 + reverse SSH tunnel
```

排障始终从下往上检查：源数据 → XML 匹配 → Collector exporter → Prometheus target/query → Grafana panel → Demo 分享入口。外部链接打不开不等于 PMT 没有采到数据。

## 四、文档优先级与冲突处理

发生内容冲突时按以下顺序判断：

1. `complete-pmt-collection-workflow.md`：avc01 当前部署和验证结果；
2. 当前运行配置、systemd unit、服务/API 实测结果；
3. `gnr-fivr-health-collection-workflow.md`：FIVR 专项实现；
4. `pmt-metrics-summary.md` 和 `pmt-metrics-catalog.csv`：当前自动生成指标事实；
5. `pmt-telemetry-backend-reproduction.md`：原理、复现、历史排障过程；
6. `getting-started.md`、`use-cases.md`、`FAQ.md`：上游通用资料。

长篇复现文档包含系统演进过程。若其中的 URL、panel 数、metric 数或单链路描述与主流程不同，以主流程和当前自动生成 catalog 为准。

## 五、三条最短路线

### 只想会看

本导航 → 主流程第 1、2、9 节 → Dashboard。

### 想会运维

本导航 → 主流程全文 → 后端复现第 8、11、12、16、17 节 → FIVR 第 12 节回滚。

### 想会开发

本导航 → 主流程全文 → 后端复现第 0、3、7、8 节 → FIVR 全文 → Receiver/配置/生成器源码 → 指标 CSV。
