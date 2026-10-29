# 识别规则与官方依据

内置种子版本由代码中的 RULE_VERSION 记录；实际识别使用数据库中的启用规则，修改后的版本为“稳定标识@修订号”。UA 按完整产品词匹配，忽略大小写；仅在说明网址中出现名称不算声明该爬虫。来源核验在接收内存中完成，使用带有效期的官方清单快照，UA 与核验状态分开保存。

| 范围 | 已配置 UA | 来源口径 |
|---|---|---|
| Kimi | KimiBot、Kimi-SearchBot、Kimi-User | 分别表示训练、搜索及用户触发访问；使用各自官方 IP 清单 |
| 字节跳动 | Bytespider | 字节跳动爬虫，产品归属未确认；无已配置的官方核验依据时仅 UA 匹配 |
| 腾讯混元 | HySpider | 腾讯混元训练爬虫，产品归属未确认；使用官方 IP 清单 |
| OpenAI | GPTBot、OAI-SearchBot、ChatGPT-User | 分别表示训练、ChatGPT 搜索及用户触发访问；使用各自官方 IP 清单 |
| Anthropic | ClaudeBot、Claude-SearchBot、Claude-User | 分别表示训练、搜索及用户触发访问；使用官方共用 IP 清单 |
| Perplexity | PerplexityBot、Perplexity-User | 搜索与用户触发访问；使用各自官方 IP 清单 |
| Mistral AI | MistralAI-User、MistralAI-Index、MistralAI-Training | 分别为用户请求、搜索索引与训练；前两者分别核验各自地址清单，训练身份无已确认地址源时仅 UA 匹配 |
| Amazon | Amazonbot、Amzn-SearchBot、Amzn-User | 通用、搜索与用户触发访问；Amazonbot 可能用于模型训练，不代表已发生训练；三种身份使用各自地址源 |
| DuckDuckGo | DuckAssistBot | AI 辅助答案实时访问，不用于模型训练；使用其官方 IP 清单 |
| 千问、DeepSeek | 暂未配置已确认的专属规则 | 显示识别能力待完善，未知线索不直接归属平台 |

官方依据（2026-10-28 核对）：

- [Kimi 爬虫说明](https://www.kimi.ai/policies/kimi-crawlers)
- [腾讯混元爬虫说明](https://hy.tencent.com/polices/hy-crawlers)
- [OpenAI 爬虫说明](https://developers.openai.com/api/docs/bots)
- [Anthropic 爬虫说明](https://privacy.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler)
- [Perplexity 爬虫说明](https://docs.perplexity.ai/docs/resources/perplexity-crawlers)
- [Mistral 官方说明](https://docs.mistral.ai/robots)及 [User 地址](https://mistral.ai/mistralai-user-ips.json)、[Index 地址](https://mistral.ai/mistralai-index-ips.json)
- [Amazon 官方说明](https://developer.amazon.com/docs/amazonbot/amazonbot.html)及 [通用地址](https://developer.amazon.com/amazonbot/ip-addresses/)、[搜索地址](https://developer.amazon.com/amazonbot/searchbot-ip-addresses/)、[用户请求地址](https://developer.amazon.com/amazonbot/live-ip-addresses/)
- [DuckAssistBot 官方说明](https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot)及 [地址清单](https://duckduckgo.com/duckassistbot.json)

初始版本 `2026-10-28.3` 共 20 个 HTTP 身份。2026-10-28 在线核对新增官方说明及文件格式：Amazon 三个官方地址页以 HTML 中的 JSON code 块发布，并兼容 `ip_prefix`；管理员维护规则时可选择 JSON 或网页 JSON 代码块两种证据格式，多个候选会拒绝。界面展示当前规则版本和配置依据，新增规则不回填、重新归属或重新核验历史记录。现可在后台“爬虫规则”维护，不再要求每次修改代码部署。

Perplexity 官方页面列出的 .com 清单会跳转至 .ai，规则使用已经核对的最终 HTTPS 地址；运行时不跟随任意重定向。共用证据地址每轮只抓取一次，最多四个抓取任务同时运行，网络错误不阻塞日志接收。

官方清单不可用、格式无效或过期时保存“证据暂不可用”；可信 IP 未命中有效清单时保存“IP 不匹配”。两者不同，均不直接断言恶意。未确认日志地址为真实客户端时，显示“客户端 IP 不可确认”。

识别访问不证明内容被训练、引用或带来转化；记录的核验依据是接收时可用的证据快照，不构成对历史访问时点 IP 归属的额外保证。

## 后台维护规则

“爬虫规则”支持新增、编辑、启用、停用、搜索和单条证据刷新，未配置官网时也能进入。规则标识创建后固定，用于历史筛选；UA 匹配词单独编辑，限定 2–100 个字母、数字、下划线或短横线，以字母开头，不填完整 UA、版本号、正则或 URL。最多 256 条，标识与 UA 匹配词分别不区分大小写唯一；存在多个完整词时，按匹配词长度降序、标识排序选择一个身份。

页面使用全宽表格，集中展示名称、UA、运营方、核验来源、启用状态及操作。点击“新增规则”或某行“编辑”打开弹窗；保存成功后关闭并更新表格，输入错误或版本冲突在弹窗内提示并保留草稿。取消、关闭按钮或 Escape 不提交；重新新增从空表单开始。弹窗支持 Tab 焦点约束和关闭后返回触发按钮，Escape 优先关闭自定义下拉。保存期间禁用提交与关闭，避免重复提交或误关。手机上仅表格横向滚动，弹窗内容内部滚动，标题和底部操作保持可达。

名称、运营方及归属说明可维护；Bytespider / HySpider 仍保留已确认名称和运营方、产品归属未确认口径。新增平台不因为填写了平台名就获得官方认证。核验地址与其身份的适用关系由管理员确认；无证据时只按 UA 识别，客户端地址未确认时仍显示客户端 IP 不可确认。

保存对下一批新增请求生效，不需要更新或重启采集器。改名后排行按稳定标识聚合，历史明细保留原名称、版本和核验；停用后仍可查询历史，不提供删除身份或历史回算。编辑需携带当前修订号，冲突时重新点击该规则的“编辑”，不会静默覆盖。后续启动不会覆盖已编辑的初始规则。

更换 UA、证据源、证据格式或启停会清除该规则的缓存；仅名称等元数据编辑保留可用证据。需要立即获取新证据时，点击列表“刷新核验”，否则由既有维护周期更新。旧版本正在执行的刷新不能覆盖新配置或使新证据失效。失败不阻塞分类，也不把无法取证当作 IP 不匹配。

证据和资料地址要求默认 443 端口的公网 HTTPS，不含凭据；证据抓取解析全部目标地址并拒绝内网，连接固定到检查过的 IP，TLS 验证原主机，不使用代理或跟随重定向。连接与读取超时 5 秒，响应最多 1 MiB。受控测试注入不作为生产不安全模式。

## 动态规则验收（2026-10-29）

- Python 全量 `145 passed, 36 skipped`；其中新增规则管理 25 项，覆盖旧库迁移、初始配置不覆盖、应用重启、动态识别、改名聚合、历史快照、停用与重启用、重传去重、权限 / CSRF、唯一性、修订冲突、256 条上限、字段与国内归属验证、证据切换及旧刷新成功 / 失败防护。
- 证据网络测试使用受控 DNS / TLS / HTTP 对象，验证连接固定到已检查 IP、原主机证书验证路径、非公网 DNS 拒绝、跳转拒绝和 1 MiB 限额；没有重新在线核对全部官方平台，也未把受控证据当成生产证据。
- 前端 25 项测试、类型检查和生产构建通过，包含规则草稿、序列化、搜索与输入边界；Ruff、wheel 构建和规范严格校验通过。
- 实际浏览器使用独立临时数据库及回环地址 8029，验证未配置官网时入口可用，新增、搜索、修改 UA / 名称、启停、冲突保留草稿、刷新后配置保留、自定义下拉和桌面视觉。窄屏实测 320 / 321 CSS 像素无横向溢出，七项导航采用两行并留足底部空间。临时暂停规则列表响应，退出后再释放，登录页保持且规则与草稿未恢复；已清除拦截并还原视口。
- Docker 按用户决定暂不恢复，本轮没有执行 Linux 容器部署与真实官网接入；36 项部署专用测试没有计为通过，原 `support-http-deployment` 活动变更的未验收状态保持不变。生产应用新迁移前需备份数据库。

## 表格与弹窗调整验收（2026-10-29）

- 本次仅调整 Vue 规则页和共用弹窗，没有修改后端、接口或数据库。25 项前端回归、TypeScript 检查与生产构建通过；没有重复执行上一节的 Python 与容器验收。
- 实际浏览器在独立临时数据库、回环地址 8030 验证创建和编辑成功，稳定标识禁用，搜索条件保留；当前 8018 预览仍保留原 20 条规则。重复标识请求失败在弹窗提示且草稿保留，取消后重新新增为空表单。
- 验证背景不可交互、首次字段焦点、Tab / Shift+Tab 循环、Escape 优先关闭下拉、关闭后焦点返回触发按钮。临时暂停真实保存响应，验证忙碌时字段与按钮禁用且 Escape 不关闭；恢复响应后成功保存，焦点在忙碌解除后返回编辑按钮。已移除请求拦截。
- 426 与 320 CSS 像素窄屏检查通过：页面无横向溢出，1080 像素表格在自身容器滚动；320 像素下弹窗宽 296 像素，上边距 12 像素，底部操作在视口内，下拉未超出屏幕。已恢复视口，并刷新用户的当前规则页。
- Docker 与真实官网接入边界沿用上一节，本次界面验收不将未完成的部署任务标记为通过。
