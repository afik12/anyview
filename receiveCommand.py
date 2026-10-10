import socket
import ctypes
from ctypes import wintypes
import protocol

user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t)
    ]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

class CommandReceiver:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

    def run_receiver(self, running_event):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("0.0.0.0", protocol.INPUT_PORT))
        srv.listen(1)
        srv.settimeout(1.0)

        conn = None
        while running_event.is_set():
            try:
                conn, _ = srv.accept()
                break
            except socket.timeout:
                continue

        while running_event.is_set() and conn:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                for line in data.decode("utf-8", errors="ignore").splitlines():
                    parts = line.split(",")
                    cmd = parts[0]
                    if cmd == "M":
                        x, y = int(float(parts[1])), int(float(parts[2]))
                        inp = INPUT()
                        inp.type = INPUT_MOUSE
                        inp.u.mi.dx = int(x * 65535 / self.screen_w)
                        inp.u.mi.dy = int(y * 65535 / self.screen_h)
                        inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
                        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                    elif cmd == "MD":
                        inp = INPUT()
                        inp.type = INPUT_MOUSE
                        inp.u.mi.dwFlags = MOUSEEVENTF_LEFTDOWN if parts[1] == "L" else MOUSEEVENTF_RIGHTDOWN
                        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                    elif cmd == "MU":
                        inp = INPUT()
                        inp.type = INPUT_MOUSE
                        inp.u.mi.dwFlags = MOUSEEVENTF_LEFTUP if parts[1] == "L" else MOUSEEVENTF_RIGHTUP
                        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            except Exception:
                break

        if conn:
            conn.close()
        srv.close()