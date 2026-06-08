#!/usr/bin/env python3
"""
通用 Python 项目启动器（增强版）
- 自动检测同目录下除自身外的唯一 .py 文件作为目标程序
- 自动管理虚拟环境：校验有效性、依赖变更增量更新、安装重试、半成品清理
- 详细日志记录到 boot.log，启动前检查大小，超过 500KB 自动清空
- 启动目标程序后 boot.py 立即退出，目标程序无控制台窗口（Windows）
"""

import sys
import os
import subprocess
import shutil
import hashlib
import time
import logging
from pathlib import Path

# ---------- 配置 ----------
REQUIREMENTS_FILE = "requirements.txt"   # 项目依赖文件
VENV_DIR = "venv"                        # 虚拟环境目录名
LOG_FILE = "boot.log"                    # 日志文件
PIP_RETRIES = 3                          # pip install 重试次数
RETRY_DELAY_BASE = 2                     # 重试间隔基数（秒）
MAX_LOG_SIZE_BYTES = 500 * 1024          # 日志文件最大大小（500KB）

# ---------- 日志配置 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ---------- 辅助函数 ----------

def check_and_clear_log(project_dir: Path):
    """检查日志文件大小，超过阈值时清空内容"""
    log_path = project_dir / LOG_FILE
    if not log_path.exists():
        return
    try:
        log_size = log_path.stat().st_size
        if log_size > MAX_LOG_SIZE_BYTES:
            with open(log_path, 'w', encoding='utf-8') as f:
                pass
    except (OSError, IOError):
        pass

def get_target_script(script_dir: Path, self_path: Path):
    """返回目录中除自己外唯一的 .py 文件，若没有或不止一个则返回 None 并打印信息"""
    all_py = list(script_dir.glob("*.py"))
    others = [p for p in all_py if p.resolve() != self_path.resolve()]
    if len(others) == 1:
        return others[0]
    elif len(others) == 0:
        logger.error("目录中没有找到除启动器以外的 .py 文件。")
        logger.info("请将你的主程序（例如 main.py）放在当前目录下。")
    else:
        logger.error("当前目录下有多个 .py 文件，无法自动确定要运行哪一个。")
        logger.info("请保持目录简洁，只保留启动器和你需要运行的一个主程序。")
        logger.info("以下是所有 .py 文件：")
        for p in all_py:
            mark = " (启动器)" if p.resolve() == self_path.resolve() else ""
            logger.info(f"  - {p.name}{mark}")
        logger.info("建议：将多余的 .py 文件移走或重命名。")
    return None

def is_venv_valid(venv_path: Path) -> bool:
    """检查虚拟环境是否有效（sys.prefix 指向正确位置）"""
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        return False

    check_script = (
        "import sys; "
        "print('OK' if sys.prefix == r'{}' else 'FAIL')"
    ).format(str(venv_path.resolve()))
    try:
        result = subprocess.run(
            [str(python_exe), "-c", check_script],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path.cwd()
        )
        return result.stdout.strip() == "OK"
    except (subprocess.SubprocessError, OSError):
        return False

def get_requirements_hash(project_dir: Path) -> str:
    """计算 requirements.txt 的 MD5 哈希值（若文件不存在则返回空字符串）"""
    req_file = project_dir / REQUIREMENTS_FILE
    if not req_file.exists():
        return ""
    return hashlib.md5(req_file.read_bytes()).hexdigest()

def is_venv_up_to_date(venv_path: Path, project_dir: Path) -> bool:
    """检查虚拟环境是否已完整安装且依赖与 requirements.txt 一致"""
    marker_installed = venv_path / ".installed"
    marker_hash = venv_path / ".requirements_hash"
    if not marker_installed.exists() or not marker_hash.exists():
        return False
    stored_hash = marker_hash.read_text().strip()
    current_hash = get_requirements_hash(project_dir)
    return stored_hash == current_hash

def pip_install_with_retry(pip_exe: Path, req_file: Path, retries=PIP_RETRIES, upgrade=False):
    """带重试机制的 pip install，失败后自动清理 venv 并抛出异常"""
    cmd = [str(pip_exe), "install", "-r", str(req_file)]
    if upgrade:
        cmd.insert(2, "--upgrade")
    
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"正在{'更新' if upgrade else '安装'}依赖（尝试 {attempt}/{retries}）...")
            subprocess.run(
                cmd,
                check=True,
                timeout=600  # 10分钟超时
            )
            logger.info(f"依赖{'更新' if upgrade else '安装'}成功。")
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"{'更新' if upgrade else '安装'}失败：{e}")
            if attempt < retries:
                delay = RETRY_DELAY_BASE * attempt
                logger.info(f"{delay} 秒后重试...")
                time.sleep(delay)
            else:
                logger.error("所有重试均失败。")
                raise

def update_venv_dependencies(project_dir: Path):
    """在现有 venv 基础上增量更新依赖，并更新哈希标记"""
    venv_path = project_dir / VENV_DIR
    
    if sys.platform == "win32":
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:
        pip_exe = venv_path / "bin" / "pip"
    
    req_file = project_dir / REQUIREMENTS_FILE
    if req_file.exists():
        try:
            pip_install_with_retry(pip_exe, req_file, upgrade=True)
        except Exception:
            logger.error("增量更新依赖失败，回退到重建虚拟环境。")
            return False
    else:
        logger.warning(f"未找到 {REQUIREMENTS_FILE}，跳过依赖更新。")
    
    current_hash = get_requirements_hash(project_dir)
    marker_installed = venv_path / ".installed"
    if not marker_installed.exists():
        marker_installed.touch()
    (venv_path / ".requirements_hash").write_text(current_hash)
    logger.info("依赖更新完成，哈希标记已更新。")
    return True

def rebuild_venv(project_dir: Path):
    """删除旧 venv，创建新 venv，安装依赖，并写入标记文件"""
    venv_path = project_dir / VENV_DIR
    if venv_path.exists():
        logger.info(f"删除旧的虚拟环境：{venv_path}")
        shutil.rmtree(venv_path)

    logger.info(f"创建新的虚拟环境：{venv_path}")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"创建虚拟环境失败：{e}")
        sys.exit(1)

    # 获取 pip 路径
    if sys.platform == "win32":
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:
        pip_exe = venv_path / "bin" / "pip"

    # 安装依赖
    req_file = project_dir / REQUIREMENTS_FILE
    if req_file.exists():
        try:
            pip_install_with_retry(pip_exe, req_file)
        except Exception:
            # 安装失败，清理半成品 venv
            logger.error("依赖安装失败，清理不完整的虚拟环境。")
            shutil.rmtree(venv_path, ignore_errors=True)
            logger.error("请检查网络、PyPI 源或系统编译工具后重试。")
            sys.exit(1)
    else:
        logger.warning(f"未找到 {REQUIREMENTS_FILE}，跳过依赖安装。")

    # 写入完成标记和哈希标记
    (venv_path / ".installed").touch()
    current_hash = get_requirements_hash(project_dir)
    (venv_path / ".requirements_hash").write_text(current_hash)

    logger.info("虚拟环境已就绪。")

def ensure_valid_venv(project_dir: Path):
    """确保虚拟环境存在、有效且依赖匹配，否则更新或重建"""
    venv_path = project_dir / VENV_DIR
    if not venv_path.exists():
        logger.info("虚拟环境不存在，正在创建...")
        rebuild_venv(project_dir)
    elif not is_venv_valid(venv_path):
        logger.warning("虚拟环境无效（可能移动了目录），正在重建...")
        rebuild_venv(project_dir)
    elif not is_venv_up_to_date(venv_path, project_dir):
        logger.warning("依赖列表已变更（requirements.txt 哈希不匹配），尝试增量更新...")
        if not update_venv_dependencies(project_dir):
            logger.info("增量更新失败，正在重建虚拟环境...")
            rebuild_venv(project_dir)
    else:
        logger.info("虚拟环境有效且依赖匹配。")

def run_target_no_console(project_dir: Path, target_script: Path, args: list):
    """使用虚拟环境的 Python 在后台运行目标程序（无控制台窗口），然后 boot.py 退出"""
    if sys.platform == "win32":
        python_exe = project_dir / VENV_DIR / "Scripts" / "python.exe"
        # 使用 CREATE_NO_WINDOW 标志（0x08000000）避免创建控制台窗口
        creation_flags = 0x08000000
    else:
        python_exe = project_dir / VENV_DIR / "bin" / "python"
        creation_flags = 0  # 无特殊标志

    if not python_exe.exists():
        logger.error(f"找不到虚拟环境的 Python 解释器：{python_exe}")
        sys.exit(1)

    cmd = [str(python_exe), str(target_script.resolve())] + args
    logger.info(f"启动目标程序：{' '.join(cmd)}")
    try:
        if sys.platform == "win32":
            subprocess.Popen(cmd, creationflags=creation_flags, close_fds=True)
        else:
            # Linux/macOS：使用 subprocess.DEVNULL 避免继承控制台
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as e:
        logger.error(f"启动目标程序失败：{e}")
        sys.exit(1)

    logger.info("目标程序已启动，启动器退出。")
    sys.exit(0)

# ---------- 主流程 ----------

def main():
    self_path = Path(__file__).resolve()
    project_dir = self_path.parent

    check_and_clear_log(project_dir)

    logger.info("========== Python 项目启动器 ==========")
    logger.info(f"工作目录：{project_dir}")

    # 1. 确定目标脚本
    target = get_target_script(project_dir, self_path)
    if target is None:
        sys.exit(1)
    logger.info(f"目标程序：{target.name}")

    # 2. 确保虚拟环境可用
    ensure_valid_venv(project_dir)

    # 3. 在后台启动目标程序（无控制台）并退出
    run_target_no_console(project_dir, target, sys.argv[1:])

if __name__ == "__main__":
    main()