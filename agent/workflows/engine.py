# ==============================================================================
# FraudGraph AI - Pure-Python Typed Workflow Engine
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import logging
from typing import Dict, Any, Callable, List, Optional, Union
from agent.workflows.state import AgentState
from backend.errors import WorkflowLoopLimitExceeded, FraudGraphException

logger = logging.getLogger("fraudgraph.workflow_engine")

NodeCallable = Callable[[AgentState], AgentState]
RouterCallable = Callable[[AgentState], str]


class WorkflowNode:
    """Represents an executable node in the workflow graph."""

    def __init__(self, name: str, func: NodeCallable):
        self.name = name
        self.func = func

    def execute(self, state: AgentState) -> AgentState:
        return self.func(state)


class WorkflowEngine:
    """
    Pure-Python, typed state machine workflow engine.
    Mirrors LangGraph StateGraph API semantics and execution guarantees:
    - Typed state passing
    - Deterministic edges
    - Conditional edge routing
    - Explicit terminal node halting
    - Loop count limit & recursion guard
    """

    def __init__(self):
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, tuple[RouterCallable, Optional[Dict[str, str]]]] = {}
        self.entry_point: Optional[str] = None
        self.terminal_nodes: set[str] = set()

    def add_node(self, name: str, func: NodeCallable) -> "WorkflowEngine":
        """Registers a node function with a unique name."""
        self.nodes[name] = WorkflowNode(name, func)
        return self

    def set_entry_point(self, name: str) -> "WorkflowEngine":
        """Sets the starting node for graph execution."""
        if name not in self.nodes:
            raise ValueError(f"Entry point node '{name}' is not registered.")
        self.entry_point = name
        return self

    def add_edge(self, from_node: str, to_node: str) -> "WorkflowEngine":
        """Adds a direct deterministic transition from one node to another."""
        if from_node not in self.nodes:
            raise ValueError(f"Source node '{from_node}' is not registered.")
        self.edges[from_node] = to_node
        return self

    def add_conditional_edges(
        self,
        from_node: str,
        router: RouterCallable,
        path_map: Optional[Dict[str, str]] = None,
    ) -> "WorkflowEngine":
        """
        Adds conditional routing out of a node based on state inspection.
        router(state) returns a branch key.
        """
        if from_node not in self.nodes:
            raise ValueError(f"Source node '{from_node}' is not registered.")
        self.conditional_edges[from_node] = (router, path_map)
        return self

    def set_terminal_nodes(self, names: List[str]) -> "WorkflowEngine":
        """Designates nodes that represent terminal workflow states."""
        self.terminal_nodes = set(names)
        return self

    def run(self, initial_state: AgentState) -> AgentState:
        """
        Executes the workflow graph starting from the entry point.
        Enforces maximum iteration bounding and records node transitions.
        """
        if not self.entry_point:
            raise ValueError("Workflow entry point is not set.")

        state = dict(initial_state) # Shallow copy of dictionary
        current_node_name = self.entry_point
        max_iters = state.get("max_iterations", 25)

        while current_node_name:
            # Check iteration limit
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            if state["iteration_count"] > max_iters:
                err_msg = f"Workflow loop limit exceeded: {state['iteration_count']} > {max_iters}"
                logger.error(err_msg)
                if "errors" not in state or state["errors"] is None:
                    state["errors"] = []
                state["errors"].append({
                    "code": "WORKFLOW_LOOP_LIMIT_EXCEEDED",
                    "message": err_msg,
                    "iteration": state["iteration_count"],
                })
                state["current_workflow_state"] = "FAILED"
                raise WorkflowLoopLimitExceeded(
                    iteration_count=state["iteration_count"],
                    max_iterations=max_iters,
                )

            # Retrieve node
            node = self.nodes.get(current_node_name)
            if not node:
                raise ValueError(f"Referenced node '{current_node_name}' is not registered.")

            state["current_workflow_state"] = current_node_name
            logger.debug(f"[Workflow] Executing node '{current_node_name}' (iter {state['iteration_count']})")

            # Execute node
            try:
                state = node.execute(state)
            except Exception as e:
                logger.error(f"[Workflow] Node '{current_node_name}' raised an error: {e}", exc_info=False)
                if "errors" not in state or state["errors"] is None:
                    state["errors"] = []

                error_detail = {
                    "node": current_node_name,
                    "error": str(e),
                    "code": getattr(e, "code", "NODE_EXECUTION_ERROR"),
                }
                state["errors"].append(error_detail)
                state["current_workflow_state"] = "FAILED"
                return state

            # Check if this node is terminal
            if current_node_name in self.terminal_nodes:
                logger.debug(f"[Workflow] Reached terminal node '{current_node_name}'. Halting execution.")
                break

            # Determine next node
            next_node = None
            if current_node_name in self.conditional_edges:
                router, path_map = self.conditional_edges[current_node_name]
                route_key = router(state)
                if path_map and route_key in path_map:
                    next_node = path_map[route_key]
                else:
                    next_node = route_key
            elif current_node_name in self.edges:
                next_node = self.edges[current_node_name]

            current_node_name = next_node

        return state
