---
kind: external_dependency
name: Shazam 音乐识别服务
slug: shazam
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
---

### 听歌识曲功能依赖
- **角色**: 识别正在播放的音乐，返回歌曲名、艺术家和相关信息
- **SDK 依赖**: 通过 `shazamio` Python 库调用 Shazam 服务
- **系统要求**: 需要预先安装 Rust 编译器用于编译 shazamio 依赖
- **音频录制方案**: 支持三种系统音频录制方式（soundcard、pyaudiowpatch WASAPI环回、pyaudio立体声混音）
- **异步接口**: 使用 `asyncio` 运行异步识别流程
- **结果解析**: 从响应中提取 track.title、track.subtitle、images.coverart、share.href 等字段
- **平台约束**: 主要针对 Windows 系统设计，对蓝牙耳机支持有限