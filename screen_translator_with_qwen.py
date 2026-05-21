# -*- coding: utf-8 -*-
import tkinter as tk
import pyautogui
from PIL import Image, ImageEnhance, ImageOps
import base64
import io
import threading
import logging
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

class ScreenTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("屏幕翻译工具 (v2.0)")
        logger.info("程序启动，初始化界面")
        
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
        
        # 关闭译文窗口
        if hasattr(self, 'translate_window') and self.translate_window:
            self.translate_window.destroy()
            self.translate_window = None
        self.current_translate_region = None
        
        # 禁用识别区域按钮
        self.select_recognize_area_btn.config(state=tk.DISABLED)
        
        # 禁用主界面的中止和关闭按钮
        self.abort_btn.config(state=tk.DISABLED)
        self.close_btn.config(state=tk.DISABLED)
        
        self.status_label.config(text="所有窗口已关闭")
    
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
            # 执行拉伸
            self.resize_window(self.translate_window, event.x, event.y, self.resize_edge)
        elif self.dragging:
            # 执行拖动
            self.move_window(self.translate_window, event.x - self.drag_start_x, event.y - self.drag_start_y)
        else:
            # 检查鼠标是否在窗口边缘，更改光标
            edge = self.get_window_edge(self.translate_window, event.x, event.y)
            if edge:
                cursor = self.get_cursor_for_edge(edge)
            else:
                # 鼠标在窗口内部，显示十字箭头光标
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

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenTranslatorApp(root)
    root.mainloop()
