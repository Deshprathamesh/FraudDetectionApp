# ==============================================================================
# FraudGraph AI - TigerGraph Configuration
# Workstream: Person 2 (Graph)
#
# Safe configuration management. USE_MOCK_GRAPH defaults to True so that
# the system operates offline by default without requiring an active cluster.
# Live mode is opt-in by setting USE_MOCK_GRAPH=false in .env.
# ==============================================================================

import os
from typing import Optional


def _load_env_file(filepath: str = ".env"):
    """Lightweight .env reader without requiring extra external dependencies."""
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val


# Load .env if present
_load_env_file()

# Safe default: mock is active by default unless explicitly disabled
USE_MOCK_GRAPH: bool = os.getenv("USE_MOCK_GRAPH", "true").lower() not in ("false", "0", "no")

# TigerGraph Connection Details
TIGERGRAPH_HOST: str = os.getenv("TIGERGRAPH_HOST", "http://127.0.0.1")
TIGERGRAPH_REST_PORT: int = int(os.getenv("TIGERGRAPH_REST_PORT", "9000"))
TIGERGRAPH_GS_PORT: int = int(os.getenv("TIGERGRAPH_GS_PORT", "14240"))
TIGERGRAPH_USERNAME: str = os.getenv("TIGERGRAPH_USERNAME", "tigergraph")
TIGERGRAPH_PASSWORD: str = os.getenv("TIGERGRAPH_PASSWORD", "tigergraph")
TIGERGRAPH_GRAPH_NAME: str = os.getenv("TIGERGRAPH_GRAPH_NAME", "FraudGraph")
TIGERGRAPH_SECRET: Optional[str] = os.getenv("TIGERGRAPH_SECRET", None)
TIGERGRAPH_API_TOKEN: Optional[str] = os.getenv("TIGERGRAPH_API_TOKEN", None)


def get_config_summary() -> dict:
    """Returns a safe, masked summary of the current TigerGraph connection configuration."""
    return {
        "use_mock_graph": USE_MOCK_GRAPH,
        "host": TIGERGRAPH_HOST,
        "rest_port": TIGERGRAPH_REST_PORT,
        "graph_studio_port": TIGERGRAPH_GS_PORT,
        "username": TIGERGRAPH_USERNAME,
        "graph_name": TIGERGRAPH_GRAPH_NAME,
        "password_set": bool(TIGERGRAPH_PASSWORD),
    }


__all__ = [
    "USE_MOCK_GRAPH",
    "TIGERGRAPH_HOST",
    "TIGERGRAPH_REST_PORT",
    "TIGERGRAPH_GS_PORT",
    "TIGERGRAPH_USERNAME",
    "TIGERGRAPH_PASSWORD",
    "TIGERGRAPH_GRAPH_NAME",
    "TIGERGRAPH_SECRET",
    "TIGERGRAPH_API_TOKEN",
    "get_config_summary",
]
