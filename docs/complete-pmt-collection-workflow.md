# avc01 Intel PMT 完整采集工作流程（从这里开始）

本文是本项目的**运行事实总入口**，说明当前所有工作、设计结论、运行链路、文件位置和验证方法。第一次接触整个资料库时，先看 `docs/README.md` 的分层导航，再读本文；FIVR、后端复现和逐指标资料由本文链接到对应深度文档。

## 1. 当前结果

avc01 已同时运行两条严格 XML 驱动的生产链路：

1. **BMC 带外**：Redfish snapshot → Collector → `localhost:8889`。
2. **OS 带内**：`/sys/class/intel_pmt/telem*` → avc01 Collector → `10.239.89.3:8889`。

两条链路都扫描全部 telemetry aggregator，并按精确 `(GUID, Size)` 选择 XML 后提取**所有已匹配指标**，不是只读取 FIVR。当前验证结果：

| 项目 | BMC Redfish | OS 带内 |
|---|---:|---:|
| metric 名称 | 5,285 | 5,285 |
| time series | 32,710 | 32,710 |
| FIVR series | 642 | 642 |
| 采集周期 | 20 秒 | 20 秒 |

合并后 catalog 为 5,285 个名称、65,420 条当前 series。逐指标名称、HELP、类型、单位、单位来源、标签和两种来源的 series 数量见 `docs/pmt-metrics-catalog.csv`；人读分类和单位解释见 `docs/pmt-metrics-summary.md`。

## 2. 总体架构

```text
                  +-- BMC Redfish snapshot ----------------------+
avc01 hardware ---+                                               +--> Prometheus :9090 --> Grafana
                  +-- Linux /sys/class/intel_pmt/telem* ----------+
                         exact GUID + Size -> XML decode all fields
```

Prometheus jobs：

- `otel-pmt`：后端主机上的 BMC Collector，`localhost:8889`；
- `otel-pmt-inband`：avc01 OS 上的 local Collector，`10.239.89.3:8889`。

Grafana dashboard 使用 `CollectionMode` 变量选择 `redfish`、`local` 或两者，并使用公共标签 `PMTEndpoint`、`DeviceId`、`AccessId`、`PMTGuid` 过滤数据。

### 2.1 当前 CPU 和 Aggregator 拓扑

目标 OS 的 `lscpu` 与 BMC Redfish 已交叉确认：

- 2-socket Intel Granite Rapids Xeon engineering sample，QDF `Q4G7`；
- 每 socket 96 physical cores、192 threads；
- 整机 192 physical cores、384 logical CPUs；
- 6 个 NUMA nodes；
- 两种采集来源各发现 36 个 aggregator。

36 个 aggregator 不是 36 个 CPU，也不是 36 个温度传感器，而是 36 块按数据域组织的 telemetry region：

| 数据域 | GUID | Size | 实例数 | 主要采集内容 |
|---|---|---:|---:|---|
| OOBMSM CORE | `0x22473996` | 14496 | 6 | Core 温度、usage、三个 residency histogram、throttle、data loss |
| PUNIT C-Die | `0x22806802` | 6784 | 6 | C-state、energy/policy、FIVR |
| OOBMSM RMID | `0x477e9373` | 6160 | 6 | CHA/RMID RDT MBM 和 CMT |
| TOPO Leaf | `0x3d4bb41a` | 24 | 8 | MCTP、Domain、UPI、socket topology |
| TOPO Root | `0x3d4bb40a` | 48 | 2 | CHA enable 等 root topology |
| PUNIT IO-Die | `0x22491753` | 6272 | 4 | IO PUNIT、socket EPB、FIVR availability |
| OOBMSM QAT | `0x6e94ffa0` | 176 | 4 | QAT PCIe 累计 MB 和 latency |

7 组实例相加为 36。完整 36 行 `DeviceId/AccessId/SourceId/GUID` 对照、Core 局部编号、Local/Redfish 对应边界见 `docs/pmt-platform-topology.md`。

## 3. XML 和严格匹配原则

当前准确 metadata 来源是上传到工作区的 Intel PMT support repository：

```text
/root/projects/applications.manageability.intel-pmt.tools.python.support.intel-pmt-master/xml/pmt.xml
```

它包含真实 GNR PUNIT 映射：

| Die | GUID | Size | XML basedir |
|---|---|---:|---|
| C-Die | `0x22806802` | 6784 | `GNR/PUNIT/CDIE` |
| IO-Die | `0x22491753` | 6272 | `GNR/PUNIT/IODIE` |

生产路径永远执行精确 `(GUID, Size)` 匹配。GUID-only fallback 只存在于离线 debug 工具，不会进入 Prometheus。内部 XML 没有复制进个人 Git 仓库；avc01 的运行副本安装在 `/opt/intel-pmt/xml`。

## 4. BMC 带外全指标流程

生产配置源文件：`tools/otel/configs/config-avc01-pmt-redfish.yaml`。

运行服务：`otelcol-pmt.service`。Collector 每 20 秒请求 Redfish PMT snapshot，逐 aggregator 读取 GUID、Size 和 Base64 Data，精确选择 XML，计算所有 low-level/high-level samples，然后暴露 Prometheus metrics。

BMC 凭据只保存在 `/etc/otelcol-pmt-redfish.env`，不得写入配置、文档、日志或 Git。

完整部署、离线 snapshot 验证和故障排查见：

- `docs/pmt-telemetry-backend-reproduction.md`
- `docs/gnr-fivr-health-collection-workflow.md`

## 5. OS 带内全指标流程

带内不是用 C 程序硬编码 5,285 个指标。Collector 的 `local` mode 完成完整采集：

1. 扫描 `/sys/class/intel_pmt/telem*`；
2. 对每个设备读取 `guid`、`size` 和完整 `telem` 二进制；
3. 使用 `/opt/intel-pmt/xml/pmt.xml` 精确匹配；
4. 根据 aggregator/interface/common XML 提取并转换所有字段；
5. 每 20 秒把所有 metrics 暴露在 avc01 `0.0.0.0:8889`。

相关文件：

- Collector 配置：`tools/otel/configs/config-avc01-pmt-local.yaml`
- systemd unit：`tools/in-band/systemd/otelcol-pmt-local.service`
- receiver 实现：`tools/otel/intelpmtreceiver/receiver.go`
- avc01 安装配置：`/etc/otelcol-pmt-local.yaml`
- avc01 binary：`/usr/local/bin/otelcol-pmt-local`
- avc01 metadata：`/opt/intel-pmt/xml`
- avc01 service：`otelcol-pmt-local.service`

`tools/in-band/read_pmt_metric.c` 和原 FIVR timer 仍是最小依赖的 raw 数据交叉验证工具，不是全指标生产采集器。

## 6. 公共标签

receiver 保留原有来源专用标签，同时为两种模式提供公共标签：

| 标签 | 含义 |
|---|---|
| `CollectionMode` | `redfish` 或 `local` |
| `PMTEndpoint` | 平台名，当前为 `avc01` |
| `PMTGuid` | aggregator GUID |
| `PMTSizeBytes` | telemetry region 字节数 |
| `DeviceId` | Redfish 为 BMC CPU ID 0/1；带内为 hostname |
| `AccessId` | Redfish 为 MCTP telemetry access；带内为 `telemX`，不是传感器物理坐标 |

因此同一指标可按 `CollectionMode` 对比 BMC 与 OS 数据，而不会混淆来源。Dashboard 中 `Core17 · D0/A27` 表示“Device 0、Access 27 aggregator 中的局部 Core17 字段”；它不能直接等同于 Linux global CPU 17。完整标签解释见 `docs/pmt-platform-topology.md`。

## 7. FIVR 特殊处理和语义边界

FIVR 是全指标中的一部分。receiver 对每个有效 64-bit FIVR monitor 额外生成：

- `.available`
- `.status_00` 到 `.status_31`
- `.nonzero_status_count`
- 原始 packed value

`0xDEADBEEF` 和 `0xDEADBEEFDEADBEEF` 是 firmware poison/data-unavailable。遇到 poison 时只输出 `.available=0`，不输出 raw/status，绝不能解释为硬件故障。

XML 只定义“2 bits per FIVR”，没有给出 0/1/2/3 的权威枚举。Dashboard 当前采用明确的运营展示约定：C-Die 的 packed words 和全部两位码均为 0、且数据可用时显示 `Healthy`，任一两位码非零时显示 `Unhealthy`；IO-Die 保留显示 `DEADBEEF`，不解释为硬件故障。独立 FIVR 诊断区会在出现非零码时列出 C-Die instance、monitor、slot、code 和采集来源，但不能把 slot 翻译为具体 rail/core。`Healthy`/`Unhealthy` 是项目运营约定，不是 XML 官方枚举。全部偏移、实现和验证见 `docs/gnr-fivr-health-collection-workflow.md`。

## 8. Prometheus、Grafana 和 catalog

Prometheus 配置位于 `/etc/prometheus/prometheus.yml`。Grafana dashboard 有两个独立可维护源：

```text
tools/otel/generate_pmt_dashboard.py                  # 保留的8栏技术演示版 + Explorer
tools/otel/generate_gnr_telemetry_overview.py         # 新版内部GNR架构化Overview
```

前者生成：

- `tools/otel/dashboards/pmt-redfish-comprehensive.json`
- `tools/otel/dashboards/pmt-metric-explorer.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-metric-explorer.json`

不要直接维护 provisioned JSON。客户演示dashboard现有8个row、34个dashboard entries（26个可视化panel和8个row header）、29个PromQL targets。默认使用`redfish`，避免把BMC与local重复聚合；需要交叉验证时再选择两种来源。01总览只回答三个客户问题：PMT Demo是否Ready、当前最高Core温度、C-Die FIVR monitor是否Healthy，并给出一张CPU温度趋势；data loss不再作为首页状态或趋势展示。

第05栏Frequency/Temperature/Voltage residency使用顶部`05 Residency window`选择2m、5m、10m、15m、30m或1h窗口。第07栏保留技术诊断：data-loss历史累计值、最近15分钟新增量和内部timestamp；只有多个PMT更新窗口持续增长，或workload结束后仍增长，才需要升级调查。Grafana原生dashboard variable不能嵌入row，因此主页面移除全局metric搜索框，第08栏链接到独立`Intel PMT · Advanced Metric Explorer`。Explorer有1个row、5个entries（4个可视化panel）、4个PromQL targets，搜索框与结果紧邻。

新版内部 `Intel PMT · GNR Redfish/Local Overview · Internal` 使用两个独立UID
`pmt-gnr-redfish-overview`和`pmt-gnr-local-overview`，不会覆盖上述8栏Dashboard。它生成：

- `tools/otel/dashboards/pmt-gnr-redfish-overview.json`
- `tools/otel/dashboards/pmt-gnr-local-overview.json`
- `tools/otel/dashboards/pmt-gnr-metric-explorer.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-redfish-overview.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-local-overview.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-gnr-metric-explorer.json`

新版按采集路径拆成Redfish与Local两个Overview，每个共7个row、25个内容panel和
32个PromQL targets，顶部仅保留全局有效的endpoint。两个Dashboard通过Header链接
互相切换，并保留时间范围。Analysis固定为各Panel明确标注的5分钟窗口，
不再伪装成全局变量。它只显示可证明单位，未知缩放统一标为Raw，
并通过独立Explorer访问全部5,285个metric names。内部双语阅读说明、每个panel的含义、
单位和Open Semantics Register见`docs/gnr-telemetry-dashboard-guide.md`。

Catalog 生成器 `tools/otel/export_pmt_metric_catalog.py` 同时读取两个 exporter。输出：

- `docs/pmt-metrics-summary.md`
- `docs/pmt-metric-family-reference.md`
- `docs/pmt-metrics-catalog.csv`

Family reference 当前把全部 5,285 个名称归入38个经人工审核的family，逐family说明含义、数值语义、推荐查询、正常/异常边界和代表性HELP；其中data loss明确区分CPU内部processing cycle、20秒Collector读取和Prometheus scrape。完整 CSV 的每个准确 metric name 都增加 `family_id`、`family_title`、`value_semantics`、`recommended_query` 和 `caveat`，同时保留HELP、Prometheus type、单位、`unit_source`、series数量和labels。Prometheus metadata 当前没有PMT unit；可从标准OpenTelemetry名称后缀推断的单位标记为 `metric_name_suffix`，其余明确标记 `unspecified`，不能根据名称自行猜测。当前5,285个名称中2,990个可从后缀推断，2,295个尚无可靠单位，未归类名称为0。

BMC 单次数据快照由 `tools/otel/export_pmt_bmc_snapshot.py` 对
`http://localhost:8889/metrics` 执行一次 scrape，并输出
`docs/pmt-bmc-snapshot.csv`。CSV 每行是一条 time series，包含当前值、类型、
HELP、完整 labels 和单位提示。由于 Prometheus metadata 当前不提供 unit，
非空单位由 OpenTelemetry 写入 metric name 的后缀推断，并通过
`unit_source=metric_name_suffix` 明确标记；`unit_source=unspecified` 表示 XML
未声明单位或无法可靠推断。

## 9. 日常验证

### 分享 Dashboard

当前后端 VM 的 `10.0.10.15` 是 VM 私网地址，不能作为浏览器分享地址。VS Code 已转发本机端口时，当前用户使用：

```text
http://localhost:3000/d/pmt-avc01-redfish
http://localhost:3000/d/pmt-gnr-redfish-overview
http://localhost:3000/d/pmt-gnr-local-overview
```

公司内网正式分享入口已经部署在 `failure-telemetry-vm1`（`10.112.227.52`）：

```text
http://10.112.227.52/d/pmt-avc01-redfish
http://10.112.227.52/d/pmt-gnr-redfish-overview
http://10.112.227.52/d/pmt-gnr-local-overview
```

观看者只需浏览器，无需 VS Code、SSH、Grafana 登录或开发服务器账号。数据路径为：浏览器 → Demo VM nginx:80 → Demo VM `127.0.0.1:13000` → persistent reverse SSH tunnel → Collector VM Grafana `127.0.0.1:3000`。

Collector VM 上的 `grafana-demo-tunnel.service` 已启用并设置为异常自动重启和开机启动。部署源文件位于：

- `tools/otel/deploy/demo-server/grafana-demo-tunnel.service`
- `tools/otel/deploy/demo-server/grafana-demo.nginx`

运维检查：

```bash
systemctl status grafana-demo-tunnel.service
ssh root@10.112.227.52 -p 2522 'systemctl status nginx'
```

应分享上面的普通 dashboard URL，而不是 Grafana 的 externally shared/public snapshot URL。此 dashboard 依赖 `endpoint`、`mode`、`device`、`access`、`die`、`core` 等 template variables；snapshot/public 分享方式可能不执行这些变量查询，最终把空值带入 PromQL 并显示 `No data`。

Grafana 已在 `/etc/grafana/grafana.ini` 启用 anonymous `Viewer`，访问者无需使用管理员会话。Prometheus datasource 使用 server-side proxy，因此访问者的浏览器不需要直接连接 Prometheus。Demo VM 仅公开 nginx 端口；反向 tunnel 只监听 Demo VM 的 loopback `127.0.0.1:13000`，Prometheus 未被公开。

无登录验证结果：外部 health HTTP 200、dashboard HTTP 200、dashboard API HTTP 200、datasource query HTTP 200；浏览器完整加载后 `No data = 0`、panel error = 0，当前查询返回 65,420 条 PMT series。

服务状态：

```bash
systemctl is-active otelcol-pmt prometheus grafana-server
ssh root@10.239.89.3 systemctl is-active otelcol-pmt-local
```

Prometheus 验证：

```promql
up{job=~"otel-pmt.*"}
count(count by (__name__) ({PMTEndpoint="avc01",CollectionMode="redfish"}))
count(count by (__name__) ({PMTEndpoint="avc01",CollectionMode="local"}))
count({PMTEndpoint="avc01",CollectionMode="local"})
```

两个 metric-name count 当前都应为 5,285；单来源 series count 当前应为 32,710。硬件、固件或 XML 版本变化后，数量允许变化，应优先检查 Collector 日志中的 XML lookup 错误，而不是放宽匹配规则。

## 10. 修改、测试和回滚顺序

修改 receiver 后：

1. `gofmt`；
2. 在 `tools/otel/intelpmtreceiver` 执行 `go test ./...`；
3. 重建 `otelcol-pmt`；
4. 分别验证 BMC/local 配置；
5. 先部署一条来源并确认 exporter，再更新另一条；
6. 验证 Prometheus targets 和 dashboard；
7. 重新生成 catalog。

回滚时两条 Collector 相互独立：停止 avc01 的 `otelcol-pmt-local` 不影响 BMC；停止后端 `otelcol-pmt` 不影响带内 exporter。Prometheus 中保留独立 job，便于定位来源故障。

## 11. 文档阅读顺序

完整的角色化阅读地图见 `docs/README.md`。最推荐的完整顺序是：

1. `docs/README.md`：文档导航、角色路线、优先级和冲突处理；
2. **本文**：当前真实架构、状态、分享、验证与回滚；
3. `docs/pmt-platform-topology.md`：理解 CPU/Core、36 个 aggregator、标签和采集数据域；
4. `docs/pmt-metrics-summary.md`：理解指标规模、分类、类型、单位和代表性指标族；
5. `docs/pmt-telemetry-backend-reproduction.md` 的原理章节：理解 PMT、XML、OTel、Prometheus 和 Grafana；
6. `docs/gnr-fivr-health-collection-workflow.md`：FIVR 精确 XML、poison 和交叉验证细节；
7. `docs/pmt-telemetry-backend-reproduction.md` 的部署与排障章节：从零复现和日常运维；
8. `docs/pmt-metrics-catalog.csv`：开发查询和 panel 时按需检索，不需要顺序通读；
9. 配置、receiver、dashboard/catalog 生成器和 systemd 源文件：修改实现时再读；
10. `docs/getting-started.md`、`docs/use-cases.md`、`docs/FAQ.md`：上游通用背景，不能覆盖本文的 avc01 生产事实。

如果文档中的 URL、metric 数、panel 数或采集模式互相冲突，以本文、当前运行配置/API 实测及自动生成 catalog 为准。
