import socket
import threading
import os
import protocol
from receiveVideo import VideoReceiver
from sendCommand import CommandSender

class MainController:
    def __init__(self, host_ip="127.0.0.1"):
        os.makedirs("logs", exist_ok=True)
        self.host_ip = host_ip
        self.running = threading.Event()
        self.running.set()
        self.logger = protocol.ThreadSafeLogger("logs/controller.log")

        self.frames_dict = {}
        self.dict_lock = threading.Lock()
        self.display_frame = [None]

        self.receiver = VideoReceiver(self.frames_dict, self.dict_lock)
        self.sender = CommandSender(host_ip=self.host_ip)

    def handshake(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self.host_ip, protocol.CONTROL_PORT))
            sock.settimeout(3.0)
            data = sock.recv(1024).decode("utf-8", errors="ignore")
            if data.startswith("RES"):
                parts = data.strip().split(",")
                self.sender.set_host_dimensions(int(parts[1]), int(parts[2]))
                self.logger.log(f"Connected to Host: {parts[1]}x{parts[2]}")
        except Exception:
            self.logger.log("Handshake skipped or standalone")
        finally:
            sock.close()

    def start(self):
        self.logger.log("Controller App started")
        self.handshake()

        t1 = threading.Thread(target=self.receiver.run_receiver, args=(self.running,), name="Video Receiver Thread", daemon=True)
        t2 = threading.Thread(target=self.receiver.run_assembler, args=(self.running, self.display_frame), name="FrameAssembler Thread", daemon=True)
        t3 = threading.Thread(target=self.receiver.run_cleanup, args=(self.running,), name="Cleanup Thread", daemon=True)
        t4 = threading.Thread(target=self.sender.run_sender, args=(self.running,), name="CommandSenderThread", daemon=True)
        t5 = threading.Thread(target=self.sender.run_ui, args=(self.running, self.display_frame), name="InputCapture Thread", daemon=True)

        t1.start()
        t2.start()
        t3.start()
        t4.start()
        t5.start()

        t5.join()
        self.running.clear()
        self.logger.log("Controller shutting down")
        self.logger.close()

if __name__ == "__main__":
    ctrl = MainController()
    ctrl.start()