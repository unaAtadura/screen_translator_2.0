---
kind: external_dependency
name: OpenAI Python SDK
slug: openai-sdk
category: external_dependency
category_hints:
    - sdk_real_api
    - framework_behavior
scope:
    - '**'
---

### OpenAI 兼容客户端
- **角色**: 作为阿里云 DashScope 服务的统一客户端接口
- **集成模式**: 通过设置自定义 base_url 指向 DashScope 兼容端点，复用 OpenAI SDK 的 chat.completions 接口
- **使用方式**: 与标准 OpenAI API 相同的调用方法，但实际连接到阿里云服务
- **重试机制**: 实现了指数退避重试策略，特别针对429频率限制错误
- **注意**: 虽然使用 OpenAI SDK，但实际服务提供方是阿里云 DashScope，不是 OpenAI 本身