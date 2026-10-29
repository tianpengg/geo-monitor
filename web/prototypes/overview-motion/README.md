# 首页与采集健康预览

直接用浏览器打开 [index.html](index.html)。最终 HTML 内嵌图片、字体和图标，复制这一个文件即可离线查看。所有统计均为演示样本，不连接后台。

本轮根据用户确认的 Dub 与 OpenPanel 参考重做：浅灰画布与白色卡片、清晰的数字层级、靛蓝面积趋势、独立采集健康卡，下方展示爬虫排行和最近访问。手机端的最近访问使用逐条卡片，完整保留时间、路径、爬虫、HTTP 状态与核验结果。

## 采集健康

- 按用户最新要求移除动画人物、轨道、扫光及放大、暂停和重播入口。
- 健康卡展示连接、读取、处理状态、最后心跳、最后收到日志、待确认量、解析异常和已知缺口。
- 卡片底部可切换“正常采集 / 补采中 / 已断连”演示；断连保留最后数据时间。
- 点击侧栏“采集健康”直接定位数据卡。减少动态效果偏好会关闭日期数字过渡。

## 页面交互

今天、近 7 天和近 30 天切换统计、趋势与排行，三者总数一致。趋势支持鼠标悬停及左右方向键。访问明细可打开并筛选演示爬虫。官网配置仅展示本次预览的来源说明。

## 重新构建

在项目根目录执行：

```sh
uv run python web/prototypes/overview-motion/build.py
```

`source.html` 为源模板；`build.py` 使用 Python 标准库将本地素材嵌入 `index.html`。素材和构建脚本保留在同一目录中，便于后续调整。

## 素材

- 图标：Tabler Icons v3.35.0，MIT；原始图标及许可证保留在 assets/。
- 西文与数字：内嵌 Inter v4.1，SIL Open Font License；中文使用系统可用的 Microsoft YaHei / PingFang SC 等黑体字体。
- 图表在运行时绘制；页面使用实际 HTML 与数据交互。

浏览器与视觉验证结果见 [design-qa.md](design-qa.md)。正式 Vue 集成不在此预览范围。

设计参考：[Dub Analytics](https://dub.co/analytics)、[OpenPanel](https://demo.openpanel.dev/demo/shoey)。仅借鉴视觉与信息组织，数据和文案使用本项目的独立演示内容。
