# TigerGraph MCP Server (Model Context Protocol)

Exposes the 9 TigerGraph Agent Tool contracts defined in Section 7 of the *FraudGraph AI Integration Specification* via standard JSON-RPC 2.0 stdio transport using the official Python MCP SDK.

---

## Registered Tools (9 Tools)

| Tool Name | Input Parameters | Output | Description |
| :--- | :--- | :--- | :--- |
| `get_transaction` | `transaction_id: str` | `TransactionDetailResponse` | Details, amount, risk score, merchant, device, card network |
| `get_customer` | `customer_id: str` | `CustomerDetailResponse` | Customer profile, accounts, linked cards, risk score |
| `get_transaction_history` | `entity_id: str`, `limit: int` | `TransactionHistoryResponse` | Historical transactions and 30-day velocity/behavioral summary |
| `get_connected_entities` | `entity_id: str`, `depth: int` | `ConnectedEntitiesResponse` | Subgraph nodes + edges for investigation graph visualizer |
| `find_shared_devices` | `entity_id: str` | `SharedDevicesResponse` | Linked devices & account counts indicating syndicate rings |
| `detect_fraud_patterns` | `case_context: str` | `DetectFraudPatternsResponse` | Algorithmic fraud pattern matches & evidence references |
| `find_similar_cases` | `case_context: str` | `SimilarCasesResponse` | Similar historical closed cases, similarity scores & outcomes |
| `get_policy_context` | `action: str`, `amount: float` | `PolicyContextResponse` | Bank policy clauses, SAR requirements, approval obligations |
| `write_case_to_graph` | `case_payload: dict` | `WriteCaseResponse` | Commits investigated case to TigerGraph case memory |

---

## Running the Server Directly

From the project root:

```bash
# Run via python module execution (stdio transport)
python -m tigergraph.mcp.server
```

---

## Client Configuration Snippets

### 1. Claude Desktop / Cursor (`claude_desktop_config.json`)

To connect Claude Desktop or Cursor to this tool server, add the following entry to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tigergraph-fraudgraph": {
      "command": "python",
      "args": [
        "-m",
        "tigergraph.mcp.server"
      ],
      "cwd": "C:\\Users\\Mayan\\OneDrive\\Desktop\\goa\\FraudDetectionApp"
    }
  }
}
```

### 2. LangGraph Agent Client Integration (Person 1 — Brain)

Person 1 can connect the LangGraph agent to this MCP server either as an external stdio process using `langchain-mcp-adapters`:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async def get_agent_graph_tools():
    client = MultiServerMCPClient({
        "tigergraph": {
            "command": "python",
            "args": ["-m", "tigergraph.mcp.server"],
            "transport": "stdio",
        }
    })
    # Returns standard LangChain/LangGraph tools ready for agent binding:
    tools = await client.get_tools()
    return tools
```

Or consume the Python tool registry directly in-process:

```python
from tigergraph.tools import get_graph_tools

tools = get_graph_tools()
# Usage:
txn = tools["get_transaction"]("TXN-104829")
```
