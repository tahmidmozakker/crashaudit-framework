import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from pyod.models.ecod import ECOD

PATH = "2006_to_2015.xlsx"
OUT = "room2_scores.csv"

CATEGORICAL_LEGAL = {
    "Accident Severity": {"F", "G", "S", "M"},
    "Day": set(range(1, 8)),
    "Month": set(range(1, 13)),
    "Junction Type": set(range(1, 8)),
    "Traffic Control": set(range(1, 9)),
    "Collision Type": set(range(1, 12)),
    "Movement": {1, 2},
    "Divider": {1, 2},
    "Weather": set(range(1, 5)),
    "Light": set(range(1, 5)),
    "Road Geometry": set(range(1, 6)),
    "Surface Condition": set(range(1, 6)),
    "Surface Type": {1, 2, 3},
    "Surface Quality": {1, 2, 3},
    "Road Class": set(range(1, 6)),
    "Road Feature": set(range(1, 6)),
    "Location Type": {1, 2},
}


def clean_cat(series, legal, letters=False):
    def one(v):
        if pd.isna(v):
            return "UNK"
        if letters:
            s = str(v).strip().upper()
            return s if s in legal else "UNK"
        try:
            i = int(float(v))
            return str(i) if i in legal else "UNK"
        except (ValueError, TypeError):
            return "UNK"
    return series.map(one)


def build_features(general, veh, pas, ped):
    def num(s):
        return pd.to_numeric(s, errors="coerce")

    cats = pd.DataFrame()
    for col, legal in CATEGORICAL_LEGAL.items():
        cats[col] = clean_cat(general[col], legal, letters=(col == "Accident Severity"))
    x_cat = pd.get_dummies(cats, prefix=[c.replace(" ", "_") for c in cats.columns])

    dist = num(general["District"])
    freq = dist.map(dist.value_counts(normalize=True)).fillna(0)

    t = num(general["Time"])
    hour = (t // 100).where((t >= 0) & (t <= 2359) & (t % 100 < 60))
    hour_missing = hour.isna().astype(int)
    hour = hour.fillna(hour.median())

    veh_rows = general["Acc_ID"].map(veh.groupby("Acc_ID").size()).fillna(0)
    pas_rows = general["Acc_ID"].map(pas.groupby("Acc_ID").size()).fillna(0)
    ped_rows = general["Acc_ID"].map(ped.groupby("Acc_ID").size()).fillna(0)
    d_cas = num(general["No of Driver Casualties"]).fillna(0)
    p_cas = num(general["No of Passenger Casualties"]).fillna(0)
    pd_cas = num(general["No of Pedestrian Casualties"]).fillna(0)
    n_veh = num(general["No of Vehicles"]).fillna(1)
    age_mean = general["Acc_ID"].map(num(veh["Age"]).groupby(veh["Acc_ID"]).mean())
    age_missing = age_mean.isna().astype(int)
    age_mean = age_mean.fillna(age_mean.median())

    x_num = pd.DataFrame(
        {
            "hour": hour,
            "hour_missing": hour_missing,
            "district_freq": freq,
            "n_vehicles": n_veh,
            "driver_cas": d_cas,
            "passenger_cas": p_cas,
            "pedestrian_cas": pd_cas,
            "total_cas": d_cas + p_cas + pd_cas,
            "veh_rows": veh_rows,
            "pass_rows": pas_rows,
            "ped_rows": ped_rows,
            "driver_age_mean": age_mean,
            "driver_age_missing": age_missing,
        }
    )
    return pd.concat([x_num, x_cat.astype(int)], axis=1)


def run(path=PATH, out=OUT, threshold_pct=95, random_state=42):
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()
    veh = pd.read_excel(path, sheet_name="Veh")
    pas = pd.read_excel(path, sheet_name="Pass")
    ped = pd.read_excel(path, sheet_name="Ped")
    for df in (veh, pas, ped):
        df["Acc_ID"] = df["Acc_ID"].astype(str).str.strip()

    x = build_features(general, veh, pas, ped)
    x_scaled = StandardScaler().fit_transform(x.values.astype(float))

    iso = IsolationForest(n_estimators=300, random_state=random_state, n_jobs=-1).fit(x_scaled)
    s_iso = -iso.score_samples(x_scaled)

    lof = LocalOutlierFactor(n_neighbors=35, n_jobs=-1)
    lof.fit(x_scaled)
    s_lof = -lof.negative_outlier_factor_

    ae = MLPRegressor(
        hidden_layer_sizes=(64, 16, 64),
        max_iter=300,
        random_state=random_state,
        early_stopping=True,
        n_iter_no_change=5,
    ).fit(x_scaled, x_scaled)
    s_ae = ((x_scaled - ae.predict(x_scaled)) ** 2).mean(axis=1)

    s_ecod = ECOD().fit(x_scaled).decision_scores_

    def pct(s):
        return pd.Series(s).rank(pct=True).values * 100

    scores = pd.DataFrame(
        {
            "Acc_ID": general["Acc_ID"],
            "iso_pct": pct(s_iso),
            "lof_pct": pct(s_lof),
            "ae_pct": pct(s_ae),
            "ecod_pct": pct(s_ecod),
        }
    )
    for m in ("iso", "lof", "ae", "ecod"):
        scores[f"{m}_flag"] = scores[f"{m}_pct"] >= threshold_pct
    scores["consensus"] = scores[[f"{m}_flag" for m in ("iso", "lof", "ae", "ecod")]].sum(axis=1)

    scores.to_csv(out, index=False)
    return scores


if __name__ == "__main__":
    result = run()
    print(result["consensus"].value_counts().sort_index())
