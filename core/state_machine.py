"""Assistant state machine management."""

from enum import Enum, auto
import threading
import time
from typing import Callable, List, Optional
from storage.logger import logger


class AssistantState(Enum):
    IDLE = auto()
    WAKE_DETECTED = auto()
    LISTENING = auto()
    PROCESSING = auto()
    EXECUTING = auto()
    SPEAKING = auto()
    ERROR = auto()
    SPEAK_ERROR = auto()


class StateMachine:
    """Manages the operational state of the assistant with transition tracking."""

    # Allowed transitions to maintain safety
    _VALID_TRANSITIONS = {
        AssistantState.IDLE: [
            AssistantState.WAKE_DETECTED,
            AssistantState.LISTENING,
            AssistantState.PROCESSING,
            AssistantState.ERROR,
        ],
        AssistantState.WAKE_DETECTED: [
            AssistantState.SPEAKING,
            AssistantState.LISTENING,
            AssistantState.IDLE,
            AssistantState.ERROR,
        ],
        AssistantState.LISTENING: [
            AssistantState.PROCESSING,
            AssistantState.SPEAKING,
            AssistantState.IDLE,
            AssistantState.ERROR,
        ],
        AssistantState.PROCESSING: [
            AssistantState.EXECUTING,
            AssistantState.SPEAKING,
            AssistantState.IDLE,
            AssistantState.ERROR,
        ],
        AssistantState.EXECUTING: [
            AssistantState.SPEAKING,
            AssistantState.IDLE,
            AssistantState.ERROR,
        ],
        AssistantState.SPEAKING: [
            AssistantState.IDLE,
            AssistantState.LISTENING,
            AssistantState.ERROR,
        ],
        AssistantState.ERROR: [
            AssistantState.SPEAK_ERROR,
            AssistantState.IDLE,
        ],
        AssistantState.SPEAK_ERROR: [
            AssistantState.IDLE,
        ],
    }

    def __init__(self, initial_state: AssistantState = AssistantState.IDLE):
        self._state = initial_state
        self._lock = threading.Lock()
        self._listeners: List[Callable[[AssistantState, AssistantState], None]] = []
        self._state_entered_time = time.time()

    @property
    def current_state(self) -> AssistantState:
        with self._lock:
            return self._state

    def add_listener(self, callback: Callable[[AssistantState, AssistantState], None]) -> None:
        """Adds an observer for state change events."""
        with self._lock:
            self._listeners.append(callback)

    def transition_to(self, new_state: AssistantState) -> bool:
        """Transitions to the target state if valid."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return True

            allowed = self._VALID_TRANSITIONS.get(old_state, [])
            if new_state not in allowed:
                logger.warning(
                    "Invalid state transition attempted: %s -> %s. Resetting to IDLE.",
                    old_state.name,
                    new_state.name,
                )
                self._state = AssistantState.IDLE
                new_state = AssistantState.IDLE
            else:
                self._state = new_state

            self._state_entered_time = time.time()
            listeners = list(self._listeners)

        logger.info("State transition: %s -> %s", old_state.name, new_state.name)
        for listener in listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                logger.error("Error in state change listener: %s", e)

        return True

    def reset_to_idle(self) -> None:
        """Safely forces state reset back to IDLE."""
        with self._lock:
            old_state = self._state
            self._state = AssistantState.IDLE
            self._state_entered_time = time.time()
            listeners = list(self._listeners)

        if old_state != AssistantState.IDLE:
            logger.info("Force reset state: %s -> IDLE", old_state.name)
            for listener in listeners:
                try:
                    listener(old_state, AssistantState.IDLE)
                except Exception as e:
                    logger.error("Error in state change listener: %s", e)
