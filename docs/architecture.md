# 目录与模块职责

根目录遵循用户确认的 cmd、internal、web、deploy、scripts、tests、docs、openspec 分工，并保留工具要求的配置文件。Python 代码直接放入 internal 包，Vue 保持独立 web 项目，不新增业务框架。

| 位置 | 职责 |
|---|---|
| `cmd/server/main.py`、`cmd/collector/main.py` | 显式启动入口，仅调用内部 CLI |
| `internal/` | Python 包；直接包含 server、collector、logparse、crawler、storage、config 和 protocol |
| `web/` | Vue 源码、前端测试、静态素材和独立设计原型 |
| `tests/` | Python、集成、隔离浏览器服务和 Linux 容器验收 |
| `deploy/` | Compose、Dockerfile、配置示例及 Nginx 示例 |
| `scripts/` | 安装、停止、重连、容器验收、容量及采集合成共存基线脚本 |
| `docs/` | 当前协议、运维、架构和各次验收记录 |
| `openspec/` | 正式规范与变更归档 |
| `.local/` | 被忽略的本地运行数据、报告、缓存及 Python 构建包 |

## 本地产物与兼容

`.local/` 按需生成，未运行相关工具时可以不存在。用户已授权清理本轮临时产物：工作区内的改写脚本、构建包、缓存、测试截图、日志、旧隔离测试数据和迁移清单已移入 Windows 回收站；正式验收结论保留在 docs。下列路径对应关系用于解释历史记录，不表示需要长期保留这些临时文件。

原 `data/`、`dist/`、`output/`、`.pytest_cache/`、`.ruff_cache/`、`.playwright-cli/` 分别迁至 `.local/data/`、`.local/build/python/`、`.local/output/`、`.local/cache/pytest/`、`.local/cache/ruff/`、`.local/playwright/`。本次迁移逐文件校验 SHA-256，结果位于 `.local/reorganization-manifest.json`。

`.venv/` 保持原位置，避免破坏解释器及工具入口的绝对路径；`web/node_modules/` 和 `web/dist/` 留在前端项目内。Git、OpenSpec 技能和 CI 等标准隐藏目录保留。

本地缺省数据库改为 `.local/data/monitor.sqlite3`；新位置不存在且旧 `data/monitor.sqlite3` 存在时使用旧库，显式 `GEO_DATABASE` 始终优先。采集器本地默认状态遵循相同回退规则。生产容器 `/app/data` 和 `/state` 及原数据卷不变。

历史验收和 OpenSpec 归档保留执行时的路径。查找旧截图时将 `output/` 替换为 `.local/output/`，旧 CLI 记录对应 `.local/playwright/`。当前执行命令以 README 和运维说明为准。

## 应用内部边界

`internal/__init__.py` 使目录本身成为 Python 包，业务导入统一为 `internal.*`，不增加 `geo_monitor` 子层。`pyproject.toml` 打包 internal，发行名称仍为 geo-monitor。`geo-monitor-server` 和 `geo-monitor-collector` 命令保持原名称；模块命令为 `python -m internal.server` 和 `python -m internal.collector`。

服务端 app.py 只组装应用；api 按功能组织 HTTP，schemas 定义请求模型，dependencies 提供认证与官网上下文，lifecycle 管理初始化和证据维护。services 包含查询、采集接收和分析操作，storage 提供连接、迁移、事务与备份；采集器不访问服务端数据库。

采集器 `tailer.py` 限制单轮新增源数据读取 256 KiB，异常长行只保留内存扫描位置，完整后确认；状态内容不变不写，退休代次回收，保存确认失败回退内存位置和计数。`runtime.py` 在积压批次之间正等待，心跳独立。`deploy/collector.compose.yaml` 提供可配置 CPU / 内存、PID、只读根文件系统及输出日志上限，实际 cgroup、节流、写入拒绝和 OOM 恢复已由 `tests/deployment/isolation.py` 在隔离 Linux CI 验证；不通过更改源站或扩大权限解决隔离问题。`scripts/collector_baseline.py` 仅在临时目录对比合成写入与采集共存，不替代真实官网性能；有限窗口观测及当前边界见 `docs/collector-isolation-verification.md`。

Vue 的 App.vue 只提供工作区与选择页面，layouts 管理导航和外壳，views 绑定页面。公共输入、下拉、日历及弹层放 components/ui，图表、健康、记录和分析展示放 components/dashboard。会话、筛选、官网设置分别由 composables 管理，useWorkspace 负责页面之间的请求与刷新编排。api 分离 HTTP、认证及监测接口，types、utils、styles、assets 各负其责。

官网配置 `views/SiteView.vue` 使用共用可搜索 `UiSelect` 选择统计时区；`utils/timezones.ts` 合并中文常用地区、Intl 时区目录及当前值，保留存量标识并提供目录缺失回退。IP 确认说明在页面呈现，`useWorkspace.ts` 仅调整选项文案，`useSiteSettings.ts` 继续提交原 timezone / client_ip_mode 字段，不改默认值、后端校验或核验逻辑。

动态爬虫规则由 `internal/crawler/catalog.py` 管理持久化及修订，`rules.py` 保存初始种子和完整词匹配，`fetch.py` 执行受限的公网 HTTPS 证据抓取，`evidence.py` 管理当前规则的证据及版本有效性。`internal/server/api/rules.py` 提供管理员接口，接收按同一批规则快照分类。稳定标识连接历史统计，历史事件保存原规则元数据。

内容目录的本地解析和共用事务合并位于 `services/inventory.py`；`services/sitemap.py` 负责同官网主机的受限 HTTP/HTTPS 下载、单层索引和 gzip，`services/sitemap_sync.py` 管理 SQLite `sitemap_sources` 配置、排队、租约和原子提交。`api/inventory.py` 提供配置与同步入口，`lifecycle.py` 启动独立维护线程，采集器不参与 Sitemap 同步。远程 Sitemap 获取与官方核验证据抓取的协议限制分别维护。

目录前端由 `views/InventoryView.vue` 编排紧凑同步摘要、入口与弹窗开关，`InventoryPanel.vue` 只呈现覆盖统计、表格及分页，空目录仍保留列头。`SitemapPanel.vue` 与 `InventoryImportDialog.vue` 复用 `UiDialog.vue` 及自定义控件，分别承载同步配置和文件导入，成功关闭、失败留存输入、取消清理草稿。`utils/inventoryImport.ts` 校验和读取 UTF-8 文件，组件负责读取忙碌及卸载代次保护；`useWorkspace.ts` 返回明确的保存 / 导入成功结果并检查会话和主机，迟到响应不恢复受保护数据。样式归入 `analysis.css`，共用弹窗首次焦点跳过隐藏文件 input 并选择可见文件按钮。

Vue 的 `views/RulesView.vue`、`composables/useCrawlerRules.ts`、`utils/crawlerRules.ts` 和 `styles/rules.css` 分别负责规则表格与编辑弹窗绑定、请求及草稿和弹窗状态、字段转换与搜索、页面样式。共用 `components/ui/UiDialog.vue` 管理背景隔离、关闭、焦点约束与恢复，样式放 `styles/controls.css`，与现有 `UiPopup.vue` 自定义下拉协作；共用认证和表单不另建实现。手机表格在自身容器横向滚动，编辑弹窗内部滚动。手机导航容纳七个功能入口并预留两行底部空间。
