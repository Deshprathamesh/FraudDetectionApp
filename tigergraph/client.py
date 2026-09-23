# ==============================================================================
# FraudGraph AI - TigerGraph Live Client
# Workstream: Person 2 (Graph)
#
# Manages live connections to TigerGraph (Savanna Cloud / Community Edition)
# via pyTigerGraph. Supports schema loading, GSQL execution, and vertex/edge counts.
# ==============================================================================

import os
import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

try:
    from tigergraph import config
except ImportError:
    import config

try:
    import pyTigerGraph as tg
except ImportError:
    tg = None


class SchemaLoadResult(dict):
    """Result of load_schema execution containing statement metrics and error details."""

    def __str__(self) -> str:
        lines = [
            "================== SCHEMA LOAD SUMMARY ==================",
            f"Total statements: {self.get('total_statements', 0)}",
            f"Succeeded: {self.get('succeeded', 0)}",
            f"Failed: {self.get('failed', 0)}",
        ]
        first_failure = self.get("first_failure")
        if first_failure:
            lines.extend([
                f"\nFirst failure at statement {first_failure.get('statement_number')}:",
                f"Statement text:\n{first_failure.get('statement_text')}",
                f"\nError:\n{first_failure.get('error')}",
            ])
        lines.append("=========================================================")
        return "\n".join(lines)


def split_gsql_statements(content: str) -> list:
    """Splits GSQL script into individual statements on semicolons outside of string literals and comments.
    Lines starting with 'DROP GRAPH' (case-insensitive) are treated as standalone statements ending at the newline.
    """
    statements = []
    curr = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    lines = content.splitlines(keepends=True)
    for line in lines:
        stripped_line = line.strip()
        # Check if line starts with DROP GRAPH when not inside a multiline block/string
        if not in_block_comment and not in_single_quote and not in_double_quote:
            clean_check = stripped_line
            while clean_check.startswith(("//", "#", "--")):
                clean_check = clean_check.lstrip("/#-").strip()

            if clean_check.upper().startswith("DROP GRAPH"):
                prev_stmt = "".join(curr).strip()
                if prev_stmt:
                    has_code = any(
                        not l.strip().startswith(("//", "#", "--")) and l.strip()
                        for l in prev_stmt.splitlines()
                    )
                    if has_code:
                        statements.append(prev_stmt)
                curr = []
                drop_stmt = clean_check.rstrip(";").strip()
                if drop_stmt:
                    statements.append(drop_stmt)
                continue

        # Character parsing within the line
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            next_ch = line[i + 1] if i + 1 < n else ""

            if escape:
                curr.append(ch)
                escape = False
                i += 1
                continue

            if (in_single_quote or in_double_quote) and ch == "\\":
                escape = True
                curr.append(ch)
                i += 1
                continue

            # Check line comments (//, --, #)
            if not in_single_quote and not in_double_quote and not in_block_comment:
                if not in_line_comment:
                    if (ch == "/" and next_ch == "/") or (ch == "-" and next_ch == "-"):
                        in_line_comment = True
                        curr.append(ch)
                        curr.append(next_ch)
                        i += 2
                        continue
                    elif ch == "#":
                        in_line_comment = True
                        curr.append(ch)
                        i += 1
                        continue
                else:
                    if ch == "\n":
                        in_line_comment = False
                    curr.append(ch)
                    i += 1
                    continue

            # Check block comments (/* ... */)
            if not in_single_quote and not in_double_quote and not in_line_comment:
                if not in_block_comment:
                    if ch == "/" and next_ch == "*":
                        in_block_comment = True
                        curr.append(ch)
                        curr.append(next_ch)
                        i += 2
                        continue
                else:
                    if ch == "*" and next_ch == "/":
                        in_block_comment = False
                        curr.append(ch)
                        curr.append(next_ch)
                        i += 2
                        continue
                    curr.append(ch)
                    i += 1
                    continue

            # Check string literals
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif ch == ";" and not in_single_quote and not in_double_quote:
                stmt = "".join(curr).strip()
                if stmt:
                    has_code = any(
                        not l.strip().startswith(("//", "#", "--")) and l.strip()
                        for l in stmt.splitlines()
                    )
                    if has_code:
                        statements.append(stmt)
                curr = []
                i += 1
                continue

            curr.append(ch)
            i += 1

    remaining = "".join(curr).strip()
    if remaining:
        has_code = any(
            not l.strip().startswith(("//", "#", "--")) and l.strip()
            for l in remaining.splitlines()
        )
        if has_code:
            statements.append(remaining)

    return statements


def is_gsql_error(resp_str: str) -> bool:
    """Checks if a GSQL response string indicates an error."""
    if not resp_str:
        return False
    error_indicators = [
        "Semantic Check Fails",
        "semantic check fails",
        "Failed to create",
        "Failed to drop",
        "Encountered ",
        "The specified Identifier",
        "Syntax Error",
        "syntax error",
        "Was expecting one of",
        "could not be created!",
    ]
    return any(ind in resp_str for ind in error_indicators)


def is_drop_graph_nonfatal_warning(stmt: str, err_or_resp: str) -> bool:
    """Checks if an error on DROP GRAPH is the expected non-fatal warning (graph does not exist yet)."""
    first_non_comment = ""
    for line in stmt.splitlines():
        l_str = line.strip()
        if l_str and not l_str.startswith(("//", "#", "--")):
            first_non_comment = l_str
            break
    if not first_non_comment.upper().startswith("DROP GRAPH"):
        return False

    lower_msg = err_or_resp.lower()
    return "could not be dropped" in lower_msg or "does not exist" in lower_msg


class TigerGraphLiveClient:
    """Live TigerGraph connection and GSQL execution manager."""

    def __init__(
        self,
        host: Optional[str] = None,
        rest_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        graph_name: Optional[str] = None,
        secret: Optional[str] = None,
    ):
        self.host = host or config.TIGERGRAPH_HOST
        self.rest_port = rest_port or config.TIGERGRAPH_REST_PORT
        self.username = username or config.TIGERGRAPH_USERNAME
        self.password = password or config.TIGERGRAPH_PASSWORD
        # TigerGraph Cloud (Savanna) issues a Database Secret stored in TIGERGRAPH_PASSWORD / TIGERGRAPH_SECRET
        self.secret = secret or config.TIGERGRAPH_SECRET or config.TIGERGRAPH_PASSWORD
        self.graph_name = graph_name or config.TIGERGRAPH_GRAPH_NAME
        self._conn = None

    def get_connection(self):
        """Initializes or returns cached pyTigerGraph connection using secret-based token retrieval."""
        if self._conn is not None:
            return self._conn

        if tg is None:
            raise RuntimeError("pyTigerGraph is not installed. Run 'pip install pyTigerGraph'.")

        # 1. Initialize TigerGraphConnection with host and graphname only (no username/password)
        conn = tg.TigerGraphConnection(
            host=self.host,
            restppPort=self.rest_port,
            graphname=self.graph_name,
        )

        # 2. Call conn.getToken(secret) using secret value from TIGERGRAPH_PASSWORD and set returned token
        secret = self.secret or self.password
        if secret:
            # pyTigerGraph sets a default Basic Auth header ('tigergraph:tigergraph') in _cached_auth.
            # TigerGraph Cloud rejects token retrieval if invalid Basic Auth headers are present.
            # Removing Authorization ensures the request authenticates solely via the secret payload.
            if hasattr(conn, "_cached_auth"):
                conn._cached_auth.pop("Authorization", None)

            token_res = conn.getToken(secret)
            token = token_res[0] if isinstance(token_res, tuple) else token_res
            conn.apiToken = token
            conn.authMode = "token"
            if hasattr(conn, "_refresh_auth_headers"):
                conn._refresh_auth_headers()

        self._conn = conn
        return self._conn

    def test_connection(self) -> Dict[str, Any]:
        """Tests if the TigerGraph server is reachable via REST++ echo / ping."""
        try:
            conn = self.get_connection()
            echo_res = conn.echo()
            return {
                "connected": True,
                "host": self.host,
                "graph_name": self.graph_name,
                "token_acquired": bool(getattr(conn, "apiToken", None)),
                "message": echo_res,
            }
        except Exception as e:
            return {
                "connected": False,
                "host": self.host,
                "graph_name": self.graph_name,
                "error": str(e),
            }

    def run_gsql(self, query: str) -> str:
        """Executes a GSQL command or query on the TigerGraph instance."""
        conn = self.get_connection()
        return conn.gsql(query)

    def load_schema(self, schema_file_path: str) -> SchemaLoadResult:
        """Loads and executes a GSQL schema DDL file statement by statement.

        1. Reads the .gsql file.
        2. Splits its contents into individual statements on semicolons (and DROP GRAPH lines).
        3. Strips empty/whitespace-only statements and trailing semicolons.
        4. Sends each non-empty statement to conn.gsql() one at a time, in order.
        5. Tolerates expected "could not be dropped" / "does not exist" non-fatal warnings on DROP GRAPH.
        6. Stops immediately and reports the exact error and which statement number/text failed,
           if any statement fails.
        7. Reports a summary at the end: how many statements succeeded, how many failed,
           and the first failure if any.
        """
        if not os.path.exists(schema_file_path):
            raise FileNotFoundError(f"Schema file not found at: {schema_file_path}")

        with open(schema_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        statements = split_gsql_statements(content)
        conn = self.get_connection()

        total = len(statements)
        succeeded = 0
        failed = 0
        first_failure = None
        results = []

        for idx, stmt in enumerate(statements, start=1):
            cleaned_stmt = stmt.rstrip(";").strip()
            if not cleaned_stmt:
                continue

            try:
                res = conn.gsql(cleaned_stmt)
                if is_gsql_error(res):
                    if is_drop_graph_nonfatal_warning(cleaned_stmt, res):
                        logger.warning("Statement %d (DROP GRAPH) non-fatal warning: %s", idx, res.strip())
                        succeeded += 1
                        results.append({
                            "statement_number": idx,
                            "status": "warning_ignored",
                            "output": res.strip()
                        })
                    else:
                        failed += 1
                        first_failure = {
                            "statement_number": idx,
                            "statement_text": cleaned_stmt,
                            "error": res.strip(),
                        }
                        results.append({"statement_number": idx, "status": "failed", "error": res.strip()})
                        break
                else:
                    if is_drop_graph_nonfatal_warning(cleaned_stmt, res):
                        succeeded += 1
                        results.append({
                            "statement_number": idx,
                            "status": "warning_ignored",
                            "output": res.strip()
                        })
                    else:
                        succeeded += 1
                        results.append({"statement_number": idx, "status": "succeeded", "output": res.strip()})
            except Exception as e:
                err_msg = str(e).strip()
                if is_drop_graph_nonfatal_warning(cleaned_stmt, err_msg):
                    logger.warning("Statement %d (DROP GRAPH) non-fatal exception: %s", idx, err_msg)
                    succeeded += 1
                    results.append({
                        "statement_number": idx,
                        "status": "warning_ignored",
                        "output": err_msg
                    })
                else:
                    failed += 1
                    first_failure = {
                        "statement_number": idx,
                        "statement_text": cleaned_stmt,
                        "error": err_msg,
                    }
                    results.append({"statement_number": idx, "status": "failed", "error": err_msg})
                    break

        result = SchemaLoadResult({
            "total_statements": total,
            "succeeded": succeeded,
            "failed": failed,
            "first_failure": first_failure,
            "results": results,
        })
        return result

    def get_vertex_counts(self) -> Dict[str, int]:
        """Queries the current count of vertices for each vertex type."""
        conn = self.get_connection()
        return conn.getVertexCount("*")

    def get_edge_counts(self) -> Dict[str, int]:
        """Queries the current count of edges for each edge type."""
        conn = self.get_connection()
        return conn.getEdgeCount("*")

    def write_case_to_graph(self, case_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Tool 9 live implementation: writes FraudCase, Evidence, and ActionRecord to live TigerGraph."""
        conn = self.get_connection()
        case_id = case_payload.get("case_id")
        if not case_id:
            raise RuntimeError("Case payload missing required 'case_id' field.")

        txn_id = case_payload.get("transaction_id", "")
        cust_id = case_payload.get("customer_id", "")
        status = case_payload.get("status", "INVESTIGATING")
        risk_score = float(case_payload.get("risk_score", 0.0))
        confidence = float(case_payload.get("confidence", 0.0))
        created_at = int(case_payload.get("created_at", 0)) or int(time.time())
        summary = case_payload.get("summary", "")

        conn.upsertVertex("FraudCase", case_id, {
            "transaction_id": txn_id,
            "customer_id": cust_id,
            "status": status,
            "risk_score": risk_score,
            "confidence": confidence,
            "created_at": created_at,
            "summary": summary
        })

        generated_graph_ids = [f"vertex_fraudcase_{case_id}"]
        nodes_written = 1
        edges_written = 0

        if txn_id:
            try:
                conn.upsertEdge("FraudCase", case_id, "INVOLVED_IN_CASE", "Transaction", txn_id)
                generated_graph_ids.append(f"edge_involved_{txn_id}")
                edges_written += 1
            except Exception as e:
                logger.warning("Could not link INVOLVED_IN_CASE: %s", e)

        if cust_id:
            try:
                conn.upsertEdge("FraudCase", case_id, "LINKED_CUSTOMER", "Customer", cust_id)
                generated_graph_ids.append(f"edge_customer_{cust_id}")
                edges_written += 1
            except Exception as e:
                logger.warning("Could not link LINKED_CUSTOMER: %s", e)

        for ev in case_payload.get("evidence", []):
            ev_id = ev.get("evidence_id") or ev.get("id")
            if ev_id:
                ev_type = ev.get("evidence_type") or ev.get("type", "UNKNOWN")
                ev_src = ev.get("source", "tigergraph")
                ev_sum = ev.get("summary", "")
                ev_conf = float(ev.get("confidence", 0.0))
                ev_ts = int(ev.get("timestamp", 0)) or int(time.time())
                conn.upsertVertex("Evidence", ev_id, {
                    "evidence_type": ev_type,
                    "source": ev_src,
                    "summary": ev_sum,
                    "confidence": ev_conf,
                    "timestamp": ev_ts
                })
                conn.upsertEdge("FraudCase", case_id, "HAS_EVIDENCE", "Evidence", ev_id)
                generated_graph_ids.append(f"vertex_evidence_{ev_id}")
                generated_graph_ids.append(f"edge_has_evidence_{ev_id}")
                nodes_written += 1
                edges_written += 1

        for act in case_payload.get("action_records", case_payload.get("actions", [])):
            act_id = act.get("action_id") or act.get("id")
            if act_id:
                act_type = act.get("action_type") or act.get("type", "MONITOR")
                act_status = act.get("status", "PENDING")
                act_req_at = int(act.get("requested_at", 0)) or int(time.time())
                act_exec_at = int(act.get("executed_at", 0))
                act_approval = bool(act.get("approval", False))
                conn.upsertVertex("ActionRecord", act_id, {
                    "action_type": act_type,
                    "status": act_status,
                    "requested_at": act_req_at,
                    "executed_at": act_exec_at,
                    "approval": act_approval
                })
                conn.upsertEdge("FraudCase", case_id, "EXECUTED_ACTION", "ActionRecord", act_id)
                generated_graph_ids.append(f"vertex_actionrecord_{act_id}")
                generated_graph_ids.append(f"edge_executed_action_{act_id}")
                nodes_written += 1
                edges_written += 1

        for pat in case_payload.get("fraud_patterns", []):
            pat_id = pat.get("pattern_id") or pat.get("id") if isinstance(pat, dict) else pat
            if isinstance(pat_id, str) and pat_id:
                try:
                    conn.upsertEdge("FraudCase", case_id, "DETECTED_PATTERN", "FraudPattern", pat_id)
                    generated_graph_ids.append(f"edge_detected_pattern_{pat_id}")
                    edges_written += 1
                except Exception as e:
                    logger.warning("Could not link DETECTED_PATTERN: %s", e)

        return {
            "status": "SUCCESS",
            "case_id": case_id,
            "graph_ids": generated_graph_ids,
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "message": f"Case '{case_id}' successfully committed to TigerGraph case memory."
        }


# Default client instance
live_client = TigerGraphLiveClient()

__all__ = [
    "TigerGraphLiveClient",
    "live_client",
    "split_gsql_statements",
    "is_gsql_error",
    "is_drop_graph_nonfatal_warning",
    "SchemaLoadResult"
]

if __name__ == "__main__":
    print("Testing connection...")
    conn_result = live_client.test_connection()
    print("test_connection() result:")
    print(conn_result)
