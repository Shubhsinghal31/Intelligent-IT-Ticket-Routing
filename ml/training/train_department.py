"""
Train and save the department prediction model.

Pipeline:
    title + description → TF-IDF → RandomForestClassifier
    → predicted department name
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "ml" / "data" / "training_data.csv"
MODEL_PATH = ROOT / "ml" / "models" / "department_model.pkl"


def build_features(df: pd.DataFrame) -> pd.Series:
    return df["title"].str.repeat(3) + " " + df["description"]


def train() -> None:
    print("Loading data...")
    df = pd.read_csv(DATA_PATH)

    X = build_features(df)
    y = df["department"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=5000,
                    sublinear_tf=True,
                    stop_words="english",
                ),
            ),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=20,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    print("Training department model...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    print("\n=== Sanity Check ===")
    samples = [
        "VPN not connecting, cannot access company network",
        "Payslip not received for last month",
        "Expense reimbursement pending for three weeks",
        "Suspicious login attempt from unknown IP address",
        "Air conditioning not working in the office",
    ]
    predictions = pipeline.predict(samples)
    for text, pred in zip(samples, predictions, strict=False):
        print(f"  [{pred:12}] {text[:55]}")


if __name__ == "__main__":
    train()
