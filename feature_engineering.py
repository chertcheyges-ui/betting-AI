"""
Feature Engineering for AI Betting System.

Input:
    data/processed/historical_fixtures.csv

Output:
    data/processed/model_dataset.csv

Important:
    All predictive features are calculated using ONLY matches
    that happened before the current fixture.

This prevents data leakage.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd


class FeatureEngineer:
    """Build chronological football features for a betting ML model."""

    RECENT_WINDOW = 5
    HOME_AWAY_WINDOW = 5
    H2H_WINDOW = 5

    INPUT_PATH = Path("data/processed/historical_fixtures.csv")
    OUTPUT_PATH = Path("data/processed/model_dataset.csv")

    def __init__(
        self,
        input_path: str | Path | None = None,
        output_path: str | Path | None = None,
    ):
        self.input_path = Path(input_path or self.INPUT_PATH)
        self.output_path = Path(output_path or self.OUTPUT_PATH)

    # =========================================================
    # BASIC HELPERS
    # =========================================================

    @staticmethod
    def safe_mean(values):
        """Return mean or 0 when there is no history."""
        if not values:
            return 0.0

        numeric = [
            float(value)
            for value in values
            if value is not None and not pd.isna(value)
        ]

        if not numeric:
            return 0.0

        return float(np.mean(numeric))

    @staticmethod
    def safe_sum(values):
        """Return sum or 0."""
        if not values:
            return 0.0

        numeric = [
            float(value)
            for value in values
            if value is not None and not pd.isna(value)
        ]

        return float(np.sum(numeric)) if numeric else 0.0

    @staticmethod
    def result_for_team(goals_for, goals_against):
        """Return W/D/L from a team's perspective."""
        if goals_for > goals_against:
            return "W"

        if goals_for < goals_against:
            return "L"

        return "D"

    @staticmethod
    def points_from_result(result):
        """Convert W/D/L into league points."""
        return {
            "W": 3,
            "D": 1,
            "L": 0,
        }.get(result, 0)

    @staticmethod
    def normalize_columns(df):
        """Normalize common column-name variations."""

        aliases = {
            "fixture": "fixture_id",
            "id": "fixture_id",
            "fixtureid": "fixture_id",

            "datetime": "date",
            "match_date": "date",

            "home": "home_team",
            "hometeam": "home_team",
            "home_name": "home_team",

            "away": "away_team",
            "awayteam": "away_team",
            "away_name": "away_team",

            "home_id": "home_team_id",
            "hometeamid": "home_team_id",

            "away_id": "away_team_id",
            "awayteamid": "away_team_id",

            "home_score": "home_goals",
            "homescore": "home_goals",
            "goals_home": "home_goals",

            "away_score": "away_goals",
            "awayscore": "away_goals",
            "goals_away": "away_goals",
        }

        rename_map = {}

        for column in df.columns:
            normalized = (
                str(column)
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )

            if normalized in aliases:
                rename_map[column] = aliases[normalized]

        return df.rename(columns=rename_map)

    # =========================================================
    # LOAD DATA
    # =========================================================

    def load_data(self):
        """Load and validate historical fixtures."""

        if not self.input_path.exists():
            raise FileNotFoundError(
                f"Input dataset not found:\n{self.input_path}"
            )

        df = pd.read_csv(self.input_path)

        if df.empty:
            raise ValueError("Historical dataset is empty.")

        df = self.normalize_columns(df)

        required = [
            "date",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Dataset is missing required columns: "
                + ", ".join(missing)
                + "\n\nAvailable columns:\n"
                + ", ".join(df.columns.astype(str))
            )

        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce",
            utc=True,
        )

        df["home_goals"] = pd.to_numeric(
            df["home_goals"],
            errors="coerce",
        )

        df["away_goals"] = pd.to_numeric(
            df["away_goals"],
            errors="coerce",
        )

        before = len(df)

        df = df.dropna(
            subset=[
                "date",
                "home_team",
                "away_team",
                "home_goals",
                "away_goals",
            ]
        ).copy()

        removed = before - len(df)

        if removed:
            print(
                f"Removed {removed} rows with invalid "
                "date/team/result data."
            )

        df["home_goals"] = df["home_goals"].astype(float)
        df["away_goals"] = df["away_goals"].astype(float)

        # Stable chronological order.
        sort_columns = ["date"]

        if "fixture_id" in df.columns:
            sort_columns.append("fixture_id")

        df = df.sort_values(sort_columns).reset_index(drop=True)

        return df

    # =========================================================
    # TEAM HISTORY
    # =========================================================

    @staticmethod
    def empty_history():
        return {
            "overall": deque(),
            "home": deque(),
            "away": deque(),
        }

    def make_match_record(
        self,
        goals_for,
        goals_against,
        date,
    ):
        """Create a historical team record."""

        result = self.result_for_team(
            goals_for,
            goals_against,
        )

        return {
            "gf": float(goals_for),
            "ga": float(goals_against),
            "result": result,
            "points": self.points_from_result(result),
            "date": date,
        }

    # =========================================================
    # TEAM FEATURES
    # =========================================================

    def get_team_features(
        self,
        history,
        prefix,
    ):
        """
        Build features from historical matches.

        history contains matches BEFORE the current fixture.
        """

        recent = list(history)[-self.RECENT_WINDOW:]

        points = [
            item["points"]
            for item in recent
        ]

        goals_for = [
            item["gf"]
            for item in recent
        ]

        goals_against = [
            item["ga"]
            for item in recent
        ]

        wins = sum(
            1
            for item in recent
            if item["result"] == "W"
        )

        draws = sum(
            1
            for item in recent
            if item["result"] == "D"
        )

        losses = sum(
            1
            for item in recent
            if item["result"] == "L"
        )

        features = {
            f"{prefix}_matches_before": len(history),

            f"{prefix}_recent_points":
                self.safe_sum(points),

            f"{prefix}_recent_points_per_game":
                self.safe_mean(points),

            f"{prefix}_recent_goals_for":
                self.safe_mean(goals_for),

            f"{prefix}_recent_goals_against":
                self.safe_mean(goals_against),

            f"{prefix}_recent_goal_difference":
                self.safe_mean(
                    [
                        gf - ga
                        for gf, ga in zip(
                            goals_for,
                            goals_against,
                        )
                    ]
                ),

            f"{prefix}_recent_wins": wins,
            f"{prefix}_recent_draws": draws,
            f"{prefix}_recent_losses": losses,

            f"{prefix}_win_rate":
                wins / len(recent)
                if recent else 0.0,

            f"{prefix}_draw_rate":
                draws / len(recent)
                if recent else 0.0,

            f"{prefix}_loss_rate":
                losses / len(recent)
                if recent else 0.0,
        }

        return features

    def get_home_away_features(
        self,
        history,
        prefix,
    ):
        """
        Features specifically for home or away matches.
        """

        recent = list(history)[-self.HOME_AWAY_WINDOW:]

        points = [
            item["points"]
            for item in recent
        ]

        goals_for = [
            item["gf"]
            for item in recent
        ]

        goals_against = [
            item["ga"]
            for item in recent
        ]

        wins = sum(
            item["result"] == "W"
            for item in recent
        )

        features = {
            f"{prefix}_matches_before": len(history),

            f"{prefix}_points_per_game":
                self.safe_mean(points),

            f"{prefix}_goals_for":
                self.safe_mean(goals_for),

            f"{prefix}_goals_against":
                self.safe_mean(goals_against),

            f"{prefix}_goal_difference":
                self.safe_mean(
                    [
                        gf - ga
                        for gf, ga in zip(
                            goals_for,
                            goals_against,
                        )
                    ]
                ),

            f"{prefix}_win_rate":
                wins / len(recent)
                if recent else 0.0,
        }

        return features

    # =========================================================
    # H2H
    # =========================================================

    def get_h2h_features(
        self,
        h2h_history,
        home_team,
    ):
        """
        Calculate historical H2H features from the perspective
        of the current home team.
        """

        recent = list(h2h_history)[-self.H2H_WINDOW:]

        if not recent:
            return {
                "h2h_matches_before": 0,
                "h2h_home_team_points_per_game": 0.0,
                "h2h_home_team_goals_for": 0.0,
                "h2h_home_team_goals_against": 0.0,
                "h2h_home_team_win_rate": 0.0,
            }

        points = []
        goals_for = []
        goals_against = []
        wins = 0

        for match in recent:
            if match["home_team"] == home_team:
                gf = match["home_goals"]
                ga = match["away_goals"]
            else:
                gf = match["away_goals"]
                ga = match["home_goals"]

            result = self.result_for_team(gf, ga)

            points.append(
                self.points_from_result(result)
            )

            goals_for.append(gf)
            goals_against.append(ga)

            if result == "W":
                wins += 1

        return {
            "h2h_matches_before": len(recent),

            "h2h_home_team_points_per_game":
                self.safe_mean(points),

            "h2h_home_team_goals_for":
                self.safe_mean(goals_for),

            "h2h_home_team_goals_against":
                self.safe_mean(goals_against),

            "h2h_home_team_win_rate":
                wins / len(recent),
        }

    # =========================================================
    # MAIN FEATURE BUILDING
    # =========================================================

    def build_features(self, df):
        """
        Build chronological features.

        VERY IMPORTANT:
        Features are calculated before adding the current match
        to the historical team records.
        """

        team_histories = defaultdict(
            self.empty_history
        )

        h2h_histories = defaultdict(deque)

        rows = []

        print(
            "Building chronological team histories..."
        )

        for index, row in df.iterrows():

            home_team = str(row["home_team"])
            away_team = str(row["away_team"])

            home_goals = float(row["home_goals"])
            away_goals = float(row["away_goals"])

            date_value = row["date"]

            # -------------------------------------------------
            # Historical information BEFORE current match
            # -------------------------------------------------

            home_history = team_histories[
                home_team
            ]

            away_history = team_histories[
                away_team
            ]

            home_overall = self.get_team_features(
                home_history["overall"],
                "home",
            )

            away_overall = self.get_team_features(
                away_history["overall"],
                "away",
            )

            home_specific = self.get_home_away_features(
                home_history["home"],
                "home_home",
            )

            away_specific = self.get_home_away_features(
                away_history["away"],
                "away_away",
            )

            h2h_key = tuple(
                sorted(
                    [
                        home_team,
                        away_team,
                    ]
                )
            )

            h2h_features = self.get_h2h_features(
                h2h_histories[h2h_key],
                home_team,
            )

            feature_row = {
                "fixture_index": index,
                "date": date_value,

                "home_team": home_team,
                "away_team": away_team,

                "home_goals": home_goals,
                "away_goals": away_goals,

                **home_overall,
                **away_overall,
                **home_specific,
                **away_specific,
                **h2h_features,
            }

            # -------------------------------------------------
            # Difference features
            # -------------------------------------------------

            feature_row[
                "form_edge"
            ] = (
                feature_row["home_recent_points_per_game"]
                - feature_row["away_recent_points_per_game"]
            )

            feature_row[
                "attack_edge"
            ] = (
                feature_row["home_recent_goals_for"]
                - feature_row["away_recent_goals_for"]
            )

            feature_row[
                "defense_edge"
            ] = (
                feature_row["away_recent_goals_against"]
                - feature_row["home_recent_goals_against"]
            )

            feature_row[
                "goal_difference_edge"
            ] = (
                feature_row["home_recent_goal_difference"]
                - feature_row["away_recent_goal_difference"]
            )

            feature_row[
                "home_away_form_edge"
            ] = (
                feature_row["home_home_points_per_game"]
                - feature_row["away_away_points_per_game"]
            )

            feature_row[
                "home_away_attack_edge"
            ] = (
                feature_row["home_home_goals_for"]
                - feature_row["away_away_goals_for"]
            )

            feature_row[
                "home_away_defense_edge"
            ] = (
                feature_row["away_away_goals_against"]
                - feature_row["home_home_goals_against"]
            )

            # -------------------------------------------------
            # Data quality
            # -------------------------------------------------

            feature_row[
                "home_history_available"
            ] = int(
                feature_row["home_matches_before"] > 0
            )

            feature_row[
                "away_history_available"
            ] = int(
                feature_row["away_matches_before"] > 0
            )

            feature_row[
                "home_home_history_available"
            ] = int(
                feature_row["home_home_matches_before"] > 0
            )

            feature_row[
                "away_away_history_available"
            ] = int(
                feature_row["away_away_matches_before"] > 0
            )

            feature_row[
                "h2h_history_available"
            ] = int(
                feature_row["h2h_matches_before"] > 0
            )

            feature_row[
                "history_quality_score"
            ] = (
                feature_row["home_history_available"]
                + feature_row["away_history_available"]
                + feature_row["home_home_history_available"]
                + feature_row["away_away_history_available"]
                + feature_row["h2h_history_available"]
            ) / 5.0

            # -------------------------------------------------
            # TARGET
            # -------------------------------------------------

            if home_goals > away_goals:
                result = "HOME_WIN"
                target = 0

            elif home_goals < away_goals:
                result = "AWAY_WIN"
                target = 2

            else:
                result = "DRAW"
                target = 1

            feature_row["result"] = result
            feature_row["target"] = target

            rows.append(feature_row)

            # -------------------------------------------------
            # NOW add current match to history.
            # -------------------------------------------------

            home_record = self.make_match_record(
                home_goals,
                away_goals,
                date_value,
            )

            away_record = self.make_match_record(
                away_goals,
                home_goals,
                date_value,
            )

            team_histories[
                home_team
            ]["overall"].append(home_record)

            team_histories[
                home_team
            ]["home"].append(home_record)

            team_histories[
                away_team
            ]["overall"].append(away_record)

            team_histories[
                away_team
            ]["away"].append(away_record)

            h2h_histories[h2h_key].append(
                {
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "date": date_value,
                }
            )

        return pd.DataFrame(rows)

    # =========================================================
    # CLEAN DATASET
    # =========================================================

    def clean_dataset(self, df):
        """Clean feature dataset for ML."""

        # Remove helper column.
        if "fixture_index" in df.columns:
            df = df.drop(
                columns=["fixture_index"]
            )

        # Convert booleans / numerical fields.
        numeric_columns = df.select_dtypes(
            include=["number"]
        ).columns

        df[numeric_columns] = df[
            numeric_columns
        ].replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # Historical absence is represented by zero.
        df[numeric_columns] = df[
            numeric_columns
        ].fillna(0.0)

        # Keep chronological order.
        df = df.sort_values(
            "date"
        ).reset_index(drop=True)

        return df

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, df):
        """Save processed dataset."""

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(
            self.output_path,
            index=False,
        )

        return self.output_path

    # =========================================================
    # RUN
    # =========================================================

    def run(self):
        print()
        print("=" * 70)
        print("FEATURE ENGINEERING")
        print("=" * 70)

        print(
            f"Input:  {self.input_path}"
        )

        print(
            f"Output: {self.output_path}"
        )

        print()

        df = self.load_data()

        print(
            f"Historical fixtures loaded: {len(df)}"
        )

        print(
            f"Date range: "
            f"{df['date'].min()} -> {df['date'].max()}"
        )

        print()

        dataset = self.build_features(df)

        dataset = self.clean_dataset(
            dataset
        )

        output_path = self.save(
            dataset
        )

        print()
        print("=" * 70)
        print("FEATURE ENGINEERING COMPLETE")
        print("=" * 70)

        print(
            f"Rows:    {len(dataset)}"
        )

        print(
            f"Columns: {len(dataset.columns)}"
        )

        print(
            f"Saved:   {output_path}"
        )

        print()

        print("Target distribution:")

        print(
            dataset["result"]
            .value_counts()
            .to_string()
        )

        print()

        print("History quality:")

        print(
            dataset[
                "history_quality_score"
            ]
            .describe()
            .round(3)
            .to_string()
        )

        print()

        print("Example rows:")

        preview_columns = [
            "date",
            "home_team",
            "away_team",
            "home_recent_points_per_game",
            "away_recent_points_per_game",
            "form_edge",
            "goal_difference_edge",
            "h2h_matches_before",
            "result",
            "target",
        ]

        available_preview = [
            column
            for column in preview_columns
            if column in dataset.columns
        ]

        print(
            dataset[
                available_preview
            ]
            .head(10)
            .to_string(index=False)
        )

        print()
        print("=" * 70)

        return dataset


def main():
    engineer = FeatureEngineer()
    engineer.run()


if __name__ == "__main__":
    main()