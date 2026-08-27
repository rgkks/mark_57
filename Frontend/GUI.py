from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from dotenv import dotenv_values
import sys
import os
import math
import json
import time
import random
import threading
import subprocess
import webbrowser
import psutil
en_vars = dotenv_values("jarvis.env")
AssistantName = en_vars["Assistantname"]
UserName = en_vars.get("UserName", "User")
current_dir = os.getcwd()
old_chat_message = ""
TempDirPath = f"{current_dir}/Frontend/Files"
GraphicsDirPath = f"{current_dir}/Frontend/Graphics"
THEME = {
    "bg_panel":        QColor(6, 14, 26, 172),
    "bg_panel_solid":  QColor(6, 12, 22),
    "border":          QColor(0, 170, 255, 80),
    "border_hi":       QColor(0, 210, 255, 140),
    "text":            QColor(198, 236, 255),
    "text_dim":        QColor(120, 180, 215, 190),
    "accent":          QColor(0, 195, 255),
    "warn":            QColor(255, 176, 32),
    "error":           QColor(255, 82, 82),
    "ok":              QColor(60, 230, 160),
    "font":            "DejaVu Sans",
}
CFG = {
    "orb_fps": 30,             # ms derived below
    "telemetry_ms": 1000,
    "watch_ms": 120,
    "clock_ms": 500,
    "terminal_ms": 400,
    "chat_ms": 200,
    "ping_every": 10,          # telemetry cycles between pings
    "max_feed": 7,
    "max_history": 30,
    "ram_warn": 88.0,
    "batt_low": 20,
}
def AnswerModifier(Answer):
    lines = Answer.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    return "\n".join(non_empty_lines)
def QueryModifier(Query):
    new_query = Query.lower().strip()
    query_words = new_query.split()
    if not query_words:
        return ""
    question_words = ["how", "what", "who", "where", "when", "why", "which", "whose",
                      "whom", "can you", "what's", "where's", "who's", "how's"]
    if new_query[-1] == '?':
        if query_words[-1][-1] != '?':
            new_query += "?"
    elif any(word + " " in new_query for word in question_words):
        if query_words[-1][-1] in [".", "?", "!"]:
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if query_words[-1][-1] in [".", "?", "!"]:
            new_query = new_query[:-1] + "."
        else:
            new_query += "."
    return new_query.capitalize()
def SetMicrophoneStatus(Command):
    with open(f"{TempDirPath}/Mic.data", "w", encoding="utf-8") as file:
        file.write(Command)
def GetMicrophoneStatus():
    with open(f"{TempDirPath}/Mic.data", "r", encoding="utf-8") as file:
        return file.read()
def SetAssistantStatus(Status):
    with open(f"{TempDirPath}/Status.data", "w", encoding="utf-8") as file:
        file.write(Status)
def GetAssistantStatus():
    try:
        with open(f"{TempDirPath}/Status.data", "r", encoding="utf-8") as file:
            return file.read()
    except Exception:
        return ""
def MicButtonInitialed():
    SetMicrophoneStatus("False")
def MicButtonClosed():
    SetMicrophoneStatus("True")
class MicButton(QWidget):
    clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 110)  # room for mic + status text
        self.setCursor(Qt.PointingHandCursor)
        self._active = False
        self._hover = False
        self._pressed = False
        self._t = 0.0
        self._lvl = 0.0           # smoothed audio level (0..1)
        self._state = "STANDBY"    # STANDBY / LISTENING / THINKING / SPEAKING / ERROR
        self._speak_file = TempDirectoryPath("Speaking.data")
    def set_active(self, active):
        self._active = active
        self.update()
    def set_state(self, state):
        self._state = state
        self.update()
    def _tick(self):
        self._t += 1
        try:
            raw = float(_read_file(TempDirectoryPath("AudioLevel.data"), "0").strip() or 0)
        except Exception:
            raw = 0.0
        self._lvl += (max(0.0, min(1.0, raw)) - self._lvl) * 0.25
        self.update()
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        cx, cy = w/2, 45  # center of mic area (not full height)
        t = self._t
        st = self._state
        lvl = self._lvl
        if st == "LISTENING":
            base_col = QColor(0, 255, 200)
            glow_col = QColor(0, 255, 200)
        elif st == "THINKING":
            base_col = QColor(100, 160, 255)
            glow_col = QColor(100, 160, 255)
        elif st == "SPEAKING":
            base_col = QColor(0, 200, 255)
            glow_col = QColor(0, 200, 255)
        elif st == "ERROR":
            base_col = QColor(255, 80, 80)
            glow_col = QColor(255, 80, 80)
        else:  # STANDBY
            base_col = QColor(0, 180, 255)
            glow_col = QColor(0, 180, 255)
        active = self._active
        hover = self._hover
        glow_r = 42
        if active:
            breath = 0.5 + 0.5 * math.sin(t * 0.06)
            ga = int(25 + 20 * breath)
            if st == "LISTENING":
                ga = int(30 + 40 * lvl)
                glow_r = 42 + int(8 * lvl)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(glow_col.red(), glow_col.green(), glow_col.blue(), ga))
            p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        ring_r = 38
        ring_pen = QPen(QColor(base_col.red(), base_col.green(), base_col.blue(),
                               100 if active else 50), 1.0)
        p.setPen(ring_pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
        if active or hover:
            arc_start = int(t * (2.0 if st == "LISTENING" else 1.0)) % 360
            arc_pen = QPen(QColor(base_col.red(), base_col.green(), base_col.blue(), 160), 2.0)
            arc_pen.setCapStyle(Qt.RoundCap)
            p.setPen(arc_pen)
            arc_rect = QRectF(cx - ring_r, cy - ring_r, ring_r*2, ring_r*2)
            p.drawArc(arc_rect, arc_start * 16, 60 * 16)
        if active:
            tick_pen = QPen(QColor(base_col.red(), base_col.green(), base_col.blue(), 80), 1.0)
            p.setPen(tick_pen)
            for i in range(12):
                a = math.radians(i * 30 + t * 0.5)
                inner = ring_r - 3
                outer = ring_r + 1
                p.drawLine(QPointF(cx + math.cos(a)*inner, cy + math.sin(a)*inner),
                           QPointF(cx + math.cos(a)*outer, cy + math.sin(a)*outer))
        if active and st == "LISTENING" and lvl > 0.01:
            audio_r = 30 + int(6 * lvl)
            audio_a = int(60 + 100 * lvl)
            p.setPen(QPen(QColor(base_col.red(), base_col.green(), base_col.blue(), audio_a), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), audio_r, audio_r)
        bg = QColor(8, 16, 30, 210)
        border_col = QColor(base_col.red(), base_col.green(), base_col.blue(),
                            180 if active else 80)
        if hover:
            border_col = QColor(base_col.red(), base_col.green(), base_col.blue(), 220)
        if self._pressed:
            bg = QColor(12, 24, 44, 230)
        p.setPen(QPen(border_col, 1.5))
        p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), 28, 28)
        hi = QRadialGradient(QPointF(cx - 6, cy - 8), 20)
        hi.setColorAt(0, QColor(255, 255, 255, 18 if active else 8))
        hi.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen); p.setBrush(hi)
        p.drawEllipse(QPointF(cx, cy), 27, 27)
        mic_col = QColor(base_col.red(), base_col.green(), base_col.blue(),
                         240 if active else 160)
        if hover:
            mic_col = QColor(base_col.red(), base_col.green(), base_col.blue(), 255)
        mic_pen = QPen(mic_col, 2.2)
        mic_pen.setCapStyle(Qt.RoundCap)
        mic_pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(mic_pen); p.setBrush(Qt.NoBrush)
        capsule = QRectF(cx - 5, cy - 14, 10, 16)
        p.drawRoundedRect(capsule, 5, 5)
        arc_rect = QRectF(cx - 9, cy - 6, 18, 16)
        p.drawArc(arc_rect, 0, 180 * 16)
        p.drawLine(QPointF(cx, cy + 10), QPointF(cx, cy + 17))
        p.drawLine(QPointF(cx - 5, cy + 17), QPointF(cx + 5, cy + 17))
        if active:
            dot_pulse = 0.5 + 0.5 * math.sin(t * 0.15)
            da = int(150 + 105 * dot_pulse)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 255, 180, da))
            p.drawEllipse(QPointF(cx + 20, cy - 20), 3, 3)
        status_map = {
            "STANDBY":    "READY",
            "LISTENING":  "LISTENING...",
            "THINKING":   "PROCESSING...",
            "SPEAKING":   "SPEAKING...",
            "ERROR":      "ERROR",
        }
        status = status_map.get(st, "READY")
        sf = QFont(THEME["font"], 7)
        sf.setLetterSpacing(QFont.AbsoluteSpacing, 1)
        p.setFont(sf)
        text_col = QColor(base_col.red(), base_col.green(), base_col.blue(),
                          180 if active else 100)
        p.setPen(QPen(text_col))
        p.drawText(QRectF(0, cy + 30, w, 20), Qt.AlignHCenter | Qt.AlignTop, status)
    def enterEvent(self, e):
        self._hover = True; self.update()
    def leaveEvent(self, e):
        self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pressed = True; self.update()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pressed = False
            self.clicked.emit()
            self.update()
def GraphicsDirectoryPath(Filename):
    return f"{GraphicsDirPath}/{Filename}"
def TempDirectoryPath(Filename):
    return f"{TempDirPath}/{Filename}"
def ShowTextToScreen(Text):
    with open(f"{TempDirPath}/Response.data", "w", encoding="utf-8") as file:
        file.write(Text)
def _read_file(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default
class GS:
    STANDBY = "STANDBY"; LISTENING = "LISTENING"; THINKING = "THINKING"
    PROCESSING = "PROCESSING"; SPEAKING = "SPEAKING"; ERROR = "ERROR"
_state_lock = threading.Lock()
_gui_state = {"state": GS.STANDBY, "level": 0.0, "partial": "", "active_task": "",
              "agent_evt": []}
_state_observers = []
def gui_state():
    with _state_lock:
        return _gui_state["state"]
def gui_level():
    with _state_lock:
        return _gui_state["level"]
def gui_partial():
    with _state_lock:
        return _gui_state["partial"]
def gui_task():
    with _state_lock:
        return _gui_state["active_task"]
def set_gui_state(new):
    with _state_lock:
        old = _gui_state["state"]
        if new != old:
            _gui_state["state"] = new
            for cb in list(_state_observers):
                try: cb(old, new)
                except Exception: pass
def set_gui_level(v):
    with _state_lock:
        _gui_state["level"] = v
def set_gui_partial(t):
    with _state_lock:
        _gui_state["partial"] = t
def set_gui_task(t):
    with _state_lock:
        _gui_state["active_task"] = t
def gui_agent_events():
    with _state_lock:
        return list(_gui_state["agent_evt"])
def set_gui_agent_events(evts):
    with _state_lock:
        _gui_state["agent_evt"] = evts
class StateWatcher(QThread):
    stateChanged   = pyqtSignal(str, str)     # old, new
    levelChanged   = pyqtSignal(float)
    partialChanged = pyqtSignal(str)
    taskChanged    = pyqtSignal(str)
    agentEventsSig = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = True
    def stop(self):
        self._run = False
    def run(self):
        last = {"status": None, "mic": None, "speak": None, "task": None, "evt": None}
        while self._run:
            status = _read_file(TempDirectoryPath("Status.data")).strip()
            mic_on = _read_file(TempDirectoryPath("Mic.data")).strip().lower() == "true"
            speak  = _read_file(TempDirectoryPath("Speaking.data")).strip().lower() in ("true", "1", "yes")
            try:
                lvl = float(_read_file(TempDirectoryPath("AudioLevel.data"), "0").strip() or 0)
            except ValueError:
                lvl = 0.0
            lvl = max(0.0, min(1.0, lvl))
            partial = _read_file(TempDirectoryPath("Partial.data")).strip()
            task, evts = "", []
            try:
                with open(os.path.join(TempDirPath, "AgentStatus.json"), encoding="utf-8") as f:
                    snap = json.load(f)
                task = (snap.get("active_task") or "").strip()
                ags = snap.get("agents") or []
                evts = [f"{a.get('specialist','?')} {a.get('state','')}".strip() for a in ags]
            except Exception:
                pass
            if status.lower() == "error":
                st = GS.ERROR
            elif speak:
                st = GS.SPEAKING
            elif task or any(k in status for k in ("Generating", "Executing")):
                st = GS.PROCESSING
            elif status.strip() in ("Thinking...", "Searching..."):
                st = GS.THINKING
            elif status.strip() == "Listening..." or mic_on:
                st = GS.LISTENING
            else:
                st = GS.STANDBY
            if status != last["status"] or mic_on != last["mic"] or \
               speak != last["speak"] or st != gui_state():
                self.stateChanged.emit(gui_state(), st)
                set_gui_state(st)
            last.update(status=status, mic=mic_on, speak=speak)
            if abs(lvl - gui_level()) > 0.004:
                set_gui_level(lvl); self.levelChanged.emit(lvl)
            if partial != gui_partial():
                set_gui_partial(partial); self.partialChanged.emit(partial)
            if task != last["task"]:
                set_gui_task(task); self.taskChanged.emit(task); last["task"] = task
            if evts != last["evt"]:
                set_gui_agent_events(evts); self.agentEventsSig.emit(evts); last["evt"] = evts
            time.sleep(CFG["watch_ms"] / 1000.0)
class TelemetryWorker(QThread):
    tick = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = True
        self._net_last = None
        self._net_t = 0.0
        self._cycle = 0
        self._gpu_ok = None   # tri-state probe cache
        self._temp_key = None
        self._net_consecutive_fails = 0
        self._net_consecutive_ok = 0
        self._net_online = None          # last emitted state (None = unknown)
        self._active_iface = None        # cached active interface name
        self._PING_HOSTS = [("1.1.1.1", 443), ("8.8.8.8", 443), ("9.9.9.9", 443)]
        self._FAIL_THRESHOLD = 3         # consecutive failures before offline
        self._OK_THRESHOLD = 2           # consecutive successes before online
    def stop(self):
        self._run = False
    def _gpu(self):
        if self._gpu_ok is None:
            from shutil import which
            self._gpu_ok = bool(which("nvidia-smi"))
        if not self._gpu_ok:
            return "N/A"
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2).stdout.strip()
            util, temp = out.split(",")
            return f"{util.strip()}%"
        except Exception:
            self._gpu_ok = False
            return "N/A"
    def _cpu_temp(self):
        try:
            t = psutil.sensors_temperatures() or {}
            if not t:
                return "N/A"
            if self._temp_key not in t:
                for k in ("coretemp", "k10temp", "zenpower", "acpitz", "cpu_thermal"):
                    if k in t:
                        self._temp_key = k; break
                else:
                    self._temp_key = next(iter(t))
            e = t[self._temp_key][0]
            return f"{e.current:.0f}°C"
        except Exception:
            return "N/A"
    def _detect_active_iface(self):
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[1] == "00000000":
                        return parts[0]
        except Exception:
            pass
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, st in stats.items():
                if st.isup and name in addrs:
                    for a in addrs[name]:
                        if a.family.name == "AF_INET" and a.address:
                            return name
        except Exception:
            pass
        return None
    def _ping_ms(self):
        import socket
        iface_up = self._check_iface_up()
        for host, port in self._PING_HOSTS:
            try:
                s = socket.socket(); s.settimeout(1.0)
                t0 = time.perf_counter()
                s.connect((host, port))
                dt = (time.perf_counter() - t0) * 1000.0
                s.close()
                return round(dt), True
            except Exception:
                continue
        return None, iface_up
    def _check_iface_up(self):
        iface = self._detect_active_iface()
        if iface:
            self._active_iface = iface
            try:
                stats = psutil.net_if_stats()
                return stats.get(iface, None) and stats[iface].isup
            except Exception:
                pass
        return True
    def _compute_net_online(self, ping_ms, iface_up, traffic_active):
        if self._net_online is None:
            self._net_online = iface_up or traffic_active
            self._net_consecutive_ok = 1 if self._net_online else 0
            self._net_consecutive_fails = 0 if self._net_online else 1
            return self._net_online
        is_ok = (ping_ms is not None) or traffic_active
        if not iface_up:
            is_ok = False
        if is_ok:
            self._net_consecutive_fails = 0
            self._net_consecutive_ok += 1
            if not self._net_online and self._net_consecutive_ok >= self._OK_THRESHOLD:
                self._net_online = True
        else:
            self._net_consecutive_ok = 0
            weight = 2 if not iface_up else 1
            self._net_consecutive_fails += weight
            if self._net_online and self._net_consecutive_fails >= self._FAIL_THRESHOLD:
                self._net_online = False
        return self._net_online
    def run(self):
        psutil.cpu_percent(interval=None)  # prime
        while self._run:
            d = {}
            try: d["cpu"] = psutil.cpu_percent(interval=None)
            except Exception: d["cpu"] = None
            try:
                vm = psutil.virtual_memory()
                d["ram"] = vm.percent
                d["ram_used"] = vm.used // (1024**2)
                d["ram_total"] = vm.total // (1024**2)
            except Exception: d["ram"] = None
            try:
                du = psutil.disk_usage("/")
                d["disk"] = du.percent
                d["disk_free"] = du.free // (1024**3)
            except Exception: d["disk"] = None
            try:
                b = psutil.sensors_battery()
                if b:
                    d["batt"] = b.percent
                    d["batt_plug"] = b.power_plugged
                    secs = b.secsleft
                    d["batt_time"] = (secs if isinstance(secs, int) and secs > 0 else None)
                else:
                    d["batt"] = None
            except Exception: d["batt"] = None
            try:
                io = psutil.net_io_counters()
                now = time.time()
                if self._net_last is not None:
                    dt = max(0.2, now - self._net_t)
                    d["down"] = max(0.0, (io.bytes_recv - self._net_last.bytes_recv) / dt / (1024*1024))
                    d["up"]   = max(0.0, (io.bytes_sent - self._net_last.bytes_sent) / dt / (1024*1024))
                else:
                    d["down"] = 0.0; d["up"] = 0.0
                self._net_last = io; self._net_t = now
            except Exception: d["down"] = d["up"] = None
            self._cycle += 1
            if self._cycle % 2 == 0 or "gpu" not in d:
                d["gpu"] = self._gpu() if self._cycle % 2 == 0 else "N/A"
            if self._cycle % 3 == 0 or "cputemp" not in d:
                d["cputemp"] = self._cpu_temp() if self._cycle % 3 == 0 else "N/A"
            if self._cycle % CFG["ping_every"] == 0:
                ping_ms, iface_up = self._ping_ms()
                d["ping"] = ping_ms
            else:
                ping_ms = d.get("ping")
                iface_up = self._check_iface_up()
            traffic = (d.get("down") or 0) > 0.001 or (d.get("up") or 0) > 0.001
            d["net_online"] = self._compute_net_online(ping_ms, iface_up, traffic)
            d["net_iface"] = self._active_iface
            self.tick.emit(d)
            for _ in range(CFG["telemetry_ms"] // 50):
                if not self._run: break
                time.sleep(0.05)
import subprocess  # noqa: E402 (used by TelemetryWorker; kept near THEME for clarity)
class GlassPanel(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self._title = title.upper()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._glow = 0.0   # 0..1 highlight pulse driven by owners
    def set_glow(self, v):
        self._glow = max(0.0, min(1.0, v)); self.update()
    def paint_glass(self, p, r=None):
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(THEME["bg_panel"])
        p.drawRoundedRect(rect, 10, 10)
        edge = QColor(THEME["border"])
        if self._glow > 0:
            edge = QColor(THEME["border_hi"]); edge.setAlpha(int(edge.alpha() * (0.6 + 0.4*self._glow)))
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 10, 10)
        p.setPen(QPen(QColor(THEME["accent"].red(), THEME["accent"].green(),
                             THEME["accent"].blue(), 150), 1))
        L = 8
        for cx, cy, dx, dy in ((rect.left(),rect.top(),1,1),(rect.right(),rect.top(),-1,1),
                               (rect.left(),rect.bottom(),1,-1),(rect.right(),rect.bottom(),-1,-1)):
            p.drawLine(QPointF(cx, cy+dy*L), QPointF(cx, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx+dx*L, cy))
        if self._title:
            f = QFont(THEME["font"], 7); f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
            f.setBold(True)
            p.setFont(f); p.setPen(QPen(THEME["text_dim"], 1))
            p.drawText(rect.adjusted(10, 4, -10, -4), Qt.AlignTop | Qt.AlignLeft, self._title)
class ActivityFeed(GlassPanel):
    def __init__(self, parent=None):
        super().__init__("SYSTEM ACTIVITY", parent)
        self._items = []           # [(icon,text,time)]
        self._last_key = ""
        self._anim = 0
        self._t = QTimer(self); self._t.timeout.connect(self._age)
        self._t.start(500)
    ICONS = {"listen": "🎤", "think": "🧠", "proc": "⚙", "web": "🌐",
             "done": "✓", "err": "⚠", "info": "•"}
    def push(self, kind, text):
        key = kind + "|" + text
        if key == self._last_key:          # de-dupe spam
            return
        self._last_key = key
        stamp = time.strftime("%H:%M:%S")
        self._items.append((self.ICONS.get(kind, "•"), text, stamp))
        del self._items[:-CFG["max_feed"]]
        self._anim = 1.0                   # slide-in animation trigger
        self.update()
    def _age(self):
        if self._anim > 0:
            self._anim = max(0.0, self._anim - 0.25); self.update()
    def paintEvent(self, e):
        p = QPainter(self); self.paint_glass(p)
        f = QFont(THEME["font"], 8); p.setFont(f)
        y = 26.0
        slide = (1.0 - self._anim) * 10
        for icon, text, stamp in reversed(self._items):
            if y > self.height() - 14: break
            p.setPen(QPen(THEME["text"]))
            p.drawText(QRectF(10, y - slide, 18, 16), Qt.AlignVCenter, icon)
            fm = p.fontMetrics()
            el = fm.elidedText(text, Qt.ElideRight, self.width() - 92)
            p.drawText(QRectF(30, y - slide, self.width()-92, 16), Qt.AlignVCenter, el)
            p.setPen(QPen(THEME["text_dim"]))
            p.drawText(QRectF(self.width()-58, y - slide, 52, 16), Qt.AlignVCenter, stamp)
            y += 19
class CommandHistory(GlassPanel):
    def __init__(self, parent=None):
        super().__init__("COMMAND HISTORY", parent)
        self._cmds = []
        self._seen = None
        self._t = QTimer(self); self._t.timeout.connect(self._poll)
        self._t.start(1500)
    def _poll(self):
        try:
            with open(os.path.join(current_dir, "Data", "Chatlog.json"), encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            return
        users = [m["content"].strip() for m in log if m.get("role") == "user"
                 and m.get("content", "").strip()]
        sig = tuple(users[-CFG["max_history"]:])
        if sig != self._seen:
            self._seen = sig
            self._cmds = users[-CFG["max_history"]:][::-1]   # newest first
            self.update()
    def paintEvent(self, e):
        p = QPainter(self); self.paint_glass(p)
        f = QFont(THEME["font"], 8); p.setFont(f)
        y = 26.0
        fm = p.fontMetrics()
        for i, c in enumerate(self._cmds):
            if y > self.height() - 12: break
            p.setPen(QPen(THEME["accent"] if i == 0 else THEME["text_dim"], 1))
            p.drawText(QRectF(12, y, 14, 15), Qt.AlignVCenter, "›")
            el = fm.elidedText(c, Qt.ElideRight, self.width() - 40)
            p.setPen(QPen(THEME["text"] if i == 0 else THEME["text_dim"], 1))
            p.drawText(QRectF(28, y, self.width()-38, 15), Qt.AlignVCenter, el)
            y += 17
class TaskPanel(GlassPanel):
    def __init__(self, parent=None):
        super().__init__("CURRENT TASK", parent)
        self.task = ""
        self.action = ""
        self._t0 = time.time()
    def set_task(self, task, action=""):
        if task != self.task:
            self.task = task; self._t0 = time.time()
        self.action = action
        self.setVisible(bool(task))
    def paintEvent(self, e):
        if not self.task: return
        p = QPainter(self); self.paint_glass(p)
        f = QFont(THEME["font"], 9, QFont.DemiBold); p.setFont(f)
        p.setPen(QPen(THEME["text"]))
        fm = p.fontMetrics()
        p.drawText(QRectF(12, 24, self.width()-24, 20), Qt.AlignVCenter,
                   fm.elidedText(self.task, Qt.ElideMiddle, self.width()-24))
        y = self.height() - 26.0
        track = QRectF(12, y, self.width()-24, 6)
        p.setPen(Qt.NoPen); p.setBrush(QColor(0, 90, 160, 70))
        p.drawRoundedRect(track, 3, 3)
        ph = (time.time() - self._t0) * 0.55 % 1.0
        bw = track.width() * 0.28
        x = track.left() + (track.width() + bw) * ph - bw
        x = max(track.left(), min(x, track.right() - bw))
        grad = QLinearGradient(x, 0, x + bw, 0)
        grad.setColorAt(0, QColor(0,195,255,20)); grad.setColorAt(0.5, QColor(0,220,255,220))
        grad.setColorAt(1, QColor(0,195,255,20))
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(x, y, bw, 6), 3, 3)
        f2 = QFont(THEME["font"], 7); p.setFont(f2)
        p.setPen(QPen(THEME["text_dim"]))
        p.drawText(QRectF(12, y-18, self.width()-24, 14), Qt.AlignVCenter,
                   fm.elidedText(self.action or "Working…", Qt.ElideRight, self.width()-24))
class ClockHUD(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._t = QTimer(self); self._t.timeout.connect(lambda: self.update())
        self._t.start(CFG["clock_ms"])
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        now = QTime.currentTime(); d = QDate.currentDate()
        p.setFont(QFont(THEME["font"], 16, QFont.Light))
        p.setPen(QPen(THEME["text"]))
        p.drawText(QRectF(0, 0, self.width(), 26), Qt.AlignRight | Qt.AlignVCenter,
                   now.toString("HH:mm:ss"))
        p.setFont(QFont(THEME["font"], 7))
        p.setPen(QPen(THEME["text_dim"]))
        day = d.toString("dddd").upper()
        p.drawText(QRectF(0, 26, self.width(), 14), Qt.AlignRight | Qt.AlignVCenter,
                   f"{d.toString('dd MMM yyyy').upper()}  ·  {day}")
class NetGraph(GlassPanel):
    def __init__(self, parent=None):
        super().__init__("NETWORK", parent)
        self.hist = [0.0]*64
        self.down = self.up = None
        self.ping = None
        self.online = None
    def update_stats(self, d):
        self.down, self.up, self.ping = d.get("down"), d.get("up"), d.get("ping")
        if d.get("down") is not None:
            self.hist.pop(0); self.hist.append(min(1.0, d["down"] / 8.0))
        new_online = d.get("net_online")
        self.update()
    def fmt(self, v):
        if v is None: return "—"
        return f"{v/1024:.1f} GB/s" if v >= 1024 else f"{v:.1f} MB/s"
    def paintEvent(self, e):
        p = QPainter(self); self.paint_glass(p)
        f = QFont(THEME["font"], 8); p.setFont(f)
        iface = getattr(self, "_iface_label", None)
        ping_str = f"{self.ping} ms" if self.ping is not None else "—"
        status_str = "ONLINE" if self.online else ("OFFLINE" if self.online is not None else "…")
        rows = [("▼ DOWN", self.fmt(self.down)), ("▲ UP", self.fmt(self.up)),
                ("PING",  ping_str),
                ("STATUS", status_str)]
        y = 26.0
        for name, val in rows:
            p.setPen(QPen(THEME["text_dim"])); p.drawText(QRectF(12, y, 52, 15), Qt.AlignVCenter, name)
            if name == "STATUS":
                col = THEME["ok"] if val == "ONLINE" else (THEME["error"] if val == "OFFLINE" else THEME["text_dim"])
            elif val == "—":
                col = THEME["text_dim"]
            else:
                col = THEME["text"]
            p.setPen(QPen(col)); p.drawText(QRectF(66, y, self.width()-76, 15), Qt.AlignVCenter, val)
            y += 17
        gx, gy = 12, y + 4
        gw, gh = self.width() - 24, self.height() - gy - 12
        if gh > 8:
            p.setPen(QPen(QColor(0,170,255,60), 1))
            p.setBrush(QColor(0,120,255,26))
            poly = QPolygonF([QPointF(gx, gy+gh)])
            n = len(self.hist)
            for i, v in enumerate(self.hist):
                poly.append(QPointF(gx + gw * i/(n-1), gy + gh*(1-v)))
            poly.append(QPointF(gx+gw, gy+gh))
            p.drawPolygon(poly)
class TelemetryPanel(GlassPanel):
    ROWS = ["CPU", "RAM", "GPU", "CPU TEMP", "DISK", "BATTERY"]
    def __init__(self, parent=None):
        super().__init__("SYSTEM TELEMETRY", parent)
        self.vals = {}
    def update_stats(self, d):
        self.vals = d
        self.update()
    @staticmethod
    def _pct(v):
        return "N/A" if v is None else f"{v:.0f}%"
    def paintEvent(self, e):
        p = QPainter(self); self.paint_glass(p)
        d = self.vals
        ram_txt = ("N/A" if d.get("ram") is None else
                   f"{d['ram']:.0f}%  ({d.get('ram_used',0)//1024}/{d.get('ram_total',0)//1024}G)")
        batt = ("N/A" if d.get("batt") is None else
                f"{d['batt']:.0f}%{' ⚡' if d.get('batt_plug') else ''}")
        rows = [
            ("CPU", self._pct(d.get("cpu")), (d.get("cpu") or 0)/100),
            ("RAM", ram_txt, (d.get("ram") or 0)/100),
            ("GPU", d.get("gpu", "N/A"), None),
            ("CPU TEMP", d.get("cputemp", "N/A"), None),
            ("DISK", self._pct(d.get("disk")), (d.get("disk") or 0)/100),
            ("BATTERY", batt, (d.get("batt") or 0)/100),
        ]
        f = QFont(THEME["font"], 8); p.setFont(f)
        y = 26.0
        for name, val, frac in rows:
            p.setPen(QPen(THEME["text_dim"]))
            p.drawText(QRectF(12, y, 66, 14), Qt.AlignVCenter, name)
            na = (val == "N/A")
            p.setPen(QPen(THEME["error"] if na else THEME["text"]))
            p.drawText(QRectF(self.width()-58, y, 48, 14), Qt.AlignVCenter | Qt.AlignRight, str(val))
            if frac is not None and self.height() > 150:
                bx, bw_, bh = 12, self.width()-24, 3
                by = y + 15
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 90, 160, 60))
                p.drawRoundedRect(QRectF(bx, by, bw_, bh), 1.5, 1.5)
                col = THEME["warn"] if frac > .85 else THEME["accent"]
                p.setBrush(col)
                p.drawRoundedRect(QRectF(bx, by, max(2, bw_*min(1,frac)), bh), 1.5, 1.5)
                y += 6
            y += 19
class NeuralViz(GlassPanel):
    def __init__(self, parent=None):
        super().__init__("NEURAL CORE", parent)
        rng = random.Random(11)
        self.nodes = []
        n = 26
        for i in range(n):
            a = i * (math.tau / n * 2.7)          # two interleaved rings + jitter
            ring = 0.62 if i % 2 else 1.0
            self.nodes.append((rng.uniform(-1,1)*0.08, rng.uniform(-1,1)*0.06, ring, a,
                               rng.uniform(0.5, 1.0)))
        self.energy = 0.15
        self.cpu = None
    def update_stats(self, d):
        self.cpu = d.get("cpu")
    def set_energy(self, e):
        self.energy = e
    def _load(self):
        base = (self.cpu / 100.0) if self.cpu is not None else 0.0
        v = 0.65*base + 0.35*self.energy
        return max(0.04, min(1.0, v))
    def paintEvent(self, e):
        p = QPainter(self); self.paint_glass(p)
        w, h = self.width(), self.height()
        cx, cy = w*0.30, h*0.56
        R = min(h*0.34, w*0.22)
        load = self._load()
        t = time.time()
        pen = QPen(QColor(0,170,255,int(50+90*load)), 1)
        p.setPen(pen)
        pts = []
        for jx, jy, ring, a, spd in self.nodes:
            aa = a + t*spd*0.25*ring*(0.6+load)
            x = cx + math.cos(aa)*R*ring + jx*R
            y = cy + math.sin(aa)*R*ring*0.85 + jy*R
            pts.append(QPointF(x,y))
        step = 3
        for i in range(len(pts)-step):
            if i % step == 0:
                p.drawLine(pts[i], pts[i+step])
        pi = int((t*1.4) % len(pts))
        p.setPen(Qt.NoPen); p.setBrush(QColor(150,240,255,220))
        p.drawEllipse(pts[pi], 2.2, 2.2)
        for pt, (jx,jy,ring,a,spd) in zip(pts, self.nodes):
            al = int(90 + 130*((math.sin(t*2+ a)+1)/2)*load + 40)
            p.setBrush(QColor(140,235,255,max(40,min(255,al))))
            p.drawEllipse(pt, 1.6, 1.6)
        f = QFont(THEME["font"], 12, QFont.Light); p.setFont(f)
        p.setPen(QPen(THEME["text"]))
        p.drawText(QRectF(w*0.58, h*0.30, w*0.38, 24), Qt.AlignVCenter|Qt.AlignLeft,
                   f"{load*100:4.1f}%")
        f2 = QFont(THEME["font"], 7); p.setFont(f2)
        p.setPen(QPen(THEME["text_dim"]))
        lbl = {"STANDBY":"IDLE","LISTENING":"INPUT","THINKING":"REASONING",
               "PROCESSING":"EXECUTE","SPEAKING":"OUTPUT","ERROR":"FAULT"}[gui_state()]
        p.drawText(QRectF(w*0.58, h*0.30+24, w*0.38, 14), Qt.AlignVCenter|Qt.AlignLeft, lbl)
class QuickActions(QWidget):
    ITEMS = [("MIC","⏺"),("SEARCH","🔍"),("MUSIC","♪"),("SCREENSHOT","▣"),
             ("FILES","▤"),("SETTINGS","⚙")]
    actionRequested = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._hover = self._press = -1
        self.setMouseTracking(True)
    def _geom(self):
        n = len(self.ITEMS); gap = 8
        bw = min(90, (self.width()-gap*(n-1)) / n)
        total = bw*n + gap*(n-1)
        x0 = (self.width()-total)/2
        bh = 40
        y = (self.height()-bh)/2
        rects = []
        for i in range(n):
            rects.append(QRectF(x0 + i*(bw+gap), y, bw, bh))
        return rects
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        rects = self._geom()
        for i, (label, glyph) in enumerate(self.ITEMS):
            r = rects[i]
            hov = i == self._hover; prs = i == self._press
            bg = QColor(8, 18, 34, 200 if prs else 165)
            p.setPen(Qt.NoPen); p.setBrush(bg)
            p.drawRoundedRect(r, 8, 8)
            col = QColor(THEME["border_hi"]) if (hov or prs) else QColor(THEME["border"])
            p.setPen(QPen(col, 1)); p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, 8, 8)
            fg = QFont(THEME["font"], 11)
            p.setFont(fg)
            p.setPen(QPen(QColor(210,245,255) if (hov or prs) else THEME["text"]))
            icon_rect = QRectF(r.left(), r.top()+2, r.width(), r.height()*0.5)
            p.drawText(icon_rect, Qt.AlignHCenter|Qt.AlignVCenter, glyph)
            fl = QFont(THEME["font"], 6); fl.setLetterSpacing(QFont.AbsoluteSpacing, 1)
            p.setFont(fl); p.setPen(QPen(THEME["text_dim"]))
            label_rect = QRectF(r.left(), r.top()+r.height()*0.5, r.width(), r.height()*0.5)
            p.drawText(label_rect, Qt.AlignHCenter|Qt.AlignVCenter, label)
    def mouseMoveEvent(self, e):
        for i, r in enumerate(self._geom()):
            if r.contains(e.pos()):
                if self._hover != i: self._hover = i; self.update()
                return
        if self._hover != -1: self._hover = -1; self.update()
    def leaveEvent(self, e):
        self._hover = -1; self.update()
    def mousePressEvent(self, e):
        for i, r in enumerate(self._geom()):
            if r.contains(e.pos()): self._press = i; self.update(); return
    def mouseReleaseEvent(self, e):
        idx = self._press; self._press = -1; self.update()
        if idx < 0: return
        for i, r in enumerate(self._geom()):
            if r.contains(e.pos()) and i == idx:
                self.actionRequested.emit(self.ITEMS[i][0]); return
BRACKETS = ("corner brackets geometry helper",)
def bracket_rects(cx, cy, R, grow):
    off = R*1.28 + grow
    L = R*0.42
    return (cx-off, cy-off, L, off+L, off-L)  # half-extent based
class JarvisOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._t = 0.0
        self._pulse = 0.0            # smoothed SPEAKING energy
        self._act   = 0.0            # smoothed activity energy (listening/thinking/processing)
        self._lvl_hist = [0.0]*48    # real mic amplitude ring
        self._speak_file = TempDirectoryPath("Speaking.data")
        rng = random.Random(7)
        self._particles = [{
            "radius": rng.uniform(0.42, 1.25),
            "phase": rng.uniform(0, math.tau),
            "speed": rng.uniform(0.0025, 0.012)*(1 if rng.random() < 0.5 else -1),
            "drift": rng.uniform(0.0, 0.06),
            "size": rng.uniform(1.0, 2.8),
            "alpha": rng.uniform(90, 200),
            "twk": rng.uniform(0.05, 0.12),      # twinkle rate (PART 14)
        } for _ in range(46)]
        self._rng = rng
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000/CFG["orb_fps"]))
    def _params(self):
        st = gui_state()
        lvl = gui_level()
        self._lvl_hist.pop(0); self._lvl_hist.append(lvl)
        target_pulse = 1.0 if st == GS.SPEAKING else 0.0
        target_act = {"LISTENING": 0.35 + 0.65*lvl, "THINKING": 0.75,
                      "PROCESSING": 0.9, "ERROR": 1.0}.get(st, 0.0)
        self._pulse += (target_pulse - self._pulse) * (0.10 if target_pulse else 0.05)
        self._act   += (target_act   - self._act)   * 0.08
        color = {
            GS.STANDBY:    (120, 160, 255),
            GS.LISTENING:  (0, 255, 190),
            GS.THINKING:   (0, 170, 255),
            GS.PROCESSING: (255, 200, 90),
            GS.SPEAKING:   (0, 195, 255),
            GS.ERROR:      (255, 90, 90),
        }[st]
        speed = {"STANDBY": 1.0, "LISTENING": 1.5, "THINKING": 2.1,
                 "PROCESSING": 2.6, "SPEAKING": 1.8, "ERROR": 2.2}[st]
        return st, color, speed, self._pulse, self._act, lvl
    def _tick(self):
        self._t += 1
        speak = _read_file(self._speak_file).strip().lower() in ("true","1","yes")
        if speak and gui_state() != GS.SPEAKING:
            set_gui_state(GS.SPEAKING)
        self.update()   # repaint (params computed in paint to stay consistent)
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        cx, cy = w/2, h/2
        t = self._t
        st, (cr,cg,cb), spd, pulse, act, lvl = self._params()
        base_r = min(w,h)*0.33
        R = base_r                                    # FIXED radius — no scale animation
        energy = 1.0 + 0.45*pulse + 0.35*act
        self._draw_outer_glow(p, cx, cy, R, energy, cr,cg,cb)
        self._draw_particles(p, cx, cy, R, t, cr,cg,cb, act)
        self._draw_waveform_ring(p, cx, cy, R, t, st, cr,cg,cb)
        self._draw_rings(p, cx, cy, R, t, energy, spd, cr,cg,cb)
        self._draw_arcs(p, cx, cy, R, t, spd, act)
        self._draw_electric(p, cx, cy, R, t, energy)
        self._draw_brackets(p, cx, cy, R, st, act)
        self._draw_core(p, cx, cy, R, energy, st, cr,cg,cb)
        p.end()
    def _draw_outer_glow(self, p, cx, cy, R, energy, cr,cg,cb):
        max_r = min(cx, cy)*0.99
        for i in range(8):
            a = int(22*energy) - i*3
            if a <= 0: break
            gr = min(R*(1.0+i*0.30), max_r)
            if gr <= R: break
            g = QRadialGradient(cx, cy, gr)
            g.setColorAt(0.0, QColor(cr, cg, cb, a))
            g.setColorAt(0.6, QColor(cr//2, cg//2, cb, int(a*0.4)))
            g.setColorAt(1.0, QColor(0, 60, 200, 0))
            p.setPen(Qt.NoPen); p.setBrush(g)
            p.drawEllipse(QPointF(cx,cy), gr, gr)
    def _draw_particles(self, p, cx, cy, R, t, cr,cg,cb, act):
        max_r = min(cx,cy)*0.99
        boost = 1.0 + act*0.8
        for q in self._particles:
            ang = q["phase"] + t*q["speed"]*(1.0+act*0.9)
            rr = min(q["radius"] + q["drift"]*math.sin(t*q["twk"]+q["phase"]), max_r/R)
            x = cx + math.cos(ang)*R*rr
            y = cy + math.sin(ang)*R*rr
            a = int(q["alpha"]*(0.6+0.4*math.sin(t*q["twk"]+q["phase"]))*boost)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(min(255,cr//2+120), min(255,cg), min(255,cb), max(0,min(255,a))))
            sz = q["size"]*(1+0.4*act)
            p.drawEllipse(QPointF(x,y), sz, sz)
    def _draw_waveform_ring(self, p, cx, cy, R, t, st, cr,cg,cb):
        rr = R*1.36
        n = len(self._lvl_hist)
        if st == GS.PROCESSING:
            pen = QPen(QColor(cr,cg,cb,170), 1.6, Qt.DashLine)
            pen.setDashOffset(-time.time()*40)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx,cy), rr, rr)
            return
        amp = 0.0
        if st == GS.LISTENING:
            amp = max(self._lvl_hist)          # live mic amplitude
        elif st == GS.SPEAKING:
            amp = 0.25 + 0.35*self._pulse      # state-driven envelope
        pts = []
        for i in range(n):
            a = -math.pi/2 + math.tau*i/n
            v = self._lvl_hist[i] if st == GS.LISTENING else 0.0
            wob = (v*0.5 + (abs(math.sin(i*0.7+t*0.11))*0.02 if st==GS.SPEAKING else 0.004))
            rad = rr*(1+wob*(0.5+amp*2))
            pts.append(QPointF(cx+math.cos(a)*rad, cy+math.sin(a)*rad))
        poly = QPolygonF(pts)
        p.setPen(QPen(QColor(min(255,cr//2+120), cg, cb, 190), 1.3))
        p.setBrush(QColor(cr//6, cg//4, cb//2, 26))
        p.drawPolygon(poly)
    def _draw_rings(self, p, cx, cy, R, t, energy, spd, cr,cg,cb):
        rings = [                                   # PART 15 — multi-speed layers
            (0.72, 1.6,  0.010*spd, 150),
            (0.86, 1.1, -0.006*spd, 110),
            (0.96, 0.8,  0.004*spd*1.6, 80),
            (1.06, 1.3, -0.012*spd, 130),
            (1.18, 0.7,  0.007*spd, 70),
        ]
        for radius, width, speed, alpha in rings:
            rr = R*radius
            p.setPen(QPen(QColor(cr, min(255,cg), min(255,cb), int(alpha*energy)), max(0.6, width)))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx,cy), rr, rr)
            self._draw_ticks(p, cx, cy, rr, t, speed, alpha)
    def _draw_ticks(self, p, cx, cy, rr, t, speed, alpha):
        rot = t*speed*6
        count = 36
        p.setPen(QPen(QColor(120,220,255,int(alpha*0.8)), 1.0))
        for i in range(count):
            a = rot + i*(math.tau/count)
            inner = rr*0.93
            outer = rr*(0.99 if i % 3 else 1.06)
            p.drawLine(QPointF(cx+math.cos(a)*inner, cy+math.sin(a)*inner),
                       QPointF(cx+math.cos(a)*outer, cy+math.sin(a)*outer))
    def _draw_arcs(self, p, cx, cy, R, t, spd, act):
        arcs = [
            (0.90, 70,  0.010*spd, 90),
            (1.00, 120, -0.008*spd, 110),
            (1.12, 55,  0.014*spd, 85),
        ]
        for radius, span, speed, alpha in arcs:
            rr = R*radius
            start = (t*speed*20) % 360
            rect = QRectF(cx-rr, cy-rr, rr*2, rr*2)
            pen = QPen(QColor(0,200,255,alpha), 1.4)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawArc(rect, int(start*16), int(span*16))
        scan_a = (t*0.9) % 360
        rr = R*1.24
        rect = QRectF(cx-rr, cy-rr, rr*2, rr*2)
        pen = QPen(QColor(150,240,255, int(60+120*act)), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, int(scan_a*16), int(26*16))
    def _draw_electric(self, p, cx, cy, R, t, energy):
        strands = [(0.80, 0.014, 1), (1.04, -0.010, -1)]
        rng = self._rng
        for radius, speed, _d in strands:
            rr = R*radius
            start = (t*speed*30) % math.tau
            segments = 14
            pts = []
            for i in range(segments+1):
                a = start + i*(0.35/segments)
                jitter = rng.uniform(-1,1)*0.04
                r = rr + jitter*R*(0.5+0.5*math.sin(t*0.05+i))
                pts.append(QPointF(cx+math.cos(a)*r, cy+math.sin(a)*r))
            pen = QPen(QColor(150,240,255,int(110*energy)), 1.2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            for i in range(len(pts)-1):
                p.drawLine(pts[i], pts[i+1])
    def _draw_brackets(self, p, cx, cy, R, st, act):
        grow = R*0.06*(0.5+0.5*math.sin(time.time()*2.4))*(1+act)
        off = R*1.30 + grow
        L = R*0.34
        col = QColor(0,255,205,170) if st==GS.LISTENING else QColor(0,200,255,120+int(60*act))
        pen = QPen(col, 2); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        for sx, sy in ((-1,-1),(1,-1),(-1,1),(1,1)):
            x, y = cx+sx*off, cy+sy*off
            p.drawLine(QPointF(x, y), QPointF(x - sx*L, y))
            p.drawLine(QPointF(x, y), QPointF(x, y - sy*L))
    def _draw_core(self, p, cx, cy, R, energy, st, cr,cg,cb):
        core_grad = QRadialGradient(QPointF(cx-R*0.35, cy-R*0.35), R*2.2)
        hi = st == GS.SPEAKING
        core_grad.setColorAt(0.0, QColor(190 if hi else 160, 250, 255))
        core_grad.setColorAt(0.4, QColor(min(255,cr+40), cg, cb))
        core_grad.setColorAt(0.8, QColor(cr//3, cg//2, cb))
        core_grad.setColorAt(1.0, QColor(0, 30, 130))
        p.setPen(Qt.NoPen); p.setBrush(core_grad)
        p.drawEllipse(QPointF(cx,cy), R, R)
        inner_grad = QRadialGradient(QPointF(cx-R*0.3, cy-R*0.35), R*1.4)
        inner_grad.setColorAt(0.0, QColor(255,255,255,int(110*energy)))
        inner_grad.setColorAt(0.5, QColor(255,255,255,int(30*energy)))
        inner_grad.setColorAt(1.0, QColor(255,255,255,0))
        p.setBrush(inner_grad)
        p.drawEllipse(QPointF(cx,cy), R*0.92, R*0.92)
        hl = QRadialGradient(QPointF(cx-R*0.35, cy-R*0.45), R*1.1)
        hl.setColorAt(0.0, QColor(255,255,255,int(170*energy)))
        hl.setColorAt(1.0, QColor(255,255,255,0))
        p.setBrush(hl)
        p.drawEllipse(QPointF(cx-R*0.32, cy-R*0.42), R*0.45, R*0.36)
class TranscriptionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.user_text = ""
        self.jarvis_text = ""
        self._pt = QTimer(self); self._pt.timeout.connect(self._poll)
        self._pt.start(250)
    def _poll(self):
        part = gui_partial()
        st = gui_state()
        if st == GS.LISTENING:
            self.user_text = part or "…"
        else:
            self.user_text = ""
        resp = _read_file(TempDirectoryPath("Response.data")).strip()
        if resp and resp != getattr(self, "_resp_seen", None):
            self._resp_seen = resp
            line = resp.splitlines()[0] if resp.splitlines() else ""
            if ":" in line[:24]:
                self.jarvis_text = line.split(":",1)[1].strip()
            else:
                self.jarvis_text = line
        self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        w = self.width()
        f = QFont(THEME["font"], 7); f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        p.setFont(f); p.setPen(QPen(THEME["text_dim"]))
        p.drawText(QRectF(0, 0, w, 12), Qt.AlignHCenter, "VOICE INPUT")
        fm = p.fontMetrics()
        f1 = QFont(THEME["font"], 10)
        p.setFont(f1); p.setPen(QPen(QColor(235,250,255)))
        if self.user_text:
            el = fm.elidedText(f"{UserName}: \u201c{self.user_text}\u201d", Qt.ElideRight, w-20)
            p.drawText(QRectF(10, 16, w-20, 22), Qt.AlignHCenter|Qt.AlignVCenter, el)
        if self.jarvis_text:
            f2 = QFont(THEME["font"], 8); p.setFont(f2)
            p.setPen(QPen(THEME["accent"]))
            jel = fm.elidedText(f"{AssistantName}: “{self.jarvis_text}”",
                                Qt.ElideRight, w-20)
            p.drawText(QRectF(10, 40, w-20, 18), Qt.AlignHCenter|Qt.AlignVCenter, jel)
class InitalScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._t = 0.0
        self._wave = [0.0]*32
        self._mic_last_toggle = 0.0
        self._streams = []                      # PART 16 data streams tokens
        rng = random.Random(3)
        tokens = ["0100101","AI_CORE","SYS_07","NEURAL","PROCESS","0x7FA3","JARVIS",
                  "LINK_OK","QBIT","SYNC_88","0x21C4","CORE_TEMP","GRID","PULSE"]
        for i in range(9):
            self._streams.append({
                "txt": rng.choice(tokens), "x": rng.random(), "y": rng.random(),
                "vx": rng.uniform(-0.004,0.004), "vy": rng.uniform(-0.002,0.002),
                "a": rng.randint(18, 34)})
        self._scan_y = 0.0
        self.orb = JarvisOrb(self)
        self.feed = ActivityFeed(self)
        self.history = CommandHistory(self)
        self.telemetry = TelemetryPanel(self)
        self.netgraph = NetGraph(self)
        self.neural = NeuralViz(self)
        self.clock = ClockHUD(self)
        self.transcript = TranscriptionView(self)
        self.quick = QuickActions(self)
        self.quick.actionRequested.connect(self._quick_action)
        self.label = QLabel("")
        self.label.setStyleSheet("color:#c6ecff; font-size:13px; background:transparent;")
        self.label.setAlignment(Qt.AlignCenter)
        self.toggled = True
        self.mic_btn = MicButton(self)
        self.mic_btn.clicked.connect(self.toggle_icon)
        self.mic_btn.set_active(True)
        MicButtonInitialed()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000/CFG["orb_fps"]))
        WIN.watch.stateChanged.connect(self._on_state)
        WIN.telem.tick.connect(self._on_telem)
        WIN.watch.taskChanged.connect(self._on_task)
    def resizeEvent(self, e):
        w, h = self.width(), self.height()
        m = 10
        col_w = max(196, min(272, int(w*0.175)))
        top = 8; bot = h-96
        col_h = bot - top
        left_w = right_w = col_w
        self.feed.setGeometry(m, top, left_w, int(col_h*0.46))
        self.history.setGeometry(m, top+self.feed.height()+8, left_w, col_h-self.feed.height()-8)
        th = int(col_h*0.40); nh = int(col_h*0.30); nnh = col_h-th-nh-16
        self.telemetry.setGeometry(w-m-right_w, top, right_w, th)
        self.netgraph.setGeometry(w-m-right_w, top+th+8, right_w, nh)
        self.neural.setGeometry(w-m-right_w, top+th+nh+16, right_w, max(84,nnh))
        cw = min(240, int(w*0.22))
        self.clock.setGeometry(w - m - right_w - cw - 10, 6, cw, 44)
        orb_w = int(min(w*0.42, h*0.52))
        tx = (w-orb_w)//2
        self.transcript.setGeometry(tx, int(h*0.665), orb_w, 62)
        self.quick.setGeometry(0, h-96, w, 50)
        self._position_mic_icon()
        osz = int(min(w,h)*0.62)
        self.orb.setGeometry((w-osz)//2, int(h*0.075), osz, osz)
        super().resizeEvent(e)
    def _tick(self):
        self._t += 1
        st = gui_state()
        lvl = gui_level() if st == GS.LISTENING else 0.0
        self._wave.pop(0); self._wave.append(lvl if st == GS.LISTENING
                                             else abs(math.sin(self._t*0.05))*0.03)
        for s in self._streams:
            s["x"] = (s["x"] + s["vx"]) % 1.0
            s["y"] = (s["y"] + s["vy"]) % 1.0
        self._scan_y = (self._t * 0.9) % (self.height()+140) - 70
        self.orb._tick()  # shared clock keeps one repaint cadence
        self.neural.set_energy({"STANDBY":0.12,"LISTENING":0.5,"THINKING":0.8,
                                "PROCESSING":0.95,"SPEAKING":0.7,"ERROR":1.0}[st])
        if hasattr(self, "mic_btn"):
            self.mic_btn._state = st
            self.mic_btn._tick()
        self.update()
        self.label.setText(_read_file(TempDirectoryPath("Status.data")).strip() or "Available...")
    @staticmethod
    def _feed():
        w = globals().get("WIN")
        return getattr(w, "feed", None) if w else None
    def _on_state(self, old, new):
        feed = self._feed()
        MAP = {
            GS.LISTENING:  ("listen", "Listening…"),
            GS.THINKING:   ("think",  "Processing request…"),
            GS.PROCESSING: ("proc",   "Executing automation…"),
            GS.SPEAKING:   ("info",   "Responding…"),
            GS.STANDBY:    ("done",   "Standby"),
            GS.ERROR:      ("err",    "Error state"),
        }
        if feed: feed.push(*MAP[new])
    def _on_task(self, task):
        feed = self._feed()
        if task:
            if feed: feed.push("proc", f"Task: {task}")
    def _on_telem(self, d):
        self.telemetry.update_stats(d)
        self.netgraph.update_stats(d)
        self.neural.update_stats(d)
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        self._draw_grid(p, w, h)
        self._draw_light_leaks(p, w, h)
        self._draw_data_streams(p, w, h)
        self._draw_scanlines(p, w, h)
    def _draw_grid(self, p, w, h):
        p.setPen(QPen(QColor(0, 150, 220, 14), 1))
        step = 46
        y = 0
        while y < h:
            p.drawLine(0, y, w, y); y += step
        x = 0
        while x < w:
            p.drawLine(x, 0, x, h); x += step
    def _draw_light_leaks(self, p, w, h):
        g1 = QRadialGradient(QPointF(w*0.15, h*0.2), w*0.5)
        g1.setColorAt(0, QColor(0, 120, 255, 22)); g1.setColorAt(1, QColor(0,0,0,0))
        p.setPen(Qt.NoPen); p.setBrush(g1)
        p.drawRect(0, 0, w, h)
        g2 = QRadialGradient(QPointF(w*0.85, h*0.8), w*0.5)
        g2.setColorAt(0, QColor(0, 200, 255, 18)); g2.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(g2); p.drawRect(0, 0, w, h)
    def _draw_data_streams(self, p, w, h):
        f = QFont("monospace", 7); p.setFont(f)
        for s in self._streams:
            p.setPen(QPen(QColor(120, 220, 255, s["a"])))
            p.drawText(QPointF(s["x"]*w, s["y"]*h), s["txt"])
    def _draw_scanlines(self, p, w, h):
        y = self._scan_y
        g = QLinearGradient(0, y-60, 0, y+60)
        g.setColorAt(0, QColor(0,220,255,0))
        g.setColorAt(0.5, QColor(0,220,255,16))
        g.setColorAt(1, QColor(0,220,255,0))
        p.setPen(Qt.NoPen); p.setBrush(g)
        p.drawRect(QRectF(0, y-60, w, 120))
        p.setPen(QPen(QColor(0,180,255,8), 1))
        yy = 0
        while yy < h:
            p.drawLine(0, yy, w, yy); yy += 4
    def mousePressEvent(self, event):
        pos = event.pos()
        og = self.orb.geometry()
        if og.contains(pos):
            now = time.time()
            if now - self._mic_last_toggle > 0.35:
                self._mic_last_toggle = now
                self.toggle_icon()
            return
        super().mousePressEvent(event)
    def _position_mic_icon(self):
        btn = getattr(self, "mic_btn", None)
        if btn is not None:
            btn.move(int(self.width()/2) - 45, self.height() - 200)
    def toggle_icon(self, event=None):
        self.toggled = not self.toggled
        self.mic_btn.set_active(self.toggled)
        if self.toggled:
            MicButtonInitialed()
        else:
            MicButtonClosed()
    def _quick_action(self, name):
        threading.Thread(target=self._run_action, args=(name,), daemon=True).start()
    def _run_action(self, name):
        feed = self._feed()
        try:
            if name == "MIC":
                QMetaObject.invokeMethod(self, "toggle_icon_queued")
            elif name == "SEARCH":
                webbrowser.open("https://www.google.com")
                if feed: feed.push("web", "Searching Google…")
            elif name == "MUSIC":
                from Backend.agents.tools import media_tools
                r = media_tools.play()
                if not r.get("ok"):
                    music_dir = os.path.expanduser("~/Music")
                    if os.path.isdir(music_dir):
                        subprocess.Popen(["xdg-open", music_dir])
                        if feed: feed.push("info", "Opened Music folder")
                    else:
                        if feed: feed.push("err", "No music found")
                else:
                    if feed: feed.push("info", r.get("message", "Music"))
            elif name == "SCREENSHOT":
                subprocess.Popen(["xfce4-screenshooter"])
                if feed: feed.push("info", "Screenshot app opened")
            elif name == "FILES":
                from Backend.agents.tools import linux_tools
                r = linux_tools.open_app("file_manager")
                if not r.get("ok"):
                    subprocess.Popen(["xdg-open", os.path.expanduser("~")])
                    if feed: feed.push("info", "Opened Home folder")
                else:
                    if feed: feed.push("info", r.get("message", "Files"))
            elif name == "SETTINGS":
                QMetaObject.invokeMethod(WIN, "show_settings", Qt.QueuedConnection)
        except Exception as ex:
            if feed: feed.push("err", f"{name}: {ex}")
    @pyqtSlot()
    def toggle_icon_queued(self):
        self.toggle_icon()
    @pyqtSlot()
    def do_screenshot(self):
        feed = self._feed()
        outdir = os.path.expanduser("~/Pictures/Screenshots")
        try:
            os.makedirs(outdir, exist_ok=True)
            path = os.path.join(outdir, time.strftime("shot_%Y%m%d_%H%M%S.png"))
            pm = QApplication.primaryScreen().grabWindow(0)
            if not pm.isNull() and pm.save(path, "PNG"):
                self._shot_ok(path, feed); return
            from shutil import which
            for cmd in (["scrot", "-o", path],
                        ["gnome-screenshot", "-f", path],
                        ["spectacle", "-b", "-n", "-o", path],
                        ["import", "-window", "root", path]):
                if which(cmd[0]):
                    r = subprocess.run(cmd, timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0:
                        self._shot_ok(path, feed); return
            raise RuntimeError("no capture backend available in this session")
        except Exception as ex:
            if feed: feed.push("err", "Screenshot failed")
    @staticmethod
    def _shot_ok(path, feed):
        if feed: feed.push("done", "Screenshot saved")
def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
class ChatSection(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        hdr = QWidget()
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            "background:rgba(8,16,30,240);"
            "border-bottom:1px solid rgba(0,170,255,40);")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)
        name = QLabel(str(AssistantName).upper() + " AI")
        name.setFont(QFont(THEME["font"], 10, QFont.DemiBold))
        name.setStyleSheet("color:#c6ecff; background:transparent;")
        hl.addWidget(name)
        hl.addStretch(1)
        self._dot = QLabel("\u25cf")
        self._dot.setFont(QFont(THEME["font"], 8))
        self._dot.setStyleSheet("color:#3ce6a0; background:transparent;")
        hl.addWidget(self._dot)
        self._st = QLabel("Online")
        self._st.setFont(QFont(THEME["font"], 9))
        self._st.setStyleSheet("color:#7cb8d8; background:transparent;")
        hl.addWidget(self._st)
        root.addWidget(hdr)
        self.messages = QTextBrowser()
        self.messages.setOpenExternalLinks(False)
        self.messages.setFrameShape(QFrame.NoFrame)
        self.messages.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.messages.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.messages.setStyleSheet("QTextBrowser{background:transparent; color:#d0f0ff; border:none;"
                                    "font-size:13px; padding:8px;}"
                                    "QScrollBar:vertical{background:rgba(6,14,26,200); width:6px;}"
                                    "QScrollBar::handle:vertical{background:rgba(0,170,255,80); border-radius:3px; min-height:30px;}"
                                    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0;}")
        self.messages.setFont(QFont(THEME["font"], 13))
        root.addWidget(self.messages, 1)
        self._think_lbl = QLabel("")
        self._think_lbl.setFont(QFont(THEME["font"], 12))
        self._think_lbl.setStyleSheet("color:#5a9cbf; background:transparent; padding:8px 20px;")
        self._think_lbl.hide()
        root.addWidget(self._think_lbl)
        self._think_dots = 0
        self._think_timer = QTimer(self)
        self._think_timer.timeout.connect(self._animate_think)
        self._think_timer.start(400)
        input_bar = QWidget()
        input_bar.setFixedHeight(56)
        input_bar.setStyleSheet(
            "background:rgba(8,16,30,240);"
            "border-top:1px solid rgba(0,170,255,40);")
        il = QHBoxLayout(input_bar)
        il.setContentsMargins(12, 8, 12, 8)
        il.setSpacing(8)
        self._mic_btn = QPushButton("\U0001f3a4")
        self._mic_btn.setFixedSize(36, 36)
        self._mic_btn.setCursor(Qt.PointingHandCursor)
        self._mic_btn.setStyleSheet("QPushButton{background:rgba(6,14,26,200); color:#9fe8ff; border:1px solid rgba(0,170,255,60);"
                                    "border-radius:18px; font-size:14px;}"
                                    "QPushButton:hover{background:rgba(0,90,160,120);}")
        self._mic_btn.clicked.connect(self._toggle_mic)
        il.addWidget(self._mic_btn)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.setFont(QFont(THEME["font"], 13))
        self.input_field.setStyleSheet("QLineEdit{background:rgba(6,14,26,220); color:#d0f0ff; border:1px solid rgba(0,170,255,60);"
                                       "border-radius:18px; padding:6px 12px; font-size:13px;}"
                                       "QLineEdit:focus{border-color:rgba(0,220,255,160);}")
        self.input_field.returnPressed.connect(self._send)
        il.addWidget(self.input_field, 1)
        self._send_btn = QPushButton("\u27a4")
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet("QPushButton{background:rgba(0,170,255,80); color:#fff; border:none;"
                                     "border-radius:18px; font-size:14px; font-weight:bold;}"
                                     "QPushButton:hover{background:rgba(0,220,255,120);}")
        self._send_btn.clicked.connect(self._send)
        il.addWidget(self._send_btn)
        root.addWidget(input_bar)
        self._last_response = ""
        self._show_empty()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.timeout.connect(self._update_status)
        self._poll_timer.start(CFG["chat_ms"])
    def _show_empty(self):
        self.messages.setHtml(
            '<div style="text-align:center; padding-top:120px; color:#3d6a85;">'
            f'<div style="font-size:24px; color:rgba(0,180,255,80); margin-bottom:12px;">\u25cf</div>'
            f'<div style="font-size:16px; color:#7cb8d8; margin-bottom:4px;">'
            f'{str(AssistantName)}</div>'
            '<div style="font-size:14px; color:#5a7a90;">How can I help you?</div>'
            '</div>')
    def _add_user(self, text):
        ts = time.strftime("%H:%M")
        html = (
            f'<div style="text-align:right; margin:10px 0;">'
            f'<div style="color:#5a9cbf; font-size:10px; margin-bottom:2px;">'
            f'{str(UserName).upper()} &nbsp; {ts}</div>'
            f'<div style="display:inline-block; text-align:left; '
            f'background:rgba(0,120,200,25); '
            f'border:1px solid rgba(0,170,255,35); '
            f'border-radius:12px 12px 2px 12px; '
            f'padding:10px 14px; max-width:70%;">'
            f'<span style="color:#d0e0f0;">{_esc(text)}</span>'
            f'</div></div>'
        )
        if self._last_response == "" and not self.messages.toPlainText().strip():
            self.messages.clear()
        self.messages.append(html)
        sb = self.messages.verticalScrollBar()
        sb.setValue(sb.maximum())
    def _add_jarvis(self, text):
        ts = time.strftime("%H:%M")
        body = _esc(text)
        if any(k in text for k in ["$ ", "```", "import ", "def ", "class "]):
            body = (f'<pre style="color:#9fe8ff; font-family:\'DejaVu Sans Mono\'; '
                    f'font-size:12px; margin:0; white-space:pre-wrap;">{body}</pre>')
        else:
            body = f'<span style="color:#d0e0f0;">{body}</span>'
        html = (
            f'<div style="text-align:left; margin:10px 0;">'
            f'<div style="color:#00c3ff; font-size:10px; margin-bottom:2px;">'
            f'{str(AssistantName).upper()} &nbsp; {ts}</div>'
            f'<div style="display:inline-block; text-align:left; '
            f'background:rgba(0,80,140,18); '
            f'border-left:2px solid rgba(0,170,255,60); '
            f'border-radius:2px 12px 12px 12px; '
            f'padding:10px 14px; max-width:70%;">'
            f'{body}'
            f'</div></div>'
        )
        if self._last_response == "" and not self.messages.toPlainText().strip():
            self.messages.clear()
        self.messages.append(html)
        sb = self.messages.verticalScrollBar()
        sb.setValue(sb.maximum())
    def _send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self._add_user(text)
        self._think_lbl.setText(f"{str(AssistantName).upper()} is thinking...")
        self._think_lbl.show()
        try:
            with open(os.path.join(TempDirPath, "Query.data"), "w",
                       encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
    def _send_from_main(self, text):
        if text and text.strip():
            self._add_user(text.strip())
            self._think_lbl.setText(f"{str(AssistantName).upper()} is thinking...")
            self._think_lbl.show()
    def _poll(self):
        vq = _read_file(TempDirectoryPath("VoiceQuery.data"))
        if vq and vq.strip():
            try:
                with open(TempDirectoryPath("VoiceQuery.data"), "w") as f:
                    f.write("")
            except Exception:
                pass
            self._add_user(vq.strip())
            self._think_lbl.setText(f"{str(AssistantName).upper()} is thinking...")
            self._think_lbl.show()
        msg = _read_file(TempDirectoryPath("Response.data"))
        if msg and msg.strip() and msg.strip() != self._last_response:
            self._last_response = msg.strip()
            self._think_lbl.hide()
            self._add_jarvis(self._last_response)
    def _animate_think(self):
        if self._think_lbl.isVisible():
            self._think_dots = (self._think_dots + 1) % 4
            dots = "." * self._think_dots
            self._think_lbl.setText(
                f"{str(AssistantName).upper()} is thinking{dots}")
    def _update_status(self):
        try:
            st = gui_state()
            colors = {
                "STANDBY": "#3ce6a0", "LISTENING": "#00ffc8",
                "THINKING": "#78a0ff", "PROCESSING": "#ffc85a",
                "SPEAKING": "#00c3ff", "ERROR": "#ff5252",
            }
            labels = {
                "STANDBY": "Online", "LISTENING": "Listening",
                "THINKING": "Thinking", "PROCESSING": "Processing",
                "SPEAKING": "Speaking", "ERROR": "Error",
            }
            c = colors.get(st, "#3ce6a0")
            l = labels.get(st, "Online")
            self._dot.setStyleSheet(f"color:{c}; background:transparent;")
            self._st.setText(l)
            self._st.setStyleSheet(f"color:{c}; background:transparent;")
        except Exception:
            pass
    def _toggle_mic(self):
        try:
            cur = GetMicrophoneStatus().strip().lower()
            if cur == "true":
                SetMicrophoneStatus("False")
                self._mic_btn.setStyleSheet("QPushButton{background:rgba(6,14,26,200); color:#9fe8ff; border:1px solid rgba(0,170,255,60);"
                                            "border-radius:18px; font-size:14px;}"
                                            "QPushButton:hover{background:rgba(0,90,160,120);}")
            else:
                SetMicrophoneStatus("True")
                self._mic_btn.setStyleSheet("QPushButton{background:rgba(0,170,255,80); color:#fff; border:1px solid rgba(0,220,255,120);"
                                            "border-radius:18px; font-size:14px;}"
                                            "QPushButton:hover{background:rgba(0,220,255,120);}")
        except Exception:
            pass
    def _clear(self):
        self.messages.clear()
        self._last_response = ""
        self._show_empty()
        try:
            with open(TempDirectoryPath("Response.data"), "w") as f:
                f.write("")
        except Exception:
            pass
class TerminalScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 12, 12, 12)
        self.view = QPlainTextEdit(); self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(2000)
        self.view.setStyleSheet("QPlainTextEdit{background:rgba(6,14,26,220); color:#9fe8ff; border:1px solid rgba(0,170,255,40);"
                                "border-radius:4px; padding:8px; font-size:11px; font-family:'DejaVu Sans Mono';}"
                                "QScrollBar:vertical{background:rgba(6,14,26,200); width:6px;}"
                                "QScrollBar::handle:vertical{background:rgba(0,170,255,80); border-radius:3px; min-height:30px;}")
        row = QHBoxLayout()
        btn = QPushButton("CLEAR"); btn.setFixedSize(90, 26)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("QPushButton{background:rgba(8,20,36,200); color:#9fe8ff; border:1px solid rgba(0,170,255,90);"
                          "border-radius:5px; font-size:11px;}"
                          "QPushButton:hover{background:rgba(0,90,160,140);}")
        btn.clicked.connect(self.clear_log)
        row.addStretch(1); row.addWidget(btn)
        lay.addWidget(self.view); lay.addLayout(row)
        self.log_path = os.path.join(current_dir, "Frontend", "Files", "Terminal.log")
        self._pos = 0
        self._t = QTimer(self); self._t.timeout.connect(self.tail_log)
        self._t.start(CFG["terminal_ms"])
    def tail_log(self):
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
        except Exception:
            return
        if chunk:
            sb = self.view.verticalScrollBar()
            stick = sb.value() >= sb.maximum() - 4
            self.view.insertPlainText(chunk)
            if stick: sb.setValue(sb.maximum())
    def clear_log(self):
        try: open(self.log_path, "w").close()
        except Exception: pass
        self._pos = 0; self.view.clear()
class MessageScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(ChatSection())
        self.setLayout(layout)
        self.setStyleSheet("background-color: black;")
class CustomTopBar(QWidget):
    def __init__(self, parent, stacked_widget):
        super().__init__(parent)
        self.parent_window = parent
        self.stacked_widget = stacked_widget
        self.dragging = False
        self.is_maximized = False
        self.draggable = True
        self.setFixedHeight(40)
        self.initUI()
    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0); layout.setSpacing(8)
        title_label = QLabel(f"{str(AssistantName).upper()} · COMMAND CENTER")
        f = QFont(THEME["font"], 10, QFont.DemiBold); f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        title_label.setFont(f)
        title_label.setStyleSheet("color:#c6ecff; background:transparent;")
        layout.addWidget(title_label); layout.addStretch(1)
        nav = QHBoxLayout(); nav.setSpacing(6)
        for label, icon, idx in (("Home","Home.png",0),("Chats","Chats.png",1),("Terminal","Chats.png",2)):
            b = QPushButton(" " + label)
            if os.path.exists(GraphicsDirectoryPath(icon)):
                b.setIcon(QIcon(GraphicsDirectoryPath(icon)))
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(self.get_button_style())
            b.clicked.connect(lambda _, i=idx: self.stacked_widget.setCurrentIndex(i))
            nav.addWidget(b)
        layout.addLayout(nav); layout.addStretch(1)
        ctrl = QHBoxLayout(); ctrl.setSpacing(0)
        for txt, fn, typ in (("─", self.minimizeWindow, "default"),
                             ("□", self.maximizeWindow, "default"),
                             ("×", self.closeWindow, "close")):
            b = QPushButton(txt); b.setFixedSize(45, 30)
            b.setStyleSheet(self.get_control_button_style(typ))
            b.clicked.connect(fn); ctrl.addWidget(b)
            if txt == "□": self.maximize_button = b
        layout.addLayout(ctrl)
        self.setStyleSheet("CustomTopBar{background-color:rgba(6,12,22,235);"
                           "border-bottom:1px solid rgba(0,170,255,60);} ")
    def get_button_style(self):
        return ("QPushButton{background:rgba(6,14,26,200); color:#9fe8ff; border:1px solid rgba(0,170,255,60);"
                "border-radius:4px; padding:6px 12px; font-size:11px; text-align:left;}"
                "QPushButton:hover{background:rgba(0,90,160,120); border-color:rgba(0,220,255,100);}"
                "QPushButton:pressed{background:rgba(0,130,200,140);}")
    def get_control_button_style(self, button_type="default"):
        base = ("QPushButton{background:transparent; color:#9fe8ff; border:none;"
                "font-size:14px; font-weight:bold; border-radius:0px;}"
                "QPushButton:hover{background:rgba(255,255,255,25);}"
                "QPushButton:pressed{background:rgba(255,255,255,55);}")
        if button_type == "close":
            hover = "QPushButton:hover{background:#e81123;} QPushButton:pressed{background:#f1707a;}"
        else:
            hover = "QPushButton:hover{background:rgba(255,255,255,25);} QPushButton:pressed{background:rgba(255,255,255,55);}"
        return base + hover
    def minimizeWindow(self): self.parent_window.showMinimized()
    def maximizeWindow(self):
        if self.is_maximized:
            self.parent_window.showNormal(); self.maximize_button.setText("□")
        else:
            self.parent_window.showMaximized(); self.maximize_button.setText("❐")
        self.is_maximized = not self.is_maximized
    def closeWindow(self): self.parent_window.close()
    def mousePressEvent(self, event):
        if self.draggable and not self.is_maximized:
            if event.button() == Qt.LeftButton:
                self.dragging = True; self.offset = event.pos()
        elif self.draggable and self.is_maximized and event.button() == Qt.LeftButton:
            self.parent_window.showNormal(); self.maximize_button.setText("□")
            self.is_maximized = False
            ratio = event.pos().x() / self.width()
            new_width = self.parent_window.minimumWidth()
            new_x = int(event.globalPos().x() - (ratio * new_width))
            self.parent_window.move(new_x, 0)
            self.dragging = True
            self.offset = QPoint(int(ratio * new_width), event.pos().y())
    def mouseReleaseEvent(self, event): self.dragging = False
    def mouseMoveEvent(self, event):
        if self.dragging and self.draggable:
            self.parent_window.move(event.globalPos() - self.offset)
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: self.maximizeWindow()
WIN = None   # global handle so panels can reach feed (set in MainWindow)
class SettingsDialog(QDialog):
    _FIELDS = [
        ("USER", [
            ("UserName",      "Your Name",          "text"),
            ("Assistantname", "Assistant Name",      "text"),
        ]),
        ("VOICE", [
            ("AssistantVoice", "Voice",              "combo",
             ["en-US-BrianNeural","en-US-AvaNeural","en-US-AndrewNeural","en-US-EmmaNeural",
              "en-US-JennyNeural","en-US-GuyNeural","en-US-RogerNeural","en-US-SteffanNeural",
              "en-US-ChristopherNeural","en-US-EricNeural","en-US-MichelleNeural",
              "en-US-AriaNeural","en-US-AnaNeural","en-US-AvaMultilingualNeural",
              "en-US-BrianMultilingualNeural","en-US-AndrewMultilingualNeural",
              "en-US-EmmaMultilingualNeural","en-US-SaraNeural","en-US-TonyNeural",
              "en-GB-LibbyNeural","en-GB-MaisieNeural","en-GB-RyanNeural",
              "en-GB-SoniaNeural","en-GB-ThomasNeural",
              "en-CA-ClaraNeural","en-CA-LiamNeural",
              "en-AU-NatashaNeural","en-AU-WilliamMultilingualNeural",
              "en-IN-NeerjaNeural","en-IN-PrabhatNeural","en-IN-NeerjaExpressiveNeural",
              "en-IE-ConnorNeural","en-IE-EmilyNeural",
              "en-SG-LunaNeural","en-SG-WayneNeural",
              "en-ZA-LeahNeural","en-ZA-LukeNeural",
              "en-HK-YanNeural","en-HK-SamNeural",
              "en-PH-JamesNeural","en-PH-RosaNeural",
              "hi-IN-MadhurNeural","hi-IN-SwaraNeural",
              "es-ES-ElviraNeural","es-ES-AlvaroNeural","es-MX-DaliaNeural","es-MX-JorgeNeural",
              "fr-FR-DeniseNeural","fr-FR-HenriNeural","fr-FR-EloiseNeural",
              "fr-CA-SylvieNeural","fr-CA-AntoineNeural","fr-CA-JeanNeural",
              "de-DE-KatjaNeural","de-DE-ConradNeural","de-DE-AmalaNeural","de-DE-KillianNeural",
              "ja-JP-KeitaNeural","ja-JP-NanamiNeural",
              "ko-KR-SunHiNeural","ko-KR-InJoonNeural",
              "zh-CN-XiaoxiaoNeural","zh-CN-YunxiNeural","zh-CN-XiaoyiNeural",
              "pt-BR-FranciscaNeural","pt-BR-AntonioNeural",
              "ru-RU-SvetlanaNeural","ru-RU-DmitryNeural",
              "it-IT-IsabellaNeural","it-IT-DiegoNeural",
              "ar-SA-ZariyahNeural","ar-SA-HamedNeural"]),
            ("Glitch",         "Glitch Effect",      "check"),
        ]),
        ("AI MODELS", [
            ("AI",             "Provider",            "text"),
            ("ChatModel",      "Chat Model",          "text"),
            ("CodeModel",      "Code Model",          "text"),
            ("ModelChain",     "Model Chain",         "text"),
        ]),
        ("KILO GATEWAY", [
            ("KILO_BASE_URL",  "Base URL",            "text"),
            ("KILO_MODEL",     "Kilo Model",          "text"),
            ("KILO_CODE_MODEL","Kilo Code Model",     "text"),
        ]),
        ("SYSTEM", [
            ("N_CTX",          "Context Size",        "text"),
            ("N_THREADS",      "Threads",             "text"),
            ("browse-use_vision","Browser Vision",    "check"),
        ]),
    ]
    _STYLE = """
        QDialog{background:#060c16;}
        QLabel{color:#9fe8ff; font-size:11px; background:transparent;}
        QLineEdit{background:rgba(6,14,26,220); color:#d0f0ff; border:1px solid rgba(0,170,255,60);
            border-radius:4px; padding:4px 8px; font-size:11px; font-family:'DejaVu Sans Mono';}
        QLineEdit:focus{border-color:rgba(0,220,255,160);}
        QComboBox{background:rgba(6,14,26,220); color:#d0f0ff; border:1px solid rgba(0,170,255,60);
            border-radius:4px; padding:4px 8px; font-size:11px; min-height:20px;}
        QComboBox::drop-down{border:none; width:20px;}
        QComboBox::down-arrow{image:none; border-left:4px solid transparent; border-right:4px solid transparent;
            border-top:6px solid #5cc;}
        QComboBox QAbstractItemView{background:#0a1220; color:#d0f0ff; selection-background-color:rgba(0,170,255,80);
            border:1px solid rgba(0,170,255,60);}
        QCheckBox{color:#9fe8ff; font-size:11px; spacing:6px;}
        QCheckBox::indicator{width:14px; height:14px; border:1px solid rgba(0,170,255,80);
            border-radius:3px; background:rgba(6,14,26,220);}
        QCheckBox::indicator:checked{background:rgba(0,195,255,200); border-color:rgba(0,220,255,200);}
        QPushButton{background:rgba(8,20,36,200); color:#9fe8ff; border:1px solid rgba(0,170,255,90);
            border-radius:5px; padding:6px 16px; font-size:11px;}
        QPushButton:hover{background:rgba(0,90,160,140);}
        QPushButton:pressed{background:rgba(0,130,200,160);}
        QScrollArea{border:none; background:transparent;}
        QWidget#scrollContent{background:transparent;}
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS SETTINGS")
        self.setModal(True)
        self.resize(520, 480)
        self.setStyleSheet(self._STYLE)
        self._env_path = os.path.join(current_dir, "jarvis.env")
        self._edited = dict(en_vars)
        self._widgets = {}
        self._build_ui()
    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        hdr = QLabel("SETTINGS")
        hdr.setStyleSheet("color:#0cf; font-size:14px; font-weight:bold; padding:12px 16px;"
                          "border-bottom:1px solid rgba(0,170,255,50); background:rgba(6,12,22,240);")
        hdr.setAlignment(Qt.AlignCenter)
        root.addWidget(hdr)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget(); container.setObjectName("scrollContent")
        lay = QVBoxLayout(container); lay.setContentsMargins(16,12,16,12); lay.setSpacing(6)
        for section, fields in self._FIELDS:
            sh = QLabel(f"  {section}")
            sh.setStyleSheet("color:#5cc; font-size:10px; font-weight:bold; letter-spacing:2px;"
                             "padding:6px 0 2px 0; border-bottom:1px solid rgba(0,170,255,30);")
            lay.addWidget(sh)
            for row in self._make_fields(fields):
                lay.addWidget(row)
            lay.addSpacing(4)
        lay.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)
        foot = QWidget(); foot.setStyleSheet("background:rgba(6,12,22,240);"
                                             "border-top:1px solid rgba(0,170,255,50);")
        fl = QHBoxLayout(foot); fl.setContentsMargins(16,8,16,8)
        env_label = QLabel("jarvis.env")
        env_label.setStyleSheet("color:#567; font-size:9px;")
        fl.addWidget(env_label); fl.addStretch()
        open_btn = QPushButton("Open File")
        open_btn.clicked.connect(lambda: webbrowser.open(f"file://{self._env_path}"))
        save_btn = QPushButton("Save && Restart")
        save_btn.setStyleSheet(save_btn.styleSheet() + "QPushButton{font-weight:bold;}")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        fl.addWidget(open_btn); fl.addWidget(save_btn); fl.addWidget(cancel_btn)
        root.addWidget(foot)
    def _make_fields(self, fields):
        rows = []
        for item in fields:
            key, label = item[0], item[1]
            typ = item[2] if len(item) > 2 else "text"
            row = QHBoxLayout(); row.setContentsMargins(0,2,0,2); row.setSpacing(10)
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(110)
            lbl.setStyleSheet("color:#7ab; font-size:11px;")
            row.addWidget(lbl)
            if typ == "text":
                le = QLineEdit(self._edited.get(key, ""))
                le.setMinimumWidth(200)
                le.textChanged.connect(lambda v, k=key: self._edited.__setitem__(k, v))
                row.addWidget(le, 1)
                self._widgets[key] = le
            elif typ == "combo":
                values = item[3]
                cb = QComboBox()
                cb.addItems(values)
                cur = self._edited.get(key, "")
                idx = cb.findText(cur)
                if idx >= 0: cb.setCurrentIndex(idx)
                cb.currentTextChanged.connect(lambda v, k=key: self._edited.__setitem__(k, v))
                row.addWidget(cb, 1)
                self._widgets[key] = cb
            elif typ == "check":
                cb = QCheckBox()
                cb.setChecked(self._edited.get(key, "").lower() in ("true","1","yes"))
                cb.toggled.connect(lambda v, k=key: self._edited.__setitem__(k, str(v).lower()))
                row.addWidget(cb)
                row.addStretch()
                self._widgets[key] = cb
            rows.append(row)
        result = []
        for item in fields:
            w = QWidget()
        result = []
        for item in fields:
            key, label = item[0], item[1]
            typ = item[2] if len(item) > 2 else "text"
            w = QWidget()
            hl = QHBoxLayout(w); hl.setContentsMargins(0,2,0,2); hl.setSpacing(10)
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(110)
            lbl.setStyleSheet("color:#7ab; font-size:11px;")
            hl.addWidget(lbl)
            if typ == "text":
                le = QLineEdit(self._edited.get(key, ""))
                le.setMinimumWidth(200)
                le.textChanged.connect(lambda v, k=key: self._edited.__setitem__(k, v))
                hl.addWidget(le, 1)
                self._widgets[key] = le
            elif typ == "combo":
                values = item[3]
                cb = QComboBox()
                cb.addItems(values)
                cur = self._edited.get(key, "")
                idx = cb.findText(cur)
                if idx >= 0: cb.setCurrentIndex(idx)
                cb.currentTextChanged.connect(lambda v, k=key: self._edited.__setitem__(k, v))
                hl.addWidget(cb, 1)
                self._widgets[key] = cb
            elif typ == "check":
                cb = QCheckBox()
                cb.setChecked(self._edited.get(key, "").lower() in ("true","1","yes"))
                cb.toggled.connect(lambda v, k=key: self._edited.__setitem__(k, str(v).lower()))
                hl.addWidget(cb)
                hl.addStretch()
                self._widgets[key] = cb
            result.append(w)
        return result
    def _save(self):
        try:
            with open(self._env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []
        out = []
        seen = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                k = stripped.split("=", 1)[0].strip()
                if k in self._edited:
                    out.append(f"{k} = {self._edited[k]}\n")
                    seen.add(k)
                    continue
            out.append(line)
        for k, v in self._edited.items():
            if k not in seen:
                out.append(f"{k} = {v}\n")
        with open(self._env_path, "w", encoding="utf-8") as f:
            f.writelines(out)
        self.accept()
        python = sys.executable
        os.execl(python, python, *sys.argv)
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(980, 640)
        self.initUI()
        self.resize_edge = None; self.resize_start_pos = None
        self.original_size = None; self.original_pos = None
        self.edge_size = 8; self.is_resizing = False
        self.installEventFilter(self)
    def initUI(self):
        global WIN
        WIN = self
        desktop = QApplication.desktop()
        self.resize(int(desktop.screenGeometry().width()*0.8),
                    int(desktop.screenGeometry().height()*0.8))
        self.setStyleSheet("QMainWindow{background-color:#02060d;}"
                           "QWidget#centralWidget{border:1px solid rgba(0,170,255,50);} ")
        self.watch = StateWatcher(); self.watch.start(QThread.LowPriority)
        self.telem = TelemetryWorker(); self.telem.start(QThread.LowPriority)
        central = QWidget(); central.setObjectName("centralWidget")
        central.installEventFilter(self)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        stacked = QStackedWidget(); stacked.installEventFilter(self)
        home = InitalScreen()                 # 0 Home
        stacked.addWidget(home)
        stacked.addWidget(MessageScreen())    # 1 Chats
        stacked.addWidget(TerminalScreen())   # 2 Terminal
        self.home = home
        self.feed = home.feed
        top_bar = CustomTopBar(self, stacked)
        main_layout.addWidget(top_bar); main_layout.addWidget(stacked)
        self.setCentralWidget(central)
        self.stacked = stacked
        self._first_boot_events()
    def _first_boot_events(self):
        QTimer.singleShot(1400, lambda: self.feed.push("done", "Command center initialized"))
    @pyqtSlot()
    def show_settings(self):
        SettingsDialog(self).exec_()
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            if self.is_resizing:
                self.handle_resize(event.globalPos()); return True
            self.update_cursor(event.pos())
        elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self.resize_edge = self.get_resize_edge(event.pos())
            if self.resize_edge:
                self.is_resizing = True
                self.resize_start_pos = event.globalPos()
                self.original_size = self.size(); self.original_pos = self.pos()
                return True
        elif event.type() == QEvent.MouseButtonRelease:
            if self.is_resizing:
                self.is_resizing = False; self.resize_edge = None
                self.resize_start_pos = None; self.original_size = None
                self.original_pos = None; self.update_cursor(event.pos())
                return True
        return super().eventFilter(obj, event)
    def handle_resize(self, global_pos):
        if self.resize_edge and self.resize_start_pos:
            delta = global_pos - self.resize_start_pos
            g = self.geometry()
            mw, mh = self.minimumWidth(), self.minimumHeight()
            if 'top' in self.resize_edge:
                nh = max(mh, self.original_size.height()-delta.y())
                if nh == mh and delta.y() > 0: return
                g.setTop(self.original_pos.y()+self.original_size.height()-nh)
            if 'bottom' in self.resize_edge:
                g.setHeight(max(mh, self.original_size.height()+delta.y()))
            if 'left' in self.resize_edge:
                nw = max(mw, self.original_size.width()-delta.x())
                if nw == mw and delta.x() > 0: return
                g.setLeft(self.original_pos.x()+self.original_size.width()-nw)
            if 'right' in self.resize_edge:
                g.setWidth(max(mw, self.original_size.width()+delta.x()))
            self.setGeometry(g)
    def get_resize_edge(self, pos):
        rect = self.geometry(); x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height(); e = self.edge_size
        if x <= e:
            if y <= e: return 'topleft'
            elif h-e <= y <= h: return 'bottomleft'
        elif w-e <= x <= w:
            if y <= e: return 'topright'
            elif h-e <= y <= h: return 'bottomright'
        if y <= e: return 'top'
        elif h-e <= y <= h: return 'bottom'
        elif x <= e: return 'left'
        elif w-e <= x <= w: return 'right'
        return None
    def update_cursor(self, pos):
        if self.is_resizing: return
        edge = self.get_resize_edge(pos)
        cur = {'topleft': Qt.SizeFDiagCursor, 'bottomright': Qt.SizeFDiagCursor,
               'topright': Qt.SizeBDiagCursor, 'bottomleft': Qt.SizeBDiagCursor,
               'top': Qt.SizeVerCursor, 'bottom': Qt.SizeVerCursor,
               'left': Qt.SizeHorCursor, 'right': Qt.SizeHorCursor}.get(edge)
        self.setCursor(cur if cur else Qt.ArrowCursor)
    def closeEvent(self, e):
        try:
            self.watch.stop(); self.telem.stop()
            self.watch.wait(800); self.telem.wait(800)
        except Exception:
            pass
        super().closeEvent(e)
def GraphicalUserInterface():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
if __name__ == "__main__":
    GraphicalUserInterface()
