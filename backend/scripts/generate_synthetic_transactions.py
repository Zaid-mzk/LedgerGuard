import argparse
import numpy as np
import pandas as pd


def generate(rows=5000, seed=42):
    rng = np.random.default_rng(seed)
    amount = np.clip(rng.lognormal(7.0, 1.0, rows), 10, 200000).round(2)
    velocity = rng.poisson(1.5, rows)
    account_age = rng.integers(1, 2500, rows)
    minutes_since = rng.integers(1, 10000, rows)
    new_receivers = rng.poisson(1.0, rows)
    ratio = (amount / np.maximum(rng.lognormal(6.7, 0.8, rows), 10)).round(3)
    new_receiver = rng.binomial(1, 0.22, rows)
    hour = rng.integers(0, 24, rows)
    label = (
        (amount > 60000) & (velocity >= 2)
        | ((ratio > 8) & (new_receiver == 1))
        | ((hour < 4) & (amount > 25000)).astype(bool)
    ).astype(int)
    return pd.DataFrame(
        {
            "amount": amount,
            "transactions_last_10m": velocity,
            "account_age_days": account_age,
            "minutes_since_previous_transfer": minutes_since,
            "unique_receivers_last_24h": new_receivers,
            "amount_vs_account_median": ratio,
            "is_new_receiver": new_receiver,
            "hour_of_day": hour,
            "synthetic_label": label,
        }
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="artifacts/synthetic_transactions.csv")
    a = p.parse_args()
    from pathlib import Path

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = generate(a.rows, a.seed)
    df.to_csv(out, index=False)
    print(
        f"Wrote {len(df)} synthetic rows to {out}; anomalies={int(df.synthetic_label.sum())}; seed={a.seed}"
    )
