import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QScrollArea
from PyQt5.QtCore import Qt, QPoint

class TransparentDragWindow(QWidget):
    def __init__(self):
        super().__init__()

        # ========== 基础窗口设置 ==========
        self.setWindowTitle("透明文本窗口")
        self.setGeometry(100, 100, 380, 320)  # 窗口大小

        # ========== 核心：透明（不会黑屏、不会消失） ==========
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  # 置顶+无边框

        # ========== 拖拽变量 ==========
        self.m_drag = False
        self.m_dragPosition = QPoint()

        # ========== 滚动区域（无滚动条） ==========
        scroll_area = QScrollArea(self)
        scroll_area.setGeometry(10, 10, 360, 300)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: rgba(0,0,0,0);
                border: none;
            }
        """)

        # 内容容器
        container = QWidget()
        scroll_area.setWidget(container)

        # ========== 长文本 Label ==========
        long_text = """这是一段非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的文本
我是 PyQt5 Label
我不能编辑
我没有光标
我可以滚轮滚动
完全隐藏滚动条
背景100%透明
支持鼠标拖拽移动窗口
完美匹配你的需求！"""

        label = QLabel(long_text, container)
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                padding: 8px;
            }
        """)
        label.setAlignment(Qt.AlignTop)

    # ========== 拖拽功能 ==========
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_dragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.m_drag:
            self.move(event.globalPos() - self.m_dragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False

    # ========== 滚轮滚动 ==========
    def wheelEvent(self, event):
        scroll = self.findChild(QScrollArea)
        bar = scroll.verticalScrollBar()
        delta = event.angleDelta().y()
        step = 40
        if delta > 0:
            bar.setValue(bar.value() - step)
        else:
            bar.setValue(bar.value() + step)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 高分屏适配（防止窗口消失）
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    window = TransparentDragWindow()
    window.show()
    sys.exit(app.exec_())
