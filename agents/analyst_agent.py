import json
import math
import os


class QuantitativeSportsAnalyst:
    """
    Quantitative Sports Analyst

    Pure Python implementation.

    Responsibilities:
    1. Load trained softmax model.
    2. Build pre-match feature vector.
    3. Standardize using training statistics.
    4. Calculate model probabilities.
    5. Validate bookmaker Match Winner odds.
    6. Calculate implied probabilities.
    7. Calculate edge.
    8. Calculate EV.
    9. Select the best positive-EV market.
    10. Return data compatible with Risk Manager and Auditor.
    """

    MODEL_PATH = "data/models/betting_model.json"

    CLASSES = [
        "HOME_WIN",
        "DRAW",
        "AWAY_WIN",
    ]

    # Kept as an additional validation layer.
    # The actual model feature list comes from model["feature_names"].
    REQUIRED_FEATURES = [
        "home_matches_before",
        "home_recent_points",
        "home_recent_points_per_game",
        "home_recent_goals_for",
        "home_recent_goals_against",
        "home_recent_goal_difference",
        "home_recent_wins",
        "home_recent_draws",
        "home_recent_losses",
        "home_win_rate",
        "home_draw_rate",
        "home_loss_rate",

        "away_matches_before",
        "away_recent_points",
        "away_recent_points_per_game",
        "away_recent_goals_for",
        "away_recent_goals_against",
        "away_recent_goal_difference",
        "away_recent_wins",
        "away_recent_draws",
        "away_recent_losses",
        "away_win_rate",
        "away_draw_rate",
        "away_loss_rate",

        "home_home_matches_before",
        "home_home_points_per_game",
        "home_home_goals_for",
        "home_home_goals_against",
        "home_home_goal_difference",
        "home_home_win_rate",

        "away_away_matches_before",
        "away_away_points_per_game",
        "away_away_goals_for",
        "away_away_goals_against",
        "away_away_goal_difference",
        "away_away_win_rate",

        "h2h_matches_before",
        "h2h_home_team_points_per_game",
        "h2h_home_team_goals_for",
        "h2h_home_team_goals_against",
        "h2h_home_team_win_rate",

        "form_edge",
        "attack_edge",
        "defense_edge",
        "goal_difference_edge",

        "home_away_form_edge",
        "home_away_attack_edge",
        "home_away_defense_edge",

        "home_history_available",
        "away_history_available",
        "home_home_history_available",
        "away_away_history_available",
        "h2h_history_available",

        "history_quality_score",
    ]

    def __init__(
        self,
        model_path=None,
        min_ev=0.03,
        min_probability=0.0,
    ):
        self.name = "Quantitative Sports Analyst"

        self.model_path = (
            model_path
            or self.MODEL_PATH
        )

        # min_ev is decimal:
        # 0.03 = 3% EV
        self.min_ev = float(min_ev)

        # Minimum model probability.
        # 0.0 means no additional probability filter.
        self.min_probability = float(
            min_probability
        )

        self.model = None
        self.model_loaded = False

        self.feature_names = []
        self.feature_means = []
        self.feature_stds = []
        self.weights = []
        self.bias = []
        self.classes = []

        self._load_model()

    # ==========================================================
    # MODEL LOADING
    # ==========================================================

    def _load_model(self):
        """Load the trained pure-Python softmax model."""

        if not os.path.exists(
            self.model_path
        ):
            print(
                "WARNING: model file not found: "
                f"{self.model_path}"
            )
            return

        try:
            with open(
                self.model_path,
                "r",
                encoding="utf-8",
            ) as file:
                model = json.load(file)

        except (
            OSError,
            ValueError,
            TypeError,
        ) as error:
            print(
                "WARNING: failed to load model: "
                f"{error}"
            )
            return

        required = [
            "feature_names",
            "feature_means",
            "feature_stds",
            "weights",
            "bias",
            "classes",
        ]

        missing = [
            field
            for field in required
            if field not in model
        ]

        if missing:
            print(
                "WARNING: model is missing fields: "
                + ", ".join(missing)
            )
            return

        try:
            feature_names = model[
                "feature_names"
            ]

            feature_means = model[
                "feature_means"
            ]

            feature_stds = model[
                "feature_stds"
            ]

            weights = model[
                "weights"
            ]

            bias = model[
                "bias"
            ]

            classes = model[
                "classes"
            ]

            if not isinstance(
                feature_names,
                list,
            ):
                raise ValueError(
                    "feature_names must be a list"
                )

            if not isinstance(
                feature_means,
                list,
            ):
                raise ValueError(
                    "feature_means must be a list"
                )

            if not isinstance(
                feature_stds,
                list,
            ):
                raise ValueError(
                    "feature_stds must be a list"
                )

            if not isinstance(
                weights,
                list,
            ):
                raise ValueError(
                    "weights must be a list"
                )

            if not isinstance(
                bias,
                list,
            ):
                raise ValueError(
                    "bias must be a list"
                )

            if not isinstance(
                classes,
                list,
            ):
                raise ValueError(
                    "classes must be a list"
                )

            if not feature_names:
                raise ValueError(
                    "Model contains no features."
                )

            if len(feature_means) != len(
                feature_names
            ):
                raise ValueError(
                    "feature_means length does not "
                    "match feature_names."
                )

            if len(feature_stds) != len(
                feature_names
            ):
                raise ValueError(
                    "feature_stds length does not "
                    "match feature_names."
                )

            if len(weights) != len(
                classes
            ):
                raise ValueError(
                    "weights/class count mismatch."
                )

            if len(bias) != len(
                classes
            ):
                raise ValueError(
                    "bias/class count mismatch."
                )

            for class_weights in weights:
                if len(class_weights) != len(
                    feature_names
                ):
                    raise ValueError(
                        "Weight/feature count mismatch."
                    )

            if len(classes) != 3:
                raise ValueError(
                    "Expected exactly 3 classes."
                )

            if classes != self.CLASSES:
                print(
                    "WARNING: model classes differ "
                    "from expected classes:"
                )
                print(
                    f"  Model:    {classes}"
                )
                print(
                    f"  Expected: {self.CLASSES}"
                )

            self.model = model

            self.feature_names = feature_names
            self.feature_means = feature_means
            self.feature_stds = feature_stds
            self.weights = weights
            self.bias = bias
            self.classes = classes

            self.model_loaded = True

            print(
                f"Model loaded: {self.model_path}"
            )

            print(
                f"Model features: "
                f"{len(self.feature_names)}"
            )

        except (
            ValueError,
            TypeError,
        ) as error:
            print(
                "WARNING: invalid model: "
                f"{error}"
            )

    # ==========================================================
    # BASIC HELPERS
    # ==========================================================

    @staticmethod
    def _to_float(value):
        """Convert value to finite float."""

        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return float(value)

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(result):
            return None

        return result

    @staticmethod
    def _safe_probability(value):
        """Keep probability inside [0, 1]."""

        value = float(value)

        if value < 0.0:
            return 0.0

        if value > 1.0:
            return 1.0

        return value

    @staticmethod
    def _softmax(logits):
        """Numerically stable softmax."""

        if not logits:
            return []

        maximum = max(logits)

        exponentials = [
            math.exp(
                value - maximum
            )
            for value in logits
        ]

        total = sum(exponentials)

        if (
            total <= 0
            or not math.isfinite(total)
        ):
            return [
                1.0 / len(logits)
                for _ in logits
            ]

        return [
            value / total
            for value in exponentials
        ]

    # ==========================================================
    # DATASET VALIDATION
    # ==========================================================

    def check_dataset(
        self,
        event,
    ):
        """
        Validate features required by the trained model.

        Important:
        The model's own feature_names are the source of truth.
        """

        missing = []

        if not self.model_loaded:
            return [
                "trained_model"
            ]

        for feature in self.feature_names:

            if feature not in event:
                missing.append(feature)
                continue

            value = event.get(feature)

            if value is None:
                missing.append(feature)
                continue

            if self._to_float(value) is None:
                missing.append(feature)

        return missing

    # ==========================================================
    # FEATURE VECTOR
    # ==========================================================

    def build_feature_vector(
        self,
        event,
    ):
        """
        Build feature vector in EXACTLY the same order
        used during model training.

        Missing numeric values become 0.0.

        Standardization uses training-set statistics
        saved inside betting_model.json.
        """

        if not self.model_loaded:
            raise RuntimeError(
                "Model is not loaded."
            )

        vector = []

        for index, feature in enumerate(
            self.feature_names
        ):

            value = self._to_float(
                event.get(feature)
            )

            if value is None:
                value = 0.0

            mean = self._to_float(
                self.feature_means[index]
            )

            std = self._to_float(
                self.feature_stds[index]
            )

            if mean is None:
                mean = 0.0

            if (
                std is None
                or abs(std) < 1e-12
            ):
                std = 1.0

            normalized = (
                value - mean
            ) / std

            if not math.isfinite(
                normalized
            ):
                normalized = 0.0

            vector.append(
                normalized
            )

        return vector

    # ==========================================================
    # MODEL PREDICTION
    # ==========================================================

    def predict_probabilities(
        self,
        vector,
    ):
        """Calculate softmax probabilities."""

        if not self.model_loaded:
            raise RuntimeError(
                "Model is not loaded."
            )

        if len(vector) != len(
            self.feature_names
        ):
            raise ValueError(
                "Feature vector length does not "
                "match model."
            )

        logits = []

        for class_index in range(
            len(self.classes)
        ):

            score = self._to_float(
                self.bias[class_index]
            )

            if score is None:
                score = 0.0

            for feature_index in range(
                len(self.feature_names)
            ):

                weight = self._to_float(
                    self.weights[
                        class_index
                    ][feature_index]
                )

                if weight is None:
                    weight = 0.0

                score += (
                    weight
                    * vector[feature_index]
                )

            logits.append(score)

        probabilities = self._softmax(
            logits
        )

        return {
            class_name: probability
            for class_name, probability
            in zip(
                self.classes,
                probabilities,
            )
        }

    # ==========================================================
    # ODDS
    # ==========================================================

    def check_odds(
        self,
        event,
    ):
        """
        Validate bookmaker Match Winner odds.

        Accepted input:

        {
            "odds": {
                "bookmaker": "Example",
                "market": "Match Winner",
                "values": {
                    "Home": 2.10,
                    "Draw": 3.40,
                    "Away": 3.60
                }
            }
        }
        """

        odds = event.get("odds")

        if not isinstance(
            odds,
            dict,
        ):
            return (
                None,
                "Bookmaker odds are missing",
            )

        values = odds.get(
            "values"
        )

        if not isinstance(
            values,
            dict,
        ):
            return (
                None,
                "Odds values are missing",
            )

        aliases = {
            "Home": "HOME_WIN",
            "home": "HOME_WIN",
            "HOME": "HOME_WIN",
            "1": "HOME_WIN",
            "HOME_WIN": "HOME_WIN",

            "Draw": "DRAW",
            "draw": "DRAW",
            "DRAW": "DRAW",
            "X": "DRAW",

            "Away": "AWAY_WIN",
            "away": "AWAY_WIN",
            "AWAY": "AWAY_WIN",
            "2": "AWAY_WIN",
            "AWAY_WIN": "AWAY_WIN",
        }

        normalized = {}

        for key, value in values.items():

            normalized_key = aliases.get(
                str(key)
            )

            if not normalized_key:
                continue

            odd = self._to_float(
                value
            )

            if odd is None:
                continue

            # Decimal odds must be > 1.
            if odd <= 1.0:
                continue

            normalized[
                normalized_key
            ] = odd

        if not normalized:
            return (
                None,
                "No valid Match Winner odds",
            )

        return {
            "bookmaker": odds.get(
                "bookmaker"
            ),
            "market": odds.get(
                "market",
                "Match Winner",
            ),
            "values": normalized,
        }, None

    # ==========================================================
    # MARKET CALCULATIONS
    # ==========================================================

    @staticmethod
    def implied_probability(
        odds,
    ):
        """
        Decimal odds -> implied probability.

        Example:
        2.00 -> 0.50
        """

        odds = float(odds)

        if odds <= 1.0:
            return None

        return 1.0 / odds

    @staticmethod
    def calculate_ev(
        probability,
        odds,
    ):
        """
        Expected value per 1 unit stake.

        EV = p * odds - 1

        Returned as decimal.

        0.05 = +5%
        """

        probability = float(
            probability
        )

        odds = float(odds)

        return (
            probability * odds
        ) - 1.0

    @staticmethod
    def calculate_edge(
        model_probability,
        market_probability,
    ):
        """
        Edge in decimal probability.

        Example:

        Model = 0.57
        Market = 0.50

        Edge = 0.07
        """

        return (
            float(model_probability)
            - float(market_probability)
        )

    # ==========================================================
    # MARKET ANALYSIS
    # ==========================================================

    def analyze_markets(
        self,
        probabilities,
        odds_data,
    ):
        """
        Calculate metrics for every available Match Winner
        market.
        """

        markets = []

        values = odds_data[
            "values"
        ]

        for market_name in self.classes:

            if market_name not in values:
                continue

            model_probability = (
                probabilities.get(
                    market_name,
                    0.0,
                )
            )

            odds = values[
                market_name
            ]

            market_probability = (
                self.implied_probability(
                    odds
                )
            )

            if (
                market_probability is None
            ):
                continue

            edge = self.calculate_edge(
                model_probability,
                market_probability,
            )

            ev = self.calculate_ev(
                model_probability,
                odds,
            )

            markets.append({
                "market": "Match Winner",
                "selection": market_name,
                "odds": odds,

                "model_probability":
                    model_probability,

                "market_probability":
                    market_probability,

                "edge":
                    edge,

                "ev":
                    ev,
            })

        markets.sort(
            key=lambda item: item["ev"],
            reverse=True,
        )

        return markets

    # ==========================================================
    # BEST BET
    # ==========================================================

    def select_best_market(
        self,
        markets,
    ):
        """
        Select the best market that passes
        the Analyst thresholds.
        """

        if not markets:
            return None

        for market in markets:

            if (
                market[
                    "model_probability"
                ]
                < self.min_probability
            ):
                continue

            if (
                market["ev"]
                >= self.min_ev
            ):
                return market

        return None

    # ==========================================================
    # SINGLE EVENT
    # ==========================================================

    def analyze(
        self,
        event,
    ):
        """
        Analyze one football event.

        Returns a dictionary compatible with RiskManager.
        """

        if not isinstance(
            event,
            dict,
        ):
            return {
                "status": "NOT READY",
                "event": "Unknown event",
                "missing_data": [
                    "event"
                ],
                "message": (
                    "Event must be a dictionary."
                ),
            }

        home_team = event.get(
            "home_team",
            "Unknown Home",
        )

        away_team = event.get(
            "away_team",
            "Unknown Away",
        )

        event_name = (
            f"{home_team} vs {away_team}"
        )

        # ------------------------------------------------------
        # MODEL
        # ------------------------------------------------------

        if not self.model_loaded:
            return {
                "status": "NOT READY",
                "event": event_name,
                "missing_data": [
                    "trained_model"
                ],
                "message": (
                    "Trained model is unavailable."
                ),
            }

        # ------------------------------------------------------
        # DATASET
        # ------------------------------------------------------

        missing_features = (
            self.check_dataset(event)
        )

        if missing_features:
            return {
                "status": "NOT READY",
                "event": event_name,
                "missing_data":
                    missing_features,
                "message": (
                    "Required pre-match model "
                    "features are missing."
                ),
            }

        # ------------------------------------------------------
        # ODDS
        # ------------------------------------------------------

        odds_data, odds_error = (
            self.check_odds(event)
        )

        if odds_data is None:
            return {
                "status": "NOT READY",
                "event": event_name,
                "missing_data": [
                    "odds"
                ],
                "message": odds_error,
            }

        # ------------------------------------------------------
        # VECTOR
        # ------------------------------------------------------

        try:
            vector = (
                self.build_feature_vector(
                    event
                )
            )

            probabilities = (
                self.predict_probabilities(
                    vector
                )
            )

        except (
            RuntimeError,
            ValueError,
            TypeError,
            IndexError,
        ) as error:

            return {
                "status": "NOT READY",
                "event": event_name,
                "missing_data": [
                    "model_calculation"
                ],
                "message": str(error),
            }

        # ------------------------------------------------------
        # MARKETS
        # ------------------------------------------------------

        markets = (
            self.analyze_markets(
                probabilities,
                odds_data,
            )
        )

        if not markets:
            return {
                "status": "NOT READY",
                "event": event_name,
                "missing_data": [
                    "valid_match_winner_odds"
                ],
                "model_probabilities":
                    probabilities,
                "message": (
                    "No valid Match Winner "
                    "market is available."
                ),
            }

        # ------------------------------------------------------
        # BEST MARKET
        # ------------------------------------------------------

        best = (
            self.select_best_market(
                markets
            )
        )

        # ------------------------------------------------------
        # NO POSITIVE EV
        # ------------------------------------------------------

        if best is None:

            best_available = markets[0]

            return {
                "status": "READY",
                "event": event_name,

                "prediction": max(
                    probabilities,
                    key=probabilities.get,
                ),

                "model_probabilities":
                    probabilities,

                "markets": markets,

                "best_market": None,

                "model_probability":
                    best_available[
                        "model_probability"
                    ],

                "market_probability":
                    best_available[
                        "market_probability"
                    ],

                "edge":
                    best_available["edge"]
                    * 100.0,

                "ev":
                    best_available["ev"]
                    * 100.0,

                "missing_data": [],

                "bookmaker":
                    odds_data.get(
                        "bookmaker"
                    ),

                "message": (
                    "Model prediction calculated, "
                    "but no market passed the "
                    "minimum EV threshold."
                ),
            }

        # ------------------------------------------------------
        # POSITIVE EV CANDIDATE
        # ------------------------------------------------------

        return {
            "status": "READY",
            "event": event_name,

            "prediction":
                best["selection"],

            "model_probabilities":
                probabilities,

            "markets":
                markets,

            "best_market":
                best,

            "selection":
                best["selection"],

            "odds":
                best["odds"],

            "model_probability":
                best[
                    "model_probability"
                ]
                * 100.0,

            "market_probability":
                best[
                    "market_probability"
                ]
                * 100.0,

            "edge":
                best["edge"]
                * 100.0,

            "ev":
                best["ev"]
                * 100.0,

            "bookmaker":
                odds_data.get(
                    "bookmaker"
                ),

            "market":
                odds_data.get(
                    "market",
                    "Match Winner",
                ),

            "missing_data": [],

            "message": (
                "Positive-EV candidate "
                "passed Analyst thresholds."
            ),
        }

    # ==========================================================
    # MULTIPLE EVENTS
    # ==========================================================

    def run(
        self,
        data,
    ):
        """
        Analyze one or multiple events.

        Accepted:

        analyst.run(event)

        OR

        analyst.run({
            "events": [...]
        })

        OR

        analyst.run({
            "results": [...]
        })
        """

        print(
            f"{self.name} started."
        )

        if not isinstance(
            data,
            dict,
        ):
            return {
                "status": "error",
                "agent": self.name,
                "results": [],
                "message": (
                    "Expected event dictionary."
                ),
            }

        # ------------------------------------------------------
        # Determine input format.
        # ------------------------------------------------------

        if isinstance(
            data.get("events"),
            list,
        ):
            events = data[
                "events"
            ]

        elif isinstance(
            data.get("fixtures"),
            list,
        ):
            events = data[
                "fixtures"
            ]

        elif isinstance(
            data.get("results"),
            list,
        ):
            events = data[
                "results"
            ]

        else:
            events = [
                data
            ]

        # ------------------------------------------------------
        # Analyze
        # ------------------------------------------------------

        results = []

        for event in events:

            if not isinstance(
                event,
                dict,
            ):
                results.append({
                    "status": "NOT READY",
                    "event": "Unknown event",
                    "missing_data": [
                        "event"
                    ],
                    "message": (
                        "Invalid event format."
                    ),
                })
                continue

            results.append(
                self.analyze(event)
            )

        ready = [
            result
            for result in results
            if result.get("status")
            == "READY"
        ]

        candidates = [
            result
            for result in ready
            if result.get(
                "best_market"
            )
            is not None
            and result.get(
                "ev",
                0.0,
            )
            >= self.min_ev * 100.0
        ]

        # Highest EV first.
        candidates.sort(
            key=lambda item: item.get(
                "ev",
                0.0,
            ),
            reverse=True,
        )

        return {
            "status": "success",
            "agent": self.name,

            "results": results,

            "ready_count":
                len(ready),

            "candidate_count":
                len(candidates),

            "candidates":
                candidates,

            "message": (
                f"Analyzed {len(results)} event(s); "
                f"{len(candidates)} positive-EV "
                "candidate(s)."
            ),
        }


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    analyst = (
        QuantitativeSportsAnalyst()
    )

    print()

    sample_event = {
        "home_team": "Test Home",
        "away_team": "Test Away",

        # Example pre-match features.
        # In production these must come from
        # the same feature-engineering pipeline.

        "home_matches_before": 20,
        "home_recent_points": 10,
        "home_recent_points_per_game": 2.0,
        "home_recent_goals_for": 1.8,
        "home_recent_goals_against": 0.8,
        "home_recent_goal_difference": 1.0,
        "home_recent_wins": 3,
        "home_recent_draws": 1,
        "home_recent_losses": 1,
        "home_win_rate": 0.6,
        "home_draw_rate": 0.2,
        "home_loss_rate": 0.2,

        "away_matches_before": 20,
        "away_recent_points": 7,
        "away_recent_points_per_game": 1.4,
        "away_recent_goals_for": 1.2,
        "away_recent_goals_against": 1.4,
        "away_recent_goal_difference": -0.2,
        "away_recent_wins": 2,
        "away_recent_draws": 1,
        "away_recent_losses": 2,
        "away_win_rate": 0.4,
        "away_draw_rate": 0.2,
        "away_loss_rate": 0.4,

        "home_home_matches_before": 10,
        "home_home_points_per_game": 2.1,
        "home_home_goals_for": 1.9,
        "home_home_goals_against": 0.7,
        "home_home_goal_difference": 1.2,
        "home_home_win_rate": 0.7,

        "away_away_matches_before": 10,
        "away_away_points_per_game": 1.2,
        "away_away_goals_for": 1.1,
        "away_away_goals_against": 1.5,
        "away_away_goal_difference": -0.4,
        "away_away_win_rate": 0.3,

        "h2h_matches_before": 5,
        "h2h_home_team_points_per_game": 1.8,
        "h2h_home_team_goals_for": 1.6,
        "h2h_home_team_goals_against": 1.0,
        "h2h_home_team_win_rate": 0.6,

        "form_edge": 0.6,
        "attack_edge": 0.6,
        "defense_edge": 0.6,
        "goal_difference_edge": 1.2,

        "home_away_form_edge": 0.9,
        "home_away_attack_edge": 0.8,
        "home_away_defense_edge": 0.8,

        "home_history_available": 1,
        "away_history_available": 1,
        "home_home_history_available": 1,
        "away_away_history_available": 1,
        "h2h_history_available": 1,

        "history_quality_score": 1.0,

        "odds": {
            "bookmaker": "TEST",
            "market": "Match Winner",
            "values": {
                "Home": 2.10,
                "Draw": 3.40,
                "Away": 3.60,
            },
        },
    }

    result = analyst.run({
        "events": [
            sample_event
        ]
    })

    print()
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )