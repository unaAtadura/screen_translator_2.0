---
kind: error_handling
name: 基于 logging 的轻量级错误处理策略
category: error_handling
scope:
    - '**'
source_files:
    - boot.py
    - screen_translator_with_qwen.py
---

该仓库未建立统一的错误类型体系或结构化错误码系统，而是采用 Python 标准库 `logging` + 裸 `try/except` 的轻量级错误处理方式。具体表现如下：

1. **无自定义异常类**：全仓未发现任何 `class.*Error|class.*Exception` 定义，所有业务错误均以字符串形式通过日志记录或直接返回空值（如 `read_api_key()` 失败时返回 `""`）。

2. **集中式日志输出**：两个入口文件各自独立调用 `logging.basicConfig(...)`，将 `ERROR` 级别消息同时写入控制台与文件（`boot.py` 写 `boot.log`，主程序写 `LogWindowHandler` 队列并渲染到 Tkinter 日志窗口）。没有统一 logger 工厂或日志等级配置模块。

3. **异常捕获模式**：`boot.py` 对 `subprocess.CalledProcessError`、`subprocess.TimeoutExpired`、`OSError` 等具体异常做针对性捕获并记录后重试或清理；主程序 `screen_translator_with_qwen.py` 在 AI 请求处用 `except Exception as e` 捕获后按 HTTP 状态码（401/429）分支提示用户，其余一律以 `f"请求失败: {error_str}"` 回退。

4. **启动器容错**：`boot.py` 作为通用启动器，在虚拟环境创建、依赖安装、目标进程拉起等环节均包裹 try/except，失败时记录 `logger.error` 并 `sys.exit(1)`，不向上抛出。

5. **可选依赖降级**：主程序通过顶层 `try/except ImportError` 设置 `SHAZAMIO_AVAILABLE`、`SOUNDCARD_AVAILABLE`、`PYAUDPATCH_AVAILABLE` 标志位，缺失时仅 `logger.warning` 并禁用对应功能按钮，而非抛错退出。

6. **无全局异常钩子**：未见 `sys.excepthook`、`threading.excepthook` 或 `atexit` 之外的全局兜底逻辑，线程内异常仅靠局部 try/except 记录。

开发者约定（隐含）：
- 新增错误路径应使用 `logger.error(f"...: {e}")` 记录，必要时配合 `logger.warning/info` 区分严重度。
- 对外部 I/O、网络、子进程调用必须显式 try/except，禁止让异常冒泡到 Tkinter 事件循环。
- 可选依赖以 `ImportError` 降级，不要直接 raise。
- 如需向用户展示错误，优先更新 UI 状态标签（如 `self.status_label.config(text=f"错误: ...")`），再记日志。