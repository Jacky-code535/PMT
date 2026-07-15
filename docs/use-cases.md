# Use Cases

> **文档定位：**以下是上游项目的通用最小示例，不代表 avc01 当前配置、XML 路径、服务名或分享方式。当前系统请先读 `docs/README.md` 和 `docs/complete-pmt-collection-workflow.md`。

## Local Validation
Run Python agent in read-once mode to quickly retireve telemetry.
```bash
sudo python tools/collectd-agent/pmt.py -s file:///path_to_repo_root/xml/pmt.xml -r
```

## Continuous Metrics Streaming
Use OpenTelemetry collector with Prometheus exporter for dashboard integration.
```bash
./otelcol-pmt --config tools/otel/configs/config-example-pmt-local.yaml
```

## Remote Metrics Streaming
Use OpenTelemetry collector in remote configuration.
```bash
./otelcol-pmt --config tools/otel/configs/config-example-pmt-redfish.yaml
```
