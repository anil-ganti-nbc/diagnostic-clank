"""Minimal Agent Output Inbox GUI — four paste boxes, registry-backed Clank list."""
from __future__ import annotations
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from clank_runtime.knowledge.inbox import AgentFamily, AgentOutputInbox, OutputType
from clank_runtime.registry.core import DEFAULT_REGISTRY

def run_inbox_gui(db_path: Path | str = "data/motherclank_knowledge.db") -> None:
    inbox = AgentOutputInbox(db_path, DEFAULT_REGISTRY)
    root = tk.Tk()
    root.title("Motherclank — Agent Inbox")
    root.geometry("960x640")
    top = ttk.Frame(root, padding=8); top.pack(fill=tk.X)
    ttk.Label(top, text="Target Clank:").pack(side=tk.LEFT)
    clank_var = tk.StringVar()
    clank_ids = DEFAULT_REGISTRY.list_ids() + ["fleet-wide"]
    clank_box = ttk.Combobox(top, textvariable=clank_var, values=clank_ids, width=28)
    clank_box.pack(side=tk.LEFT, padx=4)
    if clank_ids: clank_var.set(clank_ids[0])
    ttk.Label(top, text="Output type:").pack(side=tk.LEFT, padx=(12, 0))
    type_var = tk.StringVar(value=OutputType.GENERAL_NOTE.value)
    ttk.Combobox(top, textvariable=type_var, values=[t.value for t in OutputType], width=20).pack(side=tk.LEFT, padx=4)
    grid = ttk.Frame(root, padding=8); grid.pack(fill=tk.BOTH, expand=True)
    texts: dict[AgentFamily, tk.Text] = {}
    for family, r, c in [(AgentFamily.CLAUDE,0,0),(AgentFamily.CODEX,0,1),(AgentFamily.GROK,1,0),(AgentFamily.MISC,1,1)]:
        frame = ttk.LabelFrame(grid, text=family.value.upper(), padding=4)
        frame.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
        t = tk.Text(frame, wrap=tk.WORD, height=12, width=50); t.pack(fill=tk.BOTH, expand=True)
        texts[family] = t
    for i in (0,1):
        grid.rowconfigure(i, weight=1); grid.columnconfigure(i, weight=1)
    def save_all() -> None:
        cid = clank_var.get().strip()
        if not cid:
            messagebox.showerror("Error", "Target Clank is required"); return
        saved = 0
        try:
            for family, widget in texts.items():
                body = widget.get("1.0", tk.END)
                if not body.strip(): continue
                inbox.save(agent_family=family, primary_clank_id=cid, raw_text=body,
                           output_type=OutputType(type_var.get())); saved += 1
        except KeyError as e:
            messagebox.showerror("Unknown Clank", str(e)); return
        messagebox.showinfo("Saved", f"Created {saved} independent record(s)")
    def clear_all() -> None:
        for w in texts.values(): w.delete("1.0", tk.END)
    bot = ttk.Frame(root, padding=8); bot.pack(fill=tk.X)
    ttk.Button(bot, text="Save all non-empty", command=save_all).pack(side=tk.LEFT)
    ttk.Button(bot, text="Clear", command=clear_all).pack(side=tk.LEFT, padx=8)
    root.mainloop(); inbox.close()

if __name__ == "__main__":
    run_inbox_gui()
