"""
MLService — loads trained models and exposes prediction methods.

This is the single entry point for all ML predictions.
FastAPI injects this as a dependency into TicketService.

Design decision: models are loaded ONCE at startup (lazy singleton),
not on every request. Loading a model takes ~200ms — unacceptable per-request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# =====================================================
# Paths
# =====================================================

_MODEL_DIR = Path(__file__).parent / "models"

_PRIORITY_MODEL_PATH = _MODEL_DIR / "priority_model.pkl"
_DEPARTMENT_MODEL_PATH = _MODEL_DIR / "department_model.pkl"
_RESOLUTION_MODEL_PATH = _MODEL_DIR / "resolution_model.pkl"
_SLA_MODEL_PATH = _MODEL_DIR / "sla_model.pkl"


# =====================================================
# Prediction result — typed dataclass
# =====================================================


@dataclass
class TicketPrediction:
    """
    All ML predictions for a single ticket.

    Fields map directly to the predicted_* columns in the tickets table.
    """

    priority_score: float  # 0.0–1.0 probability the priority should be HIGH+
    department_name: str | None  # predicted department name (matched to DB later)
    resolution_hours: float  # predicted hours to resolve
    sla_breach_prob: float  # 0.0–1.0 probability of SLA breach


# =====================================================
# Service
# =====================================================


class MLService:
    """
    Wraps scikit-learn pipelines and exposes a clean predict() interface.

    Lazy loading: models are loaded on first use, not at import time.
    If a model file is missing, the service degrades gracefully —
    predictions return None instead of crashing the ticket creation flow.
    """

    def __init__(self) -> None:
        self._priority_model = None
        self._department_model = None
        self._resolution_model = None
        self._sla_model = None
        self._loaded = False

    def _load_models(self) -> None:
        """Load all models from disk. Called once on first predict()."""
        import joblib

        def _safe_load(path: Path, name: str):
            try:
                model = joblib.load(path)
                logger.info(f"ML model loaded: {name}")
                return model
            except FileNotFoundError:
                logger.warning(f"ML model not found, skipping: {path}")
                return None
            except Exception as e:
                logger.error(f"Failed to load ML model {name}: {e}")
                return None

        self._priority_model = _safe_load(_PRIORITY_MODEL_PATH, "priority")
        self._department_model = _safe_load(_DEPARTMENT_MODEL_PATH, "department")
        self._resolution_model = _safe_load(_RESOLUTION_MODEL_PATH, "resolution")
        self._sla_model = _safe_load(_SLA_MODEL_PATH, "sla_breach")
        self._loaded = True

    def predict(self, title: str, description: str) -> TicketPrediction:
        """
        Run all four models and return a TicketPrediction.

        Args:
            title:       Ticket title (short, high-signal text)
            description: Ticket description (longer context)

        Returns:
            TicketPrediction with all predicted values.
            Falls back to safe defaults if any model is unavailable.
        """
        if not self._loaded:
            self._load_models()

        # Combine title (repeated for weight) + description
        text = f"{title} {title} {title} {description}"

        import pandas as pd

        # -----------------------------------------------
        # 1. Priority score
        # -----------------------------------------------
        priority_score = 0.5  # default: uncertain
        predicted_priority = "medium"

        if self._priority_model:
            try:
                proba = self._priority_model.predict_proba([text])[0]
                classes = self._priority_model.classes_
                # Score = probability of HIGH or CRITICAL
                high_idx = list(classes).index("high") if "high" in classes else -1
                crit_idx = list(classes).index("critical") if "critical" in classes else -1
                priority_score = sum(
                    [
                        proba[high_idx] if high_idx >= 0 else 0,
                        proba[crit_idx] if crit_idx >= 0 else 0,
                    ]
                )
                predicted_priority = self._priority_model.predict([text])[0]
            except Exception as e:
                logger.error(f"Priority prediction failed: {e}")

        # -----------------------------------------------
        # 2. Department prediction
        # -----------------------------------------------
        department_name = None

        if self._department_model:
            try:
                department_name = self._department_model.predict([text])[0]
            except Exception as e:
                logger.error(f"Department prediction failed: {e}")

        # -----------------------------------------------
        # 3. Resolution time (uses predicted priority + department)
        # -----------------------------------------------
        resolution_hours = 24.0  # default: 1 day

        if self._resolution_model and department_name:
            try:
                features = pd.DataFrame(
                    [
                        {
                            "priority": predicted_priority,
                            "department": department_name,
                        }
                    ]
                )
                resolution_hours = float(self._resolution_model.predict(features)[0])
            except Exception as e:
                logger.error(f"Resolution time prediction failed: {e}")

        # -----------------------------------------------
        # 4. SLA breach probability
        # -----------------------------------------------
        sla_breach_prob = 0.2  # default: low risk

        if self._sla_model and department_name:
            try:
                features = pd.DataFrame(
                    [
                        {
                            "priority": predicted_priority,
                            "department": department_name,
                        }
                    ]
                )
                sla_breach_prob = float(self._sla_model.predict_proba(features)[0][1])
            except Exception as e:
                logger.error(f"SLA breach prediction failed: {e}")

        return TicketPrediction(
            priority_score=round(priority_score, 4),
            department_name=department_name,
            resolution_hours=round(resolution_hours, 2),
            sla_breach_prob=round(sla_breach_prob, 4),
        )


# =====================================================
# Module-level singleton — shared across all requests
# =====================================================

ml_service = MLService()
