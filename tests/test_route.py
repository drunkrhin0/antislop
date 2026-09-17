#!/usr/bin/env python3
"""Tests for prose-intent routing."""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import route  # noqa: E402


class TestRouteRequest(unittest.TestCase):
    def test_standalone_scan_request_routes_to_audit(self):
        result = route.route_request("scan this draft for formulaic writing")
        self.assertEqual(result, {"skill": "antislop", "mode": "detect"})


if __name__ == "__main__":
    unittest.main()
