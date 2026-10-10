import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
import numpy as np
import protocol

class TestAnyViewSystem(unittest.TestCase):
    def test_chunking_pack_unpack(self):
        payload = b"test_payload_123"
        packed = protocol.pack_chunk(1, protocol.FRAME_TYPE_FULL, 0, 1, 100.0, payload)
        meta, extracted = protocol.unpack_chunk(packed)
        self.assertEqual(meta[0], 1)
        self.assertEqual(meta[1], protocol.FRAME_TYPE_FULL)
        self.assertEqual(extracted, payload)

    def test_diff_engine(self):
        img1 = np.zeros((10, 10, 3), dtype=np.uint8)
        img2 = np.zeros((10, 10, 3), dtype=np.uint8)
        img2[0, 0] = [100, 100, 100]
        patch, mask = protocol.compute_diff(img2, img1, threshold=25)
        self.assertTrue(mask[0, 0])
        self.assertFalse(mask[0, 1])

    def test_coord_normalization(self):
        x, y = protocol.normalize_coords(640, 360, 1280, 720, 1920, 1080)
        self.assertEqual(x, 960)
        self.assertEqual(y, 540)

if __name__ == "__main__":
    unittest.main()