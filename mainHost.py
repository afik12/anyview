import socket
import threading
import time
import os
import ctypes
import protocol
from streamVideo import ScreenStreamer
from receiveCommand import CommandReceiver

user32 = ctypes.windll.user32

class MainHost:
    def __init__(self, controller_ip="127.0.0.1"):
        os.makedirs("logs", exist_ok=True)
        self.controller_ip = controller_ip
        self.running = threading.Event()
        self.running.set()
        self.logger = protocol.ThreadSafeLogger("logs/host.log")

        self.screen_w = user32.GetSystemMetrics(0)
        self.screen_h = user32.GetSystemMetrics(1)

        self.latest_frame = [None]
        self.frame_lock = threading.Lock()

        self.streamer = ScreenStreamer(controller_ip=self.controller_ip)
        self.receiver = CommandReceiver(self.screen_w, self.screen_h)

    def capture_worker(self):
        while self.running.is_set():
            img = self.streamer.capture_frame()
            with self.frame_lock:
                self.latest_frame[0] = img
            time.sleep(0.033)

    def heartbeat_worker(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("0.0.0.0", protocol.CONTROL_PORT))
        srv.listen(1)
        srv.settimeout(1.0)

        conn = None
        while self.running.is_set():
            try:
                conn, _ = srv.accept()
                break
            except socket.timeout:
                continue

        if conn:
            conn.sendall(f"RES,{self.screen_w},{self.screen_h}\n".encode("utf-8"))

        while self.running.is_set() and conn:
            try:
                conn.settimeout(5.0)
                data = conn.recv(1024)
                if not data:
                    break
                if b"PING" in data:
                    conn.sendall(b"PONG\n")
                    self.logger.log("PING received, PONG sent")
            except Exception:
                break

        if conn:
            conn.close()
        srv.close()

    def start(self):
        self.logger.log("Host Agent started")

        t1 = threading.Thread(target=self.capture_worker, name="Capture Thread", daemon=True)
        t2 = threading.Thread(target=self.streamer.run_stream, args=(self.running, self.frame_lock, self.latest_frame), name="VideoSender Thread", daemon=True)
        t3 = threading.Thread(target=self.receiver.run_receiver, args=(self.running,), name="Command Receiver Thread", daemon=True)
        t4 = threading.Thread(target=self.heartbeat_worker, name="HeartbeatThread", daemon=True)

        t1.start()
        t2.start()
        t3.start()
        t4.start()

        try:
            while self.running.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.running.clear()
            self.logger.log("Host shutting down")
            self.logger.close()

if __name__ == "__main__":
    host = MainHost()
    host.start()