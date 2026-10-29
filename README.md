# geo-monitor

**看清有哪些可识别的 AI 爬虫访问过你的官网。**

Self-hosted AI crawler monitoring from origin access logs.

[![Checks](https://github.com/tianpengg/geo-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/tianpengg/geo-monitor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

geo-monitor 是一个基于源站访问日志的自托管监测工具。在官网服务器安装独立采集器，以只读方式持续读取新增日志，在后台查看 AI 爬虫访问、来源核验、页面覆盖和采集健康状态。

当前版本面向 **一个管理员、一个官网、一条独立日志来源**，支持 Linux、1Panel / 宝塔、Nginx / OpenResty 和 Docker。技术栈为 Python + FastAPI、Vue 3 + TypeScript、SQLite。

[快速部署](#快速部署) · [1Panel 操作说明](docs/1panel-deployment.md) · [识别范围](docs/crawlers.md) · [参与贡献](CONTRIBUTING.md)

## 可以做什么

| 功能 | 说明 |
|---|---|
| 访问概览 | 今天、近 7 天、近 30 天的已识别请求、页面数、活跃爬虫和趋势 |
| 访问明细 | 时间、路径、方法、状态码、爬虫身份、核验状态；支持筛选及有界 CSV 导出 |
| 页面分析 | 查看页面访问排行与精确详情，了解哪些内容被观察到访问 |
| 内容目录 | 配置 Sitemap 自动同步，或导入 XML / CSV / JSON，对照目录查看观测覆盖 |
| 动态爬虫规则 | 内置 20 个 HTTP 身份，可在后台新增、编辑、停用规则及维护核验证据 |
| 采集健康 | 独立心跳、最后收到日志时间、积压、解析异常及已知采集缺口 |
| 独立采集器 | 只读挂载、批量上报、位置持久化、断网重试、重启续传及常见轮转处理 |
| 自托管 | Docker Compose 部署，HTTP / HTTPS 可选，数据由自己保存 |

初始规则包括 Kimi、OpenAI、Anthropic、Perplexity 等已确认的 HTTP 身份。`Bytespider` 显示为“字节跳动爬虫”，`HySpider` 显示为“腾讯混元训练爬虫”，不推定其属于豆包或元宝。千问、DeepSeek 缺少已确认专属规则时保留“识别能力待完善”口径。完整依据和核验边界见 [爬虫说明](docs/crawlers.md)。

## 如何工作

~~~text
官网请求 → Nginx / OpenResty 独立访问日志
                       ↓ 只读
                 独立 Python 采集器
                       ↓ HTTP / HTTPS 主动上报
                 FastAPI → SQLite
                       ↓
                    Vue 管理后台
~~~

采集器部署在日志所在服务器，控制台可同机或分机部署。采集器无需开放入站端口，也不需要修改官网业务代码。日志支持标准 **Nginx Combined**，以及 UA 后恰好多一个带引号字段的 **OpenResty main** 形式；附加字段会被忽略，不用作真实客户端 IP。

**识别与核验是两件事：** User-Agent 匹配只代表请求声明了某个爬虫身份。仅在日志地址可信、官方证据可用且 IP 命中时，才能标为来源已核验；证据缺失、失效、地址不匹配或客户端 IP 不可确认会分别展示。

## 快速部署

需要 Linux、正常运行的 Docker Engine，以及支持 `docker compose` 命令的 Compose 插件。首次安装从源码构建，需要网络访问镜像和依赖仓库，并预留足够的磁盘、内存与构建资源；当前不提供预构建镜像，也不内置公共镜像加速地址。

~~~sh
git clone https://github.com/tianpengg/geo-monitor.git
cd geo-monitor
bash scripts/deploy.sh
~~~

根据提示输入监测后台的访问地址、端口和管理员密码（至少 12 个字符，隐藏输入）。默认账号为 `admin`。脚本创建权限为 0600 的 `deploy/.env`，构建并启动控制台，健康检查通过后输出地址。

无需证书的 HTTP 测试部署示例，先把文档保留 IP 替换为你的服务器地址：

~~~sh
bash scripts/deploy.sh --public-url http://192.0.2.10:18018 --port 18018
~~~

HTTP 会明文传输登录信息、会话、采集凭据及上报数据。HTTPS 保留证书校验，需自行配置证书和反向代理；所选协议必须与访问地址、Cookie 和端口绑定一致。脚本不自动修改防火墙或官网配置。

已有 `deploy/.env` 时，重复部署执行 `bash scripts/deploy.sh`，复用配置与数据卷。配置示例见 [deploy/.env.example](deploy/.env.example)，详细操作、停止、重连及备份见 [运维说明](docs/operations.md)。

### 接入官网日志

1. 登录后台，保存官网域名和统计时区。未核实 CDN / 代理真实 IP 配置时，保持“还不确定”。
2. 在“官网配置 → 安装采集器”生成采集凭据，保留当前页面。
3. 在**官网服务器的宿主机终端**执行页面生成的安装命令，按提示输入该站独立日志的绝对路径及凭据。
4. 预检通过后查看“采集健康”，确认心跳更新。访问一次官网，等待批量上报与看板刷新后检查最后收到日志时间。

首次启用从文件末尾开始，**不自动导入安装前历史日志**。普通浏览器请求不会计为 AI 爬虫；采集正常且没有匹配请求时显示“未观察到可识别的 AI 爬虫访问”。模拟 UA 只能验证分类链路，不能当作真实爬虫或官方核验结果。完整接入测试见 [1Panel 指引](docs/1panel-deployment.md)。

## 使用边界

- 数据来自源站日志，可能不包含 CDN 缓存命中或边缘拦截请求；“未观察到”不代表“从未抓取”。
- 默认保留 30 天明细；页面目录与日志观测窗口的含义不同，不能据此断言全站历史覆盖率。
- 原始 IP 仅在接收内存中用于核验，持久化前脱敏；采集器保存位置等元数据，从保留的源日志重读未确认事件，不另建原始日志副本。上报仍包含核验所需的原始地址。
- 断网补采依赖未压缩源文件仍被保留，不保证无限期离线无损；已知缺口和 copytruncate 的限制会明确展示。
- 采集器默认运行限额为 0.25 CPU / 128 MiB，并只读挂载日志；同机运行与镜像构建仍消耗资源，不能承诺对主站零影响。
- 当前不包含品牌引用检测、内容评分、GEO 权重、转化分析、访问控制、通知告警或 CDN 日志接入。

## 项目状态

当前为 `0.1.0` 初始开源版本。最近一次完整 Python 记录为 **223 passed / 36 skipped**；前端最近记录为 **35 项通过**，类型检查与构建通过。36 项跳过项是 Linux / Docker 部署专项，不计为通过。

维护者反馈实际 HTTP 部署及基础采集展示链路正常；这是用户实测反馈，尚未由本轮工具独立复验。当前双协议完整故障矩阵、实际资源限额 / OOM、官网延迟与错误率仍待专项验收，生产负载与轮转保留窗口需按实际环境复验。最新边界及开源发布检查见 [发布记录](docs/public-release.md) 和 [闭环审查](docs/completeness-audit.md)。CI 徽章反映当前远程检查状态，不替代真实官网验收。

## 本地开发

使用 Python 3.13、uv 和 Node.js 24，依赖锁定在 `uv.lock` 和 `web/package-lock.json`。

~~~sh
uv sync --frozen
npm --prefix web ci
~~~

在后端终端中设置 `GEO_ADMIN_PASSWORD`（至少 12 个字符）、`GEO_PUBLIC_URL=http://127.0.0.1:5173` 和 `GEO_COOKIE_SECURE=false`，然后启动：

~~~sh
uv run python cmd/server/main.py
~~~

另开终端运行 `npm --prefix web run dev`，浏览器访问 `http://127.0.0.1:5173`。构建后的前端可由 FastAPI 直接提供，详见 [贡献指南](CONTRIBUTING.md)。

~~~sh
uv run ruff check internal cmd tests scripts
uv run pytest -q
npm --prefix web test
npm --prefix web run build
uv build --wheel --out-dir .local/build/python
~~~

需要完整容器验收时，在具备 Linux Docker Engine 的隔离环境运行 `uv run python scripts/container_smoke.py --full`，HTTP 增加 `--protocol http`。测试会构建镜像并创建临时容器和数据卷，不应在生产机器执行完整故障测试。

## 文档与贡献

- [部署、停止、重连、备份与 Sitemap](docs/operations.md)
- [1Panel 分步部署及接入测试](docs/1panel-deployment.md)
- [爬虫规则、身份归属与核验依据](docs/crawlers.md)
- [协议与接口](docs/protocol.md) · [目录架构](docs/architecture.md)
- [贡献指南](CONTRIBUTING.md) · [安全问题反馈](SECURITY.md)
- [AI 开发约束](AGENTS.md) · [OpenSpec 正式规范](openspec/specs/)
- [独立首页设计预览](web/prototypes/overview-motion/README.md)（合成演示内容）

欢迎通过 [Issues](https://github.com/tianpengg/geo-monitor/issues) 提交问题与建议，通过 Pull Request 参与贡献。请勿提交真实凭据、原始访问日志或生产数据库。

## 许可证

项目代码使用 [MIT License](LICENSE)。Inter 字体、Tabler 图标及生成的 OpenSpec 工作流文件保留各自许可和归属，详见 [第三方许可说明](THIRD_PARTY_NOTICES.md)。本项目与所列爬虫运营方不存在官方关联或背书。
