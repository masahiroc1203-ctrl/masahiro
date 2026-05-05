#!/usr/bin/env python3
"""Desktop load monitor - tkinter GUI (dark theme, matches browser version)."""

import tkinter as tk
from tkinter import ttk
import threading
import time
import psutil

# ── Colors ─────────────────────────────────────────────────────
BG      = "#0f1117"
CARD    = "#1a1d27"
BORDER  = "#2a2d3e"
ROW_ALT = "#1f2235"
TEXT    = "#e2e8f0"
MUTED   = "#8892a4"
GREEN   = "#22c55e"
YELLOW  = "#eab308"
RED     = "#ef4444"
BLUE    = "#3b82f6"
PURPLE  = "#a855f7"
CYAN    = "#06b6d4"

def color_for_pct(p):
    if p > 85: return RED
    if p > 60: return YELLOW
    return GREEN

# ── Rolling history (60 samples, updated every 1s) ─────────────
_lock      = threading.Lock()
_history   = {"cpu": [], "mem": [], "net_sent": [], "net_recv": []}
_MAX_H     = 60
_prev_net  = psutil.net_io_counters()
_prev_time = time.time()

def _history_thread():
    global _prev_net, _prev_time
    while True:
        now     = time.time()
        net     = psutil.net_io_counters()
        elapsed = (now - _prev_time) or 1
        sent_kb = (net.bytes_sent - _prev_net.bytes_sent) / elapsed / 1024
        recv_kb = (net.bytes_recv - _prev_net.bytes_recv) / elapsed / 1024
        _prev_net  = net
        _prev_time = now
        with _lock:
            _history["cpu"].append(psutil.cpu_percent())
            _history["mem"].append(psutil.virtual_memory().percent)
            _history["net_sent"].append(round(sent_kb, 2))
            _history["net_recv"].append(round(recv_kb, 2))
            for k in _history:
                if len(_history[k]) > _MAX_H:
                    _history[k].pop(0)
        time.sleep(1)

def get_history():
    with _lock:
        return {k: list(v) for k, v in _history.items()}

# ── Circular gauge (Canvas) ─────────────────────────────────────
class GaugeCanvas(tk.Canvas):
    SIZE = 90
    THICK = 9

    def __init__(self, parent, color=BLUE, **kw):
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         bg=CARD, highlightthickness=0, **kw)
        self._color = color
        self._pct   = 0
        self._draw()

    def _draw(self):
        self.delete("all")
        s, t = self.SIZE, self.THICK
        pad  = t // 2 + 3
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        # Track ring
        self.create_arc(x0, y0, x1, y1, start=0, extent=359.9,
                        style=tk.ARC, outline=BORDER, width=t)
        # Filled arc
        if self._pct > 0:
            col = color_for_pct(self._pct)
            self.create_arc(x0, y0, x1, y1,
                            start=90, extent=-(self._pct * 3.6),
                            style=tk.ARC, outline=col, width=t)
        # Center label
        cx, cy = s // 2, s // 2
        self.create_text(cx, cy, text=f"{self._pct}%",
                         fill=TEXT, font=("Segoe UI", 11, "bold"))

    def set_pct(self, pct):
        self._pct = int(pct)
        self._draw()

# ── Sparkline (Canvas) ──────────────────────────────────────────
class SparkCanvas(tk.Canvas):
    H = 52

    def __init__(self, parent, color=BLUE, **kw):
        super().__init__(parent, height=self.H, bg=CARD,
                         highlightthickness=0, **kw)
        self._color = color
        self._data  = []
        self.bind("<Configure>", lambda _: self._draw())

    def update_data(self, data):
        self._data = list(data)
        self._draw()

    def _draw(self):
        self.delete("all")
        data = self._data
        if len(data) < 2:
            return
        w = self.winfo_width()
        h = self.H
        if w <= 1:
            return
        mx   = max(max(data), 1)
        step = w / (len(data) - 1)
        pts  = []
        for i, v in enumerate(data):
            pts.extend([i * step, h - (v / mx) * h * 0.82 - 2])
        self.create_line(pts, fill=self._color, width=1.5, smooth=True)

# ── Horizontal bar (Canvas) ─────────────────────────────────────
class BarCanvas(tk.Canvas):
    def __init__(self, parent, height=8, **kw):
        super().__init__(parent, height=height, bg=BORDER,
                         highlightthickness=0, **kw)
        self._pct   = 0
        self._color = GREEN
        self.bind("<Configure>", lambda _: self._draw())

    def set_value(self, pct, color):
        self._pct   = pct
        self._color = color
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        fill_w = max(1, int(w * self._pct / 100))
        self.create_rectangle(0, 0, fill_w, h, fill=self._color, outline="")

# ── Card frame helper ───────────────────────────────────────────
def make_card(parent, title):
    f = tk.Frame(parent, bg=CARD, highlightthickness=1,
                 highlightbackground=BORDER)
    tk.Label(f, text=title.upper(), bg=CARD, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(8, 2))
    return f

# ── Main Application ────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("デスクトップ負荷モニター")
        self.configure(bg=BG)
        self.geometry("1100x780")
        self.minsize(800, 600)

        self._build_header()
        self._build_scrollable_main()
        self._schedule_update()

    # ── Header ─────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=CARD, height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._dot = tk.Label(hdr, text="●", fg=GREEN, bg=CARD,
                             font=("Segoe UI", 10))
        self._dot.pack(side="left", padx=(12, 4), pady=10)
        tk.Label(hdr, text="デスクトップ負荷モニター", fg=TEXT, bg=CARD,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self._ts = tk.Label(hdr, text="--", fg=MUTED, bg=CARD,
                            font=("Segoe UI", 9))
        self._ts.pack(side="right", padx=16)

    # ── Scrollable main area ────────────────────────────────────
    def _build_scrollable_main(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        vbar = tk.Scrollbar(outer, orient="vertical", bg=CARD,
                            troughcolor=BG, activebackground=BORDER)
        vbar.pack(side="right", fill="y")

        cv = tk.Canvas(outer, bg=BG, yscrollcommand=vbar.set,
                       highlightthickness=0)
        cv.pack(side="left", fill="both", expand=True)
        vbar.config(command=cv.yview)

        self._inner = tk.Frame(cv, bg=BG)
        win_id = cv.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",
                         lambda _: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>",
                lambda e: cv.itemconfig(win_id, width=e.width))
        cv.bind_all("<MouseWheel>",
                    lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))

        P = 12  # padding

        # ── Row 1: 4 summary cards ──────────────────────────────
        r1 = tk.Frame(self._inner, bg=BG)
        r1.pack(fill="x", padx=P, pady=(P, 0))
        for i in range(4):
            r1.columnconfigure(i, weight=1, uniform="r1")

        # CPU
        c = make_card(r1, "CPU")
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", padx=10, pady=4)
        self._g_cpu = GaugeCanvas(body)
        self._g_cpu.pack(side="left")
        info = tk.Frame(body, bg=CARD)
        info.pack(side="left", padx=10, fill="x", expand=True)
        self._cpu_freq  = tk.Label(info, text="--", fg=TEXT, bg=CARD,
                                   font=("Segoe UI", 14, "bold"))
        self._cpu_freq.pack(anchor="w")
        self._cpu_info  = tk.Label(info, text="--", fg=MUTED, bg=CARD,
                                   font=("Segoe UI", 8), justify="left")
        self._cpu_info.pack(anchor="w")
        self._sp_cpu = SparkCanvas(c, color=BLUE)
        self._sp_cpu.pack(fill="x", padx=8, pady=(2, 8))

        # Memory
        c = make_card(r1, "メモリ")
        c.grid(row=0, column=1, sticky="nsew", padx=3)
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", padx=10, pady=4)
        self._g_mem = GaugeCanvas(body, color=PURPLE)
        self._g_mem.pack(side="left")
        info = tk.Frame(body, bg=CARD)
        info.pack(side="left", padx=10, fill="x", expand=True)
        self._mem_used   = tk.Label(info, text="--", fg=TEXT, bg=CARD,
                                    font=("Segoe UI", 14, "bold"))
        self._mem_used.pack(anchor="w")
        self._mem_detail = tk.Label(info, text="--", fg=MUTED, bg=CARD,
                                    font=("Segoe UI", 8), justify="left")
        self._mem_detail.pack(anchor="w")
        self._sp_mem = SparkCanvas(c, color=PURPLE)
        self._sp_mem.pack(fill="x", padx=8, pady=(2, 8))

        # Net sent
        c = make_card(r1, "ネットワーク送信")
        c.grid(row=0, column=2, sticky="nsew", padx=3)
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", padx=12, pady=6)
        tk.Label(body, text="転送速度", fg=MUTED, bg=CARD,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._net_sent = tk.Label(body, text="-- KB/s", fg=TEXT, bg=CARD,
                                  font=("Segoe UI", 14, "bold"))
        self._net_sent.pack(anchor="w")
        self._sp_sent = SparkCanvas(c, color=CYAN)
        self._sp_sent.pack(fill="x", padx=8, pady=(2, 8))

        # Net recv
        c = make_card(r1, "ネットワーク受信")
        c.grid(row=0, column=3, sticky="nsew", padx=(3, 0))
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", padx=12, pady=6)
        tk.Label(body, text="転送速度", fg=MUTED, bg=CARD,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._net_recv = tk.Label(body, text="-- KB/s", fg=TEXT, bg=CARD,
                                  font=("Segoe UI", 14, "bold"))
        self._net_recv.pack(anchor="w")
        self._sp_recv = SparkCanvas(c, color=GREEN)
        self._sp_recv.pack(fill="x", padx=8, pady=(2, 8))

        # ── Row 2: per-core + disk ──────────────────────────────
        r2 = tk.Frame(self._inner, bg=BG)
        r2.pack(fill="x", padx=P, pady=(10, 0))
        r2.columnconfigure(0, weight=1)
        r2.columnconfigure(1, weight=1)

        core_card = make_card(r2, "CPUコア別使用率")
        core_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._core_frame = tk.Frame(core_card, bg=CARD)
        self._core_frame.pack(fill="x", padx=10, pady=(0, 10))

        disk_card = make_card(r2, "ディスク")
        disk_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._disk_frame = tk.Frame(disk_card, bg=CARD)
        self._disk_frame.pack(fill="x", padx=12, pady=(0, 10))

        # ── Row 3: process table ────────────────────────────────
        proc_card = make_card(self._inner, "プロセス (CPU使用率順 TOP 20)")
        proc_card.pack(fill="both", expand=True, padx=P, pady=(10, P))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("M.Treeview",
                        background=CARD, foreground=TEXT,
                        fieldbackground=CARD, rowheight=22,
                        font=("Segoe UI", 9), borderwidth=0)
        style.configure("M.Treeview.Heading",
                        background=BORDER, foreground=MUTED,
                        font=("Segoe UI", 8, "bold"), relief="flat")
        style.map("M.Treeview",
                  background=[("selected", ROW_ALT)],
                  foreground=[("selected", TEXT)])

        cols = ("pid", "name", "cpu", "mem", "status")
        self._tree = ttk.Treeview(proc_card, columns=cols, show="headings",
                                  style="M.Treeview", height=14)
        for col, lbl, w, anchor in [
            ("pid",    "PID",        55,  "e"),
            ("name",   "プロセス名", 220, "w"),
            ("cpu",    "CPU %",       70, "e"),
            ("mem",    "メモリ %",    70, "e"),
            ("status", "状態",        80, "w"),
        ]:
            self._tree.heading(col, text=lbl)
            self._tree.column(col, width=w, anchor=anchor, stretch=(col == "name"))

        sb = ttk.Scrollbar(proc_card, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 4))
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ── Periodic update ─────────────────────────────────────────
    def _schedule_update(self):
        self._do_update()
        self.after(2000, self._schedule_update)

    def _do_update(self):
        self._ts.config(text=time.strftime("%Y-%m-%d %H:%M:%S"))

        cpu_pct = psutil.cpu_percent(percpu=False)
        cores   = psutil.cpu_percent(percpu=True)
        freq    = psutil.cpu_freq()
        mem     = psutil.virtual_memory()
        swap    = psutil.swap_memory()
        hist    = get_history()

        # CPU
        self._g_cpu.set_pct(int(cpu_pct))
        self._cpu_freq.config(
            text=f"{round(freq.current)} MHz" if freq else "--")
        self._cpu_info.config(
            text=f"物理: {psutil.cpu_count(False)}コア\n"
                 f"論理: {psutil.cpu_count(True)}スレッド")

        # Memory
        self._g_mem.set_pct(int(mem.percent))
        self._mem_used.config(text=f"{round(mem.used/1e9, 1)} GB")
        self._mem_detail.config(
            text=f"合計: {round(mem.total/1e9, 1)} GB\n"
                 f"空き: {round(mem.available/1e9, 1)} GB\n"
                 f"Swap: {round(swap.used/1e9,1)}/{round(swap.total/1e9,1)} GB")

        # Network
        def fmt(kb):
            if kb >= 1024 * 1024: return f"{kb/1024/1024:.1f} GB/s"
            if kb >= 1024:        return f"{kb/1024:.1f} MB/s"
            return f"{kb:.0f} KB/s"

        self._net_sent.config(text=fmt(hist["net_sent"][-1] if hist["net_sent"] else 0))
        self._net_recv.config(text=fmt(hist["net_recv"][-1] if hist["net_recv"] else 0))

        # Sparklines
        self._sp_cpu.update_data(hist["cpu"])
        self._sp_mem.update_data(hist["mem"])
        self._sp_sent.update_data(hist["net_sent"])
        self._sp_recv.update_data(hist["net_recv"])

        # Per-core grid
        for w in self._core_frame.winfo_children():
            w.destroy()
        cols_n = min(len(cores), 8)
        for i in range(cols_n):
            self._core_frame.columnconfigure(i, weight=1)
        for i, pct in enumerate(cores):
            col = color_for_pct(pct)
            row_i, col_i = divmod(i, cols_n)
            f = tk.Frame(self._core_frame, bg=BG, padx=4, pady=4)
            f.grid(row=row_i, column=col_i, sticky="ew", padx=3, pady=3)
            tk.Label(f, text=f"Core {i}", fg=MUTED, bg=BG,
                     font=("Segoe UI", 7)).pack()
            tk.Label(f, text=f"{pct}%", fg=col, bg=BG,
                     font=("Segoe UI", 10, "bold")).pack()
            bar = BarCanvas(f, height=4)
            bar.pack(fill="x", pady=(2, 0))
            bar.update_idletasks()
            bar.set_value(pct, col)

        # Disk
        for w in self._disk_frame.winfo_children():
            w.destroy()
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue
            pct = usage.percent
            col = color_for_pct(pct)
            used_gb  = round(usage.used  / 1e9, 1)
            total_gb = round(usage.total / 1e9, 1)

            row = tk.Frame(self._disk_frame, bg=CARD)
            row.pack(fill="x", pady=5)
            hdr = tk.Frame(row, bg=CARD)
            hdr.pack(fill="x")
            tk.Label(hdr, text=part.mountpoint, fg=TEXT, bg=CARD,
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(hdr, text=f"{used_gb}/{total_gb} GB ({pct}%)",
                     fg=MUTED, bg=CARD, font=("Segoe UI", 8)).pack(side="right")
            bar = BarCanvas(row, height=8)
            bar.pack(fill="x", pady=(3, 0))
            bar.update_idletasks()
            bar.set_value(pct, col)

        # Process table
        for item in self._tree.get_children():
            self._tree.delete(item)
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                       "memory_percent", "status"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)
        for p in procs[:20]:
            self._tree.insert("", "end", values=(
                p["pid"],
                p["name"],
                f"{p.get('cpu_percent', 0):.1f}%",
                f"{p.get('memory_percent', 0):.1f}%",
                p.get("status", ""),
            ))


if __name__ == "__main__":
    psutil.cpu_percent(percpu=True)  # warm-up (first call returns 0)
    threading.Thread(target=_history_thread, daemon=True).start()
    App().mainloop()
