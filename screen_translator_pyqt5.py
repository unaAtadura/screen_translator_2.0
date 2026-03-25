# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QFrame, QScrollArea)
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QCursor, QPainter, QPen, QColor
import pyautogui
from PIL import Image, ImageEnhance, ImageOps
import base64
import io
import threading
import logging
from zai import ZhipuAiClient

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

# 读取API密钥
def read_api_key():
    """从本地key.txt文件读取API密钥"""
    try:
        with open('key.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"读取API密钥失败: {str(e)}")
        return ""

# 初始化智普AI客户端
api_key = read_api_key()
zhipu_client = None
if api_key:
    try:
        zhipu_client = ZhipuAiClient(api_key=api_key)
        logger.debug("智普AI客户端初始化成功")
    except Exception as e:
        logger.error(f"智普AI客户端初始化失败: {str(e)}")

class SelectionWindow(QWidget):
    """自定义选择窗口，用于绘制选择框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.selecting = False
        self.border_color = QColor(0, 0, 255)  # 蓝色边框
    
    def paintEvent(self, event):
        """绘制选择框"""
        super().paintEvent(event)
        if self.selecting:
            painter = QPainter(self)
            painter.setPen(QPen(self.border_color, 2))
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

class ScreenTranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("屏幕翻译工具 (v2.0 - PyQt5)")
        self.setMinimumSize(200, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建垂直布局
        layout = QVBoxLayout(central_widget)
        
        # 标题标签
        self.title_label = QLabel("屏幕翻译工具 (v2.0)")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        # 选择区域按钮
        self.select_translate_area_btn = QPushButton("选择译文区域")
        self.select_translate_area_btn.clicked.connect(self.select_translate_area)
        self.select_translate_area_btn.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px;")
        layout.addWidget(self.select_translate_area_btn)
        
        self.select_recognize_area_btn = QPushButton("选择识别区域")
        self.select_recognize_area_btn.clicked.connect(self.select_area)
        self.select_recognize_area_btn.setEnabled(False)
        self.select_recognize_area_btn.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px;")
        layout.addWidget(self.select_recognize_area_btn)
        
        # 中止按钮
        self.abort_btn = QPushButton("中止")
        self.abort_btn.clicked.connect(self.abort_ai_interaction)
        self.abort_btn.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px; background-color: orange; color: black;")
        self.abort_btn.setEnabled(False)
        layout.addWidget(self.abort_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close_border)
        self.close_btn.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px; background-color: red; color: white;")
        self.close_btn.setEnabled(False)
        layout.addWidget(self.close_btn)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px;")
        layout.addWidget(self.status_label)
        
        # 区域选择相关变量
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.selecting = False
        self.select_window = None
        self.current_region = None
        
        # 翻译区域相关变量
        self.translate_start_x = 0
        self.translate_start_y = 0
        self.translate_end_x = 0
        self.translate_end_y = 0
        self.translate_selecting = False
        self.translate_select_window = None
        self.translate_window = None
        self.current_translate_region = None
        
        # AI交互控制变量
        self.ai_interaction_active = False
        self.translating = False
        
        # 窗口拖动和拉伸相关变量
        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()
        self.resize_start = QPoint()
        self.resize_edge = None
        
        logger.debug("程序启动，初始化界面")
    
    def select_translate_area(self):
        """选择翻译区域"""
        try:
            logger.debug("开始选择译文区域")
            self.status_label.setText("请选择译文区域...")
            
            # 创建全屏半透明窗口用于选择区域
            self.translate_select_window = SelectionWindow()
            self.translate_select_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.translate_select_window.setGeometry(0, 0, QApplication.desktop().width(), QApplication.desktop().height())
            self.translate_select_window.setStyleSheet("background-color: rgba(0, 0, 0, 76);")  # 0.3透明度
            self.translate_select_window.setWindowOpacity(0.3)
            
            # 绑定鼠标事件
            self.translate_select_window.mousePressEvent = self.on_translate_mouse_down
            self.translate_select_window.mouseMoveEvent = self.on_translate_mouse_drag
            self.translate_select_window.mouseReleaseEvent = self.on_translate_mouse_up
            self.translate_select_window.keyPressEvent = self.on_escape
            
            self.translate_select_window.showFullScreen()
            
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            logger.error(f"选择译文区域失败: {str(e)}")
    
    def on_translate_mouse_down(self, event):
        """翻译区域选择鼠标按下事件"""
        self.translate_select_window.start_x = event.globalX()
        self.translate_select_window.start_y = event.globalY()
        self.translate_select_window.selecting = True
    
    def on_translate_mouse_drag(self, event):
        """翻译区域选择鼠标拖动事件"""
        if self.translate_select_window.selecting:
            self.translate_select_window.end_x = event.globalX()
            self.translate_select_window.end_y = event.globalY()
            self.translate_select_window.update()
    
    def on_translate_mouse_up(self, event):
        """翻译区域选择鼠标释放事件"""
        self.translate_select_window.end_x = event.globalX()
        self.translate_select_window.end_y = event.globalY()
        self.translate_select_window.selecting = False
        
        # 确保坐标顺序正确
        x1 = min(self.translate_select_window.start_x, self.translate_select_window.end_x)
        y1 = min(self.translate_select_window.start_y, self.translate_select_window.end_y)
        x2 = max(self.translate_select_window.start_x, self.translate_select_window.end_x)
        y2 = max(self.translate_select_window.start_y, self.translate_select_window.end_y)
        
        # 计算选择区域的宽度和高度
        width = x2 - x1
        height = y2 - y1
        
        # 关闭选择窗口
        self.translate_select_window.close()
        
        # 如果选择区域太小，提示用户
        if width < 100 or height < 50:
            self.status_label.setText("选择区域太小，请重新选择")
            return
        
        # 保存当前选择的翻译区域
        self.current_translate_region = (x1, y1, width, height)
        logger.debug(f"选择译文区域完成: x={x1}, y={y1}, width={width}, height={height}")
        
        # 创建翻译显示窗口
        self.create_translate_window(x1, y1, width, height)
        
        # 启用识别区域按钮
        self.select_recognize_area_btn.setEnabled(True)
        self.status_label.setText("译文区域创建完成")
    
    def create_translate_window(self, x, y, width, height):
        """创建翻译显示窗口"""
        # 关闭之前的窗口（如果存在）
        if self.translate_window:
            self.translate_window.close()
        
        # 创建翻译显示窗口
        self.translate_window = QWidget()
        self.translate_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.translate_window.setGeometry(x, y, width, height)
        # 设置窗口背景为半透明黑色
        self.translate_window.setStyleSheet("background-color: rgba(0, 0, 0, 76);")
        
        # 绑定鼠标事件
        self.translate_window.mousePressEvent = self.translate_window_mouse_down
        self.translate_window.mouseMoveEvent = self.translate_window_mouse_move
        self.translate_window.mouseReleaseEvent = self.translate_window_mouse_up
        self.translate_window.leaveEvent = self.translate_window_mouse_leave
        
        # 创建主布局
        main_layout = QVBoxLayout(self.translate_window)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域 - 使用透明背景
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: transparent; border: none;")
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 创建内容部件 - 使用透明背景
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_widget.setStyleSheet("background-color: transparent;")
        
        # 创建标签用于显示翻译内容
        self.translate_text_widget = QLabel()
        self.translate_text_widget.setWordWrap(True)
        self.translate_text_widget.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.translate_text_widget.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 20px; color: white; padding: 10px;")
        content_layout.addWidget(self.translate_text_widget)
        
        # 创建状态标签
        self.translate_status_label = QLabel("就绪")
        self.translate_status_label.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px; color: white; padding: 5px;")
        content_layout.addWidget(self.translate_status_label)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # 绑定滚轮事件到整个窗口
        self.translate_window.installEventFilter(self)
        
        self.translate_window.show()
    
    def eventFilter(self, obj, event):
        """事件过滤器，处理滚轮事件"""
        if event.type() == QEvent.Wheel and obj == self.translate_window:
            # 找到滚动区域并处理滚轮事件
            for child in self.translate_window.children():
                if isinstance(child, QScrollArea):
                    scroll_bar = child.verticalScrollBar()
                    delta = event.angleDelta().y()
                    if delta > 0:
                        scroll_bar.setValue(scroll_bar.value() - 10)
                    else:
                        scroll_bar.setValue(scroll_bar.value() + 10)
                    return True
        return super().eventFilter(obj, event)
    
    def select_area(self):
        """选择识别区域"""
        try:
            logger.debug("开始选择识别区域")
            self.status_label.setText("请选择识别区域...")
            
            # 创建全屏半透明窗口用于选择区域
            self.select_window = SelectionWindow()
            self.select_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.select_window.setGeometry(0, 0, QApplication.desktop().width(), QApplication.desktop().height())
            self.select_window.setStyleSheet("background-color: rgba(0, 0, 0, 76);")  # 0.3透明度
            self.select_window.setWindowOpacity(0.3)
            self.select_window.border_color = QColor(255, 255, 255)  # 白色边框
            
            # 绑定鼠标事件
            self.select_window.mousePressEvent = self.on_mouse_down
            self.select_window.mouseMoveEvent = self.on_mouse_drag
            self.select_window.mouseReleaseEvent = self.on_mouse_up
            self.select_window.keyPressEvent = self.on_escape
            
            self.select_window.showFullScreen()
            
        except Exception as e:
            self.status_label.setText(f"错误: {str(e)}")
            logger.error(f"选择识别区域失败: {str(e)}")
    
    def on_mouse_down(self, event):
        # 记录起始坐标
        self.select_window.start_x = event.globalX()
        self.select_window.start_y = event.globalY()
        self.select_window.selecting = True
    
    def on_mouse_drag(self, event):
        # 绘制选择框
        if self.select_window.selecting:
            self.select_window.end_x = event.globalX()
            self.select_window.end_y = event.globalY()
            self.select_window.update()
    
    def on_mouse_up(self, event):
        # 记录结束坐标并关闭选择窗口
        self.select_window.end_x = event.globalX()
        self.select_window.end_y = event.globalY()
        self.select_window.selecting = False
        
        # 确保坐标顺序正确
        x1 = min(self.select_window.start_x, self.select_window.end_x)
        y1 = min(self.select_window.start_y, self.select_window.end_y)
        x2 = max(self.select_window.start_x, self.select_window.end_x)
        y2 = max(self.select_window.start_y, self.select_window.end_y)
        
        # 计算选择区域的宽度和高度
        width = x2 - x1
        height = y2 - y1
        
        # 关闭选择窗口
        self.select_window.close()
        
        # 如果选择区域太小，提示用户
        if width < 10 or height < 10:
            self.status_label.setText("选择区域太小，请重新选择")
            return
        
        # 保存当前选择的区域
        self.current_region = (x1, y1, width, height)
        logger.debug(f"选择识别区域完成: x={x1}, y={y1}, width={width}, height={height}")
        
        # 创建边框窗口
        self.create_border_window(x1, y1, width, height)
        
        # 不自动执行识别，等待用户点击重新识别按钮
    
    def create_border_window(self, x, y, width, height):
        """创建带有边框和控制按钮的窗口"""
        # 关闭之前的窗口（如果存在）
        if hasattr(self, 'border_window') and self.border_window:
            self.border_window.close()
        if hasattr(self, 'button_window') and self.button_window:
            self.button_window.close()
        
        # 创建边框窗口，正好覆盖选择区域
        self.border_window = QWidget()
        self.border_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.border_window.setGeometry(x, y, width, height)
        self.border_window.setStyleSheet("background-color: rgba(0, 0, 0, 76);")  # 0.3透明度，使蒙版效果更自然
        self.border_window.setWindowOpacity(0.3)
        
        # 绑定鼠标事件
        self.border_window.mousePressEvent = self.border_window_mouse_down
        self.border_window.mouseMoveEvent = self.border_window_mouse_move
        self.border_window.mouseReleaseEvent = self.border_window_mouse_up
        self.border_window.leaveEvent = self.border_window_mouse_leave
        
        # 创建控制按钮窗口，放在选择框右上角外侧
        button_width = 100
        button_height = 40
        margin = 50  # 边界边距
        
        # 默认放在识别区域上方偏右
        button_x = x + width - button_width
        button_y = y - button_height - 5
        
        # 获取屏幕高度用于边界检查
        screen_height = QApplication.desktop().height()
        
        # 如果上方空间不够，尝试放在下方
        if button_y < margin:
            button_y = y + height + 5
            # 如果下方空间也不够，就放在识别区域内顶部
            if button_y + button_height > screen_height - margin:
                button_y = y + margin
                button_x = x + width - button_width - margin
        
        self.button_window = QWidget()
        self.button_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.button_window.setGeometry(button_x, button_y, button_width, button_height)
        self.button_window.setStyleSheet("background-color: yellow; border: 3px solid gray;")
        
        # 创建按钮布局
        button_layout = QHBoxLayout(self.button_window)
        
        # 重新识别按钮
        recognize_btn = QPushButton("重新识别")
        recognize_btn.clicked.connect(self.recognize_area)
        recognize_btn.setStyleSheet("font-family: 'Source Han Sans SC'; font-size: 14px; background-color: lime; color: black; font-weight: bold;")
        button_layout.addWidget(recognize_btn)
        
        # 启用主界面的中止和关闭按钮
        self.abort_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        
        self.border_window.show()
        self.button_window.show()
    
    def recognize_area(self):
        """识别选定区域的文字"""
        if not self.current_region:
            self.status_label.setText("未选择区域")
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
                def update_ui_recognizing():
                    # 计算图像大小
                    buffered = io.BytesIO()
                    screenshot.save(buffered, format="JPEG", quality=75)
                    image_size_kb = len(buffered.getvalue()) / 1024
                    
                    self.status_label.setText("正在识别...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText("识别中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.setText(f"正在识别. . .(图像大小 {image_size_kb:.1f} kb)")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_recognizing()
                
                # 压缩图片
                compressed_image = self.compress_image(screenshot)
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 使用智普AI进行OCR识别
                logger.debug("使用智普AI进行OCR识别")
                text = self.recognize_with_glm(compressed_image)
                logger.debug(f"识别完成，结果: {text[:100]}..." if len(text) > 100 else f"识别完成，结果: {text}")
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 更新UI
                def update_ui_recognized():
                    self.status_label.setText("识别完成，正在翻译...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText("翻译中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.setText("正在翻译 . .")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_recognized()
                
                # 自动翻译识别结果
                self.translate_text(text)
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    return
                
                # 更新UI
                def update_ui_completed():
                    self.status_label.setText("翻译完成")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_completed()
            except Exception as e:
                # 更新UI
                def update_ui_error(e):
                    self.status_label.setText(f"错误: {str(e)}")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText(f"识别失败: {str(e)}")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.setText(f"识别失败: {str(e)}")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_error(e)
                logger.error(f"识别过程出错: {str(e)}")
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
                self.translate_status_label.setText("没有可翻译的文本")
            # 更新翻译窗口文本
            if hasattr(self, 'translate_text_widget'):
                self.translate_text_widget.setText("没有可翻译的文本")
            return
        
        # 启动线程处理AI交互
        def translate_thread():
            try:
                # 设置翻译状态标志
                self.translating = True
                logger.debug("开始翻译文本")
                
                # 更新UI
                def update_ui_translating():
                    self.status_label.setText("正在翻译...")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText("翻译中...")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.setText(f"正在翻译. . .({text[:50]}...")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_translating()
                
                # 使用智普AI进行翻译
                logger.debug("使用智普AI进行翻译")
                translated_text = self.translate_with_glm(text)
                logger.debug(f"翻译完成，结果: {translated_text[:100]}..." if len(translated_text) > 100 else f"翻译完成，结果: {translated_text}")
                
                # 检查是否已中止
                if not self.translating:
                    return
                
                # 更新UI
                def update_ui_translated():
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText("翻译完成")
                    
                    # 自动更新翻译窗口内容
                    if hasattr(self, 'translate_window') and self.translate_window:
                        # 分两行显示，第一行是翻译内容，第二行是原文
                        if hasattr(self, 'translate_text_widget'):
                            self.translate_text_widget.setText(f"{translated_text if translated_text else '翻译失败'}\n\n原文: {text}")
                        self.translate_status_label.setText("翻译完成")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_translated()
            except Exception as e:
                # 更新UI
                def update_ui_error(e):
                    self.status_label.setText(f"翻译错误: {str(e)}")
                    # 更新翻译窗口状态
                    if hasattr(self, 'translate_status_label'):
                        self.translate_status_label.setText(f"翻译失败: {str(e)}")
                    # 更新翻译窗口文本
                    if hasattr(self, 'translate_text_widget'):
                        self.translate_text_widget.setText(f"翻译失败: {str(e)}")
                
                QApplication.instance().postEvent(self, QEvent(QEvent.User))
                update_ui_error(e)
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
    
    def recognize_with_glm(self, image):
        """使用智普AI进行OCR识别"""
        logger.debug("开始智普AI图像识别")
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")
        
        # 检查API客户端
        global zhipu_client
        if zhipu_client is None:
            raise Exception("智普AI客户端未初始化，请检查key.txt文件中的API密钥")
        
        # 将图像转换为base64编码
        logger.debug("将图像转换为base64编码")
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        logger.debug(f"图像base64编码长度: {len(img_str)} 字符")
        
        # 检查是否已中止
        if not self.ai_interaction_active:
            raise Exception("AI交互已中止")
        
        # 发送请求，带智能重试机制
        max_retries = 5  # 增加重试次数
        base_delay = 3  # 基础延迟时间（秒）
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"发送OCR请求到智普AI (尝试 {attempt + 1}/{max_retries})")
                
                response = zhipu_client.chat.completions.create(
                    model="glm-4.6v-flash",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": img_str
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": "请识别图片中的所有文字，保持原始格式和顺序，不要添加任何解释或说明。"
                                }
                            ]
                        }
                    ],
                    thinking={
                        "type": "disabled"
                    }
                )
                
                # 检查是否已中止
                if not self.ai_interaction_active:
                    raise Exception("AI交互已中止")
                
                recognized_text = response.choices[0].message.content
                logger.debug(f"智普AI识别完成，结果: {recognized_text[:100]}..." if len(recognized_text) > 100 else f"智普AI识别完成，结果: {recognized_text}")
                return recognized_text
                    
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
                        raise Exception(f"智普AI请求失败: {error_str}")
    
    def translate_with_glm(self, text):
        """使用智普AI进行翻译"""
        logger.debug("开始智普AI翻译")
        # 检查是否已中止
        if not self.translating:
            raise Exception("翻译已中止")
        
        # 检查API客户端
        global zhipu_client
        if zhipu_client is None:
            raise Exception("智普AI客户端未初始化，请检查key.txt文件中的API密钥")
        
        # 发送请求，带智能重试机制
        max_retries = 5  # 增加重试次数
        base_delay = 3  # 基础延迟时间（秒）
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"发送翻译请求到智普AI (尝试 {attempt + 1}/{max_retries})")
                
                response = zhipu_client.chat.completions.create(
                    model="glm-4.6v-flash",
                    messages=[
                        {
                            "role": "user",
                            "content": f"请将以下文本翻译成中文:\n\n{text}"
                        }
                    ],
                    thinking={
                        "type": "disabled"
                    }
                )
                
                # 检查是否已中止
                if not self.translating:
                    raise Exception("翻译已中止")
                
                translated_text = response.choices[0].message.content
                logger.debug(f"智普AI翻译完成，结果: {translated_text[:100]}..." if len(translated_text) > 100 else f"智普AI翻译完成，结果: {translated_text}")
                return translated_text
                    
            except Exception as e:
                error_str = str(e)
                logger.warning(f"请求错误 (尝试 {attempt + 1}/{max_retries}): {error_str}")
                
                # 检查是否已中止
                if not self.translating:
                    raise Exception("翻译已中止")
                
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
                    else:
                        raise Exception(f"智普AI请求失败: {error_str}")
    
    def border_window_mouse_down(self, event):
        """识别窗口鼠标按下事件"""
        # 检查是否在窗口边缘（用于拉伸）
        edge = self.get_window_edge(self.border_window, event.pos().x(), event.pos().y())
        if edge:
            self.resizing = True
            self.resize_edge = edge
            self.resize_start = event.pos()
        else:
            # 否则开始拖动
            self.dragging = True
            self.drag_start = event.pos()
    
    def border_window_mouse_move(self, event):
        """识别窗口鼠标移动事件"""
        if self.resizing:
            # 执行拉伸
            self.resize_window(self.border_window, event.pos(), self.resize_edge, "border")
        elif self.dragging:
            # 执行拖动
            delta = event.pos() - self.drag_start
            self.move_window(self.border_window, delta.x(), delta.y(), "border")
        else:
            # 检查鼠标是否在窗口边缘，更改光标
            edge = self.get_window_edge(self.border_window, event.pos().x(), event.pos().y())
            if edge:
                cursor = self.get_cursor_for_edge(edge)
            else:
                # 鼠标在窗口内部，显示十字箭头光标
                cursor = Qt.SizeAllCursor
            self.border_window.setCursor(cursor)
    
    def border_window_mouse_up(self, event):
        """识别窗口鼠标释放事件"""
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
    
    def border_window_mouse_leave(self, event):
        """识别窗口鼠标离开事件"""
        self.border_window.setCursor(Qt.ArrowCursor)
    
    def move_window(self, window, delta_x, delta_y, window_type="border"):
        """移动窗口
        window_type: "border" 表示识别区域窗口, "translate" 表示译文窗口
        """
        if not window:
            return
        
        x = window.x() + delta_x
        y = window.y() + delta_y
        width = window.width()
        height = window.height()
        
        # 更新窗口位置
        window.setGeometry(x, y, width, height)
        
        # 只有移动识别区域窗口时才更新按钮窗口位置和当前区域
        if window_type == "border":
            # 更新按钮窗口位置，保持在识别区域上方或下方
            if hasattr(self, 'button_window') and self.button_window:
                button_width = 100
                button_height = 40
                margin = 50
                
                button_x = x + width - button_width
                button_y = y - button_height - 5
                
                screen_height = QApplication.desktop().height()
                
                # 如果上方空间不够，尝试放在下方
                if button_y < margin:
                    button_y = y + height + 5
                    # 如果下方空间也不够，就放在识别区域内顶部
                    if button_y + button_height > screen_height - margin:
                        button_y = y + margin
                        button_x = x + width - button_width - margin
                
                self.button_window.setGeometry(button_x, button_y, button_width, button_height)
            
            # 更新当前区域
            if self.current_region:
                self.current_region = (x, y, width, height)
        elif window_type == "translate":
            # 移动译文窗口时更新翻译区域
            if self.current_translate_region:
                self.current_translate_region = (x, y, width, height)
    
    def resize_window(self, window, pos, edge, window_type="border"):
        """调整窗口大小
        window_type: "border" 表示识别区域窗口, "translate" 表示译文窗口
        """
        if not window:
            return
        
        width = window.width()
        height = window.height()
        window_x = window.x()
        window_y = window.y()
        
        delta_x = pos.x() - self.resize_start.x()
        delta_y = pos.y() - self.resize_start.y()
        
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
        window.setGeometry(new_x, new_y, new_width, new_height)
        
        # 只有调整识别区域窗口时才更新按钮窗口位置和当前区域
        if window_type == "border":
            # 更新按钮窗口位置
            if hasattr(self, 'button_window') and self.button_window:
                button_width = 100
                button_height = 40
                margin = 50
                
                button_x = new_x + new_width - button_width
                button_y = new_y - button_height - 5
                
                screen_height = QApplication.desktop().height()
                
                # 如果上方空间不够，尝试放在下方
                if button_y < margin:
                    button_y = new_y + new_height + 5
                    # 如果下方空间也不够，就放在识别区域内顶部
                    if button_y + button_height > screen_height - margin:
                        button_y = new_y + margin
                        button_x = new_x + new_width - button_width - margin
                
                self.button_window.setGeometry(button_x, button_y, button_width, button_height)
            
            # 更新当前区域
            if self.current_region:
                self.current_region = (new_x, new_y, new_width, new_height)
        elif window_type == "translate":
            # 调整译文窗口时更新翻译区域
            if self.current_translate_region:
                self.current_translate_region = (new_x, new_y, new_width, new_height)
                # 更新文本框的wraplength
                if hasattr(self, 'translate_text_widget'):
                    # 动态调整文本框的宽度限制
                    self.translate_text_widget.setStyleSheet(f"font-family: 'Source Han Sans SC'; font-size: 14px; color: white; padding: 10px;")
    
    def close_border(self):
        """关闭边框窗口和按钮窗口，同时关闭译文窗口"""
        # 先中止AI交互
        self.abort_ai_interaction()
        
        # 关闭识别窗口和按钮窗口
        if hasattr(self, 'border_window') and self.border_window:
            self.border_window.close()
            self.border_window = None
        if hasattr(self, 'button_window') and self.button_window:
            self.button_window.close()
            self.button_window = None
        self.current_region = None
        
        # 关闭译文窗口
        if hasattr(self, 'translate_window') and self.translate_window:
            self.translate_window.close()
            self.translate_window = None
        self.current_translate_region = None
        
        # 禁用识别区域按钮
        self.select_recognize_area_btn.setEnabled(False)
        
        # 禁用主界面的中止和关闭按钮
        self.abort_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        
        self.status_label.setText("所有窗口已关闭")
    
    def translate_window_mouse_down(self, event):
        """翻译窗口鼠标按下事件"""
        # 检查是否在窗口边缘（用于拉伸）
        edge = self.get_window_edge(self.translate_window, event.pos().x(), event.pos().y())
        if edge:
            self.resizing = True
            self.resize_edge = edge
            self.resize_start = event.pos()
        else:
            # 否则开始拖动
            self.dragging = True
            self.drag_start = event.pos()
    
    def translate_window_mouse_move(self, event):
        """翻译窗口鼠标移动事件"""
        if self.resizing:
            # 执行拉伸
            self.resize_window(self.translate_window, event.pos(), self.resize_edge, "translate")
        elif self.dragging:
            # 执行拖动
            delta = event.pos() - self.drag_start
            self.move_window(self.translate_window, delta.x(), delta.y(), "translate")
        else:
            # 检查鼠标是否在窗口边缘，更改光标
            edge = self.get_window_edge(self.translate_window, event.pos().x(), event.pos().y())
            if edge:
                cursor = self.get_cursor_for_edge(edge)
            else:
                # 鼠标在窗口内部，显示十字箭头光标
                cursor = Qt.SizeAllCursor
            self.translate_window.setCursor(cursor)
    
    def translate_window_mouse_up(self, event):
        """翻译窗口鼠标释放事件"""
        self.dragging = False
        self.resizing = False
        self.resize_edge = None
    
    def translate_window_mouse_leave(self, event):
        """翻译窗口鼠标离开事件"""
        self.translate_window.setCursor(Qt.ArrowCursor)
    
    def get_window_edge(self, window, x, y):
        """获取窗口边缘"""
        width = window.width()
        height = window.height()
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
            "nw": Qt.SizeFDiagCursor,
            "sw": Qt.SizeBDiagCursor,
            "ne": Qt.SizeBDiagCursor,
            "se": Qt.SizeFDiagCursor,
            "w": Qt.SizeHorCursor,
            "e": Qt.SizeHorCursor,
            "n": Qt.SizeVerCursor,
            "s": Qt.SizeVerCursor
        }
        return cursor_map.get(edge, Qt.ArrowCursor)
    
    def abort_ai_interaction(self):
        """中止当前的AI交互"""
        # 中止识别交互
        if self.ai_interaction_active:
            self.ai_interaction_active = False
        
        # 中止翻译交互
        if self.translating:
            self.translating = False
        
        # 更新UI
        self.status_label.setText("AI交互已中止")
        if hasattr(self, 'translate_status_label'):
            self.translate_status_label.setText("AI交互已中止")
        if hasattr(self, 'translate_text_widget'):
            self.translate_text_widget.setText("AI交互已中止")
    
    def on_escape(self, event):
        """处理ESC键事件"""
        if hasattr(self, 'select_window') and self.select_window:
            self.select_window.close()
            self.select_window = None
        if hasattr(self, 'translate_select_window') and self.translate_select_window:
            self.translate_select_window.close()
            self.translate_select_window = None
        self.status_label.setText("选择已取消")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScreenTranslatorApp()
    window.show()
    sys.exit(app.exec_())
