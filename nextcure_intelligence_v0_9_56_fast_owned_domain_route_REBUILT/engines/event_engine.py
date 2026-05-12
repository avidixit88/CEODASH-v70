"""Event reaction engine linking catalyst context with recent market returns."""

from __future__ import annotations

import pandas as pd

from engines.relative_performance_engine import safe_return


def build_event_reaction_table(catalyst_table: pd.DataFrame, return_table: pd.DataFrame) -> pd.DataFrame:
    if catalyst_table.empty or return_table.empty:
        return pd.DataFrame()
    rows = []
    for _, event in catalyst_table.iterrows():
        ticker = str(event["ticker"])
        r5 = safe_return(return_table, ticker, "5D %")
        r30 = safe_return(return_table, ticker, "30D %")
        r90 = safe_return(return_table, ticker, "90D %")
        label = "No usable market reaction data"
        meaning = "Market behavior cannot be interpreted yet."
        if r5 is not None and r30 is not None:
            if r5 > 5 and r30 > 0:
                label = "Positive positioning"
                meaning = "Investors appear to be buying or holding strength into the event context."
            elif r5 < -5 and r30 < 0:
                label = "Weak positioning"
                meaning = "The stock is not being rewarded into the event context."
            elif r5 > 3 and r30 < 0:
                label = "Rebound attempt"
                meaning = "Recent strength may be a bounce from a weak base, not confirmed accumulation yet."
            elif abs(r5) <= 3:
                label = "Muted positioning"
                meaning = "The event is not yet producing a strong price signal."
            else:
                label = "Mixed positioning"
                meaning = "Different timeframes disagree, so avoid over-reading the move."
        rows.append({
            "Ticker": ticker,
            "Company": event["company"],
            "Event": event["title"],
            "Timing": event["expected_timing"],
            "Impact": event["impact"],
            "Read-Through": event["read_through"],
            "5D %": r5,
            "30D %": r30,
            "90D %": r90,
            "Reaction Label": label,
            "Meaning": meaning,
        })
    return pd.DataFrame(rows).sort_values(["Impact", "5D %"], ascending=[True, False], na_position="last")


def build_event_reaction_insights(reaction_table: pd.DataFrame) -> list[str]:
    if reaction_table.empty:
        return ["Event reaction layer is waiting for both catalyst records and usable return data."]
    insights = []
    nxtc = reaction_table[reaction_table["Ticker"] == "NXTC"]
    if not nxtc.empty:
        first = nxtc.iloc[0]
        r5 = first.get("5D %")
        r30 = first.get("30D %")
        r5_txt = "N/A" if pd.isna(r5) else f"{float(r5):+.1f}%"
        r30_txt = "N/A" if pd.isna(r30) else f"{float(r30):+.1f}%"
        insights.append(f"NXTC event positioning: {first['Reaction Label']} ({r5_txt} over 5D, {r30_txt} over 30D). {first['Meaning']}")
    high = reaction_table[reaction_table["Impact"] == "High"]
    if not high.empty:
        constructive = high[high["Reaction Label"].str.contains("Positive|Rebound", case=False, regex=True)]
        insights.append(f"High-impact catalyst cohort: {len(constructive)} of {len(high)} item(s) show positive or rebound positioning.")
    return insights
