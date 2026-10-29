# Vue 后台集成验收

日期：2026-10-28，时区 Asia/Shanghai。变更：`integrate-vue-dashboard`。结论：**通过**。

## 范围与环境

将用户确认的浅色卡片设计集成到正式 Vue 应用，移除动画人物。访问概览、明细、采集健康、官网配置及登录均访问现有 FastAPI 接口；没有新增生产依赖、统计规则、数据库结构或测试专用生产接口。

浏览器验证使用 Windows、Node.js 24、Python 3.13 和 Playwright Chromium。`tests/browser/server.py` 创建可丢弃的临时 SQLite 数据库，仅监听回环地址。`--seed` 通过真实管理及接收接口写入受控样本，官方证据缓存使用测试夹具与保留测试 IP，不能视为真实平台访问或真实官方核验结果。界面代码不含这些演示数值或状态选择器。

## 自动检查

| 检查 | 实测结果 |
|---|---|
| `npm --prefix web test` | 11 项通过：缺失值与零值、时间、健康映射、核验证据过期、趋势断点、日期校验、认证状态与网络错误 |
| `npm --prefix web run build` | TypeScript / Vue 类型检查及 Vite 生产构建通过；38 个模块，JS 112.86 kB，CSS 27.33 kB |
| `uv run ruff check src tests scripts` | 通过 |
| `uv run pytest -q` | 72 项通过，53.11 秒；保留原有一条 Starlette/httpx 测试客户端弃用提示 |
| OpenSpec | 本次变更严格校验通过；同步后 10 组正式规范严格校验通过，6 / 6 项任务完成 |

本次修改前端与浏览器验收夹具，没有调整采集器、部署定义或生产后端逻辑，因此未重复完整 Docker / HTTPS 故障验收。该部分既有结果见 `docs/verification.md`。真实官网容量、日志轮转及保留窗口仍须在生产部署前补充和复验。

正式规范 `admin-dashboard-interface` 已同步并逐字比对新增需求及 Purpose；变更归档于 `openspec/changes/archive/2026-10-28-integrate-vue-dashboard/`。

## 真实接口浏览器流程

浏览器脚本及截图位于被忽略的 `output/playwright/vue-qa/`，不提交临时数据库、凭据或测试输出。

| 流程 | 验证结果 |
|---|---|
| 已配置网站登录 | 默认进入概览；四项指标与真实 API 一致：受控样本为 2,368 / 1,824 / 126 / 9；域名、身份及时区来自接口 |
| 首次配置与安装 | 未配置登录进入配置；保存官网、生成凭据及复制成功；安装命令不包含凭据；未安装显示待安装，缺失时间及数量不伪装为零 |
| 安静网站 | 使用真实采集器心跳接口且不提交爬虫事件，显示“未观察到可识别的 AI 爬虫访问”，处理栏为暂无日志 |
| 时间范围与覆盖 | 今天、近 7 天、近 30 天及自定义范围可查询；倒置日期阻止提交；30 天内的安装前时段以覆盖条纹和断线表示；单日仅一个实际日统计点 |
| 明细与核验 | 20 条分页、爬虫筛选、返回上一页通过；展开可读核验解释、实际规则版本、证据更新时间与官方来源；近期访问不混用明细爬虫及分页条件 |
| 采集健康 | 未安装、正常、断连、积压、读取错误及已知缺口分别验证；异常保留最后数据时间；缺口丢失数量未知时明确显示未知 |
| 自动刷新 | 实际等待下一次 30 秒定时刷新，约 27.2 秒收到请求；日期、KimiBot 筛选及第二页游标保持，更新时间推进 |
| 更新失败与恢复 | 注入 503 后保留最后成功数据，显示刷新失败及待刷新状态；重试恢复，失败不显示为正常零访问 |
| 请求竞争 | 延迟旧日期请求后切换范围，旧结果不能覆盖新条件；退出后的迟到响应不能恢复登录或受保护数据 |
| 认证与隐私 | 错误密码显示用户名或密码错误；服务端会话失效返回登录并清理敏感状态；退出清理凭据；localStorage / sessionStorage 不保存凭据 |
| 键盘与手机 | 图表方向键、End 操作及说明可用；手机可读取路径、时间、方法、状态、爬虫、核验结果及展开依据 |

所有流程未捕获到未处理的 JavaScript 异常。故障与认证测试产生预期的 HTTP 401 / 503 控制台网络记录，未将这些记录隐藏或计为应用运行异常。

## 视觉验证

设计依据：`web/prototypes/overview-motion/index.html` 的无人物版本；参考截图为 `output/playwright/design-research/overview-no-mascot-desktop.png`。生产截图以真实接口返回的受控样本渲染，允许与原型在日期筛选、完整时间、实际身份名称及观测覆盖方面不同。

- 配色与卡片：保留灰白画布、白色细边框卡片、靛蓝重点、桌面侧栏，以及趋势 / 健康、排行 / 近期访问的层级。
- 字体与间距：本地 Inter 加中文系统字体；浏览器确认字体加载成功；标题、指标、说明与数据列表保持统一层级。
- 素材：使用本地 Tabler SVG 和 Inter，许可证随构建输出到 `licenses/`；生产界面无人物、精灵或动效控制。
- 布局：在 320、390、768、900、1280、1499 CSS px 宽度检查，无页面横向溢出；手机记录改为卡片，保留全部字段及核验依据。
- 可访问性：标签、状态文字、键盘焦点、图表说明和减少动态效果支持保留；概览可见 HTML 文本的计算颜色对比度检查无低于普通文字 4.5:1 / 大文字 3:1 的结果。该检查不替代完整无障碍审计。

截图以 DPR 1 保存：

| 截图 | 用途 |
|---|---|
| `final-overview-desktop.png` | 1499 px 宽完整概览，最终视觉基准 |
| `final-overview-mobile.png` | 390 px 宽完整概览 |
| `final-mobile-recent.png`、`final-mobile-evidence.png` | 手机记录及展开核验依据 |
| `final-coverage.png` | 30 天未观测区域、断点与覆盖说明 |
| `health-disconnected.png`、`health-backlog.png`、`health-error.png`、`health-degraded.png` | 真实健康接口状态与最后时间 |
| `healthy-empty.png`、`uninstalled.png`、`refresh-failed.png` | 无匹配、未安装与刷新失败 |
| `setup-desktop.png`、`setup-mobile.png`、`login-desktop.png` | 配置、安装和登录 |

检查中发现并已修复：手机单元格继承桌面列宽导致路径拥挤；窄屏现在重置列宽并完整显示依据。错误密码原先误显示为会话过期，现按登录失败表达。日期分隔符对比度由 4.44:1 调整为合格值。修复后重新检查相应流程、截图和构建。无未解决的本次阻塞问题。

## 复现

后续页面分析和目录验收见 [监测增强记录](analysis-verification.md)；最新自定义输入、下拉、日历、文件选择及键盘与小屏检查见 [表单控件记录](controls-verification.md)。本记录保留首次 Vue 集成时的检查范围。

```sh
npm --prefix web ci
npm --prefix web test
npm --prefix web run build
# 仅用于本机隔离验收；不作为生产启动命令。
uv run python tests/browser/server.py --port 8018 --heartbeat-timeout 3600 --seed
```

打开 `http://127.0.0.1:8018/`，测试账号 `admin`，测试密码 `synthetic-browser-password-2026`。数据库随测试进程退出清理；不传 `--seed` 可从空白配置流程开始。浏览器不同数据库实例应使用独立浏览器上下文，避免同一主机名的会话 Cookie 相互覆盖。
