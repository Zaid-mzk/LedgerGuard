from pathlib import Path
import json
import platform
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from generate_synthetic_transactions import generate

FEATURES = [
    "amount",
    "transactions_last_10m",
    "account_age_days",
    "minutes_since_previous_transfer",
    "unique_receivers_last_24h",
    "amount_vs_account_median",
    "is_new_receiver",
    "hour_of_day",
]


def main():
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    df = generate(5000, 42)
    X = df[FEATURES]
    y = df.synthetic_label
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )
    # IsolationForest is unsupervised; use the validation split to select a review threshold on anomaly scores.
    model = make_pipeline(
        StandardScaler(), IsolationForest(n_estimators=200, contamination="auto", random_state=42)
    )
    model.fit(X_train[y_train == 0])
    val_scores = -model.decision_function(X_val)
    thresholds = np.quantile(val_scores, [0.90, 0.92, 0.94, 0.96, 0.98])
    best = None
    from sklearn.metrics import f1_score

    for threshold in thresholds:
        score = f1_score(y_val, (val_scores >= threshold).astype(int), zero_division=0)
        if best is None or score > best[0]:
            best = (score, float(threshold))
    test_scores = -model.decision_function(X_test)
    pred = (test_scores >= best[1]).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_test, pred, labels=[0, 1]).tolist()
    joblib.dump(
        {
            "model": model,
            "threshold": best[1],
            "features": FEATURES,
            "version": "isolation-forest-v1",
        },
        out / "risk_model.joblib",
    )
    report = {
        "status": "evaluated",
        "synthetic_only": True,
        "dataset_version": "synthetic-v1",
        "rows": len(df),
        "seed": 42,
        "split": "60/20/20 stratified train/validation/test; fit on normal training rows",
        "features": FEATURES,
        "label_excluded_from_features": True,
        "model_version": "isolation-forest-v1",
        "validation_threshold": best[1],
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": {"tn": cm[0][0], "fp": cm[0][1], "fn": cm[1][0], "tp": cm[1][1]},
        "python": platform.python_version(),
    }
    (out / "model_evaluation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
