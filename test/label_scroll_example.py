import tkinter as tk

# 创建窗口
root = tk.Tk()
root.title("可滚动的Label（纯展示+全窗口滚轮支持）")
root.geometry("300x200")

# --------------------------
# 核心：可滚动 Label 组件（隐藏滚动条 + 全窗口滚轮支持）
# --------------------------
# 1. 创建一个画布（用来承载滚动）
canvas = tk.Canvas(root)
canvas.pack(side="left", fill="both", expand=True)

# 2. 隐藏滚动条（不创建滚动条）
# 注：我们不需要滚动条，只通过滚轮控制

# 3. 绑定滚动（修复原滚动区域更新问题）
def update_scrollregion(event=None):
    canvas.configure(scrollregion=canvas.bbox("all"))
canvas.bind('<Configure>', update_scrollregion)

# 4. 新增：全窗口滚轮滚动逻辑（兼容Windows/Mac/Linux）
def on_mouse_wheel(event):
    # Windows/Linux：event.delta 是120的倍数；Mac：event.delta 是1的倍数（反向）
    delta = event.delta
    if event.num == 4 or event.delta > 0:  # 向上滚动
        canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:  # 向下滚动
        canvas.yview_scroll(1, "units")

# 绑定滚轮事件到整个窗口（不同系统事件名不同，全绑定确保兼容）
root.bind("<MouseWheel>", on_mouse_wheel)  # Windows/Mac 新版
root.bind("<Button-4>", on_mouse_wheel)    # Linux 向上
root.bind("<Button-5>", on_mouse_wheel)    # Linux 向下

# 4. 在画布内放一个 **真正的 Label**
inner_frame = tk.Frame(canvas)
canvas.create_window((0, 0), window=inner_frame, anchor="nw")

# 长文本Label
long_text = """这是一段非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的文本
我是 Label
我不能编辑
我没有光标
我可以滚动（全窗口滚轮支持）
完美符合你的要求！"""

label = tk.Label(
    inner_frame, 
    text=long_text,
    wraplength=280,  # 自动换行（关键）
    justify="left",  # 左对齐
    anchor="nw"      # 靠左上角显示
)
label.pack(fill="both", expand=True, padx=5, pady=5)

# 初始化时强制更新一次滚动区域（避免初始无滚动）
root.after(100, update_scrollregion)

root.mainloop()