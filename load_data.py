import duckdb

DB_PATH = "data/churn.duckdb"
CSV_PATH = "data/churn.csv"


def load():
    con = duckdb.connect(DB_PATH)
    con.execute(f"""
        CREATE OR REPLACE TABLE churn AS
        SELECT
            user_id,
            signup_date::DATE        AS signup_date,
            plan_type,
            monthly_spend::DOUBLE    AS monthly_spend,
            emails_sent::INTEGER     AS emails_sent,
            campaigns_created::INTEGER AS campaigns_created,
            login_frequency_30d::INTEGER AS login_frequency_30d,
            support_tickets_30d::INTEGER AS support_tickets_30d,
            feature_usage_score::DOUBLE AS feature_usage_score,
            last_active_date::DATE   AS last_active_date,
            churned::BOOLEAN         AS churned,
            churn_reason
        FROM read_csv_auto('{CSV_PATH}', header=True, nullstr='None')
    """)

    count, churn_rate = con.execute(
        "SELECT COUNT(*), ROUND(AVG(churned::int)*100, 1) FROM churn"
    ).fetchone()
    print(f"Loaded {count} rows into {DB_PATH}  |  overall churn rate: {churn_rate}%")

    print("\nChurn rate by plan:")
    print(con.execute("""
        SELECT plan_type,
               COUNT(*) AS users,
               ROUND(AVG(churned::int)*100, 1) AS churn_pct
        FROM churn
        GROUP BY plan_type
        ORDER BY churn_pct DESC
    """).fetchdf().to_string(index=False))

    con.close()


if __name__ == "__main__":
    load()
