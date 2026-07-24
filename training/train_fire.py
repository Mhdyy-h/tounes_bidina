"""
Trains a binary wildfire classifier on the (real, public) Algerian Forest Fires
Dataset and saves it for live inference.

Dataset: Abid, Faroudja. "Algerian Forest Fires Dataset." Zenodo, 2022.
DOI: 10.5281/zenodo.6515969, license CC-BY-4.0. 243 usable daily records (of 244
source instances - see preprocessing/clean_fire_data.py for the one excluded
corrupted row) from two Algerian regions, June-Sept 2012.

Honesty note: this is a Mediterranean fire-weather proxy dataset, not
Tunisia-specific ground truth (no public labeled Tunisian wildfire dataset was
found). It shares the same fire-weather feature family (temperature, relative
humidity, wind speed, rainfall) used operationally in Canadian/Mediterranean
Fire Weather Index systems, which is why it's a reasonable stand-in for a
hackathon MVP. This limitation is documented in README.md.

Run: python -m training.train_fire
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from preprocessing.clean_fire_data import save_clean_csv

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODELS_DIR / "wildfire_model.pkl"
META_PATH = MODELS_DIR / "wildfire_model_meta.json"

FEATURES = ["temperature_c", "humidity_pct", "wind_kmh", "rain_mm"]
TARGET = "fire"

DATASET_SOURCE = (
    "Abid, Faroudja. \"Algerian Forest Fires Dataset.\" Zenodo, 2022. "
    "DOI: 10.5281/zenodo.6515969 (CC-BY-4.0)."
)


def main():
    df = save_clean_csv()

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
        eval_metric="logloss",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred)), 4),
        "recall": round(float(recall_score(y_test, y_pred)), 4),
        "f1": round(float(f1_score(y_test, y_pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
    }
    print("Test set metrics:", json.dumps(metrics, indent=2))

    feature_importances = {
        f: round(float(imp), 4)
        for f, imp in zip(FEATURES, model.feature_importances_)
    }

    # Class-conditional feature stats, used at inference time to explain *why*
    # a given prediction leans fire/not-fire, grounded in the real training data.
    feature_stats = {
        f: {
            "fire_mean": round(float(df.loc[df[TARGET] == 1, f].mean()), 2),
            "not_fire_mean": round(float(df.loc[df[TARGET] == 0, f].mean()), 2),
        }
        for f in FEATURES
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    meta = {
        "model_type": "XGBClassifier",
        "features": FEATURES,
        "target": TARGET,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_source": DATASET_SOURCE,
        "dataset_size": {
            "total_rows": len(df),
            "train_rows": len(X_train),
            "test_rows": len(X_test),
        },
        "test_metrics": metrics,
        "feature_importances": feature_importances,
        "feature_stats_by_class": feature_stats,
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved model -> {MODEL_PATH}")
    print(f"Saved metadata -> {META_PATH}")


if __name__ == "__main__":
    main()
