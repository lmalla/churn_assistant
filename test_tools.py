import pytest

import tools


# --- Query validation: only SELECT/WITH, single statement, no dangerous keywords ---

@pytest.mark.parametrize("query", [
    "DELETE FROM churn",
    "INSERT INTO churn VALUES (1)",
    "UPDATE churn SET plan_type = 'free'",
    "DROP TABLE churn",
    "ALTER TABLE churn ADD COLUMN x INT",
    "ATTACH 'other.db' AS other",
    "COPY churn TO '/tmp/out.csv'",
    "PRAGMA database_list",
    "INSTALL httpfs",
    "LOAD httpfs",
    "CALL pragma_database_list()",
    "SELECT * FROM read_csv_auto('/etc/passwd')",
    "SELECT * FROM read_parquet('/etc/whatever')",
    "SELECT 1; DROP TABLE churn",
    "SELECT 1; SELECT 2",
    "SELECT * FROM '/etc/passwd'",
    "SELECT * FROM 'data/churn.csv'",
    "SELECT * FROM parquet_scan('/etc/passwd')",
    "SELECT * FROM sqlite_scan('x.db', 't')",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM duckdb_settings()",
    "SELECT * FROM some_other_table",
])
def test_sql_query_rejects_dangerous_queries(query):
    result = tools.sql_query(query)
    assert result.startswith("SQL validation error:")


def test_sql_query_allows_plain_select():
    result = tools.sql_query("SELECT count(*) AS n FROM churn")
    assert "SQL validation error" not in result
    assert "n" in result


def test_sql_query_allows_cte_select():
    result = tools.sql_query(
        "WITH t AS (SELECT * FROM churn) SELECT count(*) AS n FROM t"
    )
    assert "SQL validation error" not in result
    assert "n" in result


def test_sql_query_allows_trailing_semicolon():
    result = tools.sql_query("SELECT count(*) AS n FROM churn;")
    assert "SQL validation error" not in result
    assert "n" in result


def test_sql_query_allows_aliased_table():
    result = tools.sql_query("SELECT c.plan_type FROM churn c LIMIT 1")
    assert "SQL validation error" not in result


def test_sql_query_allows_subquery_over_churn():
    result = tools.sql_query(
        "SELECT count(*) AS n FROM (SELECT * FROM churn) t"
    )
    assert "SQL validation error" not in result
    assert "n" in result


# --- Row cap ---

def test_sql_query_caps_returned_rows():
    result = tools.sql_query("SELECT * FROM churn", row_cap=10)
    # header + separator + up to 10 data rows, plus a truncation note
    data_lines = [l for l in result.splitlines() if l.strip().startswith("|")]
    assert len(data_lines) - 2 <= 10
    assert "truncated" in result.lower()


# --- Query timeout ---

def test_sql_query_times_out_on_slow_query():
    slow_query = """
        WITH RECURSIVE t AS (
            SELECT 1 AS n
            UNION ALL
            SELECT n + 1 FROM t WHERE n < 100000000
        )
        SELECT count(*) AS n FROM t
    """
    result = tools.sql_query(slow_query, timeout_seconds=0.2)
    assert "timed out" in result.lower()
