import logging
from types import SimpleNamespace
from unittest.mock import patch

import agent


def _tool_use_response(tool_name="sql_query", tool_input=None, tool_use_id="t1"):
    block = SimpleNamespace(
        type="tool_use",
        id=tool_use_id,
        name=tool_name,
        input=tool_input or {"query": "SELECT 1"},
    )
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def _end_turn_response(text="final answer"):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason="end_turn")


def test_run_agent_stops_after_max_iterations():
    responses = [_tool_use_response() for _ in range(10)]
    with patch.object(agent.client.messages, "create", side_effect=responses) as create, \
         patch.object(agent, "TOOL_FNS", {"sql_query": lambda **kw: "ok"}):
        result = agent.run_agent("some question", max_iterations=3)

    assert create.call_count == 3
    assert "iteration" in result.lower()


def test_run_agent_returns_text_on_end_turn():
    responses = [_tool_use_response(), _end_turn_response("the answer")]
    with patch.object(agent.client.messages, "create", side_effect=responses), \
         patch.object(agent, "TOOL_FNS", {"sql_query": lambda **kw: "ok"}):
        result = agent.run_agent("some question", max_iterations=8)

    assert result == "the answer"


def test_run_agent_logs_tool_calls(caplog):
    responses = [_tool_use_response(tool_input={"query": "SELECT 1"}), _end_turn_response()]
    with patch.object(agent.client.messages, "create", side_effect=responses), \
         patch.object(agent, "TOOL_FNS", {"sql_query": lambda **kw: "result-data"}), \
         caplog.at_level(logging.INFO, logger="agent"):
        agent.run_agent("some question", max_iterations=8)

    messages = "\n".join(caplog.messages)
    assert "sql_query" in messages
    assert "SELECT 1" in messages
    assert "result-data" in messages
