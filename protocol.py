import struct
import time
import queue
import threading
import numpy as np

CHUNK_HEADER_FORMAT = "!IBHHdI"
HEADER_SIZE = struct.calcsize(CHUNK_HEADER_FORMAT)
MAX_PAYLOAD = 1400

FRAME_TYPE_FULL = 0
FRAME_TYPE_DIFF = 1

CONTROL_PORT = 5000
VIDEO_PORT = 5001
INPUT_PORT = 5002

def pack_chunk(frame_id, frame_type, chunk_idx, total_chunks, timestamp, payload):
    header = struct.pack(
        CHUNK_HEADER_FORMAT,
        frame_id,
        frame_type,
        chunk_idx,
        total_chunks,
        timestamp,
        len(payload)
    )
    return header + payload

def unpack_chunk(data):
    if len(data) < HEADER_SIZE:
        return None, None
    header = data[:HEADER_SIZE]
    payload = data[HEADER_SIZE:]
    frame_id, frame_type, chunk_idx, total_chunks, timestamp, payload_len = struct.unpack(CHUNK_HEADER_FORMAT, header)
    return (frame_id, frame_type, chunk_idx, total_chunks, timestamp, payload_len), payload[:payload_len]

def compute_diff(curr_img, prev_img, threshold=25):
    diff = np.abs(curr_img.astype(np.int16) - prev_img.astype(np.int16))
    mask = np.any(diff > threshold, axis=2)
    patch = np.zeros_like(curr_img)
    patch[mask] = curr_img[mask]
    return patch, mask

def normalize_coords(x_c, y_c, w_c, h_c, w_h, h_h):
    if w_c == 0 or h_c == 0:
        return 0, 0
    return int(x_c * (w_h / w_c)), int(y_c * (h_h / h_c))

class ThreadSafeLogger:
    def __init__(self, filename):
        self.filename = filename
        self.q = queue.Queue()
        self.running = True
        self.worker = threading.Thread(target=self._log_worker, name="LoggerThread", daemon=True)
        self.worker.start()

    def log(self, message):
        self.q.put(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

    def _log_worker(self):
        with open(self.filename, "a", encoding="utf-8") as f:
            while self.running or not self.q.empty():
                try:
                    msg = self.q.get(timeout=0.5)
                    f.write(msg)
                    f.flush()
                    self.q.task_done()
                except queue.Empty:
                    continue

    def close(self):
        self.running = False
        if self.worker.is_alive():
            self.worker.join()