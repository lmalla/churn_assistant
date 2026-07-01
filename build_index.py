import duckdb
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "data/churn.duckdb"
CHROMA_PATH = "chroma_db"
COLLECTION = "churn_users"
MODEL_NAME = "all-MiniLM-L6-v2"


def row_to_text(r: dict) -> str:
    status = "churned" if r["churned"] else "retained"
    reason = f", churn_reason={r['churn_reason']}" if r["churn_reason"] else ""
    tenure_days = None
    try:
        from datetime import date
        signup = date.fromisoformat(str(r["signup_date"]))
        last = date.fromisoformat(str(r["last_active_date"]))
        tenure_days = (last - signup).days
    except Exception:
        pass
    tenure_str = f", tenure={tenure_days}d" if tenure_days is not None else ""
    return (
        f"User {str(r['user_id'])[:8]} | plan={r['plan_type']} | "
        f"spend=${r['monthly_spend']}/mo | "
        f"feature_score={r['feature_usage_score']} | "
        f"logins_30d={r['login_frequency_30d']} | "
        f"tickets_30d={r['support_tickets_30d']} | "
        f"campaigns={r['campaigns_created']} | "
        f"emails={r['emails_sent']}{tenure_str} | "
        f"status={status}{reason}"
    )


def build():
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("SELECT * FROM churn").fetchall()
    cols = [d[0] for d in con.description]
    con.close()

    print(f"Loaded {len(rows)} rows from DuckDB")

    model = SentenceTransformer(MODEL_NAME)
    print(f"Loaded embedding model: {MODEL_NAME}")

    texts = [row_to_text(dict(zip(cols, r))) for r in rows]
    ids = [dict(zip(cols, r))["user_id"] for r in rows]
    metadatas = [
        {
            "plan_type": str(dict(zip(cols, r))["plan_type"]),
            "churned": str(dict(zip(cols, r))["churned"]),
            "churn_reason": str(dict(zip(cols, r))["churn_reason"] or ""),
        }
        for r in rows
    ]

    print("Generating embeddings (batch_size=64)...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True).tolist()

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Drop and recreate to allow re-runs
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION)

    print("Adding to Chroma...")
    batch = 500
    for i in range(0, len(ids), batch):
        collection.add(
            documents=texts[i:i+batch],
            embeddings=embeddings[i:i+batch],
            ids=ids[i:i+batch],
            metadatas=metadatas[i:i+batch],
        )
    print(f"Indexed {len(ids)} users into Chroma at {CHROMA_PATH}/")


if __name__ == "__main__":
    build()
