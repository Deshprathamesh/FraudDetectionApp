# ==============================================================================
# FraudGraph AI - Backend Configuration
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


def _load_env_file(filepath: str = ".env") -> None:
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


# Load local environment if present
_load_env_file()


class BackendSettings(BaseModel):
    """Typed application configuration for FraudGraph AI Backend."""
    
    # Application Environment
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"))
    
    # Server Binding
    backend_host: str = Field(default_factory=lambda: os.getenv("BACKEND_HOST", "0.0.0.0"))
    backend_port: int = Field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000")))
    backend_url: str = Field(default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8000"))
    frontend_url: str = Field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:3000"))
    
    # LLM Settings (Reasoning component only - not execution authority)
    llm_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLM_API_KEY", None))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-1.5-flash"))
    
    # TigerGraph & Graph Layer
    use_mock_graph: bool = Field(
        default_factory=lambda: os.getenv("USE_MOCK_GRAPH", "true").lower() not in ("false", "0", "no")
    )
    tigergraph_host: str = Field(default_factory=lambda: os.getenv("TIGERGRAPH_HOST", "http://127.0.0.1"))
    tigergraph_rest_port: int = Field(default_factory=lambda: int(os.getenv("TIGERGRAPH_REST_PORT", "9000")))
    tigergraph_username: str = Field(default_factory=lambda: os.getenv("TIGERGRAPH_USERNAME", "tigergraph"))
    tigergraph_password: str = Field(default_factory=lambda: os.getenv("TIGERGRAPH_PASSWORD", "tigergraph"))
    tigergraph_graph_name: str = Field(default_factory=lambda: os.getenv("TIGERGRAPH_GRAPH_NAME", "FraudGraph"))
    
    # Workflow Engine Limits
    workflow_max_iterations: int = Field(default_factory=lambda: int(os.getenv("WORKFLOW_MAX_ITERATIONS", "10")))
    workflow_node_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("WORKFLOW_NODE_TIMEOUT_SECONDS", "30")))
    
    # Logging
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def get_safe_summary(self) -> Dict[str, Any]:
        """Returns a safe dictionary representation with all secrets masked."""
        return {
            "app_env": self.app_env,
            "debug": self.debug,
            "backend_host": self.backend_host,
            "backend_port": self.backend_port,
            "backend_url": self.backend_url,
            "frontend_url": self.frontend_url,
            "use_mock_graph": self.use_mock_graph,
            "tigergraph_host": self.tigergraph_host,
            "tigergraph_graph_name": self.tigergraph_graph_name,
            "llm_api_key_configured": bool(self.llm_api_key),
            "workflow_max_iterations": self.workflow_max_iterations,
            "workflow_node_timeout_seconds": self.workflow_node_timeout_seconds,
            "log_level": self.log_level,
        }


# Global settings singleton
settings = BackendSettings()

__all__ = ["BackendSettings", "settings"]
