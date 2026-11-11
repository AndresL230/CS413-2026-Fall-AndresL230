"""Test doubles that run inside the spawned interpretation worker."""
import os


def die_before_reporting(conn, source, recursion_limit, stack_bytes):
    """Stand-in for worker._child_main: exit hard before sending any result."""
    os._exit(1)
