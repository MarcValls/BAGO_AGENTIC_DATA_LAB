"""One durable scheduler owner, cooperative shutdown; no module-level threads."""
import asyncio
import os


class CommunicationWorker:
    def __init__(self, service):
        self.service = service
        self.stop_event = asyncio.Event()
        self.handle = None
        self.task = None

    async def start(self):
        self.handle = open(self.service.root / "worker.lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                self.handle.write(b"0")
                self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            return False
        try:
            self.service.recover()
        except Exception:
            await self.stop()
            raise
        self.task = asyncio.create_task(self.run())
        return True

    async def run(self):
        while not self.stop_event.is_set():
            try:
                await asyncio.to_thread(self.service.tick, should_stop=self.stop_event.is_set)
            except Exception:
                # Persisted sending claims remain non-retryable until recovery.
                pass
            try:
                await asyncio.wait_for(self.stop_event.wait(), 1)
            except asyncio.TimeoutError:
                pass

    async def stop(self):
        self.stop_event.set()
        if self.task:
            # Wait for an already authorized transport operation; do not pretend
            # cancellation undoes browser effects or release ownership early.
            await self.task
        if self.handle:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            self.handle.close()
            self.handle = None
