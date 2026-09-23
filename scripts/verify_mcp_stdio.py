# ==============================================================================
# Throwaway Subprocess Stdio Verification Script
# scripts/verify_mcp_stdio.py
# ==============================================================================

import subprocess
import json
import sys

def test_stdio_server():
    print("Testing tigergraph.mcp.server via subprocess over stdio...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "tigergraph.mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Send MCP Initialize Request (JSON-RPC 2.0)
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }

    try:
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        print(f"Server response to initialize:\n{response_line}")
        response = json.loads(response_line)
        assert response.get("id") == 1
        assert "result" in response
        server_info = response["result"].get("serverInfo", {})
        print(f"[PASS]: Initialized MCP server over stdio! Server name: {server_info.get('name')}")

        # Send tools/list request
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        proc.stdin.write(json.dumps(list_request) + "\n")
        proc.stdin.flush()

        tools_line = proc.stdout.readline()
        tools_resp = json.loads(tools_line)
        tools = tools_resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        print(f"[PASS]: tools/list returned {len(tools)} tools: {tool_names}")
        assert len(tools) == 9

        # Send tools/call for get_transaction
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_transaction",
                "arguments": {"transaction_id": "TXN-104829"}
            }
        }
        proc.stdin.write(json.dumps(call_request) + "\n")
        proc.stdin.flush()

        call_line = proc.stdout.readline()
        call_resp = json.loads(call_line)
        print(f"[PASS]: tools/call get_transaction response: {json.dumps(call_resp, indent=2)}")
        assert call_resp.get("id") == 3

    finally:
        proc.terminate()
        proc.wait(timeout=3)

if __name__ == "__main__":
    test_stdio_server()
