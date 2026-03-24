# -*- coding: utf-8 -*-
import tkinter as tk
import pyautogui
import pytesseract
import requests
import json
from PIL import Image, ImageEnhance, ImageOps
import base64
import io
import threading
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 设置tesseract路径（如果需要）
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class AreaOCRWithAIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("区域OCR识别工具 (支持AI)")
        logger.debug("程序启动，初始化界面")
        # 先不设置固定大小，让界面元素自动调整
        self.root.wm_attributes('-topmost', False)  # 主界面不需要保持在顶层
        self.root.wm_attributes('-alpha', 0.9)
        
        # 创建界面元素
        self.title_label = tk.Label(root, text="区域OCR识别工具 (支持AI)", font=("Arial", 14, "bold"))
        self.title_label.pack(pady=10)
        
        # 识别引擎选择
        engine_frame = tk.Frame(root)
        engine_frame.pack(pady=10)
        
        self.engine_var = tk.StringVar(value="ollama")  # 设置ollama为默认选中
        tk.Label(engine_frame, text="识别引擎:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(engine_frame, text="Tesseract OCR", variable=self.engine_var, value="tesseract").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(engine_frame, text="Ollama AI", variable=self.engine_var, value="ollama").pack(side=tk.LEFT, padx=5)
        
        # 模型选择下拉菜单
        model_frame = tk.Frame(root)
        model_frame.pack(pady=5)
        
        tk.Label(model_frame, text="AI模型:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.model_var = tk.StringVar(value="glm-ocr:q8_0")  # 默认使用glm-ocr:q8_0
        self.model_menu = tk.OptionMenu(model_frame, self.model_var, "glm-ocr:q8_0", "llama3", "gemma", "mistral")
        self.model_menu.pack(side=tk.LEFT, padx=5)
        
        # 刷新模型按钮
        self.refresh_models_btn = tk.Button(model_frame, text="刷新模型", command=self.refresh_models)
        self.refresh_models_btn.pack(side=tk.LEFT, padx=5)
        
        # 选择区域按钮
        self.select_button = tk.Button(root, text="选择识别区域", command=self.select_area, font=('Arial', 12))
        self.select_button.pack(pady=10)
        
        # 识别结果文本框
        self.result_text = tk.Text(root, width=45, height=5, font=('Arial', 10))
        self.result_text.pack(pady=5)
        
        # 翻译功能
        translate_frame = tk.Frame(root)
        translate_frame.pack(pady=10)
        
        tk.Label(translate_frame, text="翻译模型:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.translate_model_var = tk.StringVar(value="qwen2.5:7b")  # 默认使用qwen2.5:7b
        self.translate_model_menu = tk.OptionMenu(translate_frame, self.translate_model_var, "qwen2.5:7b", "llama3", "gemma", "mistral")
        self.translate_model_menu.pack(side=tk.LEFT, padx=5)
        
        # 重新翻译按钮
        self.translate_btn = tk.Button(translate_frame, text="重新翻译", command=self.translate_text)
        self.translate_btn.pack(side=tk.LEFT, padx=5)
        
        # 显示翻译区域按钮
        self.show_translate_area_btn = tk.Button(translate_frame, text="显示翻译区域", command=self.select_translate_area)
        self.show_translate_area_btn.pack(side=tk.LEFT, padx=5)
        
        # 保存处理图片选项
        save_images_frame = tk.Frame(root)
        save_images_frame.pack(pady=5)
        self.save_images_var = tk.BooleanVar(value=False)
        save_images_checkbox = tk.Checkbutton(save_images_frame, text="保存处理过程中的图片", variable=self.save_images_var, command=self.toggle_save_images)
        save_images_checkbox.pack(side=tk.LEFT, padx=5)
        
        # 翻译结果文本框
        self.translate_result = tk.Text(root, width=45, height=5, font=("Arial", 10))
        self.translate_result.pack(pady=5)
        
        # 状态标签
        self.status_label = tk.Label(root, text="就绪", font=("Arial", 10))
        self.status_label.pack(pady=5)
        
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
        
        # 图像处理相关标志
        self.save_process_images = False  # 是否保存处理过程中的图片
        
        # 自动调整窗口大小以适应所有界面元素
        self.root.update()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        self.root.geometry(f"{width+20}x{height+20}+100+100")  # 增加一些边距
        logger.debug(f"自动调整窗口大小为: {width+20}x{height+20}")
        
        # 初始化模型列表
        self.refresh_models()
    
    def toggle_save_images(self):
        """切换是否保存处理过程中的图片"""
        self.save_process_images = self.save_images_var.get()
        logger.debug(f"保存处理图片功能: {'启用' if self.save_process_images else '禁用'}")
    
    def refresh_models(self):
        """刷新已安装的Ollama模型列表"""
        try:
            self.status_label.config(text="正在获取模型列表...")
            self.root.update()
            
            # 尝试不同的Ollama API路径
            api_urls = [
                "http://localhost:11434/api/tags",
                "http://127.0.0.1:11434/api/tags"
            ]
            
            success = False
            for api_url in api_urls:
                try:
                    # 调用Ollama API获取模型列表
                    response = requests.get(api_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        models = [model["name"] for model in data.get("models", [])]
                        
                        # 清空并更新下拉菜单
                        menu = self.model_menu["menu"]
                        menu.delete(0, "end")
                        
                        if models:
                            for model in models:
                                menu.add_command(label=model, command=tk._setit(self.model_var, model))
                            # 设置OCR模型为glm-ocr:q8_0（如果存在）
                            if "glm-ocr:q8_0" in models:
                                self.model_var.set("glm-ocr:q8_0")
                            else:
                                self.model_var.set(models[0])
                            
                            # 更新翻译模型下拉菜单
                            translate_menu = self.translate_model_menu["menu"]
                            translate_menu.delete(0, "end")
                            for model in models:
                                translate_menu.add_command(label=model, command=tk._setit(self.translate_model_var, model))
                            # 设置翻译模型为qwen2.5:7b（如果存在）
                            if "qwen2.5:7b" in models:
                                self.translate_model_var.set("qwen2.5:7b")
                            else:
                                self.translate_model_var.set(models[0])
                            
                            self.status_label.config(text=f"已获取 {len(models)} 个模型")
                        else:
                            # 如果没有模型，添加默认模型
                            default_models = ["glm-ocr:q8_0", "qwen2.5:7b", "llama3", "gemma", "mistral"]
                            for model in default_models:
                                menu.add_command(label=model, command=tk._setit(self.model_var, model))
                            # 设置OCR模型为glm-ocr:q8_0
                            self.model_var.set("glm-ocr:q8_0")
                            
                            # 更新翻译模型下拉菜单
                            translate_menu = self.translate_model_menu["menu"]
                            translate_menu.delete(0, "end")
                            for model in default_models:
                                translate_menu.add_command(label=model, command=tk._setit(self.translate_model_var, model))
                            # 设置翻译模型为qwen2.5:7b
                            self.translate_model_var.set("qwen2.5:7b")
                            
                            self.status_label.config(text="未找到模型，使用默认模型列表")
                        success = True
                        break
                except Exception as e:
                    continue
            
            if not success:
                self.status_label.config(text="无法连接到Ollama服务，请确保Ollama已安装并运行")
                # 添加默认模型
                default_models = ["glm-ocr:q8_0", "qwen2.5:7b", "llama3", "gemma", "mistral"]
                menu = self.model_menu["menu"]
                menu.delete(0, "end")
                for model in default_models:
                    menu.add_command(label=model, command=tk._setit(self.model_var, model))
                # 设置OCR模型为glm-ocr:q8_0
                self.model_var.set("glm-ocr:q8_0")
                
                # 更新翻译模型下拉菜单
                translate_menu = self.translate_model_menu["menu"]
                translate_menu.delete(0, "end")
                for model in default_models:
                    translate_menu.add_command(label=model, command=tk._setit(self.translate_model_var, model))
                # 设置翻译模型为qwen2.5:7b
                self.translate_model_var.set("qwen2.5:7b")
        except Exception as e:
            self.status_label.config(text=f"获取模型列表失败: {str(e)}")
    
    def select_area(self):
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
            
        except Exception as e:
            self.status_label.config(text=f"错误: {str(e)}")
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"选择区域失败: {str(e)}")
    
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
        logger.debug(f"选择区域完成: x={x1}, y={y1}, width={width}, height={height}")
        
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
        self.border_window.attributes('-alpha', 0.3)  # 降低透明度，使蒙版效果更自然
        
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
        self.button_window = tk.Toplevel(self.root)
        self.button_window.geometry(f"180x40+{x + width - 180}+{y - 45}")  # 放在选择框上方
        self.button_window.overrideredirect(True)  # 无标题栏
        self.button_window.attributes('-topmost', True)
        self.button_window.attributes('-alpha', 1.0)  # 完全不透明，确保按钮清晰可见
        
        # 创建按钮框架
        button_frame = tk.Frame(self.button_window, bg='black', bd=2, relief=tk.RAISED)
        button_frame.pack(fill=tk.BOTH, expand=True)
        
        # 重新识别按钮
        recognize_btn = tk.Button(button_frame, text="重新识别", command=self.recognize_area, 
                               bg='lime', fg='black', font=("Arial", 10, "bold"), padx=8, pady=4)
        recognize_btn.pack(side=tk.LEFT, padx=5, pady=3, fill=tk.BOTH, expand=True)
        
        # 关闭按钮
        close_btn = tk.Button(button_frame, text="关闭", command=self.close_border, 
                           bg='red', fg='white', font=("Arial", 10, "bold"), padx=8, pady=4)
        close_btn.pack(side=tk.RIGHT, padx=5, pady=3, fill=tk.BOTH, expand=True)
    
    def recognize_area(self):
        """识别选定区域的文字"""
        if not self.current_region:
            self.status_label.config(text="未选择区域")
            return
        
        # 启动线程处理AI交互
        def recognize_thread():
            try:
                # 设置AI交互标志
                self.ai_interaction_active = True
                logger.debug("开始识别区域文字")
                
                # 截取选定区域
                x, y, width, height = self.current_region
                logger.debug(f"截取区域: x={x}, y={y}, width={width}, height={height}")
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
                logger.debug("截图完成")
                
                # 更新UI
                def update_ui_recognizing(screenshot):
                    # 计算图像大小
                    buffered = io.BytesIO()
                    screenshot.save(buffered, format="JPEG", quality=75)
                    image_size_kb = len(buffered.getvalue()) / 1024
                    
                    self.status_label.config(text="正在识别...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="识别中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"正在识别. . .(图像大小 {image_size_kb:.1f} kb)")
                    self.root.update()
                
                self.root.after(0, lambda: update_ui_recognizing(screenshot))
                # 添加小延迟，让用户看到状态消息
                self.root.after(500)
                
                # 根据选择的引擎进行识别
                engine = self.engine_var.get()
                logger.debug(f"选择识别引擎: {engine}")
                if engine == "tesseract":
                    # 使用Tesseract OCR
                    logger.debug("使用Tesseract OCR进行识别")
                    text = self.recognize_with_tesseract(screenshot)
                else:
                    # 使用Ollama AI
                    logger.debug(f"使用Ollama AI进行识别，模型: {self.model_var.get()}")
                    text = self.recognize_with_ollama(screenshot)
                logger.debug(f"识别完成，结果: {text[:100]}..." if len(text) > 100 else f"识别完成，结果: {text}")
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 更新UI
                def update_ui_recognized():
                    # 清空文本框并显示识别结果
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, text if text else "未识别到文本")
                    
                    self.status_label.config(text="识别完成，正在翻译...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text="翻译中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text="正在翻译 . .")
                    self.root.update()
                
                self.root.after(0, update_ui_recognized)
                # 添加小延迟，让用户看到状态消息
                self.root.after(500)
                
                # 自动翻译识别结果
                self.translate_text()
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 更新UI
                def update_ui_completed():
                    self.status_label.config(text="翻译完成")
                
                self.root.after(0, update_ui_completed)
            except Exception as e:
                # 更新UI
                def update_ui_error(e):
                    self.status_label.config(text=f"错误: {str(e)}")
                    self.result_text.delete(1.0, tk.END)
                    self.result_text.insert(tk.END, f"识别失败: {str(e)}")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text=f"识别失败: {str(e)}")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.config(text=f"识别失败: {str(e)}")
                
                self.root.after(0, lambda e=e: update_ui_error(e))
            finally:
                # 重置AI交互标志
                self.ai_interaction_active = False
        
        # 启动线程
        thread = threading.Thread(target=recognize_thread)
        thread.daemon = True
        thread.start()
    
    def translate_text(self):
        """翻译识别结果"""
        # 获取识别结果
        text = self.result_text.get(1.0, tk.END).strip()
        if not text or text == "未识别到文本":
            self.translate_result.delete(1.0, tk.END)
            self.translate_result.insert(tk.END, "没有可翻译的文本")
            # 更新翻译窗口状态
            if hasattr(self, 'translate_status_label'):
                self.translate_status_label.config(text="没有可翻译的文本")
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
                
                # 构建翻译请求
                model = self.translate_model_var.get()
                logger.debug(f"选择翻译模型: {model}")
                prompt = f"请将以下文本翻译成中文:\n\n{text}"
                logger.debug(f"翻译提示: {prompt[:100]}..." if len(prompt) > 100 else f"翻译提示: {prompt}")
                
                data = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
                
                # 尝试不同的Ollama API路径
                api_urls = [
                    "http://localhost:11434/api/generate",
                    "http://127.0.0.1:11434/api/generate"
                ]
                
                translated_text = ""
                for api_url in api_urls:
                    # 检查是否已中止
                    if not self.translating:
                        return
                    
                    try:
                        logger.debug(f"发送翻译请求到: {api_url}")
                        response = requests.post(api_url, json=data, timeout=30)
                        logger.debug(f"收到响应，状态码: {response.status_code}")
                        # 检查是否已中止
                        if not self.translating:
                            return
                        
                        if response.status_code == 200:
                            result = response.json()
                            translated_text = result.get("response", "")
                            logger.debug(f"翻译完成，结果: {translated_text[:100]}..." if len(translated_text) > 100 else f"翻译完成，结果: {translated_text}")
                            break
                    except Exception as e:
                        logger.debug(f"翻译请求失败: {str(e)}")
                        continue
                
                # 检查是否已中止
                if not self.translating:
                    return
                
                # 更新UI
                def update_ui_translated():
                    # 显示翻译结果
                    self.translate_result.delete(1.0, tk.END)
                    self.translate_result.insert(tk.END, translated_text if translated_text else "翻译失败")
                    
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
                    self.translate_result.delete(1.0, tk.END)
                    self.translate_result.insert(tk.END, f"翻译失败: {str(e)}")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.config(text=f"翻译失败: {str(e)}")
                    
                    # 自动更新翻译窗口内容
                    if hasattr(self, 'translate_window') and self.translate_window:
                        self.show_translation_in_window()
                
                self.root.after(0, lambda e=e: update_ui_error(e))
            finally:
                # 重置翻译状态
                self.translating = False
        
        # 启动线程
        thread = threading.Thread(target=translate_thread)
        thread.daemon = True
        thread.start()
    
    def recognize_with_tesseract(self, image):
        """使用Tesseract进行OCR识别"""
        logger.debug("开始Tesseract OCR识别")
        # 图像处理以提高OCR识别率
        # 转换为灰度图
        grayscale = ImageOps.grayscale(image)
        logger.debug("转换为灰度图")
        
        # 提高对比度
        enhancer = ImageEnhance.Contrast(grayscale)
        enhanced = enhancer.enhance(2.0)
        logger.debug("提高对比度")
        
        # 轻微提高亮度
        brightness_enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = brightness_enhancer.enhance(1.2)
        logger.debug("提高亮度")
        
        # 使用tesseract识别文本，添加配置以提高识别率
        custom_config = r'--oem 3 --psm 6'
        logger.debug(f"使用Tesseract配置: {custom_config}")
        text = pytesseract.image_to_string(enhanced, lang='chi_sim+eng', config=custom_config)
        logger.debug(f"Tesseract识别完成，结果: {text[:100]}..." if len(text) > 100 else f"Tesseract识别完成，结果: {text}")
        
        return text
    
    def crop_text_area(self, image):
        """使用Tesseract-OCR裁剪出文字区域"""
        try:
            # 转换为灰度图
            grayscale = ImageOps.grayscale(image)
            
            # 使用Tesseract获取文字边界框
            boxes = pytesseract.image_to_boxes(grayscale, lang='chi_sim+eng')
            
            if not boxes:
                return image
            
            # 计算文字区域的边界
            min_x = float('inf')
            min_y = float('inf')
            max_x = 0
            max_y = 0
            
            for box in boxes.splitlines():
                parts = box.split()
                if len(parts) >= 6:
                    x = int(parts[1])
                    y = int(parts[2])
                    w = int(parts[3])
                    h = int(parts[4])
                    
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, w)
                    max_y = max(max_y, h)
            
            # 确保边界有效
            if min_x >= max_x or min_y >= max_y:
                return image
            
            # 扩展边界，增加一些边距
            margin = 10
            width, height = image.size
            min_x = max(0, min_x - margin)
            min_y = max(0, min_y - margin)
            max_x = min(width, max_x + margin)
            max_y = min(height, max_y + margin)
            
            # 裁剪文字区域
            cropped = image.crop((min_x, min_y, max_x, max_y))
            return cropped
        except Exception as e:
            # 如果Tesseract不可用，返回原图
            print(f"裁剪文字区域失败: {str(e)}")
            return image

    def enhance_contrast(self, image):
        """提高图片对比度"""
        # 转换为灰度图
        grayscale = ImageOps.grayscale(image)
        # 提高对比度
        enhancer = ImageEnhance.Contrast(grayscale)
        enhanced = enhancer.enhance(2.0)  # 对比度增强因子
        # 轻微提高亮度
        brightness_enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = brightness_enhancer.enhance(1.2)
        return enhanced

    def compress_image(self, image, quality=50):
        """压缩图片（使用旧的压缩方式）"""
        # 增加对比度
        logger.debug("增加图像对比度")
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(2.0)
        
        # 将图片转换为灰度图
        logger.debug("将图片转换为灰度图")
        if enhanced_image.mode != 'L':
            # 转换为灰度图
            enhanced_image = ImageOps.grayscale(enhanced_image)
        
        # 保存处理过程中的图片（如果启用）
        if hasattr(self, 'save_process_images') and self.save_process_images:
            import os
            # 创建screenshots文件夹
            if not os.path.exists('screenshots'):
                os.makedirs('screenshots')
            # 保存增强后的图片
            import time
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            enhanced_path = f'screenshots/enhanced_{timestamp}.jpg'
            # JPEG格式不支持P模式，需要转换为RGB模式
            if enhanced_image.mode == 'P':
                save_image = enhanced_image.convert('RGB')
            else:
                save_image = enhanced_image
            save_image.save(enhanced_path, format="JPEG", quality=90)
            logger.debug(f"保存增强后的图片到: {enhanced_path}")
        
        # 将图片保存到内存中进行压缩
        logger.debug(f"压缩图片，质量: {quality}")
        buffered = io.BytesIO()
        # JPEG格式不支持P模式，需要转换为RGB模式
        if enhanced_image.mode == 'P':
            enhanced_image = enhanced_image.convert('RGB')
        enhanced_image.save(buffered, format="JPEG", quality=quality)
        
        # 保存压缩后的图片（如果启用）
        if hasattr(self, 'save_process_images') and self.save_process_images:
            compressed_path = f'screenshots/compressed_{timestamp}.jpg'
            with open(compressed_path, 'wb') as f:
                f.write(buffered.getvalue())
            logger.debug(f"保存压缩后的图片到: {compressed_path}")
            # 重置缓冲区指针
            buffered.seek(0)
        
        # 重新读取压缩后的图片
        compressed = Image.open(buffered)
        return compressed
    
    def recognize_with_ollama(self, image):
        """使用Ollama AI进行图像识别"""
        logger.debug("开始Ollama AI图像识别")
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")
        
        # 压缩图片以减少API请求大小
        logger.debug("压缩图片以减少API请求大小")
        compressed_image = self.compress_image(image)
        
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")
        
        # 将压缩后的图像转换为base64编码
        logger.debug("将图像转换为base64编码")
        buffered = io.BytesIO()
        compressed_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        logger.debug(f"图像base64编码长度: {len(img_str)} 字符")
        
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")
        
        # 构建请求数据
        model = self.model_var.get()
        prompt = "请识别图片中的所有文字，保持原始格式和顺序，不要添加任何解释或说明。"
        logger.debug(f"使用模型: {model}")
        logger.debug(f"识别提示: {prompt}")
        
        data = {
            "model": model,
            "prompt": prompt,
            "images": [img_str],
            "stream": False
        }
        
        # 尝试不同的Ollama API路径
        api_urls = [
            "http://localhost:11434/api/generate",
            "http://127.0.0.1:11434/api/generate"
        ]
        
        errors = []
        for api_url in api_urls:
            # 检查是否已中止
            if not self.ai_interaction_active:
                raise Exception("AI交互已中止")
            
            try:
                # 发送请求到Ollama API
                logger.debug(f"尝试连接到: {api_url}")
                response = requests.post(api_url, json=data, timeout=30)
                logger.debug(f"响应状态码: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    recognized_text = result.get("response", "")
                    logger.debug(f"Ollama识别完成，结果: {recognized_text[:100]}..." if len(recognized_text) > 100 else f"Ollama识别完成，结果: {recognized_text}")
                    return recognized_text
                else:
                    error_msg = f"{api_url}: 状态码 {response.status_code}, 响应: {response.text}"
                    logger.debug(error_msg)
                    errors.append(error_msg)
            except Exception as e:
                error_msg = f"{api_url}: 错误 {str(e)}"
                logger.debug(error_msg)
                errors.append(error_msg)
                continue
        
        # 如果所有路径都失败
        error_message = "无法连接到Ollama服务，请确保Ollama已安装并运行\n"
        error_message += "详细错误信息:\n" + "\n".join(errors)
        print(error_message)
        raise Exception(error_message)
    
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
        
        # 更新按钮窗口位置
        if self.button_window:
            button_x = x + width - 180
            button_y = y - 45
            self.button_window.geometry(f"180x40+{button_x}+{button_y}")
        
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
            button_x = new_x + new_width - 180
            button_y = new_y - 45
            self.button_window.geometry(f"180x40+{button_x}+{button_y}")
        
        # 更新当前区域
        self.current_region = (new_x, new_y, new_width, new_height)
    
    def close_border(self):
        """关闭边框窗口和按钮窗口"""
        if self.border_window:
            self.border_window.destroy()
            self.border_window = None
        if hasattr(self, 'button_window') and self.button_window:
            self.button_window.destroy()
            self.button_window = None
        self.current_region = None
        self.status_label.config(text="就绪")
    
    def select_translate_area(self):
        """选择翻译区域"""
        try:
            self.status_label.config(text="请选择翻译显示区域...")
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
            
        except Exception as e:
            self.status_label.config(text=f"错误: {str(e)}")
            self.translate_result.delete(1.0, tk.END)
            self.translate_result.insert(tk.END, f"选择翻译区域失败: {str(e)}")
    
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
                outline='blue', width=2, tags='selection'
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
        
        # 创建翻译显示窗口
        self.create_translate_window(x1, y1, width, height)
        
        # 显示翻译内容
        self.show_translation_in_window()
    
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
        
        # 创建标签用于显示翻译内容（替换文本框）
        self.translate_text_widget = tk.Label(main_frame, 
                                           font=("Arial", 10), 
                                           fg='white', 
                                           bg='black',
                                           wraplength=width-20,
                                           justify=tk.LEFT,
                                           anchor=tk.NW)
        self.translate_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建状态标签
        self.translate_status_label = tk.Label(main_frame, text="就绪", font=("Arial", 8), fg='white', bg='black')
        self.translate_status_label.pack(side=tk.BOTTOM, padx=10, pady=5)
        
        # 创建控制选项窗口，放在选择框左下角外侧
        self.control_window = tk.Toplevel(self.root)
        self.control_window.geometry(f"300x40+{x}+{y + height}")  # 放在选择框下方左侧
        self.control_window.overrideredirect(True)  # 无标题栏
        self.control_window.attributes('-topmost', True)
        self.control_window.attributes('-alpha', 0.5)  # 半透明背景
        
        # 创建控制框架
        control_frame = tk.Frame(self.control_window, bg='black', bd=1, relief=tk.RAISED)
        control_frame.pack(fill=tk.BOTH, expand=True)
        
        # 透明度控制
        tk.Label(control_frame, text="透明度:", font=("Arial", 8), fg='white', bg='black').grid(row=0, column=0, padx=3, pady=5, sticky='w')
        self.alpha_var = tk.DoubleVar(value=0.7)  # 默认透明度0.7
        alpha_scale = tk.Scale(control_frame, variable=self.alpha_var, from_=0.1, to=1.0, resolution=0.1, 
                              orient=tk.HORIZONTAL, length=60, bg='black', fg='white', troughcolor='gray')
        alpha_scale.grid(row=0, column=1, padx=3, pady=5, sticky='w')
        alpha_scale.bind('<ButtonRelease-1>', self.update_translate_window)
        
        # 字体大小控制
        tk.Label(control_frame, text="字体:", font=("Arial", 8), fg='white', bg='black').grid(row=0, column=2, padx=3, pady=5, sticky='w')
        self.font_size_var = tk.IntVar(value=18)  # 默认字体大小18
        font_size_menu = tk.OptionMenu(control_frame, self.font_size_var, 8, 10, 12, 14, 16, 18, command=self.update_translate_window)
        font_size_menu.config(font=("Arial", 8), bg='gray', fg='white', width=3)
        font_size_menu.grid(row=0, column=3, padx=3, pady=5, sticky='w')
        
        # 字体加粗控制
        self.bold_var = tk.BooleanVar(value=True)  # 默认字体加粗
        bold_check = tk.Checkbutton(control_frame, text="加粗", variable=self.bold_var, 
                                   bg='black', fg='white', font=("Arial", 8), 
                                   command=self.update_translate_window)
        bold_check.grid(row=0, column=4, padx=3, pady=5, sticky='w')
        
        # 创建控制按钮窗口，放在选择框右下角外侧
        self.translate_button_window = tk.Toplevel(self.root)
        self.translate_button_window.geometry(f"180x40+{x + width - 180}+{y + height}")  # 恢复原始宽度
        self.translate_button_window.overrideredirect(True)  # 无标题栏
        self.translate_button_window.attributes('-topmost', True)
        self.translate_button_window.attributes('-alpha', 1.0)  # 完全不透明，确保按钮清晰可见
        
        # 创建按钮框架
        button_frame = tk.Frame(self.translate_button_window, bg='black', bd=2, relief=tk.RAISED)
        button_frame.pack(fill=tk.BOTH, expand=True)
        
        # 中止AI交互按钮
        abort_btn = tk.Button(button_frame, text="中止", command=self.abort_ai_interaction, 
                           bg='orange', fg='black', font=("Arial", 10, "bold"), padx=8, pady=4)
        abort_btn.pack(side=tk.LEFT, padx=5, pady=3, fill=tk.BOTH, expand=True)
        
        # 关闭按钮
        close_btn = tk.Button(button_frame, text="关闭", command=self.close_translate_window, 
                           bg='red', fg='white', font=("Arial", 10, "bold"), padx=8, pady=4)
        close_btn.pack(side=tk.RIGHT, padx=5, pady=3, fill=tk.BOTH, expand=True)
    
    def show_translation_in_window(self):
        """在翻译窗口中显示翻译内容"""
        if not self.translate_window:
            self.status_label.config(text="请先选择翻译区域")
            return
        
        # 启动线程处理，避免UI卡顿
        def show_translation_thread():
            # 获取翻译结果和原文
            translation = self.translate_result.get(1.0, tk.END).strip()
            original_text = self.result_text.get(1.0, tk.END).strip()
            
            if not translation or translation == "没有可翻译的文本" or translation == "翻译失败":
                display_text = "无翻译内容"
                status_text = "无翻译内容"
            else:
                # 分两行显示，第一行是翻译内容，第二行是原文
                display_text = f"{translation}\n\n原文: {original_text}"
                status_text = "翻译完成"
            
            # 更新UI
            def update_ui():
                # 更新翻译窗口状态
                if hasattr(self, 'translate_status_label'):
                    self.translate_status_label.config(text=status_text)
                
                # 显示翻译内容
                self.translate_text_widget.config(text=display_text)
                
                # 更新窗口设置
                self.update_translate_window()
                
                self.status_label.config(text="翻译内容已显示")
            
            self.root.after(0, update_ui)
        
        # 启动线程
        thread = threading.Thread(target=show_translation_thread)
        thread.daemon = True
        thread.start()
    
    def update_translate_window(self, event=None):
        """更新翻译窗口的设置"""
        if not self.translate_window:
            return
        
        # 更新透明度
        alpha = self.alpha_var.get()
        self.translate_window.attributes('-alpha', alpha)
        
        # 更新字体设置
        font_size = self.font_size_var.get()
        bold = self.bold_var.get()
        font_weight = "bold" if bold else "normal"
        
        # 更新文本框字体
        self.translate_text_widget.config(font=("Arial", font_size, font_weight))
    
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
        
        # 更新按钮和控制选项的位置
        if window == self.translate_window:
            if hasattr(self, 'translate_button_window') and self.translate_button_window:
                button_x = self.translate_button_window.winfo_x() + delta_x
                button_y = self.translate_button_window.winfo_y() + delta_y
                self.translate_button_window.geometry(f"+{button_x}+{button_y}")
            
            if hasattr(self, 'control_window') and self.control_window:
                control_x = self.control_window.winfo_x() + delta_x
                control_y = self.control_window.winfo_y() + delta_y
                self.control_window.geometry(f"+{control_x}+{control_y}")
    
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
        
        # 更新按钮和控制选项的位置
        if hasattr(self, 'translate_button_window') and self.translate_button_window:
            button_x = new_x + new_width - 180
            button_y = new_y + new_height
            self.translate_button_window.geometry(f"180x40+{button_x}+{button_y}")
        
        if hasattr(self, 'control_window') and self.control_window:
            control_x = new_x
            control_y = new_y + new_height
            self.control_window.geometry(f"300x40+{control_x}+{control_y}")
    
    def close_translate_window(self):
        """关闭翻译窗口和按钮窗口"""
        # 先中止AI交互
        self.abort_ai_interaction()
        
        if self.translate_window:
            self.translate_window.destroy()
            self.translate_window = None
        if hasattr(self, 'translate_button_window') and self.translate_button_window:
            self.translate_button_window.destroy()
            self.translate_button_window = None
        if hasattr(self, 'control_window') and self.control_window:
            self.control_window.destroy()
            self.control_window = None
        self.current_translate_region = None
        self.status_label.config(text="翻译窗口已关闭")

if __name__ == "__main__":
    root = tk.Tk()
    app = AreaOCRWithAIApp(root)
    root.mainloop()
