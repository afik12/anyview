import socket
import time
import cv2
import numpy as np
import protocol

class VideoReceiver:
    def __init__(self, frames_dict, dict_lock):
        self.frames_dict = frames_dict
        self.dict_lock = dict_lock

    def run_receiver(self, running_event):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", protocol.VIDEO_PORT))
        sock.settimeout(1.0)

        while running_event.is_set():
            try:
                data, _ = sock.recvfrom(65535)
                meta, payload = protocol.unpack_chunk(data)
                if not meta:
                    continue

                frame_id, frame_type, chunk_idx, total_chunks, timestamp, _ = meta

                with self.dict_lock:
                    if frame_id not in self.frames_dict:
                        self.frames_dict[frame_id] = {
                            "type": frame_type,
                            "total": total_chunks,
                            "timestamp": timestamp,
                            "chunks": {}
                        }
                    self.frames_dict[frame_id]["chunks"][chunk_idx] = payload

            except socket.timeout:
                continue
            except Exception:
                break
        sock.close()

    def run_assembler(self, running_event, display_container):
        last_frame = None

        while running_event.is_set():
            completed_id = None
            info = None

            with self.dict_lock:
                for fid in sorted(self.frames_dict.keys()):
                    if len(self.frames_dict[fid]["chunks"]) == self.frames_dict[fid]["total"]:
                        completed_id = fid
                        info = self.frames_dict.pop(fid)
                        break

            if not info:
                time.sleep(0.01)
                continue

            raw = bytearray()
            for i in range(info["total"]):
                raw.extend(info["chunks"][i])

            img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                if info["type"] == protocol.FRAME_TYPE_FULL:
                    last_frame = img
                elif last_frame is not None:
                    mask = np.any(img > 0, axis=2)
                    last_frame[mask] = img[mask]

                display_container[0] = last_frame

    def run_cleanup(self, running_event):
        while running_event.is_set():
            time.sleep(1.0)
            now = time.time()
            with self.dict_lock:
                expired = [fid for fid, data in self.frames_dict.items() if (now - data["timestamp"]) > 1.5]
                for fid in expired:
                    del self.frames_dict[fid]