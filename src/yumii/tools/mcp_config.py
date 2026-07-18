"""Load MCP server entries from config.json for MultiServerMCPClient (thin; no adapter import)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yumii.core.global_config import CONFIG_FILE, load_global_config
from yumii.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class MCPServerConfig:
    """One MCP server entry (name, command, args, transport, env)."""

    name: str
    command: str
    args: tuple[str, ...]
    transport: str = "stdio"
    env: dict[str, str] | None = None

    def to_adapter_dict(self) -> dict[str, Any]:
        """Render this config as the {command, args, transport, env} dict the adapter expects."""
        out: dict[str, Any] = {
            "command": self.command,
            "args": list(self.args),
            "transport": self.transport,
        }
        if self.env:
            out["env"] = dict(self.env)
        return out


def _parse_server_entry(raw: dict[str, Any]) -> MCPServerConfig | None:
    """Parse one entry from ``MCP_SERVERS``. Returns None on bad data."""
    if not isinstance(raw, dict):
        log.warning("mcp_server_entry_not_dict", entry=raw)
        return None

    name = raw.get("name")
    command = raw.get("command")
    if not name or not command:
        log.warning(
            "mcp_server_entry_missing_fields",
            entry=raw,
            required=["name", "command"],
        )
        return None

    args_raw = raw.get("args", [])
    if not isinstance(args_raw, list):
        log.warning("mcp_server_args_not_list", name=name, args=args_raw)
        return None

    transport = raw.get("transport", "stdio")
    if transport not in {"stdio", "sse", "websocket", "streamable_http"}:
        log.warning("mcp_server_unknown_transport", name=name, transport=transport)
        return None

    env_raw = raw.get("env")
    env: dict[str, str] | None = None
    if env_raw is not None:
        if not isinstance(env_raw, dict):
            log.warning("mcp_server_env_not_dict", name=name, env=env_raw)
            return None
        env = {str(k): str(v) for k, v in env_raw.items()}

    return MCPServerConfig(
        name=str(name),
        command=str(command),
        args=tuple(str(a) for a in args_raw),
        transport=str(transport),
        env=env,
    )


def load_mcp_servers() -> list[MCPServerConfig]:
    """Read config.json and return the configured MCP servers ([] if none/malformed; never raises)."""
    if not CONFIG_FILE.exists():
        log.debug("mcp_config_file_missing", path=str(CONFIG_FILE))
        return []

    config = load_global_config()
    raw_list = config.get("MCP_SERVERS")
    if raw_list is None:
        log.debug("mcp_no_servers_configured")
        return []
    if not isinstance(raw_list, list):
        log.warning("mcp_servers_not_list", value=raw_list)
        return []

    parsed: list[MCPServerConfig] = []
    for entry in raw_list:
        result = _parse_server_entry(entry)
        if result is not None:
            parsed.append(result)
    log.info("mcp_servers_loaded", count=len(parsed))
    return parsed


def adapter_dicts() -> dict[str, dict[str, Any]]:
    """Return the configs as the {name: {...}} dict MultiServerMCPClient expects."""
    return {cfg.name: cfg.to_adapter_dict() for cfg in load_mcp_servers()}


__all__ = [
    "MCPServerConfig",
    "load_mcp_servers",
    "adapter_dicts",
]


# Re-export for callers that want to assert where the file lives.
__all__.append("CONFIG_FILE_PATH")
CONFIG_FILE_PATH = Path(CONFIG_FILE)
