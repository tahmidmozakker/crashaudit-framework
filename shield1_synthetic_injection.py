import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from pyod.models.ecod import ECOD

from room2_anomaly_detection import CATEGORICAL_LEGAL, clean_cat

PATH = "2006_to_2015.xlsx"
R1_PATH = "room1_audit_matrix.csv"
R3_PATH = "room3_scores.csv"
N_PER_TYPE = 100
SEED = 42

ERROR_TYPES = [
    "legal_miscoding",
    "illegal_code",
    "row_shift",
    "casualty_inflation",
    "date_corruption",
]


def inject(row, error_type, rng):
    row = row.copy()
    if error_type == "legal_miscoding":
        for col in rng.choice(list(CATEGORICAL_LEGAL), size=2, replace=False):
            options = [v for v in CATEGORICAL_LEGAL[col] if str(v) != str(row[col])]
            row[col] = rng.choice(options)
    elif error_type == "illegal_code":
        col = rng.choice(list(CATEGORICAL_LEGAL))
        row[col] = rng.choice([0, 99, "?", "XX"])
    elif error_type == "row_shift":
        cols = ["Junction Type", "Traffic Control", "Collision Type", "Movement", "Divider"]
        values = [row[c] for c in cols]
        for c, v in zip(cols, [values[-1]] + values[:-1]):
            row[c] = v
    elif error_type == "casualty_inflation":
        row["No of Passenger Casualties"] = float(rng.integers(25, 60))
    elif error_type == "date_corruption":
        current = pd.to_numeric(pd.Series([row["Date"]]), errors="coerce").iloc[0]
        row["Date"] = ((current or 1) % 28) + 2
    return row


def run(path=PATH, r1_path=R1_PATH, r3_path=R3_PATH, n_per_type=N_PER_TYPE, seed=SEED):
    r3 = pd.read_csv(r3_path, dtype={"Acc_ID": str})
    r1 = pd.read_csv(r1_path, dtype={"Acc_ID": str})
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()

    rng = np.random.default_rng(seed)
    seed_mask = (r3["score_equal"] >= 90) & (r1["Room1_total_flags"] == 0)
    seed_idx = np.where(seed_mask.values)[0]
    seeds = rng.choice(seed_idx, size=len(ERROR_TYPES) * n_per_type, replace=False)

    copies, parents, labels = [], [], []
    for k, error_type in enumerate(ERROR_TYPES):
        for j in range(n_per_type):
            i = seeds[k * n_per_type + j]
            row = inject(general.iloc[i], error_type, rng)
            row["Acc_ID"] = f"SYN_{error_type[:2]}_{j}"
            copies.append(row)
            parents.append(general.iloc[i]["Acc_ID"])
            labels.append(error_type)

    synthetic = pd.DataFrame(copies)
    augmented = pd.concat([general, synthetic], ignore_index=True)
    parent_of = dict(zip(synthetic["Acc_ID"], parents))
    is_synthetic = augmented["Acc_ID"].str.startswith("SYN_")

    def num(s):
        return pd.to_numeric(s, errors="coerce")

    r1_legal = {**{k: set(v) for k, v in CATEGORICAL_LEGAL.items()},
                "Accident Severity": {"F", "G", "S", "M"}, "Day": set(range(1, 8)),
                "Month": set(range(1, 13)), "Year": set(range(6, 16)), "District": set(range(1, 71))}
    tier1_flags = pd.DataFrame(index=augmented.index)
    for col, legal in r1_legal.items():
        letters = col == "Accident Severity"
        def check(v, legal=legal, letters=letters):
            if pd.isna(v):
                return False
            if letters:
                return str(v).strip().upper() not in legal
            try:
                return int(float(v)) not in legal
            except (ValueError, TypeError):
                return True
        tier1_flags[col] = augmented[col].map(check)
    tier1_count = tier1_flags.sum(axis=1)

    cats = pd.DataFrame({c: clean_cat(augmented[c], set(v)) for c, v in CATEGORICAL_LEGAL.items()})
    x = pd.get_dummies(cats, prefix=[c.replace(" ", "_") for c in cats])
    t = num(augmented["Time"])
    hour = (t // 100).where((t >= 0) & (t <= 2359) & (t % 100 < 60))
    x["hour"] = hour.fillna(hour.median())
    x["hour_missing"] = hour.isna().astype(int)
    x["n_vehicles"] = num(augmented["No of Vehicles"]).fillna(1)
    x_scaled = StandardScaler().fit_transform(x.values.astype(float))

    s_iso = -IsolationForest(n_estimators=300, random_state=seed, n_jobs=-1).fit(x_scaled).score_samples(x_scaled)
    lof = LocalOutlierFactor(n_neighbors=35, n_jobs=-1)
    lof.fit(x_scaled)
    s_lof = -lof.negative_outlier_factor_
    ae = MLPRegressor(hidden_layer_sizes=(64, 16, 64), max_iter=300, random_state=seed,
                       early_stopping=True, n_iter_no_change=5).fit(x_scaled, x_scaled)
    s_ae = ((x_scaled - ae.predict(x_scaled)) ** 2).mean(axis=1)
    s_ecod = ECOD().fit(x_scaled).decision_scores_

    def pct(s):
        return pd.Series(s).rank(pct=True).values * 100

    p3 = np.column_stack([pct(s_iso), pct(s_lof), pct(s_ae), pct(s_ecod)]).mean(axis=1) / 100
    p1 = np.clip(tier1_count, 0, 3) / 3
    score = 100 * (1 - 0.2 * (p1 + p3.astype(float)))

    results = pd.DataFrame({"Acc_ID": augmented["Acc_ID"], "score": score, "tier1_count": tier1_count})
    results["error_type"] = "clean"
    results.loc[is_synthetic.values, "error_type"] = labels

    print(f"{'Error type':22s} {'Rule catch':>11s} {'Mean score drop':>17s}")
    for error_type in ERROR_TYPES:
        subset = results[results["error_type"] == error_type]
        parent_ids = [parent_of[a] for a in subset["Acc_ID"]]
        parent_scores = results.set_index("Acc_ID").loc[parent_ids, "score"].values
        drop = (parent_scores - subset["score"].values).mean()
        catch_rate = (subset["tier1_count"] > 0).mean() * 100
        print(f"{error_type:22s} {catch_rate:10.0f}% {drop:16.1f}")

    synthetic_scores = results[results["error_type"] != "clean"]["score"].values
    parent_scores_all = results.set_index("Acc_ID").loc[
        [parent_of[a] for a in results[results["error_type"] != "clean"]["Acc_ID"]], "score"
    ].values
    auc = roc_auc_score(
        np.r_[np.ones(len(synthetic_scores)), np.zeros(len(parent_scores_all))],
        np.r_[-synthetic_scores, -parent_scores_all],
    )
    print(f"\nComposite-score AUC (corrupted vs. clean parent): {auc:.3f}")
    return results, auc


if __name__ == "__main__":
    run()
