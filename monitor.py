#!/usr/bin/env python3
"""Desktop load monitor - serves the UI and a JSON API for system stats."""

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import psutil

# Rolling history for sparkline charts (last 60 samples)
_history_lock = threading.Lock()
_history = {
    "cpu": [],
    "mem": [],
    "net_sent": [],
    "net_recv": [],
}
_MAX_HISTORY = 60

# Baseline for network delta calculation
_prev_net = psutil.net_io_counters()
_prev_time = time.time()


def _update_history():
    global _prev_net, _prev_time
    while True:
        now = time.time()
        net = psutil.net_io_counters()
        elapsed = now - _prev_time or 1

        sent_rate = (net.bytes_sent - _prev_net.bytes_sent) / elapsed
        recv_rate = (net.bytes_recv - _prev_net.bytes_recv) / elapsed
        _prev_net = net
        _prev_time = now

        with _history_lock:
            _history["cpu"].append(psutil.cpu_percent())
            _history["mem"].append(psutil.virtual_memory().percent)
            _history["net_sent"].append(round(sent_rate / 1024, 2))  # KB/s
            _history["net_recv"].append(round(recv_rate / 1024, 2))  # KB/s
            for key in _history:
                if len(_history[key]) > _MAX_HISTORY:
                    _history[key].pop(0)

        time.sleep(1)


def _get_stats():
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / 1e9, 1),
                "used_gb": round(usage.used / 1e9, 1),
                "free_gb": round(usage.free / 1e9, 1),
                "percent": usage.percent,
            })
        except PermissionError:
            pass

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)

    with _history_lock:
        history = {k: list(v) for k, v in _history.items()}

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cpu": {
            "percent": psutil.cpu_percent(percpu=False),
            "per_core": psutil.cpu_percent(percpu=True),
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
            "freq_current_mhz": round(cpu_freq.current) if cpu_freq else None,
            "freq_max_mhz": round(cpu_freq.max) if cpu_freq else None,
        },
        "memory": {
            "total_gb": round(mem.total / 1e9, 1),
            "used_gb": round(mem.used / 1e9, 1),
            "available_gb": round(mem.available / 1e9, 1),
            "percent": mem.percent,
            "swap_total_gb": round(swap.total / 1e9, 1),
            "swap_used_gb": round(swap.used / 1e9, 1),
            "swap_percent": swap.percent,
        },
        "disks": disks,
        "processes": procs[:20],
        "history": history,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress access logs

    def _send(self, code, content_type, body):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(encoded))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/stats":
            data = json.dumps(_get_stats(), ensure_ascii=False)
            self._send(200, "application/json; charset=utf-8", data)
        elif path in ("/", "/index.html"):
            with open("index.html", "rb") as f:
                self._send(200, "text/html; charset=utf-8", f.read())
        else:
            self._send(404, "text/plain", "Not found")


if __name__ == "__main__":
    # Warm up cpu_percent (first call always returns 0)
    psutil.cpu_percent(percpu=True)

    t = threading.Thread(target=_update_history, daemon=True)
    t.start()

    port = 8080
    server = HTTPServer(("", port), Handler)
    print(f"デスクトップ負荷モニター起動中 → http://localhost:{port}")
    print("停止するには Ctrl+C を押してください")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止しました")
