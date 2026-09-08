from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional


class TaskCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskEvent:
    kind: str
    message: str = ""
    payload: Any = None
    progress: Optional[float] = None


class TaskContext:
    def __init__(self, event_queue: "queue.Queue[TaskEvent]", cancel_event: threading.Event):
        self._queue = event_queue
        self._cancel_event = cancel_event

    def emit(self, kind: str, message: str = "", payload: Any = None, progress: Optional[float] = None) -> None:
        self._queue.put(TaskEvent(kind=kind, message=message, payload=payload, progress=progress))

    def log(self, message: str) -> None:
        self.emit("log", message=message)

    def set_progress(self, progress: Optional[float], message: str = "") -> None:
        self.emit("progress", message=message, progress=progress)

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise TaskCancelled("任务已取消")


class TaskRunner:
    """Single-worker task runner used by the Tk main thread.

    Worker functions receive a TaskContext and must never touch Tk widgets.
    UI code polls ``drain_events`` from ``after()`` and applies changes on the
    main thread.
    """

    def __init__(self) -> None:
        self._events: "queue.Queue[TaskEvent]" = queue.Queue()
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def busy(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def start(self, name: str, worker: Callable[[TaskContext], Any]) -> bool:
        with self._lock:
            if self.busy:
                return False
            self._cancel_event = threading.Event()
            context = TaskContext(self._events, self._cancel_event)
            self._thread = threading.Thread(
                target=self._run,
                args=(name, worker, context),
                name=f"filecheck-{name}",
                daemon=True,
            )
            self._thread.start()
            return True

    def cancel(self) -> None:
        self._cancel_event.set()

    def drain_events(self, limit: int = 100) -> list[TaskEvent]:
        events: list[TaskEvent] = []
        for _ in range(max(1, limit)):
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def _run(self, name: str, worker: Callable[[TaskContext], Any], context: TaskContext) -> None:
        context.emit("started", message=name)
        try:
            result = worker(context)
            context.raise_if_cancelled()
        except TaskCancelled as exc:
            context.emit("cancelled", message=str(exc))
        except Exception as exc:
            context.emit("error", message=str(exc), payload=exc)
        else:
            context.emit("success", message=name, payload=result, progress=1.0)
