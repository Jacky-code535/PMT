# Intel PMT 后端采集链路：原理、部署、复现与当前状态

> **文档定位：**这是长篇原理、复现和历史排障资料，不是当前运行状态的唯一来源。阅读顺序先看 `docs/README.md`，再看 `docs/complete-pmt-collection-workflow.md`。本文中的旧 URL、metric 数、panel 数和单链路阶段记录仅用于理解演进过程；冲突时以主流程和自动生成 catalog 为准。
>
> 本文记录当前服务器上 Intel PMT 后端链路的完整过程，目标是让读者能够理解每一层的职责，并可以在命令行中重新完成安装、构建、验证、切换和故障排查。
>
> 当前链路已经从 synthetic 测试切换到真实 BMC Redfish PMT 数据。
>
> **安全说明：**本文不保存、也不展示 BMC 密码。所有命令都使用交互式输入、临时文件或环境变量。真实密码不应写入 Git、YAML、Shell 历史或聊天记录。

## 快速入口：PMT Dashboard 在哪里

完整 dashboard 说明位于本文的 [第 15 节：当前真实 Grafana dashboard](#15-当前真实-grafana-dashboard)。

当前公司内网分享 URL：

```text
http://10.112.227.52/d/pmt-avc01-redfish
```

公司内网或 VPN 用户直接在浏览器打开即可，不需要 Demo 服务器账号、密码或 SSH。当前 dashboard 和指标数量见主流程第 1、8、9 节；不要使用本文历史段落中的旧数量判断当前状态。

相关内容：

- [13 个面板分别表示什么](#15-当前真实-grafana-dashboard)
- [metric 分类和逐条说明（历史章节；当前数量以自动生成 catalog 为准）](#130-当前全部-pmt-metrics-在哪里)
- [持续采集、Prometheus scrape 和 Grafana 刷新的区别](#85-这是不是持续监测)
- [Grafana 无数据的排查方法](#175-grafana-页面打开但没有-panel)

## 0. 零基础先读：这套系统到底在做什么

如果完全没有接触过 telemetry、OpenTelemetry、Prometheus 或 Grafana，可以先把整套系统类比成“定期体检并保存体检结果”：

| 实际组件 | 初学者类比 | 它做什么 | 它不做什么 |
|---|---|---|---|
| GNR CPU/平台 PMT | 人体里的传感器和体征 | 产生温度、频率、使用量、节流、错误等原始状态 | 不负责画图，也不长期保存历史 |
| BMC | 独立的体检设备/管理控制器 | 不依赖主机操作系统，通过 Redfish 帮我们触发和读取硬件 telemetry | 不把二进制字段解释成所有人都能理解的图表 |
| Intel-PMT GitHub 仓库 | “说明书 + 解码字典 + 采集程序源码” | 提供 XML schema 和 `intelpmtreceiver` 源码 | GitHub 网站本身不参与运行时采集 |
| OCB | 组装/编译 Collector 的工具 | 把需要的 receiver、processor、exporter 编译成 `otelcol-pmt` | 构建完成后不参与采集，不需要常驻运行 |
| `intelpmtreceiver` | 能读 PMT 的专用翻译器 | 定时访问 BMC，读取原始数据，根据 XML 解码成指标 | 不保存长期历史 |
| OTel Collector | 数据加工流水线 | 运行 receiver，批处理数据，并把数据提供给下游 | 默认不是长期数据库 |
| Prometheus exporter | Collector 的“取数窗口” | 在 `:8889/metrics` 暴露当前可抓取的指标 | 不主动把数据推给 Prometheus |
| Prometheus | 定时抄表员 + 时间序列数据库 | 每隔一段时间抓取指标，并保存“时间、标签、数值” | 不负责理解 PMT 二进制 XML，也不主要负责复杂 UI |
| Grafana | 看板和画图工具 | 向 Prometheus 查询数据并画曲线、表格、状态值 | 通常不保存 PMT 原始时间序列 |

### 0.1 先区分四个经常混淆的动作

1. **采集（collect）**：Collector 每 20 秒向 BMC 请求一份新的 PMT snapshot。
2. **解码（decode）**：`intelpmtreceiver` 使用 `GUID + Size + XML` 把二进制数据翻译成温度、计数器等指标。
3. **抓取（scrape）**：Prometheus 每 15 秒访问 Collector 的 `:8889/metrics`。
4. **展示（visualize）**：Grafana 查询 Prometheus，当前 dashboard 默认每 20 秒刷新页面数据。

这四个动作不是一回事，它们由不同程序在不同时间执行。

### 0.2 一条温度数据是怎样走完整条链路的

以“core 0 当前温度”为例：

```text
1. GNR 平台内部产生温度相关硬件字段
2. BMC 收集 PMT aggregator，并通过 Redfish 返回 Data
3. Data 还是编码后的原始二进制内容，不能直接看成 44°C
4. receiver 读取 Guid 和 Size，用它们在 pmt.xml 中找正确 XMLSet
5. XML 告诉 receiver：字段在哪些 bit、是什么数据类型、使用什么转换公式
6. receiver 得到 OpenTelemetry metric：
  c0_c1_c2_c3_temp_c0_temp_celcius = 44
7. Prometheus exporter 在 localhost:8889/metrics 暴露该值
8. Prometheus 抓取后保存：时间戳 + metric 名 + labels + 44
9. Grafana 用 PromQL 查询并显示 44°C 和历史曲线
```

最终看到的一个时间序列样本可以抽象为：

```text
metric name: c0_c1_c2_c3_temp_c0_temp_celcius
labels:      RedfishEndpoint="avc01", DeviceId="0", AccessId="25", ...
timestamp:   Prometheus 抓取该值的时间
value:       46.5
```

不同 labels 即使 metric name 相同，也属于不同的 time series。例如 `DeviceId="0"` 和 `DeviceId="1"` 是两条独立曲线。

### 0.3 OTel、OTLP、OCB 不要混淆

| 缩写 | 全称 | 在本项目中的含义 |
|---|---|---|
| OTel | OpenTelemetry | 一套观测数据模型、协议和 Collector 生态 |
| OTLP | OpenTelemetry Protocol | 发送 metrics/logs/traces 的协议；本机 synthetic 测试使用 OTLP/HTTP `:4318` |
| OCB | OpenTelemetry Collector Builder | 生成自定义 Collector 二进制的构建工具 |

有时口头会误写成 “OTC”。本项目实际运行的是 **OTel Collector**，构建工具是 **OCB**。不存在一个必须单独安装、名为 OTC 的 PMT 服务。

---

## 1. 当前最终目标

整个系统要完成以下数据流：

```text
GNR 平台硬件 PMT Aggregator
        |
        | 通过 BMC Redfish
        v
BMC LogService PMT
  1. POST CollectDiagnosticData
  2. GET PMTTelemetrySnapshot.json
        |
        v
Intel PMT OpenTelemetry Collector
  intelpmtreceiver / redfish mode
        |
        | Prometheus exporter :8889
        v
Prometheus :9090
        |
        | Grafana Prometheus datasource
        v
Grafana :3000
```

当前服务器中的实际服务关系是：

```text
avc01-bmc.sh.intel.com
        |
        | HTTPS + Basic Authentication
        v
otelcol-pmt
  - Redfish PMT receiver
  - OTLP/HTTP receiver :127.0.0.1:4318
  - Prometheus exporter :0.0.0.0:8889
  - debug exporter
        |
        v
Prometheus
  - scrape localhost:8889
        |
        v
Grafana
  - datasource -> http://localhost:9090
```

---

## 2. 当前服务器的最终状态

最后一次确认的组件状态如下：

| 组件 | 当前状态 | 端口/路径 | 作用 |
|---|---|---|---|
| `otelcol-pmt` | active | `127.0.0.1:4318`、`0.0.0.0:8889` | 采集、解析、转换并暴露 PMT 指标 |
| Prometheus | active | `0.0.0.0:9090` | 抓取并保存时间序列 |
| Grafana | active | `0.0.0.0:3000` | 查询 Prometheus 并可视化 |
| BMC | 可访问 | `avc01-bmc.sh.intel.com` | 提供真实 PMT Redfish 数据 |
| 本地 PMT sysfs | absent | `/sys/class/intel_pmt/` | 当前服务器不是实际 PMT host，因此不使用 local mode |

当前软件版本：

```text
otelcol-pmt 0.134.0-pmt
Prometheus 2.53.5+ds1
Grafana 13.1.0
Go 1.26.0
```

当前 BMC 验证结果：

```text
POST CollectDiagnosticData: HTTP 201
GET PMT Entries:             HTTP 200
GET PMTTelemetrySnapshot:    HTTP 200
TelemetryData aggregators:   36
```

当前真实 PMT 数据结果：

```text
Prometheus 中真实 metric 名称约 4914 个
Collector 每轮处理约 27126 个真实 PMT data points
Prometheus up{job="otel-pmt"} = 1
```

---

## 3. 先理解 Intel PMT 的几个概念

### 3.1 PMT 是什么

Intel Platform Monitoring Technology（Intel PMT）是一套平台遥测机制。它把底层硬件计数器、温度、频率、功耗、节流状态等信息通过统一的方式暴露出来。

PMT 不只是“读取一个温度文件”，而是由多层组成：

1. **Discovery**：发现平台上有哪些 PMT provider/aggregator。
2. **Aggregator**：硬件或固件侧负责收集原始数据的聚合器。
3. **Watcher**：控制采样、stream 或触发动作的控制机制。
4. **Schema/XML**：描述每个原始字段的偏移、位宽、类型和转换公式。
5. **Access**：规定如何访问数据，例如 Linux sysfs 或 BMC Redfish。

### 3.2 Aggregator 是什么

一个 aggregator 可以理解为一块有固定格式的二进制 telemetry memory region。它通常具有：

- `GUID`：标识它属于哪一种 PMT telemetry 空间；
- `Size`：这块数据区域的大小；
- `Data`：真正的二进制数据，Redfish 返回时通常是 Base64 或 JSON 中的编码字符串；
- `CollectionTimestamp`：这次采集发生的时间；
- `Attributes`：设备、访问方式、CPU、source 等附加信息。

当前 BMC 返回的 aggregator 示例包括：

```text
GUID        Size    CollectionTimestamp
0x22491753  6272    1783869473
0x3d4bb40a    48    1783869473
0x6e94ffa0   176    1783869473
0x22806802  6784    1783869474
```

这里的 `GUID + Size` 组合非常重要，因为 Collector 会使用这两个值去 `xml/pmt.xml` 中查找正确的 XML 定义。

### 3.3 XML 的作用

PMT XML 不是普通配置文件，而是 telemetry 的解码 schema。它描述：

- 数据类型，例如 unsigned integer、signed integer、float、枚举；
- 原始 sample 位于哪一个 container；
- 起始 bit，也就是 `LSB`；
- 结束 bit，也就是 `MSB`；
- sample 的长度；
- 高层 metric 如何由低层 sample 计算出来；
- 单位，例如 Celsius、Watt、Hz、count 等；
- metric 名称和描述。

因此，原始 `Data` 本身不能直接变成“CPU 温度”。Collector 必须执行：

```text
GUID + Size
   -> XMLSet
   -> 读取二进制字段
   -> 按 LSB/MSB 截取 bit range
   -> 按 datatype 解码
   -> 按 transformation 公式计算
   -> 生成 OpenTelemetry metric
```

---

## 4. 当前仓库中各目录的作用

仓库路径：

```text
/root/projects/Intel-PMT
```

重要目录：

| 路径 | 作用 |
|---|---|
| `xml/` | PMT XML schema、GUID registry 和 XML 组合文件 |
| `tools/collectd-agent/` | Python 参考采集程序 |
| `tools/otel/` | Intel PMT OpenTelemetry Collector receiver 和 OCB 构建配置 |
| `tools/otel/intelpmtreceiver/` | 自定义 PMT receiver 的 Go 源码 |
| `tools/otel/configs/` | Collector 示例和运行配置 |
| `tools/docker/` | Python agent + OTel Collector 的容器方案 |
| `docs/` | 项目文档和本说明文档 |

参考文件：

- [Intel-PMT/Readme.md](../Readme.md)
- [Intel-PMT/docs/getting-started.md](getting-started.md)
- [Intel-PMT/tools/otel/Readme.md](../tools/otel/Readme.md)
- [Intel-PMT/tools/collectd-agent/Readme.md](../tools/collectd-agent/Readme.md)
- [Intel-PMT/tools/otel/intelpmtreceiver/receiver.go](../tools/otel/intelpmtreceiver/receiver.go)
- [Intel-PMT/tools/otel/intelpmtreceiver/redfish_aggregator.go](../tools/otel/intelpmtreceiver/redfish_aggregator.go)

### 4.1 `intel/Intel-PMT` GitHub 仓库到底起什么作用

这个仓库有两个完全不同但同样重要的角色。

#### 角色 A：运行程序的源代码

`tools/otel/intelpmtreceiver/` 中是 Intel PMT receiver 的 Go 源码。标准 OpenTelemetry Collector 不认识 Intel PMT 的 BMC JSON、GUID、XML 和二进制布局，所以必须把这个 receiver 编译进自定义 Collector。

关键代码职责：

- `config.go`：定义 `mode`、`interval`、`metadata`、`endpoints` 等配置字段；
- `receiver.go`：负责周期执行、发 POST、发 GET、发现 aggregator、产生 OTel metrics；
- `redfish_aggregator.go`：定义 BMC JSON 中 `Guid`、`Size`、`Data` 等字段；
- XML parser 相关代码：加载 XMLSet、数据类型和转换公式；
- `factory.go`：让 OTel Collector 能创建名为 `intelpmtreceiver` 的组件。

#### 角色 B：PMT 数据的“解码字典”

`xml/` 中的文件不是程序源码，而是平台数据定义。即使已经有 receiver，如果没有正确 XML，receiver 也只拿到一段无法解释的原始 `Data`。

```text
receiver 源码 = 会查字典和执行公式的翻译程序
PMT XML       = 每种 GUID/Size 对应的字典和公式
BMC Data      = 等待翻译的原始内容
```

#### GitHub 是否参与持续运行

不参与。运行时不会每 20 秒访问 GitHub。仓库被 clone 到本机后：

1. 源码由 OCB/Go 编译进 `/usr/local/bin/otelcol-pmt`；
2. XML 保留在 `/root/projects/Intel-PMT/xml/`，Collector 运行时从本地读取；
3. 真正每 20 秒访问的是 BMC，而不是 GitHub。

只有在升级 receiver 源码或更新 PMT XML 时，才需要再次从 GitHub 获取更新并重新构建/重启。

---

## 5. 为什么当前使用 Redfish mode 而不是 local mode

### 5.1 local mode 的工作方式

Linux host mode 依赖 Intel PMT kernel driver 暴露的目录：

```text
/sys/class/intel_pmt/
```

正常情况下目录中会有类似：

```text
/sys/class/intel_pmt/telem0/guid
/sys/class/intel_pmt/telem0/size
/sys/class/intel_pmt/telem0/telem
```

Collector 的 local 逻辑会：

1. 扫描 `/sys/class/intel_pmt/`；
2. 找到所有 `telem*` 目录；
3. 读取每个目录的 `guid`；
4. 读取 `size`；
5. 读取二进制 `telem`；
6. 使用 XML 解码；
7. 输出指标。

当前服务器检查结果是：

```text
/sys/class/intel_pmt absent
```

所以 local mode 会出现：

```text
Failed to discover local aggregators
open /sys/class/intel_pmt/: no such file or directory
```

这不是 Prometheus 的错误，而是当前服务器没有可用的本地 PMT sysfs 数据源。

### 5.2 Redfish mode 的工作方式

Redfish mode 不依赖本机 `/sys/class/intel_pmt/`，而是通过 BMC 获取数据：

```text
POST /redfish/v1/Systems/system/LogServices/PMT/Actions/LogService.CollectDiagnosticData
GET  /redfish/v1/Systems/system/LogServices/PMT/Entries
GET  /redfish/v1/Systems/system/LogServices/PMT/Entries/0/PMTTelemetrySnapshot.json
```

当前 BMC 使用的两个关键 endpoint 是：

```text
Trigger:
https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Actions/LogService.CollectDiagnosticData

Snapshot:
https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Entries/0/PMTTelemetrySnapshot.json
```

---

## 6. 重新准备服务器环境

以下命令适用于 Ubuntu/Debian 类 Linux 环境。命令会根据你的发行版和网络策略略有不同。

### 6.1 安装基础工具

```bash
sudo apt-get update
sudo apt-get install -y curl wget git jq ca-certificates build-essential gcc make
```

当前项目构建需要 Go。检查 Go：

```bash
go version
```

本次环境使用：

```text
go1.26.0 linux/amd64
```

项目的 `tools/otel/Readme.md` 说明测试版本是 Go 1.24.4；当前 Go 1.26.0 也已经成功构建并运行了本项目 Collector。

### 6.2 如果服务器需要代理

在 Intel 网络环境中，外网访问可能需要代理。代理配置应根据组织实际策略设置，示例结构如下：

```bash
export http_proxy='http://proxy.example:port'
export https_proxy='http://proxy.example:port'
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export no_proxy='localhost,127.0.0.1,.intel.com,intel.com'
export NO_PROXY="$no_proxy"
```

BMC 请求使用了：

```bash
curl --noproxy '*'
```

因为 BMC 是内部地址，应绕过通用外网代理。如果不确定是否需要 `--noproxy '*'`，先测试：

```bash
getent hosts avc01-bmc.sh.intel.com
curl --noproxy '*' -k -I \
  'https://avc01-bmc.sh.intel.com/redfish/v1/'
```

预期至少能看到一个 HTTP 响应。没有认证时通常是：

```text
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic
```

这说明网络可达，接下来只需要正确凭据。

### 6.3 获取源码

如果还没有仓库：

```bash
git clone https://github.com/intel/Intel-PMT.git /root/projects/Intel-PMT
cd /root/projects/Intel-PMT
```

检查当前仓库：

```bash
git status
git log -1 --oneline
```

---

## 7. 构建 PMT-enabled OpenTelemetry Collector

### 7.1 为什么要自定义 Collector

标准 OTel Collector 不一定包含 Intel PMT receiver。因此需要用 OpenTelemetry Collector Builder（OCB）把：

- Intel PMT receiver；
- OTLP receiver；
- Prometheus exporter；
- debug exporter；
- batch processor；

组合成一个新的二进制：

```text
otelcol-pmt
```

### 7.1.1 Receiver 到底是什么

OpenTelemetry Collector 是一个可插拔框架。它把组件分成三大类：

```text
Receiver  ->  Processor  ->  Exporter
输入          中间处理        输出
```

- **Receiver**：知道如何从某个来源获取数据。本项目的 `intelpmtreceiver` 知道如何和 PMT BMC 通信及解码 PMT；`otlp` receiver 知道如何接收标准 OTLP 请求。
- **Processor**：在数据流中做批处理、过滤、增加属性等。本项目使用 `batch`，把数据成批交给 exporter，减少逐点处理开销。
- **Exporter**：把处理后的 OTel 数据送到某个目的地。本项目的 Prometheus exporter 提供 `:8889/metrics`；debug exporter 把每轮指标数量写入日志。

这里容易产生一个误解：PMT 的 `intelpmtreceiver` 名字叫 receiver，但在 Redfish mode 下，它实际上会**主动**向 BMC 发请求。Receiver 表示它是 Collector pipeline 的输入组件，并不表示网络上一定是被动接收。

### 7.1.2 OCB 到底是什么，为什么需要它

OCB 的全称是 **OpenTelemetry Collector Builder**。它不是 Collector 本身，也不负责采集。

可以把它类比为“定制装配工具”：

```text
build-config-pmt-minimal.yaml  告诉 OCB 要哪些零件
              |
              v
OCB 生成 Go 工程并解析依赖
              |
              v
Go compiler 编译并链接所有组件
              |
              v
build-minimal/otelcol-pmt      最终可运行程序
```

为什么不能直接使用普通 `otelcol`：

- 普通发行版不一定包含 Intel 定制的 `intelpmtreceiver`；
- 即使安装了标准 OTel Collector，它也无法识别配置中的 `intelpmtreceiver:`；
- OCB 让我们只选择需要的组件，得到更小、更可控的 Collector。

OCB 只在“构建阶段”使用。构建完成后，systemd 运行的是：

```text
/usr/local/bin/otelcol-pmt
```

不是 `ocb`。所以即使运行时删除 OCB，已经编译好的 Collector 仍能工作；只是以后无法重新构建。

### 7.2 为什么使用 minimal build config

原始完整 `build-config.yaml` 包含很多 receiver、exporter 和 processor。完整构建会带来：

- 更长的下载和编译时间；
- 更多不相关依赖；
- 某些与 PMT 无关的依赖可能造成运行时问题。

当前使用的最小构建配置是：

```text
/root/projects/Intel-PMT/tools/otel/build-config-pmt-minimal.yaml
```

它只保留 PMT 后端需要的组件：

```text
receiver:
  - intelpmtreceiver
  - otlpreceiver

processor:
  - batchprocessor

exporter:
  - debugexporter
  - prometheusexporter
```

### 7.3 安装并使用 OCB

本项目匹配的 OCB 版本是 `0.134.0`。当前服务器已经将它安装为：

```text
/usr/local/bin/ocb
```

原始下载文件保留在：

```text
/root/projects/otel-build-tools/ocb_0.134.0_linux_amd64
```

检查：

```bash
command -v ocb
ocb --version
```

如果 `command -v ocb` 没有输出，直接运行 `ocb ...` 会得到：

```text
bash: ocb: command not found
exit code 127
```

`127` 在 shell 中通常表示“命令不存在或不在 PATH”，并不表示 PMT 源码编译失败。

如果已存在本次下载的二进制，可以安装到 PATH：

```bash
sudo install -m 755 \
  /root/projects/otel-build-tools/ocb_0.134.0_linux_amd64 \
  /usr/local/bin/ocb
command -v ocb
ocb version
```

如果是全新机器，可以从 OpenTelemetry Collector Releases 下载与 build config 匹配的 OCB 0.134.0：

```bash
mkdir -p /root/projects/otel-build-tools
curl -fL \
  'https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/cmd%2Fbuilder%2Fv0.134.0/ocb_0.134.0_linux_amd64' \
  -o /root/projects/otel-build-tools/ocb_0.134.0_linux_amd64
sudo install -m 755 \
  /root/projects/otel-build-tools/ocb_0.134.0_linux_amd64 \
  /usr/local/bin/ocb
ocb version
```

如果 GitHub 下载需要代理，先按第 6.2 节配置代理。下载后必须添加执行权限，或像上面一样用 `install -m 755` 安装到 `/usr/local/bin/ocb`。

构建：

```bash
cd /root/projects/Intel-PMT/tools/otel
ocb --config build-config-pmt-minimal.yaml
```

也可以完全不依赖 PATH，使用绝对路径：

```bash
cd /root/projects/Intel-PMT/tools/otel
/root/projects/otel-build-tools/ocb_0.134.0_linux_amd64 \
  --config build-config-pmt-minimal.yaml
```

构建时 OCB 会读取 YAML、生成 Go 源文件、下载 Go modules 并调用 Go 编译器。第一次构建可能比较慢，因为依赖尚未进入 Go module cache。

构建结果：

```text
/root/projects/Intel-PMT/tools/otel/build-minimal/otelcol-pmt
```

检查：

```bash
/root/projects/Intel-PMT/tools/otel/build-minimal/otelcol-pmt --version
```

预期：

```text
otelcol-pmt version 0.134.0-pmt
```

安装到系统路径：

```bash
sudo install -m 755 \
  /root/projects/Intel-PMT/tools/otel/build-minimal/otelcol-pmt \
  /usr/local/bin/otelcol-pmt
```

验证二进制：

```bash
/usr/local/bin/otelcol-pmt --version
```

### 7.4 最小构建配置的核心内容

当前文件的关键内容是：

```yaml
dist:
  module: github.com/intel/Intel-PMT/tools/otel
  name: otelcol-pmt
  version: 0.134.0-pmt
  output_path: ./build-minimal

exporters:
  - gomod: go.opentelemetry.io/collector/exporter/debugexporter v0.134.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/exporter/prometheusexporter v0.134.0

processors:
  - gomod: go.opentelemetry.io/collector/processor/batchprocessor v0.134.0

receivers:
  - gomod: github.com/intel/Intel-PMT/tools/otel/intelpmtreceiver v0.0.0
  - gomod: go.opentelemetry.io/collector/receiver/otlpreceiver v0.134.0

replaces:
  - github.com/intel/Intel-PMT/tools/otel/intelpmtreceiver => ../intelpmtreceiver
```

`replaces` 很重要，它确保构建时使用当前仓库中的本地 PMT receiver 源码，而不是拉取一个不存在或不可访问的外部模块版本。

---

## 8. 理解 Collector 配置

当前实际运行配置：

```text
/etc/otelcol-pmt-local.yaml
```

文件名仍叫 `local`，但内容已经是 `redfish` mode。这是历史命名，实际 mode 以 YAML 中的 `mode: redfish` 为准。

### 8.1 Receiver 配置

```yaml
receivers:
  intelpmtreceiver:
    interval: 20s
    metadata: "/root/projects/Intel-PMT/xml/pmt.xml"
    mode: redfish
    endpoints:
      avc01:
        endpoint: "https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Entries/0/PMTTelemetrySnapshot.json"
        trigger_action: "https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Actions/LogService.CollectDiagnosticData"
        trigger_param: '{"DiagnosticDataType":"OEM","OEMDiagnosticDataType":"TelemetrySnapshot"}'
        headers:
          Authorization: "${env:BMC_AUTHORIZATION}"
        tls:
          insecure_skip_verify: true
```

各字段含义：

| 字段 | 含义 |
|---|---|
| `interval: 20s` | 每 20 秒触发一次 PMT 采集周期 |
| `metadata` | PMT XML 根文件，用来解码 aggregator |
| `mode: redfish` | 使用 BMC Redfish，而不是 Linux sysfs |
| `endpoints.avc01` | endpoint 的逻辑名称，最终作为 `RedfishEndpoint="avc01"` 标签 |
| `endpoint` | GET telemetry snapshot 的 URL |
| `trigger_action` | POST 触发 BMC 采集的 URL |
| `trigger_param` | POST JSON body |
| `Authorization` | 从环境变量读取，不把密码写进 YAML |
| `insecure_skip_verify` | 跳过 BMC TLS 证书校验；生产环境应尽量使用可信证书 |

### 8.1.1 为什么是每 20 秒采集一次

`interval: 20s` 不是 Intel PMT 的固定要求，也不是“只能采一次”。它表示 Collector 内部有一个长期运行的周期任务：

```text
每隔约 20 秒：
  1. POST trigger_action，让 BMC 生成/更新 telemetry snapshot
  2. GET endpoint，读取这次 snapshot
  3. 解析 36 个 aggregators
  4. 对能匹配 XML 的数据执行解码和 transformation
  5. 更新 Prometheus exporter 中的 metrics
  6. 等待下一个周期
```

当前真实日志已经证明它在持续运行：

```text
08:39:49  Metrics: 27126, data points: 27126
08:40:08  Metrics: 27126, data points: 27126
```

两轮之间约 20 秒。只要 `otelcol-pmt` systemd 服务保持 active，这个循环就不会因为一次 snapshot 完成而退出。

选择 20 秒是当前 MVP 的工程折中：

- 每轮会处理约 27,126 个数据点，不是一个很小的请求；
- BMC 需要时间生成 snapshot；
- 更短间隔会增加 BMC、网络、Collector、Prometheus 的 CPU、内存和存储压力；
- 温度和健康趋势通常不要求毫秒级采样；
- receiver 源码规定最小 interval 是 5 秒，低于 5 秒配置验证会失败；
- 20 秒足以验证故障遥测后端和观察秒级到分钟级趋势。

可以改成 10 秒：

```yaml
interval: 10s
```

修改后必须验证并重启：

```bash
sudo /usr/local/bin/otelcol-pmt validate \
  --config /etc/otelcol-pmt-local.yaml
sudo systemctl restart otelcol-pmt
```

不应盲目调到 5 秒。先观察 BMC 响应时间、Collector CPU、每轮是否完成、Prometheus series 数和磁盘增长。若一轮采集本身接近或超过 interval，还可能出现重叠、超时或 BMC 压力。

### 8.2 OTLP receiver

```yaml
  otlp:
    protocols:
      http:
        endpoint: "127.0.0.1:4318"
```

它用于两种场景：

1. 保留后端 synthetic smoke test；
2. 未来让其他本机采集程序通过 OTLP/HTTP 把指标送入同一个 Collector。

它只监听 `127.0.0.1`，因此不会直接暴露到外部网络。

### 8.3 Exporter

```yaml
exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
  debug:
    verbosity: basic
```

`prometheus` exporter 在 `8889` 暴露 Prometheus pull endpoint：

```bash
curl http://localhost:8889/metrics
```

`debug` exporter 将 OTel metrics 数量写入 Collector 日志，适合确认 pipeline 是否实际处理了数据：

```text
Metrics ... resource metrics: 1, metrics: 27126, data points: 27126
```

### 8.4 Pipeline

```yaml
service:
  pipelines:
    metrics:
      receivers: [intelpmtreceiver, otlp]
      processors: [batch]
      exporters: [debug, prometheus]
```

数据路径是：

```text
intelpmtreceiver 或 otlp
        |
        v
batch processor
        |
        +--> debug exporter
        |
        +--> Prometheus exporter :8889
```

### 8.5 这是不是“持续监测”

**是，当前已经是持续监测。**但计算机监控里的“持续”通常是“服务 24×7 运行并周期采样”，不是无限频率地读取模拟信号。

当前有三个独立时钟：

| 层 | 当前周期 | 发生什么 |
|---|---:|---|
| PMT receiver | 20 秒 | 向 BMC 触发并解码一份新 snapshot |
| Prometheus | 15 秒 | 从 `localhost:8889/metrics` 抓取当前指标 |
| Grafana dashboard | 20 秒 | 重新向 Prometheus 发查询并刷新画面 |

一个简化时间线：

```text
时间       0s      15s      20s      30s      40s      45s      60s
Receiver   采集              采集              采集              采集
Prometheus 抓取    抓取                抓取              抓取     抓取
Grafana    刷新              刷新              刷新              刷新
```

因此 Grafana 中一条曲线可能在相邻 Prometheus 抓取点上暂时保持相同值，然后在下一轮 PMT 采集后变化。这是正常行为。

#### 为什么使用 snapshot 仍然能持续监测

“Snapshot”只描述**一次读取的数据形态**：某一时刻的一组平台状态。Collector 会反复请求 snapshot：

```text
snapshot 1 + snapshot 2 + snapshot 3 + ...
                    |
                    v
Prometheus 按时间保存
                    |
                    v
形成历史时间序列
```

相机每 20 秒拍一张照片也能形成长期观察记录。它不是视频级连续，但属于周期性持续监测。

#### 当前方案会漏掉什么

如果某个异常只持续 2 秒，而采集间隔是 20 秒，并且硬件没有累计 counter、sticky bit 或历史记录，那么确实可能错过。是否会错过取决于数据类型：

- **当前值 gauge**，例如当前温度：短暂尖峰可能被采样间隔漏掉；
- **累计 counter**，例如 throttle 次数：即使事件发生在两轮之间，下一轮通常仍能看到 counter 增加；
- **histogram counter**：记录某区间累计停留时间，通常不会只依赖采样瞬间；
- **data-loss timestamp/count**：用于保留异常发生的累计信息或最近时间。

如果项目要求捕获非常短的瞬态故障，需要评估更短 interval、PMT streaming/watcher、BMC 能力或其他事件通道，而不是只把 Grafana 刷新调快。Grafana 刷新更快不会让底层产生更多数据。

#### 如何证明服务一直在采集

观察多轮 `Metrics` 日志：

```bash
journalctl -u otelcol-pmt -f \
  | grep --line-buffered 'Metrics'
```

或者在 Grafana/Prometheus 查询某条真实 metric 最近 10 分钟的数据：

```promql
c0_c1_c2_c3_temp_c0_temp_celcius{RedfishEndpoint="avc01"}
```

还可以检查：

```promql
up{job="otel-pmt"}
```

`up = 1` 只证明 Prometheus 能抓到 Collector，不单独证明 BMC 数据每轮都更新。因此还应同时看真实 PMT metric 的时间和值，以及 Collector 日志。

### 8.6 “持续采集”“自动恢复”“保存历史”是三件事

#### 持续采集

`otelcol-pmt` 进程保持运行，并每 20 秒执行采集循环。由 `systemctl is-active otelcol-pmt` 判断进程当前是否 active。

#### 自动恢复和开机启动

当前三个服务都已经设置为 enabled：

```bash
systemctl is-enabled otelcol-pmt prometheus grafana-server
```

Collector service 还有：

```ini
Restart=on-failure
RestartSec=10
```

所以 Collector 异常退出时，systemd 会在约 10 秒后尝试重启；服务器重启后，三个 enabled 服务也会自动启动。但断电期间不会产生样本，BMC/网络长时间不可达时仍会形成数据缺口。

#### 保存历史

Collector exporter 主要提供当前可抓取数据，真正长期保存历史的是 Prometheus TSDB。当前数据路径是：

```text
/var/lib/prometheus/metrics2/
```

当前已使用约 435 MB，但这个数字会随采集时间和 series 数持续变化。查看：

```bash
du -sh /var/lib/prometheus/metrics2
```

当前运行时没有显式设置基于时间或容量的 retention 限制：

```text
storage.tsdb.retention.time = 0s
storage.tsdb.retention.size = 0B
```

这表示本项目尚未主动定义清晰的保留策略，不应理解为“保证永久保存”。生产环境必须根据磁盘容量、series 数量和审计需求显式设置 retention，并配置磁盘告警。Grafana 关闭不会丢失 Prometheus 历史；Prometheus 数据目录损坏或磁盘满则会影响历史保存。

检查实际运行参数：

```bash
curl -fsS http://localhost:9090/api/v1/status/flags \
  | jq '.data | {
      path: .["storage.tsdb.path"],
      time: .["storage.tsdb.retention.time"],
      size: .["storage.tsdb.retention.size"]
    }'
```

---

## 9. 安全保存 BMC 凭据

当前 systemd service 使用：

```text
/etc/otelcol-pmt-redfish.env
```

该文件权限是：

```text
600 root root
```

内容格式是：

```text
BMC_AUTHORIZATION=Basic <base64(user:password)>
```

不要把真实内容写进文档。推荐用交互式方式生成：

```bash
read -r -s -p 'BMC password: ' P
printf '\n'
printf 'BMC_AUTHORIZATION=%s\n' \
  "Basic $(printf '%s' "debuguser:${P}" | base64 -w0)" \
  | sudo tee /etc/otelcol-pmt-redfish.env >/dev/null
unset P
sudo chmod 600 /etc/otelcol-pmt-redfish.env
```

检查权限，但不要打印内容：

```bash
sudo stat -c '%a %U %G %n' /etc/otelcol-pmt-redfish.env
```

预期：

```text
600 root root /etc/otelcol-pmt-redfish.env
```

如果只想临时验证，可以把密码输入到临时文件：

```bash
read -r -s -p 'BMC password: ' P
printf '\n'
printf '%s' "$P" > /tmp/pmt-bmc-password
unset P
chmod 600 /tmp/pmt-bmc-password
```

使用后必须删除：

```bash
rm -f /tmp/pmt-bmc-password
```

**不要使用下面这种方式：**

```bash
curl -u debuguser:password ...
```

因为密码可能出现在 shell history、进程列表、终端日志或聊天记录中。

---

## 10. BMC Redfish 验证流程

仓库中的验证脚本：

```text
/root/projects/failure telemetry infra/validate_bmc_pmt_redfish.sh
```

它执行三个步骤。

### 10.1 第一步：POST 触发 PMT snapshot

等价命令：

```bash
curl --noproxy '*' \
  --user 'debuguser' \
  --insecure \
  --request POST \
  --header 'Content-Type: application/json' \
  --data '{"DiagnosticDataType":"OEM","OEMDiagnosticDataType":"TelemetrySnapshot"}' \
  'https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Actions/LogService.CollectDiagnosticData'
```

推荐不要在命令行写密码，而是使用脚本交互输入。

成功时本次返回：

```text
HTTP 201
Location: /redfish/v1/Systems/system/LogServices/PMT/Entries/0
```

`201` 表示 BMC 已经创建/生成了新的诊断数据记录。

### 10.2 第二步：读取 Entries

```bash
curl --noproxy '*' --insecure \
  'https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Entries'
```

当前返回：

```text
HTTP 200
```

### 10.3 第三步：读取 snapshot JSON

```bash
curl --noproxy '*' --insecure \
  'https://avc01-bmc.sh.intel.com/redfish/v1/Systems/system/LogServices/PMT/Entries/0/PMTTelemetrySnapshot.json'
```

当前返回：

```text
HTTP 200
```

Collector 期待的顶层结构是：

```json
{
  "TelemetryData": [
    {
      "Guid": "0x22491753",
      "Size": 6272,
      "CollectionTimestamp": "1783869473",
      "Data": "...",
      "attributes": {
        "...": "..."
      }
    }
  ]
}
```

代码定义位于：

```text
Intel-PMT/tools/otel/intelpmtreceiver/redfish_aggregator.go
```

对应 Go 结构：

```go
type RedfishMetricAggregator struct {
    GUID                string                 `json:"Guid"`
    CollectionTimestamp string                 `json:"CollectionTimestamp"`
    Size                uint64                 `json:"Size"`
    Attributes          map[string]interface{} `json:"attributes"`
    Data                string                 `json:"Data"`
}

type RedfishTelemetryData struct {
    TelemetryData []RedfishMetricAggregator `json:"TelemetryData"`
}
```

### 10.4 用验证脚本复现

```bash
/root/projects/failure telemetry infra/validate_bmc_pmt_redfish.sh
```

脚本会交互式要求密码，并将不含密码的验证结果写入：

```text
/tmp/pmt-redfish-validation/
```

文件权限是 `0700` 目录和 `0600` 文件。

查看安全的响应摘要：

```bash
sudo jq '.TelemetryData | length' /tmp/pmt-redfish-validation/snapshot.json
sudo jq -r '.TelemetryData[] | [.Guid, .Size, .CollectionTimestamp] | @tsv' \
  /tmp/pmt-redfish-validation/snapshot.json | head
```

不要把 `snapshot.json` 直接上传到公共位置，因为其中的 telemetry data 可能包含平台内部信息。

---

## 11. 配置 systemd 服务

当前 service 文件：

```text
/etc/systemd/system/otelcol-pmt.service
```

内容结构：

```ini
[Unit]
Description=OpenTelemetry Collector with Intel PMT receiver
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/environment
EnvironmentFile=-/etc/otelcol-pmt-redfish.env
ExecStart=/usr/local/bin/otelcol-pmt --config /etc/otelcol-pmt-local.yaml
Restart=on-failure
RestartSec=10
WorkingDirectory=/root/projects/Intel-PMT/tools/otel

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now otelcol-pmt
```

检查状态：

```bash
systemctl is-active otelcol-pmt
systemctl status otelcol-pmt --no-pager
```

查看日志：

```bash
journalctl -u otelcol-pmt --no-pager -n 100
```

实时查看日志：

```bash
journalctl -u otelcol-pmt -f
```

修改配置后的标准流程：

```bash
sudo /usr/local/bin/otelcol-pmt validate \
  --config /etc/otelcol-pmt-local.yaml
sudo systemctl restart otelcol-pmt
systemctl is-active otelcol-pmt
```

---

## 12. Prometheus 配置与验证

当前 Prometheus 配置：

```text
/etc/prometheus/prometheus.yml
```

关键 scrape job：

```yaml
  - job_name: otel-pmt
    static_configs:
      - targets: ['localhost:8889']
```

这意味着 Prometheus 每隔全局 scrape interval 访问：

```text
http://localhost:8889/metrics
```

### 12.1 检查 Collector exporter

```bash
curl -fsS http://localhost:8889/metrics | head -n 30
```

搜索真实 PMT 指标：

```bash
curl -fsS http://localhost:8889/metrics \
  | grep 'RedfishEndpoint="avc01"' \
  | head -n 20
```

### 12.2 检查 Prometheus 健康状态

```bash
curl -fsS http://localhost:9090/-/healthy
```

### 12.3 检查 scrape target

```bash
curl -fsS http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | {job, health, scrapeUrl, lastError}'
```

预期：

```json
{
  "job": "otel-pmt",
  "health": "up",
  "scrapeUrl": "http://localhost:8889/metrics",
  "lastError": ""
}
```

### 12.4 查询真实 PMT 指标

当前已经验证过的温度 metric：

```promql
c0_c1_c2_c3_temp_c0_temp_celcius{RedfishEndpoint="avc01"}
```

命令行查询：

```bash
curl -fsS --get \
  --data-urlencode 'query=c0_c1_c2_c3_temp_c0_temp_celcius{RedfishEndpoint="avc01"}' \
  http://localhost:9090/api/v1/query | jq
```

示例返回的值包括：

```text
43.0
43.5
44.0
45.5
46.0
47.5
```

注意：这些 series 的具体含义还要结合标签，例如：

```text
DeviceId
AccessId
SourceId
SourceType
AccessType
DeviceType
RedfishEndpoint
```

查看所有 metric 名称：

```bash
curl -fsS http://localhost:9090/api/v1/label/__name__/values \
  | jq -r '.data[]' | sort
```

查看带有 avc01 标签的 metric：

```bash
curl -fsS http://localhost:8889/metrics \
  | grep 'RedfishEndpoint="avc01"' \
  | sed 's/{.*//' \
  | sort -u
```

---

## 13. 当前已经发现的数据类型

当前 BMC PMT 数据中已经看到以下类别的指标。

### 13.0 当前全部 PMT metrics 在哪里

当前 `avc01` 实际暴露：

```text
4387 个 PMT metric 名称
27126 条当前 PMT time series
```

这里严格过滤了：

```text
RedfishEndpoint="avc01"
```

因此没有把 Prometheus 自身、node-exporter 或 apt 等非 PMT metrics 混进来。

所有 4387 个 metric 的逐条清单已经自动导出：

- [完整 CSV：每个 metric 一行](pmt-metrics-catalog.csv)
- [中文分类摘要](pmt-metrics-summary.md)
- [导出工具](../tools/otel/export_pmt_metric_catalog.py)

CSV 每一行都包含：

| 字段 | 含义 |
|---|---|
| `metric_name` | Prometheus 中可直接查询的准确名称 |
| `category` | 按名称和 HELP 自动归类 |
| `type` | `gauge` 或 `counter` |
| `unit` | Prometheus metadata 中的单位；为空时看 HELP/XML |
| `series_count` | 当前该名称产生了多少条不同 labels 的 series |
| `label_names` | 当前观察到的全部标签名 |
| `help` | receiver/XML 暴露的官方含义说明 |

当前全部 4387 个 metric 都有 HELP，缺失说明数量为 0。按自动分类统计：

| 类别 | metric 名称数 |
|---|---:|
| 内存 | 1051 |
| 温度 | 832 |
| 频率 | 769 |
| 电压 | 768 |
| Usage/Residency | 576 |
| 状态与配置 | 142 |
| Throttle | 128 |
| Cache/CHA | 64 |
| 其他 | 29 |
| Latency | 22 |
| Interconnect/I/O | 4 |
| Data loss | 2 |

按 Prometheus 类型：

```text
counter: 2368
gauge:   2019
```

重新生成清单：

```bash
cd /root/projects/Intel-PMT
/usr/bin/python3 tools/otel/export_pmt_metric_catalog.py
```

每次更新 PMT XML、更换 BMC 或升级 receiver 后，都应重新生成，因为 metric 集合可能变化。

### 13.0.1 先理解“抓到的数据”有三层

#### 第一层：BMC 返回的原始 aggregator

每项主要包含：

| 字段 | 类型 | 含义 |
|---|---|---|
| `Guid` | 字符串/十六进制标识 | 这块 telemetry 数据遵循哪套定义 |
| `Size` | 整数 | 原始 telemetry 区域大小，用于和 GUID 一起匹配 XML |
| `CollectionTimestamp` | 字符串形式整数 | BMC/PMT 采集时间 |
| `Data` | 编码字符串 | 原始二进制 telemetry payload，不适合人工直接阅读 |
| `attributes` | key-value map | DeviceId、AccessId、SourceType 等来源信息 |

当前一次 snapshot 有 36 个 aggregators。36 不等于 36 个最终指标；一个 aggregator 可以根据 XML 解码出大量 samples，所以一轮最后得到约 27,126 个 data points。

#### 第二层：OpenTelemetry metric

Receiver 解码后创建 OTel metric。一个 metric 通常包括：

- name：例如 `c0_c1_c2_c3_temp_c0_temp_celcius`；
- description：来自 XML，说明它是什么；
- unit：例如温度、秒、计数或无量纲；
- data point value：例如 `44`；
- timestamp：这次数据对应的时间；
- attributes：DeviceId、AccessId、RedfishEndpoint 等。

常见 metric 语义：

| 语义 | 如何理解 | 例子 |
|---|---|---|
| Gauge/当前值 | 某一时刻的状态，可升可降 | 当前温度 |
| Counter/累计值 | 从某个起点开始累计，通常只增，重启时可能清零 | throttle 次数、累计使用量 |
| Histogram buckets/区间累计 | 在不同区间累计的次数或时间 | 频率、温度、电压直方图 |

#### 第三层：Prometheus time series

Prometheus 将 OTel metric 转换为自己的 metric name 和 labels，并在每次 scrape 时保存样本：

```text
time series identity = metric name + 完整 labels 集合
sample               = timestamp + numeric value
```

例如同一个温度 metric，因为 `AccessId` 不同，会有多条曲线。这也是为什么“约 4914 个 metric 名称”不等于只有 4914 条 series；每个名称可以因为 labels 组合产生多条 series。

### 13.0.2 如何查看官方 description，而不是只猜名字

Prometheus exposition 中的 `# HELP` 来自 PMT XML/receiver：

```bash
curl -fsS http://localhost:8889/metrics \
  | grep '^# HELP ' \
  | less
```

查看某个具体指标：

```bash
curl -fsS http://localhost:8889/metrics \
  | grep -E '^# (HELP|TYPE) c0_c1_c2_c3_temp_c0_temp_celcius '
```

不要仅凭自动生成的 metric name 判断物理意义。优先级应是：

```text
# HELP description > XML description/unit/transformation > metric name 猜测
```

### 13.1 CPU 温度

示例：

```text
c0_c1_c2_c3_temp_c0_temp_celcius
```

当前官方 HELP：

```text
Current temperature for core 0
```

Grafana 显示单位为 Celsius。当前样例约为 43°C 到 47.5°C。名称中的 `c0_c1_c2_c3` 和 `temp_c0` 是 XML schema 中定义的 sample/metric 命名结果，不能只凭名字猜测业务含义，最好回到 XML 查看 description 和 transformation。

### 13.2 Core usage

示例：

```text
c0_usage_meter_core_usage_total
```

当前官方 HELP：

```text
Accumulated relative usage level for core 0 (experimental).
This counter is not retained on processor reset.
```

所以它不是简单的“当前 CPU 使用率百分比”，而是一个实验性的累计相对使用量 counter；处理器 reset 后不会保留。若要看变化速度，应考虑 PromQL 的 `rate()` 或 `increase()`，而不是直接把累计值当百分比。

### 13.3 频率直方图

示例：

```text
c0_freq_hist_r0_second_total
c0_freq_hist_r1_second_total
c0_freq_hist_r10_second_total
```

当前 `r0` 官方 HELP：

```text
Frequency histogram range 0 (core in C6) counter for core 0
```

`r0`、`r1` 等表示频率区间或 histogram bucket。这里 `r0` 特别表示 core 处于 C6。指标后缀 `_second_total` 表明它是累计类 metric，但其他 bucket 的具体频率范围仍应逐项读取 HELP/XML。

### 13.4 温度直方图

示例：

```text
c0_temp_hist_r0_second_total
c0_temp_hist_r1_second_total
```

当前 `r0` 官方 HELP：

```text
Temperature histogram range 0 (less then 20C) counter for core 0
```

用于观察温度落入不同区间的累计时间或累计次数。这里 `r0` 表示低于 20°C；其他范围必须查看对应 metric 的 HELP/XML。

### 13.5 电压直方图

示例：

```text
c0_volt_hist_r0_second_total
c0_volt_hist_r1_second_total
```

当前 `r0` 官方 HELP：

```text
Voltage histogram range 0 (less then 602mV) counter for core 0
```

用于观察电压区间统计。这里 `r0` 表示低于 602 mV。

### 13.6 PVP throttle

示例：

```text
c0_pvp_throttle_64_c0_pvp_throttle_64
c0_pvp_throttle_1024_c0_pvp_throttle_1024
```

当前 `64` 官方 HELP：

```text
Counter indicating number of times core 0 was throttled in last 64 cycles window
```

因此它是节流事件计数器，不是温度，也不是直接的功耗数值。`64` 和 `1024` 表示观察窗口尺度。

### 13.7 Aggregator data loss

示例：

```text
agg_data_loss_count_agg_data_loss_count
agg_data_loss_timestamp_agg_data_loss_timestamp
```

当前官方 HELP 表明：

```text
agg_data_loss_count:
  aggregator 无法更新全部 samples 的 processing cycle 累计次数。
  如果实际变化率为 0，说明没有新增 data loss；如果在增长，期间其他 samples 可能不可靠。

agg_data_loss_timestamp:
  最近一次无法更新全部 samples 的时间，单位是 25MHz crystal clock TSC ticks。
```

注意：`data_loss_count` 是运行累计值，绝对值非零不一定代表“此刻正在丢数据”。更有意义的是观察它是否继续增长：

```promql
increase(agg_data_loss_count_agg_data_loss_count{RedfishEndpoint="avc01"}[5m])
```

如果结果大于 0，表示最近 5 分钟发生了新增 data-loss cycle。

### 13.8 指标标签

真实 PMT metric 通常带有以下标签：

```text
AccessId
AccessType
DeviceId
DeviceType
RedfishEndpoint
SourceId
SourceType
instance
job
```

其中：

- `RedfishEndpoint="avc01"`：来自 Collector 配置中的 endpoint label；
- `job="otel-pmt"`：来自 Prometheus scrape job；
- `instance="localhost:8889"`：Prometheus 实际抓取的 exporter 地址；
- `DeviceId`、`AccessId`：由 BMC/PMT aggregator attributes 传播而来；
- `SourceType="Aggregator"`：说明数据来源是 PMT aggregator。

---

## 14. Synthetic backend smoke test

真实 PMT 接入之前，我们先使用 synthetic metric 验证了三件套的联动。

脚本：

```text
/root/projects/failure telemetry infra/send_backend_test_metric.py
```

它向：

```text
http://127.0.0.1:4318/v1/metrics
```

发送 OTLP/HTTP JSON，metric 名称为：

```text
pmt_backend_test_metric
```

经过 Prometheus exporter 后实际看到：

```text
pmt_backend_test_metric_ratio
```

发送：

```bash
/root/projects/failure telemetry infra/send_backend_test_metric.py
```

预期：

```text
OTLP response: HTTP 200
Prometheus metric name: pmt_backend_test_metric_ratio
```

Prometheus 查询：

```bash
curl -fsS --get \
  --data-urlencode 'query=pmt_backend_test_metric_ratio' \
  http://localhost:9090/api/v1/query | jq
```

重要：这条 synthetic metric 是一次性发送的，不是持续生成的。没有重新发送时，经过一段时间可能显示 `no data`。这并不代表 Collector、Prometheus 或 Grafana 宕机。

synthetic dashboard：

```text
http://localhost:3000/d/pmt-backend-link-test/pmt-backend-linkage-validation-synthetic
```

它用于验证：

```text
OTLP -> Collector -> Prometheus -> Grafana
```

它不代表真实 PMT 数据。

---

## 15. 当前真实 Grafana dashboard

当前真实 dashboard：

```text
http://localhost:3000/d/pmt-avc01-redfish/pmt-real-data-avc01-redfish
```

dashboard 文件：

```text
/var/lib/grafana/dashboards/pmt-backend-test/pmt-real-redfish.json
```

仓库中可移植、可版本控制的 dashboard 和生成器：

```text
tools/otel/dashboards/pmt-redfish-comprehensive.json
tools/otel/generate_pmt_dashboard.py
```

Grafana provisioning 文件：

```text
/etc/grafana/provisioning/dashboards/pmt-backend-test.yml
```

当前 dashboard 有 41 个 JSON panel entries，其中 7 个是分区标题、34 个是实际可视化面板：

| 分区 | 主要内容 |
|---|---|
| Fleet health / 采集总览 | Collector、series 数、metric 名称数、scrape age、最高温度、data loss、scrape duration |
| Thermal / 全 Core 热状态 | 当前最热 32 cores、Top 20 历史、最高/平均/最低热包络、选定 core 温度 |
| Core activity & throttling | Core usage 变化率、选定 core usage、64/1024-cycle throttle |
| Selected Core histograms | 任意 core 的频率、温度和电压 bucket 驻留变化率 |
| Memory, CHA & accelerator | RDT MBM local/total、RDT CMT、CHA enable、QAT bandwidth 和 latency |
| Inventory & collection quality | PMT source 拓扑、data-loss count/timestamp、core enable 和新增 data loss |
| Metric Explorer | 从 4387 个名称中搜索任意 metric，查看历史、当前 labels、`rate()` 和 `delta()` |

顶部有 5 个全局变量：

| 变量 | 作用 |
|---|---|
| Endpoint | 选择 BMC/Redfish endpoint |
| Device | 单选、多选或查看所有 DeviceId |
| Access | 单选、多选或查看所有 AccessId |
| Core | 在温度、usage 和三个 histogram 面板中选择 core 0–127 |
| Metric (search all) | 搜索并绘制任意一个 PMT metric |

关键指标使用专用图表和正确单位；不适合同时绘制的数千条长尾 metrics 由 Metric Explorer 完整覆盖。这样既全面，又避免一次渲染 27126 条 series 造成浏览器卡顿。

dashboard 配置为：

```json
"refresh": "20s"
```

因此浏览器打开 dashboard 时，每 20 秒重新查询 Prometheus。底层 PMT receiver 同时每 20 秒采集一次，Prometheus 每 15 秒 scrape 一次。三层都在持续运行。

当前 38 个 PromQL targets 已逐条向 Prometheus 实测，全部查询成功；Dashboard 也已在 Grafana 浏览器中完成渲染检查。注意：dashboard 自动刷新不能替代底层采集；判断 BMC 周期是否持续执行还应查看：

```bash
journalctl -u otelcol-pmt -f \
  | grep --line-buffered 'Metrics'
```

正常情况下约每 20 秒看到一轮：

```text
metrics: 27126, data points: 27126
```

打开 Grafana：

```text
http://localhost:3000
```

默认安装时首次账号通常是：

```text
用户名：admin
密码：admin
```

首次登录后应立即修改默认密码。本文不记录新密码。

如果通过 SSH 连接远程服务器，需要端口转发：

```bash
ssh -L 3000:127.0.0.1:3000 \
    -L 9090:127.0.0.1:9090 \
    root@10.239.173.80 -p 2522
```

然后在本地浏览器打开：

```text
http://localhost:3000
```

如果只需要 Prometheus：

```text
http://localhost:9090
```

---

## 16. 常用的一键检查命令

### 16.1 检查三项服务

```bash
systemctl is-active otelcol-pmt prometheus grafana-server
```

### 16.2 检查端口

```bash
ss -ltnp | grep -E ':3000|:4318|:8889|:9090'
```

### 16.3 检查 PMT mode

```bash
grep -nE 'mode:|metadata:|endpoint:|trigger_action:' \
  /etc/otelcol-pmt-local.yaml
```

预期：

```text
mode: redfish
```

### 16.4 检查 Collector exporter

```bash
curl -fsS http://localhost:8889/metrics >/dev/null \
  && echo 'collector metrics endpoint OK'
```

### 16.5 检查 Prometheus

```bash
curl -fsS http://localhost:9090/-/healthy
curl -fsS --get \
  --data-urlencode 'query=up{job="otel-pmt"}' \
  http://localhost:9090/api/v1/query | jq
```

### 16.6 检查真实 PMT

```bash
curl -fsS http://localhost:8889/metrics \
  | grep 'RedfishEndpoint="avc01"' \
  | head -n 10
```

### 16.7 查看关键日志

```bash
journalctl -u otelcol-pmt --no-pager -n 100 \
  | grep -E 'Everything is ready|Metrics|Failed|aggregator|Redfish'
```

---

## 17. 故障排查手册

### 17.1 Prometheus 显示 `no data`

按顺序检查：

```bash
systemctl is-active otelcol-pmt prometheus
curl -fsS http://localhost:8889/metrics | head
curl -fsS http://localhost:9090/-/healthy
curl -fsS --get \
  --data-urlencode 'query=up{job="otel-pmt"}' \
  http://localhost:9090/api/v1/query | jq
```

如果：

```text
up{job="otel-pmt"} = 1
```

但真实 metric 没有，检查 Collector 日志：

```bash
journalctl -u otelcol-pmt --no-pager -n 100
```

可能原因：

- local mode 下 `/sys/class/intel_pmt/` 不存在；
- BMC 认证失败；
- BMC endpoint 返回空数据；
- GUID + Size 没有 XML 映射；
- Prometheus 查询的 metric 名称写错；
- 时间范围太短；
- 查询使用了错误的标签过滤条件。

### 17.2 BMC 返回 401

典型结果：

```text
HTTP 401 Unauthorized
WWW-Authenticate: Basic
```

说明：

- DNS 和网络通常已经正常；
- URL 能够访问；
- BMC 要求 Basic Authentication；
- 用户名或密码错误、过期，或者账号没有权限。

不要切换 Collector，先单独重新运行：

```bash
/root/projects/failure telemetry infra/validate_bmc_pmt_redfish.sh
```

### 17.3 BMC POST 返回 201，但 Collector 没有指标

检查：

1. GET snapshot 是否返回 200；
2. JSON 顶层是否存在 `TelemetryData`；
3. `TelemetryData` 是否为数组；
4. 每项是否有 `Guid`、`Size`、`CollectionTimestamp`、`Data`；
5. `Guid + Size` 是否在 XML lookup map 中；
6. Collector 日志是否有 `Failed to find XML set for aggregator`。

### 17.4 `Failed to find XML set for aggregator`

示例：

```text
Aggregator not found in lookup map: 0x22491753, size: 6272
```

含义：

```text
BMC 数据已收到
但当前 xml/pmt.xml 找不到对应的 GUID + Size 定义
```

解决方向：

- 确认使用了正确平台的 `xml/pmt.xml`；
- 检查仓库是否为最新版本；
- 确认 BMC 返回的 GUID/Size 是否属于另一个平台配置；
- 向 PMT XML registry 添加正确映射；
- 不要只根据 GUID 名称猜测，必须同时核对 `Size`。

### 17.5 Grafana 页面打开但没有 panel

检查：

```bash
find /var/lib/grafana/dashboards -type f -maxdepth 3
journalctl -u grafana-server --no-pager -n 100
```

确认 provisioning path：

```text
/var/lib/grafana/dashboards/pmt-backend-test
```

然后重启：

```bash
sudo systemctl restart grafana-server
```

### 17.6 SSH 后本地浏览器访问不到

确认 SSH 使用端口转发：

```bash
ssh -L 3000:127.0.0.1:3000 root@10.239.173.80 -p 2522
```

如果本地 3000 被占用，可以换成本地端口：

```bash
ssh -L 3300:127.0.0.1:3000 root@10.239.173.80 -p 2522
```

然后打开：

```text
http://localhost:3300
```

---

## 18. 回滚到 local/synthetic 配置

当前真实 Redfish 配置切换前已经备份：

```text
/etc/otelcol-pmt-local.yaml.before-redfish
```

回滚命令：

```bash
sudo install -m 644 \
  /etc/otelcol-pmt-local.yaml.before-redfish \
  /etc/otelcol-pmt-local.yaml
sudo systemctl restart otelcol-pmt
```

注意：备份文件是切换前的 local + OTLP 配置。回滚后：

- local PMT 仍然会因为 `/sys/class/intel_pmt/` 不存在而没有真实 PMT 数据；
- OTLP synthetic 测试仍可使用；
- Redfish 真实采集会停止。

如果只想停止 synthetic 输入而保留 Redfish，需要从 pipeline 中移除 `otlp` receiver；但当前保留它作为后端 smoke test 是有价值的。

---

## 19. 当前状态和下一步

### 19.1 GNR PUNIT XML 映射已解决

2026-07-14 已切换到上传的 Intel PMT support metadata：

```text
/root/projects/applications.manageability.intel-pmt.tools.python.support.intel-pmt-master/xml/pmt.xml
```

其中包含真实平台所需的精确映射：

- C-Die：`0x22806802 / 6784`；
- IO-Die：`0x22491753 / 6272`。

离线 snapshot 的 36 个 aggregators 已全部 exact match，生产日志不再出现这两组 lookup failure。Collector 仍保持严格 GUID+Size lookup，没有启用 GUID-only fallback。

生产检查：

```bash
journalctl -u otelcol-pmt --since '-5 minutes' --no-pager \
  | grep 'Failed to find XML set for aggregator'
curl -fsS http://127.0.0.1:8889/metrics \
  | grep '^fivr_health_monitor_' | head
```

FIVR 的 exact-schema 解码、poison 处理、两位状态拆分和带内交叉验证见 `docs/gnr-fivr-health-collection-workflow.md`。

### 19.2 Dashboard 已完成全面重构，下一步是告警和业务语义

当前 Dashboard 已覆盖全 Core 温度、usage、三个 histogram、两种 throttle 窗口、RDT MBM/CMT、CHA、QAT、data-loss、设备拓扑、GNR FIVR Health 和全部 metric explorer。下一步不应继续无差别堆图，而应：

- 和平台 owner 确认温度、latency、throttle 和 data-loss 的生产阈值；
- 为关键状态建立 Grafana/Prometheus alert rules；
- 取得 GNR FIVR 两位状态码 0/1/2/3 的权威枚举后增加语义化告警；
- 为 BMC trigger/GET 成功率增加 Collector 自监控 metric；
- 根据业务场景保存不同 dashboard view，例如 thermal、memory、failure triage；
- 为大规模多 BMC 部署评估 recording rules，降低 Top-K 和动态正则查询成本。

### 19.3 设置 Grafana 默认密码和权限

当前默认账号曾用于初始登录。生产使用前必须：

- 修改默认密码；
- 创建个人账号或最小权限账号；
- 不要多人共用 admin；
- 轮换曾经暴露过的 BMC 密码；
- 保护 `/etc/otelcol-pmt-redfish.env`；
- 不将凭据提交到 Git。

### 19.4 处理 TLS 证书

当前配置使用：

```yaml
tls:
  insecure_skip_verify: true
```

这是为了适配 BMC 自签名证书，便于实验验证。生产环境应优先：

- 获取 BMC CA 证书；
- 配置可信 CA；
- 删除 `insecure_skip_verify: true`；
- 验证 TLS hostname 和证书链。

---

## 20. 从零到最终状态的最短复现顺序

如果已经具备源码、Go、OCB、Prometheus 和 Grafana，可以按以下顺序操作。

### Step 1：确认源码和 XML

```bash
cd /root/projects/Intel-PMT
test -f xml/pmt.xml && echo 'XML metadata OK'
```

### Step 2：构建 Collector

```bash
cd /root/projects/Intel-PMT/tools/otel
command -v ocb
ocb --config build-config-pmt-minimal.yaml
sudo install -m 755 build-minimal/otelcol-pmt /usr/local/bin/otelcol-pmt
```

如果 `command -v ocb` 没有输出，先执行第 7.3 节的 OCB 安装步骤；不要在缺少 OCB 时继续运行构建命令。

### Step 3：验证 BMC，不启动 Collector

```bash
/root/projects/failure telemetry infra/validate_bmc_pmt_redfish.sh
```

必须先确认：

```text
POST 2xx
Entries 2xx
Snapshot 2xx
TelemetryData contains aggregators
```

### Step 4：创建认证环境文件

用交互式密码输入生成：

```bash
read -r -s -p 'BMC password: ' P
printf '\n'
printf 'BMC_AUTHORIZATION=%s\n' \
  "Basic $(printf '%s' "debuguser:${P}" | base64 -w0)" \
  | sudo tee /etc/otelcol-pmt-redfish.env >/dev/null
unset P
sudo chmod 600 /etc/otelcol-pmt-redfish.env
```

### Step 5：安装 Redfish 配置

```bash
sudo install -m 644 \
  /root/projects/Intel-PMT/tools/otel/configs/config-avc01-pmt-redfish.yaml \
  /etc/otelcol-pmt-local.yaml
```

### Step 6：配置 systemd

确保 service 包含：

```ini
EnvironmentFile=-/etc/otelcol-pmt-redfish.env
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now otelcol-pmt
```

### Step 7：验证 Collector

```bash
sudo /usr/local/bin/otelcol-pmt validate \
  --config /etc/otelcol-pmt-local.yaml
systemctl is-active otelcol-pmt
curl -fsS http://localhost:8889/metrics \
  | grep 'RedfishEndpoint="avc01"' \
  | head
```

### Step 8：验证 Prometheus

```bash
curl -fsS --get \
  --data-urlencode 'query=up{job="otel-pmt"}' \
  http://localhost:9090/api/v1/query | jq
```

再查询真实温度：

```bash
curl -fsS --get \
  --data-urlencode 'query=c0_c1_c2_c3_temp_c0_temp_celcius{RedfishEndpoint="avc01"}' \
  http://localhost:9090/api/v1/query | jq
```

### Step 9：打开 Grafana

```text
http://localhost:3000/d/pmt-avc01-redfish/pmt-real-data-avc01-redfish
```

---

## 21. 最终理解总结

这套系统不是：

```text
BMC -> Grafana
```

而是：

```text
BMC Redfish
  -> PMT receiver 发起 trigger + collection
  -> 读取 TelemetryData aggregator
  -> 使用 GUID + Size 查 XML
  -> 解析 Data 的 bit fields
  -> 执行 transformation
  -> 生成 OTel metrics
  -> Prometheus exporter :8889
  -> Prometheus scrape :9090
  -> Grafana datasource 查询
  -> Dashboard 展示
```

每一层的问题可以这样定位：

| 现象 | 应检查的层 |
|---|---|
| BMC 401 | 用户名、密码、账号权限、Basic Auth |
| BMC POST 非 2xx | Redfish action URL、JSON body、BMC PMT service |
| BMC GET 非 2xx | snapshot URL、Entries、BMC snapshot 状态 |
| Collector 报 local path absent | 错误使用 local mode 或本机没有 PMT driver |
| Collector 报 XML set not found | GUID + Size 没有 schema 映射 |
| Collector :8889 无指标 | receiver、解析、exporter pipeline |
| Prometheus target down | scrape URL、端口、防火墙、Collector exporter |
| Prometheus target up 但 query no data | metric 名称、标签、时间范围、数据是否持续产生 |
| Grafana no data | datasource、PromQL、时间范围、Prometheus query |

当前最重要的结论是：

```text
真实 BMC PMT 数据已经进入 Collector、Prometheus 和 Grafana。
```

剩余的主要工作不是打通后端链路，而是补齐少数未映射的 PMT XML aggregator，并继续完善面向业务的 dashboard 和告警规则。
