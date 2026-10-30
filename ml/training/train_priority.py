"""
Train and save the priority prediction model.

Pipeline:
    title + description (text)
        → TF-IDF vectorizer (unigrams + bigrams)
        → RandomForestClassifier
        → predicted priority: low / medium / high / critical

Run this script from the project root:
    python ml/training/train_priority.py
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# =====================================================
# Paths
# =====================================================

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "ml" / "data" / "training_data.csv"
MODEL_PATH = ROOT / "ml" / "models" / "priority_model.pkl"


# =====================================================
# Feature engineering
# =====================================================


def build_features(df: pd.DataFrame) -> pd.Series:
    """
    Combine title and description into a single text field.

    We give the title more weight by repeating it 3 times.
    Titles are short but highly informative — "URGENT: server down"
    carries more signal than most of the description text.
    """
    return df["title"].str.repeat(3) + " " + df["description"]


# =====================================================
# Training
# =====================================================


def train() -> None:
    print("Loading data...")
    df = pd.read_csv(DATA_PATH)
    print(f"  Loaded {len(df)} samples")

    X = build_features(df)
    y = df["priority"]

    # 80% train, 20% test — stratified to preserve class proportions
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )
    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    # -----------------------------------------------
    # Build pipeline
    # -----------------------------------------------
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),  # unigrams + bigrams: "VPN not", "not connecting"
                    max_features=5000,  # keep top 5000 most informative terms
                    sublinear_tf=True,  # dampen high term frequencies
                    stop_words="english",  # remove "the", "is", "and", etc.
                ),
            ),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,  # 200 decision trees
                    max_depth=20,  # prevent overfitting
                    class_weight="balanced",  # handle class imbalance
                    random_state=42,
                    n_jobs=-1,  # use all CPU cores
                ),
            ),
        ]
    )

    print("\nTraining priority model...")
    pipeline.fit(X_train, y_train)

    # -----------------------------------------------
    # Evaluate
    # -----------------------------------------------
    y_pred = pipeline.predict(X_test)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred))

    # -----------------------------------------------
    # Save
    # -----------------------------------------------
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    # -----------------------------------------------
    # Quick sanity check — predict on new examples
    # -----------------------------------------------
    print("\n=== Sanity Check ===")
    samples = [
        "Server is completely down — all users affected",
        "Need a new mouse for my workstation",
        "Payroll system showing wrong salary deduction",
        "Suspicious login attempt from unknown country",
    ]
    predictions = pipeline.predict(samples)
    probabilities = pipeline.predict_proba(samples)

    for text, pred, prob in zip(samples, predictions, probabilities, strict=False):
        confidence = max(prob)
        print(f"  [{pred.upper():8}] ({confidence:.0%}) {text[:60]}")


if __name__ == "__main__":
    train()
