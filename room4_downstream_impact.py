"""
Room 4: Downstream impact analysis with placebo control.

Compares a raw cohort against a reliability-filtered cohort across four
standard crash-analysis tasks, benchmarking every comparison against a
placebo control (equal-size random record removal) to separate genuine
data-quality effects from sample-size artifacts.

Input : ARI workbook (sheet General); room3_scores.csv
Output: printed summary tables (see functions below for programmatic use)
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

PATH = "2006_to_2015.xlsx"
R3_PATH = "room3_scores.csv"
CLEAN_THRESHOLD = 75

CATEGORICAL_LEGAL = {
    "Junction Type": set(range(1, 8)), "Traffic Control": set(range(1, 9)),
    "Collision Type": set(range(1, 12)), "Movement": {1, 2}, "Divider": {1, 2},
    "Weather": set(range(1, 5)), "Light": set(range(1, 5)), "Road Geometry": set(range(1, 6)),
    "Surface Condition": set(range(1, 6)), "Surface Type": {1, 2, 3}, "Surface Quality": {1, 2, 3},
    "Road Class": set(range(1, 6)), "Road Feature": set(range(1, 6)), "Location Type": {1, 2},
}


def clean_cat(series, legal):
    def one(v):
        if pd.isna(v):
            return "UNK"
        try:
            i = int(float(v))
            return str(i) if i in legal else "UNK"
        except (ValueError, TypeError):
            return "UNK"
    return series.map(one)


def load(path=PATH, r3_path=R3_PATH):
    r3 = pd.read_csv(r3_path, dtype={"Acc_ID": str})
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()
    return general, r3


def build_features(general):
    def num(s):
        return pd.to_numeric(s, errors="coerce")

    cats = pd.DataFrame({c: clean_cat(general[c], l) for c, l in CATEGORICAL_LEGAL.items()})
    x = pd.get_dummies(cats, prefix=[c.replace(" ", "_") for c in cats])
    t = num(general["Time"])
    hour = (t // 100).where((t >= 0) & (t <= 2359) & (t % 100 < 60))
    x["hour"] = hour.fillna(hour.median())
    x["hour_missing"] = hour.isna().astype(int)
    x["n_vehicles"] = num(general["No of Vehicles"]).fillna(1)
    return x


def bootstrap_significance(x, y, mask, n_boot=100, seed=42):
    rng = np.random.default_rng(seed)
    idx_all = np.where(mask)[0]
    coefs = np.empty((n_boot, x.shape[1]))
    x_values = x.values.astype(float)
    for b in range(n_boot):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        scaler = StandardScaler().fit(x_values[idx])
        coefs[b] = LogisticRegression(max_iter=1500).fit(scaler.transform(x_values[idx]), y.values[idx]).coef_[0]
    lo, hi = np.percentile(coefs, [2.5, 97.5], axis=0)
    return (lo > 0) | (hi < 0)


def placebo_significance_test(x, y, valid_mask, score, threshold=CLEAN_THRESHOLD, n_placebo=10, seed=100):
    sig_raw = bootstrap_significance(x, y, valid_mask)
    sig_clean = bootstrap_significance(x, y, valid_mask & (score >= threshold))
    observed = int((sig_raw != sig_clean).sum())

    rng = np.random.default_rng(seed)
    n_keep = (valid_mask & (score >= threshold)).sum()
    placebo = []
    for _ in range(n_placebo):
        keep = np.zeros(len(x), bool)
        keep[rng.choice(np.where(valid_mask)[0], size=n_keep, replace=False)] = True
        sig_placebo = bootstrap_significance(x, y, keep)
        placebo.append(int((sig_raw != sig_placebo).sum()))
    return observed, np.array(placebo)


def district_ranking_test(general, severity, score, threshold=CLEAN_THRESHOLD, n_placebo=200, seed=100):
    dist = pd.to_numeric(general["District"], errors="coerce")
    base = severity.isin(["F", "G", "S", "M"]).values & dist.between(1, 70).values
    dd = pd.DataFrame({"d": dist, "f": (severity == "F").astype(int)})

    def rank_fatal(mask):
        return dd[mask].groupby("d")["f"].sum().rank(ascending=False, method="min")

    rk_raw = rank_fatal(base)
    rk_clean = rank_fatal(base & (score >= threshold))
    common = rk_raw.index.intersection(rk_clean.index)
    exits_observed = len(set(rk_raw.nsmallest(10).index) - set(rk_clean.nsmallest(10).index))
    rho_observed = spearmanr(rk_raw.loc[common], rk_clean.loc[common]).statistic

    rng = np.random.default_rng(seed)
    n_keep = (base & (score >= threshold)).sum()
    exits_placebo, rho_placebo = [], []
    for _ in range(n_placebo):
        keep = np.zeros(len(general), bool)
        keep[rng.choice(np.where(base)[0], size=n_keep, replace=False)] = True
        rk_p = rank_fatal(keep)
        c = rk_raw.index.intersection(rk_p.index)
        exits_placebo.append(len(set(rk_raw.nsmallest(10).index) - set(rk_p.nsmallest(10).index)))
        rho_placebo.append(spearmanr(rk_raw.loc[c], rk_p.loc[c]).statistic)
    return exits_observed, np.array(exits_placebo), rho_observed, np.array(rho_placebo)


def feature_importance_comparison(x, y, valid_mask, score, threshold=CLEAN_THRESHOLD, seed=42):
    rf_raw = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1).fit(
        x.values[valid_mask], y.values[valid_mask]
    )
    clean_mask = valid_mask & (score >= threshold)
    rf_clean = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1).fit(
        x.values[clean_mask], y.values[clean_mask]
    )
    return spearmanr(rf_raw.feature_importances_, rf_clean.feature_importances_).statistic


def temporal_trend(general, score, threshold=CLEAN_THRESHOLD):
    yr = pd.to_numeric(general["Year"], errors="coerce")
    ok = yr.between(6, 15)
    years_all = (2000 + yr[ok]).astype(int)
    raw_counts = years_all.value_counts().sort_index()
    clean_counts = (2000 + yr[ok.values & (score >= threshold)]).astype(int).value_counts().sort_index()
    slope_raw = np.polyfit(raw_counts.index, np.log(raw_counts.values), 1)[0] * 100
    slope_clean = np.polyfit(clean_counts.index, np.log(clean_counts.values), 1)[0] * 100
    return slope_raw, slope_clean


def run(path=PATH, r3_path=R3_PATH):
    general, r3 = load(path, r3_path)
    x = build_features(general)
    severity = general["Accident Severity"].astype(str).str.strip().str.upper()
    y = (severity == "F").astype(int)
    valid = severity.isin(["F", "G", "S", "M"]).values
    score = r3["score_equal"].values

    sig_obs, sig_placebo = placebo_significance_test(x, y, valid, score)
    exits_obs, exits_placebo, rho_obs, rho_placebo = district_ranking_test(general, severity, score)
    fi_rho = feature_importance_comparison(x, y, valid, score)
    trend_raw, trend_clean = temporal_trend(general, score)

    print(f"Predictor significance changes: observed={sig_obs}, placebo mean={sig_placebo.mean():.1f} "
          f"range=[{sig_placebo.min()},{sig_placebo.max()}]")
    print(f"Feature-importance rank correlation (raw vs. clean): rho={fi_rho:.3f}")
    print(f"District top-10 exits: observed={exits_obs}, placebo mean={exits_placebo.mean():.2f} "
          f"p={(exits_placebo >= exits_obs).mean():.4f}")
    print(f"District rank correlation: observed rho={rho_obs:.3f}, placebo mean rho={rho_placebo.mean():.3f} "
          f"p={(rho_placebo <= rho_obs).mean():.4f}")
    print(f"Temporal trend (relative, %/yr): raw={trend_raw:.2f}, clean={trend_clean:.2f}")


if __name__ == "__main__":
    run()
