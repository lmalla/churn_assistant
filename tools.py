from __future__ import annotations

import re
import threading

import duckdb
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "data/churn.duckdb"
CHROMA_PATH = "chroma_db"
COLLECTION = "churn_users"
MODEL_NAME = "all-MiniLM-L6-v2"

DEFAULT_ROW_CAP = 200
DEFAULT_TIMEOUT_SECONDS = 10

# Keywords that would let a query write data, change schema, load extensions,
# or otherwise act outside a plain read.
_BLOCKED_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "ATTACH", "DETACH", "COPY", "PRAGMA", "INSTALL", "LOAD", "CALL",
    "EXPORT", "IMPORT", "SET", "GRANT", "REVOKE", "VACUUM", "CHECKPOINT",
    "PREPARE", "EXECUTE", "EXPLAIN",
)
_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(_BLOCKED_KEYWORDS) + r")\b", re.IGNORECASE
)

# The only table this tool is meant to expose. Any other identifier used as a
# FROM/JOIN target is rejected — this is an allowlist, not a blocklist, so it
# can't be bypassed by a DuckDB table function or file shorthand we forgot to
# name (e.g. `parquet_scan(...)`, `sqlite_scan(...)`, `FROM '/etc/passwd'`).
_ALLOWED_TABLE = "churn"

_FROM_JOIN_KEYWORD = re.compile(r"\b(?:FROM|JOIN)\s+", re.IGNORECASE)
_CTE_NAME_PATTERN = re.compile(r"(\w+)\s+AS\s*\(", re.IGNORECASE)
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?")


def _validate_from_targets(body: str) -> str | None:
    """Return an error message if any FROM/JOIN target isn't `churn` or a CTE."""
    allowed = {_ALLOWED_TABLE} | {m.lower() for m in _CTE_NAME_PATTERN.findall(body)}

    for kw_match in _FROM_JOIN_KEYWORD.finditer(body):
        rest = body[kw_match.end():]
        if not rest or rest[0] in ("'", '"'):
            return "table references must be plain identifiers, not string literals"
        if rest[0] == "(":
            continue  # subquery — its own FROM/JOIN targets are checked separately

        id_match = _IDENTIFIER_PATTERN.match(rest)
        if not id_match:
            return "could not parse table reference"

        identifier = id_match.group(0)
        after = rest[id_match.end():].lstrip()
        if after.startswith("("):
            return f"table functions are not allowed: {identifier}"
        if identifier.lower() not in allowed:
            return f"unknown table: {identifier}"

    return None


def _validate_select_only(query: str) -> str | None:
    """Return an error message if `query` isn't a safe, single SELECT statement."""
    stripped = query.strip()
    if not stripped:
        return "empty query"

    body = stripped[:-1].strip() if stripped.endswith(";") else stripped
    if ";" in body:
        return "only a single statement is allowed"

    if not re.match(r"^(SELECT|WITH)\b", body, re.IGNORECASE):
        return "only SELECT statements are allowed"

    match = _KEYWORD_PATTERN.search(body)
    if match:
        return f"disallowed keyword: {match.group(1)}"

    return _validate_from_targets(body)

# Lazy-loaded singletons
_con = None
_model = None
_collection = None


def _get_con():
    global _con
    if _con is None:
        _con = duckdb.connect(DB_PATH, read_only=True)
    return _con


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection(COLLECTION)
    return _collection


def sql_query(
    query: str,
    row_cap: int = DEFAULT_ROW_CAP,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Execute a read-only SELECT query against the churn DuckDB table and return markdown."""
    error = _validate_select_only(query)
    if error:
        return f"SQL validation error: {error}"

    con = _get_con()
    timer = threading.Timer(timeout_seconds, con.interrupt)
    timer.start()
    try:
        df = con.execute(query).fetchdf()
    except duckdb.InterruptException:
        return f"SQL error: query timed out after {timeout_seconds}s"
    except Exception as e:
        return f"SQL error: {e}"
    finally:
        timer.cancel()

    if df.empty:
        return "Query returned no rows."

    truncated = len(df) > row_cap
    if truncated:
        df = df.head(row_cap)

    table = df.to_markdown(index=False)
    if truncated:
        table += f"\n\n_Results truncated to {row_cap} rows._"
    return table


def semantic_search(query: str, n_results: int = 5) -> str:
    """Semantic search over churn user profiles. Returns matching user summaries."""
    try:
        emb = _get_model().encode([query]).tolist()
        results = _get_collection().query(query_embeddings=emb, n_results=n_results)
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No results found."
        return "\n\n".join(f"• {d}" for d in docs)
    except Exception as e:
        return f"Retrieval error: {e}"


TOOLS = [
    {
        "name": "sql_query",
        "description": (
            "Run a SQL query against the `churn` table in DuckDB. "
            "Use for aggregations, counts, GROUP BY, filtering, and precise statistics. "
            "Schema: user_id (VARCHAR), signup_date (DATE), plan_type (VARCHAR: free/starter/pro/enterprise), "
            "monthly_spend (DOUBLE), emails_sent (INTEGER), campaigns_created (INTEGER), "
            "login_frequency_30d (INTEGER), support_tickets_30d (INTEGER), "
            "feature_usage_score (DOUBLE 0-1), last_active_date (DATE), "
            "churned (BOOLEAN), churn_reason (VARCHAR: price/support/competitor/inactivity/feature_gap or NULL)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Valid DuckDB SQL query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "semantic_search",
        "description": (
            "Semantic vector search over churn user profile text. "
            "Use for fuzzy/exploratory questions: finding users with similar behavior patterns, "
            "surfacing examples, or when aggregation SQL won't capture the nuance. "
            "Returns up to n_results user profile snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of user profiles to find",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]

TOOL_FNS = {
    "sql_query": lambda **kw: sql_query(**kw),
    "semantic_search": lambda **kw: semantic_search(**kw),
}
