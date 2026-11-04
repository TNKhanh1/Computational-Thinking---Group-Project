"""
SmartSchedule Verification Test Studio (MVP Native Desktop Window)
Author: Nguyen Nguyen Gia Bao (Builder 3 - System Architecture & Testing)
Course: CSC10014 - Computational Thinking (Group 03 - The Seven Dwarfs)

Organized into 5 sections:
  1. UI Tests (ui_tests/)
  2. Architecture Tests (architecture_tests/)
  3. Logical Tests (logical_tests/)
  4. Benchmark Tests (benchmark_tests/)
  5. Development Gap Tests (development_gap_tests/ - tracks Improve Plan milestones)
"""

import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

VERIFICATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = VERIFICATION_DIR.parent

SECTIONS = {
    "UI Tests": VERIFICATION_DIR / "ui_tests",
    "Architecture Tests": VERIFICATION_DIR / "architecture_tests",
    "Logical Tests": VERIFICATION_DIR / "logical_tests",
    "Benchmark Tests": VERIFICATION_DIR / "benchmark_tests",
    "Development Gaps (Improve Plan)": VERIFICATION_DIR / "development_gap_tests",
}

for folder in SECTIONS.values():
    folder.mkdir(parents=True, exist_ok=True)

TEMPLATES = {
    "UI Test": '''"""
UI Test: Endpoint & Frontend Contract Verification
"""
from fastapi.testclient import TestClient
from web.api import app

client = TestClient(app)

def test_custom_ui_behavior():
    res = client.get("/api/presets")
    assert res.status_code == 200
''',
    "Architecture Invariant": '''"""
Unit Test: System Architecture Boundary Verification
"""
import ast
from pathlib import Path
import pytest

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"

def test_custom_layer_boundary():
    solvers_dir = SRC_DIR / "solvers"
    for py_file in solvers_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("web"), f"Layer violation in {py_file.name}"
''',
    "Logical Validation": '''"""
Logical Test: Math, Boundaries & Determinism
"""
import pytest
from src.utils import minutes_to_slots, round_up_to_15

def test_custom_logic():
    assert round_up_to_15(25) == 30
    assert minutes_to_slots(30) == 2
''',
    "Development Gap Milestone": '''"""
Development Gap Test: Future Feature from Improve Plan
"""
import pytest

def test_future_improve_plan_milestone():
    # Will fail until the team implements this feature!
    assert False, "[GAP] Target milestone from improve_plan.md not yet implemented."
''',
}


class TestStudioApp:
    __test__ = False

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SmartSchedule — Verification Test Studio (Builder 3)")
        self.root.geometry("1150;720".replace(";", "x"))
        self.root.minsize(950, 620)
        self.current_file: Path | None = None

        self._apply_styles()
        self._build_ui()
        self.refresh_file_tree()

    def _apply_styles(self):
        self.bg_dark = "#1E1E24"
        self.bg_panel = "#282830"
        self.bg_editor = "#141418"
        self.fg_text = "#E4E4E7"
        self.accent_indigo = "#4F46E5"
        self.accent_green = "#16A34A"
        self.accent_red = "#DC2626"
        self.accent_amber = "#D97706"

        self.root.configure(bg=self.bg_dark)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=self.bg_dark)
        style.configure("Treeview", background=self.bg_editor, foreground=self.fg_text, fieldbackground=self.bg_editor, font=("Segoe UI", 9))
        style.map("Treeview", background=[("selected", self.accent_indigo)], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        # Top toolbar
        toolbar = tk.Frame(self.root, bg=self.bg_panel, height=52, padx=12, pady=8)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Label(toolbar, text="🧪 Verification Studio", font=("Segoe UI", 12, "bold"), fg="#FFFFFF", bg=self.bg_panel).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(toolbar, text="Builder 3 · System Architecture & Pre-deployment", font=("Segoe UI", 9), fg="#818CF8", bg=self.bg_panel).pack(side=tk.LEFT, padx=(0, 16))

        tk.Button(toolbar, text="➕ Add Test File", bg=self.accent_indigo, fg="#FFFFFF", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, command=self.on_add_file).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="💾 Save", bg="#3F3F46", fg="#FFFFFF", relief="flat", font=("Segoe UI", 9), padx=10, command=self.on_save_file).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="▶ Run Selected", bg=self.accent_green, fg="#FFFFFF", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, command=self.on_run_selected).pack(side=tk.LEFT, padx=8)
        tk.Button(toolbar, text="🚀 Run Production Tests", bg="#2563EB", fg="#FFFFFF", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, command=self.on_run_production_tests).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="🚩 Track Improve Plan Gaps", bg=self.accent_amber, fg="#FFFFFF", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, command=self.on_run_gaps).pack(side=tk.LEFT, padx=4)

        self.status_badge = tk.Label(toolbar, text="READY", font=("Segoe UI", 9, "bold"), bg="#3F3F46", fg="#FFFFFF", padx=10, pady=2)
        self.status_badge.pack(side=tk.RIGHT, padx=8)

        # Paned container
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left Explorer Tree
        left_frame = tk.Frame(main_paned, bg=self.bg_panel, width=320)
        main_paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="Test Hierarchy (verification_tests/)", font=("Segoe UI", 10, "bold"), fg=self.fg_text, bg=self.bg_panel, pady=6).pack(side=tk.TOP, fill=tk.X)

        self.tree = ttk.Treeview(left_frame, selectmode="browse")
        self.tree.heading("#0", text="Categories & Test Files", anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        left_actions = tk.Frame(left_frame, bg=self.bg_panel)
        left_actions.pack(fill=tk.X, padx=6, pady=6)
        tk.Button(left_actions, text="🗑️ Delete File", bg="#7F1D1D", fg="#FCA5A5", relief="flat", font=("Segoe UI", 8), command=self.on_delete_file).pack(side=tk.LEFT)
        tk.Button(left_actions, text="🔄 Refresh", bg="#3F3F46", fg="#E4E4E7", relief="flat", font=("Segoe UI", 8), command=self.refresh_file_tree).pack(side=tk.RIGHT)

        # Right Panel: Editor (Top) & Console (Bottom)
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=3)

        editor_frame = tk.Frame(right_paned, bg=self.bg_panel)
        right_paned.add(editor_frame, weight=3)

        self.editor_label = tk.Label(editor_frame, text="Select a test file from the explorer on the left", font=("Segoe UI", 9, "italic"), fg="#A1A1AA", bg=self.bg_panel, anchor="w", padx=8, pady=4)
        self.editor_label.pack(side=tk.TOP, fill=tk.X)

        self.editor_text = tk.Text(editor_frame, bg=self.bg_editor, fg=self.fg_text, insertbackground="#FFFFFF", font=("Consolas", 10), wrap="none", undo=True, padx=8, pady=8)
        scroll_y = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=self.editor_text.yview)
        scroll_x = ttk.Scrollbar(editor_frame, orient=tk.HORIZONTAL, command=self.editor_text.xview)
        self.editor_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.editor_text.pack(fill=tk.BOTH, expand=True)

        console_frame = tk.Frame(right_paned, bg=self.bg_panel)
        right_paned.add(console_frame, weight=2)

        tk.Label(console_frame, text="Diagnostic Output Console", font=("Segoe UI", 9, "bold"), fg=self.fg_text, bg=self.bg_panel, anchor="w", padx=8, pady=4).pack(side=tk.TOP, fill=tk.X)

        self.console_text = tk.Text(console_frame, bg="#0D0D11", fg="#A3E635", font=("Consolas", 9), wrap="word", state="disabled", padx=8, pady=6)
        c_scroll = ttk.Scrollbar(console_frame, orient=tk.VERTICAL, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=c_scroll.set)
        c_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.console_text.pack(fill=tk.BOTH, expand=True)

    def refresh_file_tree(self):
        self.tree.delete(*self.tree.get_children())
        first_file = None
        for sec_name, sec_path in SECTIONS.items():
            parent_id = self.tree.insert("", "end", text=sec_name, open=True)
            for f in sorted(sec_path.glob("test_*.py")):
                f_id = self.tree.insert(parent_id, "end", text=f.name, values=(str(f),))
                if not first_file:
                    first_file = (f_id, f)

        if first_file:
            self.tree.selection_set(first_file[0])
            self._load_file(first_file[1])

    def on_tree_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if vals:
            target_path = Path(vals[0])
            self._load_file(target_path)

    def _load_file(self, path: Path):
        self.current_file = path
        rel = path.relative_to(PROJECT_ROOT)
        self.editor_label.configure(text=f"Editing: {rel}", font=("Segoe UI", 9, "bold"), fg="#E0E7FF")
        self.editor_text.delete("1.0", tk.END)
        if path.exists():
            self.editor_text.insert("1.0", path.read_text(encoding="utf-8"))

    def on_save_file(self):
        if not self.current_file:
            messagebox.showwarning("No File", "No test file selected.")
            return
        content = self.editor_text.get("1.0", tk.END)
        try:
            self.current_file.write_text(content, encoding="utf-8")
            self._log_console(f"[SAVED] {self.current_file.name}\n")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    def on_add_file(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Verification Test")
        dialog.geometry("480x300")
        dialog.configure(bg=self.bg_panel)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Target Section:", bg=self.bg_panel, fg=self.fg_text, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
        sec_var = tk.StringVar(value=list(SECTIONS.keys())[0])
        ttk.Combobox(dialog, textvariable=sec_var, values=list(SECTIONS.keys()), state="readonly").pack(fill=tk.X, padx=16)

        tk.Label(dialog, text="File Name (e.g. test_new_feature.py):", bg=self.bg_panel, fg=self.fg_text, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 2))
        name_entry = tk.Entry(dialog, font=("Segoe UI", 10))
        name_entry.insert(0, "test_custom_check.py")
        name_entry.pack(fill=tk.X, padx=16)

        tk.Label(dialog, text="Boilerplate Template:", bg=self.bg_panel, fg=self.fg_text, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(10, 2))
        tpl_var = tk.StringVar(value=list(TEMPLATES.keys())[0])
        ttk.Combobox(dialog, textvariable=tpl_var, values=list(TEMPLATES.keys()), state="readonly").pack(fill=tk.X, padx=16)

        def do_create():
            fname = name_entry.get().strip()
            if not fname.endswith(".py"):
                fname += ".py"
            sec_folder = SECTIONS[sec_var.get()]
            target_path = sec_folder / fname
            if target_path.exists():
                messagebox.showerror("Error", f"File '{fname}' already exists!")
                return
            template_code = TEMPLATES.get(tpl_var.get(), "")
            target_path.write_text(template_code, encoding="utf-8")
            dialog.destroy()
            self.refresh_file_tree()
            self._load_file(target_path)
            self._log_console(f"[CREATED] {fname} in {sec_var.get()}\n")

        tk.Button(dialog, text="Create Test File", bg=self.accent_indigo, fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", command=do_create).pack(pady=16)

    def on_delete_file(self):
        if not self.current_file or not self.current_file.exists():
            return
        if messagebox.askyesno("Confirm Delete", f"Delete {self.current_file.name}?"):
            try:
                self.current_file.unlink()
                self._log_console(f"[DELETED] {self.current_file.name}\n")
                self.refresh_file_tree()
            except Exception as exc:
                messagebox.showerror("Delete Error", str(exc))

    def on_run_selected(self):
        if not self.current_file:
            messagebox.showwarning("No File", "Select a test file first.")
            return
        self.on_save_file()
        rel_path = self.current_file.relative_to(PROJECT_ROOT)
        cmd = [sys.executable, "-m", "pytest", str(rel_path), "-v", "--tb=short"]
        self._execute_test_cmd(cmd, f"Running: {self.current_file.name}")

    def on_run_production_tests(self):
        self.on_save_file()
        # Runs UI, Arch, Logic, Benchmarks (excludes intentional development failure gaps)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "verification_tests/ui_tests",
            "verification_tests/architecture_tests",
            "verification_tests/logical_tests",
            "verification_tests/benchmark_tests",
            "-v",
            "--tb=short",
        ]
        self._execute_test_cmd(cmd, "Running All Production Verification Tests (UI, Arch, Logic, Benchmarks)")

    def on_run_gaps(self):
        self.on_save_file()
        cmd = [sys.executable, "-m", "pytest", "verification_tests/development_gap_tests", "-v", "--tb=short"]
        self._execute_test_cmd(cmd, "Tracking Improve Plan Development Gaps (Expected Failures)")

    def _execute_test_cmd(self, cmd: list, title: str):
        self.status_badge.configure(text="RUNNING...", bg=self.accent_amber, fg="#FFFFFF")
        self._clear_console()
        self._log_console(f"=== {title} ===\n$ {' '.join(cmd)}\n\n")

        def run_thread():
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                output, _ = proc.communicate()
                self.root.after(0, lambda: self._on_test_finished(proc.returncode, output))
            except Exception as exc:
                self.root.after(0, lambda: self._on_test_finished(1, f"Execution failed: {exc}"))

        threading.Thread(target=run_thread, daemon=True).start()

    def _on_test_finished(self, exit_code: int, output: str):
        self._log_console(output)
        if exit_code == 0:
            self.status_badge.configure(text="ALL PASSED ✓", bg=self.accent_green, fg="#FFFFFF")
            self._log_console("\n[SUCCESS] Verification passed cleanly!\n")
        else:
            self.status_badge.configure(text="FAILURES / GAPS ✗", bg=self.accent_red, fg="#FFFFFF")
            self._log_console(f"\n[DIAGNOSTIC] Pytest reported exit code {exit_code}.\n")

    def _clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", tk.END)
        self.console_text.configure(state="disabled")

    def _log_console(self, text: str):
        self.console_text.configure(state="normal")
        self.console_text.insert(tk.END, text)
        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")


def main():
    root = tk.Tk()
    app = TestStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

