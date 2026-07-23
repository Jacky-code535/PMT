# Reference Papers

## E-SCOUT

文件：

`E-SCOUT_Efficient-Spatial_Clustering-based_Outlier_Detection_through_Telemetry.pdf`

论文信息：

- Eduardo Ortega et al., “E-SCOUT: Efficient-Spatial Clustering-based Outlier Detection through Telemetry”
- 2024 IEEE International Test Conference
- DOI: `10.1109/ITC51657.2024.00044`

与当前实验直接相关的事实：

- 论文使用 PAMPAR benchmark suite 生成正常 workload telemetry signature；
- 13 个 workload 为 PI、DP、NI、OE、HA、DFT、MM、GS、JA、DJ、TR、SH、GL；
- 原实验硬件为 i5-7600K（4 cores）和 i5-12600K（16 cores），不是当前 GNR 服务器；
- 原论文采集 Intel PCM、lm-sensors 和 MSR 0x198 等性能计数器/传感器；
- 论文没有公开每个 PAMPAR workload 的输入规模、OpenMP/MPI/PThreads 选择、线程 affinity、单次持续时间或完整运行命令；
- 论文的 Rowhammer/TRRespass、Spectre 和 Plundervolt/voltage-droop 属于异常注入实验，不在当前正常 workload 数据采集范围内。

PAMPAR 上游：

- Repository: `https://github.com/adrianomg/PAMPAR`
- 固定实验 commit: `568430be779f5bf1d0bfddca35bc796adc215262`
- 论文引用：A. Marques Garcia et al., “PAMPAR: A new parallel benchmark for performance and energy consumption evaluation,” 2020, DOI `10.1002/cpe.5504`

当前 GNR 复现实验不会声称与 E-SCOUT 原始数据逐点一致。它复用“PAMPAR workload + runtime telemetry signature”的方法，但硬件、telemetry schema、采样周期和实验控制均单独记录。

注意：当前 PDF 带有 IEEE Xplore 授权下载提示。提交或公开仓库前，应确认该文件的再分发许可；实验 manifest 可以记录 DOI 和文件 SHA256，但许可不明确时不应公开上传 PDF。
