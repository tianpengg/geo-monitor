# 目录整理验收

日期：2026-10-28。变更：`reorganize-project-structure`。目录职责以 [架构说明](architecture.md)和 [AGENTS](../AGENTS.md) 为准。

6 项任务均已完成，部署规范已同步并通过严格校验，归档于 `openspec/changes/archive/2026-10-28-reorganize-project-structure/`。

后续清理：按用户授权，本轮本地临时文件及 Python 字节码缓存共 246 个文件（约 16.5 MiB）已移入 Windows 回收站，包括下文引用的临时截图、日志和机器报告。本文保留已执行结果；源码、当前运行环境及当前预览数据库未删除。

## 最终结构

- 根目录保留 cmd、internal、web、deploy、scripts、tests、docs、openspec，以及标准工具和依赖配置。
- internal 本身为 Python 包，直接包含 server、collector、logparse、crawler、storage；没有 src 或嵌套 geo_monitor 目录。cmd 提供服务端和采集器入口，发行名称与两个已安装 CLI 名称保持不变。
- 服务端 app.py 从 501 行拆为 32 行应用组装；api、services、schemas、dependencies、lifecycle 和 middleware 分离。Vue App.vue 从 316 行拆为 37 行组装，页面、布局、控件、业务展示、会话、筛选、官网设置、接口、类型和样式独立组织。
- 本地数据、wheel、验收输出和缓存集中至 .local。迁移时 184 个文件逐一核对 SHA-256，记录位于 `.local/reorganization-manifest.json`；其中运维目录最终保留原位置。缓存后续允许正常更新，源数据和历史报告不删除。
- 默认本地数据库采用 .local/data，兼容旧默认库及显式配置；Docker 的 /app/data 与采集器 /state 及原卷保持不变。镜像显式设置 GEO_DATABASE，直接运行也能使用非 root 用户写入原数据目录。

## 已执行检查

| 检查 | 结果 |
|---|---|
| `uv run ruff check internal cmd tests scripts` | 通过 |
| `uv run pytest -q` | 117 通过；新增本地路径兼容回归 |
| `npm --prefix web test` | 19 通过；新增筛选查询契约与状态隔离回归 |
| `npm --prefix web run build` | 含 noUnusedLocals 的类型检查及构建通过，86 个模块 |
| `uv build --wheel --out-dir .local/build/python` | internal 包构建成功 |
| 两个 cmd 入口 `--help` | 均通过 |
| `uv run python scripts/container_smoke.py --full --report .local/output/structure-container-acceptance.json` | 8 组 Linux / HTTPS 验收通过，Docker Engine 29.6.2，SQLite 3.40.1 / DELETE |
| 服务端镜像单独启动检查 | 默认数据库为 /app/data/monitor.sqlite3，非 root 写权限通过；本次独立镜像已移除 |

完整容器验收覆盖真实 HTTPS 安装和预检、首次 EOF、正常无匹配、20 种身份与核验、实际停止和重连、离线轮转、已提交响应丢失及强杀重传、真实断网与默认 90 秒断连、数据库与配置及游标配套恢复、未确认源清理缺口、只读挂载及脱敏持久化。新增日志可见耗时 10.17 秒，断连检查在最后心跳后 90.093 秒触发，最终 29 条唯一事件及 1 个已知缺口。

首次完整验收发现历史脚本只对 Bytespider 预期 UA 匹配，没有覆盖已在增强版本加入的 MistralAI-Training；已按现有规范及单测补齐该身份的预期，并重新执行完整验收通过。生产识别与来源核验算法保持原有行为。

报告和日志分别位于 `.local/output/structure-container-acceptance.json`、`.local/output/structure-container.log`，本次临时测试容器、网络和数据卷由验收脚本清理。

## 隔离浏览器回归

使用仅监听 127.0.0.1:8018 的临时 FastAPI、独立临时数据库和合成种子，不接入真实官网。

1. 登录后概览显示真实接口提供的 2368 / 1824 / 126 / 9 样本指标；页面、健康和本地图标正常渲染。
2. 页面分析打开 /blog/ai-search 详情，再跳转对应明细；取消精确路径、搜索并选择 KimiBot、查询后明细条件正确。
3. 官网原值保存成功；采集健康、官方身份和核验说明可读。
4. 从迁移后的文件位置选择 JSON，实际导入成功（新增 4 页、目录共 4 页）。
5. 320 × 844 视口下日历左右边界为 12 / 308 px，页面无水平溢出；选择日期回填正确，清空有效；之后恢复正常视口。
6. 退出后回到登录；再次登录后爬虫筛选清空，导航后焦点进入 main；浏览器 console error 为 0。

最终截图位于 `.local/output/playwright/structure-qa/overview-desktop.png` 和 `mobile-calendar.png`。界面视觉与业务口径保持一致；本次验证不替代真实官网接入和生产容量验收。
