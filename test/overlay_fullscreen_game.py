# -*- coding: utf-8 -*-
import tkinter as tk
import ctypes
import time
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010

WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

GWL_EXSTYLE = -20


def set_window_topmost(hwnd):
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
    )


def get_window_exstyle(hwnd):
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def set_window_exstyle(hwnd, exstyle):
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)


class OverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("全屏游戏悬浮测试")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 400
        window_height = 200
        x = (screen_width - window_width) // 2
        y = 50
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.85)
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.force_topmost = True
        self.topmost_thread = None
        self.running = True
        
        self._create_ui()
        self._apply_winapi_overlay()
        self._start_topmost_thread()
        
    def _create_ui(self):
        self.frame = tk.Frame(self.root, bg='black', bd=2, relief='solid')
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.title_label = tk.Label(
            self.frame, 
            text="全屏游戏悬浮窗口测试", 
            bg='black', 
            fg='lime', 
            font=("Arial", 14, "bold")
        )
        self.title_label.pack(pady=10)
        
        self.info_label = tk.Label(
            self.frame,
            text="该窗口应该可以悬浮在全屏游戏上方\n按 ESC 关闭",
            bg='black',
            fg='white',
            font=("Arial", 10)
        )
        self.info_label.pack(pady=5)
        
        self.status_label = tk.Label(
            self.frame,
            text="状态: 运行中",
            bg='black',
            fg='cyan',
            font=("Arial", 9)
        )
        self.status_label.pack(pady=5)
        
        self.frame.bind('<Button-1>', self._start_drag)
        self.frame.bind('<B1-Motion>', self._on_drag)
        self.title_label.bind('<Button-1>', self._start_drag)
        self.title_label.bind('<B1-Motion>', self._on_drag)
        
        self.root.bind('<Escape>', lambda e: self._close())
        
    def _apply_winapi_overlay(self):
        hwnd = int(self.root.winfo_id())
        
        exstyle = get_window_exstyle(hwnd)
        exstyle |= WS_EX_TOPMOST
        exstyle |= WS_EX_TOOLWINDOW
        exstyle |= WS_EX_NOACTIVATE
        set_window_exstyle(hwnd, exstyle)
        
        set_window_topmost(hwnd)
        
    def _start_topmost_thread(self):
        def topmost_loop():
            while self.running:
                try:
                    if self.force_topmost:
                        hwnd = int(self.root.winfo_id())
                        set_window_topmost(hwnd)
                except Exception:
                    pass
                time.sleep(0.1)
        
        self.topmost_thread = threading.Thread(target=topmost_loop, daemon=True)
        self.topmost_thread.start()
        
    def _start_drag(self, event):
        self.drag_start_x = event.x_root - self.root.winfo_x()
        self.drag_start_y = event.y_root - self.root.winfo_y()
        
    def _on_drag(self, event):
        x = event.x_root - self.drag_start_x
        y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")
        
    def _close(self):
        self.running = False
        self.root.destroy()
        
    def run(self):
        self.root.mainloop()


class AdvancedOverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("高级全屏游戏悬浮测试")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 300
        window_height = 150
        x = screen_width - window_width - 50
        y = screen_height - window_height - 100
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.force_topmost = True
        self.running = True
        
        self._create_ui()
        self._apply_advanced_style()
        self._start_keep_top()
        
    def _create_ui(self):
        self.frame = tk.Frame(self.root, bg='#1a1a2e', bd=0)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        header = tk.Frame(self.frame, bg='#16213e', height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(
            header, 
            text="游戏悬浮层", 
            bg='#16213e', 
            fg='#e94560', 
            font=("Arial", 11, "bold")
        )
        title.pack(side=tk.LEFT, padx=10, pady=5)
        
        close_btn = tk.Label(
            header,
            text="×",
            bg='#16213e',
            fg='white',
            font=("Arial", 14, "bold"),
            cursor='hand2'
        )
        close_btn.pack(side=tk.RIGHT, padx=10)
        close_btn.bind('<Button-1>', lambda e: self._close())
        
        content = tk.Frame(self.frame, bg='#1a1a2e')
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.text_label = tk.Label(
            content,
            text="按 F1 切换置顶\n按 ESC 关闭\n可拖拽移动",
            bg='#1a1a2e',
            fg='white',
            font=("Arial", 10),
            justify=tk.LEFT
        )
        self.text_label.pack(anchor=tk.W)
        
        self.status_label = tk.Label(
            content,
            text="置顶: 开启",
            bg='#1a1a2e',
            fg='#00ff88',
            font=("Arial", 9)
        )
        self.status_label.pack(anchor=tk.W, pady=(10, 0))
        
        header.bind('<Button-1>', self._start_drag)
        header.bind('<B1-Motion>', self._on_drag)
        title.bind('<Button-1>', self._start_drag)
        title.bind('<B1-Motion>', self._on_drag)
        
        self.root.bind('<Escape>', lambda e: self._close())
        self.root.bind('<F1>', lambda e: self._toggle_topmost())
        
    def _apply_advanced_style(self):
        hwnd = int(self.root.winfo_id())
        
        exstyle = get_window_exstyle(hwnd)
        exstyle |= WS_EX_TOPMOST
        exstyle |= WS_EX_TOOLWINDOW
        exstyle |= WS_EX_NOACTIVATE
        set_window_exstyle(hwnd, exstyle)
        
        set_window_topmost(hwnd)
        
    def _start_keep_top(self):
        def keep_top():
            while self.running:
                try:
                    if self.force_topmost:
                        hwnd = int(self.root.winfo_id())
                        set_window_topmost(hwnd)
                        
                        exstyle = get_window_exstyle(hwnd)
                        if not (exstyle & WS_EX_TOPMOST):
                            exstyle |= WS_EX_TOPMOST
                            set_window_exstyle(hwnd, exstyle)
                except Exception:
                    pass
                time.sleep(0.05)
        
        thread = threading.Thread(target=keep_top, daemon=True)
        thread.start()
        
    def _toggle_topmost(self):
        self.force_topmost = not self.force_topmost
        if self.force_topmost:
            hwnd = int(self.root.winfo_id())
            set_window_topmost(hwnd)
            self.status_label.config(text="置顶: 开启", fg='#00ff88')
        else:
            hwnd = int(self.root.winfo_id())
            user32.SetWindowPos(
                hwnd,
                HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
            self.status_label.config(text="置顶: 关闭", fg='#ff6b6b')
            
    def _start_drag(self, event):
        self.drag_start_x = event.x_root - self.root.winfo_x()
        self.drag_start_y = event.y_root - self.root.winfo_y()
        
    def _on_drag(self, event):
        x = event.x_root - self.drag_start_x
        y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")
        
    def _close(self):
        self.running = False
        self.root.destroy()
        
    def run(self):
        self.root.mainloop()


class TransparentTextOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("透明文字悬浮层")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 500
        window_height = 120
        x = (screen_width - window_width) // 2
        y = screen_height - window_height - 80
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.running = True
        
        self._create_ui()
        self._apply_overlay_style()
        self._start_keep_top()
        
    def _create_ui(self):
        self.frame = tk.Frame(self.root, bg='black')
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_label = tk.Label(
            self.frame,
            text="这是一条测试翻译文本\nThis is a test translation text",
            bg='black',
            fg='white',
            font=("Microsoft YaHei", 16, "bold"),
            justify=tk.CENTER,
            wraplength=480
        )
        self.text_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.frame.bind('<Button-1>', self._start_drag)
        self.frame.bind('<B1-Motion>', self._on_drag)
        self.text_label.bind('<Button-1>', self._start_drag)
        self.text_label.bind('<B1-Motion>', self._on_drag)
        
        self.root.bind('<Escape>', lambda e: self._close())
        
    def _apply_overlay_style(self):
        hwnd = int(self.root.winfo_id())
        
        exstyle = get_window_exstyle(hwnd)
        exstyle |= WS_EX_TOPMOST
        exstyle |= WS_EX_TOOLWINDOW
        exstyle |= WS_EX_NOACTIVATE
        set_window_exstyle(hwnd, exstyle)
        
        set_window_topmost(hwnd)
        
    def _start_keep_top(self):
        def keep_top():
            while self.running:
                try:
                    hwnd = int(self.root.winfo_id())
                    set_window_topmost(hwnd)
                except Exception:
                    pass
                time.sleep(0.05)
        
        thread = threading.Thread(target=keep_top, daemon=True)
        thread.start()
            
    def _start_drag(self, event):
        self.drag_start_x = event.x_root - self.root.winfo_x()
        self.drag_start_y = event.y_root - self.root.winfo_y()
        
    def _on_drag(self, event):
        x = event.x_root - self.drag_start_x
        y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")
        
    def _close(self):
        self.running = False
        self.root.destroy()
        
    def run(self):
        self.root.mainloop()


def main():
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        print("请选择要运行的窗口类型:")
        print("1. 基础悬浮窗口 (OverlayWindow)")
        print("2. 高级悬浮窗口 (AdvancedOverlayWindow)")
        print("3. 透明文字悬浮层 (TransparentTextOverlay)")
        print("直接输入数字或类名:")
        choice = input().strip()
        
        if choice == '1' or choice.lower() == 'overlaywindow':
            mode = 'basic'
        elif choice == '2' or choice.lower() == 'advancedoverlaywindow':
            mode = 'advanced'
        elif choice == '3' or choice.lower() == 'transparenttextoverlay':
            mode = 'text'
        else:
            mode = 'advanced'
    
    if mode == 'basic':
        app = OverlayWindow()
    elif mode == 'text':
        app = TransparentTextOverlay()
    else:
        app = AdvancedOverlayWindow()
    
    print(f"运行模式: {mode}")
    print("按 ESC 关闭窗口")
    app.run()


if __name__ == '__main__':
    main()
