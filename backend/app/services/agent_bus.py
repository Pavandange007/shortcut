from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final


@dataclass
class AgentBusMessage:
    id: str
    job_id: str
    from_agent: str
    to_agent: str | None
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class InMemoryJobMessageBus:
    """
    In-process message bus partitioned by job_id.

    Phase-1: append-only inbox per job; orchestrator and UI read recent messages.
    """

    def __init__(self) -> None:
        self._lock: Final[threading.Lock] = threading.Lock()
        self._messages: dict[str, list[AgentBusMessage]] = defaultdict(list)

    def publish(self, job_id: str, message: AgentBusMessage) -> None:
        with self._lock:
            self._messages[job_id].append(message)

    def publish_simple(
        self,
        *,
        job_id: str,
        from_agent: str,
        type: str,
        payload: dict[str, Any] | None = None,
        to_agent: str | None = None,
    ) -> AgentBusMessage:
        msg = AgentBusMessage(
            id=uuid.uuid4().hex,
            job_id=job_id,
            from_agent=from_agent,
            to_agent=to_agent,
            type=type,
            payload=payload or {},
        )
        self.publish(job_id, msg)
        return msg

    def recent(self, job_id: str, *, limit: int = 24) -> list[AgentBusMessage]:
        with self._lock:
            items = list(self._messages.get(job_id, []))
        if limit <= 0:
            return []
        return items[-limit:]

    def to_ui_dicts(self, job_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in self.recent(job_id, limit=limit):
            out.append(
                {
                    "id": m.id,
                    "fromAgent": m.from_agent,
                    "toAgent": m.to_agent,
                    "type": m.type,
                    "payload": m.payload,
                    "createdAt": m.created_at,
                }
            )
        return out


_global_bus = InMemoryJobMessageBus()


def get_message_bus() -> InMemoryJobMessageBus:
    return _global_bus
