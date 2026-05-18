"""Context-window simulation for retention and reload pressure."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextWindowEvent:
    """One context simulation event."""

    symbol: str
    reloaded: bool = False
    evicted: str | None = None


@dataclass
class ContextWindowState:
    """Current and historical context window state."""

    active: deque[str]
    evicted: set[str] = field(default_factory=set)
    events: list[ContextWindowEvent] = field(default_factory=list)

    @property
    def reload_count(self) -> int:
        return sum(1 for event in self.events if event.reloaded)

    @property
    def eviction_count(self) -> int:
        return sum(1 for event in self.events if event.evicted is not None)


class ContextWindowSimulator:
    """Simulate active context retention, eviction, and reload pressure."""

    def __init__(self, capacity: int = 12) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity

    def simulate(self, symbols: list[str]) -> ContextWindowState:
        """Run a least-recently-used style simulation over active symbols."""
        active: deque[str] = deque(maxlen=self.capacity)
        active_set: set[str] = set()
        evicted: set[str] = set()
        events: list[ContextWindowEvent] = []

        for symbol in symbols:
            reloaded = symbol in evicted and symbol not in active_set
            evicted_symbol: str | None = None

            if symbol in active_set:
                active.remove(symbol)
                active.append(symbol)
                events.append(ContextWindowEvent(symbol=symbol, reloaded=reloaded))
                continue

            if len(active) == active.maxlen:
                evicted_symbol = active.popleft()
                active_set.remove(evicted_symbol)
                evicted.add(evicted_symbol)

            if reloaded:
                evicted.remove(symbol)
            active.append(symbol)
            active_set.add(symbol)
            events.append(
                ContextWindowEvent(
                    symbol=symbol,
                    reloaded=reloaded,
                    evicted=evicted_symbol,
                )
            )

        return ContextWindowState(active=active, evicted=evicted, events=events)
