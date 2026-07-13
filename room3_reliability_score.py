"""
Room 3: Composite reliability scoring.

Fuses the outputs of Room 1 and Room 2, together with field
incompleteness and narrative-boilerplate duplication, into a single
0-100 reliability score per record. Reports both equal and entropy
weighting schemes and a Dirichlet-based sensitivity sweep.

Input : ARI workbook (sheets General, Factors); room1_audit_matrix.csv;
        room2_scores.csv
Output: room3_scores.csv
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PATH = "2006_to_2015.xlsx"
R1_PATH = "room1_audit_matrix.csv"
R2_PATH = "room2_scores.csv"
OUT = "room3_scores.csv"

KEY_FIELDS = [
    "Accident Severity", "Day", "Date", "Month", "Year", "Time", "District",
    "Junction Type", "Traffic Control", "Collision Type", "Movement", "Divider",
    "Weather", "Light", "Road Geometry", "Surface Condition", "Surface Type",
    "Surface Quality", "Road Class", "Road Feature", "Location Type",
]


def run(path=PATH, r1_path=R1_PATH, r2_path=R2_PATH, out=OUT, n_sweep=1000, seed=42):
    r1 = pd.read_csv(r1_path, dtype={"Acc_ID": str})
    r2 = pd.read_csv(r2_path, dtype={"Acc_ID": str})

    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()
    fac = pd.read_excel(path, sheet_name="Factors")
    fac["Acc_ID"] = fac["Acc_ID"].astype(str).str.strip()

    p1 = (r1["Tier1_flags"].clip(upper=3) / 3).values
    p2 = (r1["Tier2_flags"].clip(upper=2) / 2).values
    p3 = (r2[["iso_pct", "lof_pct", "ae_pct", "ecod_pct"]].mean(axis=1) / 100).values

    def is_blank(col):
        return general[col].astype(str).str.strip().isin(["", "nan", "None"]) | general[col].isna()

    p4 = pd.concat([is_blank(c) for c in KEY_FIELDS], axis=1).mean(axis=1).values

    desc = fac.dropna(subset=["Acc_ID"]).copy()
    desc["norm"] = (
        desc["Acc Description"]
        .astype(str)
        .str.lower()
        .str.replace(r"[^a-z0-9 ]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    freq_map = desc["norm"].value_counts()
    desc["narr_freq"] = desc["norm"].map(freq_map)
    id_freq = desc.groupby("Acc_ID")["narr_freq"].max()
    nf = general["Acc_ID"].map(id_freq).fillna(freq_map.max())
    p5 = pd.Series(nf).rank(pct=True).values

    p = np.column_stack([p1, p2, p3, p4, p5])
    names = ["Tier1", "Tier2", "Anomaly", "Incomplete", "Boilerplate"]

    w_eq = np.full(5, 0.2)
    score_eq = 100 * (1 - p @ w_eq)

    p_norm = p / np.maximum(p.sum(axis=0), 1e-12)
    log_p = np.where(p_norm > 0, np.log(np.where(p_norm > 0, p_norm, 1)), 0.0)
    entropy = -(p_norm * log_p).sum(axis=0) / np.log(len(p))
    diversity = 1 - entropy
    w_ent = diversity / diversity.sum()
    score_ent = 100 * (1 - p @ w_ent)

    rng = np.random.default_rng(seed)
    correlations = np.array(
        [spearmanr(score_eq, 100 * (1 - p @ rng.dirichlet(np.ones(5)))).statistic for _ in range(n_sweep)]
    )

    out_df = pd.DataFrame(
        {
            "Acc_ID": r1["Acc_ID"],
            "score_equal": score_eq,
            "score_entropy": score_ent,
            "P1_tier1": p1,
            "P2_tier2": p2,
            "P3_anomaly": p3,
            "P4_incomplete": p4,
            "P5_boilerplate": p5,
        }
    )
    out_df["grade"] = pd.cut(out_df["score_equal"], bins=[-1, 50, 75, 90, 101], labels=["D", "C", "B", "A"])
    out_df.to_csv(out, index=False)

    summary = {
        "entropy_weights": dict(zip(names, w_ent.round(3))),
        "mean": score_eq.mean(),
        "median": float(np.median(score_eq)),
        "min": score_eq.min(),
        "grade_counts": out_df["grade"].value_counts().sort_index(ascending=False).to_dict(),
        "rho_equal_vs_entropy": spearmanr(score_eq, score_ent).statistic,
        "sweep_median": float(np.median(correlations)),
        "sweep_min": float(correlations.min()),
    }
    return out_df, summary


if __name__ == "__main__":
    _, summary = run()
    for k, v in summary.items():
        print(f"{k}: {v}")
