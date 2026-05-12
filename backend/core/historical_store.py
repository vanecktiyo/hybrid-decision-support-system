"""
Historical Store - Persist validated rankings for incremental ML training.
Each session saved as CSV: [feature_cols..., Validated_Tier]
Tier labels: Faible | Moyen | Bon | Excellent
"""
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

TIER_LABELS = ["Faible", "Moyen", "Bon", "Excellent"]
VALID_TIERS = set(TIER_LABELS)


class HistoricalStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ write
    def save(self, features: pd.DataFrame, tiers: pd.Series, session_id: str) -> str:
        """Persist a validated session. tiers must contain TIER_LABELS values."""
        df = features.copy().reset_index(drop=True)
        df["Validated_Tier"] = tiers.values
        filepath = self.base_dir / f"{session_id}.csv"
        df.to_csv(str(filepath), index=False)
        logger.info(f"Historical session saved: {session_id} ({len(df)} records)")
        return str(filepath)

    # ------------------------------------------------------------------ read
    def load_all(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """Concatenate all historical sessions into (X, y) for training."""
        files = sorted(self.base_dir.glob("*.csv"))
        if not files:
            return None, None

        frames = []
        for f in files:
            try:
                df = pd.read_csv(str(f))
                if "Validated_Tier" in df.columns:
                    frames.append(df)
                else:
                    logger.warning(f"Skip {f.name}: no Validated_Tier column")
            except Exception as exc:
                logger.warning(f"Failed to load {f.name}: {exc}")

        if not frames:
            return None, None

        combined = pd.concat(frames, ignore_index=True)
        y = combined["Validated_Tier"]
        X = combined.drop(columns=["Validated_Tier"])
        return X, y

    # ------------------------------------------------------------------ meta
    def list_sessions(self) -> List[dict]:
        sessions = []
        for f in sorted(self.base_dir.glob("*.csv")):
            try:
                df = pd.read_csv(str(f))
                tier_dist = (
                    df["Validated_Tier"].value_counts().to_dict()
                    if "Validated_Tier" in df.columns
                    else {}
                )
                sessions.append(
                    {
                        "session_id": f.stem,
                        "n_records": len(df),
                        "tier_distribution": tier_dist,
                        "columns": [c for c in df.columns if c != "Validated_Tier"],
                    }
                )
            except Exception:
                pass
        return sessions

    def delete_session(self, session_id: str) -> bool:
        filepath = self.base_dir / f"{session_id}.csv"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted historical session: {session_id}")
            return True
        return False

    def n_sessions(self) -> int:
        return len(list(self.base_dir.glob("*.csv")))

    def total_records(self) -> int:
        total = 0
        for f in self.base_dir.glob("*.csv"):
            try:
                total += len(pd.read_csv(str(f)))
            except Exception:
                pass
        return total
