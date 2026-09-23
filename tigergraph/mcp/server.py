# ==============================================================================
# FraudGraph AI - TigerGraph Model Context Protocol (MCP) Server
# Workstream: Person 2 (Graph)
#
# Exposes all 9 contract tools from tigergraph/tools.py over standard JSON-RPC
# 2.0 stdio transport via the official Model Context Protocol (MCP) Python SDK.
# Ready for consumption by LangGraph MCP clients, Claude Desktop, and Cursor.
# ==============================================================================

import sys
import os
from typing import Dict, Any, Union

# Ensure project root is in sys.path when executed directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Support both MCP SDK 2.x (MCPServer) and 1.x (FastMCP)
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
    except ImportError as e:
        raise ImportError(
            "The official MCP Python SDK is required. Please install with 'pip install mcp'."
        ) from e

from tigergraph.tools import (
    get_transaction,
    get_customer,
    get_transaction_history,
    get_connected_entities,
    find_shared_devices,
    detect_fraud_patterns,
    find_similar_cases,
    get_policy_context,
    write_case_to_graph,
    WriteCaseResponse,
)


def _mcp_write_case_to_graph(case_payload: Dict[str, Any]) -> Union[WriteCaseResponse, Dict[str, Any]]:
    """Commits an investigated fraud case payload into TigerGraph case memory."""
    return write_case_to_graph(case_payload=case_payload)


def create_mcp_server() -> MCPServer:
    """
    Initializes and configures the TigerGraph MCP Server.
    Registers all 9 contract tools matching Section 7 of the Integration Specification.
    """
    server = MCPServer(
        name="tigergraph-fraudgraph",
        instructions=(
            "TigerGraph FraudGraph AI Tool Server. Provides graph analytics, customer profiles, "
            "transaction history, fraud pattern detection, similar case memory retrieval, "
            "policy and SAR threshold checks, and case-memory persistence for fraud investigations."
        )
    )

    # Register all 9 tools using their exact contract names and docstrings
    server.add_tool(
        get_transaction,
        name="get_transaction",
        description="Retrieve transaction details including amount, risk score, merchant, device, card network, and behavioral attributes for a given transaction_id."
    )

    server.add_tool(
        get_customer,
        name="get_customer",
        description="Retrieve customer profile, risk tier, linked accounts, cards, email, and historical customer risk score for a given customer_id."
    )

    server.add_tool(
        get_transaction_history,
        name="get_transaction_history",
        description="Retrieve historical transaction records and behavioral summary (velocity, 30-day baseline, average amount, risk distribution) for a customer or account."
    )

    server.add_tool(
        get_connected_entities,
        name="get_connected_entities",
        description="Perform multi-hop graph BFS traversal returning connected nodes and edges (transactions, devices, IPs, merchants) for investigation visualization."
    )

    server.add_tool(
        find_shared_devices,
        name="find_shared_devices",
        description="Query TigerGraph for devices linked across multiple customer accounts to detect device-hopping syndicates and account takeover rings."
    )

    server.add_tool(
        detect_fraud_patterns,
        name="detect_fraud_patterns",
        description="Execute algorithmic graph pattern detection (syndicates, velocity bursts, mule daisy-chains, Tor/proxy churn, card testing) and return evidence references."
    )

    server.add_tool(
        find_similar_cases,
        name="find_similar_cases",
        description="Retrieve similar historical closed cases, similarity scores, matched pattern typologies, and past investigation outcomes from graph memory."
    )

    server.add_tool(
        get_policy_context,
        name="get_policy_context",
        description="Retrieve governing bank fraud policy clauses, mandatory SAR filing requirements, and human approval obligations for a proposed investigation action."
    )

    server.add_tool(
        _mcp_write_case_to_graph,
        name="write_case_to_graph",
        description="Commit an investigated fraud case payload (status, evidence, findings, decisions, actions) into TigerGraph case memory for audit and future retrieval."
    )

    return server


# Global server instance
mcp_server = create_mcp_server()


def main():
    """Runs the MCP server over standard input/output (stdio) transport."""
    # stdio transport is standard for sub-process execution by MCP clients
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
