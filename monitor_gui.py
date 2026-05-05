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

# ── Shared data store (written by BG threads, read by UI thread) ─
_lock    = threading.Lock()
_data    = {}
_history = {"cpu": [], "mem": [], "net_sent": [], "net_recv": []}
_MAX_H   = 60

def get_snapshot():
    with _lock:
        return dict(_data), {k: list(v) for k, v in _history.items()}

# ── Fast collector: CPU / memory / network  (every 1 s) ─────────
def _fast_collector():
    prev_net  = psutil.net_io_counters()
    prev_time = time.time()
    psutil.cpu_percent(percpu=True)   # discard first (always 0)

    while True:
        time.sleep(1)

        now     = time.time()
        net     = psutil.net_io_counters()
        elapsed = (now - prev_time) or 1
        sent_kb = (net.bytes_sent - prev_net.bytes_sent) / elapsed / 1024
        recv_kb = (net.bytes_recv - prev_net.bytes_recv) / elapsed / 1024
        prev_net  = net
        prev_time = now

        cpu_pct = psutil.cpu_percent(percpu=False)
        cores   = psutil.cpu_percent(percpu=True)
        freq    = psutil.cpu_freq()
        mem     = psutil.virtual_memory()
        swap    = psutil.swap_memory()

        snap = {
            "ts":         time.strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_pct":    cpu_pct,
            "cores":      cores,
            "freq":       round(freq.current) if freq else None,
            "n_phys":     psutil.cpu_count(logical=False),
            "n_logic":    psutil.cpu_count(logical=True),
            "mem_pct":    mem.percent,
            "mem_used":   round(mem.used        / 1e9, 1),
            "mem_total":  round(mem.total       / 1e9, 1),
            "mem_avail":  round(mem.available   / 1e9, 1),
            "swap_used":  round(swap.used       / 1e9, 1),
            "swap_total": round(swap.total      / 1e9, 1),
            "net_sent":   round(sent_kb, 2),
            "net_recv":   round(recv_kb, 2),
        }

        with _lock:
            _data.update(snap)
            for key in ("cpu", "mem", "net_sent", "net_recv"):
                src = "cpu_pct" if key == "cpu" else \
                      "mem_pct" if key == "mem" else key
                _history[key].append(snap[src])
                if len(_history[key]) > _MAX_H:
                    _history[key].pop(0)

# ── Slow collector: processes / disk  (every 5 s) ───────────────
def _slow_collector():
    while True:
        # Processes
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent",
                                       "memory_percent", "status"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)

        # Disks
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "mountpoint": part.mountpoint,
                    "used_gb":    round(usage.used  / 1e9, 1),
                    "total_gb":   round(usage.total / 1e9, 1),
                    "percent":    usage.percent,
                })
            except PermissionError:
                pass

        with _lock:
            _data["procs"] = procs[:20]
            _data["disks"] = disks

        time.sleep(5)

# ── Circular gauge (Canvas) ─────────────────────────────────────
class GaugeCanvas(tk.Canvas):
    SIZE  = 90
    THICK = 9

    def __init__(self, parent, color=BLUE, **kw):
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         bg=CARD, highlightthickness=0, **kw)
        self._color = color
        self._pct   = 0
        self._arc   = None
        self._label = None
        self._init_items()

    def _init_items(self):
        s, t = self.SIZE, self.THICK
        pad  = t // 2 + 3
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        self.create_arc(x0, y0, x1, y1, start=0, extent=359.9,
                        style=tk.ARC, outline=BORDER, width=t)
        self._arc   = self.create_arc(x0, y0, x1, y1,
                                       start=90, extent=-1,
                                       style=tk.ARC, outline=self._color, width=t)
        self._label = self.create_text(s // 2, s // 2, text="0%",
                                        fill=TEXT, font=("Segoe UI", 11, "bold"))

    def set_pct(self, pct):
        if pct == self._pct:
            return
        self._pct = int(pct)
        col = color_for_pct(self._pct)
        extent = -(self._pct * 3.6) if self._pct > 0 else -0.01
        self.itemconfig(self._arc, extent=extent, outline=col)
        self.itemconfig(self._label, text=f"{self._pct}%")

# ── Sparkline (Canvas) ──────────────────────────────────────────
class SparkCanvas(tk.Canvas):
    H = 52

    def __init__(self, parent, color=BLUE, **kw):
        super().__init__(parent, height=self.H, bg=CARD,
                         highlightthickness=0, **kw)
        self._color = color
        self._data  = []
        self._line  = None
        self.bind("<Configure>", lambda _: self._draw())

    def update_data(self, data):
        self._data = list(data)
        self._draw()

    def _draw(self):
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
        if self._line is None:
            self._line = self.create_line(pts, fill=self._color,
                                          width=1.5, smooth=True)
        else:
            self.coords(self._line, pts)

# ── Horizontal bar (Canvas) ─────────────────────────────────────
class BarCanvas(tk.Canvas):
    def __init__(self, parent, height=8, **kw):
        super().__init__(parent, height=height, bg=BORDER,
                         highlightthickness=0, **kw)
        self._pct   = 0
        self._color = GREEN
        self._rect  = None
        self.bind("<Configure>", lambda _: self._draw())

    def set_value(self, pct, color):
        changed = (pct != self._pct or color != self._color)
        self._pct   = pct
        self._color = color
        if changed:
            self._draw()

    def _draw(self):
        w = self.winfo_width()
        h = self.winfo_height()
        fill_w = max(1, int(w * self._pct / 100))
        if self._rect is None:
            self._rect = self.create_rectangle(0, 0, fill_w, h,
                                                fill=self._color, outline="")
        else:
            self.coords(self._rect, 0, 0, fill_w, h)
            self.itemconfig(self._rect, fill=self._color)

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

        self._core_widgets = []   # (label_pct, bar) per core
        self._disk_widgets = {}   # mountpoint -> (label, bar)

        self._build_header()
        self._build_scrollable_main()
        self.after(1000, self._schedule_update)

    # ── Header ─────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=CARD, height=42)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="●", fg=GREEN, bg=CARD,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 4), pady=10)
        tk.Label(hdr, text="デスクトップ負荷モニター", fg=TEXT, bg=CARD,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        self._ts = tk.Label(hdr, text="--", fg=MUTED, bg=CARD,
                            font=("Segoe UI", 9))
        self._ts.pack(side="right", padx=16)

    # ── Scrollable main area ────────────────────────────────────
    def _build_scrollable_main(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        vbar = tk.Scrollbar(outer, orient="vertical",
                            bg=CARD, troughcolor=BG, activebackground=BORDER)
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

        P = 12

        # ── Row 1: 4 summary cards ──────────────────────────────
        r1 = tk.Frame(self._inner, bg=BG)
        r1.pack(fill="x", padx=P, pady=(P, 0))
        for i in range(4):
            r1.columnconfigure(i, weight=1, uniform="r1")

        # CPU card
        c = make_card(r1, "CPU")
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        body = tk.Frame(c, bg=CARD)
        body.pack(fill="x", padx=10, pady=4)
        self._g_cpu = GaugeCanvas(body)
        self._g_cpu.pack(side="left")
        info = tk.Frame(body, bg=CARD)
        info.pack(side="left", padx=10, fill="x", expand=True)
        self._cpu_freq = tk.Label(info, text="--", fg=TEXT, bg=CARD,
                                  font=("Segoe UI", 14, "bold"))
        self._cpu_freq.pack(anchor="w")
        self._cpu_info = tk.Label(info, text="--", fg=MUTED, bg=CARD,
                                  font=("Segoe UI", 8), justify="left")
        self._cpu_info.pack(anchor="w")
        self._sp_cpu = SparkCanvas(c, color=BLUE)
        self._sp_cpu.pack(fill="x", padx=8, pady=(2, 8))

        # Memory card
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

        # Net sent card
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

        # Net recv card
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
            self._tree.column(col, width=w, anchor=anchor,
                              stretch=(col == "name"))

        sb = ttk.Scrollbar(proc_card, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 4))
        self._tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Pre-fill 20 empty rows so the table doesn't jump on first update
        for _ in range(20):
            self._tree.insert("", "end", values=("", "", "", "", ""))
        self._tree_ids = self._tree.get_children()

    # ── Periodic UI update (main thread only) ───────────────────
    def _schedule_update(self):
        snap, hist = get_snapshot()
        if snap:
            self._apply(snap, hist)
        self.after(1000, self._schedule_update)

    def _apply(self, s, hist):
        self._ts.config(text=s["ts"])

        # CPU gauge + labels
        self._g_cpu.set_pct(int(s["cpu_pct"]))
        self._cpu_freq.config(
            text=f"{s['freq']} MHz" if s["freq"] else "--")
        self._cpu_info.config(
            text=f"物理: {s['n_phys']}コア\n論理: {s['n_logic']}スレッド")

        # Memory gauge + labels
        self._g_mem.set_pct(int(s["mem_pct"]))
        self._mem_used.config(text=f"{s['mem_used']} GB")
        self._mem_detail.config(
            text=f"合計: {s['mem_total']} GB\n"
                 f"空き: {s['mem_avail']} GB\n"
                 f"Swap: {s['swap_used']}/{s['swap_total']} GB")

        # Network labels
        def fmt(kb):
            if kb >= 1024 * 1024: return f"{kb/1024/1024:.1f} GB/s"
            if kb >= 1024:        return f"{kb/1024:.1f} MB/s"
            return f"{kb:.0f} KB/s"

        self._net_sent.config(text=fmt(s["net_sent"]))
        self._net_recv.config(text=fmt(s["net_recv"]))

        # Sparklines
        self._sp_cpu.update_data(hist["cpu"])
        self._sp_mem.update_data(hist["mem"])
        self._sp_sent.update_data(hist["net_sent"])
        self._sp_recv.update_data(hist["net_recv"])

        # Per-core: build widgets once, then update values only
        cores = s["cores"]
        if len(self._core_widgets) != len(cores):
            for w in self._core_frame.winfo_children():
                w.destroy()
            self._core_widgets = []
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
                lbl = tk.Label(f, text=f"{pct}%", fg=col, bg=BG,
                               font=("Segoe UI", 10, "bold"))
                lbl.pack()
                bar = BarCanvas(f, height=4)
                bar.pack(fill="x", pady=(2, 0))
                bar.update_idletasks()
                bar.set_value(pct, col)
                self._core_widgets.append((lbl, bar))
        else:
            for (lbl, bar), pct in zip(self._core_widgets, cores):
                col = color_for_pct(pct)
                lbl.config(text=f"{pct}%", fg=col)
                bar.set_value(pct, col)

        # Disk: build rows once, update labels/bars in place
        current_mounts = {d["mountpoint"] for d in s["disks"]}
        if current_mounts != set(self._disk_widgets):
            for w in self._disk_frame.winfo_children():
                w.destroy()
            self._disk_widgets = {}
            for d in s["disks"]:
                row = tk.Frame(self._disk_frame, bg=CARD)
                row.pack(fill="x", pady=5)
                hdr = tk.Frame(row, bg=CARD)
                hdr.pack(fill="x")
                tk.Label(hdr, text=d["mountpoint"], fg=TEXT, bg=CARD,
                         font=("Segoe UI", 9, "bold")).pack(side="left")
                info_lbl = tk.Label(hdr, fg=MUTED, bg=CARD,
                                    font=("Segoe UI", 8))
                info_lbl.pack(side="right")
                bar = BarCanvas(row, height=8)
                bar.pack(fill="x", pady=(3, 0))
                bar.update_idletasks()
                self._disk_widgets[d["mountpoint"]] = (info_lbl, bar)
        for d in s["disks"]:
            mp = d["mountpoint"]
            if mp not in self._disk_widgets:
                continue
            info_lbl, bar = self._disk_widgets[mp]
            col = color_for_pct(d["percent"])
            info_lbl.config(
                text=f"{d['used_gb']}/{d['total_gb']} GB ({d['percent']}%)")
            bar.set_value(d["percent"], col)

        # Process table: update rows in place
        procs = s["procs"]
        ids   = self._tree_ids
        for i, row_id in enumerate(ids):
            if i < len(procs):
                p   = procs[i]
                cpu = f"{p.get('cpu_percent', 0):.1f}%"
                mem = f"{p.get('memory_percent', 0):.1f}%"
                self._tree.item(row_id, values=(
                    p["pid"], p["name"], cpu, mem, p.get("status", "")))
            else:
                self._tree.item(row_id, values=("", "", "", "", ""))


if __name__ == "__main__":
    threading.Thread(target=_fast_collector, daemon=True).start()
    threading.Thread(target=_slow_collector, daemon=True).start()
    App().mainloop()
