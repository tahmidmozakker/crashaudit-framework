import sys

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, precision_score, recall_score

PATH = "2006_to_2015.xlsx"
R1_PATH = "room1_audit_matrix.csv"
R2_PATH = "room2_scores.csv"
R3_PATH = "room3_scores.csv"
KEY_PATH = "adjudication_key.xlsx"
SHEET_PATH = "adjudication_sheet.xlsx"
N_PER_STRATUM = 100
SEED = 42

SEVERITY_MAP = {"F": "Fatal", "G": "Grievous injury", "S": "Simple injury", "M": "Motor collision"}
COLLISION_MAP = {
    1: "Head on", 2: "Rear end", 3: "Right angle", 4: "Side swipe", 5: "Overturned",
    6: "Hit object on road", 7: "Hit object off road", 8: "Hit parked vehicle",
    9: "Hit pedestrian", 10: "Hit animal", 11: "Other",
}
WEATHER_MAP = {1: "Good", 2: "Rain", 3: "Storm", 4: "Fog"}
LIGHT_MAP = {1: "Daylight", 2: "Dawn/dusk", 3: "Night-lit", 4: "Night-unlit"}
LOCATION_MAP = {1: "Urban", 2: "Rural"}


def decode(value, mapping, letters=False):
    if pd.isna(value):
        return ""
    try:
        key = str(value).strip().upper() if letters else int(float(value))
    except (ValueError, TypeError):
        return f"INVALID({value})"
    return mapping.get(key, f"INVALID({value})")


def generate(path=PATH, r1_path=R1_PATH, r2_path=R2_PATH, r3_path=R3_PATH,
             key_out=KEY_PATH, sheet_out=SHEET_PATH, n_per_stratum=N_PER_STRATUM, seed=SEED):
    rng = np.random.default_rng(seed)
    r1 = pd.read_csv(r1_path, dtype={"Acc_ID": str})
    r2 = pd.read_csv(r2_path, dtype={"Acc_ID": str})
    r3 = pd.read_csv(r3_path, dtype={"Acc_ID": str})
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()
    fac = pd.read_excel(path, sheet_name="Factors")
    fac["Acc_ID"] = fac["Acc_ID"].astype(str).str.strip()
    narratives = fac.dropna(subset=["Acc_ID"]).groupby("Acc_ID")["Acc Description"].first()

    tier1 = r1["Tier1_flags"] > 0
    anomaly_only = (r2["consensus"] >= 2) & ~tier1
    clean = (r3["score_equal"] >= 90) & (r1["Room1_total_flags"] == 0) & (r2["consensus"] == 0)

    def draw(mask, n):
        return rng.choice(np.where(mask.values)[0], size=n, replace=False)

    idx = np.r_[draw(tier1, n_per_stratum), draw(anomaly_only, n_per_stratum), draw(clean, n_per_stratum)]
    stratum = ["rule_flagged"] * n_per_stratum + ["anomaly_only"] * n_per_stratum + ["clean_control"] * n_per_stratum

    subset = general.iloc[idx].copy()
    sheet = pd.DataFrame({
        "Case no": range(1, len(idx) + 1),
        "Severity": subset["Accident Severity"].map(lambda v: decode(v, SEVERITY_MAP, letters=True)),
        "Date (D/M/Y)": subset["Date"].astype(str) + "/" + subset["Month"].astype(str) + "/" + subset["Year"].astype(str),
        "Day of week (1=Mon)": subset["Day"].values,
        "Time": subset["Time"].values,
        "Vehicles": subset["No of Vehicles"].values,
        "Driver cas.": subset["No of Driver Casualties"].values,
        "Passenger cas.": subset["No of Passenger Casualties"].values,
        "Pedestrian cas.": subset["No of Pedestrian Casualties"].values,
        "Collision type": subset["Collision Type"].map(lambda v: decode(v, COLLISION_MAP)),
        "Weather": subset["Weather"].map(lambda v: decode(v, WEATHER_MAP)),
        "Light": subset["Light"].map(lambda v: decode(v, LIGHT_MAP)),
        "Area": subset["Location Type"].map(lambda v: decode(v, LOCATION_MAP)),
        "Narrative": subset["Acc_ID"].map(narratives).fillna(""),
        "Judgment (Yes/No/Cannot judge)": "",
    })
    shuffle = rng.permutation(len(idx))
    sheet = sheet.iloc[shuffle].reset_index(drop=True)
    sheet["Case no"] = range(1, len(idx) + 1)

    key = pd.DataFrame({
        "Case no": range(1, len(idx) + 1),
        "Acc_ID": subset["Acc_ID"].values[shuffle],
        "stratum": np.array(stratum)[shuffle],
    })

    sheet.to_excel(sheet_out, index=False)
    key.to_excel(key_out, index=False)
    return sheet, key


def score(rater_paths, key_path=KEY_PATH):
    key = pd.read_excel(key_path)

    def load_rater(p):
        df = pd.read_excel(p)
        judgment_col = [c for c in df.columns if "judgment" in c.lower() or "notes" in c.lower()]
        raw = df[judgment_col[0]].astype(str).str.strip().str.lower()
        mapped = raw.map({"yes": "Yes", "no": "No", "cannot judge": "Cannot judge"})
        return pd.DataFrame({"Case no": df["Case no"], "judgment": mapped})

    raters = [load_rater(p) for p in rater_paths]
    merged = key.copy()
    for i, r in enumerate(raters, start=1):
        merged = merged.merge(r.rename(columns={"judgment": f"r{i}"}), on="Case no")

    if len(raters) == 2:
        kappa = cohen_kappa_score(merged["r1"], merged["r2"])
        print(f"Cohen's kappa (3-category): {kappa:.3f}")
        binary = merged[merged["r1"].isin(["Yes", "No"]) & merged["r2"].isin(["Yes", "No"])]
        kappa_bin = cohen_kappa_score(binary["r1"], binary["r2"])
        print(f"Cohen's kappa (binary): {kappa_bin:.3f}")

        merged["both_problem"] = (merged["r1"] == "No") & (merged["r2"] == "No")
        for stratum_name in ["rule_flagged", "anomaly_only", "clean_control"]:
            rate = merged.loc[merged["stratum"] == stratum_name, "both_problem"].mean() * 100
            print(f"{stratum_name:16s}: {rate:.1f}% judged problematic by both raters")

        for layer, other in [("rule_flagged", "clean_control"), ("anomaly_only", "clean_control")]:
            sub = merged[merged["stratum"].isin([layer, other])].copy()
            sub = sub[sub["r1"].isin(["Yes", "No"]) & sub["r2"].isin(["Yes", "No"])]
            y_true = ((sub["r1"] == "No") & (sub["r2"] == "No")).astype(int)
            y_pred = (sub["stratum"] == layer).astype(int)
            print(f"{layer}: precision={precision_score(y_true, y_pred, zero_division=0)*100:.1f}%  "
                  f"recall={recall_score(y_true, y_pred, zero_division=0)*100:.1f}%  "
                  f"accuracy={accuracy_score(y_true, y_pred)*100:.1f}%")

    return merged


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "generate":
        generate()
    elif sys.argv[1] == "score":
        score(sys.argv[2:])
