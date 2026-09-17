#!/usr/bin/env python3
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: build-release-json.py TAG VERSION NOTES_FILE")

    tag, version, notes_file = sys.argv[1:]
    payload = {
        "tag_name": tag,
        "name": "antislop v%s" % version,
        "body": Path(notes_file).read_text(encoding="utf-8"),
        "draft": False,
        "prerelease": False,
    }
    json.dump(payload, sys.stdout)


if __name__ == "__main__":
    main()
