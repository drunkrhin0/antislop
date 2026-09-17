"""Input size limits shared by the command-line tools.

The audit and repair tools read untrusted text from stdin or a file. The
detection regexes and diffs are bounded but still cost linear time per
character, so cap the input size to keep a hostile or accidentally huge pipe
from stalling the tool.
"""

import json

MAX_INPUT_CHARS = 1_000_000


def check_input_size(text, what="input"):
    """Return text unchanged, or raise ValueError when it exceeds the cap."""
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(
            "%s exceeds the %d-character limit" % (what, MAX_INPUT_CHARS)
        )
    return text


def read_text(stream, what="input", max_chars=None):
    """Read at most the accepted character budget from an open text stream."""
    limit = MAX_INPUT_CHARS if max_chars is None else max_chars
    if limit < 0 or limit > MAX_INPUT_CHARS:
        raise ValueError("invalid input character budget")
    text = stream.read(limit + 1)
    if len(text) > limit:
        raise ValueError("%s exceeds the %d-character limit" % (what, limit))
    return text


def read_text_file(path, what=None, max_chars=None):
    """Read a UTF-8 file without allocating beyond the character budget."""
    label = what or "file %s" % path
    with open(path, encoding="utf-8") as stream:
        return read_text(stream, label, max_chars=max_chars)


def load_json_file(path, what=None):
    """Load a JSON file through the same bounded text-input path."""
    return json.loads(read_text_file(path, what or "JSON file %s" % path))


def check_input_collection(texts, what="documents"):
    """Reject a collection whose combined text exceeds the same budget."""
    total = 0
    for text in texts:
        check_input_size(text, what)
        total += len(text)
        if total > MAX_INPUT_CHARS:
            raise ValueError(
                "%s exceed the %d-character aggregate limit"
                % (what, MAX_INPUT_CHARS)
            )
    return texts
