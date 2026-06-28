"""Tests for LRC detection in get_track_lyrics and the LRC line regex."""

import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

from services.database import get_track_lyrics, _LRC_LINE_RE


LRC_SAMPLE = """[ti:Test Song]
[ar:Test Artist]
[00:01.23]First line
[00:03.45]Second line
[00:05.67]Third line
"""

PLAIN_SAMPLE = """First line
Second line
Third line
"""


class LRCLineRegexTest(unittest.TestCase):
    def test_matches_timestamp_line(self):
        self.assertTrue(_LRC_LINE_RE.match("[00:01.23]hello"))
        self.assertTrue(_LRC_LINE_RE.match("[01:00]hello"))
        self.assertTrue(_LRC_LINE_RE.match("[10:30.001]hello"))

    def test_rejects_metadata_line(self):
        self.assertFalse(_LRC_LINE_RE.match("[ti:Song]"))
        self.assertFalse(_LRC_LINE_RE.match("[ar:Artist]"))
        self.assertFalse(_LRC_LINE_RE.match("plain text"))


class GetTrackLyricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("CREATE TABLE tracks (id TEXT, lyrics TEXT)")
        conn.execute("INSERT INTO tracks VALUES ('lrc', ?)", (LRC_SAMPLE,))
        conn.execute("INSERT INTO tracks VALUES ('plain', ?)", (PLAIN_SAMPLE,))
        conn.execute("INSERT INTO tracks VALUES ('empty', NULL)")
        conn.commit()
        conn.close()

        import config
        config.Config.DB_PATH = self.tmp.name
        config.Config.DB_PERSIST_PATH = self.tmp.name

        from flask import Flask
        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_lrc_lyrics_detected_as_synced(self):
        with self.app.app_context():
            result = get_track_lyrics("lrc")
        self.assertIsNotNone(result["lyrics"])
        self.assertTrue(result["synced"])

    def test_plain_lyrics_not_synced(self):
        with self.app.app_context():
            result = get_track_lyrics("plain")
        self.assertIsNotNone(result["lyrics"])
        self.assertFalse(result["synced"])

    def test_missing_lyrics(self):
        with self.app.app_context():
            result = get_track_lyrics("empty")
        self.assertIsNone(result["lyrics"])
        self.assertFalse(result["synced"])

    def test_missing_track(self):
        with self.app.app_context():
            result = get_track_lyrics("nope")
        self.assertIsNone(result["lyrics"])
        self.assertFalse(result["synced"])

    def test_none_track_id(self):
        with self.app.app_context():
            result = get_track_lyrics(None)
        self.assertIsNone(result["lyrics"])
        self.assertFalse(result["synced"])


if __name__ == "__main__":
    unittest.main()
