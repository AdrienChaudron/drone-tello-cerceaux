import queue
import threading


class AxisLogger:
    """Thread-safe background file logger for an individual control axis."""

    def __init__(self, filename: str) -> None:
        self.filename: str = filename
        self._queue: queue.Queue[tuple[float, float, float, float, int] | None] = queue.Queue()
        self._thread: threading.Thread = threading.Thread(target=self._worker, daemon=True)
        self._is_running: bool = False

    def start(self) -> None:
        """Starts the background worker thread and writes the header."""
        self._is_running = True
        self._thread.start()

    def push(self, timestamp: float, target: float, command: float, measure: float, speed: int) -> None:
        """Non-blocking producer call: pushes a state tuple into the FIFO queue."""
        if self._is_running:
            self._queue.put((timestamp, target, command, measure, speed))

    def stop(self) -> None:
        """Flushes remaining queued items and shuts down the worker thread cleanly."""
        if not self._is_running:
            return
        self._is_running = False
        self._queue.put(None)  # Sentinel/poison-pill to stop worker
        self._thread.join()

    def _worker(self) -> None:
        """Consumer worker loop running in the background."""
        with open(self.filename, mode="w", encoding="utf-8") as f:
            while True:
                item = self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break

                t, target, cmd, measure, speed = item
                # Format: timestamp target command measure
                f.write(f"{t:.4f},{target:.2f},{cmd:.2f},{measure:.2f},{speed}\n")
                self._queue.task_done()
