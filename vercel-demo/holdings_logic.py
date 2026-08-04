from __future__ import annotations

from datetime import date
from typing import Dict, Optional


def compute_sell_signal(scores: Dict[str, Dict[str, object]]) -> Dict[str, str]:
    short_term_score = scores["short_term"]["score"]
    swing_score = scores["swing"]["score"]

    if short_term_score < 0 and swing_score < 0:
        return {
            "action": "Consider selling",
            "reason": "Both short-term and long-term signals have turned negative.",
        }
    if short_term_score < 0 <= swing_score:
        return {
            "action": "Short-term weakness",
            "reason": "Short-term signal is negative but the long-term signal is still positive — your call whether to ride it out.",
        }
    if swing_score < 0 <= short_term_score:
        return {
            "action": "Long-term weakness",
            "reason": "Long-term signal is negative but short-term is still positive — may be worth watching closely.",
        }
    return {"action": "Hold", "reason": "Both short-term and long-term signals remain positive."}


def compute_holding_period(buy_date: date, symbol: str) -> Dict[str, Optional[object]]:
    days_held = (date.today() - buy_date).days
    ltcg_applicable = symbol.upper().endswith((".NS", ".BO"))
    if not ltcg_applicable:
        return {
            "days_held": days_held,
            "ltcg_applicable": False,
            "ltcg_eligible": None,
            "days_to_ltcg": None,
        }
    ltcg_eligible = days_held >= 365
    days_to_ltcg = max(0, 365 - days_held)
    return {
        "days_held": days_held,
        "ltcg_applicable": True,
        "ltcg_eligible": ltcg_eligible,
        "days_to_ltcg": days_to_ltcg,
    }
