"""Tests for get_track_lyrics: returns the stored lyrics text, or None."""

import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

from services.database import get_track_lyrics


SAMPLE = "First line\nSecond line\nThird line\n"


class GetTrackLyricsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("CREATE TABLE tracks (id TEXT, lyrics TEXT)")
        conn.execute("INSERT INTO tracks VALUES ('has', ?)", (SAMPLE,))
        conn.execute("INSERT INTO tracks VALUES ('empty', NULL)")
        conn.commit()
        conn.close()

        from flask import Flask
        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_returns_lyrics_text(self):
        with self.app.app_context():
            self.assertEqual(get_track_lyrics("has"), SAMPLE)

    def test_missing_lyrics(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics("empty"))

    def test_missing_track(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics("nope"))

    def test_none_track_id(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics(None))


if __name__ == "__main__":
    unittest.main()
