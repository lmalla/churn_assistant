import random
import csv
import uuid
from datetime import date, timedelta

random.seed(42)

PLANS = ["free", "starter", "pro", "enterprise"]
PLAN_SPEND = {"free": 0, "starter": 29, "pro": 99, "enterprise": 399}
CHURN_RATES = {"free": 0.45, "starter": 0.25, "pro": 0.15, "enterprise": 0.08}
REASONS = ["price", "support", "competitor", "inactivity", "feature_gap"]


def make_user():
    plan = random.choice(PLANS)
    signup = date(2021, 1, 1) + timedelta(days=random.randint(0, 1095))
    feature_score = round(random.betavariate(2, 3), 2)
    tickets = random.choices(
        [0, 1, 2, 3, 4, 5, 6, 7, 8],
        weights=[40, 25, 15, 8, 5, 3, 2, 1, 1]
    )[0]

    base_churn_p = CHURN_RATES[plan]
    if feature_score < 0.3:
        base_churn_p += 0.20
    if tickets > 3:
        base_churn_p += 0.15
    churned = random.random() < min(base_churn_p, 0.95)

    days_active = random.randint(30, 900) if not churned else random.randint(7, 400)
    last_active = signup + timedelta(days=min(days_active, (date.today() - signup).days))

    base_spend = PLAN_SPEND[plan]
    monthly_spend = round(base_spend * random.uniform(0.85, 1.15), 2) if base_spend > 0 else 0.0

    return {
        "user_id": str(uuid.uuid4()),
        "signup_date": signup.isoformat(),
        "plan_type": plan,
        "monthly_spend": monthly_spend,
        "emails_sent": random.randint(50, 10000) if not churned else random.randint(0, 1500),
        "campaigns_created": random.randint(1, 200) if not churned else random.randint(0, 30),
        "login_frequency_30d": random.randint(5, 30) if not churned else random.randint(0, 4),
        "support_tickets_30d": tickets,
        "feature_usage_score": feature_score,
        "last_active_date": last_active.isoformat(),
        "churned": churned,
        "churn_reason": random.choice(REASONS) if churned else None,
    }


def generate(n=1000, path="data/churn.csv"):
    rows = [make_user() for _ in range(n)]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    churned_count = sum(1 for r in rows if r["churned"])
    print(f"Generated {n} rows  |  churned={churned_count} ({churned_count/n*100:.1f}%)")
    print(f"Saved to {path}")


if __name__ == "__main__":
    generate(1000)
