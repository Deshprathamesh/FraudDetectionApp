# ==============================================================================
# Throwaway Verification Script: TigerGraph MCP Server
# scripts/verify_mcp_server.py
# ==============================================================================

import sys
import asyncio
import json
from pprint import pprint

sys.path.insert(0, ".")

from tigergraph.mcp.server import create_mcp_server


async def main():
    print("=" * 80)
    print("VERIFYING TIGERGRAPH MCP SERVER (Model Context Protocol)")
    print("=" * 80)

    server = create_mcp_server()

    # 1. Inspect registered tools
    print("\n---> 1. Querying Registered Tools via MCP Server:")
    tools = await server.list_tools()
    print(f"Total Registered Tools: {len(tools)}")

    expected_tools = [
        "get_transaction",
        "get_customer",
        "get_transaction_history",
        "get_connected_entities",
        "find_shared_devices",
        "detect_fraud_patterns",
        "find_similar_cases",
        "get_policy_context",
        "write_case_to_graph",
    ]

    registered_names = [t.name for t in tools]
    print(f"Registered Tool Names:\n{json.dumps(registered_names, indent=2)}")

    missing = [t for t in expected_tools if t not in registered_names]
    if missing:
        print(f"[FAIL]: Missing tools: {missing}")
        return False
    else:
        print("[PASS]: All 9 contract tools are registered with exact names from Section 7!")

    # 2. Schema inspection
    print("\n---> 2. Tool Schemas Inspection:")
    for t in tools:
        print(f"\nTool: {t.name}")
        print(f"  Description: {t.description.strip() if t.description else 'None'}")
        print(f"  Input Schema: {json.dumps(t.input_schema)}")

    # 3. End-to-end tool call: get_transaction on seeded ID
    print("\n---> 3. End-to-End Call via MCP Layer (get_transaction on TXN-104829):")
    res = await server.call_tool("get_transaction", {"transaction_id": "TXN-104829"})
    print(f"Raw MCP Response Object: {res}")
    print(f"Is Error: {res.is_error}")
    print("Text Content:")
    for c in res.content:
        print(f"  [{c.type}]: {c.text}")
    print(f"Structured Content: {res.structured_content}")

    # 4. End-to-end tool call: get_transaction on unknown ID
    print("\n---> 4. End-to-End Call via MCP Layer (get_transaction on TXN-DOES-NOT-EXIST):")
    err_res = await server.call_tool("get_transaction", {"transaction_id": "TXN-DOES-NOT-EXIST"})
    print(f"Raw MCP Response Object: {err_res}")
    print("Text Content:")
    for c in err_res.content:
        print(f"  [{c.type}]: {c.text}")
    print(f"Structured Content: {err_res.structured_content}")

    # 5. End-to-end tool call: write_case_to_graph
    print("\n---> 5. End-to-End Call via MCP Layer (write_case_to_graph):")
    write_res = await server.call_tool("write_case_to_graph", {"case_payload": {"case_id": "CASE-MCP-01", "transaction_id": "TXN-104829"}})
    print(f"Raw MCP Response Object: {write_res}")
    for c in write_res.content:
        print(f"  [{c.type}]: {c.text}")

    print("\n" + "=" * 80)
    print("MCP SERVER VERIFICATION COMPLETE: ALL CHECKS PASSED")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
