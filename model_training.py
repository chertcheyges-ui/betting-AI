"""
BETTING AI — MODEL TRAINING

Pure Python implementation.
NO NumPy
NO Pandas
NO Scikit-learn

Input:
    data/processed/model_dataset.csv

Output:
    data/models/betting_model.json
    data/processed/model_predictions.csv

IMPORTANT:
    Current-match outcome information is excluded from training.

Excluded:
    home_goals
    away_goals
    result
    target

The model uses only information that should be available BEFORE
the match starts.

Model:
    Multiclass softmax logistic regression
    implemented with Python standard library only.

Evaluation:
    Chronological train/test split
    Accuracy
    Log Loss
    Brier Score

Betting:
    ROI is calculated only when PRE-MATCH odds exist in the dataset.
    Otherwise no betting backtest is performed.
"""

import csv
import json
import math
import os
import random
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "data/processed/model_dataset.csv"
MODEL_FILE = "data/models/betting_model.json"
PREDICTIONS_FILE = "data/processed/model_predictions.csv"

TRAIN_RATIO = 0.80

EPOCHS = 1200
LEARNING_RATE = 0.025
L2_REGULARIZATION = 0.0005

PRINT_EVERY = 100

CLASSES = [
    "HOME_WIN",
    "DRAW",
    "AWAY_WIN",
]

CLASS_TO_INDEX = {
    "HOME_WIN": 0,
    "DRAW": 1,
    "AWAY_WIN": 2,
}


# ============================================================
# TARGET LEAKAGE PROTECTION
# ============================================================

# These fields contain information that is known only after
# the match has happened or directly encode the target.

LEAKAGE_FIELDS = {
    "home_goals",
    "away_goals",
    "result",
    "target",
}

# Additional names that should never accidentally enter the model.

POST_MATCH_KEYWORDS = (
    "score",
    "goals",
    "result",
    "winner",
    "target",
)


# ============================================================
# SAFE NUMERIC CONVERSION
# ============================================================

def to_float(value):
    """Convert a CSV value to float safely."""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        number = float(text)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


# ============================================================
# DATE PARSING
# ============================================================

def parse_date(value):
    """Parse ISO date strings for chronological sorting."""

    if not value:
        return datetime.min

    text = str(value).strip()

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


# ============================================================
# DATA LOADING
# ============================================================

def load_dataset(path):
    print("=" * 70)
    print("BETTING AI — MODEL TRAINING")
    print("=" * 70)

    print()
    print("NumPy:       NOT USED")
    print("Pandas:      NOT USED")
    print("Scikit-learn: NOT USED")
    print()

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    with open(path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        rows = list(reader)

        if not reader.fieldnames:
            raise ValueError("CSV has no header.")

    if not rows:
        raise ValueError("CSV contains no rows.")

    print(f"Input: {path}")
    print(f"Historical fixtures loaded: {len(rows)}")

    return rows, reader.fieldnames


# ============================================================
# CHRONOLOGICAL SORT
# ============================================================

def sort_rows(rows):
    rows.sort(
        key=lambda row: parse_date(row.get("date"))
    )

    print()
    print("Data sorted chronologically.")

    return rows


# ============================================================
# TARGET PREPARATION
# ============================================================

def get_target(row):
    """
    Get the actual match outcome.

    target:
        0 = HOME_WIN
        1 = DRAW
        2 = AWAY_WIN
    """

    result = str(row.get("result", "")).strip().upper()

    if result not in CLASS_TO_INDEX:
        return None

    return CLASS_TO_INDEX[result]


# ============================================================
# FEATURE DISCOVERY
# ============================================================

def discover_features(rows, fieldnames):
    """
    Discover numeric pre-match features.

    Strictly excludes:
        home_goals
        away_goals
        result
        target

    Also excludes obvious post-match fields.
    """

    features = []

    for field in fieldnames:

        field_lower = field.lower().strip()

        if field_lower in LEAKAGE_FIELDS:
            continue

        # Don't allow obvious post-match fields.
        if any(
            keyword in field_lower
            for keyword in POST_MATCH_KEYWORDS
        ):
            continue

        # Never use identifiers or textual fields.
        if field_lower in {
            "date",
            "home_team",
            "away_team",
            "league",
            "country",
            "round",
            "fixture_id",
            "id",
        }:
            continue

        numeric_found = False

        # Check whether this column contains numeric data.
        for row in rows[:100]:
            value = to_float(row.get(field))

            if value is not None:
                numeric_found = True
                break

        if numeric_found:
            features.append(field)

    return features


# ============================================================
# DATASET MATRIX
# ============================================================

def build_matrix(rows, feature_names):
    """
    Convert rows into:

        X = feature matrix
        y = targets
        metadata = fixture information

    Missing numeric values become 0.

    Important:
    this happens BEFORE model training.
    """

    X = []
    y = []
    metadata = []

    for row in rows:

        target = get_target(row)

        if target is None:
            continue

        vector = []

        for feature in feature_names:
            value = to_float(row.get(feature))

            if value is None:
                value = 0.0

            vector.append(value)

        X.append(vector)
        y.append(target)

        metadata.append({
            "date": row.get("date", ""),
            "home_team": row.get("home_team", ""),
            "away_team": row.get("away_team", ""),
            "actual": CLASSES[target],
        })

    return X, y, metadata


# ============================================================
# STANDARDIZATION
# ============================================================

def calculate_scaler(X):
    """
    Calculate mean and standard deviation using training data only.
    """

    if not X:
        return [], []

    feature_count = len(X[0])

    means = []
    stds = []

    for column in range(feature_count):

        values = [
            row[column]
            for row in X
        ]

        mean = sum(values) / len(values)

        variance = sum(
            (value - mean) ** 2
            for value in values
        ) / len(values)

        std = math.sqrt(variance)

        if std < 1e-12:
            std = 1.0

        means.append(mean)
        stds.append(std)

    return means, stds


def standardize(X, means, stds):
    """Standardize features using training-set statistics."""

    result = []

    for row in X:

        normalized = []

        for value, mean, std in zip(row, means, stds):
            normalized.append(
                (value - mean) / std
            )

        result.append(normalized)

    return result


# ============================================================
# SOFTMAX
# ============================================================

def softmax(logits):
    """
    Numerically stable softmax.
    """

    maximum = max(logits)

    exponentials = [
        math.exp(value - maximum)
        for value in logits
    ]

    total = sum(exponentials)

    if total <= 0:
        return [
            1.0 / len(logits)
            for _ in logits
        ]

    return [
        value / total
        for value in exponentials
    ]


# ============================================================
# MODEL
# ============================================================

class SoftmaxRegression:
    """
    Multiclass logistic regression.

    Pure Python implementation.
    """

    def __init__(
        self,
        feature_count,
        class_count=3,
        learning_rate=LEARNING_RATE,
        l2=L2_REGULARIZATION,
    ):
        self.feature_count = feature_count
        self.class_count = class_count
        self.learning_rate = learning_rate
        self.l2 = l2

        # Small deterministic initialization.
        random.seed(42)

        self.weights = [
            [
                random.uniform(-0.01, 0.01)
                for _ in range(feature_count)
            ]
            for _ in range(class_count)
        ]

        self.bias = [
            0.0
            for _ in range(class_count)
        ]

    def predict_proba_one(self, x):
        logits = []

        for class_index in range(self.class_count):

            score = self.bias[class_index]

            for feature_index in range(self.feature_count):
                score += (
                    self.weights[class_index][feature_index]
                    * x[feature_index]
                )

            logits.append(score)

        return softmax(logits)

    def predict_proba(self, X):
        return [
            self.predict_proba_one(row)
            for row in X
        ]

    def predict(self, X):
        predictions = []

        for row in X:

            probabilities = self.predict_proba_one(row)

            prediction = max(
                range(self.class_count),
                key=lambda index: probabilities[index],
            )

            predictions.append(prediction)

        return predictions

    def loss(self, X, y):
        """
        Cross entropy + L2 regularization.
        """

        total = 0.0

        for x, target in zip(X, y):

            probabilities = self.predict_proba_one(x)

            probability = max(
                probabilities[target],
                1e-15,
            )

            total -= math.log(probability)

        if X:
            total /= len(X)

        regularization = 0.0

        for class_weights in self.weights:
            for weight in class_weights:
                regularization += weight * weight

        regularization *= self.l2 / 2.0

        return total + regularization

    def train(self, X, y, epochs):
        print()
        print("=" * 70)
        print("TRAINING")
        print("=" * 70)

        print()
        print(f"Training samples: {len(X)}")
        print(f"Features:         {self.feature_count}")
        print(f"Classes:          {self.class_count}")
        print(f"Epochs:           {epochs}")
        print(f"Learning rate:    {self.learning_rate}")
        print(f"L2:               {self.l2}")

        sample_count = len(X)

        for epoch in range(1, epochs + 1):

            gradients_w = [
                [0.0] * self.feature_count
                for _ in range(self.class_count)
            ]

            gradients_b = [
                0.0
                for _ in range(self.class_count)
            ]

            for x, target in zip(X, y):

                probabilities = self.predict_proba_one(x)

                for class_index in range(self.class_count):

                    error = (
                        probabilities[class_index]
                        - (
                            1.0
                            if class_index == target
                            else 0.0
                        )
                    )

                    gradients_b[class_index] += error

                    for feature_index in range(self.feature_count):
                        gradients_w[class_index][feature_index] += (
                            error * x[feature_index]
                        )

            # Average gradient.
            for class_index in range(self.class_count):

                gradients_b[class_index] /= sample_count

                for feature_index in range(self.feature_count):

                    gradients_w[class_index][feature_index] /= sample_count

                    # L2 penalty.
                    gradients_w[class_index][feature_index] += (
                        self.l2
                        * self.weights[class_index][feature_index]
                    )

            # Update.
            for class_index in range(self.class_count):

                self.bias[class_index] -= (
                    self.learning_rate
                    * gradients_b[class_index]
                )

                for feature_index in range(self.feature_count):

                    self.weights[class_index][feature_index] -= (
                        self.learning_rate
                        * gradients_w[class_index][feature_index]
                    )

            if (
                epoch == 1
                or epoch % PRINT_EVERY == 0
                or epoch == epochs
            ):
                current_loss = self.loss(X, y)

                print(
                    f"Epoch {epoch:4d}/{epochs} "
                    f"| loss={current_loss:.5f}"
                )


# ============================================================
# METRICS
# ============================================================

def accuracy(y_true, y_pred):
    if not y_true:
        return 0.0

    correct = sum(
        1
        for actual, predicted in zip(y_true, y_pred)
        if actual == predicted
    )

    return correct / len(y_true)


def log_loss(y_true, probabilities):
    """
    Multiclass logarithmic loss.
    """

    if not y_true:
        return 0.0

    total = 0.0

    for actual, probs in zip(
        y_true,
        probabilities,
    ):
        probability = max(
            min(probs[actual], 1.0),
            1e-15,
        )

        total -= math.log(probability)

    return total / len(y_true)


def brier_score(y_true, probabilities):
    """
    Multiclass Brier score.
    """

    if not y_true:
        return 0.0

    total = 0.0

    for actual, probs in zip(
        y_true,
        probabilities,
    ):

        for class_index in range(len(CLASSES)):

            expected = (
                1.0
                if class_index == actual
                else 0.0
            )

            total += (
                probs[class_index] - expected
            ) ** 2

    return total / len(y_true)


# ============================================================
# DISTRIBUTION
# ============================================================

def print_distribution(title, values):

    print()
    print(title)

    counts = {
        "HOME_WIN": 0,
        "DRAW": 0,
        "AWAY_WIN": 0,
    }

    for value in values:
        counts[CLASSES[value]] += 1

    for name in CLASSES:
        print(
            f"  {name:10s}: {counts[name]}"
        )


# ============================================================
# FEATURE IMPORTANCE
# ============================================================

def calculate_feature_importance(model, feature_names):
    """
    Average absolute weight across the three classes.
    """

    importance = []

    for feature_index, name in enumerate(feature_names):

        value = sum(
            abs(
                model.weights[class_index][feature_index]
            )
            for class_index in range(model.class_count)
        ) / model.class_count

        importance.append(
            (name, value)
        )

    importance.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    return importance


# ============================================================
# SAVE MODEL
# ============================================================

def save_model(
    model,
    feature_names,
    means,
    stds,
    path,
):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    payload = {
        "model_type": "softmax_logistic_regression",
        "implementation": "pure_python",
        "numpy": False,
        "pandas": False,
        "scikit_learn": False,

        "classes": CLASSES,

        "feature_names": feature_names,

        "feature_means": means,
        "feature_stds": stds,

        "weights": model.weights,
        "bias": model.bias,

        "learning_rate": model.learning_rate,
        "l2_regularization": model.l2,

        "leakage_protection": {
            "excluded_fields": sorted(
                LEAKAGE_FIELDS
            ),
            "description": (
                "Current-match outcome fields are excluded "
                "from model features."
            ),
        },
    }

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            indent=2,
        )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    metadata,
    probabilities,
    predictions,
    path,
):
    directory = os.path.dirname(path)

    if directory:
        os.makedirs(
            directory,
            exist_ok=True,
        )

    with open(
        path,
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "date",
            "home_team",
            "away_team",
            "model_home_probability",
            "model_draw_probability",
            "model_away_probability",
            "prediction",
            "actual",
        ])

        for meta, probs, prediction in zip(
            metadata,
            probabilities,
            predictions,
        ):

            writer.writerow([
                meta["date"],
                meta["home_team"],
                meta["away_team"],
                f"{probs[0]:.6f}",
                f"{probs[1]:.6f}",
                f"{probs[2]:.6f}",
                CLASSES[prediction],
                meta["actual"],
            ])


# ============================================================
# ODDS CHECK
# ============================================================

def detect_pre_match_odds(feature_names):
    """
    We intentionally do not assume that odds exist.

    If the historical dataset contains bookmaker odds as
    pre-match features, they can later be used for a separate
    betting backtest.

    For now this function only reports availability.
    """

    odds_fields = [
        field
        for field in feature_names
        if "odds" in field.lower()
    ]

    return odds_fields


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    rows, fieldnames = load_dataset(
        INPUT_FILE
    )

    rows = sort_rows(rows)

    # --------------------------------------------------------
    # FEATURES
    # --------------------------------------------------------

    feature_names = discover_features(
        rows,
        fieldnames,
    )

    if not feature_names:
        raise ValueError(
            "No valid numeric pre-match features found."
        )

    print()
    print(
        f"Numeric pre-match features discovered: "
        f"{len(feature_names)}"
    )

    print()
    for feature in feature_names:
        print(f"  - {feature}")

    # Explicit leakage check.
    leaked = [
        feature
        for feature in feature_names
        if feature.lower() in LEAKAGE_FIELDS
    ]

    if leaked:
        raise RuntimeError(
            "TARGET LEAKAGE DETECTED: "
            + ", ".join(leaked)
        )

    print()
    print(
        "Target leakage check: PASSED"
    )

    print(
        "Excluded:"
    )

    for field in sorted(LEAKAGE_FIELDS):
        print(
            f"  - {field}"
        )

    # --------------------------------------------------------
    # MATRIX
    # --------------------------------------------------------

    X, y, metadata = build_matrix(
        rows,
        feature_names,
    )

    if len(X) < 10:
        raise ValueError(
            "Not enough valid training rows."
        )

    print()
    print(
        f"Usable rows: {len(X)}"
    )

    # --------------------------------------------------------
    # CHRONOLOGICAL SPLIT
    # --------------------------------------------------------

    split_index = int(
        len(X) * TRAIN_RATIO
    )

    if split_index <= 0:
        raise ValueError(
            "Training set is empty."
        )

    if split_index >= len(X):
        raise ValueError(
            "Testing set is empty."
        )

    X_train = X[:split_index]
    y_train = y[:split_index]

    X_test = X[split_index:]
    y_test = y[split_index:]

    metadata_test = metadata[
        split_index:
    ]

    print()
    print("=" * 70)
    print("CHRONOLOGICAL SPLIT")
    print("=" * 70)

    print(
        f"Training rows: {len(X_train)}"
    )

    print(
        f"Testing rows:  {len(X_test)}"
    )

    print(
        f"Train start:   {metadata[0]['date']}"
    )

    print(
        f"Train end:     {metadata[split_index - 1]['date']}"
    )

    print(
        f"Test start:    {metadata[split_index]['date']}"
    )

    print(
        f"Test end:      {metadata[-1]['date']}"
    )

    # --------------------------------------------------------
    # SCALING
    # --------------------------------------------------------

    means, stds = calculate_scaler(
        X_train
    )

    X_train_scaled = standardize(
        X_train,
        means,
        stds,
    )

    X_test_scaled = standardize(
        X_test,
        means,
        stds,
    )

    # --------------------------------------------------------
    # DISTRIBUTION
    # --------------------------------------------------------

    print_distribution(
        "\nTraining distribution:",
        y_train,
    )

    print_distribution(
        "\nTesting distribution:",
        y_test,
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = SoftmaxRegression(
        feature_count=len(feature_names),
        class_count=len(CLASSES),
        learning_rate=LEARNING_RATE,
        l2=L2_REGULARIZATION,
    )

    model.train(
        X_train_scaled,
        y_train,
        EPOCHS,
    )

    # --------------------------------------------------------
    # OUT OF SAMPLE TEST
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("OUT-OF-SAMPLE TEST")
    print("=" * 70)

    probabilities = model.predict_proba(
        X_test_scaled
    )

    predictions = model.predict(
        X_test_scaled
    )

    test_accuracy = accuracy(
        y_test,
        predictions,
    )

    test_log_loss = log_loss(
        y_test,
        probabilities,
    )

    test_brier = brier_score(
        y_test,
        probabilities,
    )

    print()
    print(
        f"Test samples: {len(y_test)}"
    )

    print(
        f"Accuracy:     {test_accuracy * 100:.2f}%"
    )

    print(
        f"Log Loss:     {test_log_loss:.5f}"
    )

    print(
        f"Brier Score:  {test_brier:.5f}"
    )

    print_distribution(
        "\nActual test distribution:",
        y_test,
    )

    print_distribution(
        "\nPredicted distribution:",
        predictions,
    )

    # --------------------------------------------------------
    # BETTING BACKTEST
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BETTING BACKTEST")
    print("=" * 70)

    odds_fields = detect_pre_match_odds(
        feature_names
    )

    if not odds_fields:
        print()
        print(
            "Bets:               0"
        )

        print(
            "ROI:                NOT CALCULATED"
        )

        print()
        print(
            "Reason:"
        )

        print(
            "Historical pre-match bookmaker odds "
            "are not available as usable fields "
            "in model_dataset.csv."
        )

        print()
        print(
            "This is intentional."
        )

        print(
            "We will NOT invent odds and we will NOT "
            "pretend that model accuracy equals betting profit."
        )

    else:
        print()
        print(
            "Potential odds fields detected:"
        )

        for field in odds_fields:
            print(
                f"  - {field}"
            )

        print()
        print(
            "ROI backtest is NOT activated yet."
        )

        print(
            "Odds must be explicitly mapped to the "
            "corresponding betting market before calculating ROI."
        )

    # --------------------------------------------------------
    # FEATURE IMPORTANCE
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TOP MODEL FEATURES")
    print("=" * 70)

    importance = calculate_feature_importance(
        model,
        feature_names,
    )

    for name, value in importance[:20]:
        print(
            f"  {name:45s} {value:.6f}"
        )

    # --------------------------------------------------------
    # SAVE MODEL
    # --------------------------------------------------------

    save_model(
        model,
        feature_names,
        means,
        stds,
        MODEL_FILE,
    )

    save_predictions(
        metadata_test,
        probabilities,
        predictions,
        PREDICTIONS_FILE,
    )

    # --------------------------------------------------------
    # EXAMPLES
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EXAMPLE MODEL PREDICTIONS")
    print("=" * 70)

    for meta, probs, prediction in list(
        zip(
            metadata_test,
            probabilities,
            predictions,
        )
    )[:10]:

        print()
        print(
            f"{meta['date']} | "
            f"{meta['home_team']} vs "
            f"{meta['away_team']}"
        )

        print(
            f"  Model: "
            f"H={probs[0]:.3f} "
            f"D={probs[1]:.3f} "
            f"A={probs[2]:.3f}"
        )

        print(
            f"  Prediction: "
            f"{CLASSES[prediction]}"
        )

        print(
            f"  Actual:     "
            f"{meta['actual']}"
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MODEL TRAINING COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Model saved:       {MODEL_FILE}"
    )

    print(
        f"Predictions saved: {PREDICTIONS_FILE}"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This model uses only pre-match historical "
        "features and does not use current-match goals."
    )

    print(
        "The reported metrics are out-of-sample."
    )

    print(
        "Accuracy alone does NOT prove that the strategy "
        "is profitable."
    )

    print(
        "Before connecting Risk Manager/CFO to real "
        "betting decisions, we need bookmaker odds, "
        "EV calculations, ROI, drawdown and walk-forward validation."
    )


if __name__ == "__main__":
    main()