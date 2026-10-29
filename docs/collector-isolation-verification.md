# 采集器低干扰验收

本记录区分隔离 Linux 容器的故障执行证据和真实官网短窗口观测。只读采集仍占用 CPU、内存、磁盘和网络；任何结果都不构成“官网零影响”或生产峰值吞吐保证。

`harden-collector-isolation` 的 6 项任务已完成；增量采集和自托管部署规范已同步，变更归档于 `openspec/changes/archive/2026-10-29-harden-collector-isolation/`。公开验收仅包含脱敏汇总，不包含现场日志、域名、地址或凭据。

## 隔离方法

复用完整容器验收执行器，在其随机命名的采集器容器中运行 `tests/deployment/isolation.py`。故障入口要求目标标签属于本次 `geo-monitor-check-…-installed` 项目且服务为 collector，拒绝正常生产项目；QA 文件不进入生产镜像或采集器下载包。

验收同时核对 Docker 配置和 cgroup v2 控制文件，要求默认 0.25 CPU、128 MiB、64 PID、每文件 5 MiB / 2 个输出日志。对只读根目录和来源尝试打开写入，要求实际返回 EROFS；状态卷写入临时合成探针成功，来源摘要不变。

CPU 压力仅发生在隔离采集器内，通过真实 `nr_throttled` 增量证明节流。内存测试在同一受限容器内触碰匿名内存，并提高该容器 PID 1 的 OOM 选择分数；要求 Docker 出现真实 OOM 事件且自动重启计数增加，不将手动 kill 或只有辅助进程退出当作通过。

独立合成 Python HTTP 源站持续写入同一合成日志，依次测量采集器停止、积压采集和 OOM / 自动恢复阶段的请求数、错误率、P95 和最大耗时。源站进程 ID、启动时间与重启计数不变，样本请求全部成功才通过。故障后添加一个唯一已识别请求，再重连，确认基线、来源身份及唯一计数保持一致。

合成服务用于验证持续服务和故障隔离，不模拟完整 Nginx、TLS、真实业务或生产负载。cgroup 资源样本包含探测 exec 的自身开销；IO 可能命中页缓存。P95 只描述有限样本，不设跨机器性能 SLA。

## 执行与报告

```sh
uv run python scripts/container_smoke.py --full
uv run python scripts/container_smoke.py --full --protocol http --report .local/output/container-http-acceptance.json
```

只在具备 cgroup v2 的隔离 Linux Docker 环境执行，不能把该故障工具指向生产容器。每份 JSON 的 `isolation` 包含：

- `limits`：实际限额、CPU 节流增量和只读写入拒绝结果。
- `collector_stopped` / `collector_catching_up` / `during_oom`：分阶段 HTTP 样本和 P95。
- `active_resources`：有限窗口 CPU、cgroup 内存、采集器 PID 1 RSS 和块 IO。
- `oom` / `recovery`：真实事件、自动重启及恢复后的唯一计数。

CI 在成功或失败后保存脱敏 JSON 为 Actions Artifacts，保留 30 天。失败报告也保留已取得的部分证据，不能只凭服务仍在运行判断通过。本地 29 项相关回归、Ruff 和规范检查已通过；实际资源验收以对应 CI 运行及 JSON 结果为准，尚未取得的结果不记为通过。

## 实际隔离结果（2026-10-29）

[验证分支 CI 40895324515](https://github.com/tianpengg/geo-monitor/actions/runs/40895324515) 全部成功。验证代码提交为 `c9e7d9678f48796ca5b48eb2f50468f7aed0fee2`，北京时间 22:49:25 至 23:05:19。完整 Linux Python 为 **267 passed / 2 skipped**，随后独立部署执行器 **36 passed**；前端、Ruff、wheel、Bash 语法以及 HTTP / HTTPS 各 9 组完整检查通过。两种 Python 计数有重叠，不相加。

实际环境为 Docker Engine 29.4.2 / cgroup v2；生产镜像内 SQLite 3.40.1，按项目策略使用 DELETE 日志模式。

| 证据 | HTTPS | HTTP |
|---|---:|---:|
| 实际 CPU / 内存 / PID 上限 | 0.25 CPU / 128 MiB / 64 | 0.25 CPU / 128 MiB / 64 |
| CPU 压力后的节流周期增量 | 28 | 27 |
| 根目录 / 源日志写入拒绝 | EROFS / EROFS | EROFS / EROFS |
| 状态卷合成探针写入 | 成功 | 成功 |
| 真实 OOM 事件 / 自动重启 | 1 / 1 | 1 / 1 |
| 停采源站探测，30 次 | 0 失败，P95 1.538 ms | 0 失败，P95 1.372 ms |
| 积压采集源站探测，60 次 | 0 失败，P95 1.458 ms | 0 失败，P95 1.308 ms |
| OOM 期间源站探测 | 41 次，0 失败，P95 2.776 ms | 39 次，0 失败，P95 2.301 ms |
| 源站容器进程连续性 | 启动时间不变，0 重启 | 启动时间不变，0 重启 |
| 故障后新增 / 重连重复计数 | 1 条 / 0 条 | 1 条 / 0 条 |

积压样本窗口分别为 3.813 秒 / 3.716 秒；CPU 单核占用约 23.483% / 23.909%，cgroup 当前内存约 37.61 / 37.94 MiB，采集器 PID 1 RSS 约 42.64 / 42.77 MiB，块写入差为 16 / 20 KiB，块读取差均为 0。内存口径不同不能相加，CPU 含探针开销；块读取为 0 不代表没有文件读取，可能命中页缓存。有限样本 P95 的差异不代表采集改善或消除了服务延迟。

已下载 Artifacts `12907094135` 的两份 JSON，核对全部断言及内容；归档 ZIP 的 SHA-256 与 GitHub 提供的 digest 一致：`457bb9afaca896a2bed7ed093329fd4236fcba3cbe639fce8b402437da0d7ece`。脱敏本地副本为 `.local/output/isolation-https-acceptance.json`、`isolation-http-acceptance.json` 和 `collector-isolation-ci-summary.json`。本次仅 QA / 文档改变，生产代码、配置默认值及数据库没有变化。

## 真实官网观测

维护者通过 1Panel 宿主机终端只读查看采集器的限额、重启数、CPU / 内存 / 块 IO，并向本机源站发 20 次低频普通 GET。请求使用普通探测 UA，不冒充真实爬虫；只保留状态码和耗时，不保存页面正文、地址、凭据或原始日志。

该短窗口保持官网与采集器正常运行，不执行生产压力、OOM、停采或 Nginx 重启；因此没有真实官网“停采 / 开采”的生产对照，不据此宣称因果上的零影响。结果需与隔离证据、当前流量和资源余量一起评估；真实峰值、平均日志行大小、轮转与未压缩保留期限仍需另行复验。

维护者已回传上述只读命令的 20 组脱敏终端结果，日期为 2026-10-29：

| 指标 | 观测结果 |
|---|---|
| 配置限额 | 250000000 NanoCPU（0.25 CPU）、134217728 字节（128 MiB）、64 PID、根文件系统只读 |
| CPU | 最高显示样本 0.36%；其余 19 个样本显示 0.00%，不将显示舍入解释为绝对零开销 |
| 内存 | 30.73–30.84 MiB / 128 MiB |
| 进程与重启 | 2 个 PID，重启计数 0 |
| 累计块 IO | 读显示 4.79 MB 未变；写由 299 kB 到 356 kB，显示差约 57 kB，不代表所有文件读取 / 写入操作数 |
| 本机源站探测 | 20 / 20 为 HTTP 200，失败 0 |
| 耗时 | P95 13.866 ms，最大 19.835 ms；按原 20 个耗时重新计算核对 |

来源为维护者在官网宿主机运行只读命令回传，工具没有直接登录或读取生产日志。公开记录只保留无地址和凭据的聚合指标，本地脱敏摘要位于 `.local/output/production-observation-summary.json`。

在该有限窗口内未观察到异常重启、源站失败或较高的采集资源占用；结合两协议隔离故障证据，支持本次保守配置下同机运行并持续观察的结论。没有生产停采对照，不能推断采集增加的额外延迟或量化其因果影响；生产峰值、磁盘争用、长期稳定性和轮转保留窗口继续按实际环境复验。本次任务验收通过，不承诺零开销、全工况或无限补采窗口。
