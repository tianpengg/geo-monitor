# Spec Delta

## Purpose

把有效采集来源上报的请求转换为可解释的爬虫访问记录，分离 UA 自报身份与官方来源核验结果。该能力约束国内平台归属、证据有效性和 IP 使用方式，防止将未知或未经核验的流量展示为已确认平台访问。

## ADDED Requirements

### Requirement: 校验采集身份和协议

后台 SHALL 校验网站标识、来源身份、采集凭据和请求结构；拒绝无效来源或不兼容批次，拒绝结果不得写入访问记录或推进来源确认状态。

#### Scenario: 无效采集凭据
- **WHEN** 采集请求使用错误凭据或与凭据不匹配的网站标识
- **THEN** 后台明确拒绝请求，访问明细和统计保持不变

### Requirement: UA 声明身份与国内展示口径

系统 SHALL 将 UA 匹配结果作为声明身份独立保存，支持 KimiBot、Kimi-SearchBot、Kimi-User、Bytespider、HySpider，以及官方已确认的 OpenAI、Claude 和 Perplexity 爬虫 UA；不得仅因 UA 命中就将来源标记为已核验。

#### Scenario: 匹配 Kimi 的三类请求
- **WHEN** UA 命中 KimiBot、Kimi-SearchBot 或 Kimi-User
- **THEN** 系统分别显示 Kimi 训练爬虫、Kimi 搜索爬虫或 Kimi 用户触发访问，并独立显示来源核验结果

#### Scenario: 匹配 Bytespider 或 HySpider
- **WHEN** UA 命中 Bytespider 或 HySpider
- **THEN** 系统分别展示“字节跳动爬虫”或“腾讯混元训练爬虫”，并标注产品归属未确认，不显示为已确认豆包或元宝访问

#### Scenario: 匹配已确认的国际平台 UA
- **WHEN** UA 命中 GPTBot、OAI-SearchBot、ChatGPT-User、ClaudeBot、Claude-SearchBot、Claude-User、PerplexityBot 或 Perplexity-User
- **THEN** 系统展示对应运营方和训练、搜索或用户触发用途，来源核验使用相应官方清单独立判定

### Requirement: 官方来源核验和证据记录

系统 SHALL 使用已配置的官方核验依据检查来源，记录规则版本、证据来源、证据版本或更新时间；核验结果须区分已核验、仅 UA 匹配、IP 不匹配、证据暂不可用和客户端 IP 不可确认。

#### Scenario: IP 命中有效官方清单
- **WHEN** 请求 UA 命中规则，客户端地址可信且位于该规则有效的官方 IP 清单内
- **THEN** 系统保存已核验状态及所使用的证据记录

#### Scenario: IP 未命中官方清单
- **WHEN** 请求客户端地址可信但不在可用官方清单中
- **THEN** 系统显示 IP 不匹配，不将该请求计为已核验来源，也不直接断言其恶意伪造

#### Scenario: 官方证据不可用
- **WHEN** 官方证据无法获取、格式无效或已超过有效期限
- **THEN** 系统继续保存可识别的请求并显示证据暂不可用，不误判为 IP 不匹配

#### Scenario: 没有确认的官方核验方式
- **WHEN** 已识别规则没有可用且已确认的官方核验依据
- **THEN** 系统显示仅 UA 匹配，并说明缺少来源核验依据

#### Scenario: 日志没有可信客户端地址
- **WHEN** 来源尚不能确认日志中的地址代表真实客户端
- **THEN** 系统保留 UA 分类并显示客户端 IP 不可确认，不以代理地址做出确定性来源结论

### Requirement: 原始 IP 的最小使用和脱敏

系统 SHALL 仅在内存中使用原始客户端 IP 完成接收与核验，持久化前脱敏；业务库、采集器状态、错误日志及未知线索不得额外保存原始日志或原始客户端 IP。

#### Scenario: 请求处理完成
- **WHEN** 一批请求完成分类和来源核验
- **THEN** 持久化记录仅包含脱敏地址及核验依据，不保留原始客户端地址

#### Scenario: 核验失败或日志解析异常
- **WHEN** 处理流程发生核验不可用或解析错误
- **THEN** 诊断信息不输出原始日志行和原始客户端 IP，异常不会绕过脱敏要求

### Requirement: 未知请求线索和识别覆盖说明

系统 SHALL 对暂无已确认专属规则的千问、DeepSeek 显示“识别能力待完善”；保留限量、脱敏的未知爬虫线索供后续完善规则，不把未知请求直接归属给平台。

#### Scenario: 规则尚未覆盖的平台
- **WHEN** 管理员查看千问或 DeepSeek 的识别能力说明
- **THEN** 系统显示识别能力待完善，不将没有记录解释为平台从未访问

#### Scenario: 观察到未知爬虫 UA
- **WHEN** 新请求具有未知的爬虫声明线索但未命中已确认规则
- **THEN** 系统保存受数量限制的规范化 UA 线索、计数及最近时间，不将其加入某个已知平台的请求数
