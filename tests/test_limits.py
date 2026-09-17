#!/usr/bin/env python3
"""Tests for bounded text ingestion shared by untrusted-text CLIs."""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import limits  # noqa: E402
import registry  # noqa: E402


class RecordingStream(io.StringIO):
    def __init__(self, value):
        super().__init__(value)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class TestBoundedReads(unittest.TestCase):
    def test_stream_read_requests_only_limit_plus_one(self):
        stream = RecordingStream("plain text")
        self.assertEqual(limits.read_text(stream), "plain text")
        self.assertEqual(stream.read_sizes, [limits.MAX_INPUT_CHARS + 1])

    def test_stream_rejects_oversized_input(self):
        stream = RecordingStream("x" * (limits.MAX_INPUT_CHARS + 1))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            limits.read_text(stream)

    def test_file_rejects_oversized_input_without_unbounded_read(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         delete=False) as handle:
            path = handle.name
            handle.write("x" * (limits.MAX_INPUT_CHARS + 1))
        try:
            with self.assertRaisesRegex(ValueError, "exceeds"):
                limits.read_text_file(path)
        finally:
            os.unlink(path)

    def test_collection_enforces_aggregate_limit(self):
        half = "x" * (limits.MAX_INPUT_CHARS // 2 + 1)
        with self.assertRaisesRegex(ValueError, "aggregate"):
            limits.check_input_collection([half, half])

    def test_json_loader_uses_the_same_bounded_reader(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         delete=False) as handle:
            path = handle.name
            json.dump({"source": "x" * limits.MAX_INPUT_CHARS}, handle)
        try:
            with self.assertRaisesRegex(ValueError, "exceeds"):
                limits.load_json_file(path)
        finally:
            os.unlink(path)

    def test_registry_loader_uses_the_bounded_json_reader(self):
        with mock.patch.object(
                limits, "load_json_file",
                return_value={"version": "test"}) as load:
            self.assertEqual(registry.load_registry("custom.json")["version"],
                             "test")
        load.assert_called_once_with("custom.json", "rule registry")


if __name__ == "__main__":
    unittest.main()
