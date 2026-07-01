import duckdb
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "data/churn.duckdb"
CHROMA_PATH = "chroma_db"
COLLECTION = "churn_users"
MODEL_NAME = "all-MiniLM-L6-v2"

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


def sql_query(query: str) -> str:
    """Execute a SQL query against the churn DuckDB table and return markdown."""
    try:
        df = _get_con().execute(query).fetchdf()
        if df.empty:
            return "Query returned no rows."
        return df.to_markdown(index=False)
    except Exception as e:
        return f"SQL error: {e}"


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
