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

合并后 catalog 为 5,285 个名称、65,420 条当前 series。逐指标名称、HELP、类型、单位、标签和两种来源的 series 数量见 `docs/pmt-metrics-catalog.csv`。

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
| `DeviceId` | BMC device ID；带内为 hostname |
| `AccessId` | BMC access ID；带内为 `telemX` |

因此同一指标可按 `CollectionMode` 对比 BMC 与 OS 数据，而不会混淆来源。

## 7. FIVR 特殊处理和语义边界

FIVR 是全指标中的一部分。receiver 对每个有效 64-bit FIVR monitor 额外生成：

- `.available`
- `.status_00` 到 `.status_31`
- `.nonzero_status_count`
- 原始 packed value

`0xDEADBEEF` 和 `0xDEADBEEFDEADBEEF` 是 firmware poison/data-unavailable。遇到 poison 时只输出 `.available=0`，不输出 raw/status，绝不能解释为硬件故障。

XML 只定义“2 bits per FIVR”，没有给出 0/1/2/3 的权威枚举，因此 dashboard 只显示原始两位码和 non-zero count，不擅自命名健康级别。全部偏移、实现和验证见 `docs/gnr-fivr-health-collection-workflow.md`。

## 8. Prometheus、Grafana 和 catalog

Prometheus 配置位于 `/etc/prometheus/prometheus.yml`。Grafana dashboard 的唯一可维护源是：

```text
tools/otel/generate_pmt_dashboard.py
```

它生成：

- `tools/otel/dashboards/pmt-redfish-comprehensive.json`
- `/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json`

不要直接维护 provisioned JSON。dashboard 现有 8 个 row、53 个 panel，并支持 `Collection mode` 来源筛选和全部 metric 探索。

Catalog 生成器 `tools/otel/export_pmt_metric_catalog.py` 同时读取两个 exporter。输出：

- `docs/pmt-metrics-summary.md`
- `docs/pmt-metrics-catalog.csv`

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
```

公司内网正式分享入口已经部署在 `failure-telemetry-vm1`（`10.112.227.52`）：

```text
http://10.112.227.52/d/pmt-avc01-redfish
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
3. `docs/pmt-metrics-summary.md`：先了解指标规模与分类；
4. `docs/pmt-telemetry-backend-reproduction.md` 的原理章节：理解 PMT、XML、OTel、Prometheus 和 Grafana；
5. `docs/gnr-fivr-health-collection-workflow.md`：FIVR 精确 XML、poison 和交叉验证细节；
6. `docs/pmt-telemetry-backend-reproduction.md` 的部署与排障章节：从零复现和日常运维；
7. `docs/pmt-metrics-catalog.csv`：开发查询和 panel 时按需检索，不需要顺序通读；
8. 配置、receiver、dashboard/catalog 生成器和 systemd 源文件：修改实现时再读；
9. `docs/getting-started.md`、`docs/use-cases.md`、`docs/FAQ.md`：上游通用背景，不能覆盖本文的 avc01 生产事实。

如果文档中的 URL、metric 数、panel 数或采集模式互相冲突，以本文、当前运行配置/API 实测及自动生成 catalog 为准。
