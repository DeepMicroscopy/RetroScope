"""Objective-change detection state machine.

Driven by frame brightness. State transitions:
NORMAL: brightness drops below 'dark_threshold_pct' of the average: DARK
DARK: brightness recovers above 'recovery_threshold_pct' of the average: Emit SWITCH event, return to NORMAL. 
If darkness persists past 'max_dark_ms', silently abort to NORMAL.

Note: Partially AI-generated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

DEFAULT_HISTORY_LEN = 20
DEFAULT_MIN_HISTORY = 5
DEFAULT_MAX_DARK_MS = 3000

class Phase(Enum):
    NORMAL = auto()
    DARK = auto()

class Event(Enum):
    NONE = auto()
    SWITCH = auto()

@dataclass
class DetectorState:
    phase: Phase = Phase.NORMAL
    history: list[float] = field(default_factory=list)
    dark_since_ms: float = 0.0

def step(
    state: DetectorState,
    brightness: float,
    now_ms: float,
    *,
    dark_threshold_pct: float,
    dark_duration_ms: float,
    recovery_threshold_pct: float,
    history_len: int = DEFAULT_HISTORY_LEN,
    min_history: int = DEFAULT_MIN_HISTORY,
    max_dark_ms: float = DEFAULT_MAX_DARK_MS,
) -> Event:
    """Feed one brightness sample. Mutates state and return event."""
    # Accumulate average only while stable
    if state.phase == Phase.NORMAL:
        state.history.append(brightness)
        if len(state.history) > history_len:
            state.history.pop(0)

    if len(state.history) < min_history:
        return Event.NONE

    avg = sum(state.history) / len(state.history)
    if avg < 1.0:
        return Event.NONE   # all-black scene: Ignore

    if state.phase == Phase.NORMAL:
        if brightness < avg * dark_threshold_pct / 100.0:
            state.phase = Phase.DARK
            state.dark_since_ms = now_ms
        return Event.NONE

    # Phase.DARK
    elapsed = now_ms - state.dark_since_ms
    if elapsed > max_dark_ms:
        state.phase = Phase.NORMAL
        return Event.NONE

    if brightness > avg * recovery_threshold_pct / 100.0:
        if elapsed >= dark_duration_ms:
            state.phase = Phase.NORMAL
            state.history.clear()
            return Event.SWITCH
        # Too brief (e.g. slide change)
        state.phase = Phase.NORMAL
    return Event.NONE
