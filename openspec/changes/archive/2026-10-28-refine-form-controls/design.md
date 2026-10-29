# Design

## Context

现有 Vue 3.5 仅依赖 Vue，原生 select、date、datalist、file 在 App 与 InventoryPanel 出现，普通输入和 textarea 已有基础 CSS。沿用现有配色与 SVG 图标，不改接口或业务口径。

## Goals / Non-Goals

统一可见控件外观和弹层交互。保留底层文本输入、文件选择、自动填充及语义能力，不自行实现操作系统文件浏览器，不增加大型组件库。

## Decisions

- UiInput 封装一致边框、图标、清除和密码显示；属性透传到真实输入，保留 label、autocomplete、required、pattern、readonly、disabled。
- UiPopup 使用 Teleport 与锚点定位，响应滚动和 resize，屏幕上下避让且有最大高度；外部 pointer/focus 关闭，Escape 恢复到触发器。
- UiSelect 使用 combobox/listbox、活动选项与选中标记，爬虫可搜索；可编辑模式用于状态码，保留任意合法 100–599 或 1xx–5xx 输入，不局限建议列表。
- UiDatePicker 使用文本 ISO 输入与自绘 42 格日历，UTC 纯日期计算避免夏令时偏移，官网时区只决定今天；支持方向键、Home/End、PageUp/PageDown，月份变化保持合法日期。日期辅助函数测试闰年、跨月、无效日期及跨时区今天。
- UiFilePicker 保留隐藏文件 input，提供自定义选择、拖入、大小与清空；父组件继续负责 UTF-8、格式及上限检查。原生 details 保留语义，替换默认箭头为本地图标。
- 组件与 CSS 统一为 40 px 基准、浅色边框、靛蓝焦点，弹层独立层级。手机点击区域与浮层尺寸有界，减少动态效果跟随全站设置。

## Risks / Trade-offs

自定义控件增加键盘与焦点责任，因此验证清除、Tab、Escape、外部关闭、弹层位置和查询/导入/登录回归。不把样式完成当作功能完成；仅修改前端，保留既有 Python 验收记录。
