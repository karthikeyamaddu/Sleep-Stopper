import http.server
import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime

# Windows native power & input APIs
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import ctypes

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    VK_F15 = 0x7E
    KEYEVENTF_KEYUP = 0x0002

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except ImportError:
    pyautogui = None

try:
    import psutil
    CURRENT_PROCESS = psutil.Process(os.getpid())
    CURRENT_PROCESS.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None)
except ImportError:
    psutil = None
    CURRENT_PROCESS = None

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_history.json")


class SleepStopperCore:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.interval = 60  # seconds
        self.use_mouse = True
        self.use_f15 = True
        self.use_power_api = True

        # Current session live counters (reset to zero on stop)
        self.current_session_pings = 0
        self.current_session_start_time = None
        self.current_session_start_str = None
        self.next_ping_in = self.interval
        self.last_ping_time = None

        # Lifetime background accumulation & history
        self.lifetime_active_seconds = 0.0
        self.lifetime_pings = 0
        self.history = []

        # Load persisted history if available
        self.load_history()

        # Activity logs
        self.logs = []
        self.add_log("System initialized and ready.", "info")

        # Background worker
        self._stop_event = threading.Event()
        self._worker_thread = None

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.lifetime_active_seconds = float(data.get("lifetime_active_seconds", 0.0))
                    self.lifetime_pings = int(data.get("lifetime_pings", 0))
            except Exception:
                pass

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "lifetime_active_seconds": round(self.lifetime_active_seconds, 1),
                    "lifetime_pings": self.lifetime_pings,
                    "history": self.history
                }, f, indent=2)
        except Exception as e:
            self.add_log(f"Failed to save history: {e}", "warning")

    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append({"time": timestamp, "message": message, "level": level})
            if len(self.logs) > 40:
                self.logs.pop(0)

    def set_windows_power_state(self, keep_awake: bool):
        if not IS_WINDOWS:
            return
        try:
            if keep_awake and self.use_power_api:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        except Exception as e:
            self.add_log(f"Power API error: {e}", "error")

    def trigger_nudge(self):
        # 1. Windows Power API refresh
        if self.use_power_api:
            self.set_windows_power_state(True)

        # 2. Virtual harmless F15 key tap
        if self.use_f15 and IS_WINDOWS:
            try:
                ctypes.windll.user32.keybd_event(VK_F15, 0, 0, 0)
                time.sleep(0.01)
                ctypes.windll.user32.keybd_event(VK_F15, 0, KEYEVENTF_KEYUP, 0)
            except Exception as e:
                self.add_log(f"F15 key event error: {e}", "warning")

        # 3. Mouse 2px nudge
        if self.use_mouse and pyautogui:
            try:
                cx, cy = pyautogui.position()
                pyautogui.moveRel(2, 0, duration=0.06)
                time.sleep(0.02)
                pyautogui.moveTo(cx, cy, duration=0.06)
            except Exception:
                pass

        with self.lock:
            self.current_session_pings += 1
            self.lifetime_pings += 1
            self.last_ping_time = datetime.now().strftime("%H:%M:%S")
            pings_this_session = self.current_session_pings

        self.add_log(f"Ping #{pings_this_session} triggered in current session (Total all-time: {self.lifetime_pings})", "success")

    def _run_loop(self):
        countdown = self.interval
        while not self._stop_event.is_set():
            time.sleep(1)
            with self.lock:
                if not self.is_running:
                    break
                countdown -= 1
                self.next_ping_in = max(0, countdown)

            if countdown <= 0:
                self.trigger_nudge()
                with self.lock:
                    countdown = self.interval
                    self.next_ping_in = self.interval

    def start(self, interval: int = 60, use_mouse: bool = True, use_f15: bool = True, use_power_api: bool = True):
        with self.lock:
            if self.is_running:
                return False

            self.interval = max(2, int(interval))
            self.use_mouse = use_mouse
            self.use_f15 = use_f15
            self.use_power_api = use_power_api
            self.is_running = True
            
            # Initialize current session metrics fresh
            self.current_session_pings = 0
            self.current_session_start_time = time.time()
            self.current_session_start_str = datetime.now().strftime("%H:%M:%S")
            self.next_ping_in = self.interval
            self._stop_event.clear()

        # Engage Windows stay-awake state
        self.set_windows_power_state(True)
        session_num = len(self.history) + 1
        self.add_log(f"Started Session #{session_num} at {self.current_session_start_str} (Interval: {self.interval}s)", "info")

        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()
        return True

    def stop(self):
        session_record = None
        with self.lock:
            if not self.is_running:
                return False

            self.is_running = False
            self._stop_event.set()

            # Record and archive this instance
            elapsed = 0.0
            if self.current_session_start_time:
                elapsed = time.time() - self.current_session_start_time
                self.lifetime_active_seconds += elapsed

            session_id = len(self.history) + 1
            stop_str = datetime.now().strftime("%H:%M:%S")
            today_str = datetime.now().strftime("%Y-%m-%d")

            session_record = {
                "id": session_id,
                "date": today_str,
                "start_time": self.current_session_start_str or "N/A",
                "stop_time": stop_str,
                "duration_seconds": round(elapsed, 1),
                "pings": self.current_session_pings,
                "interval": self.interval,
            }
            # Add to history (newest first)
            self.history.insert(0, session_record)

            # Reset current session live counters to initial/zero
            self.current_session_pings = 0
            self.current_session_start_time = None
            self.current_session_start_str = None
            self.next_ping_in = self.interval

        # Disengage Windows stay-awake state
        self.set_windows_power_state(False)
        self.save_history()

        dur_display = f"{int(elapsed // 60)}m {int(elapsed % 60)}s" if elapsed >= 60 else f"{int(elapsed)}s"
        self.add_log(f"Session #{session_record['id']} stored in history ({dur_display}, {session_record['pings']} pings). Current counters reset to 0.", "warning")
        return True

    def clear_history(self):
        with self.lock:
            self.history.clear()
            self.lifetime_active_seconds = 0.0
            self.lifetime_pings = 0
            self.current_session_pings = 0
            if self.is_running and self.current_session_start_time:
                self.current_session_start_time = time.time()
        self.save_history()
        self.add_log("History and lifetime stats cleared.", "info")

    def get_resource_usage(self):
        process_cpu = 0.0
        process_mem_mb = 0.0
        sys_cpu = 0.0
        sys_mem_percent = 0.0
        battery_info = None

        if psutil and CURRENT_PROCESS:
            try:
                process_cpu = round(CURRENT_PROCESS.cpu_percent(interval=None), 2)
                process_mem_mb = round(CURRENT_PROCESS.memory_info().rss / (1024 * 1024), 2)
                sys_cpu = round(psutil.cpu_percent(interval=None), 1)
                sys_mem_percent = round(psutil.virtual_memory().percent, 1)

                batt = psutil.sensors_battery()
                if batt:
                    battery_info = {
                        "percent": batt.percent,
                        "power_plugged": batt.power_plugged,
                        "secsleft": batt.secsleft if batt.secsleft != psutil.POWER_TIME_UNLIMITED else None
                    }
            except Exception:
                pass
        elif IS_WINDOWS:
            try:
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", ctypes.c_ulong),
                        ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    process_mem_mb = round(counters.WorkingSetSize / (1024 * 1024), 2)
            except Exception:
                pass

        return {
            "process_cpu_percent": process_cpu,
            "process_memory_mb": process_mem_mb,
            "system_cpu_percent": sys_cpu,
            "system_memory_percent": sys_mem_percent,
            "battery": battery_info,
            "psutil_installed": psutil is not None
        }

    def get_status(self):
        with self.lock:
            # Active duration of current running session (0 if stopped)
            current_session_dur = 0.0
            if self.is_running and self.current_session_start_time:
                current_session_dur = time.time() - self.current_session_start_time

            # Total background usage includes all completed sessions + ongoing active time
            total_lifetime = self.lifetime_active_seconds + (current_session_dur if self.is_running else 0.0)

            status = {
                "running": self.is_running,
                "interval": self.interval,
                "next_ping_in": self.next_ping_in,
                "use_mouse": self.use_mouse,
                "use_f15": self.use_f15,
                "use_power_api": self.use_power_api,
                "current_session_seconds": round(current_session_dur, 1),
                "current_session_pings": self.current_session_pings,
                "lifetime_active_seconds": round(total_lifetime, 1),
                "lifetime_pings": self.lifetime_pings,
                "completed_sessions_count": len(self.history),
                "last_ping_time": self.last_ping_time,
                "history": list(self.history[:40]),  # return recent sessions
                "logs": list(self.logs),
            }

        status.update(self.get_resource_usage())
        return status


CORE = SleepStopperCore()
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class SleepStopperHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            data = CORE.get_status()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return
        
        if parsed.path in ["", "/"]:
            self.path = "/index.html"
            
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if parsed.path == "/api/start":
            interval = body.get("interval", 60)
            use_mouse = body.get("use_mouse", True)
            use_f15 = body.get("use_f15", True)
            use_power_api = body.get("use_power_api", True)
            success = CORE.start(interval, use_mouse, use_f15, use_power_api)
            self._send_json({"success": success, "status": CORE.get_status()})

        elif parsed.path == "/api/stop":
            success = CORE.stop()
            self._send_json({"success": success, "status": CORE.get_status()})

        elif parsed.path == "/api/clear_history":
            CORE.clear_history()
            self._send_json({"success": True, "status": CORE.get_status()})

        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def find_free_port(start_port=5000):
    for port in range(start_port, start_port + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start_port


def run_server(port=5000, auto_open=True):
    port = find_free_port(port)
    server_address = ("127.0.0.1", port)
    httpd = http.server.ThreadingHTTPServer(server_address, SleepStopperHTTPHandler)
    url = f"http://127.0.0.1:{port}"

    print("=" * 65)
    print("           SLEEP STOPPER PRO - WEB DASHBOARD            ")
    print("=" * 65)
    print(f"[*] Dashboard URL: {url}")
    print("[*] Keep-awake Engine, Session History & Monitor ready.")
    print("[*] Press Ctrl+C in this terminal to shut down.")
    print("=" * 65 + "\n")

    if auto_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down web server...")
    finally:
        CORE.stop()
        httpd.server_close()
        print("[*] Server stopped cleanly. Windows power policy restored.\n")


if __name__ == "__main__":
    run_server()
