# Design

## Context

见 proposal.md。现场复现空轮询改写状态、单轮读完 4194305 字节异常行；默认 Compose 只做日志只读挂载。现有 194 项 Python / 35 项前端通过，36 项部署测试跳过；Docker Linux 引擎管道不存在，无法实际容器验收。

## Goals / Non-Goals

Goals：限制补采与损坏输入的单轮开销，减少状态写放大，保持去重和隐私，给出真实的闭环审查结果。

Non-Goals：不改变官网或 Nginx，不读取真实生产日志、不安装或修复 Docker，不保证零 CPU / IO，不加入分布式存储、通知和新数据源。

## Decisions

- Tailer 设置每轮 READ_BUDGET=256 KiB。常规行在剩余预算可容纳 MAX_LINE_BYTES+1 时才读取；超长行以内存 offset / cursor / identity / reason 扫描，可用剩余预算继续，行尾完整后提交一个 Issue 区间。确认前不写扫描位置，重启重新从已确认位置分轮扫描；避免引入部分无效行的持久化格式与旧版本兼容问题。扫描到旧文件 EOF 时仍可查看其他文件，预算耗尽才结束本轮。
- save 缓存最后成功序列化状态，内容不变不执行 fsync / replace。发现阶段清理退休代次及已消失的初始忽略文件 ID；缺口独立保留直到服务端确认。acknowledge 失败恢复旧内存快照，pending 继续重传，防止重复增加错误计数。
- 正常空闲仍用 flush_seconds；积压用 catchup_pause_seconds（默认 0.25、范围 0.05–30）。使用已有 stop.wait，保持失败退避和独立心跳，不引入忙轮询。
- Compose 设置 service 级 cpus / mem_limit / pids_limit / read_only 和日志轮转，CPU、内存使用 GEO_COLLECTOR_CPUS / GEO_COLLECTOR_MEMORY_LIMIT，根文件系统只读且 /tmp 为 16 MiB tmpfs。保留既有用户与权限模型，不通过放宽日志权限或增加内核能力解决读取权限。源码构建开销不受运行限额约束，建议低峰安装及控制台分机。
- 本次审查报告放 docs/completeness-audit.md，按功能、证据、主站边界和待验事项列出；HTTP 已授权代码与旧正式 HTTPS 规范的差异明确标注，不混同本次修复。

## Risks / Trade-offs

- 节流降低补采速度 → 默认参数保守、允许显式调整，保留积压展示，生产日志保留窗口须按真实峰值复验。
- 未结束的异常长行重启会重扫 → 每轮有预算，确认位置安全，心跳与其他文件不被无限长读取占用。
- 128 MiB 或 0.25 CPU 在具体主机可能不足 → 可配置并记录实际限额和内存 / IO，OOM 重启继续原状态；当前不承诺 Docker 执行已经通过。
- 源码构建和同盘文件读取仍有开销 → 明确低峰安装与持续资源观察，不以只读等同于零影响。

## Migration Plan

原配置未包含新增等待字段时使用安全默认；状态版本和已确认偏移保留。更新 Compose 后需要重建容器才能应用限额，复用状态卷，不执行 down -v。容器验证待 Docker 恢复后执行，完成前本变更保留活动状态。
