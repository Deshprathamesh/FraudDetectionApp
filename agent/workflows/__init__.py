# ==============================================================================
# FraudGraph AI - Agent Workflows Package
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

from agent.workflows.state import (
    AgentState,
    create_initial_agent_state,
    add_timeline_event,
)
from agent.workflows.engine import (
    WorkflowEngine,
    WorkflowNode,
)
from agent.workflows.workflow import (
    create_investigation_workflow,
    create_risk_assessment_workflow,
    create_nba_workflow,
    create_policy_workflow,
    next_best_action_node,
    nba_complete_node,
    policy_compliance_node,
    hitl_gate_node,
    policy_complete_node,
)

__all__ = [
    "AgentState",
    "create_initial_agent_state",
    "add_timeline_event",
    "WorkflowEngine",
    "WorkflowNode",
    "create_investigation_workflow",
    "create_risk_assessment_workflow",
    "create_nba_workflow",
    "create_policy_workflow",
    "next_best_action_node",
    "nba_complete_node",
    "policy_compliance_node",
    "hitl_gate_node",
    "policy_complete_node",
]
