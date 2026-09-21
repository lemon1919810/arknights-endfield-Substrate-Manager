import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from collections import Counter

# ================= 核心路径适配 =================
if getattr(sys, 'frozen', False):
    # 如果是被 PyInstaller 打包成了 exe，使用 exe 所在的真实目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 如果是直接运行 Python 脚本，使用脚本所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        messagebox.showerror("文件错误", f"找不到文件：{filename}\n\n请确认它和 main.py 在同一个文件夹。")
        raise

attributes_data = load_json("attributes.json")
weapons_data = load_json("weapons.json")
regions_data = load_json("regions.json")
builds_data = load_json("builds.json")


# ================= 新增：用户配置管理 =================
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    """读取用户配置，如果文件不存在则生成默认配置"""
    default_cfg = {
        "history": [], 
        "sort_mode": "strategic", 
        "region_sort_mode": "yield",
        "perfect_mode": "custom",     # 【修改】默认直接启用“自定义模式”
        "perfect_score": 7,           
        "perfect_custom": [6, 6, 3],  # 【修改】默认值直接定为 6/6/3
        "perfect_count": 2
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k, v in default_cfg.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
        except Exception:
            pass
    return default_cfg

global_config = load_config()

def save_config(config_data):
    """保存用户配置到本地"""
    global global_config
    global_config.update(config_data)  # 同步更新全局内存
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"配置文件保存失败: {e}")
# ====================================================

weapons = weapons_data.get("weapons", [])
regions = regions_data.get("regions", [])
builds = builds_data.get("builds", [])
weapon_by_name = {w["name"]: w for w in weapons}
build_by_triple = {(x.get("main", ""), x.get("sub", ""), x.get("skill", "")): x.get("beads", []) for x in builds}

def triple(w):
    a = w.get("attributes", {})
    return a.get("主词条", ""), a.get("副词条", ""), a.get("技能", "")

def rarity_text(r):
    return {6: "★6", 5: "★5", 4: "★4"}.get(r, "")

def rarity_tag(r):
    return {6: "rarity6", 5: "rarity5", 4: "rarity4"}.get(r, "rarity")

# def bead_count(w):
#     return len(build_by_triple.get(triple(w), [])) or "—"

def best_beads_text(w):
    beads = build_by_triple.get(triple(w), [])
    if not beads:
        return "—"
    
    # 按照 main + sub + skill 的总和降序排序，选出“最佳数值”
    sorted_beads = sorted(
        beads, 
        key=lambda b: b.get("main", 0) + b.get("sub", 0) + b.get("skill", 0), 
        reverse=True
    )
    
    # 截取前三个，并格式化为 "主/副/技" 的形式
    top_3 = sorted_beads[:3]
    formatted = [f"{b.get('main', 0)}/{b.get('sub', 0)}/{b.get('skill', 0)}" for b in top_3]

    return " | ".join(formatted)


def can_farm(region, w):
    _, sub, skill = triple(w)
    return sub in region.get("sub_attributes", []) and skill in region.get("skills", [])

def regions_for(w, sort_mode="default"):
    rs = [r for r in regions if can_farm(r, w)]
    
    if sort_mode == "yield":
        main, sub, skill = triple(w)
        def get_yield(r):
            # 收益 = 锁定副词条可歪出的武器数 + 锁定技能可歪出的武器数
            c_sub = len(strategy_weapons(r, "sub", sub))
            c_skill = len(strategy_weapons(r, "skill", skill))
            return c_sub + c_skill
            
        # 按照 收益总和(降序) -> 地区名称 排序
        rs.sort(key=lambda r: (-get_yield(r), r["name"]))
    return rs

def strategy_weapons(region, lock_type, value, target_main="", sort_mode="strategic"):
    result = []
    
    # 【修改】同步默认值，确保就算配置文件丢失，底层计算也会默认按 custom 和 6/3/3 拦截
    perf_mode = global_config.get("perfect_mode", "custom")
    perf_score = global_config.get("perfect_score", 7)
    perf_custom = global_config.get("perfect_custom", [6, 6, 3])
    perf_count = global_config.get("perfect_count", 2)
    
    for w in weapons:
        main, sub, skill = triple(w)
        
        # ================== 双模式毕业拦截系统 ==================
        if perf_mode != "none":
            beads = build_by_triple.get((main, sub, skill), [])
            perfects = 0
            
            for b in beads:
                m, s, sk = b.get("main", 0), b.get("sub", 0), b.get("skill", 0)
                
                if perf_mode == "score":
                    if m + s + (sk * 2) >= perf_score:
                        perfects += 1
                elif perf_mode == "custom":
                    if m >= perf_custom[0] and s >= perf_custom[1] and sk >= perf_custom[2]:
                        perfects += 1
                        
            if perfects >= perf_count:
                continue 
        # ==========================================================

        if sub not in region.get("sub_attributes", []) or skill not in region.get("skills", []):
            continue
        if lock_type == "sub" and sub != value:
            continue
        if lock_type == "skill" and skill != value:
            continue
        result.append(w)
        
    if sort_mode == "strategic":
        main_counts = Counter(triple(w)[0] for w in result)
        result.sort(key=lambda w: (
            0 if triple(w)[0] == target_main else 1,
            -main_counts.get(triple(w)[0], 0),
            triple(w)[0],
            -(w.get("rarity") or 0),
            w.get("name", "")
        ))
    else:
        result.sort(key=lambda w: (
            -(w.get("rarity") or 0),
            triple(w)[0], 
            w.get("name", "")
        ))
        
    return result


def top_3_beads_tuple(w):
    # 获取该武器所有胚子组合
    beads = build_by_triple.get(triple(w), [])
    
    # 按数值总和降序排序
    sorted_beads = sorted(
        beads, 
        key=lambda b: b.get("main", 0) + b.get("sub", 0) + b.get("skill", 0), 
        reverse=True
    )
    
    res = []
    # 提取前三个
    for b in sorted_beads[:3]:
        res.append(f"{b.get('main',0)}/{b.get('sub',0)}/{b.get('skill',0)}")
        
    # 如果不足三个，用 "—" 补齐
    while len(res) < 3:
        res.append("—")
        
    return tuple(res)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # 【新增】程序启动时，加载用户配置
        self.user_config = load_config() 
        
        self.title("基质珠子筛选器")
        self.geometry("1100x800")
        self.minsize(900, 600)
        self.configure(bg="#f4f5f7")
        self.setup_style()
        self.build_ui()
        self.current_weapon = None

        self.default_sort_mode = "strategic"

    def _create_primary_btn(self, parent, text, command):
        """生成现代 Web 风格的扁平化操作按钮"""
        btn = tk.Label(
            parent, text=text,
            bg="#0066cc", fg="#ffffff",
            font=("Microsoft YaHei UI", 11, "bold"),
            cursor="hand2", padx=24, pady=10
        )
        # 绑定鼠标悬浮变色
        btn.bind("<Enter>", lambda e: btn.config(bg="#0055aa"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#0066cc"))
        # 绑定左键点击事件
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def _create_secondary_btn(self, parent, text, command):
        """生成次级操作按钮（灰色，用于不抢眼的辅助功能）"""
        btn = tk.Label(
            parent, text=text,
            bg="#e2e6ea", fg="#1d1d1f",
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2", padx=16, pady=8
        )
        btn.bind("<Enter>", lambda e: btn.config(bg="#d2d6da"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#e2e6ea"))
        btn.bind("<Button-1>", lambda e: command())
        return btn


    def setup_style(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except tk.TclError: pass
        
        bg_color = "#f0f2f5"
        card_bg = "#ffffff"
        text_primary = "#1d1d1f"
        text_secondary = "#6e6e73"
        accent_color = "#0066cc"
        accent_hover = "#0055aa"
        
        s.configure("App.TFrame", background=bg_color)
        s.configure("Card.TFrame", background=card_bg)
        
        # 【修改】全面提升各级文本的字号 (例如 20->22, 12->14, 10->11)
        s.configure("Title.TLabel", background=bg_color, foreground=text_primary, font=("Microsoft YaHei UI", 22, "bold"))
        s.configure("SubTitle.TLabel", background=bg_color, foreground=text_secondary, font=("Microsoft YaHei UI", 11))
        s.configure("CardTitle.TLabel", background=card_bg, foreground=text_primary, font=("Microsoft YaHei UI", 14, "bold"))
        s.configure("CardText.TLabel", background=card_bg, foreground=text_secondary, font=("Microsoft YaHei UI", 11))
        
        s.configure("Primary.TButton", font=("Microsoft YaHei UI", 11, "bold"), 
                    padding=(16, 8), background=accent_color, foreground="#ffffff", borderwidth=0)
        s.map("Primary.TButton", background=[("active", accent_hover)])
        
        # 次级窗口的表格字号也略微调大一点，行高拉大
        s.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), background="#f8f9fa", foreground="#333")
        s.map("Treeview.Heading", background=[("active", "#e2e6ea")])

    def build_ui(self):
        root = ttk.Frame(self, style="App.TFrame", padding=20)
        root.pack(fill="both", expand=True)

        # ================= 顶部标题与数据管理入口 =================
        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x")
        
        title_box = ttk.Frame(header, style="App.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="基质珠子筛选器", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="输入目标武器，查看可刷地区，再对比“锁定副词条”和“锁定技能”两种刷取方式。", style="SubTitle.TLabel").pack(anchor="w", pady=(4, 16))
        
        btn_box = tk.Frame(header, bg="#f0f2f5")
        btn_box.pack(side="right", anchor="n", pady=(10, 0))
        
        self._create_secondary_btn(btn_box, "⚙️ 全局配置", self.open_settings).pack(side="right", padx=(10, 0))
        self._create_secondary_btn(btn_box, "✚ 录入新数据", self.open_data_manager).pack(side="right", padx=(10, 0))
        self._create_secondary_btn(btn_box, "📚 全武器胚子管理", self.open_all_weapons_manager).pack(side="right")
        # 搜索区域
        search = ttk.Frame(root, style="Card.TFrame", padding=16)
        search.pack(fill="x", pady=(0, 14))



        ttk.Label(search, text="目标武器", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.all_weapon_names = [w["name"] for w in weapons]
        self.weapon_var = tk.StringVar()

        self.weapon_entry = ttk.Entry(search, textvariable=self.weapon_var, font=("Microsoft YaHei UI", 11), width=38)
        self.weapon_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(7, 0))
        
        self.suggestion_list = tk.Listbox(self, font=("Microsoft YaHei UI", 11), bg="#ffffff", fg="#1d1d1f",
                                          selectbackground="#0066cc", selectforeground="#ffffff",
                                          borderwidth=1, relief="solid", cursor="hand2")
        
        self.weapon_entry.bind("<Return>", lambda e: self.search())
        self.weapon_entry.bind("<KeyRelease>", self.on_weapon_input)
        self.weapon_entry.bind("<Down>", self.on_down_arrow)
        self.suggestion_list.bind("<ButtonRelease-1>", self.on_suggestion_select)
        self.suggestion_list.bind("<Return>", self.on_suggestion_select)
        self.suggestion_list.bind("<Up>", self.on_up_arrow)
        self.bind("<Button-1>", self.hide_suggestion_list, add="+")
        
        self._create_primary_btn(search, "查询", self.search).grid(row=1, column=1, pady=(7, 0), padx=(10, 0))
        search.columnconfigure(0, weight=1)
        self.status = tk.StringVar(value="请输入武器名称")
        ttk.Label(search, textvariable=self.status, style="CardText.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(9, 0))

        self.history_frame = tk.Frame(search, bg="#ffffff")
        self.history_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.refresh_history_ui()

# ================= 3. 下半部分：左右分栏 =================
        body = ttk.Frame(root, style="App.TFrame")
        body.pack(fill="both", expand=True)
        
        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="y")
        
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        
        # --- 左侧：地区列表与排序头部 ---
        left_header = tk.Frame(left, bg="#ffffff")
        left_header.pack(fill="x", pady=(0, 10))
        
        ttk.Label(left_header, text="可刷地区", style="CardTitle.TLabel").pack(side="left")
        
        # 【新增】左侧列表的排序切换按钮
        self.region_sort_btn = tk.Label(left_header, text="▼ 默认排序", fg="#6e6e73", bg="#ffffff", font=("Microsoft YaHei UI", 10, "underline"), cursor="hand2")
        self.region_sort_btn.pack(side="right", pady=(2, 0))
        self.region_sort_btn.bind("<Button-1>", lambda e: self.toggle_region_sort())
        
        self.region_list = tk.Listbox(left, width=28, font=("Microsoft YaHei UI", 11), activestyle="none", borderwidth=0, highlightthickness=0, bg="#ffffff", fg="#1d1d1f", selectbackground="#0066cc", selectforeground="#ffffff")
        self.region_list.pack(fill="both", expand=True)
        self.region_list.bind("<<ListboxSelect>>", self.region_selected)
        self.region_list.bind("<Double-1>", self.open_selected_region)

# --- 右侧：详情与标签框 ---
        self.detail_title = tk.StringVar(value="选择一个地区")
        ttk.Label(right, textvariable=self.detail_title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        
        self.tags_container = tk.Frame(right, bg="#ffffff")
        self.tags_container.pack(fill="both", expand=True)
        
        self.show_default_right_panel("查询武器后，从左侧选择一个地区。")

        # ================= 底部专属署名 =================
        signature_lbl = tk.Label(
            self, text="Designed by lemon冷梦 1009129647 | v1.0", # 这里改成你自己的名字或ID
            bg="#f0f2f5", fg="#b0b0b5",              # 使用低对比度的浅灰色，高级且不喧宾夺主
            font=("Microsoft YaHei UI", 12)
        )
        # 使用绝对定位，锚定在右下角 (se: South-East)
        signature_lbl.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-10)



    def show_default_right_panel(self, text):
        for widget in self.tags_container.winfo_children():
            widget.destroy()
        ttk.Label(self.tags_container, text=text, style="CardText.TLabel").pack(anchor="w", pady=(6, 14))

    def toggle_region_sort(self):
        """切换左侧地区的排序策略并保存到配置"""
        current_mode = self.user_config.get("region_sort_mode", "default")
        new_mode = "yield" if current_mode == "default" else "default"
        self.user_config["region_sort_mode"] = new_mode
        save_config(self.user_config)
        self.refresh_region_list()

    def refresh_region_list(self):
        """重新渲染左侧地区列表"""
        if not self.current_weapon: return
        self.region_list.delete(0, tk.END)
        
        mode = self.user_config.get("region_sort_mode", "default")
        if mode == "yield":
            self.region_sort_btn.config(text="▼ 收益优先", fg="#0066cc")
        else:
            self.region_sort_btn.config(text="▼ 默认排序", fg="#6e6e73")
            
        rs = regions_for(self.current_weapon, sort_mode=mode)
        for r in rs: self.region_list.insert(tk.END, r["name"])
        
        if rs:
            self.region_list.selection_set(0)
            self.region_list.activate(0)
            self.region_selected()
        else:
            self.detail_title.set("没有找到可刷地区")
            self.show_default_right_panel("该武器在所有地区均无掉落。")

    def on_weapon_input(self, event):
        # 排除方向键、回车键等控制按键，防止干扰选择
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"):
            return
            
        # 记录当前光标位置
        cursor_pos = self.combo.index(tk.INSERT)
        typed_text = self.weapon_var.get().strip().lower()
        
        if not typed_text:
            self.combo["values"] = self.all_weapon_names
        else:
            filtered = [name for name in self.all_weapon_names if typed_text in name.lower()]
            self.combo["values"] = filtered
            
        # 【核心修改】将下拉和夺回焦点的逻辑打包成一个独立函数
        def post_and_focus():
            try:
                # 1. 弹出下拉列表
                self.combo.tk.call('ttk::combobox::Post', self.combo)
                # 2. 强行夺回输入框的焦点
                self.combo.focus_set()
                # 3. 恢复光标到刚刚打字的位置
                self.combo.icursor(cursor_pos)
                # 4. 清除可能产生的文本全选/高亮现象
                self.combo.selection_clear()
            except tk.TclError:
                pass
                
        # 延迟 20 毫秒执行，等待系统底层彻底完成下拉菜单的渲染后再抢回焦点
        self.combo.after(20, post_and_focus)


    def search(self):
        if hasattr(self, 'suggestion_list'):
            self.suggestion_list.place_forget()

        name = self.weapon_var.get().strip()
        w = weapon_by_name.get(name)
        if w is None:
            matches = [x for x in weapons if name and name.lower() in x["name"].lower()]
            if len(matches) == 1:
                w = matches[0]; self.weapon_var.set(w["name"])
            elif matches:
                messagebox.showinfo("找到多个武器", "请从下拉框选择具体武器：\n\n" + "\n".join(x["name"] for x in matches[:12])); return
            else:
                messagebox.showwarning("未找到武器", f"没有找到“{name}”。"); return

        # ================= 新增：记录搜索历史 =================
        hist = self.user_config.setdefault("history", [])
        actual_name = w["name"]
        if actual_name in hist:
            hist.remove(actual_name)# 如果已经搜过，先移出
        hist.insert(0, actual_name)# 插入到最新的第一位
        if len(hist) > 6:# 最多只保留最新 6 条记录
            hist.pop()
        save_config(self.user_config)
        self.refresh_history_ui()# 更新主界面 UI
        # ====================================================
        self.current_weapon = w
        main, sub, skill = triple(w)
        self.status.set(f"目标：{w['name']}   {rarity_text(w.get('rarity'))}   {main} / {sub} / {skill}")
        
        # 然后再调用刷新列表
        self.refresh_region_list()





    def on_weapon_input(self, event):
        # 排除控制键，防止在打字期间产生干扰
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
            
        typed_text = self.weapon_var.get().strip().lower()
        if not typed_text:
            self.suggestion_list.place_forget()
            return
            
        # 模糊过滤
        filtered = [name for name in self.all_weapon_names if typed_text in name.lower()]
        
        if filtered:
            self.suggestion_list.delete(0, tk.END)
            # 最多显示 8 条，避免列表过长显得累赘
            for name in filtered[:8]:
                self.suggestion_list.insert(tk.END, name)
                
            # 动态调整列表高度
            self.suggestion_list.config(height=min(len(filtered), 8))
            
            # 【核心黑科技】使用 place 布局，让列表像幽灵一样绝对定位在输入框的正下方！
            self.suggestion_list.place(in_=self.weapon_entry, x=0, rely=1.0, relwidth=1.0)
            self.suggestion_list.lift()
        else:
            self.suggestion_list.place_forget()

    def on_down_arrow(self, event):
        # 当联想框显示时，如果在输入框按【向下箭头】，自动把焦点交给联想框的第一项
        if self.suggestion_list.winfo_ismapped():
            self.suggestion_list.focus_set()
            self.suggestion_list.selection_set(0)
            return "break" # 阻止输入框光标乱动
        
    def on_up_arrow(self, event):
        sel = self.suggestion_list.curselection()
        # 如果当前有选中项，且正好是列表的第一项（索引为0）
        if sel and sel[0] == 0:
            # 1. 焦点强行退回输入框
            self.weapon_entry.focus_set()
            # 2. 将输入框的光标移到文字的最末尾，方便用户继续按退格键(Backspace)删除
            self.weapon_entry.icursor(tk.END)
            # 3. 清除列表的选中高亮状态
            self.suggestion_list.selection_clear(0, tk.END)
            # 4. 返回 "break" 拦截系统默认行为，防止列表发生意外滚动
            return "break"
        
    def on_suggestion_select(self, event):
        sel = self.suggestion_list.curselection()
        if sel:
            name = self.suggestion_list.get(sel[0])
            self.weapon_var.set(name)
            self.suggestion_list.place_forget()
            self.weapon_entry.focus_set()
            
            # 极致 UX：一旦用户用鼠标点选，或用方向键+回车选中了武器，直接自动触发搜索！
            self.search()

    def hide_suggestion_list(self, event):
        if not hasattr(self, 'suggestion_list') or not hasattr(self, 'weapon_entry'): 
            return
        # 如果点击的地方既不是输入框，也不是悬浮列表本身，就立刻隐藏列表
        if event.widget not in (self.weapon_entry, self.suggestion_list):
            self.suggestion_list.place_forget()



    def _draw_tags(self, parent, items, bg_col, fg_col):
        """将文字列表转化为现代徽章(Tag)样式"""
        frame = tk.Frame(parent, bg="#ffffff")
        frame.pack(anchor="w", fill="x", pady=(8, 12))
        
        max_cols =  8 # 每行最多显示 5 个词条框
        for i, text in enumerate(items):
            # 使用内边距(padx/pady)撑开一个显眼的框
            lbl = tk.Label(frame, text=text, bg=bg_col, fg=fg_col, 
                           font=("Microsoft YaHei UI", 11, "bold"), padx=14, pady=6)
            # 使用网格布局，外边距留白
            lbl.grid(row=i // max_cols, column=i % max_cols, padx=(0, 10), pady=(0, 10))


    def region_selected(self, event=None):
        if not self.current_weapon: return
        sel = self.region_list.curselection()
        if not sel: return
        name = self.region_list.get(sel[0])
        region = next((r for r in regions if r["name"] == name), None)
        
        if region:
            self.detail_title.set(f"地区信息：{region['name']}")
            main, sub, skill = triple(self.current_weapon)
            
            for widget in self.tags_container.winfo_children():
                widget.destroy()
                
            # 画副词条区域 (浅蓝色底 + 科技蓝字)
            ttk.Label(self.tags_container, text="【该地区副词条池】", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
            self._draw_tags(self.tags_container, region.get("sub_attributes", []), "#e8f0fe", "#1a73e8")
            # 【新增】副产物收益数据
            sub_count = len(strategy_weapons(region, "sub", sub))
            tk.Label(self.tags_container, text=f"💡 与【{self.current_weapon['name']}】的副词条 ({sub}) 相同的武器有 {sub_count} 把", bg="#ffffff", fg="#1a73e8", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 15))
            
            # 画技能区域 (浅橙色底 + 橘红色字)
            ttk.Label(self.tags_container, text="【该地区技能池】", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
            self._draw_tags(self.tags_container, region.get("skills", []), "#fef0e8", "#e84d1a")
            # 【新增】技能产物收益数据
            skill_count = len(strategy_weapons(region, "skill", skill))
            tk.Label(self.tags_container, text=f"💡 与【{self.current_weapon['name']}】的技能 ({skill}) 相同的武器有 {skill_count} 把", bg="#ffffff", fg="#e84d1a", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 15))
            
            ttk.Label(self.tags_container, text="👉 双击左侧列表，或点击下方按钮对比刷取策略。", style="CardText.TLabel").pack(anchor="w", pady=(10, 0))
            
            btn = self._create_primary_btn(self.tags_container, "打开刷取策略对比", self.open_selected_region)
            btn.pack(anchor="w", pady=(10, 10))

    # 【新增】专门处理打开详情页的方法
    def open_selected_region(self, event=None):
        if not self.current_weapon: return
        sel = self.region_list.curselection()
        if not sel: return
        name = self.region_list.get(sel[0])
        region = next((r for r in regions if r["name"] == name), None)
        if region: 
            self.open_detail(region)

    def open_detail(self, region):
        win = tk.Toplevel(self)
        win.title(f"{region['name']} - 刷取策略")
        
        # 【修改点 1】让次级窗口完美继承主窗口的尺寸和屏幕坐标，实现无缝覆盖
        win.geometry(self.geometry())
        win.minsize(1050, 620)
        win.configure(bg="#f4f5f7")
        
        outer = ttk.Frame(win, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        
        w = self.current_weapon
        main, sub, skill = triple(w)
        
        # 【修改点 2】将头部划分为左右两侧：左侧放文字，右侧放返回按钮
        header = ttk.Frame(outer, style="Card.TFrame", padding=14)
        header.pack(fill="x", pady=(0, 14))
        
        header_left = ttk.Frame(header, style="Card.TFrame")
        header_left.pack(side="left", fill="both", expand=True)
        
        ttk.Label(header_left, text=region["name"], style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(header_left, text=f"目标武器：{w['name']} {rarity_text(w.get('rarity'))}    |    {main} / {sub} / {skill}", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
        ttk.Label(header_left, text=f"该地区副词条：{'、'.join(region.get('sub_attributes', []))}    |    技能：{'、'.join(region.get('skills', []))}", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
        
        header_right = ttk.Frame(header, style="Card.TFrame")
        header_right.pack(side="right", fill="y", padx=(10, 10))
        
        # 绑定销毁当前子窗口的方法，视觉上就是“返回上一层”
        self._create_primary_btn(header_right, "< 返回上一栏", win.destroy).pack(expand=True)
        
        bar = ttk.Frame(outer, style="Card.TFrame", padding=10)
        bar.pack(fill="x", pady=(0, 14))
        ttk.Label(bar, text="两种刷法同时展示：", style="CardText.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(bar, text="V1 仅展示信息，不评分、不推荐。", style="CardText.TLabel").pack(side="right")
        
        content = ttk.Frame(outer, style="App.TFrame")
        content.pack(fill="both", expand=True)
        
        # 渲染左右两侧的表格
        tree_sub = self.build_panel(content, region, "sub", sub, f"锁定副词条：{sub}")
        tree_skill = self.build_panel(content, region, "skill", skill, f"锁定技能：{skill}")
        
        # 【保留】全局点击取消选中的功能
        def clear_selection_on_click(event):
            if not isinstance(event.widget, (ttk.Treeview, ttk.Scrollbar)):
                tree_sub.selection_remove(tree_sub.selection())
                tree_skill.selection_remove(tree_skill.selection())
                
        win.bind("<Button-1>", clear_selection_on_click)

    def build_panel(self, parent, region, lock_type, value, title):
        panel = ttk.Frame(parent, style="Card.TFrame", padding=14)
        panel.pack(side="left", fill="both", expand=True, padx=(0, 7) if lock_type == "sub" else (7, 0))
        
        ttk.Label(panel, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(panel, text="点击【星级】或【主词条】表头切换排序。双击右侧胚子修改。", style="CardText.TLabel").pack(anchor="w", pady=(4, 10))
        
        tree = ttk.Treeview(panel, columns=("name", "rarity", "main", "sub", "skill", "bead1", "bead2", "bead3"), show="headings")
        
        columns_config = [
            ("name", "武器", 95, "w"),
            ("rarity", "星级", 50, "center"),
            ("main", "主词条", 60, "center"),  # 稍微加宽一点，容纳箭头符号
            ("sub", "副词条", 45, "center"),
            ("skill", "技能", 45, "center"),
            ("bead1", "胚子 1", 55, "center"),
            ("bead2", "胚子 2", 55, "center"),
            ("bead3", "胚子 3", 55, "center")
        ]
        
        for col, text, width, anchor in columns_config:
            tree.column(col, width=width, anchor=anchor)
            
        tree.tag_configure("rarity6", foreground="#d40000")
        tree.tag_configure("rarity5", foreground="#d49a00")
        tree.tag_configure("rarity4", foreground="#7030a0")
        
        sb = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        def on_tree_empty_click(event):
            if tree.identify_region(event.x, event.y) == "nothing":
                tree.selection_remove(tree.selection())
        tree.bind("<Button-1>", on_tree_empty_click, add="+")
        tree.bind("<Double-1>", lambda e, t=tree: self.edit_bead(e, t))
        
        # ==================== 排序切换逻辑 ====================
        panel_state = {"sort_mode": self.default_sort_mode}
        
        def refresh_tree():
            for item in tree.get_children():
                tree.delete(item)
                
            # 读取当前用户偏好的排序模式
            current_mode = self.user_config.get("sort_mode", "strategic")
                
            for col, text, _, _ in columns_config:
                if col == "rarity":
                    prefix = "▼ " if current_mode == "rarity" else ""
                    tree.heading(col, text=f"{prefix}{text}")
                elif col == "main":
                    prefix = "▼ " if current_mode == "strategic" else ""
                    tree.heading(col, text=f"{prefix}{text}")
                else:
                    tree.heading(col, text=text)
                    
            target_main = triple(self.current_weapon)[0]
            # 把 current_mode 传给策略函数
            for w in strategy_weapons(region, lock_type, value, target_main, current_mode):
                main, sub, skill = triple(w)
                b1, b2, b3 = top_3_beads_tuple(w)
                tree.insert("", tk.END, 
                            values=(w["name"], rarity_text(w.get("rarity")), main, sub, skill, b1, b2, b3), 
                            tags=(rarity_tag(w.get("rarity")),))

        def set_sort_mode(mode):
            # 【修改 2】切换排序时，将偏好直接写入文件
            if self.user_config.get("sort_mode", "strategic") != mode:
                self.user_config["sort_mode"] = mode
                save_config(self.user_config)  # 自动保存到 config.json
                refresh_tree()
                
        # 绑定的代码不变...
        tree.heading("rarity", command=lambda: set_sort_mode("rarity"))
        tree.heading("main", command=lambda: set_sort_mode("strategic"))
        
        refresh_tree()

    def edit_bead(self, event, tree):
        # 1. 判断点中了哪一列
        region_clicked = tree.identify_region(event.x, event.y)
        if region_clicked != "cell": return
        
        col_str = tree.identify_column(event.x)
        try: col_idx = int(col_str.replace("#", "")) - 1
        except: return
        
        # 只处理对 bead1, bead2, bead3（索引 5, 6, 7）的双击
        if col_idx not in [5, 6, 7]: return
        bead_rank = col_idx - 5  # 0, 1, 2
        
        item_id = tree.focus()
        if not item_id: return
        
        # 2. 提取当前行的武器数据
        values = list(tree.item(item_id, "values"))
        weapon_name, main, sub, skill = values[0], values[2], values[3], values[4]
        triple_key = (main, sub, skill)
        
        # 取出并重新排序当前的胚子，找到用户点的是哪一个
        beads = build_by_triple.setdefault(triple_key, [])
        sorted_beads = sorted(beads, key=lambda b: b.get("main", 0) + b.get("sub", 0) + b.get("skill", 0), reverse=True)
        
        current_bead = sorted_beads[bead_rank] if bead_rank < len(sorted_beads) else None
        current_str = f"{current_bead['main']}/{current_bead['sub']}/{current_bead['skill']}" if current_bead else "无"
        
        # 3. 弹出输入框
        prompt = f"武器：{weapon_name}\n槽位：第 {bead_rank + 1} 顺位 (当前: {current_str})\n\n请输入新胚子数值，支持格式: 411 或 4/1/1 或 4 1 1\n(若要删除该胚子，请输入 0 或直接留空清空):"
        top_window = tree.winfo_toplevel() 
        new_val = simpledialog.askstring("修改胚子", prompt, parent=top_window)
        
        if new_val is None: return  # 取消输入
        
        new_val = new_val.strip()
        
        # 4. 执行数据变更：删除 or 更新
        if not new_val or new_val == "0":
            if current_bead in beads:
                beads.remove(current_bead)
        else:
            # 智能解析输入
            nums = re.findall(r'\d+', new_val)
            if len(nums) == 1 and len(new_val) == 3 and new_val.isdigit():
                m, s, sk = int(new_val[0]), int(new_val[1]), int(new_val[2])
            elif len(nums) == 3:
                m, s, sk = int(nums[0]), int(nums[1]), int(nums[2])
            else:
                messagebox.showerror("格式错误", "无法识别输入的数值，请使用 411 或 4/1/1 格式。")
                return
            
            if current_bead in beads:
                current_bead["main"], current_bead["sub"], current_bead["skill"] = m, s, sk
            else:
                beads.append({"main": m, "sub": s, "skill": sk})
                
        # 5. 更新总数据字典，准备存盘
        target_build = next((x for x in builds_data.get("builds", []) if x.get("main") == main and x.get("sub") == sub and x.get("skill") == skill), None)
        if not target_build:
            target_build = {"main": main, "sub": sub, "skill": skill, "beads": beads}
            builds_data["builds"].append(target_build)
        else:
            target_build["beads"] = beads
            
        # 6. 持久化保存到 JSON
        try:
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f:
                json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入 builds.json:\n{e}")
            return
            
        # 7. 无缝刷新 UI 当前行的数据
        w_fake = {"attributes": {"主词条": main, "副词条": sub, "技能": skill}}
        new_b1, new_b2, new_b3 = top_3_beads_tuple(w_fake)
        values[5], values[6], values[7] = new_b1, new_b2, new_b3
        tree.item(item_id, values=values)

    def search_from_history(self, name):
        """点击历史记录时触发"""
        self.weapon_var.set(name)
        self.search()

    def refresh_history_ui(self):
        """渲染历史记录区"""
        # 清空旧的历史 UI
        for widget in self.history_frame.winfo_children():
            widget.destroy()
            
        history_list = self.user_config.get("history", [])
        if not history_list:
            return  # 没有历史就不显示
            
        ttk.Label(self.history_frame, text="历史记录：", style="CardText.TLabel").pack(side="left")
        
        # 遍历历史记录生成标签
        for weapon_name in history_list:
            tag_frame = tk.Frame(self.history_frame, bg="#f0f2f5", cursor="hand2", padx=8, pady=2)
            tag_frame.pack(side="left", padx=(0, 8))
            
            # 武器名字体
            name_lbl = tk.Label(tag_frame, text=weapon_name, bg="#f0f2f5", fg="#1d1d1f", font=("Microsoft YaHei UI", 10))
            name_lbl.pack(side="left")
            
            # 删除按钮 "×"
            close_lbl = tk.Label(tag_frame, text="×", bg="#f0f2f5", fg="#999999", font=("Microsoft YaHei UI", 10, "bold"))
            close_lbl.pack(side="left", padx=(4, 0))
            
            # 使用闭包绑定事件，防止作用域变量覆盖
            def make_events(name_val):
                # 鼠标点击文字 -> 触发查询
                tag_frame.bind("<Button-1>", lambda e: self.search_from_history(name_val))
                name_lbl.bind("<Button-1>", lambda e: self.search_from_history(name_val))
                
                # 鼠标点击 × -> 触发删除
                def on_delete(e):
                    self.user_config["history"].remove(name_val)
                    save_config(self.user_config)
                    self.refresh_history_ui()
                close_lbl.bind("<Button-1>", on_delete)
                
                # “×” 悬浮变红特效
                close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg="#d40000"))
                close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg="#999999"))
                
            make_events(weapon_name)



    def open_data_manager(self):
        win = tk.Toplevel(self)
        win.title("数据录入与管理")
        win.geometry("900x700")
        win.minsize(850, 650)
        win.configure(bg="#f0f2f5")
        win.grab_set()  # 锁定子窗口，必须处理完才能点主窗口

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)

        # 专门生成用于删除的高危按钮引擎
        def create_danger_btn(parent, text, command):
            btn = tk.Label(parent, text=text, bg="#dc3545", fg="#ffffff", font=("Microsoft YaHei UI", 11, "bold"), cursor="hand2", padx=24, pady=10)
            btn.bind("<Enter>", lambda e: btn.config(bg="#c82333"))
            btn.bind("<Leave>", lambda e: btn.config(bg="#dc3545"))
            btn.bind("<Button-1>", lambda e: command())
            return btn

        # ================= 选项卡 1：🗡️ 武器库管理 =================
        tab_w = tk.Frame(notebook, bg="#ffffff")
        notebook.add(tab_w, text="  🗡️ 武器库管理  ")

        # 左侧列表区
        left_w = tk.Frame(tab_w, bg="#f8f9fa")
        left_w.pack(side="left", fill="y")
        
        btn_add_w_ui = self._create_secondary_btn(left_w, "✚ 录入新武器", lambda: prep_w_add())
        btn_add_w_ui.pack(fill="x", padx=10, pady=10)
        
        list_w = tk.Listbox(left_w, width=20, font=("Microsoft YaHei UI", 11), activestyle="none", borderwidth=0, highlightthickness=0, selectbackground="#0066cc", selectforeground="#ffffff")
        list_w.pack(fill="both", expand=True, padx=10, pady=(0,10))

        # 右侧编辑区
        right_w = tk.Frame(tab_w, bg="#ffffff", padx=40, pady=30)
        right_w.pack(side="left", fill="both", expand=True)

        lbl_w_title = tk.Label(right_w, text="录入新武器", bg="#ffffff", font=("Microsoft YaHei UI", 14, "bold"), fg="#1d1d1f")
        lbl_w_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        def build_row(parent, label_text, row_idx):
            tk.Label(parent, text=label_text, bg="#ffffff", font=("Microsoft YaHei UI", 11)).grid(row=row_idx, column=0, sticky="w", pady=10)

        w_name_var = tk.StringVar()
        w_rarity_var = tk.StringVar(value="6")
        w_main_var = tk.StringVar()
        w_sub_var = tk.StringVar()
        w_skill_var = tk.StringVar()

        build_row(right_w, "武器名称:", 1)
        ttk.Entry(right_w, textvariable=w_name_var, font=("Microsoft YaHei UI", 11), width=28).grid(row=1, column=1, sticky="w", padx=10, pady=10)
        
        build_row(right_w, "武器星级:", 2)
        ttk.Combobox(right_w, textvariable=w_rarity_var, values=["4", "5", "6"], state="readonly", width=26, font=("Microsoft YaHei UI", 11)).grid(row=2, column=1, sticky="w", padx=10, pady=10)
        
        build_row(right_w, "主词条:", 3)
        ttk.Combobox(right_w, textvariable=w_main_var, values=attributes_data.get("main", []), state="readonly", width=26, font=("Microsoft YaHei UI", 11)).grid(row=3, column=1, sticky="w", padx=10, pady=10)
        
        build_row(right_w, "副词条:", 4)
        ttk.Combobox(right_w, textvariable=w_sub_var, values=attributes_data.get("sub", []), state="readonly", width=26, font=("Microsoft YaHei UI", 11)).grid(row=4, column=1, sticky="w", padx=10, pady=10)
        
        build_row(right_w, "技能:", 5)
        ttk.Combobox(right_w, textvariable=w_skill_var, values=attributes_data.get("skills", []), state="readonly", width=26, font=("Microsoft YaHei UI", 11)).grid(row=5, column=1, sticky="w", padx=10, pady=10)

        # 状态机：判断当前是添加还是修改
        w_state = {"mode": "add", "old_name": ""}
        btn_box_w = tk.Frame(right_w, bg="#ffffff")
        btn_box_w.grid(row=6, column=0, columnspan=2, sticky="w", pady=30)
        
        def refresh_list_w():
            list_w.delete(0, tk.END)
            for w in weapons: list_w.insert(tk.END, w["name"])

        def prep_w_add():
            list_w.selection_clear(0, tk.END)
            w_state["mode"] = "add"
            w_state["old_name"] = ""
            lbl_w_title.config(text="录入新武器")
            w_name_var.set("")
            w_main_var.set(""); w_sub_var.set(""); w_skill_var.set("")
            btn_del_w.pack_forget() # 新增模式下隐藏删除按钮

        def on_w_select(event):
            sel = list_w.curselection()
            if not sel: return
            w_name = list_w.get(sel[0])
            w = weapon_by_name[w_name]
            
            w_state["mode"] = "edit"
            w_state["old_name"] = w_name
            lbl_w_title.config(text=f"修改武器：{w_name}")
            
            w_name_var.set(w["name"])
            w_rarity_var.set(str(w.get("rarity", 6)))
            main, sub, skill = triple(w)
            w_main_var.set(main); w_sub_var.set(sub); w_skill_var.set(skill)
            
            btn_del_w.pack(side="right", padx=(15, 0)) # 显示删除按钮

        list_w.bind("<<ListboxSelect>>", on_w_select)

        def save_weapon():
            name = w_name_var.get().strip()
            if not all([name, w_rarity_var.get(), w_main_var.get(), w_sub_var.get(), w_skill_var.get()]):
                messagebox.showwarning("提示", "所有字段都必须填写！", parent=win)
                return
            
            if w_state["mode"] == "add":
                if name in weapon_by_name:
                    messagebox.showwarning("提示", f"武器 '{name}' 已存在！", parent=win)
                    return
                new_w = {"name": name, "rarity": int(w_rarity_var.get()), "attributes": {"主词条": w_main_var.get(), "副词条": w_sub_var.get(), "技能": w_skill_var.get()}}
                weapons.append(new_w)
                weapon_by_name[name] = new_w
                self.all_weapon_names.append(name)
                weapons_data["weapons"].append(new_w)
                msg = f"新武器 '{name}' 已成功录入！"
            else:
                old = w_state["old_name"]
                if name != old and name in weapon_by_name:
                    messagebox.showwarning("提示", f"武器名称 '{name}' 已被占用！", parent=win)
                    return
                for w in weapons:
                    if w["name"] == old:
                        w["name"] = name
                        w["rarity"] = int(w_rarity_var.get())
                        w["attributes"]["主词条"] = w_main_var.get()
                        w["attributes"]["副词条"] = w_sub_var.get()
                        w["attributes"]["技能"] = w_skill_var.get()
                        break
                if name != old: # 处理改名引发的连带更新
                    weapon_by_name[name] = weapon_by_name.pop(old)
                    self.all_weapon_names.remove(old)
                    self.all_weapon_names.append(name)
                    if old in self.user_config.get("history", []):
                        idx = self.user_config["history"].index(old)
                        self.user_config["history"][idx] = name
                        save_config(self.user_config)
                        self.refresh_history_ui()
                    if self.current_weapon and self.current_weapon["name"] == old:
                        self.weapon_var.set(name)
                msg = f"武器 '{name}' 已成功修改！"

            with open(os.path.join(BASE_DIR, "weapons.json"), "w", encoding="utf-8") as f:
                json.dump(weapons_data, f, ensure_ascii=False, indent=2)
            
            refresh_list_w()
            prep_w_add()
            messagebox.showinfo("成功", msg, parent=win)
            
            # 热更新主界面
            if self.current_weapon and self.current_weapon["name"] in (name, w_state.get("old_name", "")):
                self.search()

        def del_weapon():
            old = w_state["old_name"]
            if not messagebox.askyesno("确认", f"确定永久删除武器【{old}】？", parent=win): return
            for w in weapons:
                if w["name"] == old:
                    weapons.remove(w)
                    break
            del weapon_by_name[old]
            self.all_weapon_names.remove(old)
            weapons_data["weapons"] = [x for x in weapons_data.get("weapons", []) if x["name"] != old]
            with open(os.path.join(BASE_DIR, "weapons.json"), "w", encoding="utf-8") as f:
                json.dump(weapons_data, f, ensure_ascii=False, indent=2)
                
            if old in self.user_config.get("history", []):
                self.user_config["history"].remove(old)
                save_config(self.user_config)
                self.refresh_history_ui()
                
            if self.current_weapon and self.current_weapon["name"] == old:
                self.current_weapon = None
                self.weapon_var.set("")
                self.status.set("请输入武器名称")
                self.region_list.delete(0, tk.END)
                self.show_default_right_panel("武器已被删除，请重新搜索。")
                
            refresh_list_w()
            prep_w_add()
            messagebox.showinfo("删除成功", f"武器 '{old}' 已删除。", parent=win)

        btn_save_w = self._create_primary_btn(btn_box_w, "💾 保存", save_weapon)
        btn_save_w.pack(side="left")
        btn_del_w = create_danger_btn(btn_box_w, "🗑️ 删除", del_weapon)
        
        refresh_list_w()
        prep_w_add()

        # ================= 选项卡 2：🗺️ 地区库管理 =================
        tab_r = tk.Frame(notebook, bg="#ffffff")
        notebook.add(tab_r, text="  🗺️ 地区库管理  ")

        left_r = tk.Frame(tab_r, bg="#f8f9fa")
        left_r.pack(side="left", fill="y")
        
        btn_add_r_ui = self._create_secondary_btn(left_r, "✚ 录入新地区", lambda: prep_r_add())
        btn_add_r_ui.pack(fill="x", padx=10, pady=10)
        
        list_r = tk.Listbox(left_r, width=18, font=("Microsoft YaHei UI", 11), activestyle="none", borderwidth=0, highlightthickness=0, selectbackground="#0066cc", selectforeground="#ffffff")
        list_r.pack(fill="both", expand=True, padx=10, pady=(0,10))

        right_r = tk.Frame(tab_r, bg="#ffffff", padx=30, pady=20)
        right_r.pack(side="left", fill="both", expand=True)

        lbl_r_title = tk.Label(right_r, text="录入新地区", bg="#ffffff", font=("Microsoft YaHei UI", 14, "bold"), fg="#1d1d1f")
        lbl_r_title.pack(anchor="w", pady=(0, 15))

        r_name_var = tk.StringVar()
        tk.Label(right_r, text="地区名称:", bg="#ffffff", font=("Microsoft YaHei UI", 11)).pack(anchor="w", pady=(0, 5))
        ttk.Entry(right_r, textvariable=r_name_var, font=("Microsoft YaHei UI", 11), width=40).pack(anchor="w", pady=(0, 15))

        def create_check_grid(parent, title, items):
            tk.Label(parent, text=title, bg="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), fg="#6e6e73").pack(anchor="w", pady=(5, 5))
            grid_frame = tk.Frame(parent, bg="#ffffff")
            grid_frame.pack(anchor="w", fill="x", pady=(0, 10))
            vars_dict = {}
            for i, item in enumerate(items):
                var = tk.BooleanVar()
                cb = tk.Checkbutton(grid_frame, text=item, variable=var, bg="#ffffff", activebackground="#ffffff", font=("Microsoft YaHei UI", 10), cursor="hand2")
                cb.grid(row=i // 4, column=i % 4, sticky="w", padx=10, pady=2)
                vars_dict[item] = var
            return vars_dict

        sub_vars = create_check_grid(right_r, "包含副词条 (可多选):", attributes_data.get("sub", []))
        skill_vars = create_check_grid(right_r, "包含技能 (可多选):", attributes_data.get("skills", []))

        r_state = {"mode": "add", "old_name": ""}
        btn_box_r = tk.Frame(right_r, bg="#ffffff")
        btn_box_r.pack(fill="x", pady=20)

        def refresh_list_r():
            list_r.delete(0, tk.END)
            for r in regions: list_r.insert(tk.END, r["name"])

        def prep_r_add():
            list_r.selection_clear(0, tk.END)
            r_state["mode"] = "add"
            r_state["old_name"] = ""
            lbl_r_title.config(text="录入新地区")
            r_name_var.set("")
            for v in sub_vars.values(): v.set(False)
            for v in skill_vars.values(): v.set(False)
            btn_del_r.pack_forget()

        def on_r_select(event):
            sel = list_r.curselection()
            if not sel: return
            r_name = list_r.get(sel[0])
            r_obj = next((x for x in regions if x["name"] == r_name), None)
            if not r_obj: return
            
            r_state["mode"] = "edit"
            r_state["old_name"] = r_name
            lbl_r_title.config(text=f"修改地区：{r_name}")
            r_name_var.set(r_obj["name"])
            
            for k, v in sub_vars.items(): v.set(k in r_obj.get("sub_attributes", []))
            for k, v in skill_vars.items(): v.set(k in r_obj.get("skills", []))
            
            btn_del_r.pack(side="right", padx=(15, 0))

        list_r.bind("<<ListboxSelect>>", on_r_select)

        def save_region():
            name = r_name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "地区名称不能为空！", parent=win)
                return
            
            selected_subs = [k for k, v in sub_vars.items() if v.get()]
            selected_skills = [k for k, v in skill_vars.items() if v.get()]
            if not selected_subs or not selected_skills:
                messagebox.showwarning("提示", "必须至少勾选一个副词条和一个技能！", parent=win)
                return

            if r_state["mode"] == "add":
                if any(r["name"] == name for r in regions):
                    messagebox.showwarning("提示", f"地区 '{name}' 已存在！", parent=win)
                    return
                new_r = {"name": name, "sub_attributes": selected_subs, "skills": selected_skills}
                regions.append(new_r)
                regions_data["regions"].append(new_r)
                msg = f"新地区 '{name}' 已成功录入！"
            else:
                old = r_state["old_name"]
                if name != old and any(r["name"] == name for r in regions):
                    messagebox.showwarning("提示", f"地区名称 '{name}' 已被占用！", parent=win)
                    return
                for r in regions:
                    if r["name"] == old:
                        r["name"] = name
                        r["sub_attributes"] = selected_subs
                        r["skills"] = selected_skills
                        break
                msg = f"地区 '{name}' 已成功修改！"

            with open(os.path.join(BASE_DIR, "regions.json"), "w", encoding="utf-8") as f:
                json.dump(regions_data, f, ensure_ascii=False, indent=2)
            
            refresh_list_r()
            prep_r_add()
            messagebox.showinfo("成功", msg, parent=win)
            if self.current_weapon:
                self.refresh_region_list()

        def del_region():
            old = r_state["old_name"]
            if not messagebox.askyesno("确认", f"确定永久删除地区【{old}】？", parent=win): return
            for r in regions:
                if r["name"] == old:
                    regions.remove(r)
                    break
            regions_data["regions"] = [r for r in regions_data.get("regions", []) if r["name"] != old]
            with open(os.path.join(BASE_DIR, "regions.json"), "w", encoding="utf-8") as f:
                json.dump(regions_data, f, ensure_ascii=False, indent=2)
                
            refresh_list_r()
            prep_r_add()
            messagebox.showinfo("删除成功", f"地区 '{old}' 已删除。", parent=win)
            if self.current_weapon:
                self.refresh_region_list()

        btn_save_r = self._create_primary_btn(btn_box_r, "💾 保存", save_region)
        btn_save_r.pack(side="left")
        btn_del_r = create_danger_btn(btn_box_r, "🗑️ 删除", del_region)
        
        refresh_list_r()
        prep_r_add()



    #初始化配置
    def initialize_data(self, parent_window=None):
        """恢复出厂设置，备份并清空历史和用户录入的胚子"""
        global builds_data, builds, build_by_triple
        
        # 【新增】智能定位弹窗父级，如果没传，就默认主窗口 self
        target_parent = parent_window if parent_window else self
        
        ans = messagebox.askyesno(
            "初始化所有数据与配置", 
            "【警告】此操作将清除您的搜索历史和偏好配置，并【清空所有自定义胚子】。\n\n（系统会自动在本地生成一份 builds_backup.json 备份以便反悔）\n\n是否确认要初始化回到全新状态？", 
            parent=target_parent
        )
        if not ans: return
        
        # 0. 备份当前的 builds_data
        try:
            with open(os.path.join(BASE_DIR, "builds_backup.json"), "w", encoding="utf-8") as f:
                json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("备份失败", f"无法创建备份文件：{e}", parent=target_parent)
            return
        
        # 1. 恢复 config.json 默认值 (双收益优先)
        self.user_config = {"history": [], "sort_mode": "strategic", "region_sort_mode": "yield"}
        save_config(self.user_config)
        
        # 2. 清空 builds.json 的内存和文件
        builds_data["builds"] = []
        builds.clear()
        build_by_triple.clear()
        try:
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f:
                json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
            
        # 3. 实时清理主界面状态
        self.refresh_history_ui()
        self.status.set("请输入武器名称")
        self.current_weapon = None
        self.weapon_var.set("")
        self.region_list.delete(0, tk.END)
        self.show_default_right_panel("数据已成功初始化。如果您是误操作，请在全局配置中恢复备份。")
        self.detail_title.set("选择一个地区")
        if hasattr(self, 'suggestion_list'):
            self.suggestion_list.place_forget()
            
        messagebox.showinfo("成功", "所有用户数据已成功初始化，已在文件夹内生成备份文件 builds_backup.json！", parent=target_parent)


    def restore_backup_data(self, parent_window=None):
        """恢复备份的胚子数据"""
        global builds_data, builds, build_by_triple
        
        target_parent = parent_window if parent_window else self
        
        backup_path = os.path.join(BASE_DIR, "builds_backup.json")
        if not os.path.exists(backup_path):
            messagebox.showwarning("无法恢复", "未找到备份文件 (builds_backup.json)！\n可能是您还没有进行过初始化，或者备份文件已被移动或删除。", parent=target_parent)
            return
        
        ans = messagebox.askyesno(
            "恢复备份数据",
            "是否确认要读取 builds_backup.json 中的数据？\n此操作将覆盖您当前的全部胚子数据！",
            parent=target_parent
        )
        if not ans: return
        
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
                
            # 重新加载内存中的全局变量，保证后续操作的数据正确性
            builds_data.clear()
            builds_data.update(backup_data)
            
            builds.clear()
            builds.extend(builds_data.get("builds", []))
            
            build_by_triple.clear()
            for x in builds:
                build_by_triple[(x.get("main", ""), x.get("sub", ""), x.get("skill", ""))] = x.get("beads", [])
                
            # 覆盖写回正式的 builds.json 文件
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f:
                json.dump(builds_data, f, ensure_ascii=False, indent=2)
                
            messagebox.showinfo("恢复成功", "所有胚子数据已成功从备份中恢复！", parent=target_parent)
            
            # 如果当前正显示着武器，立刻热更新主页面
            if self.current_weapon:
                self.search()
                
        except Exception as e:
            messagebox.showerror("恢复失败", f"读取备份文件时出错：\n{e}", parent=target_parent)

    def open_all_weapons_manager(self):
        """打开全局武器概览与胚子管理窗口"""
        win = tk.Toplevel(self)
        win.title("全武器胚子管理库")
        win.geometry("980x600")
        win.minsize(850, 500)
        win.configure(bg="#f4f5f7")
        
        panel = ttk.Frame(win, style="Card.TFrame", padding=14)
        panel.pack(fill="both", expand=True, padx=20, pady=20)
        
        header_f = tk.Frame(panel, bg="#ffffff")
        header_f.pack(fill="x", pady=(0, 10))
        ttk.Label(header_f, text="全武器胚子库", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(header_f, text="在此可纵览所有武器。点击表头进行排序，双击右侧【胚子】数据快速修改。", style="CardText.TLabel").pack(side="left", padx=20, pady=(4,0))
        
        tree = ttk.Treeview(panel, columns=("name", "rarity", "main", "sub", "skill", "bead1", "bead2", "bead3"), show="headings")
        
        columns_config = [
            ("name", "武器名称", 140, "w"),
            ("rarity", "星级", 50, "center"),
            ("main", "主词条", 70, "center"),
            ("sub", "副词条", 70, "center"),
            ("skill", "技能", 70, "center"),
            ("bead1", "胚子 1", 70, "center"),
            ("bead2", "胚子 2", 70, "center"),
            ("bead3", "胚子 3", 70, "center")
        ]
        
        # 实现点击表头排序功能
        sort_state = {"col": None, "reverse": False}
        def sort_by_col(col):
            if sort_state["col"] == col:
                sort_state["reverse"] = not sort_state["reverse"]
            else:
                sort_state["col"] = col
                sort_state["reverse"] = True # 第一次点击默认降序，更符合直觉
                
            data = []
            for child in tree.get_children():
                val = tree.set(child, col)
                if col == "rarity":
                    val = int(val.replace("★", "")) if "★" in val else 0
                data.append((val, child))
                
            data.sort(reverse=sort_state["reverse"], key=lambda x: x[0])
            for idx, item in enumerate(data):
                tree.move(item[1], '', idx)
                
            # 刷新表头箭头
            for c_name, c_text, _, _ in columns_config:
                arrow = " ▼" if (c_name == col and sort_state["reverse"]) else " ▲" if (c_name == col) else ""
                tree.heading(c_name, text=c_text + arrow)
        
        for col, text, width, anchor in columns_config:
            tree.heading(col, text=text, command=lambda c=col: sort_by_col(c))
            tree.column(col, width=width, anchor=anchor)
            
        tree.tag_configure("rarity6", foreground="#d40000")
        tree.tag_configure("rarity5", foreground="#d49a00")
        tree.tag_configure("rarity4", foreground="#7030a0")
        
        sb = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        def on_tree_empty_click(event):
            if tree.identify_region(event.x, event.y) == "nothing":
                tree.selection_remove(tree.selection())
        tree.bind("<Button-1>", on_tree_empty_click, add="+")
        
        # 【核心黑科技】因为列的结构完全一样，直接复用 edit_bead 方法，它会自动完成存盘和表格局部刷新！
        tree.bind("<Double-1>", lambda e, t=tree: self.edit_bead(e, t))
        
        # 把库里所有的武器都灌进去
        for w in weapons:
            main, sub, skill = triple(w)
            b1, b2, b3 = top_3_beads_tuple(w)
            tree.insert("", tk.END, 
                        values=(w["name"], rarity_text(w.get("rarity")), main, sub, skill, b1, b2, b3), 
                        tags=(rarity_tag(w.get("rarity")),))
                        
        # 打开时，默认按星级降序排好
        sort_by_col("rarity")

    def open_settings(self):
        """打开全局配置窗口 (VS Code 风格)"""
        win = tk.Toplevel(self)
        win.title("全局配置 (Settings)")
        
        # 【修改点 1】将窗口宽度从 850 加宽到 950，确保“恢复备份数据”完全显示
        window_width = 950
        window_height = 620
        
        # 【修改点 2】计算主界面的中心点，让弹窗完美居中对齐，消除位置偏差
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        center_x = main_x + (main_width - window_width) // 2
        center_y = main_y + (main_height - window_height) // 2
        
        # 边缘保护：防止主窗口在屏幕最边缘时，弹窗跑到屏幕外面
        center_x = max(0, center_x)
        center_y = max(0, center_y)

        win.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        win.minsize(900, 600)
        win.configure(bg="#ffffff")
        win.grab_set()

        # ================= 左侧导航栏 =================
        sidebar = tk.Frame(win, bg="#f3f3f3", width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False) # 锁定侧边栏宽度

        tk.Label(sidebar, text="设置", font=("Microsoft YaHei UI", 16, "bold"), bg="#f3f3f3", fg="#1d1d1f").pack(anchor="w", padx=20, pady=20)
        
        # 模拟 VS Code 的导航选项 (目前单页足够，此处作为 UI 视觉增强)
        tk.Label(sidebar, text="通用设置", font=("Microsoft YaHei UI", 10), bg="#e4e6f1", fg="#000000", anchor="w", padx=20, pady=8, cursor="hand2").pack(fill="x")
        tk.Label(sidebar, text="数据管理", font=("Microsoft YaHei UI", 10), bg="#f3f3f3", fg="#6e6e73", anchor="w", padx=20, pady=8, cursor="hand2").pack(fill="x")

        # ================= 右侧配置内容区 =================
        content = tk.Frame(win, bg="#ffffff", padx=40, pady=30)
        content.pack(side="left", fill="both", expand=True)

        tk.Label(content, text="通用设置", font=("Microsoft YaHei UI", 18, "bold"), bg="#ffffff", fg="#1d1d1f").pack(anchor="w", pady=(0, 20))

        def create_setting_item(parent, title, desc, control_fn):
            """生成标准化的配置项 UI (左文右件)"""
            f = tk.Frame(parent, bg="#ffffff")
            f.pack(fill="x", pady=12)
            
            tf = tk.Frame(f, bg="#ffffff")
            tf.pack(side="left", fill="x", expand=True)
            tk.Label(tf, text=title, font=("Microsoft YaHei UI", 11, "bold"), bg="#ffffff", fg="#1d1d1f").pack(anchor="w")
            tk.Label(tf, text=desc, font=("Microsoft YaHei UI", 9), bg="#ffffff", fg="#6e6e73").pack(anchor="w", pady=(4,0))
            
            cf = tk.Frame(f, bg="#ffffff")
            cf.pack(side="right", padx=(20, 0))
            control_fn(cf)

        # ---------------- 1. 完美基质判定标准 (双模式动态 UI) ----------------
        def ctrl_perfect_criteria(parent):
            # 【修改】把 (默认) 这个标识移到了 custom 上
            mode_map = {"none": "不启用", "score": "综合得分 (技能分翻倍)", "custom": "自定义三维下限 (默认)"}
            inv_mode_map = {v: k for k, v in mode_map.items()}
            
            # 【修改】如果读不到配置，默认让下拉框显示 custom
            mode_var = tk.StringVar(value=mode_map.get(self.user_config.get("perfect_mode", "custom"), "自定义三维下限 (默认)"))
            cb_mode = ttk.Combobox(parent, textvariable=mode_var, values=list(mode_map.values()), state="readonly", width=22, font=("Microsoft YaHei UI", 10))
            cb_mode.pack(anchor="e")
            
            param_frame = tk.Frame(parent, bg="#ffffff")
            param_frame.pack(anchor="e", pady=(8, 0))
            
            def save_and_refresh():
                save_config(self.user_config)
                if self.current_weapon: self.refresh_region_list()

            def build_params(event=None):
                for widget in param_frame.winfo_children(): widget.destroy()
                
                current_mode = inv_mode_map[mode_var.get()]
                self.user_config["perfect_mode"] = current_mode
                
                if current_mode == "score":
                    tk.Label(param_frame, text="要求得分 ≥", bg="#ffffff", fg="#1a73e8", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
                    score_var = tk.IntVar(value=self.user_config.get("perfect_score", 7))
                    cb_score = ttk.Combobox(param_frame, textvariable=score_var, values=[5, 6, 7, 8, 9, 10, 11, 12], state="readonly", width=4)
                    cb_score.pack(side="left", padx=5)
                    def on_score_change(e):
                        self.user_config["perfect_score"] = score_var.get()
                        save_and_refresh()
                    cb_score.bind("<<ComboboxSelected>>", on_score_change)
                    
                elif current_mode == "custom":
                    # 【修改】此处的默认读取值也改为 [6, 6, 3]
                    vals = self.user_config.get("perfect_custom", [6, 6, 3])
                    m_var, s_var, sk_var = tk.IntVar(value=vals[0]), tk.IntVar(value=vals[1]), tk.IntVar(value=vals[2])
                    
                    def on_custom_change(e):
                        self.user_config["perfect_custom"] = [m_var.get(), s_var.get(), sk_var.get()]
                        save_and_refresh()

                    tk.Label(param_frame, text="主≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left")
                    cb_m = ttk.Combobox(param_frame, textvariable=m_var, values=[2,3,4,5,6], state="readonly", width=3); cb_m.pack(side="left")
                    
                    tk.Label(param_frame, text="副≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(5,0))
                    # 此处副词条的值域还是保留了 0~6
                    cb_s = ttk.Combobox(param_frame, textvariable=s_var, values=[0,1,2,3,4,5,6], state="readonly", width=3); cb_s.pack(side="left")
                    
                    tk.Label(param_frame, text="技≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(5,0))
                    cb_sk = ttk.Combobox(param_frame, textvariable=sk_var, values=[0,1,2,3], state="readonly", width=3); cb_sk.pack(side="left")
                    
                    cb_m.bind("<<ComboboxSelected>>", on_custom_change)
                    cb_s.bind("<<ComboboxSelected>>", on_custom_change)
                    cb_sk.bind("<<ComboboxSelected>>", on_custom_change)

                if event: save_and_refresh()

            cb_mode.bind("<<ComboboxSelected>>", build_params)
            build_params() 

        create_setting_item(content, "完美基质判定标准", "可按综合得分(技能评分x2)或自定义三维底线进行毕业判定。", ctrl_perfect_criteria)

        # ---------------- 2. 达成毕业的完美基质数量 ----------------
        def ctrl_perfect_count(parent):
            # 【修改】更新文字提示，2 颗为默认
            val_map = {1: "1 颗", 2: "2 颗 (默认)", 3: "3 颗"}
            inv_map = {v: k for k, v in val_map.items()}
            
            # 【修改】更新默认抓取值为 2
            current_val = self.user_config.get("perfect_count", 2)
            var = tk.StringVar(value=val_map.get(current_val, "2 颗 (默认)"))
            
            cb = ttk.Combobox(parent, textvariable=var, values=list(val_map.values()), state="readonly", width=22, font=("Microsoft YaHei UI", 10))
            cb.pack()
            
            def on_change(e):
                self.user_config["perfect_count"] = inv_map[var.get()]
                save_config(self.user_config)
                if self.current_weapon: self.refresh_region_list()
                
            cb.bind("<<ComboboxSelected>>", on_change)
            
        create_setting_item(content, "毕业所需完美基质数量", "当完美基质达到此数量时，该词条排列不再加入刷取策略计算。", ctrl_perfect_count)

        # ---------------- 3. 可刷地区排序方式 ----------------
        def ctrl_region_sort(parent):
            # 将“收益优先”放在第一位，判断也反过来
            var = tk.StringVar(value="默认排序" if self.user_config.get("region_sort_mode") == "default" else "收益优先")
            cb = ttk.Combobox(parent, textvariable=var, values=["收益优先", "默认排序"], state="readonly", width=20, font=("Microsoft YaHei UI", 10))
            cb.pack()
            def on_change(e):
                val = "default" if var.get() == "默认排序" else "yield"
                self.user_config["region_sort_mode"] = val
                save_config(self.user_config)
                if self.current_weapon: self.refresh_region_list()
            cb.bind("<<ComboboxSelected>>", on_change)
        create_setting_item(content, "可刷地区列表排序", "控制主页面左侧“可刷地区”的默认展示优先级。", ctrl_region_sort)

        # ---------------- 4. 珠子排列方式 ----------------
        def ctrl_bead_sort(parent):
            # 同样将“收益优先”放在前面
            var = tk.StringVar(value="星级优先" if self.user_config.get("sort_mode") == "rarity" else "收益优先 (按数量)")
            cb = ttk.Combobox(parent, textvariable=var, values=["收益优先 (按数量)", "星级优先"], state="readonly", width=20, font=("Microsoft YaHei UI", 10))
            cb.pack()
            def on_change(e):
                val = "rarity" if var.get() == "星级优先" else "strategic"
                self.user_config["sort_mode"] = val
                save_config(self.user_config)
            cb.bind("<<ComboboxSelected>>", on_change)
        create_setting_item(content, "策略页面珠子排列方式", "在次要页面中，武器矩阵是以星级还是以流派收益数量排序。", ctrl_bead_sort)

        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=15)

        # ---------------- 5. 初始化与备份恢复 ----------------
        def ctrl_init(parent):
            # 用 Frame 将两个按钮横向并排
            btn_frame = tk.Frame(parent, bg="#ffffff")
            btn_frame.pack(anchor="e")
            
            # 按钮 1：红色的危险初始化按钮
            btn_init = tk.Label(btn_frame, text="初始化所有数据与配置", bg="#dc3545", fg="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2", padx=16, pady=6)
            btn_init.bind("<Enter>", lambda e: btn_init.config(bg="#c82333"))
            btn_init.bind("<Leave>", lambda e: btn_init.config(bg="#dc3545"))
            
            # 【修改】不再销毁配置窗口，并指定弹窗要在配置窗口(win)的正上方出现
            btn_init.bind("<Button-1>", lambda e: self.initialize_data(parent_window=win))
            btn_init.pack(side="left")

            # 按钮 2：绿色的安全恢复按钮
            btn_restore = tk.Label(btn_frame, text="恢复备份数据", bg="#28a745", fg="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2", padx=16, pady=6)
            btn_restore.bind("<Enter>", lambda e: btn_restore.config(bg="#218838"))
            btn_restore.bind("<Leave>", lambda e: btn_restore.config(bg="#28a745"))
            
            # 【修改】同样不销毁配置窗口
            btn_restore.bind("<Button-1>", lambda e: self.restore_backup_data(parent_window=win))
            btn_restore.pack(side="left", padx=(10, 0))
            
        create_setting_item(content, "数据初始化与备份", "初始化将清空自定义胚子并生成备份。误操作可通过恢复备份还原。", ctrl_init)


if __name__ == "__main__":
    App().mainloop()
