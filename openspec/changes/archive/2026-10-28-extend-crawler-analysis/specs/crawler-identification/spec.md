# Spec Delta

## ADDED Requirements

### Requirement: 扩展身份及规则依据
系统 SHALL 增加经官方确认的 MistralAI-User、MistralAI-Index、MistralAI-Training、Amazonbot、Amzn-SearchBot、Amzn-User 及 DuckAssistBot，准确标注其用途，不将 Amazonbot 的可能训练用途写成实际已训练。能力列表展示当前规则版本及可用官方资料；地址源只应用于其适用身份，缺失训练地址证据时保留仅 UA 匹配，不借用其他身份的地址源。新规则不重写历史未识别记录。

#### Scenario: 相似名称和未匹配地址
- **WHEN** UA 只有某身份的文档 URL 或相似非完整 token，或来源 IP 不在该身份可用清单内
- **THEN** 前者不冒充该身份，后者保留 IP 不匹配，不借用厂商的其他地址证明身份
