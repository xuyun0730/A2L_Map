import tkinter as tk
from difflib import SequenceMatcher
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from a2l_parser import parse_a2l
from exporter import export_csv, export_json
from map_parser import parse_map
from matcher import match_indexes


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MAP / A2L 变量地址匹配")
        self.geometry("1100x650")
        self.records = []
        self.search_mode = tk.StringVar(value="name")
        self.type_filter = tk.StringVar(value="全部")
        self.grade_filter = tk.StringVar(value="全部")
        self.match_filter = tk.StringVar(value="全部")
        self.min_address = tk.StringVar()
        self.max_address = tk.StringVar()
        self._build()

    def _build(self) -> None:
        controls = ttk.Frame(self, padding=8)
        controls.pack(fill="x")
        ttk.Button(controls, text="选择 MAP", command=self.load_map).pack(side="left")
        ttk.Button(controls, text="选择 A2L", command=self.load_a2l).pack(side="left", padx=5)
        self.query = ttk.Entry(controls, width=45)
        self.query.pack(side="left", padx=12)
        self.query.bind("<Return>", lambda _: self.search())
        ttk.Radiobutton(controls, text="变量模糊匹配", variable=self.search_mode, value="name").pack(side="left")
        ttk.Radiobutton(controls, text="严格匹配", variable=self.search_mode, value="strict").pack(side="left")
        ttk.Radiobutton(controls, text="地址匹配", variable=self.search_mode, value="address").pack(side="left")
        ttk.Button(controls, text="查询", command=self.search).pack(side="left")
        ttk.Button(controls, text="导出 CSV", command=lambda: self.export(export_csv, "*.csv")).pack(side="left", padx=5)
        ttk.Button(controls, text="导出 JSON", command=lambda: self.export(export_json, "*.json")).pack(side="left")
        filters = ttk.LabelFrame(self, text="逻辑筛选（条件之间为 AND）", padding=5)
        filters.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(filters, text="对象类型").pack(side="left")
        ttk.Combobox(filters, textvariable=self.type_filter, values=("全部", "MEASUREMENT", "CHARACTERISTIC"), width=16, state="readonly").pack(side="left", padx=4)
        ttk.Label(filters, text="等级").pack(side="left")
        ttk.Combobox(filters, textvariable=self.grade_filter, values=("全部", "A", "B", "C", "D", "E"), width=8, state="readonly").pack(side="left", padx=4)
        ttk.Label(filters, text="匹配状态").pack(side="left")
        ttk.Combobox(filters, textvariable=self.match_filter, values=("全部", "名称+地址", "仅地址", "仅名称", "未匹配", "歧义"), width=12, state="readonly").pack(side="left", padx=4)
        ttk.Label(filters, text="地址范围").pack(side="left", padx=(8, 2))
        ttk.Entry(filters, textvariable=self.min_address, width=12).pack(side="left")
        ttk.Label(filters, text="至").pack(side="left", padx=2)
        ttk.Entry(filters, textvariable=self.max_address, width=12).pack(side="left")
        ttk.Button(filters, text="应用筛选", command=self.search).pack(side="left", padx=6)
        ttk.Button(filters, text="清空筛选", command=self.clear_filters).pack(side="left")
        self.info = ttk.Label(self, text="请先选择 MAP 和 A2L")
        self.info.pack(anchor="w", padx=8)
        columns = ("name", "type", "a2l", "vma", "lma", "size", "status", "explanation", "diagnostics")
        self.table = ttk.Treeview(self, columns=columns, show="headings")
        headings = {"name": "变量", "type": "类型", "a2l": "A2L 地址", "vma": "MAP VMA", "lma": "MAP LMA", "size": "Size", "status": "等级", "explanation": "等级说明", "diagnostics": "诊断"}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=120 if column not in {"diagnostics", "explanation"} else 260)
        self.table.pack(fill="both", expand=True, padx=8, pady=8)

    def load_map(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("MAP files", "*.map"), ("All files", "*.*")])
        if path:
            self.map_index = parse_map(path)
            self.info.config(text=f"MAP: {Path(path).name}，符号 {len(self.map_index.symbols)}")
            self._rematch()

    def load_a2l(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("A2L files", "*.a2l"), ("All files", "*.*")])
        if path:
            self.a2l_index = parse_a2l(path)
            if not self.a2l_index.objects:
                messagebox.showwarning("A2L 无对象", "\n".join(self.a2l_index.diagnostics))
            self.info.config(text=f"A2L: {Path(path).name}，对象 {len(self.a2l_index.objects)}")
            self._rematch()

    def _rematch(self) -> None:
        if hasattr(self, "map_index") and hasattr(self, "a2l_index"):
            self.records = match_indexes(self.a2l_index, self.map_index)
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
            matched = []
            for record in self.records:
                candidate = record.name.lower()
                score = 1.0 if query in candidate else SequenceMatcher(None, query, candidate).ratio()
                if query in candidate or score >= 0.45:
                    matched.append((score, record))
            candidates = [record for _, record in sorted(matched, key=lambda item: (-item[0], item[1].name))]
        matched = [record for record in candidates if self.passes_filters(record)]
        for record in matched:
            fmt = lambda value: "" if value is None else f"0x{value:X}"
            self.table.insert("", "end", values=(record.name, record.object_type, fmt(record.a2l_address), fmt(record.map_vma), fmt(record.map_lma), record.size or "", record.status, record.grade_explanation, "; ".join(record.diagnostics)))
        self.info.config(text=f"当前显示 {len(matched)} / {len(self.records)} 条记录")

    def address_matches(self, query: str):
        try:
            address = int(query, 0) if query.startswith("0x") else int(query, 16)
        except ValueError:
            messagebox.showerror("地址格式错误", "请输入十六进制地址，例如 0xB0056364。")
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
        status = {"名称+地址": "A", "仅地址": "B", "仅名称": "C", "未匹配": "D", "歧义": "E"}.get(self.match_filter.get())
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
        self.search()

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
