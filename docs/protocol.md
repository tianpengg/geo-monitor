# 采集协议 v1

所有采集接口位于 `/api/collector/`，使用 `Authorization: Bearer <采集凭据>`，与管理员会话分开。请求最多 2 MiB；批次最多 1000 条事件及 1000 条行诊断。当前代码支持选择 HTTP / HTTPS，HTTP 需显式允许明文上报；两种传输的实际容器验收状态见运维说明，不改变本协议的身份和确认语义。

- `POST /preflight`：提交 `version=1`、`site_id`、`source_id`，只验证连接和凭据，不移动采集位置。
- `POST /batches`：提交版本、来源、`generation`、`start_offset`、`end_offset`、`batch_id`、`events` 和 `issues`。
- `POST /heartbeat`：提交来源、进程实例与单调序号、首次基线、读取/确认位置、积压、错误计数和已知缺口。

位置均为源文件字节偏移，区间开始包含、结束不包含。事件和诊断必须无重叠地完整覆盖批次区间；每个事件包含位置、带时区的发生时间、原始客户端 IP、方法、路径、状态码和 UA。原始 IP 仅在内存中用于核验；原查询参数和完整日志不持久化。

事件标识由 `SHA256(source_id:generation:line_start_offset)` 派生；批次标识由 `SHA256(source_id:generation:start_offset:end_offset)` 派生。文件截断或替换须建立新代次。相同内容、不同位置是不同事件。

成功响应包含原 `batch_id`、该批次的 `acknowledged_offset` 和新入库爬虫事件数。只有数据库事务成功后返回确认；采集器核对标识和位置后才保存确认位置。响应丢失时可重传；已确认区间不再次入库，即使相应明细已过保留期。后台拒绝出现未解释位置跳跃的批次。

诊断只包含位置及固定错误代码，不上传原始错误行。未知线索仅保存规范化的爬虫产品 token，最多保留 100 组。

错误：`401` 为凭据或来源错误；`409` 为位置冲突；`413` 为请求超限；`422` 为格式或版本错误；网络与暂时 `5xx` 可退避重试。认证/协议错误不得视作成功推进位置。校验响应不回显密码、原始 IP 或原始负载。

管理接口使用 HttpOnly 会话 Cookie。写请求还需要登录返回的 `X-CSRF-Token`，并检查浏览器 Origin。`/api/overview` 与 `/api/events` 支持 `days=1|7|30` 或 `start=YYYY-MM-DD&end=YYYY-MM-DD`，结束日期包含当天。明细采用 `(occurred_at,id)` 游标，不依赖可漂移的页码偏移。

## 爬虫规则管理

`GET /api/crawler-rules` 返回全部配置与证据可用状态（最多 256 条）；`POST /api/crawler-rules` 新增，`PUT /api/crawler-rules/{token}` 修改，`POST /api/crawler-rules/{token}/refresh-evidence` 刷新单条证据。以上均要求管理员会话，写入要求 CSRF 与合法 Origin，不要求先配置官网。只读识别覆盖仍使用 `GET /api/crawlers`，包含停用规则供历史查询。

写入字段：`token`（稳定标识）、`match_token`、`name`、`operator`、`product_attribution`、`enabled`（布尔）、可空 `evidence_url` / `documentation_url`、`evidence_format=json|amazon-code`。创建不传 `revision`；编辑必须传当前整数修订号且路径标识与 body token 一致。重复或过期修订返回 409，无效字段返回 422，不存在返回 404；不能重命名稳定标识。返回配置包含 `origin`、`revision`、`version`、`updated_at`、`evidence_state` 与最后证据时间；证据可用不等同于某条请求已核验。

规则作用于下一批新增请求，保存每条事件实际使用的规则版本；历史事件、去重与确认位置不回算。证据网络请求不接收或传递采集凭据，不写入原始访问日志。规则配置与备份同属服务端 SQLite，恢复原数据库可恢复配置。

## 页面、明细及内容目录

以下接口要求管理员会话。查询共用 `days` 或 `start/end`，以及可选的 `crawler`、`q`（路径字面子串，最多 200 字符）、`path`（精确路径）、`status`（100–599 或 1xx–5xx）、`verification`（verified / ua_only / ip_mismatch / evidence_unavailable / client_ip_unknown）。无效筛选返回 400；超出分页字段边界返回 422。查询不额外解码路径、合并斜杠或尾斜杠。

| 接口 | 作用与边界 |
|---|---|
| `GET /api/events` | 共用筛选及原时间／ID 游标，limit 1–200 |
| `GET /api/events/export` | 忽略分页游标，按同条件及同顺序导出；最多 10000 条、20 MiB，超限 400，不截断 |
| `GET /api/pages` | 路径聚合排行及筛选后总量；请求量降序、路径升序；limit 1–200，offset 0–1000000 |
| `GET /api/pages/detail?path=/docs/a` | 精确页面的请求与核验量、最近访问、趋势、爬虫及状态分布和观察限制 |
| `GET /api/inventory` | 当前主机的目录、统计与观察限制；共用筛选，另有 state=observed/unobserved，limit/offset 同上 |
| `POST /api/inventory/import` | JSON 请求体 `{ "format": "json", "text": "[\"/docs/a\"]" }`；format 为 xml/csv/json，完整校验后事务合并 |
| `DELETE /api/inventory?path=/docs/a` | 移除当前主机的一个目录条目，不删除已采集日志；需要 CSRF |

CSV 使用 UTF-8 BOM，包含事件时间、路径、方法、状态、爬虫、核验、规则及归属、官方证据来源与版本和时间、时区及源站说明；时间转为官网时区的 ISO 格式。文件不包含原始 IP、完整 UA、查询参数或凭据，单元格公式前缀转义。无记录时只生成表头；响应为 no-store，文件名固定。

本地目录的 UTF-8 文件最多 1 MiB、输入最多 10000 项，目录当前主机总量最多 10000 页。XML 仅 urlset，拒绝 DTD、实体及 sitemap index，不展开网络地址；CSV 需要 path 或 url 列，可选 title；JSON 为字符串或 path/url、可选 title 对象的数组。地址只接受同站 HTTP(S) 标准端口或 / 开头路径，去查询参数和片段，保留原路径编码；同路径更新标题。错误整批拒绝，返回不包含原始文件片段。修改官网主机后不混用旧主机目录。

目录统计分母为符合路径搜索／精确路径的已导入页面；爬虫、状态及核验条件决定哪些页面有匹配访问。state 只筛选列表，不改变分母。空目录比例为 null；缺口、积压、未安装、未来、安装前及默认 30 天明细保留期之外明确提示观察限制。排名和目录的 offset 分页会随新增数据和导入而变化，不承诺跨刷新冻结快照。
## Sitemap 配置与任务

管理员接口：`GET /api/inventory/sitemap` 返回当前官网的配置与实际状态；`PUT /api/inventory/sitemap` 接收 `{ "url": "https://example.com/sitemap.xml", "enabled": true }`；`POST /api/inventory/sitemap/sync` 返回 202，表示已排队或已有任务运行。写接口沿用会话、来源和 CSRF 校验，无官网时返回 404，地址无效返回 400，字段类型或长度错误返回 422。

状态包括 `not_configured`、`pending`、`running`、`success`、`failed`、`paused`。返回 `host`、`url`、`enabled`、`revision`、`last_attempt_at`、`last_success_at`、`next_run_at`、`last_error`、上次成功的 `pages` / `files` / `added` 及 `interval_seconds`（86400）；时间为 Unix 秒。运行 token 和租约不对外暴露。暂停后的手动同步可成功，`enabled` 仍为 false，下一次自动时间为空。

每次完成在事务中确认官网主机、配置修订和运行 token，之后原子合并及更新结果。配置变化使旧任务失效，失败不重置最后成功计数与时间。后台按持久化到期时间恢复，不依赖浏览器常驻。
