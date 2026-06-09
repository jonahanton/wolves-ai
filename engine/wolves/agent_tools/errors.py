from __future__ import annotations


class AgentToolError(Exception):
    pass


class ToolTimeoutError(AgentToolError):
    def __init__(self, tool_name: str, timeout_seconds: float) -> None:
        super().__init__(f"{tool_name} timed out after {timeout_seconds:.0f}s")
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds


class ToolDispatchError(AgentToolError):
    pass
