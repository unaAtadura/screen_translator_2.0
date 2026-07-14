---
kind: external_dependency
name: 阿里云 CosyVoice 语音合成服务
slug: aliyun-cosyvoice
category: external_dependency
category_hints:
    - vendor_identity
    - framework_behavior
scope:
    - '**'
---

### 文本转语音合成服务
- **角色**: 将识别的原文转换为可播放的语音音频
- **集成方式**: 通过 DashScope SDK 的 `HttpSpeechSynthesizer` 类进行流式调用
- **模型配置**: 使用 `cosyvoice-v3-flash` 模型，默认音色为 `longanhuan`
- **输出格式**: 生成 WAV 格式音频文件 (`cosyvoice.wav`)，采样率 24000Hz
- **播放控制**: 支持正常速度(1.0x)和0.75倍速切换，通过线性插值实现变速播放
- **临时文件管理**: 程序启动和关闭时自动清理 `cosyvoice.wav` 临时文件
- **验证**: 确认具体API参数和音色列表以官方文档为准