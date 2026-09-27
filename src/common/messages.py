"""Shared BaseMessage <-> dict reconstruction for wire-serialized agent state.

Redis Streams and Temporal both carry LangGraph messages across a JSON
boundary as plain dicts, and each needs to turn a dict back into the right
BaseMessage subclass by its own "type" field. This is the one place that
lookup lives.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage

_MESSAGE_TYPES = {"human": HumanMessage, "ai": AIMessage, "system": SystemMessage, "tool": ToolMessage}


def message_from_dict(m):
    """Reconstruct a BaseMessage from its serialized dict (see BaseMessage.dict()) by its own
    "type" field, not blindly as one fixed class — wire payloads mix human, ai, system and tool
    messages."""
    if not isinstance(m, dict):
        return m
    msg_type = m.get("type")
    if msg_type not in _MESSAGE_TYPES:
        raise ValueError(f"Unrecognized message type {msg_type!r} in payload: {m!r}")
    return _MESSAGE_TYPES[msg_type](**m)


def messages_from_dicts(serialized: list) -> list:
    return [message_from_dict(m) for m in serialized]
