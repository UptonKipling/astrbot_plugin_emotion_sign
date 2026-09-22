# AstrBot 情感举牌插件 (Emotion Sign Plugin)

> 作者：UptonKipling | 版本：v1.1.0

## 功能介绍

当 LLM 回复用户对话时，插件会以一定概率（默认 30%）将 **15 字以内** 的短回复转换为举牌图片发送，而不是纯文本回复。

图片素材根据回复内容的**情感/语境**自动匹配，文字会写在角色手中的素描本位置，使用手写体风格字体。

## 12 种情感类型

| 编号 | 情感 | 图片文件 | 关键词示例 |
|------|------|----------|-----------|
| 1 | 安逸、宁静、困倦、柔和 | image.png | 晚安、好梦、温柔 |
| 2 | 无情感、冷漠 | image(1).png | 嗯、哦、无所谓 |
| 3 | 开心、甜美、温柔、愉悦 | image(2).png | 嘻嘻、哈哈、好耶 |
| 4 | 愤怒、生气 | image(3).png | 生气、讨厌、烦 |
| 5 | 难受、痛苦 | image(4).png | 难受、痛苦、伤心 |
| 6 | 脸红、害羞 | image(5).png | 害羞、脸红、紧张 |
| 7 | 哭泣、悲伤、难过 | image(6).png | 哭、泪、呜呜 |
| 8 | 惊讶、不可思议 | image(7).png | 啊、哇、不会吧 |
| 9 | 激动、兴奋 | image(8).png | 太棒了、冲、燃 |
| 10 | 害怕、恐惧 | image(9).png | 怕、恐怖、不敢 |
| 11 | 无语 | image(10).png | 无语、无奈、服了 |
| 12 | 病娇、黑化 | image(11).png | 病娇、黑化、永远 |

## 安装方法

1. 将本插件压缩包直接上传至 AstrBot WebUI 的插件市场（本地安装），或将解压后的插件文件夹放入 `data/plugins/` 目录
2. 依赖说明：插件依赖 `Pillow` 和 `aiohttp`。AstrBot 加载插件时会自动按 `requirements.txt` 安装；若个别环境下自动安装失败，插件内置了兜底机制，会在导入时自动调用 pip 补装
3. 在 AstrBot WebUI 中重载插件即可使用

## 配置说明

v1.1.0 起支持 **WebUI 可视化配置**（插件管理 → 本插件 → 设置），所有配置项说明如下：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable` | bool | true | 是否启用插件 |
| `generate_probability` | float | 0.3 | 生成图片的概率 (0.0-1.0) |
| `image_provider` | string | "pillow" | 图片生成方式: "pillow"(本地) / "api"(外部) |
| `api_url` | string | "" | 外部图片生成 API 地址（api 模式下必填） |
| `api_key` | string | "" | 外部 API 密钥 |
| `font_path` | string | "" | 自定义字体文件路径（留空自动搜索，插件自带 msyh.ttc 兜底） |
| `max_text_length` | int | 15 | 触发图片生成的最大文字长度 |
| `upscale` | int | 2 | 图片放大倍数 (1-4) |
| `debug` | bool | false | 调试模式 |
| `cleanup_enable` | bool | true | 自动清理渲染图片 |
| `cleanup_days` | int | 7 | 渲染图片保留天数，超过自动删除 |

> **从旧版本升级**：旧版 `data/config.json` 中的自定义配置会在首次加载时自动迁移到 WebUI 配置，无需手动重新填写。

## 渲染图片自动清理

插件生成的渲染图片（`data/output_*.png`、`data/api_output_*.png`）默认**保留 7 天**：

- 插件启动时立即清理一次过期图片，之后**每 24 小时后台检查一次**
- 只删除超过保留天数的渲染产物，`config.json` 等配置文件不受影响
- 保留天数可在 WebUI 配置中修改（`cleanup_days`），也可关闭清理（`cleanup_enable`）

## 管理指令

所有指令前缀为 `/emotion_sign`：

| 指令 | 参数 | 说明 |
|------|------|------|
| `set_prob` | `<概率>` | 设置生成图片的概率 (0.0-1.0) |
| `set_provider` | `<pillow/api>` | 设置图片生成方式 |
| `set_api` | `<url> [key]` | 设置外部 API 地址和密钥 |
| `set_font` | `<路径>` | 设置自定义字体路径 |
| `set_upscale` | `<倍数>` | 设置图片放大倍数 (1-4) |
| `cleanup` | 无 | 立即清理过期的渲染图片 |
| `status` | 无 | 查看当前配置状态 |
| `toggle` | 无 | 切换插件启用/禁用 |
| `test` | `<文本>` | 测试生成举牌图片 |
| `list_emotions` | 无 | 列出所有情感类型 |

## 图片生成方式

### Pillow（默认）
使用 Pillow 库在本地合成图片，无需外部依赖。

### API 模式
可以对接外部图片生成服务。API 请求格式：

```json
POST {api_url}
Content-Type: application/json
Authorization: Bearer {api_key}

{
  "text": "要显示的文本",
  "emotion": "情感名称",
  "image_file": "图片文件名",
  "font_color": [R, G, B]
}
```

API 响应格式（支持以下任一）：
```json
{"image_url": "https://..."}
{"url": "https://..."}
{"image_base64": "base64encoded..."}
{"base64": "base64encoded..."}
```

## 字体说明

插件优先使用自定义字体（`font_path` 配置），其次自动搜索系统中常见的中文字体，插件 `fonts` 目录下自带的 `msyh.ttc` 也会作为兜底，保证各平台开箱即用。

## 工作原理

1. 监听 `on_decorating_result` 事件钩子
2. 提取回复的纯文本内容
3. 检查文本长度是否 <= 15 字
4. 按配置的概率决定是否生成图片
5. 分析文本情感，匹配对应的图片素材
6. 使用 Pillow 将文字渲染到素描本位置
7. 将消息链替换为生成的图片

## License

MIT
