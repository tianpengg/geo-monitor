# Design

## Context

SiteView 使用 UiInput 手填时区，后端接受 ZoneInfo 标识，默认 Asia/Shanghai；IP 的 unknown / trusted 由管理员确认，来源核验读取该配置。UiSelect 已支持中文和 value 搜索、键盘及边界定位。

## Goals / Non-Goals

Goals：减少时区输入门槛，解释 IP 确认含义，保留现有配置与保存协议。

Non-Goals：不检测或修改 Nginx、CDN、代理配置，不自动判断地址可信，不改事件时间或历史核验。

## Decisions

- 新增 utils/timezones.ts，合并中文常用时区、Intl.supportedValuesOf('timeZone') 与当前值，按标识去重；不支持目录 API 时回退常用列表及当前值。UiSelect searchable 提供检索，值仍为 IANA 标识。避免仅列少数地区导致已有配置丢失。
- 不显示易随季节变化的固定偏移；表单说明日期边界、时间显示及夏令时，既有 Asia/Shanghai 默认不变。
- IP 标签采用问句与两种直白选项；推荐 unknown，保留已存 trusted。简短帮助常驻，CDN / 代理的判断放折叠说明，避免扩大表单。
- 仅前端和文档变更；测试选项去重、中文搜索、目录缺失回退、当前值保留及地区时区展示，再用隔离浏览器验证保存重载、键盘及 320 px。

## Risks / Trade-offs

- 浏览器时区目录可能与服务端版本不同 → 保留当前值，最终校验继续由服务端执行，不自动更改时区。
- 解释可能使用户误以为开启即通过官方核验 → 明确需要可用证据，且不更改 Nginx，也不回算历史。
