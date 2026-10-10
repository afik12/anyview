import socket
import time
import ctypes
from ctypes import wintypes
import cv2
import numpy as np
import protocol

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD)
    ]

class ScreenStreamer:
    def __init__(self, controller_ip="127.0.0.1"):
        self.controller_ip = controller_ip
        self.screen_w = user32.GetSystemMetrics(0)
        self.screen_h = user32.GetSystemMetrics(1)
        self.frame_id = 0

    def capture_frame(self):
        hdesktop_dc = user32.GetDC(0)
        hcapture_dc = gdi32.CreateCompatibleDC(hdesktop_dc)
        hbitmap = gdi32.CreateCompatibleBitmap(hdesktop_dc, self.screen_w, self.screen_h)
        gdi32.SelectObject(hcapture_dc, hbitmap)

        gdi32.BitBlt(hcapture_dc, 0, 0, self.screen_w, self.screen_h, hdesktop_dc, 0, 0, 0x00CC0020)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = self.screen_w
        bmi.biHeight = -self.screen_h
        bmi.biPlanes = 1
        bmi.biBitCount = 24
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(self.screen_w * self.screen_h * 3)
        gdi32.GetDIBits(hcapture_dc, hbitmap, 0, self.screen_h, buf, ctypes.byref(bmi), 0)

        img = np.frombuffer(buf, dtype=np.uint8).reshape((self.screen_h, self.screen_w, 3))

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hcapture_dc)
        user32.ReleaseDC(0, hdesktop_dc)

        return img.copy()

    def run_stream(self, running_event, frame_lock, frame_container):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        prev_frame = None
        last_keyframe_time = 0

        while running_event.is_set():
            curr_frame = None
            with frame_lock:
                if frame_container[0] is not None:
                    curr_frame = frame_container[0].copy()

            if curr_frame is None:
                time.sleep(0.01)
                continue

            now = time.time()
            is_keyframe = (now - last_keyframe_time > 2.0) or (prev_frame is None)

            if is_keyframe:
                frame_type = protocol.FRAME_TYPE_FULL
                _, encoded = cv2.imencode(".jpg", curr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                payload = encoded.tobytes()
                prev_frame = curr_frame
                last_keyframe_time = now
            else:
                patch, mask = protocol.compute_diff(curr_frame, prev_frame)
                changed = np.count_nonzero(mask)
                if changed == 0:
                    time.sleep(0.03)
                    continue

                if changed > (self.screen_w * self.screen_h * 0.4):
                    frame_type = protocol.FRAME_TYPE_FULL
                    _, encoded = cv2.imencode(".jpg", curr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    payload = encoded.tobytes()
                    last_keyframe_time = now
                else:
                    frame_type = protocol.FRAME_TYPE_DIFF
                    _, encoded = cv2.imencode(".png", patch)
                    payload = encoded.tobytes()

                prev_frame = curr_frame

            self.frame_id += 1
            total_chunks = (len(payload) + protocol.MAX_PAYLOAD - 1) // protocol.MAX_PAYLOAD
            for idx in range(total_chunks):
                start = idx * protocol.MAX_PAYLOAD
                chunk = payload[start:start + protocol.MAX_PAYLOAD]
                packet = protocol.pack_chunk(self.frame_id, frame_type, idx, total_chunks, now, chunk)
                sock.sendto(packet, (self.controller_ip, protocol.VIDEO_PORT))

            time.sleep(0.033)

        sock.close()