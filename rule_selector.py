import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from rule_engine import get_rules_by_id, load_config, process_excel


GROUP_ORDER = ["data", "country", "email", "affiliation", "name"]


class RuleSelectorApp:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.rules_by_id = get_rules_by_id(self.config)
        self.group_labels = self.config.get("group_labels", {})
        self.presets = self.config.get("presets", {})
        self.result = None

        self.root = tk.Tk()
        self.root.title("Excel 清洗 - 规则选择")
        self.root.geometry("720x620")
        self.root.attributes("-topmost", True)

        self.preset_var = tk.StringVar()
        self.checkbox_vars = {}
        self.preset_id_by_label = {}
        self.preset_label_by_id = {}

        self._build_ui()
        default_preset = "full_legacy" if "full_legacy" in self.presets else next(iter(self.presets), "")
        if default_preset and default_preset in self.preset_label_by_id:
            self.preset_var.set(self.preset_label_by_id[default_preset])
        self.apply_preset()

    def _build_ui(self):
        preset_frame = ttk.LabelFrame(self.root, text="预设方案", padding=10)
        preset_frame.pack(fill="x", padx=12, pady=(12, 6))

        preset_names = [(pid, info["label"]) for pid, info in self.presets.items() if pid != "custom"]
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            state="readonly",
            values=[label for _, label in preset_names],
            width=50,
        )
        self.preset_combo.pack(side="left", fill="x", expand=True)
        self.preset_id_by_label = {label: pid for pid, label in preset_names}
        self.preset_label_by_id = {pid: label for pid, label in preset_names}

        ttk.Button(preset_frame, text="应用预设", command=self.apply_preset).pack(side="left", padx=(8, 0))

        rule_frame = ttk.LabelFrame(self.root, text="清洗规则（可多选）", padding=10)
        rule_frame.pack(fill="both", expand=True, padx=12, pady=6)

        canvas = tk.Canvas(rule_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(rule_frame, orient="vertical", command=canvas.yview)
        self.scrollable = ttk.Frame(canvas)
        self.scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        rules_by_group = {group: [] for group in GROUP_ORDER}
        for rule in sorted(self.config.get("rules", []), key=lambda r: r.get("order", 0)):
            group = rule.get("group", "other")
            rules_by_group.setdefault(group, []).append(rule)

        for group in GROUP_ORDER + [g for g in rules_by_group if g not in GROUP_ORDER]:
            group_rules = rules_by_group.get(group, [])
            if not group_rules:
                continue

            group_label = self.group_labels.get(group, group)
            ttk.Label(self.scrollable, text=group_label, font=("", 10, "bold")).pack(
                anchor="w", pady=(8, 4)
            )

            for rule in group_rules:
                var = tk.BooleanVar(value=rule.get("default_enabled", False))
                self.checkbox_vars[rule["id"]] = var
                level = rule.get("level", 0)
                text = f"L{level}  {rule['name']}  —  {rule['note']}"
                ttk.Checkbutton(self.scrollable, text=text, variable=var).pack(anchor="w", padx=8)

        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="全选", command=self.select_all).pack(side="left")
        ttk.Button(btn_frame, text="全不选", command=self.select_none).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="开始清洗", command=self.start).pack(side="right")
        ttk.Button(btn_frame, text="取消", command=self.cancel).pack(side="right", padx=8)

    def apply_preset(self):
        label = self.preset_var.get()
        preset_id = self.preset_id_by_label.get(label)
        if not preset_id:
            return

        preset_rules = set(self.presets[preset_id].get("rules", []))
        for rule_id, var in self.checkbox_vars.items():
            var.set(rule_id in preset_rules)

    def select_all(self):
        for var in self.checkbox_vars.values():
            var.set(True)

    def select_none(self):
        for var in self.checkbox_vars.values():
            var.set(False)

    def get_selected_rule_ids(self):
        selected = [rule_id for rule_id, var in self.checkbox_vars.items() if var.get()]
        return sorted(
            selected,
            key=lambda rid: self.rules_by_id.get(rid, {}).get("order", 999),
        )

    def start(self):
        enabled_rule_ids = self.get_selected_rule_ids()
        if not enabled_rule_ids:
            messagebox.showwarning("提示", "请至少选择一条清洗规则")
            return

        file_path = filedialog.askopenfilename(
            title="请选择需要清洗的 Excel 文件",
            filetypes=[("Excel files", "*.xlsx *.xls")],
        )
        if not file_path:
            return

        try:
            result = process_excel(file_path, self.config_path, enabled_rule_ids)
        except Exception as exc:
            messagebox.showerror("错误", str(exc))
            return

        self.result = result
        print(f"运行完毕，总耗时: {result['elapsed']:.2f} 秒")
        print(f"原始总行数: {result['total_rows']}")
        print(f"删除行数: {result['deleted_rows']}")
        print(f"保留行数: {result['kept_rows']}")
        print(
            f"清洗后文件已保存至：\n"
            f"  {result['format_path']}\n"
            f"  {result['deleted_path']}\n"
            f"  {result['run_config_path']}"
        )
        messagebox.showinfo(
            "完成",
            (
                f"原始总行数: {result['total_rows']}\n"
                f"删除行数: {result['deleted_rows']}\n"
                f"保留行数: {result['kept_rows']}\n"
                f"耗时: {result['elapsed']:.2f} 秒\n\n"
                f"清洗后: {result['format_path']}\n"
                f"删除明细: {result['deleted_path']}\n"
                f"运行配置: {result['run_config_path']}"
            ),
        )
        self.root.destroy()

    def cancel(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


def select_rules_and_process(config_path):
    app = RuleSelectorApp(config_path)
    return app.run()
