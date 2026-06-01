# -*- coding: utf-8 -*-
import tkinter as tk
import pyautogui
from PIL import Image, ImageEnhance, ImageOps
import base64
import io
import threading
import logging
import os
import atexit
import wave
import pyaudio
import asyncio
import tempfile
from pathlib import Path
from openai import OpenAI
from dashscope.audio.http_tts.http_speech_synthesizer import HttpSpeechSynthesizer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 检查可选依赖
try:
    from shazamio import Shazam
    SHAZAMIO_AVAILABLE = True
except ImportError:
    SHAZAMIO_AVAILABLE = False
    logger.warning("shazamio 未安装，听歌识曲功能不可用")

try:
    import soundcard as sc
    import soundfile as sf
    import numpy as np
    SOUNDCARD_AVAILABLE = True
except ImportError:
    SOUNDCARD_AVAILABLE = False
    logger.warning("soundcard/soundfile/numpy 未安装，系统音频录制功能不可用")

try:
    import pyaudiowpatch as pyaudio_patch
    PYAUDPATCH_AVAILABLE = True
except ImportError:
    PYAUDPATCH_AVAILABLE = False
    logger.warning("pyaudiowpatch 未安装，蓝牙耳机系统音频录制功能不可用")

# 读取API密钥
def read_api_key():
    """从本地key.txt文件读取API密钥"""
    try:
        with open('key.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"读取API密钥失败: {str(e)}")
        return ""

# 初始化通义千问AI客户端
api_key = read_api_key()
qwen_client = None
if api_key:
    try:
        qwen_client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        logger.info("通义千问AI客户端初始化成功")
    except Exception as e:
        logger.error(f"通义千问AI客户端初始化失败: {str(e)}")

COSYVOICE_WAV_FILE = "cosyvoice.wav"

def cleanup_cosyvoice_wav():
    """清理cosyvoice.wav文件"""
    try:
        if os.path.exists(COSYVOICE_WAV_FILE):
            os.remove(COSYVOICE_WAV_FILE)
            logger.info(f"已删除旧文件: {COSYVOICE_WAV_FILE}")
    except Exception as e:
        logger.error(f"删除文件失败: {e}")

def play_cosyvoice_wav(stop_event=None, speed=1.0):
    """播放cosyvoice.wav文件，支持变速播放
    
    Args:
        stop_event: 停止事件
        speed: 播放速度，1.0为正常速度，0.75为0.75倍速
    """
    try:
        if not os.path.exists(COSYVOICE_WAV_FILE):
            return
        
        wf = wave.open(COSYVOICE_WAV_FILE, 'rb')
        p = pyaudio.PyAudio()
        
        # 获取音频参数
        sample_width = wf.getsampwidth()
        channels = wf.getnchannels()
        rate = wf.getframerate()
        
        # 打开音频流
        stream = p.open(format=p.get_format_from_width(sample_width),
                       channels=channels,
                       rate=rate,
                       output=True)
        
        # 读取所有音频数据到内存
        all_data = []
        chunk_size = 1024
        data = wf.readframes(chunk_size)
        while data:
            all_data.append(data)
            data = wf.readframes(chunk_size)
        
        all_data_bytes = b''.join(all_data)
        
        # 将字节数据转换为样本数组
        import struct
        num_samples = len(all_data_bytes) // (sample_width * channels)
        format_str = f"{num_samples * channels}h" if sample_width == 2 else f"{num_samples * channels}B"
        samples = list(struct.unpack(format_str, all_data_bytes))
        
        # 变速重采样
        if speed != 1.0:
            new_samples = []
            num_new_samples = int(num_samples / speed)
            for i in range(num_new_samples):
                # 计算原样本位置
                orig_pos = i * speed
                # 使用简单的线性插值
                floor_pos = int(orig_pos)
                frac = orig_pos - floor_pos
                
                if floor_pos >= num_samples - 1:
                    floor_pos = num_samples - 2
                    frac = 1.0
                
                for ch in range(channels):
                    idx1 = floor_pos * channels + ch
                    idx2 = idx1 + channels
                    
                    if idx2 >= len(samples):
                        idx2 = idx1
                    
                    # 线性插值
                    val1 = samples[idx1]
                    val2 = samples[idx2]
                    new_val = int(val1 * (1 - frac) + val2 * frac)
                    
                    # 限制范围
                    if sample_width == 2:
                        new_val = max(-32768, min(32767, new_val))
                    else:
                        new_val = max(0, min(255, new_val))
                    
                    new_samples.append(new_val)
            
            # 转换回字节数据
            samples = new_samples
            num_samples = num_new_samples
        
        # 打包为字节
        format_str = f"{len(samples)}h" if sample_width == 2 else f"{len(samples)}B"
        audio_data = struct.pack(format_str, *samples)
        
        # 分块播放
        chunk_size = 1024 * channels
        for i in range(0, len(audio_data), chunk_size):
            if stop_event and stop_event.is_set():
                break
            chunk = audio_data[i:i + chunk_size]
            stream.write(chunk)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()
        
        if not (stop_event and stop_event.is_set()):
            logger.info(f"音频播放完成(速度: {speed}x)")
    except Exception as e:
        logger.error(f"音频播放失败: {e}")

class ScreenTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("屏幕翻译工具 (v2.0)")
        logger.info("程序启动，初始化界面")
        
        # 清理旧的语音文件
        cleanup_cosyvoice_wav()
        
        # 注册程序关闭时的清理函数
        atexit.register(cleanup_cosyvoice_wav)
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # 语音合成相关状态
        self.synthesizing = False
        self.playing = False
        self.play_stop_event = None
        self.play_thread = None
        # 播放速度状态：0=正常速度(1.0x)，1=0.75x，循环切换
        self.speed_mode = 0
        # 标记是否是新音频
        self.is_new_audio = False
        
        # 先不设置固定大小，让界面元素自动调整
        self.root.wm_attributes('-topmost', False)  # 主界面不需要保持在顶层
        self.root.wm_attributes('-alpha', 0.9)
        
        # 创建界面元素
        self.title_label = tk.Label(root, text="屏幕翻译工具 (v2.0)", font=("Arial", 14, "bold"))
        self.title_label.pack(pady=10)
        
        # 选择区域按钮
        self.select_translate_area_btn = tk.Button(root, text="选择译文区域", command=self.select_translate_area, font=('Arial', 12))
        self.select_translate_area_btn.pack(pady=5)
        
        self.select_recognize_area_btn = tk.Button(root, text="选择识别区域", command=self.select_area, font=('Arial', 12), state=tk.DISABLED)
        self.select_recognize_area_btn.pack(pady=5)
        
        # 中止按钮
        self.abort_btn = tk.Button(root, text="中止", command=self.abort_ai_interaction, 
                                   bg='orange', fg='black', font=('Arial', 12), state=tk.DISABLED)
        self.abort_btn.pack(pady=5)
        
        # 关闭按钮
        self.close_btn = tk.Button(root, text="关闭", command=self.close_border, 
                                   bg='red', fg='white', font=('Arial', 12), state=tk.DISABLED)
        self.close_btn.pack(pady=5)
        
        # 听歌识曲按钮
        self.shazam_btn = tk.Button(root, text="听歌识曲", command=self.recognize_song, 
                                   bg='purple', fg='white', font=('Arial', 12))
        self.shazam_btn.pack(pady=5)
        
        # 快捷键设置区域
        self.shortcut_frame = tk.Frame(root)
        self.shortcut_frame.pack(pady=5)
        
        self.shortcut_label = tk.Label(self.shortcut_frame, text="重新识别快捷键:", font=("Arial", 10))
        self.shortcut_label.pack(side=tk.LEFT, padx=5)
        
        self.current_shortcut = "F1"  # 默认快捷键
        self.shortcut_entry = tk.Entry(self.shortcut_frame, width=10, font=("Arial", 10))
        self.shortcut_entry.insert(0, self.current_shortcut)
        self.shortcut_entry.pack(side=tk.LEFT, padx=5)
        
        self.set_shortcut_btn = tk.Button(self.shortcut_frame, text="设置", command=self.set_shortcut, font=("Arial", 10))
        self.set_shortcut_btn.pack(side=tk.LEFT, padx=5)
        
        self.shortcut_hint = tk.Label(root, text="设置后按快捷键可触发重新识别（窗口失去焦点也有效）", font=("Arial", 8), fg="gray")
        self.shortcut_hint.pack(pady=2)
        
        # 状态标签
        self.status_label = tk.Label(root, text="就绪", font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # 快捷键相关变量
        self.hotkey_handle = None  # 保存快捷键注册句柄
        
        # 注册全局快捷键
        self.register_global_shortcut()
        
        # 区域选择相关变量
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.selecting = False
        self.select_window = None
        self.canvas = None
        self.border_window = None
        self.button_window = None
        self.current_region = None
        
        # 翻译区域相关变量
        self.translate_start_x = 0
        self.translate_start_y = 0
        self.translate_end_x = 0
        self.translate_end_y = 0
        self.translate_selecting = False
        self.translate_select_window = None
        self.translate_canvas = None
        self.translate_window = None
        self.translate_button_window = None
        self.current_translate_region = None
        
        # AI交互控制变量
        self.ai_interaction_active = False
        self.current_request = None
        # 翻译线程控制
        self.translating = False
        
        # 听歌识曲相关变量
        self.shazam_recognizing = False
        
        # 窗口拖动和拉伸相关变量
        self.dragging = False
        self.resizing = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.resize_edge = None
        self.border_window_dragging = False
        self.border_window_resizing = False
        self.border_drag_start_x = 0
        self.border_drag_start_y = 0
        self.border_resize_start_x = 0
        self.border_resize_start_y = 0
        self.border_resize_edge = None
        
        # 自动调整窗口大小以适应所有界面元素
        self.root.update()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        self.root.geometry(f"{width+20}x{height+20}+100+100")  # 增加一些边距
        logger.debug(f"自动调整窗口大小为: {width+20}x{height+20}")
        
        # 缓存变量，用于存储识别和翻译结果
        self.ocr_cache = {}
        self.translation_cache = {}
    
    def select_translate_area(self):
        """选择翻译区域"""
        try:
            logger.debug("开始选择译文区域")
            self.status_label.config(text="请选择译文区域...")
            self.root.update()
            
            # 创建全屏半透明窗口用于选择区域
            self.translate_select_window = tk.Toplevel(self.root)
            self.translate_select_window.attributes('-fullscreen', True)
            self.translate_select_window.attributes('-alpha', 0.3)
            self.translate_select_window.attributes('-topmost', True)
            self.translate_select_window.configure(bg='black')
            
            # 创建画布用于绘制选择框
            self.translate_canvas = tk.Canvas(self.translate_select_window, cursor='cross', bg='black', highlightthickness=0)
            self.translate_canvas.pack(fill=tk.BOTH, expand=True)
            
            # 绑定鼠标事件
            self.translate_canvas.bind('<Button-1>', self.on_translate_mouse_down)
            self.translate_canvas.bind('<B1-Motion>', self.on_translate_mouse_drag)
            self.translate_canvas.bind('<ButtonRelease-1>', self.on_translate_mouse_up)
            # 绑定ESC键退出
            self.translate_canvas.bind('<Escape>', self.on_escape)
            
        except Exception as e:
            self.status_label.config(text=f"错误: {str(e)}")
            logger.error(f"选择译文区域失败: {str(e)}")
    
    def on_translate_mouse_down(self, event):
        """翻译区域选择鼠标按下事件"""
        self.translate_start_x = event.x
        self.translate_start_y = event.y
        self.translate_selecting = True
    
    def on_translate_mouse_drag(self, event):
        """翻译区域选择鼠标拖动事件"""
        if self.translate_selecting:
            self.translate_canvas.delete('selection')
            self.translate_canvas.create_rectangle(
                self.translate_start_x, self.translate_start_y, event.x, event.y,
                outline='white', width=2, tags='selection'
            )
    
    def on_translate_mouse_up(self, event):
        """翻译区域选择鼠标释放事件"""
        self.translate_end_x = event.x
        self.translate_end_y = event.y
        self.translate_selecting = False
        
        # 确保坐标顺序正确
        x1 = min(self.translate_start_x, self.translate_end_x)
        y1 = min(self.translate_start_y, self.translate_end_y)
        x2 = max(self.translate_start_x, self.translate_end_x)
        y2 = max(self.translate_start_y, self.translate_end_y)
        
        # 计算选择区域的宽度和高度
        width = x2 - x1
        height = y2 - y1
        
        # 关闭选择窗口
        self.translate_select_window.destroy()
        
        # 如果选择区域太小，提示用户
        if width < 100 or height < 50:
            self.status_label.config(text="选择区域太小，请重新选择")
            return
        
        # 保存当前选择的翻译区域
        self.current_translate_region = (x1, y1, width, height)
        logger.debug(f"选择译文区域完成: x={x1}, y={y1}, width={width}, height={height}")
        
        # 创建翻译显示窗口
        self.create_translate_window(x1, y1, width, height)
        
        # 启用识别区域按钮
        self.select_recognize_area_btn.config(state=tk.NORMAL)
        self.status_label.config(text="译文区域创建完成")
    
    def create_translate_window(self, x, y, width, height):
        """创建翻译显示窗口"""
        # 关闭之前的窗口（如果存在）
        if self.translate_window:
            self.translate_window.destroy()
        if hasattr(self, 'translate_button_window') and self.translate_button_window:
            self.translate_button_window.destroy()
        
        # 创建翻译显示窗口
        self.translate_window = tk.Toplevel(self.root)
        self.translate_window.geometry(f"{width}x{height}+{x}+{y}")
        self.translate_window.overrideredirect(True)  # 无标题栏
        self.translate_window.attributes('-topmost', True)
        self.translate_window.attributes('-alpha', 0.9)
        
        # 绑定鼠标事件
        self.translate_window.bind('<Button-1>', self.translate_window_mouse_down)
        self.translate_window.bind('<B1-Motion>', self.translate_window_mouse_move)
        self.translate_window.bind('<ButtonRelease-1>', self.translate_window_mouse_up)
        self.translate_window.bind('<Leave>', self.translate_window_mouse_leave)
        
        # 创建主框架
        main_frame = tk.Frame(self.translate_window, bg='black')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建标签用于显示翻译内容
        self.translate_text_widget = tk.Label(main_frame, 
                                           font=("Arial", 12), 
                                           fg='white', 
                                           bg='black',
                                           wraplength=width-40,
                                           justify=tk.LEFT,
                                           anchor=tk.NW)
        self.translate_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建状态标签
        self.translate_status_label = tk.Label(main_frame, text="就绪", font=("Arial", 8), fg='white', bg='black')
        self.translate_status_label.pack(side=tk.BOTTOM, padx=10, pady=5)
        
        # 创建发音按钮窗口，放在翻译窗口上方
        button_width = 100
        button_height = 40
        margin = 50
        
        button_x = x + width - button_width
        button_y = y - button_height - 5
        
        screen_height = self.root.winfo_screenheight()
        if button_y < margin:
            button_y = y + height + 5
            if button_y + button_height > screen_height - margin:
                button_y = y + margin
                button_x = x + width - button_width - margin
        
        self.translate_button_window = tk.Toplevel(self.root)
        self.translate_button_window.geometry(f"{button_width}x{button_height}+{button_x}+{button_y}")
        self.translate_button_window.overrideredirect(True)
        self.translate_button_window.attributes('-topmost', True)
        self.translate_button_window.attributes('-alpha', 1.0)
        
        button_frame = tk.Frame(self.translate_button_window, bg='cyan', bd=3, relief=tk.RAISED)
        button_frame.pack(fill=tk.BOTH, expand=True)
        
        speak_btn = tk.Button(button_frame, text="发音", command=self.speak_original_text, 
                             bg='deepskyblue', fg='black', font=("Arial", 10, "bold"), padx=5, pady=4)
        speak_btn.pack(side=tk.LEFT, padx=3, pady=3, fill=tk.BOTH, expand=True)
    
    def select_area(self):
        """选择识别区域"""
        try:
            logger.debug("开始选择识别区域")
            self.status_label.config(text="请选择识别区域...")
            self.root.update()
            
            # 创建全屏半透明窗口用于选择区域
            self.select_window = tk.Toplevel(self.root)
            self.select_window.attributes('-fullscreen', True)
            self.select_window.attributes('-alpha', 0.3)
            self.select_window.attributes('-topmost', True)
            self.select_window.configure(bg='black')
            
            # 创建画布用于绘制选择框
            self.canvas = tk.Canvas(self.select_window, cursor='cross', bg='black', highlightthickness=0)
            self.canvas.pack(fill=tk.BOTH, expand=True)
            
            # 绑定鼠标事件
            self.canvas.bind('<Button-1>', self.on_mouse_down)
            self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
            # 绑定ESC键退出
            self.canvas.bind('<Escape>', self.on_escape)
            
        except Exception as e:
            self.status_label.config(text=f"错误: {str(e)}")
            logger.error(f"选择识别区域失败: {str(e)}")
    
    def on_mouse_down(self, event):
        # 记录起始坐标
        self.start_x = event.x
        self.start_y = event.y
        self.selecting = True
    
    def on_mouse_drag(self, event):
        # 绘制选择框
        if self.selecting:
            self.canvas.delete('selection')
            self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline='white', width=2, tags='selection'
            )
    
    def on_mouse_up(self, event):
        # 记录结束坐标并关闭选择窗口
        self.end_x = event.x
        self.end_y = event.y
        self.selecting = False
        
        # 确保坐标顺序正确
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)
        
        # 计算选择区域的宽度和高度
        width = x2 - x1
        height = y2 - y1
        
        # 关闭选择窗口
        self.select_window.destroy()
        
        # 如果选择区域太小，提示用户
        if width < 10 or height < 10:
            self.status_label.config(text="选择区域太小，请重新选择")
            return
        
        # 保存当前选择的区域
        self.current_region = (x1, y1, width, height)
        logger.debug(f"选择识别区域完成: x={x1}, y={y1}, width={width}, height={height}")
        
        # 创建边框窗口
        self.create_border_window(x1, y1, width, height)
        
        # 执行第一次识别
        self.recognize_area()
    
    def create_border_window(self, x, y, width, height):
        """创建带有边框和控制按钮的窗口"""
        # 关闭之前的窗口（如果存在）
        if self.border_window:
            self.border_window.destroy()
        if hasattr(self, 'button_window') and self.button_window:
            self.button_window.destroy()
        
        # 创建边框窗口，正好覆盖选择区域
        self.border_window = tk.Toplevel(self.root)
        self.border_window.geometry(f"{width}x{height}+{x}+{y}")
        self.border_window.overrideredirect(True)  # 无标题栏
        self.border_window.attributes('-topmost', True)
        self.border_window.attributes('-alpha', 0.1)  # 降低透明度，使蒙版效果更自然
        
        # 绑定鼠标事件
        self.border_window.bind('<Button-1>', self.border_window_mouse_down)
        self.border_window.bind('<B1-Motion>', self.border_window_mouse_move)
        self.border_window.bind('<ButtonRelease-1>', self.border_window_mouse_up)
        self.border_window.bind('<Leave>', self.border_window_mouse_leave)
        
        # 创建画布用于绘制边框
        canvas = tk.Canvas(self.border_window, width=width, height=height, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绘制边框
        canvas.create_rectangle(0, 0, width, height, outline='red', width=2)
        
        # 创建控制按钮窗口，放在选择框右上角外侧
        button_width = 100
        button_height = 40
        margin = 50  # 边界边距
        
        # 使用识别区域的实际像素坐标，不依赖屏幕尺寸检测
        # 默认放在识别区域上方偏右
        button_x = x + width - button_width
        button_y = y - button_height - 5
        
        # 获取屏幕高度用于边界检查
        screen_height = self.root.winfo_screenheight()
        
        # 如果上方空间不够，尝试放在下方
        if button_y < margin:
            button_y = y + height + 5
            # 如果下方空间也不够，就放在识别区域内顶部
            if button_y + button_height > screen_height - margin:
                button_y = y + margin
                button_x = x + width - button_width - margin
        
        self.button_window = tk.Toplevel(self.root)
        self.button_window.geometry(f"{button_width}x{button_height}+{button_x}+{button_y}")
        self.button_window.overrideredirect(True)  # 无标题栏
        self.button_window.attributes('-topmost', True)
        self.button_window.attributes('-alpha', 1.0)  # 完全不透明，确保按钮清晰可见
        
        # 创建按钮框架
        button_frame = tk.Frame(self.button_window, bg='yellow', bd=3, relief=tk.RAISED)
        button_frame.pack(fill=tk.BOTH, expand=True)
        
        # 重新识别按钮
        recognize_btn = tk.Button(button_frame, text="重新识别", command=self.recognize_area, 
                               bg='lime', fg='black', font=("Arial", 10, "bold"), padx=5, pady=4)
        recognize_btn.pack(side=tk.LEFT, padx=3, pady=3, fill=tk.BOTH, expand=True)
        
        # 启用主界面的中止和关闭按钮
        self.abort_btn.config(state=tk.NORMAL)
        self.close_btn.config(state=tk.NORMAL)
    
    def recognize_area(self):
        """识别选定区域的文字"""
        if not self.current_region:
            self.status_label.config(text="未选择区域")
            return
        
        # 检查是否已有正在进行的识别，防止重复点击
        if self.ai_interaction_active:
            logger.info("已有识别任务进行中，忽略重复点击")
            return
        
        # 启动线程处理AI交互
        def recognize_thread():
            # 在启动时保存截图，避免在线程中使用后可能被回收
            screenshot_local = None
            
            try:
                # 设置AI交互标志
                self.ai_interaction_active = True
                logger.info("开始识别区域文字")
                
                # 截取选定区域
                x, y, width, height = self.current_region
                logger.info(f"截取区域: x={x}, y={y}, width={width}, height={height}")
                screenshot_local = pyautogui.screenshot(region=(x, y, width, height))
                logger.info("截图完成")
                
                # 先在主线程中更新UI显示识别中状态
                buffered = io.BytesIO()
                screenshot_local.save(buffered, format="JPEG", quality=75)
                image_size_kb = len(buffered.getvalue()) / 1024
                
                # 使用线程安全的方式更新UI
                def update_ui_recognizing():
                    self.status_label.config(text="正在识别...")
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="识别中...")
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"正在识别. . .(图像大小 {image_size_kb:.1f} kb)")
                self.root.after(0, update_ui_recognizing)
                
                # 使用time.sleep代替root.after，避免在非主线程调用tk方法
                import time
                time.sleep(0.5)
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 压缩图片
                compressed_image = self.compress_image(screenshot_local)
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 使用通义千问AI进行OCR识别和翻译
                logger.info("使用通义千问AI进行OCR识别和翻译")
                text, translated_text = self.recognize_with_qwen(compressed_image)
                logger.info(f"识别完成，结果长度: {len(text)}")
                logger.info(f"翻译完成，结果长度: {len(translated_text)}")
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 更新UI
                def update_ui_completed():
                    cleanup_cosyvoice_wav()
                    self.status_label.config(text="翻译完成")
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="翻译完成")
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"{translated_text if translated_text else '翻译失败'}\n\n原文: {text}")
                self.root.after(0, update_ui_completed)
            except Exception as e:
                # 更新UI
                error_msg = str(e)
                def update_ui_error():
                    self.status_label.config(text=f"错误: {error_msg}")
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text=f"识别失败: {error_msg}")
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"识别失败: {error_msg}")
                self.root.after(0, update_ui_error)
                logger.error(f"识别过程出错: {error_msg}")
            finally:
                # 重置AI交互标志
                self.ai_interaction_active = False
        
        # 启动线程
        thread = threading.Thread(target=recognize_thread)
        thread.daemon = True
        thread.start()
    
    def translate_text(self, text):
        """翻译识别结果"""
        if not text or text == "未识别到文本":
            # 更新翻译窗口状态
            if hasattr(self, 'translate_status_label'):
                self.translate_status_label.config(text="没有可翻译的文本")
            # 更新翻译窗口文本
            if hasattr(self, 'translate_text_widget'):
                self.translate_text_widget.config(text="没有可翻译的文本")
            return
        
        # 启动线程处理AI交互
        def translate_thread():
            try:
                # 设置翻译状态标志
                self.translating = True
                logger.debug("开始翻译文本")
                
                # 更新UI
                def update_ui_translating():
                    self.status_label.config(text="正在翻译...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="翻译中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"正在翻译. . .({text[:50]}...")
                    self.root.update()
                
                self.root.after(0, update_ui_translating)
                
                # 使用通义千问AI进行翻译
                logger.debug("使用通义千问AI进行翻译")
                translated_text = self.translate_with_qwen(text)
                logger.debug(f"翻译完成，结果: {translated_text[:100]}..." if len(translated_text) > 100 else f"翻译完成，结果: {translated_text}")
                
                # 检查是否已中止
                if not self.translating:
                    return
                
                # 更新UI
                def update_ui_translated():
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="翻译完成")
                    
                    # 自动更新翻译窗口内容
                    if hasattr(self, 'translate_window') and self.translate_window:
                        # 分两行显示，第一行是翻译内容，第二行是原文
                        if hasattr(self, 'translate_text_widget'):
                            self.translate_text_widget.config(text=f"{translated_text if translated_text else '翻译失败'}\n\n原文: {text}")
                        self.translate_status_label.config(text="翻译完成")
                
                self.root.after(0, update_ui_translated)
            except Exception as e:
                # 更新UI
                def update_ui_error(e):
                    self.status_label.config(text=f"翻译错误: {str(e)}")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text=f"翻译失败: {str(e)}")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"翻译失败: {str(e)}")
                
                self.root.after(0, lambda e=e: update_ui_error(e))
                logger.error(f"翻译过程出错: {str(e)}")
            finally:
                # 重置翻译状态
                self.translating = False
        
        # 启动线程
        thread = threading.Thread(target=translate_thread)
        thread.daemon = True
        thread.start()
    
    def compress_image(self, image, quality=50):
        """压缩图片"""
        # 增加对比度
        logger.debug("增加图像对比度")
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(2.0)
        
        # 将图片转换为灰度图
        logger.debug("将图片转换为灰度图")
        if enhanced_image.mode != 'L':
            # 转换为灰度图
            enhanced_image = ImageOps.grayscale(enhanced_image)
        
        # 将图片保存到内存中进行压缩
        logger.debug(f"压缩图片，质量: {quality}")
        buffered = io.BytesIO()
        # JPEG格式不支持P模式，需要转换为RGB模式
        if enhanced_image.mode == 'P':
            enhanced_image = enhanced_image.convert('RGB')
        enhanced_image.save(buffered, format="JPEG", quality=quality)
        
        # 重新读取压缩后的图片
        compressed = Image.open(buffered)
        return compressed
    
    def recognize_with_qwen(self, image):
        """使用通义千问AI进行OCR识别和翻译"""
        logger.info("开始通义千问AI图像识别和翻译")
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")

        # 检查API客户端
        global qwen_client
        if qwen_client is None:
            raise Exception("通义千问AI客户端未初始化，请检查key.txt文件中的API密钥")

        # 将图像转换为base64编码
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")

        # 发送请求，带智能重试机制
        max_retries = 5  # 增加重试次数
        base_delay = 3  # 基础延迟时间（秒）

        for attempt in range(max_retries):
            try:
                logger.info(f"发送OCR和翻译请求到通义千问AI (尝试 {attempt + 1}/{max_retries})")

                response = qwen_client.chat.completions.create(
                    model="qwen3.6-flash",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_str}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "请识别图片中的所有文字，保持原始格式和顺序，然后将识别结果翻译成中文。返回格式为：\n识别结果：[识别的原文]\n翻译结果：[翻译后的中文]"
                                }
                            ]
                        }
                    ]
                )

                # 检查是否已中止
                if not self.ai_interaction_active:
                    raise Exception("AI交互已中止")

                result = response.choices[0].message.content
                logger.info("通义千问AI处理完成")

                # 解析结果
                recognized_text = ""
                translated_text = ""
                current_section = None
                
                lines = result.split('\n')
                for line in lines:
                    line_stripped = line.strip()
                    if '识别结果：' in line_stripped:
                        # 找到冒号位置，提取后面的内容
                        colon_pos = line_stripped.find('：')
                        if colon_pos != -1:
                            recognized_text = line_stripped[colon_pos+1:].strip()
                            current_section = 'recognized'
                    elif '翻译结果：' in line_stripped:
                        # 找到冒号位置，提取后面的内容
                        colon_pos = line_stripped.find('：')
                        if colon_pos != -1:
                            translated_text = line_stripped[colon_pos+1:].strip()
                            current_section = 'translated'
                    elif current_section == 'recognized' and line_stripped:
                        # 如果在识别结果段落中且该行不为空，追加内容
                        recognized_text += '\n' + line_stripped
                    elif current_section == 'translated' and line_stripped:
                        # 如果在翻译结果段落中且该行不为空，追加内容
                        translated_text += '\n' + line_stripped

                # 保存到缓存
                cache_key = img_str[:100]  # 使用图像的前100个字符作为缓存键
                self.ocr_cache[cache_key] = recognized_text
                self.translation_cache[cache_key] = translated_text
                logger.debug(f"保存识别和翻译结果到缓存，缓存键: {cache_key}")

                return recognized_text, translated_text

            except Exception as e:
                error_str = str(e)
                logger.warning(f"请求错误 (尝试 {attempt + 1}/{max_retries}): {error_str}")

                # 检查是否已中止
                if not self.ai_interaction_active:
                    raise Exception("AI交互已中止")

                # 特殊处理429错误
                if "429" in error_str or "Too Many Requests" in error_str:
                    if attempt < max_retries - 1:
                        # 计算退避时间（指数退避 + 随机抖动）
                        import time
                        import random
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"遇到429错误，等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception("请求过于频繁，请等待几分钟后再试")

                # 其他错误的处理
                if attempt < max_retries - 1:
                    import time
                    time.sleep(base_delay)
                    continue
                else:
                    if "401" in error_str or "Unauthorized" in error_str:
                        raise Exception("API密钥无效或已过期，请检查key.txt文件中的API密钥")
                    elif "413" in error_str or "Payload Too Large" in error_str:
                        raise Exception("请求体过大，请选择更小的识别区域")
                    else:
                        raise Exception(f"通义千问AI请求失败: {error_str}")
    
    def translate_with_qwen(self, text):
        """从缓存中读取翻译结果"""
        logger.debug("从缓存中读取翻译结果")
        # 检查是否已中止
        if not self.translating:
            raise Exception("翻译已中止")
        
        # 遍历缓存，查找匹配的识别文本
        for cache_key, cached_text in self.ocr_cache.items():
            if cached_text == text:
                # 找到匹配的缓存项
                translated_text = self.translation_cache.get(cache_key, "")
                logger.debug(f"从缓存中找到翻译结果: {translated_text[:100]}..." if len(translated_text) > 100 else f"从缓存中找到翻译结果: {translated_text}")
                return translated_text
        
        # 如果没有找到缓存，返回空字符串
        logger.warning("未找到缓存的翻译结果")
        return ""
    
    def border_window_mouse_down(self, event):
        """识别窗口鼠标按下事件"""
        # 检查是否在窗口边缘（用于拉伸）
        edge = self.get_window_edge(self.border_window, event.x, event.y)
        if edge:
            self.border_window_resizing = True
            self.border_resize_edge = edge
            self.border_resize_start_x = event.x
            self.border_resize_start_y = event.y
        else:
            # 否则开始拖动
            self.border_window_dragging = True
            self.border_drag_start_x = event.x
            self.border_drag_start_y = event.y
    
    def border_window_mouse_move(self, event):
        """识别窗口鼠标移动事件"""
        if self.border_window_resizing:
            # 执行拉伸
            self.resize_border_window(event.x, event.y, self.border_resize_edge)
        elif self.border_window_dragging:
            # 执行拖动
            self.move_border_window(event.x - self.border_drag_start_x, event.y - self.border_drag_start_y)
        else:
            # 检查鼠标是否在窗口边缘，更改光标
            edge = self.get_window_edge(self.border_window, event.x, event.y)
            if edge:
                cursor = self.get_cursor_for_edge(edge)
            else:
                # 鼠标在窗口内部，显示十字箭头光标
                cursor = "fleur"
            self.border_window.config(cursor=cursor)
    
    def border_window_mouse_up(self, event):
        """识别窗口鼠标释放事件"""
        self.border_window_dragging = False
        self.border_window_resizing = False
        self.border_resize_edge = None
    
    def border_window_mouse_leave(self, event):
        """识别窗口鼠标离开事件"""
        self.border_window.config(cursor="arrow")
    
    def move_border_window(self, delta_x, delta_y):
        """移动识别窗口"""
        if not self.border_window:
            return
        
        x = self.border_window.winfo_x() + delta_x
        y = self.border_window.winfo_y() + delta_y
        width = self.border_window.winfo_width()
        height = self.border_window.winfo_height()
        
        # 更新窗口位置
        self.border_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # 更新按钮窗口位置，保持在识别区域上方或下方
        if self.button_window:
            button_width = 100
            button_height = 40
            margin = 50
            
            button_x = x + width - button_width
            button_y = y - button_height - 5
            
            screen_height = self.root.winfo_screenheight()
            
            # 如果上方空间不够，尝试放在下方
            if button_y < margin:
                button_y = y + height + 5
                # 如果下方空间也不够，就放在识别区域内顶部
                if button_y + button_height > screen_height - margin:
                    button_y = y + margin
                    button_x = x + width - button_width - margin
            
            self.button_window.geometry(f"{button_width}x{button_height}+{button_x}+{button_y}")
        
        # 更新当前区域
        if self.current_region:
            self.current_region = (x, y, width, height)
    
    def resize_border_window(self, x, y, edge):
        """调整识别窗口大小"""
        if not self.border_window:
            return
        
        width = self.border_window.winfo_width()
        height = self.border_window.winfo_height()
        window_x = self.border_window.winfo_x()
        window_y = self.border_window.winfo_y()
        
        delta_x = x - self.border_resize_start_x
        delta_y = y - self.border_resize_start_y
        
        # 降低缩放灵敏度
        sensitivity = 0.1
        delta_x = int(delta_x * sensitivity)
        delta_y = int(delta_y * sensitivity)
        
        new_width = width
        new_height = height
        new_x = window_x
        new_y = window_y
        
        if edge in ["e", "se", "ne"]:
            new_width = max(50, width + delta_x)
        if edge in ["s", "se", "sw"]:
            new_height = max(20, height + delta_y)
        if edge in ["w", "sw", "nw"]:
            new_width = max(50, width - delta_x)
            new_x = window_x + delta_x
        if edge in ["n", "nw", "ne"]:
            new_height = max(20, height - delta_y)
            new_y = window_y + delta_y
        
        # 更新窗口大小和位置
        self.border_window.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
        
        # 更新按钮窗口位置
        if self.button_window:
            button_width = 100
            button_height = 40
            margin = 50
            
            button_x = new_x + new_width - button_width
            button_y = new_y - button_height - 5
            
            screen_height = self.root.winfo_screenheight()
            
            # 如果上方空间不够，尝试放在下方
            if button_y < margin:
                button_y = new_y + new_height + 5
                # 如果下方空间也不够，就放在识别区域内顶部
                if button_y + button_height > screen_height - margin:
                    button_y = new_y + margin
                    button_x = new_x + new_width - button_width - margin
            
            self.button_window.geometry(f"{button_width}x{button_height}+{button_x}+{button_y}")
        
        # 更新当前区域
        self.current_region = (new_x, new_y, new_width, new_height)
    
    def close_border(self):
        """关闭边框窗口和按钮窗口，同时关闭译文窗口"""
        # 先中止AI交互
        self.abort_ai_interaction()
        
        # 关闭识别窗口和按钮窗口
        if self.border_window:
            self.border_window.destroy()
            self.border_window = None
        if hasattr(self, 'button_window') and self.button_window:
            self.button_window.destroy()
            self.button_window = None
        self.current_region = None
        
        # 关闭译文窗口和发音按钮窗口
        if hasattr(self, 'translate_window') and self.translate_window:
            self.translate_window.destroy()
            self.translate_window = None
        if hasattr(self, 'translate_button_window') and self.translate_button_window:
            self.translate_button_window.destroy()
            self.translate_button_window = None
        self.current_translate_region = None
        
        # 禁用识别区域按钮
        self.select_recognize_area_btn.config(state=tk.DISABLED)
        
        # 禁用主界面的中止和关闭按钮
        self.abort_btn.config(state=tk.DISABLED)
        self.close_btn.config(state=tk.DISABLED)
        
        self.status_label.config(text="所有窗口已关闭")
    
    def speak_original_text(self):
        """将原文部分合成语音"""
        if not hasattr(self, 'translate_text_widget'):
            logger.warning("翻译窗口未创建，无法发音")
            return
        
        text = self.translate_text_widget.cget("text")
        if not text or text == "就绪" or "识别中" in text:
            logger.info("无有效文本可发音")
            return
        
        # 如果正在合成中，忽略重复点击
        if self.synthesizing:
            logger.info("正在合成中，忽略重复点击")
            return
        
        # 停止当前播放
        if self.playing and self.play_stop_event:
            self.play_stop_event.set()
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=0.5)
        
        # 提取原文部分（格式为：翻译文本\n\n原文: 原始文本）
        original_text = text
        if "原文:" in text:
            original_text = text.split("原文:")[-1].strip()
        
        # 如果文件已存在，直接播放
        if os.path.exists(COSYVOICE_WAV_FILE):
            # 如果是新音频，重置速度模式
            if self.is_new_audio:
                self.speed_mode = 0
                self.is_new_audio = False
            
            # 计算当前速度
            speed = 1.0 if self.speed_mode == 0 else 0.75
            speed_text = "正常速度" if self.speed_mode == 0 else "0.75倍速"
            
            # 切换速度模式
            self.speed_mode = (self.speed_mode + 1) % 2
            
            logger.info(f"音频文件已存在，停止当前播放并以{speed_text}重新播放")
            
            # 更新UI显示速度
            def update_ui_speed():
                if hasattr(self, 'translate_status_label'):
                    self.translate_status_label.config(text=f"正在播放({speed_text})...")
            self.root.after(0, update_ui_speed)
            
            self.play_stop_event = threading.Event()
            self.playing = True
            self.play_thread = threading.Thread(target=self._play_audio, args=(self.play_stop_event, speed), daemon=True)
            self.play_thread.start()
            return
        
        # 否则进行语音合成
        def synthesize_thread():
            try:
                logger.info("开始语音合成")
                self.synthesizing = True
                
                # 更新UI状态
                def update_ui_start():
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="正在合成语音...")
                self.root.after(0, update_ui_start)
                
                # 调用语音合成API
                stream_result = HttpSpeechSynthesizer.call(
                    model="cosyvoice-v3-flash",
                    text=original_text[:500],  # 限制文本长度
                    voice="longanhuan",
                    format="wav",
                    sample_rate=24000,
                    stream=True,
                    api_key=api_key,
                )
                
                # 收集音频数据
                audio_chunks = []
                for chunk in stream_result:
                    if not chunk.audio_url and chunk.audio_data:
                        audio_chunks.append(chunk.audio_data)
                
                # 保存音频文件
                full_audio = b"".join(audio_chunks)
                with open(COSYVOICE_WAV_FILE, "wb") as f:
                    f.write(full_audio)
                
                logger.info(f"语音合成完成，文件已保存: {COSYVOICE_WAV_FILE}")
                self.synthesizing = False
                
                # 标记为新音频，重置速度模式
                self.is_new_audio = True
                self.speed_mode = 0
                
                # 播放音频
                def update_ui_done():
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="语音合成完成，正在播放(正常速度)...")
                self.root.after(0, update_ui_done)
                
                self.play_stop_event = threading.Event()
                self.playing = True
                self._play_audio(self.play_stop_event, 1.0)
                
            except Exception as e:
                logger.error(f"语音合成失败: {e}")
                self.synthesizing = False
                def update_ui_error():
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text=f"语音合成失败: {str(e)}")
                self.root.after(0, update_ui_error)
        
        threading.Thread(target=synthesize_thread, daemon=True).start()
    
    def _play_audio(self, stop_event, speed=1.0):
        """播放音频并在播放完成后更新UI"""
        try:
            play_cosyvoice_wav(stop_event, speed)
        finally:
            self.playing = False
            if not stop_event.is_set():
                def update_ui_restore():
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="翻译完成")
                self.root.after(0, update_ui_restore)
    
    def translate_window_mouse_down(self, event):
        """翻译窗口鼠标按下事件"""
        # 检查是否在窗口边缘（用于拉伸）
        edge = self.get_window_edge(self.translate_window, event.x, event.y)
        if edge:
            self.resizing = True
            self.resize_edge = edge
            self.resize_start_x = event.x
            self.resize_start_y = event.y
        else:
            # 否则开始拖动
            self.dragging = True
            self.drag_start_x = event.x
            self.drag_start_y = event.y
    
    def translate_window_mouse_move(self, event):
        """翻译窗口鼠标移动事件"""
        if self.resizing:
            self.resize_window(self.translate_window, event.x, event.y, self.resize_edge)
        elif self.dragging:
            self.move_window(self.translate_window, event.x - self.drag_start_x, event.y - self.drag_start_y)
            if hasattr(self, 'translate_button_window') and self.translate_button_window:
                self.move_window(self.translate_button_window, event.x - self.drag_start_x, event.y - self.drag_start_y)
        else:
            edge = self.get_window_edge(self.translate_window, event.x, event.y)
            if edge:
                cursor = self.get_cursor_for_edge(edge)
            else:
                cursor = "fleur"
            self.translate_window.config(cursor=cursor)
    
    def translate_window_mouse_up(self, event):
        """翻译窗口鼠标释放事件"""
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
    
    def translate_window_mouse_leave(self, event):
        """翻译窗口鼠标离开事件"""
        self.translate_window.config(cursor="arrow")
    
    def get_window_edge(self, window, x, y):
        """获取窗口边缘"""
        width = window.winfo_width()
        height = window.winfo_height()
        edge_threshold = 10
        
        if x < edge_threshold and y < edge_threshold:
            return "nw"
        elif x < edge_threshold and y > height - edge_threshold:
            return "sw"
        elif x > width - edge_threshold and y < edge_threshold:
            return "ne"
        elif x > width - edge_threshold and y > height - edge_threshold:
            return "se"
        elif x < edge_threshold:
            return "w"
        elif x > width - edge_threshold:
            return "e"
        elif y < edge_threshold:
            return "n"
        elif y > height - edge_threshold:
            return "s"
        return None
    
    def get_cursor_for_edge(self, edge):
        """获取边缘对应的光标"""
        cursor_map = {
            "nw": "size_nw_se",
            "sw": "size_sw_ne",
            "ne": "size_ne_sw",
            "se": "size_se_nw",
            "w": "size_we",
            "e": "size_we",
            "n": "size_ns",
            "s": "size_ns"
        }
        return cursor_map.get(edge, "arrow")
    
    def move_window(self, window, delta_x, delta_y):
        """移动窗口"""
        x = window.winfo_x() + delta_x
        y = window.winfo_y() + delta_y
        window.geometry(f"+{x}+{y}")
    
    def resize_window(self, window, x, y, edge):
        """调整窗口大小"""
        width = window.winfo_width()
        height = window.winfo_height()
        window_x = window.winfo_x()
        window_y = window.winfo_y()
        
        delta_x = x - self.resize_start_x
        delta_y = y - self.resize_start_y
        
        # 降低缩放灵敏度
        sensitivity = 0.1
        delta_x = int(delta_x * sensitivity)
        delta_y = int(delta_y * sensitivity)
        
        new_width = width
        new_height = height
        new_x = window_x
        new_y = window_y
        
        if edge in ["e", "se", "ne"]:
            new_width = max(100, width + delta_x)
        if edge in ["s", "se", "sw"]:
            new_height = max(50, height + delta_y)
        if edge in ["w", "sw", "nw"]:
            new_width = max(100, width - delta_x)
            new_x = window_x + delta_x
        if edge in ["n", "nw", "ne"]:
            new_height = max(50, height - delta_y)
            new_y = window_y + delta_y
        
        window.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
        
        # 更新文本框的wraplength
        if hasattr(self, 'translate_text_widget'):
            self.translate_text_widget.config(wraplength=new_width-40)  # 减去边距
            # 强制更新滚动区域
            if hasattr(self, 'translate_window') and self.translate_window:
                self.translate_window.update_idletasks()
                # 触发滚动区域更新
                if window == self.translate_window:
                    # 找到canvas并更新滚动区域
                    for child in window.winfo_children():
                        if isinstance(child, tk.Frame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, tk.Canvas):
                                    grandchild.configure(scrollregion=grandchild.bbox("all"))
                                    break
    
    def abort_ai_interaction(self):
        """中止当前的AI交互"""
        # 中止识别交互
        if self.ai_interaction_active:
            self.ai_interaction_active = False
            # 这里可以添加具体的中止逻辑，例如关闭当前请求
            # 由于requests库不支持直接取消请求，我们使用标志来控制
        
        # 中止翻译交互
        if self.translating:
            self.translating = False
        
        # 更新UI
        self.status_label.config(text="AI交互已中止")
        if hasattr(self, 'translate_status_label'):
            self.translate_status_label.config(text="AI交互已中止")
        if hasattr(self, 'translate_text_widget'):
            self.translate_text_widget.config(text="AI交互已中止")
        self.root.update()
    
    def on_escape(self, event):
        """处理ESC键事件"""
        if self.select_window:
            self.select_window.destroy()
            self.select_window = None
        if self.translate_select_window:
            self.translate_select_window.destroy()
            self.translate_select_window = None
        self.status_label.config(text="选择已取消")
    
    def set_shortcut(self):
        """设置重新识别快捷键"""
        new_shortcut = self.shortcut_entry.get().strip()
        if not new_shortcut:
            self.status_label.config(text="请输入快捷键")
            return
        
        # 尝试取消旧的快捷键注册
        self.unregister_global_shortcut()
        
        # 更新当前快捷键
        self.current_shortcut = new_shortcut
        
        # 注册新的快捷键
        self.register_global_shortcut()
        
        self.status_label.config(text=f"快捷键已设置为: {new_shortcut}")
        logger.info(f"重新识别快捷键已设置为: {new_shortcut}")
    
    def register_global_shortcut(self):
        """注册全局快捷键（窗口失去焦点也有效）"""
        try:
            import keyboard
            # 取消之前的注册
            self.unregister_global_shortcut()
            
            # 注册新的快捷键，保存句柄
            self.hotkey_handle = keyboard.add_hotkey(self.current_shortcut, self.on_shortcut_pressed, suppress=False)
            logger.info(f"全局快捷键 {self.current_shortcut} 注册成功")
        except ImportError:
            logger.warning("未安装 keyboard 库，全局快捷键功能不可用")
            self.status_label.config(text="警告: 需安装 keyboard 库以使用全局快捷键")
        except Exception as e:
            logger.error(f"注册快捷键失败: {str(e)}")
            self.status_label.config(text=f"快捷键注册失败: {str(e)}")
    
    def unregister_global_shortcut(self):
        """取消全局快捷键注册"""
        if self.hotkey_handle is not None:
            try:
                import keyboard
                keyboard.remove_hotkey(self.hotkey_handle)
                self.hotkey_handle = None
            except Exception as e:
                logger.warning(f"取消快捷键注册失败: {str(e)}")
    
    def on_shortcut_pressed(self):
        """快捷键触发时执行重新识别"""
        logger.info(f"快捷键 {self.current_shortcut} 被按下，执行重新识别")
        # 模拟点击重新识别按钮的效果
        if self.current_region:
            self.recognize_area()
        else:
            logger.info("未选择识别区域，快捷键无效")
    
    def record_system_audio(self, duration=8, sample_rate=44100):
        """录制系统音频（环形回录或立体声混音）
        
        Args:
            duration: 录制时长（秒）
            sample_rate: 采样率
            
        Returns:
            临时音频文件路径，如果录制失败返回 None
        """
        result = None
        errors = []
        
        # 方案 1: 使用 soundcard 的环形回录
        if SOUNDCARD_AVAILABLE:
            result, err = self._record_with_soundcard_silent(duration, sample_rate)
            if result:
                print("正在录制系统音频（约 8 秒）...")
                return result
            if err:
                errors.append(f"方案1 (soundcard): {err}")
        
        # 方案 2: 使用 pyaudiowpatch 的 WASAPI 环回（支持蓝牙耳机）
        if PYAUDPATCH_AVAILABLE:
            result, err = self._record_with_pyaudiowpatch_silent(duration)
            if result:
                print("正在录制系统音频（约 8 秒）...")
                return result
            if err:
                errors.append(f"方案2 (pyaudiowpatch): {err}")
        
        # 方案 3: 使用 pyaudio 录制立体声混音
        result, err = self._record_with_pyaudio_silent(duration, sample_rate)
        if result:
            print("正在录制系统音频（约 8 秒）...")
            return result
        if err:
            errors.append(f"方案3 (pyaudio): {err}")
        
        # 所有方案都失败，提供帮助信息
        print("\n" + "=" * 60)
        print("无法录制系统音频")
        print("=" * 60)
        print("可能的原因和解决方案:")
        print("")
        print("方案一: 安装 pyaudiowpatch（推荐，支持蓝牙耳机）")
        print("  pip install pyaudiowpatch")
        print("  这个库专门支持 Windows WASAPI 环回，包括蓝牙耳机")
        print("")
        print("方案二: 确保音频从内置扬声器或有线耳机播放")
        print("  - 部分蓝牙耳机可能不支持系统音频环形回录")
        print("  - 请切换到笔记本内置扬声器或 3.5mm 有线耳机")
        print("")
        print("方案三: 启用 Windows 立体声混音")
        print("  1. 右键点击任务栏音量图标 → '声音设置'")
        print("  2. 点击右侧 '声音控制面板'")
        print("  3. 切换到 '录制' 选项卡")
        print("  4. 右键空白处 → 勾选 '显示禁用的设备'")
        print("  5. 找到 '立体声混音' → 右键 → 启用")
        print("  6. 重启程序后重试")
        print("=" * 60 + "\n")
        
        return None
    
    def _record_with_soundcard_silent(self, duration, sample_rate):
        """使用 soundcard 录制系统音频（静默模式，不向用户输出信息）
        
        Returns:
            (临时音频文件路径或 None, 错误信息或 None)
        """
        try:
            logger.info("[方案1] 正在使用 soundcard 查找系统音频录制设备...")
            
            default_speaker = sc.default_speaker()
            logger.info(f"使用默认扬声器: {default_speaker.name}")
            
            if "蓝牙耳机" in default_speaker.name or "Bluetooth" in default_speaker.name:
                logger.info("检测到蓝牙耳机，soundcard 可能不支持")
                return None, "蓝牙耳机可能不支持 soundcard 环回"
            
            loopback_mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            logger.info(f"成功获取环形回录麦克风: {loopback_mic.name}")
            
            logger.info(f"开始录制系统音频，时长: {duration} 秒")
            
            with loopback_mic.recorder(samplerate=sample_rate, channels=2) as mic:
                audio_data = mic.record(numframes=int(sample_rate * duration))
            
            logger.info("音频录制完成")
            
            audio_data_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
            
            sf.write(str(temp_file), audio_data_int16, sample_rate, subtype='PCM_16')
            logger.info(f"音频已保存到临时文件: {temp_file}")
            
            return temp_file, None
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"[方案1] soundcard 录制失败: {error_str}")
            return None, error_str
    
    def _record_with_soundcard(self, duration, sample_rate):
        """使用 soundcard 录制系统音频（环形回录）
        
        Returns:
            临时音频文件路径，失败返回 None
        """
        try:
            logger.info("[方案1] 正在使用 soundcard 查找系统音频录制设备...")
            
            default_speaker = sc.default_speaker()
            logger.info(f"使用默认扬声器: {default_speaker.name}")
            
            if "蓝牙耳机" in default_speaker.name or "Bluetooth" in default_speaker.name:
                print("注意: 检测到您使用的是蓝牙耳机，环形回录可能不支持")
                print("建议切换到内置扬声器或有线耳机后重试")
            
            loopback_mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
            logger.info(f"成功获取环形回录麦克风: {loopback_mic.name}")
            
            print(f"开始录制系统音频，时长: {duration} 秒...")
            logger.info(f"开始录制系统音频，时长: {duration} 秒")
            
            with loopback_mic.recorder(samplerate=sample_rate, channels=2) as mic:
                audio_data = mic.record(numframes=int(sample_rate * duration))
            
            logger.info("音频录制完成")
            
            audio_data_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
            
            sf.write(str(temp_file), audio_data_int16, sample_rate, subtype='PCM_16')
            logger.info(f"音频已保存到临时文件: {temp_file}")
            logger.info(f"文件大小: {temp_file.stat().st_size} bytes")
            
            return temp_file
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"[方案1] soundcard 录制失败: {error_str}")
            if "0x80070005" in error_str:
                print("[方案1] 环形回录访问被拒绝 (可能是蓝牙耳机不支持)")
            elif "0x8889000A" in error_str:
                print("[方案1] 音频格式不支持")
            else:
                print(f"[方案1] 录制失败: {error_str}")
            return None
    
    def _record_with_pyaudiowpatch_silent(self, duration):
        """使用 pyaudiowpatch 录制系统音频（静默模式，不向用户输出信息）
        
        Returns:
            (临时音频文件路径或 None, 错误信息或 None)
        """
        try:
            logger.info("[方案2] 正在使用 pyaudiowpatch 查找 WASAPI 环回设备...")
            
            CHUNK = 1024
            
            with pyaudio_patch.PyAudio() as p:
                try:
                    wasapi_loopback = p.get_default_wasapi_loopback()
                except OSError as e:
                    logger.error(f"[方案2] 未找到 WASAPI 环回设备: {str(e)}")
                    return None, "未找到 WASAPI 环回设备"
                
                SAMPLE_RATE = int(wasapi_loopback["defaultSampleRate"])
                CHANNELS = wasapi_loopback["maxInputChannels"]
                
                logger.info(f"[方案2] 使用 WASAPI 环回设备: {wasapi_loopback['name']}")
                logger.info(f"[方案2] 开始录制，采样率: {SAMPLE_RATE} Hz, 声道数: {CHANNELS}")
                
                with p.open(format=pyaudio_patch.paInt16,
                            channels=CHANNELS,
                            rate=SAMPLE_RATE,
                            input=True,
                            frames_per_buffer=CHUNK,
                            input_device_index=wasapi_loopback['index']) as stream:
                    
                    frames = []
                    total_frames_to_read = int(SAMPLE_RATE / CHUNK * duration)
                    
                    for _ in range(total_frames_to_read):
                        data = stream.read(CHUNK)
                        frames.append(data)
                
                logger.info("[方案2] 音频录制完成")
                
                temp_dir = tempfile.gettempdir()
                temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
                
                with wave.open(str(temp_file), 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(pyaudio_patch.paInt16))
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(b''.join(frames))
                
                logger.info(f"[方案2] 音频已保存到临时文件: {temp_file}")
                
                return temp_file, None
            
        except Exception as e:
            logger.error(f"[方案2] pyaudiowpatch 录制失败: {str(e)}")
            return None, str(e)
    
    def _record_with_pyaudiowpatch(self, duration):
        """使用 pyaudiowpatch 录制系统音频（WASAPI 环回，支持蓝牙耳机）
        
        Args:
            duration: 录制时长（秒）
            
        Returns:
            临时音频文件路径，失败返回 None
        """
        try:
            logger.info("[方案2] 正在使用 pyaudiowpatch 查找 WASAPI 环回设备...")
            
            CHUNK = 1024
            
            with pyaudio_patch.PyAudio() as p:
                try:
                    wasapi_loopback = p.get_default_wasapi_loopback()
                except OSError as e:
                    logger.error(f"[方案2] 未找到 WASAPI 环回设备: {str(e)}")
                    print("[方案2] 未找到 WASAPI 环回设备，请确保在 Windows 系统上运行")
                    return None
                
                SAMPLE_RATE = int(wasapi_loopback["defaultSampleRate"])
                CHANNELS = wasapi_loopback["maxInputChannels"]
                
                print(f"[方案2] 录音设备: {wasapi_loopback['name']}")
                print(f"[方案2]   -> 默认采样率: {SAMPLE_RATE} Hz")
                print(f"[方案2]   -> 最大声道数: {CHANNELS}")
                logger.info(f"[方案2] 使用 WASAPI 环回设备: {wasapi_loopback['name']}")
                
                print(f"[方案2] 开始录制系统音频，时长: {duration} 秒...")
                logger.info(f"[方案2] 开始录制，采样率: {SAMPLE_RATE} Hz, 声道数: {CHANNELS}")
                
                with p.open(format=pyaudio_patch.paInt16,
                            channels=CHANNELS,
                            rate=SAMPLE_RATE,
                            input=True,
                            frames_per_buffer=CHUNK,
                            input_device_index=wasapi_loopback['index']) as stream:
                    
                    frames = []
                    total_frames_to_read = int(SAMPLE_RATE / CHUNK * duration)
                    
                    for _ in range(total_frames_to_read):
                        data = stream.read(CHUNK)
                        frames.append(data)
                
                logger.info("[方案2] 音频录制完成")
                
                temp_dir = tempfile.gettempdir()
                temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
                
                print(f"[方案2] 正在保存音频文件...")
                
                with wave.open(str(temp_file), 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(pyaudio_patch.paInt16))
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(b''.join(frames))
                
                logger.info(f"[方案2] 音频已保存到临时文件: {temp_file}")
                logger.info(f"[方案2] 文件大小: {temp_file.stat().st_size} bytes")
                
                return temp_file
            
        except Exception as e:
            logger.error(f"[方案2] pyaudiowpatch 录制失败: {str(e)}")
            print(f"[方案2] 录制失败: {str(e)}")
            return None
    
    def _record_with_pyaudio_silent(self, duration, sample_rate):
        """使用 pyaudio 录制系统音频（静默模式，不向用户输出信息）
        
        Returns:
            (临时音频文件路径或 None, 错误信息或 None)
        """
        try:
            logger.info("[方案3] 正在使用 pyaudio 查找立体声混音设备...")
            
            p = pyaudio.PyAudio()
            
            stereo_mix_index = None
            
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                name = info.get('name', '')
                max_input_channels = int(info.get('maxInputChannels', 0))
                
                if max_input_channels > 0:
                    if "立体声混音" in name or "Stereo Mix" in name or "stereo mix" in name:
                        stereo_mix_index = i
                        logger.info(f"找到立体声混音设备: {name}")
            
            if not stereo_mix_index:
                logger.info("[方案3] 未找到立体声混音设备")
                p.terminate()
                return None, "未找到立体声混音设备"
            
            logger.info(f"[方案3] 开始录制，设备索引: {stereo_mix_index}")
            
            device_info = p.get_device_info_by_index(stereo_mix_index)
            channels = min(int(device_info.get('maxInputChannels', 2)), 2)
            
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=stereo_mix_index,
                frames_per_buffer=1024
            )
            
            frames = []
            total_frames = int(sample_rate / 1024 * duration)
            
            for _ in range(total_frames):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            logger.info("[方案3] 音频录制完成")
            
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
            
            wf = wave.open(str(temp_file), 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            logger.info(f"[方案3] 音频已保存到临时文件: {temp_file}")
            
            return temp_file, None
            
        except Exception as e:
            logger.error(f"[方案3] pyaudio 录制失败: {str(e)}")
            try:
                p.terminate()
            except:
                pass
            return None, str(e)
    
    def _record_with_pyaudio(self, duration, sample_rate):
        """使用 pyaudio 录制系统音频（立体声混音）
        
        Returns:
            临时音频文件路径，失败返回 None
        """
        try:
            logger.info("[方案2] 正在使用 pyaudio 查找立体声混音设备...")
            
            p = pyaudio.PyAudio()
            
            stereo_mix_index = None
            available_mics = []
            
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                name = info.get('name', '')
                max_input_channels = int(info.get('maxInputChannels', 0))
                
                if max_input_channels > 0:
                    available_mics.append(f"{i}: {name} (输入通道: {max_input_channels})")
                    
                    if "立体声混音" in name or "Stereo Mix" in name or "stereo mix" in name:
                        stereo_mix_index = i
                        logger.info(f"找到立体声混音设备: {name}")
            
            if not stereo_mix_index:
                print("[方案2] 未找到立体声混音设备")
                print("可用的输入设备:")
                for mic in available_mics:
                    print(f"  {mic}")
                p.terminate()
                return None
            
            print(f"[方案2] 使用立体声混音设备进行录制，时长: {duration} 秒...")
            logger.info(f"[方案2] 开始录制，设备索引: {stereo_mix_index}")
            
            device_info = p.get_device_info_by_index(stereo_mix_index)
            channels = min(int(device_info.get('maxInputChannels', 2)), 2)
            
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=stereo_mix_index,
                frames_per_buffer=1024
            )
            
            frames = []
            total_frames = int(sample_rate / 1024 * duration)
            
            for _ in range(total_frames):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            logger.info("[方案2] 音频录制完成")
            
            temp_dir = tempfile.gettempdir()
            temp_file = Path(temp_dir) / f"shazam_record_{os.getpid()}.wav"
            
            wf = wave.open(str(temp_file), 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            logger.info(f"[方案2] 音频已保存到临时文件: {temp_file}")
            logger.info(f"[方案2] 文件大小: {temp_file.stat().st_size} bytes")
            
            return temp_file
            
        except Exception as e:
            logger.error(f"[方案2] pyaudio 录制失败: {str(e)}")
            print(f"[方案2] 录制失败: {str(e)}")
            try:
                p.terminate()
            except:
                pass
            return None
    
    async def _recognize_with_shazam(self, audio_path: Path):
        """使用 shazamio 识别歌曲（异步函数）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果字典，失败返回 None
        """
        if not SHAZAMIO_AVAILABLE:
            logger.error("shazamio 未安装，无法识别歌曲")
            print("错误: 未安装 shazamio 库")
            print("请运行: pip install shazamio")
            return None
        
        if not audio_path.exists():
            logger.error(f"音频文件不存在: {audio_path}")
            return None
        
        try:
            shazam = Shazam()
            logger.info(f"正在使用 Shazam 识别音频: {audio_path}")
            
            out = await shazam.recognize(audio_path.as_posix())
            
            if not out:
                logger.warning("Shazam 未返回任何结果")
                return None
            
            track = out.get("track")
            if not track:
                logger.warning("未识别到歌曲信息")
                logger.debug(f"完整响应: {out}")
                return None
            
            return track
            
        except Exception as e:
            logger.error(f"Shazam 识别过程中发生错误: {str(e)}")
            print(f"识别过程中发生错误: {str(e)}")
            return None
    
    def _run_shazam_recognition(self):
        """在单独线程中执行听歌识曲流程"""
        try:
            self.shazam_recognizing = True
            
            # 更新 UI
            def update_ui_recognizing():
                self.shazam_btn.config(state=tk.DISABLED, text="识别中...")
                self.status_label.config(text="正在听歌识曲...")
            self.root.after(0, update_ui_recognizing)
            
            print("\n" + "=" * 50)
            print("开始听歌识曲...")
            print("=" * 50)
            
            # 录制系统音频
            print("正在录制系统音频（约 8 秒）...")
            audio_file = self.record_system_audio(duration=8)
            
            if not audio_file:
                print("音频录制失败，无法识别")
                def update_ui_failed():
                    self.shazam_btn.config(state=tk.NORMAL, text="听歌识曲")
                    self.status_label.config(text="音频录制失败")
                self.root.after(0, update_ui_failed)
                return
            
            print(f"音频录制完成，开始识别...")
            
            # 使用 asyncio 运行异步识别
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                track = loop.run_until_complete(self._recognize_with_shazam(audio_file))
            finally:
                try:
                    loop.close()
                except:
                    pass
            
            # 清理临时文件
            try:
                if audio_file.exists():
                    audio_file.unlink()
                    logger.info(f"已删除临时音频文件: {audio_file}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")
            
            # 处理识别结果
            if track:
                title = track.get("title", "未知")
                subtitle = track.get("subtitle", "未知")
                
                print("\n" + "=" * 50)
                print("识别结果:")
                print("=" * 50)
                print(f"歌曲名: {title}")
                print(f"艺术家: {subtitle}")
                
                link = None
                cover = None
                
                if "images" in track:
                    images = track["images"]
                    if "coverart" in images:
                        cover = images['coverart']
                        print(f"封面: {cover}")
                
                if "share" in track:
                    share = track["share"]
                    if "href" in share:
                        link = share['href']
                        print(f"链接: {link}")
                
                print("=" * 50 + "\n")
                
                def update_ui_success():
                    self.shazam_btn.config(state=tk.NORMAL, text="听歌识曲")
                    self.status_label.config(text=f"识别成功: {title} - {subtitle}")
                self.root.after(0, update_ui_success)
            else:
                print("\n" + "=" * 50)
                print("未识别到歌曲")
                print("=" * 50 + "\n")
                
                def update_ui_no_match():
                    self.shazam_btn.config(state=tk.NORMAL, text="听歌识曲")
                    self.status_label.config(text="未识别到歌曲")
                self.root.after(0, update_ui_no_match)
                
        except Exception as e:
            logger.error(f"听歌识曲过程中发生错误: {str(e)}")
            print(f"听歌识曲过程中发生错误: {str(e)}")
            
            def update_ui_error():
                self.shazam_btn.config(state=tk.NORMAL, text="听歌识曲")
                self.status_label.config(text=f"识别错误: {str(e)}")
            self.root.after(0, update_ui_error)
            
        finally:
            self.shazam_recognizing = False
    
    def recognize_song(self):
        """听歌识曲主函数"""
        # 检查依赖
        if not SHAZAMIO_AVAILABLE:
            self.status_label.config(text="错误: 未安装 shazamio 库")
            print("错误: 未安装 shazamio 库")
            print("请运行: pip install shazamio")
            return
        
        if not SOUNDCARD_AVAILABLE:
            self.status_label.config(text="错误: 未安装 soundcard 等音频库")
            print("错误: 未安装 soundcard/soundfile/numpy 库")
            print("请运行: pip install soundcard soundfile numpy")
            return
        
        # 防止重复点击
        if self.shazam_recognizing:
            logger.info("已有识别任务进行中，忽略重复点击")
            return
        
        # 在新线程中执行识别，避免阻塞 UI
        thread = threading.Thread(target=self._run_shazam_recognition, daemon=True)
        thread.start()
    
    def on_window_close(self):
        """程序关闭时的清理"""
        logger.info("程序正在关闭，清理资源")
        cleanup_cosyvoice_wav()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenTranslatorApp(root)
    root.mainloop()
