import json
import os
import re
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from collections import Counter

# ================= 核心路径适配 (支持 PyInstaller) =================
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
        messagebox.showerror("文件错误", f"找不到文件：{filename}\n\n请确认它和 main.py (或 exe) 在同一个文件夹。")
        raise

attributes_data = load_json("attributes.json")
weapons_data = load_json("weapons.json")
regions_data = load_json("regions.json")
builds_data = load_json("builds.json")


# ================= 用户配置管理 =================
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    """读取用户配置，如果文件不存在则生成默认配置"""
    default_cfg = {
        "history": [], 
        "sort_mode": "strategic", 
        "region_sort_mode": "yield",
        "perfect_mode": "custom",     # 默认开启自定义毕业标准
        "perfect_score": 7,           
        "perfect_custom": [6, 3, 3],  # 默认数值 6/3/3
        "perfect_count": 2            # 默认 2 颗毕业
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
    """保存用户配置到本地，并同步全局内存"""
    global global_config
    global_config.update(config_data)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"配置文件保存失败: {e}")

# ================= 核心数据结构 =================
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

def top_3_beads_tuple(w):
    beads = build_by_triple.get(triple(w), [])
    sorted_beads = sorted(beads, key=lambda b: b.get("main", 0) + b.get("sub", 0) + b.get("skill", 0), reverse=True)
    res = []
    for b in sorted_beads[:3]:
        res.append(f"{b.get('main',0)}/{b.get('sub',0)}/{b.get('skill',0)}")
    while len(res) < 3: res.append("—")
    return tuple(res)

def can_farm(region, w):
    _, sub, skill = triple(w)
    return sub in region.get("sub_attributes", []) and skill in region.get("skills", [])

# ================= 核心策略与排序引擎 =================
def strategy_weapons(region, lock_type, value, target_main="", sort_mode="strategic"):
    result = []
    perf_mode = global_config.get("perfect_mode", "custom")
    perf_score = global_config.get("perfect_score", 7)
    perf_custom = global_config.get("perfect_custom", [6, 3, 3])
    perf_count = global_config.get("perfect_count", 2)
    
    for w in weapons:
        main, sub, skill = triple(w)
        
        # 毕业武器拦截系统
        if perf_mode != "none":
            beads = build_by_triple.get((main, sub, skill), [])
            perfects = 0
            for b in beads:
                m, s, sk = b.get("main", 0), b.get("sub", 0), b.get("skill", 0)
                if perf_mode == "score":
                    if m + s + (sk * 2) >= perf_score: perfects += 1
                elif perf_mode == "custom":
                    if m >= perf_custom[0] and s >= perf_custom[1] and sk >= perf_custom[2]: perfects += 1
            if perfects >= perf_count:
                continue # 已毕业，剔除出策略池

        if sub not in region.get("sub_attributes", []) or skill not in region.get("skills", []): continue
        if lock_type == "sub" and sub != value: continue
        if lock_type == "skill" and skill != value: continue
        result.append(w)
        
    if sort_mode == "strategic":
        main_counts = Counter(triple(w)[0] for w in result)
        result.sort(key=lambda w: (
            0 if triple(w)[0] == target_main else 1,
            -main_counts.get(triple(w)[0], 0),
            triple(w)[0], -(w.get("rarity") or 0), w.get("name", "")
        ))
    else:
        result.sort(key=lambda w: (-(w.get("rarity") or 0), triple(w)[0], w.get("name", "")))
        
    return result

def regions_for(w, sort_mode="default"):
    rs = [r for r in regions if can_farm(r, w)]
    if sort_mode == "yield":
        main, sub, skill = triple(w)
        def get_yield(r):
            return len(strategy_weapons(r, "sub", sub)) + len(strategy_weapons(r, "skill", skill))
        rs.sort(key=lambda r: (-get_yield(r), r["name"]))
    return rs


# ================= UI 主程序 =================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
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
        btn = tk.Label(parent, text=text, bg="#0066cc", fg="#ffffff", font=("Microsoft YaHei UI", 11, "bold"), cursor="hand2", padx=24, pady=10)
        btn.bind("<Enter>", lambda e: btn.config(bg="#0055aa"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#0066cc"))
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def _create_secondary_btn(self, parent, text, command):
        btn = tk.Label(parent, text=text, bg="#e2e6ea", fg="#1d1d1f", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2", padx=16, pady=8)
        btn.bind("<Enter>", lambda e: btn.config(bg="#d2d6da"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#e2e6ea"))
        btn.bind("<Button-1>", lambda e: command())
        return btn

    def setup_style(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except tk.TclError: pass
        
        s.configure("App.TFrame", background="#f0f2f5")
        s.configure("Card.TFrame", background="#ffffff")
        s.configure("Title.TLabel", background="#f0f2f5", foreground="#1d1d1f", font=("Microsoft YaHei UI", 22, "bold"))
        s.configure("SubTitle.TLabel", background="#f0f2f5", foreground="#6e6e73", font=("Microsoft YaHei UI", 11))
        s.configure("CardTitle.TLabel", background="#ffffff", foreground="#1d1d1f", font=("Microsoft YaHei UI", 14, "bold"))
        s.configure("CardText.TLabel", background="#ffffff", foreground="#6e6e73", font=("Microsoft YaHei UI", 11))
        s.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=30, borderwidth=0)
        s.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), background="#f8f9fa", foreground="#333")
        s.map("Treeview.Heading", background=[("active", "#e2e6ea")])

    def build_ui(self):
        root = ttk.Frame(self, style="App.TFrame", padding=20)
        root.pack(fill="both", expand=True)

        # --- 顶部 ---
        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x")
        
        title_box = ttk.Frame(header, style="App.TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="基质珠子筛选器", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="输入目标武器，查看可刷地区，再对比“锁定副词条”和“锁定技能”两种刷取方式。", style="SubTitle.TLabel").pack(anchor="w", pady=(4, 16))
        
        btn_box = tk.Frame(header, bg="#f0f2f5")
        btn_box.pack(side="right", anchor="n", pady=(10, 0))
        self._create_secondary_btn(btn_box, "⚙️ 全局配置", self.open_settings).pack(side="right", padx=(10, 0))
        self._create_secondary_btn(btn_box, "✚ 数据管理", self.open_data_manager).pack(side="right", padx=(10, 0))
        self._create_secondary_btn(btn_box, "📚 胚子总库", self.open_all_weapons_manager).pack(side="right")
        
        # --- 搜索区 ---
        search = ttk.Frame(root, style="Card.TFrame", padding=16)
        search.pack(fill="x", pady=(0, 14))

        ttk.Label(search, text="目标武器", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.all_weapon_names = [w["name"] for w in weapons]
        self.weapon_var = tk.StringVar()
        self.weapon_entry = ttk.Entry(search, textvariable=self.weapon_var, font=("Microsoft YaHei UI", 11), width=38)
        self.weapon_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(7, 0))
        
        self.suggestion_list = tk.Listbox(self, font=("Microsoft YaHei UI", 11), bg="#ffffff", fg="#1d1d1f", selectbackground="#0066cc", selectforeground="#ffffff", borderwidth=1, relief="solid", cursor="hand2")
        
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

        # --- 左右分栏 ---
        body = ttk.Frame(root, style="App.TFrame")
        body.pack(fill="both", expand=True)
        
        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="y")
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        
        left_header = tk.Frame(left, bg="#ffffff")
        left_header.pack(fill="x", pady=(0, 10))
        ttk.Label(left_header, text="可刷地区", style="CardTitle.TLabel").pack(side="left")
        
        self.region_sort_btn = tk.Label(left_header, text="▼ 默认排序", fg="#6e6e73", bg="#ffffff", font=("Microsoft YaHei UI", 10, "underline"), cursor="hand2")
        self.region_sort_btn.pack(side="right", pady=(2, 0))
        self.region_sort_btn.bind("<Button-1>", lambda e: self.toggle_region_sort())
        
        self.region_list = tk.Listbox(left, width=28, font=("Microsoft YaHei UI", 11), activestyle="none", borderwidth=0, highlightthickness=0, bg="#ffffff", fg="#1d1d1f", selectbackground="#0066cc", selectforeground="#ffffff")
        self.region_list.pack(fill="both", expand=True)
        self.region_list.bind("<<ListboxSelect>>", self.region_selected)
        self.region_list.bind("<Double-1>", self.open_selected_region)

        self.detail_title = tk.StringVar(value="选择一个地区")
        ttk.Label(right, textvariable=self.detail_title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        self.tags_container = tk.Frame(right, bg="#ffffff")
        self.tags_container.pack(fill="both", expand=True)
        self.show_default_right_panel("查询武器后，从左侧选择一个地区。")

        # 底部署名
        signature_lbl = tk.Label(
            self, text="Designed by lemon冷梦 1009129647 | v1.0",
            bg="#f0f2f5", fg="#b0b0b5", font=("Microsoft YaHei UI", 12)
        )
        signature_lbl.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-10)

    def show_default_right_panel(self, text):
        for widget in self.tags_container.winfo_children(): widget.destroy()
        ttk.Label(self.tags_container, text=text, style="CardText.TLabel").pack(anchor="w", pady=(6, 14))

    def toggle_region_sort(self):
        current_mode = self.user_config.get("region_sort_mode", "default")
        self.user_config["region_sort_mode"] = "yield" if current_mode == "default" else "default"
        save_config(self.user_config)
        self.refresh_region_list()

    def refresh_region_list(self):
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
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab"): return
        typed_text = self.weapon_var.get().strip().lower()
        if not typed_text:
            self.suggestion_list.place_forget()
            return
        filtered = [name for name in self.all_weapon_names if typed_text in name.lower()]
        if filtered:
            self.suggestion_list.delete(0, tk.END)
            for name in filtered[:8]: self.suggestion_list.insert(tk.END, name)
            self.suggestion_list.config(height=min(len(filtered), 8))
            self.suggestion_list.place(in_=self.weapon_entry, x=0, rely=1.0, relwidth=1.0)
            self.suggestion_list.lift()
        else:
            self.suggestion_list.place_forget()

    def on_down_arrow(self, event):
        if self.suggestion_list.winfo_ismapped():
            self.suggestion_list.focus_set()
            self.suggestion_list.selection_set(0)
            return "break"
        
    def on_up_arrow(self, event):
        sel = self.suggestion_list.curselection()
        if sel and sel[0] == 0:
            self.weapon_entry.focus_set()
            self.weapon_entry.icursor(tk.END)
            self.suggestion_list.selection_clear(0, tk.END)
            return "break"
        
    def on_suggestion_select(self, event):
        sel = self.suggestion_list.curselection()
        if sel:
            self.weapon_var.set(self.suggestion_list.get(sel[0]))
            self.suggestion_list.place_forget()
            self.weapon_entry.focus_set()
            self.search()

    def hide_suggestion_list(self, event):
        if not hasattr(self, 'suggestion_list') or not hasattr(self, 'weapon_entry'): return
        if event.widget not in (self.weapon_entry, self.suggestion_list):
            self.suggestion_list.place_forget()

    def search(self):
        if hasattr(self, 'suggestion_list'): self.suggestion_list.place_forget()
        name = self.weapon_var.get().strip()
        w = weapon_by_name.get(name)
        if w is None:
            matches = [x for x in weapons if name and name.lower() in x["name"].lower()]
            if len(matches) == 1:
                w = matches[0]; self.weapon_var.set(w["name"])
            elif matches:
                messagebox.showinfo("找到多个武器", "请从下拉框选择具体武器：\n" + "\n".join(x["name"] for x in matches[:12])); return
            else:
                messagebox.showwarning("未找到武器", f"没有找到“{name}”。"); return

        hist = self.user_config.setdefault("history", [])
        actual_name = w["name"]
        if actual_name in hist: hist.remove(actual_name)
        hist.insert(0, actual_name)
        if len(hist) > 6: hist.pop()
        save_config(self.user_config)
        self.refresh_history_ui()
        
        self.current_weapon = w
        main, sub, skill = triple(w)
        self.status.set(f"目标：{w['name']}   {rarity_text(w.get('rarity'))}   {main} / {sub} / {skill}")
        self.refresh_region_list()

    def refresh_history_ui(self):
        for widget in self.history_frame.winfo_children(): widget.destroy()
        history_list = self.user_config.get("history", [])
        if not history_list: return
        ttk.Label(self.history_frame, text="历史记录：", style="CardText.TLabel").pack(side="left")
        for weapon_name in history_list:
            tag_frame = tk.Frame(self.history_frame, bg="#f0f2f5", cursor="hand2", padx=8, pady=2)
            tag_frame.pack(side="left", padx=(0, 8))
            name_lbl = tk.Label(tag_frame, text=weapon_name, bg="#f0f2f5", fg="#1d1d1f", font=("Microsoft YaHei UI", 10))
            name_lbl.pack(side="left")
            close_lbl = tk.Label(tag_frame, text="×", bg="#f0f2f5", fg="#999999", font=("Microsoft YaHei UI", 10, "bold"))
            close_lbl.pack(side="left", padx=(4, 0))
            def make_events(name_val):
                tag_frame.bind("<Button-1>", lambda e: self.search_from_history(name_val))
                name_lbl.bind("<Button-1>", lambda e: self.search_from_history(name_val))
                def on_delete(e):
                    self.user_config["history"].remove(name_val)
                    save_config(self.user_config)
                    self.refresh_history_ui()
                close_lbl.bind("<Button-1>", on_delete)
                close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg="#d40000"))
                close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg="#999999"))
            make_events(weapon_name)

    def search_from_history(self, name):
        self.weapon_var.set(name)
        self.search()

    def _draw_tags(self, parent, items, bg_col, fg_col):
        frame = tk.Frame(parent, bg="#ffffff")
        frame.pack(anchor="w", fill="x", pady=(8, 12))
        max_cols = 8 
        for i, text in enumerate(items):
            lbl = tk.Label(frame, text=text, bg=bg_col, fg=fg_col, font=("Microsoft YaHei UI", 11, "bold"), padx=14, pady=6)
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
            for widget in self.tags_container.winfo_children(): widget.destroy()
                
            ttk.Label(self.tags_container, text="【该地区副词条池】", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
            self._draw_tags(self.tags_container, region.get("sub_attributes", []), "#e8f0fe", "#1a73e8")
            sub_count = len(strategy_weapons(region, "sub", sub))
            tk.Label(self.tags_container, text=f"💡 与【{self.current_weapon['name']}】的副词条 ({sub}) 相同的武器有 {sub_count} 把", bg="#ffffff", fg="#1a73e8", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 15))
            
            ttk.Label(self.tags_container, text="【该地区技能池】", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
            self._draw_tags(self.tags_container, region.get("skills", []), "#fef0e8", "#e84d1a")
            skill_count = len(strategy_weapons(region, "skill", skill))
            tk.Label(self.tags_container, text=f"💡 与【{self.current_weapon['name']}】的技能 ({skill}) 相同的武器有 {skill_count} 把", bg="#ffffff", fg="#e84d1a", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(0, 15))
            
            ttk.Label(self.tags_container, text="👉 双击左侧列表，或点击下方按钮对比刷取策略。", style="CardText.TLabel").pack(anchor="w", pady=(10, 0))
            btn = self._create_primary_btn(self.tags_container, "打开刷取策略对比", self.open_selected_region)
            btn.pack(anchor="w", pady=(10, 10))

    def open_selected_region(self, event=None):
        if not self.current_weapon: return
        sel = self.region_list.curselection()
        if not sel: return
        region = next((r for r in regions if r["name"] == self.region_list.get(sel[0])), None)
        if region: self.open_detail(region)

    def open_detail(self, region):
        win = tk.Toplevel(self)
        win.title(f"{region['name']} - 刷取策略")
        win.geometry(self.geometry())
        win.minsize(1050, 620)
        win.configure(bg="#f4f5f7")
        outer = ttk.Frame(win, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        w = self.current_weapon
        main, sub, skill = triple(w)
        
        header = ttk.Frame(outer, style="Card.TFrame", padding=14)
        header.pack(fill="x", pady=(0, 14))
        header_left = ttk.Frame(header, style="Card.TFrame")
        header_left.pack(side="left", fill="both", expand=True)
        ttk.Label(header_left, text=region["name"], style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(header_left, text=f"目标武器：{w['name']} {rarity_text(w.get('rarity'))}    |    {main} / {sub} / {skill}", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
        ttk.Label(header_left, text=f"该地区副词条：{'、'.join(region.get('sub_attributes', []))}    |    技能：{'、'.join(region.get('skills', []))}", style="CardText.TLabel").pack(anchor="w", pady=(5, 0))
        header_right = ttk.Frame(header, style="Card.TFrame")
        header_right.pack(side="right", fill="y", padx=(10, 10))
        self._create_primary_btn(header_right, "< 返回上一栏", win.destroy).pack(expand=True)
        
        bar = ttk.Frame(outer, style="Card.TFrame", padding=10)
        bar.pack(fill="x", pady=(0, 14))
        ttk.Label(bar, text="两种刷法同时展示：", style="CardText.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(bar, text="V1 仅展示信息，不评分、不推荐。", style="CardText.TLabel").pack(side="right")
        
        content = ttk.Frame(outer, style="App.TFrame")
        content.pack(fill="both", expand=True)
        
        tree_sub = self.build_panel(content, region, "sub", sub, f"锁定副词条：{sub}")
        tree_skill = self.build_panel(content, region, "skill", skill, f"锁定技能：{skill}")
        
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
            ("name", "武器", 95, "w"), ("rarity", "星级", 50, "center"), ("main", "主词条", 60, "center"), 
            ("sub", "副词条", 45, "center"), ("skill", "技能", 45, "center"),
            ("bead1", "胚子 1", 55, "center"), ("bead2", "胚子 2", 55, "center"), ("bead3", "胚子 3", 55, "center")
        ]
        for col, text, width, anchor in columns_config: tree.column(col, width=width, anchor=anchor)
            
        tree.tag_configure("rarity6", foreground="#d40000")
        tree.tag_configure("rarity5", foreground="#d49a00")
        tree.tag_configure("rarity4", foreground="#7030a0")
        
        sb = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        tree.bind("<Button-1>", lambda e: tree.selection_remove(tree.selection()) if tree.identify_region(e.x, e.y) == "nothing" else None, add="+")
        tree.bind("<Double-1>", lambda e, t=tree: self.edit_bead(e, t))
        
        def refresh_tree():
            for item in tree.get_children(): tree.delete(item)
            current_mode = self.user_config.get("sort_mode", "strategic")
            for col, text, _, _ in columns_config:
                if col == "rarity": tree.heading(col, text=f"{'▼ ' if current_mode == 'rarity' else ''}{text}")
                elif col == "main": tree.heading(col, text=f"{'▼ ' if current_mode == 'strategic' else ''}{text}")
                else: tree.heading(col, text=text)
                    
            target_main = triple(self.current_weapon)[0]
            for w in strategy_weapons(region, lock_type, value, target_main, current_mode):
                main, sub, skill = triple(w)
                b1, b2, b3 = top_3_beads_tuple(w)
                tree.insert("", tk.END, values=(w["name"], rarity_text(w.get("rarity")), main, sub, skill, b1, b2, b3), tags=(rarity_tag(w.get("rarity")),))

        def set_sort_mode(mode):
            if self.user_config.get("sort_mode", "strategic") != mode:
                self.user_config["sort_mode"] = mode
                save_config(self.user_config)
                refresh_tree()
                
        tree.heading("rarity", command=lambda: set_sort_mode("rarity"))
        tree.heading("main", command=lambda: set_sort_mode("strategic"))
        refresh_tree()

    def edit_bead(self, event, tree):
        if tree.identify_region(event.x, event.y) != "cell": return
        try: col_idx = int(tree.identify_column(event.x).replace("#", "")) - 1
        except: return
        if col_idx not in [5, 6, 7]: return
        bead_rank = col_idx - 5
        
        item_id = tree.focus()
        if not item_id: return
        
        values = list(tree.item(item_id, "values"))
        weapon_name, main, sub, skill = values[0], values[2], values[3], values[4]
        
        beads = build_by_triple.setdefault((main, sub, skill), [])
        sorted_beads = sorted(beads, key=lambda b: b.get("main", 0) + b.get("sub", 0) + b.get("skill", 0), reverse=True)
        current_bead = sorted_beads[bead_rank] if bead_rank < len(sorted_beads) else None
        current_str = f"{current_bead['main']}/{current_bead['sub']}/{current_bead['skill']}" if current_bead else "无"
        
        prompt = f"武器：{weapon_name}\n槽位：第 {bead_rank + 1} 顺位 (当前: {current_str})\n\n请输入新胚子数值，支持格式: 411 或 4/1/1 或 4 1 1\n(若要删除该胚子，请输入 0 或直接留空清空):"
        new_val = simpledialog.askstring("修改胚子", prompt, parent=tree.winfo_toplevel())
        if new_val is None: return
        new_val = new_val.strip()
        
        if not new_val or new_val == "0":
            if current_bead in beads: beads.remove(current_bead)
        else:
            nums = re.findall(r'\d+', new_val)
            if len(nums) == 1 and len(new_val) == 3 and new_val.isdigit(): m, s, sk = int(new_val[0]), int(new_val[1]), int(new_val[2])
            elif len(nums) == 3: m, s, sk = int(nums[0]), int(nums[1]), int(nums[2])
            else:
                messagebox.showerror("格式错误", "无法识别输入的数值，请使用 411 或 4/1/1 格式。")
                return
            if current_bead in beads:
                current_bead["main"], current_bead["sub"], current_bead["skill"] = m, s, sk
            else: beads.append({"main": m, "sub": s, "skill": sk})
                
        target_build = next((x for x in builds_data.get("builds", []) if x.get("main") == main and x.get("sub") == sub and x.get("skill") == skill), None)
        if not target_build:
            target_build = {"main": main, "sub": sub, "skill": skill, "beads": beads}
            builds_data["builds"].append(target_build)
        else: target_build["beads"] = beads
            
        try:
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f: json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入 builds.json:\n{e}")
            return
            
        w_fake = {"attributes": {"主词条": main, "副词条": sub, "技能": skill}}
        new_b1, new_b2, new_b3 = top_3_beads_tuple(w_fake)
        values[5], values[6], values[7] = new_b1, new_b2, new_b3
        tree.item(item_id, values=values)

    # ================= 弹窗管理引擎 =================
    def open_data_manager(self):
        win = tk.Toplevel(self)
        win.title("数据录入与管理")
        win.geometry("900x700")
        win.minsize(850, 650)
        win.configure(bg="#f0f2f5")
        win.grab_set()

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)

        def create_danger_btn(parent, text, command):
            btn = tk.Label(parent, text=text, bg="#dc3545", fg="#ffffff", font=("Microsoft YaHei UI", 11, "bold"), cursor="hand2", padx=24, pady=10)
            btn.bind("<Enter>", lambda e: btn.config(bg="#c82333"))
            btn.bind("<Leave>", lambda e: btn.config(bg="#dc3545"))
            btn.bind("<Button-1>", lambda e: command())
            return btn

        # --- 🗡️ 武器库管理 ---
        tab_w = tk.Frame(notebook, bg="#ffffff")
        notebook.add(tab_w, text="  🗡️ 武器库管理  ")

        left_w = tk.Frame(tab_w, bg="#f8f9fa")
        left_w.pack(side="left", fill="y")
        self._create_secondary_btn(left_w, "✚ 录入新武器", lambda: prep_w_add()).pack(fill="x", padx=10, pady=10)
        list_w = tk.Listbox(left_w, width=20, font=("Microsoft YaHei UI", 11), activestyle="none", borderwidth=0, highlightthickness=0, selectbackground="#0066cc", selectforeground="#ffffff")
        list_w.pack(fill="both", expand=True, padx=10, pady=(0,10))

        right_w = tk.Frame(tab_w, bg="#ffffff", padx=40, pady=30)
        right_w.pack(side="left", fill="both", expand=True)

        lbl_w_title = tk.Label(right_w, text="录入新武器", bg="#ffffff", font=("Microsoft YaHei UI", 14, "bold"), fg="#1d1d1f")
        lbl_w_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        def build_row(parent, label_text, row_idx): tk.Label(parent, text=label_text, bg="#ffffff", font=("Microsoft YaHei UI", 11)).grid(row=row_idx, column=0, sticky="w", pady=10)

        w_name_var, w_rarity_var = tk.StringVar(), tk.StringVar(value="6")
        w_main_var, w_sub_var, w_skill_var = tk.StringVar(), tk.StringVar(), tk.StringVar()

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

        w_state = {"mode": "add", "old_name": ""}
        btn_box_w = tk.Frame(right_w, bg="#ffffff")
        btn_box_w.grid(row=6, column=0, columnspan=2, sticky="w", pady=30)
        
        def refresh_list_w():
            list_w.delete(0, tk.END)
            for w in weapons: list_w.insert(tk.END, w["name"])

        def prep_w_add():
            list_w.selection_clear(0, tk.END)
            w_state["mode"] = "add"
            lbl_w_title.config(text="录入新武器")
            w_name_var.set(""); w_main_var.set(""); w_sub_var.set(""); w_skill_var.set("")
            btn_del_w.pack_forget()

        def on_w_select(event):
            sel = list_w.curselection()
            if not sel: return
            w_name = list_w.get(sel[0])
            w = weapon_by_name[w_name]
            w_state["mode"], w_state["old_name"] = "edit", w_name
            lbl_w_title.config(text=f"修改武器：{w_name}")
            w_name_var.set(w["name"])
            w_rarity_var.set(str(w.get("rarity", 6)))
            main, sub, skill = triple(w)
            w_main_var.set(main); w_sub_var.set(sub); w_skill_var.set(skill)
            btn_del_w.pack(side="right", padx=(15, 0))

        list_w.bind("<<ListboxSelect>>", on_w_select)

        def save_weapon():
            name = w_name_var.get().strip()
            if not all([name, w_rarity_var.get(), w_main_var.get(), w_sub_var.get(), w_skill_var.get()]): return messagebox.showwarning("提示", "所有字段都必须填写！", parent=win)
            
            if w_state["mode"] == "add":
                if name in weapon_by_name: return messagebox.showwarning("提示", f"武器 '{name}' 已存在！", parent=win)
                new_w = {"name": name, "rarity": int(w_rarity_var.get()), "attributes": {"主词条": w_main_var.get(), "副词条": w_sub_var.get(), "技能": w_skill_var.get()}}
                weapons.append(new_w)
                weapon_by_name[name] = new_w
                self.all_weapon_names.append(name)
                msg = f"新武器 '{name}' 已成功录入！"
            else:
                old = w_state["old_name"]
                if name != old and name in weapon_by_name: return messagebox.showwarning("提示", f"武器名称 '{name}' 已被占用！", parent=win)
                for w in weapons:
                    if w["name"] == old:
                        w.update({"name": name, "rarity": int(w_rarity_var.get()), "attributes": {"主词条": w_main_var.get(), "副词条": w_sub_var.get(), "技能": w_skill_var.get()}})
                        break
                if name != old: 
                    weapon_by_name[name] = weapon_by_name.pop(old)
                    self.all_weapon_names.remove(old)
                    self.all_weapon_names.append(name)
                    if old in self.user_config.get("history", []):
                        self.user_config["history"][self.user_config["history"].index(old)] = name
                        save_config(self.user_config)
                        self.refresh_history_ui()
                    if self.current_weapon and self.current_weapon["name"] == old: self.weapon_var.set(name)
                msg = f"武器 '{name}' 已成功修改！"

            weapons_data["weapons"] = weapons
            with open(os.path.join(BASE_DIR, "weapons.json"), "w", encoding="utf-8") as f: json.dump(weapons_data, f, ensure_ascii=False, indent=2)
            refresh_list_w(); prep_w_add()
            messagebox.showinfo("成功", msg, parent=win)
            if self.current_weapon and self.current_weapon["name"] in (name, w_state.get("old_name", "")): self.search()

        def del_weapon():
            old = w_state["old_name"]
            if not messagebox.askyesno("确认", f"确定永久删除武器【{old}】？", parent=win): return
            for w in weapons:
                if w["name"] == old: weapons.remove(w); break
            del weapon_by_name[old]
            self.all_weapon_names.remove(old)
            weapons_data["weapons"] = weapons
            with open(os.path.join(BASE_DIR, "weapons.json"), "w", encoding="utf-8") as f: json.dump(weapons_data, f, ensure_ascii=False, indent=2)
            if old in self.user_config.get("history", []):
                self.user_config["history"].remove(old); save_config(self.user_config); self.refresh_history_ui()
            if self.current_weapon and self.current_weapon["name"] == old:
                self.current_weapon = None; self.weapon_var.set(""); self.status.set("请输入武器名称"); self.region_list.delete(0, tk.END)
                self.show_default_right_panel("武器已被删除，请重新搜索。")
            refresh_list_w(); prep_w_add()
            messagebox.showinfo("删除成功", f"武器 '{old}' 已删除。", parent=win)

        self._create_primary_btn(btn_box_w, "💾 保存", save_weapon).pack(side="left")
        btn_del_w = create_danger_btn(btn_box_w, "🗑️ 删除", del_weapon)
        refresh_list_w(); prep_w_add()

        # --- 🗺️ 地区库管理 ---
        tab_r = tk.Frame(notebook, bg="#ffffff")
        notebook.add(tab_r, text="  🗺️ 地区库管理  ")

        left_r = tk.Frame(tab_r, bg="#f8f9fa")
        left_r.pack(side="left", fill="y")
        self._create_secondary_btn(left_r, "✚ 录入新地区", lambda: prep_r_add()).pack(fill="x", padx=10, pady=10)
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
            r_state["mode"], r_state["old_name"] = "edit", r_name
            lbl_r_title.config(text=f"修改地区：{r_name}")
            r_name_var.set(r_obj["name"])
            for k, v in sub_vars.items(): v.set(k in r_obj.get("sub_attributes", []))
            for k, v in skill_vars.items(): v.set(k in r_obj.get("skills", []))
            btn_del_r.pack(side="right", padx=(15, 0))

        list_r.bind("<<ListboxSelect>>", on_r_select)

        def save_region():
            name = r_name_var.get().strip()
            if not name: return messagebox.showwarning("提示", "地区名称不能为空！", parent=win)
            selected_subs = [k for k, v in sub_vars.items() if v.get()]
            selected_skills = [k for k, v in skill_vars.items() if v.get()]
            if not selected_subs or not selected_skills: return messagebox.showwarning("提示", "必须至少勾选一个副词条和一个技能！", parent=win)

            if r_state["mode"] == "add":
                if any(r["name"] == name for r in regions): return messagebox.showwarning("提示", f"地区 '{name}' 已存在！", parent=win)
                new_r = {"name": name, "sub_attributes": selected_subs, "skills": selected_skills}
                regions.append(new_r)
                msg = f"新地区 '{name}' 已成功录入！"
            else:
                old = r_state["old_name"]
                if name != old and any(r["name"] == name for r in regions): return messagebox.showwarning("提示", f"地区名称 '{name}' 已被占用！", parent=win)
                for r in regions:
                    if r["name"] == old:
                        r.update({"name": name, "sub_attributes": selected_subs, "skills": selected_skills})
                        break
                msg = f"地区 '{name}' 已成功修改！"

            regions_data["regions"] = regions
            with open(os.path.join(BASE_DIR, "regions.json"), "w", encoding="utf-8") as f: json.dump(regions_data, f, ensure_ascii=False, indent=2)
            refresh_list_r(); prep_r_add()
            messagebox.showinfo("成功", msg, parent=win)
            if self.current_weapon: self.refresh_region_list()

        def del_region():
            old = r_state["old_name"]
            if not messagebox.askyesno("确认", f"确定永久删除地区【{old}】？", parent=win): return
            for r in regions:
                if r["name"] == old: regions.remove(r); break
            regions_data["regions"] = regions
            with open(os.path.join(BASE_DIR, "regions.json"), "w", encoding="utf-8") as f: json.dump(regions_data, f, ensure_ascii=False, indent=2)
            refresh_list_r(); prep_r_add()
            messagebox.showinfo("删除成功", f"地区 '{old}' 已删除。", parent=win)
            if self.current_weapon: self.refresh_region_list()

        self._create_primary_btn(btn_box_r, "💾 保存", save_region).pack(side="left")
        btn_del_r = create_danger_btn(btn_box_r, "🗑️ 删除", del_region)
        refresh_list_r(); prep_r_add()

    def initialize_data(self, parent_window=None):
        global builds_data, builds, build_by_triple
        target_parent = parent_window if parent_window else self
        ans = messagebox.askyesno("初始化所有数据与配置", "【警告】此操作将清除您的搜索历史和偏好配置，并【清空所有自定义胚子】。\n\n（系统会自动在本地生成一份 builds_backup.json 备份以便反悔）\n\n是否确认要初始化回到全新状态？", parent=target_parent)
        if not ans: return
        
        try:
            with open(os.path.join(BASE_DIR, "builds_backup.json"), "w", encoding="utf-8") as f: json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("备份失败", f"无法创建备份文件：{e}", parent=target_parent)
            return
            
        self.user_config = {"history": [], "sort_mode": "strategic", "region_sort_mode": "yield", "perfect_mode": "custom", "perfect_score": 7, "perfect_custom": [6, 3, 3], "perfect_count": 2}
        save_config(self.user_config)
        
        builds_data["builds"] = []
        builds.clear(); build_by_triple.clear()
        try:
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f: json.dump(builds_data, f, ensure_ascii=False, indent=2)
        except: pass
            
        self.refresh_history_ui(); self.status.set("请输入武器名称")
        self.current_weapon = None; self.weapon_var.set(""); self.region_list.delete(0, tk.END)
        self.show_default_right_panel("数据已成功初始化。如果您是误操作，请在全局配置中恢复备份。")
        self.detail_title.set("选择一个地区")
        if hasattr(self, 'suggestion_list'): self.suggestion_list.place_forget()
        messagebox.showinfo("成功", "所有用户数据已成功初始化，已生成备份文件 builds_backup.json！", parent=target_parent)

    def restore_backup_data(self, parent_window=None):
        global builds_data, builds, build_by_triple
        target_parent = parent_window if parent_window else self
        backup_path = os.path.join(BASE_DIR, "builds_backup.json")
        if not os.path.exists(backup_path):
            return messagebox.showwarning("无法恢复", "未找到备份文件 (builds_backup.json)！", parent=target_parent)
        if not messagebox.askyesno("恢复备份数据", "是否确认要读取 builds_backup.json 中的数据？\n此操作将覆盖您当前的全部胚子数据！", parent=target_parent): return
        
        try:
            with open(backup_path, "r", encoding="utf-8") as f: backup_data = json.load(f)
            builds_data.clear(); builds_data.update(backup_data)
            builds.clear(); builds.extend(builds_data.get("builds", []))
            build_by_triple.clear()
            for x in builds: build_by_triple[(x.get("main", ""), x.get("sub", ""), x.get("skill", ""))] = x.get("beads", [])
            with open(os.path.join(BASE_DIR, "builds.json"), "w", encoding="utf-8") as f: json.dump(builds_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("恢复成功", "所有胚子数据已成功从备份中恢复！", parent=target_parent)
            if self.current_weapon: self.search()
        except Exception as e:
            messagebox.showerror("恢复失败", f"读取备份文件时出错：\n{e}", parent=target_parent)

    def open_all_weapons_manager(self):
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
        columns_config = [("name", "武器名称", 140, "w"), ("rarity", "星级", 50, "center"), ("main", "主词条", 70, "center"), ("sub", "副词条", 70, "center"), ("skill", "技能", 70, "center"), ("bead1", "胚子 1", 70, "center"), ("bead2", "胚子 2", 70, "center"), ("bead3", "胚子 3", 70, "center")]
        
        sort_state = {"col": None, "reverse": False}
        def sort_by_col(col):
            if sort_state["col"] == col: sort_state["reverse"] = not sort_state["reverse"]
            else: sort_state["col"] = col; sort_state["reverse"] = True 
                
            data = []
            for child in tree.get_children():
                val = tree.set(child, col)
                if col == "rarity": val = int(val.replace("★", "")) if "★" in val else 0
                data.append((val, child))
                
            data.sort(reverse=sort_state["reverse"], key=lambda x: x[0])
            for idx, item in enumerate(data): tree.move(item[1], '', idx)
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
        
        tree.bind("<Button-1>", lambda e: tree.selection_remove(tree.selection()) if tree.identify_region(e.x, e.y) == "nothing" else None, add="+")
        tree.bind("<Double-1>", lambda e, t=tree: self.edit_bead(e, t))
        
        for w in weapons:
            main, sub, skill = triple(w)
            b1, b2, b3 = top_3_beads_tuple(w)
            tree.insert("", tk.END, values=(w["name"], rarity_text(w.get("rarity")), main, sub, skill, b1, b2, b3), tags=(rarity_tag(w.get("rarity")),))
        sort_by_col("rarity")

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("全局配置 (Settings)")
        
        window_width = 950
        window_height = 620
        center_x = max(0, self.winfo_x() + (self.winfo_width() - window_width) // 2)
        center_y = max(0, self.winfo_y() + (self.winfo_height() - window_height) // 2)

        win.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        win.minsize(900, 600)
        win.configure(bg="#ffffff")
        win.grab_set()

        sidebar = tk.Frame(win, bg="#f3f3f3", width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="设置", font=("Microsoft YaHei UI", 16, "bold"), bg="#f3f3f3", fg="#1d1d1f").pack(anchor="w", padx=20, pady=20)
        tk.Label(sidebar, text="通用设置", font=("Microsoft YaHei UI", 10), bg="#e4e6f1", fg="#000000", anchor="w", padx=20, pady=8, cursor="hand2").pack(fill="x")
        tk.Label(sidebar, text="数据管理", font=("Microsoft YaHei UI", 10), bg="#f3f3f3", fg="#6e6e73", anchor="w", padx=20, pady=8, cursor="hand2").pack(fill="x")

        content = tk.Frame(win, bg="#ffffff", padx=40, pady=30)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(content, text="通用设置", font=("Microsoft YaHei UI", 18, "bold"), bg="#ffffff", fg="#1d1d1f").pack(anchor="w", pady=(0, 20))

        def create_setting_item(parent, title, desc, control_fn):
            f = tk.Frame(parent, bg="#ffffff"); f.pack(fill="x", pady=12)
            tf = tk.Frame(f, bg="#ffffff"); tf.pack(side="left", fill="x", expand=True)
            tk.Label(tf, text=title, font=("Microsoft YaHei UI", 11, "bold"), bg="#ffffff", fg="#1d1d1f").pack(anchor="w")
            tk.Label(tf, text=desc, font=("Microsoft YaHei UI", 9), bg="#ffffff", fg="#6e6e73").pack(anchor="w", pady=(4,0))
            cf = tk.Frame(f, bg="#ffffff"); cf.pack(side="right", padx=(20, 0))
            control_fn(cf)

        def ctrl_perfect_criteria(parent):
            mode_map = {"none": "不启用", "score": "综合得分 (技能分翻倍)", "custom": "自定义三维下限 (默认)"}
            inv_mode_map = {v: k for k, v in mode_map.items()}
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
                    cb_score.bind("<<ComboboxSelected>>", lambda e: (self.user_config.update({"perfect_score": score_var.get()}), save_and_refresh()))
                    
                elif current_mode == "custom":
                    vals = self.user_config.get("perfect_custom", [6, 3, 3])
                    m_var, s_var, sk_var = tk.IntVar(value=vals[0]), tk.IntVar(value=vals[1]), tk.IntVar(value=vals[2])
                    def on_custom_change(e):
                        self.user_config["perfect_custom"] = [m_var.get(), s_var.get(), sk_var.get()]
                        save_and_refresh()

                    tk.Label(param_frame, text="主≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left")
                    cb_m = ttk.Combobox(param_frame, textvariable=m_var, values=[2,3,4,5,6], state="readonly", width=3); cb_m.pack(side="left")
                    tk.Label(param_frame, text="副≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(5,0))
                    cb_s = ttk.Combobox(param_frame, textvariable=s_var, values=[0,1,2,3,4,5,6], state="readonly", width=3); cb_s.pack(side="left")
                    tk.Label(param_frame, text="技≥", bg="#ffffff", font=("Microsoft YaHei UI", 10)).pack(side="left", padx=(5,0))
                    cb_sk = ttk.Combobox(param_frame, textvariable=sk_var, values=[0,1,2,3], state="readonly", width=3); cb_sk.pack(side="left")
                    
                    for cb in (cb_m, cb_s, cb_sk): cb.bind("<<ComboboxSelected>>", on_custom_change)
                if event: save_and_refresh()

            cb_mode.bind("<<ComboboxSelected>>", build_params)
            build_params() 

        create_setting_item(content, "完美基质判定标准", "可按综合得分(技能评分x2)或自定义三维底线进行毕业判定。", ctrl_perfect_criteria)

        def ctrl_perfect_count(parent):
            val_map = {1: "1 颗", 2: "2 颗 (默认)", 3: "3 颗"}
            inv_map = {v: k for k, v in val_map.items()}
            var = tk.StringVar(value=val_map.get(self.user_config.get("perfect_count", 2), "2 颗 (默认)"))
            cb = ttk.Combobox(parent, textvariable=var, values=list(val_map.values()), state="readonly", width=22, font=("Microsoft YaHei UI", 10))
            cb.pack()
            cb.bind("<<ComboboxSelected>>", lambda e: (self.user_config.update({"perfect_count": inv_map[var.get()]}), save_config(self.user_config), self.refresh_region_list() if self.current_weapon else None))
            
        create_setting_item(content, "毕业所需完美基质数量", "当完美基质达到此数量时，该词条排列不再加入刷取策略计算。", ctrl_perfect_count)

        def ctrl_region_sort(parent):
            var = tk.StringVar(value="默认排序" if self.user_config.get("region_sort_mode") == "default" else "收益优先")
            cb = ttk.Combobox(parent, textvariable=var, values=["收益优先", "默认排序"], state="readonly", width=20, font=("Microsoft YaHei UI", 10))
            cb.pack()
            cb.bind("<<ComboboxSelected>>", lambda e: (self.user_config.update({"region_sort_mode": "default" if var.get() == "默认排序" else "yield"}), save_config(self.user_config), self.refresh_region_list() if self.current_weapon else None))
        create_setting_item(content, "可刷地区列表排序", "控制主页面左侧“可刷地区”的默认展示优先级。", ctrl_region_sort)

        def ctrl_bead_sort(parent):
            var = tk.StringVar(value="星级优先" if self.user_config.get("sort_mode") == "rarity" else "收益优先 (按数量)")
            cb = ttk.Combobox(parent, textvariable=var, values=["收益优先 (按数量)", "星级优先"], state="readonly", width=20, font=("Microsoft YaHei UI", 10))
            cb.pack()
            cb.bind("<<ComboboxSelected>>", lambda e: (self.user_config.update({"sort_mode": "rarity" if var.get() == "星级优先" else "strategic"}), save_config(self.user_config)))
        create_setting_item(content, "策略页面珠子排列方式", "在次要页面中，武器矩阵是以星级还是以流派收益数量排序。", ctrl_bead_sort)

        ttk.Separator(content, orient="horizontal").pack(fill="x", pady=15)

        def ctrl_init(parent):
            btn_frame = tk.Frame(parent, bg="#ffffff"); btn_frame.pack(anchor="e")
            
            btn_init = tk.Label(btn_frame, text="初始化所有数据与配置", bg="#dc3545", fg="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2", padx=16, pady=6)
            btn_init.bind("<Enter>", lambda e: btn_init.config(bg="#c82333"))
            btn_init.bind("<Leave>", lambda e: btn_init.config(bg="#dc3545"))
            btn_init.bind("<Button-1>", lambda e: self.initialize_data(parent_window=win))
            btn_init.pack(side="left")

            btn_restore = tk.Label(btn_frame, text="恢复备份数据", bg="#28a745", fg="#ffffff", font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2", padx=16, pady=6)
            btn_restore.bind("<Enter>", lambda e: btn_restore.config(bg="#218838"))
            btn_restore.bind("<Leave>", lambda e: btn_restore.config(bg="#28a745"))
            btn_restore.bind("<Button-1>", lambda e: self.restore_backup_data(parent_window=win))
            btn_restore.pack(side="left", padx=(10, 0))
            
        create_setting_item(content, "数据初始化与备份", "初始化将清空自定义胚子并生成备份。误操作可通过恢复备份还原。", ctrl_init)


if __name__ == "__main__":
    App().mainloop()