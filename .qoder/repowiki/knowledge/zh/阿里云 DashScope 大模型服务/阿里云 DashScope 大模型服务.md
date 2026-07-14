---
kind: external_dependency
name: 阿里云 DashScope 大模型服务
slug: aliyun-dashscope
category: external_dependency
category_hints:
    - vendor_identity
    - auth_protocol
scope:
    - '**'
---

### 通义千问与大模型服务
- **角色**: 提供OCR识别、文本翻译和AI对话能力的核心云服务
- **集成方式**: 通过 OpenAI SDK 兼容模式访问，base_url 指向 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **认证机制**: 使用 `key.txt` 文件存储 API Key，或通过环境变量 `DASHSCOPE_API_KEY` 配置
- **主要功能**: 
  - OCR+翻译：使用 `qwen3.6-flash` 模型进行图像文字识别和中文翻译
  - AI对话：支持多轮问答交互
- **错误处理**: 包含401(密钥无效)、429(频率限制)、413(请求过大)等常见错误的友好提示
- **验证**: 确认具体API参数和模型名称以官方文档为准