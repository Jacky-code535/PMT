# GNR FIVR Health 精确 XML 采集工作流程

本文记录 avc01 Granite Rapids（GNR）FIVR Health 的完整生产流程，包括 BMC Redfish、OpenTelemetry Collector、Prometheus、Grafana，以及 Linux OS 带内交叉验证。

## 1. 最终结论

已上传的 Intel PMT support metadata 包含与真实平台完全匹配的 GNR PUNIT 定义：

| Die | GUID | telemetry size | FIVR offsets | XML 目录 |
|---|---|---:|---|---|
| C-Die | `0x22806802` | 6784 | 1440、1448、1456 | `xml/GNR/PUNIT/CDIE` |
| IO-Die | `0x22491753` | 6272 | 32、40、48 | `xml/GNR/PUNIT/IODIE` |

映射入口为：

```text
/root/projects/applications.manageability.intel-pmt.tools.python.support.intel-pmt-master/xml/pmt.xml
```

BMC 和 avc01 OS 暴露相同的 GUID、size 和 FIVR 字节值。因此：

- 生产 Collector 继续使用严格 `(GUID, Size)` 匹配；
- 不需要、也没有启用 GUID-only fallback；
- C-Die 的三个 FIVR monitor 当前均为 0；
- IO-Die 的三个 monitor 当前均为 `0xdeadbeefdeadbeef`；
- `DEADBEEF` 是明显的 debug/data-unavailable sentinel，不是合理的 packed FIVR 状态，不得解释为硬件故障状态；
- XML 只说明“2 bits per FIVR”，未提供 slot 对应的 rail 名称，也未提供 0/1/2/3 的权威状态枚举。当前管理层 dashboard 采用项目运营约定：C-Die 全 0 且数据可用时显示 Healthy；该显示不等同于 XML 官方枚举。

### 1.1 “无法解析”的准确原因

当前问题不是 GUID、offset、大小、字节序或解析器错误。完整检查 production XML、preproduction XML、生成的 JSON、Python 工具和 upstream Git 历史后，能确定：

1. C-Die 的三个 64-bit words 位于 1440、1448、1456，实测全部为 `0x0000000000000000`；
2. IO-Die 的三个 words 位于 32、40、48，实测全部为 `0xDEADBEEFDEADBEEF`；
3. Redfish 与 Linux in-band 在所有实例上给出相同结果；
4. metadata 唯一的语义描述是 `FIVR Health Indicator Status - 2bits per FIVR`；
5. metadata 没有提供 `slot 0..95 -> FIVR rail` 和 `code 0..3 -> 状态含义` 两张必要映射表。

因此当前能做出的最强、且不会误导客户的结论是：

- **C-Die：所有公开 packed fields 均为 0。** Dashboard 按当前项目约定显示 Healthy，但 metadata 没有 codebook，因此该名称不是平台规范结论；
- **IO-Die：FIVR 状态不可用。** DEADBEEF 是 sentinel，不能拆成 2-bit 状态后解释；
- 若需要 rail 级 Healthy/Warning/Fault，必须向 GNR PUNIT/FIVR firmware owner 获取内部 register/BXML codebook，或要求 Intel-PMT metadata 补充 bitfield 和枚举定义。

## 2. 数据流

```text
BMC CollectDiagnosticData action
  -> PMTTelemetrySnapshot.json
  -> Base64 Data
  -> exact GUID + Size lookup in pmt.xml
  -> aggregator XML extracts raw fields
  -> aggregator-interface XML executes transforms
  -> receiver expands each valid FIVR 64-bit word into 32 two-bit gauges
  -> OpenTelemetry metrics
  -> Prometheus :9090
  -> Grafana dashboard
```

每 20 秒重复一次。一次 snapshot 是一个时间点的数据，不代表采集只运行一次。

## 3. BMC 配置

仓库配置：

```text
tools/otel/configs/config-avc01-pmt-redfish.yaml
```

核心配置：

```yaml
receivers:
  intelpmtreceiver:
    interval: 20s
    metadata: "/root/projects/applications.manageability.intel-pmt.tools.python.support.intel-pmt-master/xml/pmt.xml"
    mode: redfish
```

BMC Authorization 只保存在：

```text
/etc/otelcol-pmt-redfish.env
```

权限必须为 `0600`，凭据不得写入 YAML、日志、Git 或文档。

## 4. 精确 XML 验证

在上线前使用保存的 snapshot 做离线验证：

```bash
cd /root/projects/Intel-PMT/tools/otel/intelpmtreceiver
go run ./cmd/pmt-fallback-debug \
  -metadata /root/projects/applications.manageability.intel-pmt.tools.python.support.intel-pmt-master/xml/pmt.xml \
  -input /tmp/pmt-redfish-validation/snapshot.json \
  > /tmp/pmt-exact-decode.json
```

尽管工具名称保留 `fallback-debug`，本次结果为：

- 36/36 aggregators 精确匹配；
- 0 个 fallback；
- 0 个 lookup error；
- 6 个 C-Die instance，每个解析 410 个 XML metrics；
- 4 个 IO-Die instance，每个解析 52 个 XML metrics。

检查：

```bash
jq '{
  results: (.results | length),
  errors: (.errors | length),
  exact: ([.results[] | select(.exact_guid_size_match)] | length),
  fallback: ([.results[] | select(.unique_guid_fallback)] | length)
}' /tmp/pmt-exact-decode.json
```

只有 exact=36、fallback=0、errors=0 时，才允许进入生产链路。

## 5. Receiver 的 FIVR 安全处理

XML 中每个 `FIVR_HEALTH_MONITOR_N` 是 64-bit packed word。receiver 生成：

| 后缀 | 含义 |
|---|---|
| 无后缀 | 有效 packed raw word |
| `.available` | 1=packed word 存在，0=DEADBEEF sentinel |
| `.status_00` ... `.status_31` | `(raw >> (2 * index)) & 3` |
| `.nonzero_status_count` | 32 个两位码中非零码的数量 |

若 raw 为 `0xDEADBEEF` 或 `0xDEADBEEFDEADBEEF`：

1. 输出 `.available=0`；
2. 不输出 raw；
3. 不输出 32 个伪状态；
4. 不把 sentinel 当作 FIVR 状态送入 Prometheus。

所有 Redfish metrics 增加两个来源标签：

- `PMTGuid`
- `PMTSizeBytes`

这样 dashboard 可以区分 C-Die、IO-Die，并证明数据来自哪个精确 mapping。

## 6. 构建与部署 Collector

```bash
cd /root/projects/Intel-PMT/tools/otel/intelpmtreceiver
go test ./...

cd ../build-minimal
go build -o otelcol-pmt .
./otelcol-pmt --version

sudo install -m 0755 otelcol-pmt /usr/local/bin/otelcol-pmt
sudo install -m 0644 ../configs/config-avc01-pmt-redfish.yaml \
  /etc/otelcol-pmt-local.yaml
sudo /usr/local/bin/otelcol-pmt validate \
  --config /etc/otelcol-pmt-local.yaml
sudo systemctl restart otelcol-pmt
```

检查：

```bash
systemctl is-active otelcol-pmt
journalctl -u otelcol-pmt --since '-5 minutes' --no-pager \
  | grep -E 'Failed to find XML set|Failed to setup aggregator'
curl -fsS http://127.0.0.1:8889/metrics \
  | grep '^fivr_health_monitor_' | head
```

当前生产验证结果：

- Collector active；
- 不再出现 PUNIT 6784/6272 lookup failure；
- exporter 当前有 642 条 FIVR series；
- C-Die availability=1；
- IO-Die availability=0，因为 payload 明确为 `DEADBEEF` sentinel。

BMC 偶尔可能在触发 snapshot 时返回 503。单次 503 不应导致使用旧 snapshot 冒充新数据；Collector 会在下一个 20 秒周期重试。

## 7. Prometheus 指标示例

```promql
# C-Die monitor 数据是否全部有效
min({__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22806802"})

# IO-Die monitor 数据是否全部有效
min({__name__=~"fivr_health_monitor_.*_available",PMTGuid="0x22491753"})

# 当前不可用 monitor word 数
count({__name__=~"fivr_health_monitor_.*_available"})
-
sum({__name__=~"fivr_health_monitor_.*_available"})

# 有效 monitor 中非零两位码总数
sum({__name__=~"fivr_health_monitor_.*_nonzero_status_count"})
```

Prometheus exporter 会把 OTel metric name 中的点转换为下划线。

## 8. Grafana dashboard

生成器和输出：

```text
tools/otel/generate_pmt_dashboard.py
tools/otel/dashboards/pmt-redfish-comprehensive.json
/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json
```

重新生成：

```bash
cd /root/projects/Intel-PMT/tools/otel
/usr/bin/python3 generate_pmt_dashboard.py
sudo systemctl restart grafana-server
```

FIVR section 包含：

- 客户总览只保留一张简明`C-Die FIVR Monitor`卡；完整信息位于独立`FIVR Health & Diagnostics` row；
- C-Die 总体 `Healthy`/`Unhealthy`、非零 slot 数量和 IO-Die `DEADBEEF` 数据状态；
- 只在检测到非零码时显示的定位表，列出 C-Die instance、Access、monitor、slot、code 和 CollectionMode；
- 技术人员仍可通过`PMT GUID / Die`筛选器和独立`Advanced Metric Explorer`查询底层series。

当前客户dashboard为8 rows、34个dashboard entries（26个可视化panel）、29个PromQL targets。当前默认Redfish数据下，C-Die总体查询返回`Healthy`，非零数量返回0，IO-Die返回`DEADBEEF`，非零定位表为空；空表是正常结果，表示没有检测到非零slot。

## 9. Metric catalog

XML 或 receiver 更新后必须重新生成：

```bash
cd /root/projects/Intel-PMT
/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py
```

输出：

```text
docs/pmt-metrics-catalog.csv
docs/pmt-metrics-summary.md
```

## 10. Linux OS 带内交叉验证

Linux 路径：

```text
/sys/class/intel_pmt/telemX/guid
/sys/class/intel_pmt/telemX/size
/sys/class/intel_pmt/telemX/telem
```

不要硬编码 `telemX`。`read_pmt_metric` 会扫描设备并按 GUID+size 精确匹配：

```bash
cd /root/projects/Intel-PMT
gcc -std=c11 -Wall -Wextra -Werror -O2 \
  tools/in-band/read_pmt_metric.c -o read_pmt_metric
sudo ./read_pmt_metric --fivr
```

内置 exact schema：

- C-Die：size 6784，offset 1440/1448/1456；
- IO-Die：size 6272，offset 32/40/48。

工具使用 `pread()` little-endian 读取，输出 JSON Lines，识别 `DEADBEEF` sentinel，并只为真实 packed word 输出 `two_bit_codes`。

周期采集：

```bash
sudo install -m 0755 read_pmt_metric /usr/local/bin/read_pmt_metric
sudo install -m 0755 tools/in-band/collect_fivr_health.sh \
  /usr/local/libexec/collect_fivr_health.sh
sudo install -m 0644 tools/in-band/systemd/intel-pmt-fivr-health.service \
  /etc/systemd/system/
sudo install -m 0644 tools/in-band/systemd/intel-pmt-fivr-health.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now intel-pmt-fivr-health.timer
```

输出文件：

```text
/var/lib/intel-pmt/fivr-health.jsonl
```

avc01 实测 BMC 与 OS 的 raw word 一致：C-Die 为 0，IO-Die 为 `DEADBEEF` sentinel。这证明两条路径使用同一个 PUNIT layout，且问题不在 Redfish 或 in-band 传输。

## 11. 状态解释边界

以下三层含义必须分开：

1. **Schema exact**：GUID+size 与 XML 完全匹配；
2. **Data available**：raw 是真实 packed word，而不是 `DEADBEEF` sentinel；
3. **Health semantic**：两位码的 0/1/2/3 已由平台规格定义。

当前已完成 schema 解析和逐 word availability 判定：每个 C-Die instance 的 96 个 packed slots 全为 0，IO-Die 数据不可用。独立 FIVR 诊断区按项目运营约定把“C-Die 数据可用且全部 code=0”显示为 `Healthy`，任一 code 非零时显示 `Unhealthy` 并定位到 instance、monitor 和 slot；它只能指出 packed bitfield 的逻辑位置，不能指出具体 rail/core。IO-Die 明确显示 `DEADBEEF`。第三层的正式平台语义仍需 GNR FIVR 状态枚举和 slot 映射文档确认。

## 12. 回滚

若新 metadata 导致回归：

1. 恢复 `/etc/otelcol-pmt-local.yaml` 中原 metadata 路径；
2. 恢复旧 Collector binary；
3. `systemctl restart otelcol-pmt`；
4. 检查 exporter 与 Prometheus；
5. 保留离线 snapshot 和 exact decode JSON，不把 fallback 接入生产。

无论何时都不要通过关闭 size 校验来“修复” lookup failure。
