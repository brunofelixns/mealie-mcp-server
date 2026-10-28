"""Make process termination observable as EOF by the SDK's blocking stdin reader.

The SDK reads AsyncFile with a non-cancellable worker thread. On POSIX a bounded
pipe bridge lets signals close that input without touching MCP internals. This
module owns its descriptors and joins its pump before restoring process stdin.
"""

import os
import select
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType


@contextmanager
def terminating_stdin() -> Iterator[None]:
    original = os.dup(0)
    reader, writer = os.pipe()
    wake_reader, wake_writer = os.pipe()
    stopped = threading.Event()
    os.set_blocking(writer, False)

    def terminate(signum: int, frame: FrameType | None) -> None:
        if not stopped.is_set():
            stopped.set()
            os.write(wake_writer, b"x")

    def pump() -> None:
        pending = b""
        try:
            while not stopped.is_set():
                readable, writable, _ = select.select(
                    [wake_reader] if pending else [wake_reader, original],
                    [writer] if pending else [],
                    [],
                )
                if wake_reader in readable:
                    break
                if original in readable:
                    pending = os.read(original, 65536)
                    if not pending:
                        break
                if writer in writable:
                    try:
                        pending = pending[os.write(writer, pending) :]
                    except BlockingIOError:
                        continue
        except OSError:
            # The SDK or its client may already have closed the channel.
            pass
        finally:
            os.close(writer)

    previous = {sig: signal.signal(sig, terminate) for sig in (signal.SIGTERM, signal.SIGINT)}
    thread = threading.Thread(target=pump, name="mcp-stdin", daemon=True)
    try:
        os.dup2(reader, 0)
        thread.start()
        yield
    finally:
        terminate(signal.SIGTERM, None)
        thread.join(timeout=2)
        os.dup2(original, 0)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        for descriptor in (reader, original, wake_reader, wake_writer):
            os.close(descriptor)
