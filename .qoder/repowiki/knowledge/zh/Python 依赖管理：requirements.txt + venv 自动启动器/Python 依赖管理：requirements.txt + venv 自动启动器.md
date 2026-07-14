---
kind: dependency_management
name: Python 依赖管理：requirements.txt + venv 自动启动器
category: dependency_management
scope:
    - '**'
source_files:
    - requirements.txt
    - boot.py
    - .gitignore
---

本项目采用 Python 生态中最基础的依赖管理方案，结合一个自研的 boot.py 启动器实现虚拟环境自动化管理。

1. 依赖声明与版本约束
- 所有第三方库集中声明于根目录 requirements.txt，使用 >= 宽松版本约束（如 pyautogui>=0.9.54、Pillow>=10.0.0），未使用精确锁定文件（无 requirements.lock / poetry.lock）。
- 依赖按功能分组并附带中文注释（屏幕截图、图像处理、音频播放、OpenAI API、阿里云 DashScope、键盘监听、听歌识曲、系统音频录制等），便于维护者理解用途。

2. 虚拟环境与安装策略
- 项目自带 boot.py 通用启动器，核心职责是自动检测同目录下唯一的 .py 主程序，并在其之前完成 venv 生命周期管理：
  - 有效性校验：通过执行子进程检查 sys.prefix 是否指向当前 venv/ 目录，防止目录移动后失效。
  - 变更检测：对 requirements.txt 计算 MD5 哈希，写入 venv/.requirements_hash 标记；若哈希变化则触发增量更新或重建。
  - 增量更新：优先尝试 pip install --upgrade -r requirements.txt，失败时回退到删除旧 venv 再重建。
  - 重试机制：pip_install_with_retry 支持最多 3 次重试，指数退避间隔（2s、4s…），超时 10 分钟，失败后自动清理半成品 venv。
  - 跨平台兼容：Windows 下 Scripts/python.exe，Linux/macOS 下 bin/python。
- 目标程序以 CREATE_NO_WINDOW（Windows）或 start_new_session=True（类 Unix）后台启动，boot.py 立即退出，避免控制台窗口残留。

3. 构建产物与隔离
- build/、dist/ 为打包输出目录（推测由 PyInstaller 生成），venv/ 被 .gitignore 忽略，不纳入版本控制。
- 未发现 vendoring、私有 PyPI 源配置、setup.py、pyproject.toml、Pipfile、poetry.lock 等更高级依赖管理工具的使用痕迹。

4. 开发者应遵循的规则
- 新增依赖必须同步添加到 requirements.txt 并按功能分区添加注释。
- 不要手动修改 venv/ 目录，始终通过双击 boot.py 启动，让启动器负责环境一致性。
- 如需切换 PyPI 镜像源，应在系统 pip 配置中设置（~/.config/pip/pip.conf 或 Windows 注册表），而非在代码中硬编码。
- 由于使用 >= 宽松约束，建议定期运行 pip list --outdated 审查潜在升级风险。