---
kind: build_system
name: Python 桌面应用构建与启动流程
category: build_system
scope:
    - '**'
source_files:
    - boot.py
    - requirements.txt
    - screen_translator_with_qwen.py
---

本项目为纯 Python + Tkinter 桌面应用，未使用传统编译型构建系统（Makefile、Dockerfile、CI 流水线等），而是采用「轻量级启动器 + 虚拟环境自动管理」的极简构建方式。

## 1. 使用的系统与工具
- 依赖管理：requirements.txt 声明所有第三方库版本范围。
- 运行环境隔离：通过标准库 venv 创建本地虚拟环境，由启动器自动检测/重建。
- 打包分发：仓库中未发现任何打包脚本（pyinstaller / cx_Freeze / Nuitka / auto-py-to-exe）或发布配置，build/ 与 dist/ 目录为空且被 .gitignore 忽略，说明二进制产物不纳入版本控制。
- CI/CD：无 GitHub Actions、Jenkins、GitLab CI 等配置文件。

## 2. 核心文件与职责
- boot.py：通用 Python 项目启动器。负责扫描同目录下除自身外的唯一 .py 作为目标程序；校验并维护 venv/ 虚拟环境（有效性检查、requirements.txt 哈希比对、增量更新、失败回退重建）；以后台进程方式启动目标程序（Windows 下隐藏控制台窗口）；将日志写入 boot.log，超过 500KB 自动清空。
- requirements.txt：固定依赖清单，包含截图、OCR、语音合成、音频录制、AI 客户端等模块。
- screen_translator_with_qwen.py：主应用程序入口，实现屏幕截图 OCR、通义千问翻译、CosyVoice 语音合成、听歌识曲等功能。
- test/：独立测试脚本集合，与主程序解耦。

## 3. 架构与约定
- 单入口模式：开发者只需把主程序 .py 放在根目录，双击 boot.py 即可运行，无需手动激活 venv 或执行 pip install。
- 依赖变更感知：每次启动计算 requirements.txt 的 MD5，与 venv/.requirements_hash 对比，不一致时尝试 pip install --upgrade，失败则删除旧 venv 重建。
- 跨平台兼容：启动器根据 sys.platform 选择 Scripts/python.exe 或 bin/python，并在 Windows 上使用 CREATE_NO_WINDOW 标志隐藏控制台。
- 可插拔功能：主程序通过 try/except ImportError 检测可选依赖（shazamio、soundcard、pyaudiowpatch），缺失时降级提示而非崩溃。

## 4. 开发者应遵循的规则
- 新增依赖后务必同步更新 requirements.txt，否则下次启动会自动安装但可能因网络/编译问题失败。
- 不要直接运行主程序 .py，始终通过 boot.py 启动，以确保虚拟环境一致。
- 如需分发，需自行引入打包工具（如 pyinstaller），当前仓库不包含任何打包配置。
- 保持根目录仅含 boot.py 和单个主程序 .py，避免启动器无法确定目标脚本。