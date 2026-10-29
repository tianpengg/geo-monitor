"""OS-managed source lock, automatically released on process exit/crash."""

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def source_lock(state_path: Path):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    handle = state_path.with_suffix(state_path.suffix + ".lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()
