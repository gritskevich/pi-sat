import os
import unittest

import config
from modules.music_library import MusicLibrary


def _mpd_available() -> bool:
    return os.getenv("PISAT_RUN_MPD_TESTS", "0") == "1"


@unittest.skipUnless(_mpd_available(), "MPD integration tests disabled")
class TestIntentMpdCatalog(unittest.TestCase):
    def setUp(self):
        try:
            from mpd import MPDClient
        except Exception as exc:
            self.skipTest(f"python-mpd2 not available: {exc}")

        self.client = MPDClient()
        self.client.timeout = 5
        self.client.idletimeout = None
        self.client.connect(
            getattr(config, "MPD_HOST", "localhost"),
            int(getattr(config, "MPD_PORT", 6600)),
        )

    def tearDown(self):
        try:
            self.client.close()
            self.client.disconnect()
        except Exception:
            pass

    def test_mpd_catalog_load_and_search(self):
        library = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
        count = library.load_from_mpd(self.client)
        self.assertGreater(count, 0)

        # Use MPD tags when available; fallback to filename.
        items = self.client.listallinfo()
        samples = []
        for item in items:
            file_path = item.get("file")
            if not file_path:
                continue
            title = item.get("Title") or item.get("title")
            artist = item.get("Artist") or item.get("artist")
            if title:
                samples.append((title, file_path))
            elif artist:
                samples.append((artist, file_path))
            else:
                samples.append((os.path.splitext(os.path.basename(file_path))[0], file_path))
            if len(samples) >= 5:
                break

        self.assertTrue(samples, "MPD catalog returned no usable samples")

        for query, expected_path in samples:
            with self.subTest(query=query):
                result = library.search_best(query)
                self.assertIsNotNone(result)
                matched_path, confidence = result
                self.assertEqual(matched_path, expected_path)
                self.assertGreaterEqual(confidence, 0.4)
