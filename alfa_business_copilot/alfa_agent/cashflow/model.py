from __future__ import annotations

from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from alfa_agent.cashflow.db import PROJECT_ROOT

TRAINING_CSV_PATH = PROJECT_ROOT / "otbor" / "training_dataset.csv"
MODEL_PATH = PROJECT_ROOT / "data" / "cashflow_model.cbm"

FEATURE_COLUMNS = [
    "avg_daily_income_30d", "avg_daily_income_10d", "income_volatility", "income_trend",
    "current_balance", "upcoming_fixed_expenses_30d", "n_recurring_patterns",
    "avg_pattern_confidence", "business_age_months", "account_age_days", "industry",
]


def load_training_data(path: Path = TRAINING_CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["income_trend"] = pd.to_numeric(df["income_trend"], errors="coerce")
    return df.dropna()


def train_model(path: Path = TRAINING_CSV_PATH, seed: int = 42) -> tuple[CatBoostClassifier, dict]:
    train_df = load_training_data(path)
    X = train_df[FEATURE_COLUMNS]
    y = train_df["gap_within_21d"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    model = CatBoostClassifier(
        iterations=200, depth=4, learning_rate=0.1,
        cat_features=["industry"], verbose=False, random_state=seed, thread_count=1,
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    pred_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": round(accuracy_score(y_test, pred), 3),
        "roc_auc": round(roc_auc_score(y_test, pred_proba), 3),
        "report": classification_report(y_test, pred),
    }
    return model, metrics


def save_model(model: CatBoostClassifier, path: Path = MODEL_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))
    return path


def load_model(path: Path = MODEL_PATH) -> CatBoostClassifier:
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Обучите модель: python -m alfa_agent.cashflow.model"
        )
    model = CatBoostClassifier()
    model.load_model(str(path))
    return model


def main() -> None:
    model, metrics = train_model()
    path = save_model(model)
    print(f"Модель обучена и сохранена -> {path}")
    print(f"Accuracy: {metrics['accuracy']}   ROC-AUC: {metrics['roc_auc']}")
    print(metrics["report"])
    print(model.get_feature_importance(prettified=True))


if __name__ == "__main__":
    main()
