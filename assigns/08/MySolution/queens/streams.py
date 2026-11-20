"""Process-local table of open event streams. Knows nothing about JSON-RPC.

Each entry holds a lock, the unconsumed rest of one trace (an EventStream,
whose stored lazy is always the next *unforced* tail), and a last-used time
from an injectable clock. When `done` is reached the EventStream is dropped
and the entry becomes an exhausted marker until it is closed or expires.
"""

import threading
import time
import uuid


class UnknownStream(Exception):
    """The id was never issued, was closed, or expired."""


class TooManyStreams(Exception):
    """The table already holds `cap` entries."""


class _Entry:
    __slots__ = ("lock", "stream", "last_used")

    def __init__(self, stream, now):
        self.lock = threading.Lock()
        self.stream = stream  # EventStream, or None once exhausted
        self.last_used = now


class StreamTable:
    def __init__(self, open_stream, clock=time.monotonic, ttl=600, cap=256):
        self._open_stream = open_stream
        self._clock = clock
        self.ttl = ttl
        self.cap = cap
        self._entries = {}
        self._lock = threading.Lock()  # guards the dict only

    def __len__(self):
        with self._lock:
            return len(self._entries)

    def _sweep(self, now):
        """Drop entries idle for ttl seconds or more. Caller holds self._lock."""
        expired = [sid for sid, e in self._entries.items() if now - e.last_used >= self.ttl]
        for sid in expired:
            del self._entries[sid]

    def _touch(self, stream_id):
        """Sweep, then return the live entry for stream_id (refreshing it)."""
        with self._lock:
            now = self._clock()
            self._sweep(now)
            entry = self._entries.get(stream_id)
            if entry is None:
                raise UnknownStream(stream_id)
            entry.last_used = now
            return entry

    def live_count(self):
        """Streams still holding solver state. Caller holds self._lock.
        Exhausted markers (stream is None) do not count toward the cap;
        they are tiny and are removed by close or expiry."""
        return sum(1 for e in self._entries.values() if e.stream is not None)

    def open(self, size):
        """Allocate a stream. The size must already be validated by the caller.
        The cap (live streams only) is checked before the solver is touched."""
        with self._lock:
            now = self._clock()
            self._sweep(now)
            if self.live_count() >= self.cap:
                raise TooManyStreams(self.cap)
            stream_id = str(uuid.uuid4())
            self._entries[stream_id] = _Entry(self._open_stream(size), now)
            return stream_id

    def next(self, stream_id, limit):
        """Force at most `limit` cells; return (events, done)."""
        entry = self._touch(stream_id)
        with entry.lock:
            events = []
            if entry.stream is None:
                return events, True
            try:
                while len(events) < limit:
                    # EventStream.next swaps its stored lazy for the tail, so
                    # the table only ever holds the next unforced cell.
                    event = entry.stream.next()
                    if event is None or event["event"] == "done":
                        if event is not None:
                            events.append(event)
                        entry.stream = None  # release every interpreter closure
                        return events, True
                    events.append(event)
            except Exception:
                self._discard(stream_id, entry)
                raise
            return events, False

    def close(self, stream_id):
        with self._lock:
            self._sweep(self._clock())
            if self._entries.pop(stream_id, None) is None:
                raise UnknownStream(stream_id)

    def _discard(self, stream_id, entry):
        with self._lock:
            if self._entries.get(stream_id) is entry:
                del self._entries[stream_id]

    def entry_stream(self, stream_id):
        """Test hook: the stored EventStream (None for an exhausted marker)."""
        with self._lock:
            return self._entries[stream_id].stream
