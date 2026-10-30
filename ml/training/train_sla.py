"""
Train and save two models:
1. Resolution time predictor (regression)
2. SLA breach probability predictor (classification)

These models use structured features (priority + department)
rather than raw text — the text models already extracted
the semantic meaning.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import classification_report, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "ml" / "data" / "training_data.csv"
RESOLUTION_MODEL_PATH = ROOT / "ml" / "models" / "resolution_model.pkl"
SLA_MODEL_PATH = ROOT / "ml" / "models" / "sla_model.pkl"


def build_features(df: pd.DataFrame):
    """
    Structured features: priority + department.
    These are categorical — we one-hot encode them.
    """
    return df[["priority", "department"]]


def train() -> None:
    print("Loading data...")
    df = pd.read_csv(DATA_PATH)

    X = build_features(df)

    # One-hot encoder for categorical features
    preprocessor = ColumnTransformer(
        [
            ("ohe", OneHotEncoder(handle_unknown="ignore"), ["priority", "department"]),
        ]
    )

    # -----------------------------------------------
    # Model 1: Resolution time (regression)
    # -----------------------------------------------
    y_hours = df["resolution_hours"]

    X_train, X_test, y_train, y_test = train_test_split(X, y_hours, test_size=0.2, random_state=42)

    resolution_pipeline = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=200,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    print("Training resolution time model...")
    resolution_pipeline.fit(X_train, y_train)

    y_pred_hours = resolution_pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred_hours)
    print(f"  Mean Absolute Error: {mae:.2f} hours")

    joblib.dump(resolution_pipeline, RESOLUTION_MODEL_PATH)
    print(f"  Saved to {RESOLUTION_MODEL_PATH}")

    # -----------------------------------------------
    # Model 2: SLA breach probability (classification)
    # -----------------------------------------------
    y_sla = df["sla_breached"]

    X_train2, X_test2, y_train2, y_test2 = train_test_split(
        X, y_sla, test_size=0.2, random_state=42
    )

    sla_pipeline = Pipeline(
        [
            (
                "preprocessor",
                ColumnTransformer(
                    [
                        ("ohe", OneHotEncoder(handle_unknown="ignore"), ["priority", "department"]),
                    ]
                ),
            ),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",  # ← this is the fix
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    print("\nTraining SLA breach model...")
    sla_pipeline.fit(X_train2, y_train2)

    y_pred_sla = sla_pipeline.predict(X_test2)
    print("\n=== SLA Breach Classification Report ===")
    print(classification_report(y_test2, y_pred_sla, target_names=["no breach", "breach"]))

    joblib.dump(sla_pipeline, SLA_MODEL_PATH)
    print(f"Saved to {SLA_MODEL_PATH}")

    # -----------------------------------------------
    # Sanity check
    # -----------------------------------------------
    print("\n=== Sanity Check ===")
    test_cases = [
        {"priority": "critical", "department": "IT Support"},
        {"priority": "low", "department": "HR"},
        {"priority": "high", "department": "Security"},
    ]
    test_df = pd.DataFrame(test_cases)

    hours = resolution_pipeline.predict(test_df)
    sla_probs = sla_pipeline.predict_proba(test_df)[:, 1]

    for case, h, p in zip(test_cases, hours, sla_probs, strict=False):
        print(
            f"  {case['priority'].upper():8} / {case['department']:12} → "
            f"{h:.1f}h resolution | {p:.0%} SLA breach risk"
        )


if __name__ == "__main__":
    train()
