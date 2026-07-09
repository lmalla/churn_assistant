# AI Churn Analytics Assistant

A demo-ready, laptop-local AI assistant that answers business questions about user churn using natural language. Combines a SQL analytics layer with semantic vector search, orchestrated by a Claude-powered agent, surfaced through a Streamlit UI.

---

## Architecture

```
User Question (Streamlit)
        │
        ▼
  Claude Agent (tool_use)
  ├── sql_query  ──►  DuckDB          ← precise aggregations & statistics
  └── semantic_search ──► Chroma      ← fuzzy pattern discovery
                            │
                    sentence-transformers
                    (all-MiniLM-L6-v2, runs offline)
```

| Layer | Tool | Why |
|---|---|---|
| LLM / Agent | Claude API (`claude-haiku-4-5`) | Fast, cheap, native tool_use |
| Database | DuckDB (embedded) | Zero-config, fast analytics SQL |
| Vector store | Chroma (local) | Free, persistent, works offline |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | Free, ~90 MB, runs on CPU |
| App | Streamlit | Minimal boilerplate, demo-ready |

> **Why not Databricks?** Community Edition is cloud-only. Vector Search and Databricks Apps are enterprise-only features. This stack gives identical capability with zero cost and zero cloud dependency.

---

## Dataset

Synthetic churn data modelled after a subscription-based SaaS product.

| Column | Type | Description |
|---|---|---|
| `user_id` | UUID | Unique user identifier |
| `signup_date` | DATE | Account creation date |
| `plan_type` | VARCHAR | `free` / `starter` / `pro` / `enterprise` |
| `monthly_spend` | DOUBLE | Monthly revenue from user |
| `emails_sent` | INTEGER | Total emails sent by user |
| `campaigns_created` | INTEGER | Marketing campaigns created |
| `login_frequency_30d` | INTEGER | Logins in last 30 days |
| `support_tickets_30d` | INTEGER | Support tickets in last 30 days |
| `feature_usage_score` | DOUBLE | Composite feature engagement (0–1) |
| `last_active_date` | DATE | Most recent activity date |
| `churned` | BOOLEAN | Whether the user churned |
| `churn_reason` | VARCHAR | `price` / `support` / `competitor` / `inactivity` / `feature_gap` (NULL if retained) |

Churn rates are seeded realistically: `free` ≈ 58%, `starter` ≈ 36%, `pro` ≈ 20%, `enterprise` ≈ 20%. Low feature usage and high support tickets increase churn probability.

---

## Project Structure

```
churn_assistant/
├── .env.example          # API key template
├── .gitignore
├── requirements.txt
├── generate_data.py      # Generate 1,000-row synthetic dataset → data/churn.csv
├── load_data.py          # Load CSV into DuckDB → data/churn.duckdb
├── build_index.py        # Embed rows → Chroma vector index → chroma_db/
├── tools.py              # sql_query() + semantic_search() + Claude tool schemas
├── agent.py              # Claude tool_use agent loop
└── app.py                # Streamlit UI
```

---

## Prerequisites

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com)

---

## Setup

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd churn_assistant

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Edit .env and replace with your real key:
# ANTHROPIC_API_KEY=sk-ant-...
```

---

## Data Pipeline

Run these once (in order) to build the local database and vector index:

```bash
# Generate 1,000 synthetic users → data/churn.csv
python generate_data.py

# Load into DuckDB → data/churn.duckdb
python load_data.py

# Embed rows and index in Chroma → chroma_db/
# Downloads all-MiniLM-L6-v2 (~90 MB) on first run
python build_index.py
```

---

## Run the App

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

### Test the agent from the terminal

```bash
python agent.py
```

---

## Example Questions

The agent decides whether to use SQL (precise aggregations) or vector search (pattern discovery), or both.

| Question | Strategy |
|---|---|
| What are the top churn reasons by plan type? | SQL `GROUP BY` |
| Which users are most likely to churn? | SQL filter + order |
| Summarize churn patterns for high-spend users. | SQL + semantic |
| Which features are associated with retention? | SQL `AVG(feature_usage_score)` |
| Give me SQL-backed evidence for churn drivers. | SQL correlation |
| Find users with low feature usage who haven't churned yet. | Semantic search |
| Compare login frequency between churned and retained users. | SQL `GROUP BY churned` |

---

## How the Agent Works

`agent.py` implements a simple tool-use loop against the Claude API:

1. User question → sent to Claude with two tool definitions
2. Claude decides which tool(s) to call and with what arguments
3. Tool results are returned to Claude
4. Claude synthesizes a final markdown answer

The agent keeps calling tools until Claude returns `stop_reason = "end_turn"`.

```
User ──► Claude ──► tool_use ──► sql_query / semantic_search
                 ◄── tool_result ◄──────────────────────────
                 ──► (more tool calls if needed)
                 ◄── end_turn: final answer
```

---

## Cost

Running on `claude-haiku-4-5` (the cheapest Claude model), a typical agent query costs **< $0.01**. Swap to `claude-sonnet-4-6` in `agent.py` for higher-quality answers.

---

## Regenerating Data

The `data/` and `chroma_db/` directories are excluded from git (generated artifacts). Any contributor can recreate them in ~90 seconds by running the three pipeline commands above.
