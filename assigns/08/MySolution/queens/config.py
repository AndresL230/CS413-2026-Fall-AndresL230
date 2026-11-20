"""Service constants and defaults (overridable per app for tests)."""

from pathlib import Path

API_VERSION = "1.0"
HOST = "127.0.0.1"
PORT = 8000
MAX_CONTENT_LENGTH = 64 * 1024     # request body bytes
STREAM_TTL_SECONDS = 600           # inactivity lifetime of a stream id
MAX_STREAMS = 256                  # live streams; exhausted markers do not count
MAX_LIMIT = 32                     # events per queens.next
STREAM_ID_MAX_CHARS = 64

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

DEFAULTS = {
    "MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH,
    "STREAM_TTL_SECONDS": STREAM_TTL_SECONDS,
    "MAX_STREAMS": MAX_STREAMS,
}
