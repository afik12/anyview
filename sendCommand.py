import socket
import time
import queue
import cv2
import protocol

class CommandSender:
    def __init__(self, host_ip="127.0.0.1", ctrl_w=1280, ctrl_h=720):
        self.host_ip = host_ip
        self.ctrl_w = ctrl_w
        self.ctrl_h = ctrl_h
        self.host_w = 1920
        self.host_h = 1080
        self.input_queue = queue.Queue()

    def set_host_dimensions(self, w, h):
        self.host_w = w
        self.host_h = h

    def mouse_callback(self, event, x, y, flags, param):
        norm_x, norm_y = protocol.normalize_coords(x, y, self.ctrl_w, self.ctrl_h, self.host_w, self.host_h)
        if event == cv2.EVENT_MOUSEMOVE:
            self.input_queue.put(f"M,{norm_x},{norm_y}\n")
        elif event == cv2.EVENT_LBUTTONDOWN:
            self.input_queue.put("MD,L\n")
        elif event == cv2.EVENT_LBUTTONUP:
            self.input_queue.put("MU,L\n")
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.input_queue.put("MD,R\n")
        elif event == cv2.EVENT_RBUTTONUP:
            self.input_queue.put("MU,R\n")

    def run_ui(self, running_event, display_container):
        cv2.namedWindow("AnyView Controller", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("AnyView Controller", self.ctrl_w, self.ctrl_h)
        cv2.setMouseCallback("AnyView Controller", self.mouse_callback)

        while running_event.is_set():
            if display_container[0] is not None:
                resized = cv2.resize(display_container[0], (self.ctrl_w, self.ctrl_h))
                cv2.imshow("AnyView Controller", resized)

            key = cv2.waitKey(16) & 0xFF
            if key == 27:
                running_event.clear()
                break

        cv2.destroyAllWindows()

    def run_sender(self, running_event):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while running_event.is_set():
            try:
                sock.connect((self.host_ip, protocol.INPUT_PORT))
                break
            except Exception:
                time.sleep(1)

        while running_event.is_set():
            try:
                msg = self.input_queue.get(timeout=0.5)
                sock.sendall(msg.encode("utf-8"))
                self.input_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                break
        sock.close()