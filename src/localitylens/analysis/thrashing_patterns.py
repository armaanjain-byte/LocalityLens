"""Reusable thrashing pattern detectors."""

from __future__ import annotations

from collections import Counter


def oscillation_pairs(items: list[str], width: int = 4) -> Counter[tuple[str, str]]:
    """Count A/B/A/B oscillation pairs."""
    pairs: Counter[tuple[str, str]] = Counter()
    if width != 4:
        raise ValueError("only width=4 oscillation detection is currently supported")

    for i in range(max(0, len(items) - 3)):
        a, b, c, d = items[i : i + 4]
        if a == c and b == d and a != b:
            pairs[(a, b)] += 1
    return pairs


def repeated_items(items: list[str], window: int = 6) -> int:
    """Count repeated item activations inside a small rolling window."""
    repeats = 0
    for index, item in enumerate(items):
        if item in items[max(0, index - window) : index]:
            repeats += 1
    return repeats
