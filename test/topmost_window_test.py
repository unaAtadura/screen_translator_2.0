# -*- coding: utf-8 -*-
import tkinter as tk


class TopMostWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("始终置顶窗口测试")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = 300
        window_height = 150
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        self.root.attributes('-topmost', True)
        
        self._create_ui()
        
        self._schedule_keep_topmost()
        
    def _create_ui(self):
        frame = tk.Frame(self.root, bg='#2d3436')
        frame.pack(fill=tk.BOTH, expand=True)
        
        title = tk.Label(
            frame,
            text="始终置顶窗口",
            bg='#2d3436',
            fg='#00cec9',
            font=("Microsoft YaHei", 14, "bold")
        )
        title.pack(pady=10)
        
        info = tk.Label(
            frame,
            text="这个窗口始终显示在最顶层\n按 ESC 关闭",
            bg='#2d3436',
            fg='white',
            font=("Microsoft YaHei", 10)
        )
        info.pack(pady=5)
        
        self.status_label = tk.Label(
            frame,
            text="状态: 置顶中",
            bg='#2d3436',
            fg='#55efc4',
            font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(pady=5)
        
        btn_frame = tk.Frame(frame, bg='#2d3436')
        btn_frame.pack(pady=5)
        
        close_btn = tk.Button(
            btn_frame,
            text="关闭",
            command=self._close,
            bg='#e17055',
            fg='white',
            font=("Microsoft YaHei", 10),
            padx=20,
            relief=tk.FLAT
        )
        close_btn.pack()
        
        self.root.bind('<Escape>', lambda e: self._close())
        
    def _schedule_keep_topmost(self):
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.after(100, self._schedule_keep_topmost)
        
    def _close(self):
        self.root.destroy()
        
    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = TopMostWindow()
    app.run()
