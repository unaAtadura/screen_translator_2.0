---
kind: frontend_style
name: Tkinter 原生样式与硬编码主题风格
category: frontend_style
scope:
    - '**'
source_files:
    - screen_translator_with_qwen.py
---

本项目为基于 Python + Tkinter 的桌面应用，前端样式完全依赖 Tkinter 原生控件，未引入任何 CSS/SCSS/Tailwind 等外部样式系统或第三方 UI 框架。所有视觉表现通过组件构造参数直接硬编码实现，具体特征如下：

1. **样式方式**：全部使用 `tk.Button`、`tk.Label`、`tk.Text`、`scrolledtext.ScrolledText` 等原生控件，通过构造函数参数 `font=`、`bg=`、`fg=`、`bd=`、`relief=`、`padx=`、`pady=` 等内联指定外观，未见 `ttk.Style` 或 `tk.Style` 全局主题配置。

2. **配色方案**：采用深色主题（dark theme）风格，主背景色统一为 `#1e1e1e`，前景文字为 `#d4d4d4` / `#E0E0E0`；按钮使用语义化颜色区分功能——发送/确认用蓝色系（`#0078D4`、`#1565C0`）、成功/捕获用绿色（`#2E7D32`、`lime`）、关闭/危险用红色（`red`）、中止用橙色（`orange`），聊天标签使用 Material Design 调色板（`#4FC3F7` 用户、`#81C784` AI、`#FFB74D` 系统）。

3. **字体策略**：英文标题使用 `Arial`，中文正文使用 `Microsoft YaHei`，日志输出使用等宽 `Consolas`，字号集中在 8–14pt 之间，加粗仅用于标题和角色标识行。

4. **透明度与窗口效果**：通过 `wm_attributes('-alpha', 0.9)` 控制半透明覆盖层，`overrideredirect(True)` 去除标题栏创建无边框浮动窗口，配合 `-topmost` 置顶显示，形成“屏幕叠加层”式的交互体验。

5. **布局组织**：以 `pack()` 为主进行垂直/水平堆叠布局，辅以 `Frame` 容器分组，无网格或绝对定位；响应式能力有限，主要依赖 `fill=tk.BOTH, expand=True` 自适应填充。

6. **设计令牌缺失**：颜色、字体、间距等视觉常量散落在各方法内部，未提取到集中配置文件或类级常量区，导致同一值（如 `#1e1e1e`、`Arial`、`10`）在多处重复出现，缺乏统一的设计令牌体系。

综上，该项目不存在独立的前端样式系统，属于典型的「代码即样式」模式，适合小型工具型应用，但可维护性和主题切换能力较弱。