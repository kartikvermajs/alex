"""Unit tests for StateMachine transitions and observers."""

import pytest
from core.state_machine import AssistantState, StateMachine


def test_initial_state():
    sm = StateMachine()
    assert sm.current_state == AssistantState.IDLE


def test_valid_voice_cycle_transitions():
    sm = StateMachine()

    # IDLE -> LISTENING -> PROCESSING -> EXECUTING -> SPEAKING -> IDLE
    assert sm.transition_to(AssistantState.LISTENING)
    assert sm.current_state == AssistantState.LISTENING

    assert sm.transition_to(AssistantState.PROCESSING)
    assert sm.current_state == AssistantState.PROCESSING

    assert sm.transition_to(AssistantState.EXECUTING)
    assert sm.current_state == AssistantState.EXECUTING

    assert sm.transition_to(AssistantState.SPEAKING)
    assert sm.current_state == AssistantState.SPEAKING

    assert sm.transition_to(AssistantState.IDLE)
    assert sm.current_state == AssistantState.IDLE


def test_invalid_transition_resets_safely_to_idle():
    sm = StateMachine()
    assert sm.current_state == AssistantState.IDLE

    # IDLE directly to EXECUTING is invalid
    sm.transition_to(AssistantState.EXECUTING)
    # Must safely reset to IDLE without getting stuck
    assert sm.current_state == AssistantState.IDLE


def test_state_change_listener():
    sm = StateMachine()
    history = []

    def observer(old_state, new_state):
        history.append((old_state, new_state))

    sm.add_listener(observer)
    sm.transition_to(AssistantState.LISTENING)
    sm.transition_to(AssistantState.IDLE)

    assert len(history) == 2
    assert history[0] == (AssistantState.IDLE, AssistantState.LISTENING)
    assert history[1] == (AssistantState.LISTENING, AssistantState.IDLE)


def test_reset_to_idle():
    sm = StateMachine()
    sm.transition_to(AssistantState.LISTENING)
    sm.reset_to_idle()
    assert sm.current_state == AssistantState.IDLE
