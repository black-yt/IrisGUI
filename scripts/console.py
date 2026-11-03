"""Configure Unicode-safe console streams, including Windows Python via WSL."""
import sys


def configure_console_encoding():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            # Test captures, notebooks and GUI launchers can replace or omit streams.
            continue
        try:
            reconfigure(encoding="utf-8", errors="backslashreplace")
        except (OSError, ValueError):
            # An input stream that has already been read cannot change encoding.
            continue
