# ==============================================================================
# FraudGraph AI - Backend API Package
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from backend.api.app import create_app, app
from backend.api.routes import router

__all__ = ["create_app", "app", "router"]
