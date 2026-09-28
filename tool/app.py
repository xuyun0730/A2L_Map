import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from a2l_parser import parse_a2l
from exporter import export_csv, export_json
from map_parser import parse_map
from matcher import match_indexes


_TkBase = TkinterDnD.Tk if TkinterDnD else tk.Tk


class App(_TkBase):
    def __init__(self) -> None:
        super().__init__()
        self.title("MAP / A2L 变量地址匹配工具")
        self.geometry("1320x760")
        self.minsize(980, 620)
        self.configure(bg="#f8fafc")
        self.records = []
        self.search_mode = tk.StringVar(value="name")
        self.type_filter = tk.StringVar(value="全部")
        self.grade_filter = tk.StringVar(value="全部")
        self.match_filter = tk.StringVar(value="全部")
        self.min_address = tk.StringVar()
        self.max_address = tk.StringVar()
        self.slider_min = tk.DoubleVar(value=0)
        self.slider_max = tk.DoubleVar(value=100)
        self._address_bounds = (0, 1)
        self._debounce_job = None
        self._tooltip = None
        self._query_placeholder = ""
        self.map_file = tk.StringVar(value="MAP：未选择")
        self.a2l_file = tk.StringVar(value="A2L：未选择")
        self._build()

    def _build(self) -> None:
        self._setup_style()
        outer = ttk.Frame(self, padding=(18, 14))
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="MAP / A2L", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="变量地址匹配与排查工作台", style="Subtitle.TLabel").pack(anchor="w")

        top_panel = ttk.Frame(outer, style="Card.TFrame", padding=12)
        top_panel.pack(fill="x", pady=(0, 10))
        top_panel.columnconfigure(0, weight=1, uniform="top")
        top_panel.columnconfigure(1, weight=1, uniform="top")
        top_panel.rowconfigure(0, weight=1)
        top_panel.rowconfigure(1, weight=1)

        file_panel = ttk.Frame(top_panel, style="Inner.TFrame")
        file_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12))
        file_panel.columnconfigure(1, weight=1)
        ttk.Label(file_panel, text="MAP文件：", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6)
        )
        self.map_drop = self._file_drop_box(file_panel, "选择文件", self.map_file, self.load_map)
        self.map_drop.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        ttk.Label(file_panel, text="A2L文件：", style="Section.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        self.a2l_drop = self._file_drop_box(file_panel, "选择文件", self.a2l_file, self.load_a2l)
        self.a2l_drop.grid(row=1, column=1, sticky="ew", pady=(6, 0))

        query_panel = ttk.Frame(top_panel, style="Inner.TFrame")
        query_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(12, 0))
        query_panel.columnconfigure(0, weight=1)
        query_panel.rowconfigure(0, weight=1)
        query_panel.rowconfigure(1, weight=1)
        query_box = ttk.Frame(query_panel, style="Query.TFrame")
        query_box.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        query_box.columnconfigure(1, weight=1)
        ttk.Label(query_box, text="查询：", style="Muted.TLabel").grid(row=0, column=0, padx=(8, 4))
        self.query = ttk.Entry(query_box, width=42, style="Search.TEntry")
        self.query.grid(row=0, column=1, sticky="ew", ipady=5)
        self.query.bind("<KeyRelease>", lambda _: self.schedule_search())
        self.query.bind("<Return>", lambda _: self.search())
        self.query_hint = ttk.Label(query_box, text="", style="Hint.TLabel")
        self.query_hint.grid(row=0, column=2, padx=(8, 10))
        ttk.Button(query_box, text="清空", command=self.clear_query, style="Small.TButton").grid(
            row=0, column=3, padx=(4, 8)
        )
        action_row = ttk.Frame(query_panel, style="Inner.TFrame")
        action_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        for text, value in (("包含", "name"), ("严格", "strict"), ("地址", "address")):
            ttk.Radiobutton(
                action_row, text=text, variable=self.search_mode, value=value,
                command=self._search_mode_changed,
            ).pack(side="left", padx=(0, 10))
        ttk.Button(action_row, text="导出 JSON", command=lambda: self.export(export_json, "*.json")).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(action_row, text="导出 CSV", command=lambda: self.export(export_csv, "*.csv")).pack(
            side="right", padx=(8, 0)
        )
        self._update_query_hint()

        filters = ttk.Frame(outer, style="Card.TFrame", padding=12)
        filters.pack(fill="x", pady=(0, 10))
        filters.columnconfigure(0, weight=1)
        filters.columnconfigure(1, weight=1)
        filters.columnconfigure(2, weight=1)

        type_box = self._filter_box(
            filters, "对象类型", self.type_filter, ("全部", "MEASUREMENT", "CHARACTERISTIC")
        )
        type_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        grade_box = self._filter_box(
            filters, "等级", self.grade_filter,
            ("全部", "A：完全一致", "B：地址匹配", "C：名称匹配", "D：未匹配", "E：歧义")
        )
        grade_box.grid(row=0, column=1, sticky="ew", padx=8)
        match_box = self._filter_box(
            filters, "匹配状态", self.match_filter,
            ("全部", "名称+地址", "仅地址", "仅名称", "未匹配", "歧义")
        )
        match_box.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        address_box = ttk.Frame(filters, style="Inner.TFrame")
        address_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        address_box.columnconfigure(1, weight=1)
        address_box.columnconfigure(3, weight=1)
        ttk.Label(address_box, text="起始地址", style="Muted.TLabel").grid(row=0, column=0, padx=(0, 6))
        self.min_entry = ttk.Entry(address_box, textvariable=self.min_address, width=18)
        self.min_entry.grid(row=0, column=1, sticky="ew", padx=(0, 18))
        self.min_entry.bind("<KeyRelease>", lambda _: self.schedule_search())
        ttk.Label(address_box, text="终止地址", style="Muted.TLabel").grid(row=0, column=2, padx=(0, 6))
        self.max_entry = ttk.Entry(address_box, textvariable=self.max_address, width=18)
        self.max_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12))
        self.max_entry.bind("<KeyRelease>", lambda _: self.schedule_search())
        ttk.Button(address_box, text="清空", command=self.clear_filters, style="Clear.TButton").grid(
            row=0, column=4, sticky="ns"
        )

        slider_box = ttk.Frame(filters, style="Inner.TFrame")
        slider_box.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        slider_box.columnconfigure(0, weight=1)
        slider_box.columnconfigure(1, weight=1)
        self.min_scale = ttk.Scale(
            slider_box, from_=0, to=100, variable=self.slider_min, command=self._slider_changed
        )
        self.max_scale = ttk.Scale(
            slider_box, from_=0, to=100, variable=self.slider_max, command=self._slider_changed
        )
        self.min_scale.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.max_scale.grid(row=0, column=1, sticky="ew")
        self.range_label = ttk.Label(
            slider_box, text="加载数据后可拖动地址范围", style="Muted.TLabel"
        )
        self.range_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        self.stats = ttk.Frame(outer, style="Card.TFrame", padding=(12, 8))
        self.stats.pack(fill="x", pady=(0, 10))
        self.info = ttk.Label(self.stats, text="请先选择 MAP 和 A2L", style="Muted.TLabel")
        self.info.pack(side="left")
        ttk.Button(self.stats, text="重新匹配", command=self._rematch, style="Small.TButton").pack(
            side="left", padx=(12, 0)
        )
        self.stat_buttons = {}
        for grade, label in (("A", "完全一致"), ("B", "地址匹配"), ("C", "名称匹配"), ("D", "未匹配"), ("E", "歧义")):
            button = ttk.Button(self.stats, text=f"{label} 0", style=f"Stat{grade}.TButton",
                                command=lambda value=grade: self._set_grade(value))
            button.pack(side="right", padx=(6, 0))
            self.stat_buttons[grade] = button

        columns = ("name", "type", "a2l", "vma", "lma", "size", "status", "explanation", "diagnostics")
        table_frame = ttk.Frame(outer, style="Card.TFrame", padding=8)
        table_frame.pack(fill="both", expand=True)
        self.empty_label = ttk.Label(
            table_frame, text="暂无结果\n请先选择 MAP 和 A2L，或调整查询条件",
            style="Empty.TLabel", justify="center",
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {"name": "变量", "type": "类型", "a2l": "A2L 地址", "vma": "MAP VMA", "lma": "MAP LMA", "size": "Size", "status": "等级", "explanation": "等级说明", "diagnostics": "诊断"}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=120 if column not in {"diagnostics", "explanation"} else 250, anchor="e" if column in {"a2l", "vma", "lma", "size"} else "w")
        self.table.column("status", width=70, anchor="center")
        self.table.tag_configure("A", background="#e6f7ed", foreground="#0f7a45")
        self.table.tag_configure("B", background="#fff7df", foreground="#a45a00")
        self.table.tag_configure("C", background="#fff7df", foreground="#a45a00")
        self.table.tag_configure("D", background="#fee2e2", foreground="#b91c1c")
        self.table.tag_configure("E", background="#fce7f3", foreground="#9d174d")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<Motion>", self._show_tooltip)
        self.table.bind("<Leave>", self._hide_tooltip)
        self.table.bind("<Double-1>", self.copy_cell)
        self.table.bind("<Control-c>", self.copy_cell)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#f8fafc", foreground="#1e293b")
        style.configure("Header.TFrame", background="#f8fafc")
        style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        style.configure("Query.TFrame", background="#f8fafc", relief="solid", borderwidth=1)
        style.configure("Inner.TFrame", background="#ffffff")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground="#0f172a", background="#f8fafc")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#64748b", background="#f8fafc")
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 11), foreground="#0f172a", background="#ffffff")
        style.configure("Muted.TLabel", foreground="#64748b", background="#ffffff")
        style.configure("File.TLabel", foreground="#475569", background="#ffffff", font=("Segoe UI", 9))
        style.configure("Empty.TLabel", foreground="#94a3b8", background="#ffffff", font=("Segoe UI", 11))
        style.configure("DropTitle.TLabel", foreground="#334155", background="#ffffff",
                        font=("Segoe UI Semibold", 10))
        style.configure("Hint.TLabel", foreground="#94a3b8", background="#ffffff", font=("Segoe UI", 9))
        style.configure("Search.TEntry", padding=(7, 4), fieldbackground="#f8fafc")
        style.map("Search.TEntry", fieldbackground=[("focus", "#eff6ff")],
                  bordercolor=[("focus", "#2563eb")])
        style.configure("Small.TButton", padding=(6, 3))
        style.configure("Clear.TButton", padding=(12, 6), font=("Segoe UI Semibold", 10))
        style.configure("TButton", padding=(10, 6), background="#ffffff")
        style.map("TButton", background=[("active", "#e0f2fe")])
        for grade, color in (("A", "#dcfce7"), ("B", "#fef3c7"), ("C", "#fef3c7"), ("D", "#fee2e2"), ("E", "#fce7f3")):
            style.configure(f"Stat{grade}.TButton", background=color, padding=(8, 5))
        style.configure("Treeview", rowheight=30, background="#ffffff", fieldbackground="#ffffff", borderwidth=0)
        style.configure("Treeview.Heading", background="#f1f5f9", foreground="#334155", font=("Segoe UI Semibold", 10), padding=8)
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#1e3a8a")])

    def _file_drop_box(self, parent, title, variable, browse_command):
        box = tk.Frame(parent, bg="#ffffff", highlightthickness=1, highlightbackground="#cbd5e1",
                       padx=10, pady=7)
        tk.Label(box, text=title, bg="#ffffff", fg="#334155",
                 font=("Segoe UI Semibold", 10)).pack(side="left")
        tk.Label(box, textvariable=variable, bg="#ffffff", fg="#64748b",
                 anchor="w").pack(side="left", fill="x", expand=True, padx=(12, 8))
        ttk.Button(box, text="选择文件", command=browse_command, style="Small.TButton").pack(side="right")
        if DND_FILES:
            box.drop_target_register(DND_FILES)
            box.dnd_bind("<<Drop>>", lambda event: self._drop_file(event, title))
        else:
            tk.Label(box, text="拖拽需安装 tkinterdnd2", bg="#ffffff", fg="#b45309",
                     font=("Segoe UI", 8)).pack(side="right", padx=(4, 8))
        return box

    def _drop_file(self, event, title):
        paths = self.tk.splitlist(event.data)
        if not paths:
            return
        path = Path(paths[0])
        suffix = path.suffix.casefold()
        if title.startswith("MAP") and suffix != ".map":
            messagebox.showwarning("文件类型不匹配", "MAP 拖放框只接受 .map 文件。")
            return
        if title.startswith("A2L") and suffix != ".a2l":
            messagebox.showwarning("文件类型不匹配", "A2L 拖放框只接受 .a2l 文件。")
            return
        if title.startswith("MAP"):
            self._load_map_path(path)
        else:
            self._load_a2l_path(path)

    def _combo(self, parent, label, variable, values, column):
        ttk.Label(parent, text=label, style="Muted.TLabel").grid(row=0, column=column, sticky="w")
        combo = ttk.Combobox(parent, textvariable=variable, values=values, width=15, state="readonly")
        combo.grid(row=0, column=column + 1, padx=(4, 8), sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda _: self.schedule_search())

    def _filter_box(self, parent, label, variable, values):
        box = ttk.Frame(parent, style="Inner.TFrame")
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text=label, style="Muted.TLabel").grid(row=0, column=0, padx=(0, 6))
        combo = ttk.Combobox(box, textvariable=variable, values=values, state="readonly")
        combo.grid(row=0, column=1, sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda _: self.schedule_search())
        return box

    def schedule_search(self) -> None:
        if self._debounce_job:
            self.after_cancel(self._debounce_job)
        self._debounce_job = self.after(250, self.search)

    def _search_mode_changed(self) -> None:
        self._update_query_hint()
        self.schedule_search()

    def _update_query_hint(self) -> None:
        hints = {
            "name": "输入部分字符串，如 IMU",
            "strict": "输入完整变量名",
            "address": "十六进制，如 0xB0056364",
        }
        self._query_placeholder = hints[self.search_mode.get()]
        self.query_hint.config(text=self._query_placeholder)

    def clear_query(self) -> None:
        self.query.delete(0, "end")
        self.query.focus_set()
        self.schedule_search()

    def _set_grade(self, grade: str) -> None:
        self.grade_filter.set("" if self.grade_filter.get() == grade else grade)
        if not self.grade_filter.get():
            self.grade_filter.set("全部")
        self.schedule_search()

    def load_map(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("MAP files", "*.map"), ("All files", "*.*")])
        if path:
            self._load_map_path(Path(path))

    def load_a2l(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("A2L files", "*.a2l"), ("All files", "*.*")])
        if path:
            self._load_a2l_path(Path(path))

    def _load_map_path(self, path: Path) -> None:
        self.map_index = parse_map(path)
        self.map_file.set(f"MAP：{path.name}")
        self._reset_search_state()
        self._rematch()

    def _load_a2l_path(self, path: Path) -> None:
        self.a2l_index = parse_a2l(path)
        self.a2l_file.set(f"A2L：{path.name}")
        if not self.a2l_index.objects:
            messagebox.showwarning("A2L 无对象", "\n".join(self.a2l_index.diagnostics))
        self._reset_search_state()
        self._rematch()

    def _reset_search_state(self) -> None:
        if self._debounce_job:
            self.after_cancel(self._debounce_job)
            self._debounce_job = None
        self.query.delete(0, "end")
        self.type_filter.set("全部")
        self.grade_filter.set("全部")
        self.match_filter.set("全部")
        self.min_address.set("")
        self.max_address.set("")
        self.slider_min.set(0)
        self.slider_max.set(100)

    def _rematch(self) -> None:
        if hasattr(self, "map_index") and hasattr(self, "a2l_index"):
            self.records = match_indexes(self.a2l_index, self.map_index)
            addresses = [
                address
                for record in self.records
                for address in (record.a2l_address, record.map_vma, record.map_lma)
                if address is not None
            ]
            if addresses:
                self._address_bounds = (min(addresses), max(addresses))
                self.slider_min.set(0)
                self.slider_max.set(100)
                self.range_label.config(text=f"0x{min(addresses):X} - 0x{max(addresses):X}")
            else:
                self._address_bounds = (0, 1)
                self.range_label.config(text="当前数据没有可用地址")
            self.search()
        else:
            self.records = []
            self.search()

    def search(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        raw_query = self.query.get().strip()
        query = raw_query.lower()
        if self.search_mode.get() == "address":
            candidates = self.address_matches(query)
        elif self.search_mode.get() == "strict":
            candidates = [record for record in self.records if record.name.casefold() == raw_query.casefold()]
        elif not query:
            candidates = self.records
        else:
            candidates = [
                record for record in self.records
                if query in record.name.casefold()
            ]
            candidates.sort(key=lambda record: record.name.casefold())
        matched = [record for record in candidates if self.passes_filters(record)]
        for record in matched:
            fmt = lambda value: "" if value is None else f"0x{value:X}"
            self.table.insert(
                "", "end",
                values=(record.name, record.object_type, fmt(record.a2l_address), fmt(record.map_vma),
                        fmt(record.map_lma), record.size or "", record.status,
                        record.grade_explanation, "; ".join(record.diagnostics)),
                tags=(record.status,),
            )
        if matched:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.empty_label.lift()
        counts = {grade: sum(record.status == grade for record in self.records) for grade in "ABCDE"}
        labels = {"A": "完全一致", "B": "地址匹配", "C": "名称匹配", "D": "未匹配", "E": "歧义"}
        for grade, button in self.stat_buttons.items():
            button.config(text=f"{labels[grade]} {counts[grade]}")
        self.info.config(text=f"当前显示 {len(matched)} / {len(self.records)} 条记录")

    def address_matches(self, query: str):
        if not query:
            return self.records
        try:
            address = int(query, 0) if query.startswith("0x") else int(query, 16)
        except ValueError:
            self.info.config(text="地址格式无效，请输入十六进制，例如 0xB0056364")
            return []
        found = []
        for record in self.records:
            addresses = {record.a2l_address, record.map_vma, record.map_lma}
            symbols = record.map_symbols
            if address in addresses:
                found.append(record)
            for symbol in symbols:
                if symbol.vma <= address < symbol.vma + max(symbol.size, 1) or symbol.lma <= address < symbol.lma + max(symbol.size, 1):
                    if record not in found:
                        found.append(record)
        self.info.config(text=f"地址 0x{address:X} 匹配 {len(found)} 条记录")
        return found

    def passes_filters(self, record) -> bool:
        if self.type_filter.get() != "全部" and record.object_type != self.type_filter.get():
            return False
        if self.grade_filter.get() != "全部" and record.status != self.grade_filter.get():
            return False
        status = {"A：名称+地址": "A", "B：仅地址": "B", "C：仅名称": "C", "D：未匹配": "D", "E：歧义": "E"}.get(self.match_filter.get())
        if status and record.status != status:
            return False
        try:
            low = int(self.min_address.get().strip(), 0) if self.min_address.get().strip() else None
            high = int(self.max_address.get().strip(), 0) if self.max_address.get().strip() else None
        except ValueError:
            messagebox.showerror("地址范围错误", "地址范围请输入十六进制，例如 0xB0000000。")
            return False
        address = record.a2l_address if record.a2l_address is not None else record.map_vma
        if low is None and high is None:
            return True
        return address is not None and (low is None or address >= low) and (high is None or address <= high)

    def clear_filters(self) -> None:
        self.type_filter.set("全部")
        self.grade_filter.set("全部")
        self.match_filter.set("全部")
        self.min_address.set("")
        self.max_address.set("")
        self.slider_min.set(0)
        self.slider_max.set(100)
        self.search()

    def _slider_changed(self, _value=None) -> None:
        if not self.records:
            return
        if self.slider_min.get() > self.slider_max.get():
            if _value is not None and self.slider_min.get() == float(_value):
                self.slider_min.set(self.slider_max.get())
            else:
                self.slider_max.set(self.slider_min.get())
        low, high = self._address_bounds
        span = max(high - low, 1)
        min_value = round(low + span * self.slider_min.get() / 100)
        max_value = round(low + span * self.slider_max.get() / 100)
        self.min_address.set(f"0x{min_value:X}")
        self.max_address.set(f"0x{max_value:X}")
        self.schedule_search()

    def _show_tooltip(self, event) -> None:
        item = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not item:
            self._hide_tooltip()
            return
        values = self.table.item(item, "values")
        index = int(column[1:]) - 1 if column.startswith("#") else -1
        if index < 0 or index >= len(values):
            return
        text = values[7] if index == 6 else str(values[index])
        if not text:
            self._hide_tooltip()
            return
        if self._tooltip is not None:
            self._tooltip.destroy()
        self._tooltip = tk.Toplevel(self)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.configure(bg="#0f172a")
        label = tk.Label(self._tooltip, text=text, bg="#0f172a", fg="#f8fafc",
                         padx=8, pady=5, justify="left", wraplength=520)
        label.pack()
        self._tooltip.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

    def _hide_tooltip(self, _event=None) -> None:
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None

    def copy_cell(self, _event=None) -> str:
        item = self.table.focus() or self.table.identify_row(getattr(_event, "y", 0))
        if not item:
            return "break"
        column = self.table.identify_column(getattr(_event, "x", 0))
        index = int(column[1:]) - 1 if column.startswith("#") else 0
        values = self.table.item(item, "values")
        if values and 0 <= index < len(values):
            self.clipboard_clear()
            self.clipboard_append(str(values[index]))
            self.info.config(text=f"已复制: {values[index]}")
        return "break"

    def export(self, exporter, pattern: str) -> None:
        if not self.records:
            messagebox.showinfo("没有结果", "请先加载 MAP 和 A2L。")
            return
        path = filedialog.asksaveasfilename(filetypes=[("导出文件", pattern)])
        if path:
            exporter(self.records, path)
            self.info.config(text=f"已导出 {len(self.records)} 条记录：{Path(path).name}")


if __name__ == "__main__":
    App().mainloop()
