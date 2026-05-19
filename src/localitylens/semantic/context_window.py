"""Context-window simulation for retention and reload pressure."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextWindowEvent:
    """One context simulation event."""

    symbol: str
    module: str = ""
    neighborhood: frozenset[str] = field(default_factory=frozenset)
    reloaded: bool = False
    evicted: str | None = None
    active_symbols: frozenset[str] = field(default_factory=frozenset)
    active_modules: frozenset[str] = field(default_factory=frozenset)
    active_neighborhoods: frozenset[str] = field(default_factory=frozenset)
    token_pressure: float = 0.0
    compression_ratio: float = 1.0


@dataclass
class ContextWindowState:
    """Current and historical context window state."""

    active_symbols: deque[str]
    active_modules: set[str] = field(default_factory=set)
    active_neighborhoods: set[str] = field(default_factory=set)
    evicted: set[str] = field(default_factory=set)
    events: list[ContextWindowEvent] = field(default_factory=list)
    retained_symbols: set[str] = field(default_factory=set)

    @property
    def active(self) -> deque[str]:
        """Backward-compatible active symbol deque."""
        return self.active_symbols

    @property
    def reload_count(self) -> int:
        return sum(1 for event in self.events if event.reloaded)

    @property
    def eviction_count(self) -> int:
        return sum(1 for event in self.events if event.evicted is not None)

    @property
    def reload_pressure(self) -> float:
        return self.reload_count / max(1, len(self.events))

    @property
    def eviction_pressure(self) -> float:
        return self.eviction_count / max(1, len(self.events))

    @property
    def compression_ratio(self) -> float:
        if not self.events:
            return 1.0
        return self.events[-1].compression_ratio


class ContextWindowSimulator:
    """Simulate active context retention, eviction, and reload pressure."""

    def __init__(self, capacity: int = 12, token_capacity: int | None = None) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if token_capacity is not None and token_capacity < 1:
            raise ValueError("token_capacity must be >= 1")
        self.capacity = capacity
        self.token_capacity = token_capacity

    def simulate(
        self,
        symbols: list[str],
        *,
        symbol_to_module: dict[str, str] | None = None,
        neighborhoods: dict[str, set[str]] | None = None,
        token_weights: dict[str, int] | None = None,
    ) -> ContextWindowState:
        """Run a least-recently-used style simulation over active symbols."""
        active: deque[str] = deque(maxlen=self.capacity)
        active_set: set[str] = set()
        retained_symbols: set[str] = set()
        evicted: set[str] = set()
        events: list[ContextWindowEvent] = []
        modules = symbol_to_module or {}
        neighborhood_index = neighborhoods or {}
        weights = token_weights or {}

        for symbol in symbols:
            reloaded = symbol in evicted and symbol not in active_set
            evicted_symbol: str | None = None

            if symbol in active_set:
                active.remove(symbol)
                active.append(symbol)
                retained_symbols.add(symbol)
                events.append(
                    self._event(
                        symbol,
                        active,
                        retained_symbols,
                        evicted_symbol,
                        reloaded,
                        modules,
                        neighborhood_index,
                        weights,
                    )
                )
                continue

            if len(active) == active.maxlen:
                evicted_symbol = self._evict(active, active_set, evicted)

            while self._token_total([*active, symbol], weights) > self._token_limit():
                if not active:
                    break
                evicted_symbol = self._evict(active, active_set, evicted)

            if reloaded:
                evicted.remove(symbol)
            active.append(symbol)
            active_set.add(symbol)
            events.append(
                self._event(
                    symbol,
                    active,
                    retained_symbols,
                    evicted_symbol,
                    reloaded,
                    modules,
                    neighborhood_index,
                    weights,
                )
            )

        active_modules = {modules.get(symbol, self._module_from_symbol(symbol)) for symbol in active}
        active_neighborhoods = set().union(*(neighborhood_index.get(symbol, {symbol}) for symbol in active))
        return ContextWindowState(
            active_symbols=active,
            active_modules=active_modules,
            active_neighborhoods=active_neighborhoods,
            evicted=evicted,
            events=events,
            retained_symbols=retained_symbols,
        )

    def _event(
        self,
        symbol: str,
        active: deque[str],
        retained_symbols: set[str],
        evicted_symbol: str | None,
        reloaded: bool,
        modules: dict[str, str],
        neighborhoods: dict[str, set[str]],
        weights: dict[str, int],
    ) -> ContextWindowEvent:
        active_symbols = frozenset(active)
        active_modules = frozenset(modules.get(item, self._module_from_symbol(item)) for item in active)
        active_neighborhoods = frozenset().union(*(neighborhoods.get(item, {item}) for item in active))
        total_seen = len(retained_symbols | set(active))
        compression_ratio = len(active_symbols) / max(1, total_seen)
        return ContextWindowEvent(
            symbol=symbol,
            module=modules.get(symbol, self._module_from_symbol(symbol)),
            neighborhood=frozenset(neighborhoods.get(symbol, {symbol})),
            reloaded=reloaded,
            evicted=evicted_symbol,
            active_symbols=active_symbols,
            active_modules=active_modules,
            active_neighborhoods=active_neighborhoods,
            token_pressure=self._token_total(active, weights) / self._token_limit(),
            compression_ratio=round(compression_ratio, 4),
        )

    @staticmethod
    def _evict(active: deque[str], active_set: set[str], evicted: set[str]) -> str:
        evicted_symbol = active.popleft()
        active_set.remove(evicted_symbol)
        evicted.add(evicted_symbol)
        return evicted_symbol

    def _token_limit(self) -> int:
        return self.token_capacity or self.capacity

    @staticmethod
    def _token_total(symbols: list[str] | deque[str], weights: dict[str, int]) -> int:
        return sum(weights.get(symbol, 1) for symbol in symbols)

    @staticmethod
    def _module_from_symbol(symbol: str) -> str:
        if "/" in symbol or "\\" in symbol:
            return symbol.rsplit(".", 1)[0].replace("/", ".").replace("\\", ".")
        return symbol.rsplit(".", 1)[0] if "." in symbol else symbol
