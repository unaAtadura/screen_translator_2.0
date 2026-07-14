---
kind: logging_system
name: 基于标准 logging 的双通道日志系统
category: logging_system
scope:
    - '**'
source_files:
    - boot.py
    - screen_translator_with_qwen.py
---

本项目使用 Python 标准库 logging 模块实现日志系统，采用双通道输出策略：启动器与主程序各自独立配置根 logger，分别将日志写入文件和控制台或自定义 UI。

## 架构与组件
- 启动器日志（boot.py）：通过 logging.basicConfig 配置根 logger，同时输出到 boot.log 文件和 stdout。内置日志轮转逻辑——启动前检查文件大小，超过 500KB 自动清空。
- 主程序日志（screen_translator_with_qwen.py）：同样调用 basicConfig，但将输出路由到两个 Handler：标准控制台和自定义 LogWindowHandler。后者继承 logging.Handler，通过 queue.Queue 将日志消息异步投递到 Tkinter 的「日志窗口」UI，避免阻塞 GUI 线程。

## 关键设计决策
1. 每个入口自初始化：boot.py 和 screen_translator_with_qwen.py 各自独立调用 logging.basicConfig，不存在全局共享的 logger 工厂或集中式配置模块。
2. GUI 非阻塞：通过 LogWindowHandler + queue.Queue + after(100, poll_queue) 模式，在后台线程中消费队列并安全更新 Tkinter 控件。
3. 日志格式统一：两处均使用 %(asctime)s - %(name)s - %(levelname)s - %(message)s 格式，便于跨进程关联。
4. 日志级别：默认 INFO；业务代码广泛使用 debug/info/warning/error，未见 critical 使用。

## 开发者约定
- 使用 logger = logging.getLogger(__name__) 获取模块级 logger。
- 优先用 logger.info 记录业务流程节点，logger.debug 记录调试细节，logger.warning 记录可恢复异常，logger.error 记录错误路径。
- 不要在 GUI 线程中直接操作日志 UI，应依赖 LogWindowHandler 的队列机制。
- 未引入第三方日志框架（如 loguru、structlog），保持对标准库的零依赖。