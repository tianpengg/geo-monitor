# AI 开发规范

## 工作原则

- 编程、代码审查、调试和重构时使用 karpathy-guidelines。
- 在已授权范围内完成任务；必要的实现细节可合理判断。
- 信息缺失会实质改变目标、范围、验收或授权时，先询问。
- 只读取当前任务需要的文件、文档和技能。
- 保持实现简单，改动与需求直接相关，范围外问题单独说明。
- 验证与改动风险相称；缺陷修复和业务逻辑变更覆盖相关回归。
- 实施任务完成必要验证并修复本次改动的问题后交付；分析和方案任务以给出结论为完成。

## OpenSpec 工作流

- 新增功能、行为变更和架构调整先使用 OpenSpec 明确提案、需求场景、必要设计及实施任务，再编写业务代码。
- 开始变更前阅读相关的 `openspec/specs/` 和 `openspec/changes/`；项目配置以 `openspec/config.yaml` 为准。
- 文档、格式和简单配置修改可直接处理；恢复既有规范行为的局部缺陷修复无需额外提案，但须进行相关回归验证。
- 规范和说明默认使用简体中文，保留 OpenSpec 模板要求的结构和解析关键字。
- 按任务推进实现并记录验证结果；完成后同步规范、归档变更，不将未验证的工作标记为完成。
- 沿用当前会话已有授权，不因进入 OpenSpec 工作流重复请求确认；目标、范围、验收或授权存在实质歧义时再询问。

## 项目目标与范围

- 首版目标：用户在官网服务器安装一次采集器，持续查看可识别的 AI 爬虫访问。
- MVP 仅支持一个管理员、一个官网、一条该站独立的 Nginx Combined 日志来源，运行环境为 Linux / 宝塔 + Docker。
- 从首次启用后的新增日志开始采集，后台按分钟更新；明确说明源站日志可能不包含 CDN 缓存命中或边缘拦截请求。
- 原始 IP 仅用于来源核验，核验后脱敏保存；不得在应用日志、业务库或采集器状态文件中额外保存原始日志或原始 IP。
- 品牌引用检测、内容评分、GEO 权重、转化分析、爬虫访问控制、通知告警和 CDN 接入不属于首版。

## 技术与部署约定

- 使用单仓库：Python + FastAPI 服务端、Python 独立采集器、Vue 3 + TypeScript + Vite 管理后台，SQLite 数据库。
- 服务端提供 API 和构建后的后台静态资源，数据库及采集器状态使用独立持久化卷。
- 采集器作为独立 Python 进程和独立容器运行，不放入 FastAPI 生命周期或 Web worker 的启动任务中。
- Python 代码直接放在 `internal/` 包中，使用 `internal.*` 导入；`cmd/` 提供显式入口，根目录 `pyproject.toml` 管理包、CLI 和检查配置，`uv.lock` 及 `web/package-lock.json` 锁定具体依赖版本。
- `.python-version` 默认选择已验证的 Python 3.13；生产镜像采用相同次版本。
- 采集器部署在官网日志所在服务器，通过管理员选择的 HTTP 或 HTTPS 主动上报；控制台可同机或独立部署。HTTP 安装显式允许明文上报并说明凭据、会话及原始日志未经传输加密；HTTPS 保留证书校验，下载不得降级至 HTTP。
- 日志目录只读挂载；采集器只处理指定来源及其轮转文件，不扫描其他官网日志。
- 源日志保留期限决定断网补采窗口；无法补采的数据须记录缺口，不保证无限期离线无损。
- SQLite 作为首版单实例方案；当前按用户确认的合成测试基线验证容量，生产部署前再根据实际日志量复验，不预先引入分布式组件。
- SQLite 含官方 WAL-reset 修复时启用 WAL；其他版本采用事务性的 DELETE 模式，依据及实际模式记录在设计和验收文档。

## 目录架构与职责

```text
geo-monitor/
|-- AGENTS.md                 # 项目约束、目录职责与维护规则
|-- README.md                 # 项目入口、命令与当前交付状态
|-- LICENSE / THIRD_PARTY_NOTICES.md # 项目及第三方许可
|-- CONTRIBUTING.md / SECURITY.md  # 贡献及安全反馈说明
|-- pyproject.toml / uv.lock   # Python 包、CLI 与依赖锁定
|-- cmd/
|   |-- server/main.py        # 后台服务显式启动入口
|   `-- collector/main.py     # 独立采集器显式启动入口
|-- internal/                # Python 包，直接使用 internal.* 导入
|   |-- server/
|   |   |-- app.py            # FastAPI 应用组装
|   |   |-- api/              # 认证、官网、采集、分析、目录、系统路由
|   |   |-- services/         # 接收、查询、分析、目录及 Sitemap 获取调度、共用过滤器
|   |   |-- schemas.py        # HTTP 请求模型
|   |   |-- dependencies.py   # 认证与官网依赖、应用上下文
|   |   |-- lifecycle.py      # 初始化、证据维护与 Sitemap 调度生命周期
|   |   `-- middleware.py     # 请求大小限制与安全验证错误
|   |-- collector/            # 文件跟踪、确认位置、重试与心跳
|   |-- logparse/             # Combined 解析及字段规范化
|   |-- crawler/              # 初始及动态 UA 规则、受限证据抓取、缓存与核验
|   |-- storage/              # SQLite 连接、迁移、事务与备份
|   |-- config.py             # 配置与本地数据路径兼容
|   `-- protocol.py           # 上报协议与校验
|-- web/
|   |-- src/
|   |   |-- App.vue           # 工作区提供与页面组装
|   |   |-- layouts/          # 后台导航、页头与外壳
|   |   |-- views/            # 登录及七个功能页面（含爬虫规则）
|   |   |-- components/ui/    # 图标、输入、下拉、日历、弹层、文件选择
|   |   |-- components/dashboard/ # 趋势、健康、表格、分析及目录配置导入弹窗
|   |   |-- composables/      # 会话、筛选、官网设置及工作区编排
|   |   |-- api/              # HTTP 客户端、认证与业务接口
|   |   |-- types/            # API 与界面类型
|   |   |-- utils/            # 格式、状态呈现、搜索、日期、时区选项与有界文件读取
|   |   |-- styles/           # 基础、布局、分析及控件样式
|   |   `-- assets/           # 本地图标与字体
|   |-- tests/                # 前端回归
|   |-- public/               # 随构建发布的素材许可证
|   `-- prototypes/           # 独立 HTML 设计预览
|-- deploy/                   # Compose、Dockerfile 与配置示例
|-- scripts/                  # 一条命令部署、采集器安装、停止、重连及验收
|-- tests/
|   |-- unit/                 # Python 单元与服务端 API 测试
|   |-- fixtures/             # 脱敏日志及核验证据
|   |-- browser/              # 隔离浏览器验证服务
|   |-- deployment/           # Linux / HTTP(S) 容器验收
|   `-- integration/          # 续传、断网、轮转与去重
|-- docs/                     # 协议、运维、架构及验收记录
|-- openspec/                 # 配置、正式规范与变更归档
|-- .github/                  # CI
|-- .agents/                  # OpenSpec 工作流技能
`-- .local/                   # 运行时按需生成，本地数据、产物及缓存
```

- `internal/server/` 负责服务端启动、API 和业务组装；`internal/collector/` 提供独立采集入口，包导入不得隐式启动任何进程。
- `internal/logparse/` 和 `internal/crawler/` 不依赖前端或 HTTP 处理器；服务端负责最终身份分类、来源核验和统计口径。
- 日志解析支持标准 Combined，及末尾恰好多一个带引号字段的 OpenResty main；预检和运行使用相同严格规则。附加字段不进入事件或状态、不替换第一列 IP，也不自动确认代理信任，不放宽为任意后缀。1Panel 的容器内日志路径与宿主机路径须分别核实，接入步骤见 `docs/1panel-deployment.md`。
- 爬虫规则由 `internal/crawler/catalog.py` 管理 SQLite 配置及修订，`rules.py` 仅保留初始种子与匹配；`fetch.py` 固定连接到检查过的公网地址并验证 HTTPS，禁止内网、代理和重定向。管理接口位于 `internal/server/api/rules.py`。每批使用一致规则快照，历史保留原元数据，排行按不可变标识聚合；修改 UA、证据或启停时失效缓存并防止旧刷新覆盖。规则最多 256 条，不提供身份删除、任意正则或历史回算。
- 规则页由 `web/src/views/RulesView.vue`、`composables/useCrawlerRules.ts`、`utils/crawlerRules.ts` 及 `styles/rules.css` 分工，复用既有控件、认证和 CSRF；未配置官网仍可进入。退出清理规则与草稿，迟到响应不得恢复；停用身份继续用于历史筛选。Bytespider / HySpider 保留已确认展示与产品归属未确认口径，新增证据源的官方适用性由管理员确认。
- `internal/collector/` 不直接访问服务端数据库；`web/` 通过服务端 API 访问数据。
- 采集器 `tailer.py` 每轮新增源数据读取预算为 256 KiB（不含元数据及身份锚点），超长行只保存内存扫描游标，完整后确认；状态无变化不落盘，退休代次及时回收，本地确认写失败回退内存位置及计数。`runtime.py` 的积压等待默认 0.25 秒、允许 0.05–30 秒，保持独立心跳及失败退避；不得恢复无等待的积压循环或无界超长行读取。
- `deploy/collector.compose.yaml` 默认配置 0.25 CPU、128 MiB、64 PID、只读根文件系统及有限输出日志；CPU / 内存可显式覆盖，不通过修改官网或扩大日志权限绕过隔离。构建与运行都有开销，配置解析不等于真实引擎执行或官网零影响；`scripts/collector_baseline.py` 仅验证临时合成日志写入与采集共存，不能代替真实官网或 cgroup 验收。
- 页面聚合、精确详情、明细和 CSV 使用共用事件过滤器；导出不带分页游标，超过 10000 条或 20 MiB 明确拒绝，不能静默截断。
- 内容目录保留本地 UTF-8 urlset XML、CSV / JSON 导入（1 MiB / 10000 页，不访问上传的地址），并支持官网主域或已登记别名的标准 HTTP/HTTPS Sitemap 自动同步。`services/sitemap.py` 负责固定公网 IP 获取和 XML / 单层索引 / gzip 校验，最多 20 文件、单文件传输和解压各 1 MiB、累计解压 10 MiB / 10000 页，拒绝跳转、内网、DTD 和实体，不访问页面正文；不放宽官方证据的 HTTPS 限制。
- 官网 `aliases` 是管理员明确登记的最多 10 个精确域名，保存在 site 表 JSON 列，默认空，标准化去重并排除主域；不放行通配子域或 IP，不创建第二站。Sitemap 主文件、子文件、页面及本地导入使用同一允许集合，目录归入主域并按路径去重；实际下载器必须使用每个 URL 的主机执行公网 DNS / 固定 IP / TLS，不用主域替别名担保。别名或主域变化在同一事务内递增同步修订、失效运行 token，启用配置重排、暂停保持，旧结果不能提交；目录和最后成功保留。Vue 的 `utils/siteAliases.ts` 处理分隔和数量，官网表单保存 / 载入受会话代次保护、退出清理草稿，定时刷新不得回填未保存字段。
- `services/sitemap_sync.py` 与 `sitemap_sources` 表负责 24 小时调度、排队和 5 分钟租约恢复，由生命周期独立线程执行，不依赖浏览器。事务确认官网主机、配置修订及运行 token 后合并；失败不提交部分目录，配置变化后的旧结果不能写入。保留手动标题与旧页面，不自动删除；暂停保留目录，手动移除但仍在 Sitemap 的路径会再次加入。目录分母、日志保留与观测限制须同时表达，不把未观察当作从未抓取。
- Vue 的 `views/` 负责页面绑定；`InventoryView.vue` 编排目录管理入口与紧凑同步摘要，`InventoryPanel.vue` 仅展示统计、表格及筛选（空目录保留列头），`SitemapPanel.vue` 和 `InventoryImportDialog.vue` 使用共用 `UiDialog.vue` 承载配置和手动导入。保存 / 导入成功关闭，失败在弹窗保留输入，取消重新打开初始化草稿。`utils/inventoryImport.ts` 校验文件格式、1 MiB 和 UTF-8，读取与提交有忙碌及卸载防护；工作区确认会话代次和官网主机后更新并返回成功结果。`PagesPanel.vue` 负责页面分析，`styles/analysis.css` 延续现有视觉；状态刷新不覆盖草稿，退出及迟到响应不能恢复受保护数据。
- 表单统一使用 `UiInput.vue`、`UiSelect.vue`、`UiDatePicker.vue` 和 `UiFilePicker.vue`，由 `UiPopup.vue` 管理弹层定位、外部关闭及 Escape；`utils/controls.ts` 负责可测试的搜索与日期计算，`styles/controls.css` 负责控件状态。后续页面复用这些组件，保留键盘、标签、自动填充及禁用语义，不恢复可见的系统下拉、日期面板或文件按钮；文件选择仍使用隐藏 input 唤起系统文件对话框。
- 官网统计时区用 `UiSelect` 搜索选择；`utils/timezones.ts` 合并中文常用地区、浏览器时区目录和当前已保存值，按标识去重，目录不可用时回退，不静默重置存量时区，不使用固定 UTC 偏移替代地区规则。`SiteView.vue` 解释日期边界及日志第一列 IP；IP 选项保持 unknown / trusted，新官网默认 unknown，不确定时采集和 UA 识别继续，已存状态不能因文案变更而修改。CDN / 代理判断说明采用折叠帮助，配置只在保存后生效，不自动改 Nginx 或历史核验。
- 规则页采用全宽表格，新增及编辑放入共用 `UiDialog.vue` 弹窗；`useCrawlerRules.ts` 管理弹窗与草稿，成功保存关闭，失败保留草稿。弹窗负责背景隔离、Escape、Tab 焦点约束及忙碌解除后的焦点恢复，与 `UiPopup.vue` 下拉协作；样式归入 `controls.css`。手机仅表格横向滚动，弹窗内部滚动，保存期间防止重复提交或误关闭。
- `internal/storage/` 提供明确的事务边界，接收去重、事件入库及相关统计必须保持一致；同步数据库或文件操作不得长时间阻塞 ASGI 事件循环。
- 空目录中的 `.gitkeep` 仅用于保留骨架；目录产生实际文件时移除对应占位文件。
- `scripts/deploy.sh` 负责控制台配置、Compose 构建启动与健康确认，采集器模式复用原安装脚本；既有配置和卷须保留，密码不进入命令行或输出。1Panel 的证书、反向代理和官网日志由管理员配置，容器就绪不等于公网接入完成。相关 Linux 脚本与实际重复部署由 `tests/unit/server/test_deploy_script.py`、`tests/deployment/deploy_script.py` 验证。
- 部署地址决定传输协议：HTTP 默认开放所选主机端口、Cookie 不设置 Secure，无需证书；HTTPS 保持 Secure Cookie、本机绑定及外部证书代理。HTTP 默认端口跟随地址（省略端口为 80），HTTPS 上游默认 8000；既有配置不自动改写，切换须同时调整地址、Cookie、绑定和端口。Vue 的 `utils/installation.ts` 生成同协议下载命令，命令不含采集凭据。

## 目录与规范维护

- 公开仓库使用 Apache-2.0；LICENSE 须随 Python 包、镜像和采集器下载包保留，第三方素材保留原许可。发布前检查待提交文件，实际凭据、日志、数据库、采集状态、运行环境及私人部署说明不得公开；文档使用保留地址和示例域名。通用部署说明为 `docs/1panel-deployment.md`，首次发布及后续许可变更记录为 `docs/public-release.md`。

- 用户明确指定的一级目录为 `cmd/`、`internal/`、`web/`、`deploy/`、`scripts/`、`tests/`、`docs/` 和 `openspec/`。不得自行恢复 `src/`、嵌套 `internal/geo_monitor/` 或合并为 `ops/`。入口只调用内部 CLI，页面与业务逻辑不得堆入入口文件。
- 本地数据、Python 构建包、验收输出与工具缓存统一写入 `.local/`；`.venv/`、`web/node_modules/`、`web/dist/` 及工具标准隐藏目录保持各自位置。显式数据库配置优先，旧默认库有兼容回退；生产持久化卷位置不变。
- `.local/` 不预建；可再生成的缓存、构建包、改写脚本及明确的隔离测试产物在不再需要时清理。临时改写脚本优先使用系统临时目录，不长期留在项目；实际运行数据、当前在用环境及必要配置不得按临时文件清理。
- 目录说明及职责见 `docs/architecture.md`，历史验收与归档保留当时路径，当前执行命令以 README 和运维说明为准。

- 新增、移动或删除一级目录及核心模块时，在同一次变更中更新本文件的目录树和职责；不预建与当前任务无关的目录。
- 调整技术栈、部署边界或数据流时，同步更新 `openspec/config.yaml` 及相关变更的 `design.md`；行为变化同步更新需求场景和任务。
- OpenSpec 自动生成的 `.agents/skills/openspec-*` 文件通过 `openspec update` 维护，不手工修改以承载业务约束。
- 初始变更 44 项任务已实现并通过测试基线验收，归档于 `openspec/changes/archive/2026-10-28-bootstrap-ai-crawler-monitor/`；8 组正式能力规范位于 `openspec/specs/`。
- 后续功能和视觉设计按新的 OpenSpec 变更推进；只有实际实现并验证后才更新任务状态，不将占位目录、文档或 OpenSpec 状态视为实现完成。
- 用户已授权先完整开发专注的爬虫监测产品：页面分析、搜索筛选与 CSV、官方身份扩充、内容目录及观察盲区；开发期间执行隔离测试，真实官网统一接入验收放在最后。单管理员、单官网、单来源及首版排除项保持适用。
- 用户已选定浅色靛蓝首页方向，并确认参考 Dub 的视觉细节和 OpenPanel 的信息层级重做卡片；独立预览位于 `web/prototypes/overview-motion/`。健康区域采用纯数据卡，不提供人物或其动效控制。正式 Vue 已接入真实 API，保留登录、配置安装、明细及健康流程；演示数据仅存在于独立预览和隔离验收环境。
- 首页独立预览 4 项任务已实现并通过浏览器、离线资源和视觉检查，验收记录位于 `web/prototypes/overview-motion/design-qa.md`；变更归档于 `openspec/changes/archive/2026-10-28-preview-overview-motion/`，新增正式规范 `overview-motion-preview`。
- 取消动画人物的 2 项任务已完成并通过相关浏览器回归，归档于 `openspec/changes/archive/2026-10-28-remove-overview-mascot/`；当前正式预览规范与验收记录以纯数据健康卡为准。
- 正式 Vue 集成 6 项任务已实现并验收，归档于 `openspec/changes/archive/2026-10-28-integrate-vue-dashboard/`，新增正式规范 `admin-dashboard-interface`。验证记录位于 `docs/frontend-verification.md`；共用组件与 `utils/presentation.ts` 负责呈现，统计及健康判断继续使用服务端接口口径，前端不得写入演示统计或健康状态模拟器。
- 监测增强 9 项任务已实现并通过隔离验收，归档于 `openspec/changes/archive/2026-10-28-extend-crawler-analysis/`；新增 `page-analytics` 和 `content-inventory`，当前 12 组正式规范。116 项 Python、12 项前端测试及含新增接口的 Docker 基础冒烟通过，详见 `docs/analysis-verification.md`。规则版本 2026-10-28.3 共 20 个 HTTP 身份，仍不推定未确认的国内产品归属。
- 表单控件优化 4 项任务已实现并验收，归档于 `openspec/changes/archive/2026-10-28-refine-form-controls/`；同步 `admin-dashboard-interface`，正式规范仍为 12 组。17 项前端测试、类型检查与生产构建及隔离浏览器通过，含 320 px 弹层检查，详见 `docs/controls-verification.md`；没有新增生产依赖。
- 目录整理 6 项任务已实现并验收，归档于 `openspec/changes/archive/2026-10-28-reorganize-project-structure/`；同步 `self-hosted-deployment`，正式规范仍为 12 组。当前 117 项 Python、19 项前端、类型与构建、wheel、隔离浏览器和 8 组完整 Linux Docker / HTTPS 验收通过，详见 `docs/structure-verification.md`。Python 包直接为 `internal`，不得恢复旧包名层；本次未接入真实官网。
- 独立预览须能直接离线打开，优先内嵌本地素材，不修改生产依赖、后台接口或既有统计口径；记录浏览器与视觉验证结果。
- 一条命令部署的 3 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-add-one-command-deployment/`；已同步 `self-hosted-deployment`。24 项 Linux 回归（包含真实首次部署、登录和重复部署保留数据）及 3 项既有相关回归通过，记录见 `docs/operations.md`；1Panel 公网 HTTPS、反向代理和真实官网接入仍须部署时完成。
- HTTP / HTTPS 首次本地交付记录：120 项 Python、21 项前端测试、类型检查、构建、Ruff、Bash 语法及配置解析通过；当时 Docker Desktop 启动错误导致实际容器验收未完成，用户确认先交付并保留待验任务。后续已由 GitHub Linux CI 收口并归档，见下方最新记录及 `docs/http-deployment-verification.md`。
- 动态爬虫规则的 4 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-manage-crawler-rules/`；已同步 `crawler-identification` 与 `admin-dashboard-interface`，仍为 12 组正式规范。145 项 Python（含 25 项新增规则管理）、25 项前端、类型构建、Ruff、wheel 及隔离浏览器通过；窄屏与退出后迟到响应已验证，详见 `docs/crawlers.md`。36 项 Linux / Docker 部署测试继续跳过，HTTP 活动变更与真实官网接入的未验收状态不变。
- 规则表格及弹窗调整的 3 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-compact-crawler-rule-management/`；已同步 `admin-dashboard-interface`。25 项前端回归、类型构建及实际浏览器验收通过，覆盖保存成功、失败保留草稿、取消、键盘焦点、忙碌保护及 320 px 窄屏，记录见 `docs/crawlers.md`；没有后端变更，未重跑 Python 或 Docker 验收。
- Sitemap 自动同步的 4 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-sync-remote-sitemap/`；已同步 `content-inventory`，仍为 12 组正式规范。194 项 Python（含 49 项新增）、25 项前端、类型构建、Ruff、wheel 及隔离浏览器通过，记录见 `docs/operations.md`。覆盖受限获取、索引 / gzip、事务合并、失败保留、调度重启、旧任务及会话防护和 320 px 窄屏；36 项部署测试继续跳过，HTTP 活动任务及真实官网未验收状态保持不变。
- 内容目录紧凑布局的 3 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-compact-content-inventory/`；同步 `admin-dashboard-interface`，仍为 12 组规范。30 项前端、类型构建与实际浏览器通过，覆盖两个弹窗成功及失败、文件边界、忙碌、键盘、320 px、分页筛选和退出后迟到响应；详见 `docs/operations.md`。仅前端变化，没有重跑 Python、wheel 或 Docker；原部署及真实官网待验边界不变。
- 官网配置易用性 2 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-clarify-site-settings/`；同步 `admin-dashboard-interface`。35 项前端、类型构建和隔离浏览器通过，覆盖时区搜索、回退及保存重载、IP 默认与存量状态、键盘和 320 px；验收见 `docs/operations.md`。仅前端及说明变化，未重跑 Python、wheel 或 Docker，真实官网与部署未验收边界保持不变。
- 功能闭环与低干扰首次本地审查记录：`harden-collector-isolation` 当时 4 / 5 项完成，211 项 Python、35 项前端、类型构建、Ruff、wheel、严格规范与合成共存基线通过，36 项部署测试因 Docker 不可用跳过。采集读取、节流、状态及 Compose 边界已实现；实际限额、只读运行、OOM 及官网观测当时保留待验，未提前归档。后续将隔离故障和真实官网只读观测分为两项任务并完成，见下方最新记录；历史本地数据保留于 `docs/completeness-audit.md`。

- OpenResty main 格式兼容及 1Panel 交付的 3 项任务已完成，归档于 `openspec/changes/archive/2026-10-29-support-openresty-main-logs/`；同步 `incremental-log-collection`，仍为 12 组正式规范。223 项 Python（含 12 项新增格式 / 进程链路回归）、Ruff、wheel 及严格规范校验通过，36 项部署专项跳过；没有 Vue 变更。部署源码包及摘要位于 `.local/build/releases/`，排除实际凭据、数据库、状态及本机环境，校验路径、必需文件、CRC 和逐文件摘要。一例站点的日志路径和资源曾通过 1Panel 只读核对，操作步骤见 `docs/1panel-deployment.md`；未执行真实服务器安装，原 HTTP / 隔离待验任务不变。

- 首次开源交付 `prepare-public-release` 的 3 项任务已完成并归档于 `openspec/changes/archive/2026-10-29-prepare-public-release/`，同步 `self-hosted-deployment`，仍为 12 组规范。公开仓库为 `https://github.com/tianpengg/geo-monitor`，MIT 已识别，真实部署说明留在忽略目录，公开内容脱敏，首次提交采用 GitHub noreply 邮箱。17 项相关 Python、35 项前端、类型构建、Ruff、wheel 许可及元数据、锁文件、文档链接和 346 个索引文件检查通过；GitHub Actions 的完整 Python / 容器检查在发布核对时仍在运行，最终结果见运行链接，不改变原专项未验状态。记录见 `docs/public-release.md`。

## 实施与验证重点

- HTTP 验收已由真实 GitHub Linux CI `40856262530` 收口：257 项 Python / 2 个普通入口跳过、独立 Docker 部署 36 项及 HTTP / HTTPS 各 8 组矩阵通过。`support-http-deployment` 3 / 3 完成并同步两组正式规范，归档于 `openspec/changes/archive/2026-10-29-support-http-deployment/`，依据见 `docs/http-deployment-verification.md`。本机 Engine 仍不可用；低干扰由下一条独立专项证据确认。
- 低干扰验收的 6 / 6 项任务已完成，`harden-collector-isolation` 同步两组规范并归档于 `openspec/changes/archive/2026-10-29-harden-collector-isolation/`，当前没有活动变更，仍为 12 组正式规范。GitHub Linux CI `40895324515`：267 项 Python / 2 个普通入口跳过、独立 Docker 部署 36 项、前端 35 项及类型构建、Ruff、wheel、Bash 均通过；两协议各 9 组矩阵确认实际 cgroup、CPU 节流、只读边界，各 1 次真实 OOM / 自动重启后续传去重及独立合成源站持续服务。维护者回传的官网只读 20 次请求均为 200、P95 13.866 ms、采集内存 30.73–30.84 MiB；工具未直接操作生产服务器，未在生产故障注入。证据和 Artifacts 摘要见 `docs/collector-isolation-verification.md`。生产峰值、长期负载、磁盘争用和轮转保留窗口仍按实际环境复验，无生产停采对照，不作零影响承诺。
- 官网别名 `add-site-aliases` 的 4 / 4 项任务已完成，三组规范已同步，归档于 `openspec/changes/archive/2026-10-29-add-site-aliases/`，仍为 12 组正式能力。271 项 Python 通过 / 36 项本机 Linux 部署专项跳过、37 项前端、类型构建、Ruff、wheel 和严格规范通过；Edge 隔离浏览器验证保存 / 重载、未登记失败后自动恢复、路径去重、错误草稿、刷新、会话失效和迟到保存、正常退出及 320 px。修复已关闭 UiSelect 吞 Escape 的既有局部缺陷并在桌面 / 手机复验层级关闭。公开 XML 的 15 页别名解析通过，但本机代理 DNS 阻止直接受限下载，未复验生产服务器网络或容器；没有修改实际官网、自动添加真实别名或重装采集器，详见 `docs/site-aliases-verification.md`。

- 首次启用从文件末尾建立采集基线，重启恢复已有读取状态；后台提交成功后才推进确认位置。
- 重传使用稳定事件标识去重；心跳独立于业务日志，安静网站也能报告采集健康状态。
- 分开保存 UA 声明身份和官方来源核验结果；未取得证据、证据失效和 IP 不匹配须分别表达。
- 采集正常且无匹配记录时显示“未观察到可识别的 AI 爬虫访问”；断连、积压、解析异常和已知缺口不得显示为正常零访问。
- 安装前时段和采集缺口不按零访问展示；访问发生时间、接收时间和后台统计时区分别定义。
- Python 单元测试使用 pytest，放入 `tests/unit/` 并随模块变更交付；`tests/integration/` 覆盖真实新增日志、重启续传、网络失败、响应丢失后的重传及日志轮转。
- 常用验证：`uv run ruff check internal cmd tests scripts`、`uv run pytest -q`、`npm --prefix web test`、`npm --prefix web run build`、`uv build --wheel --out-dir .local/build/python`；完整 Docker 验收运行 `uv run python scripts/container_smoke.py --full`，不带 `--full` 只执行基础冒烟检查。
- 完整容器验收使用独立 Linux 测试容器、随机 Compose 项目及数据卷，通过 Docker socket 操作本次测试资源；测试 CA、固定核验证据与响应丢失代理只存在于验收环境，不加入生产接口或降低生产 HTTPS 要求。
- `tests/deployment/isolation.py` 仅接受本次随机验收项目的采集器，验证实际 cgroup、只读写入拒绝、CPU 节流及真实 OOM 后恢复；独立合成 HTTP 源站用于停采 / 补采 / OOM 的服务连续性比较。不得用于生产目标或把手动 kill 当作 OOM。JSON 报告记录有限样本 P95、错误率、资源与测量开销，CI 保存脱敏报告，不将其解释为真实官网零影响。
- 浏览器验证使用独立临时数据库，测试截图与日志放入被忽略的 `.local/output/` / `.local/playwright/`，不接入生产数据。
- 有环境阻塞或生产参数未提供时，记录实际已通过的检查及边界，对应 OpenSpec 验收任务保持未完成。
- 用户已确认先使用测试基线，生产参数稍后补充：基线任务可依据已执行结果完成；真实峰值、平均日志行大小、轮转及未压缩保留窗口在生产部署前补齐，不把合成处理速率作为生产吞吐或补采时长承诺。
