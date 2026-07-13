"""
Room 1: Logical consistency engine.

Checks every accident record against the legal code sets defined on
Bengal Form 403Q (Regulation 254(b)), detects identifier collisions and
duplicate records, cross-checks declared vs. actual sub-record counts,
and flags in-record contradictions.

Input : ARI workbook (sheets General, Veh, Pass, Ped, Factors)
Output: room1_audit_matrix.csv
"""

import datetime as dt
import pandas as pd

PATH = "2006_to_2015.xlsx"
OUT = "room1_audit_matrix.csv"


def load_sheets(path):
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    veh = pd.read_excel(path, sheet_name="Veh")
    pas = pd.read_excel(path, sheet_name="Pass")
    ped = pd.read_excel(path, sheet_name="Ped")
    fac = pd.read_excel(path, sheet_name="Factors")
    for df in (general, veh, pas, ped, fac):
        df["Acc_ID"] = df["Acc_ID"].astype(str).str.strip()

    def blank_to_nan(df):
        return df.apply(
            lambda c: c.where(~c.astype(str).str.strip().isin(["", "nan", "None"]), other=pd.NA)
        )

    return (blank_to_nan(d) for d in (general, veh, pas, ped, fac))


LEGAL_CODES = {
    "Accident Severity": {"F", "G", "S", "M"},
    "Day": set(range(1, 8)),
    "Month": set(range(1, 13)),
    "Year": set(range(6, 16)),
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
    "District": set(range(1, 71)),
}


def check_code(series, legal, letters=False):
    def one(v):
        if pd.isna(v):
            return False
        if letters:
            return str(v).strip().upper() not in legal
        try:
            return int(float(v)) not in legal
        except (ValueError, TypeError):
            return True
    return series.map(one)


def bad_time(v):
    if pd.isna(v):
        return False
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return True
    return not (0 <= t <= 2359 and t % 100 < 60)


def weekday_mismatch(row):
    yy, mm, dd, w = row
    if any(pd.isna(x) for x in (yy, mm, dd, w)):
        return False
    try:
        real = dt.date(2000 + int(yy), int(mm), int(dd)).isoweekday()
    except ValueError:
        return True
    return real != int(w)


def run(path=PATH, out=OUT):
    general, veh, pas, ped, fac = load_sheets(path)

    def num(s):
        return pd.to_numeric(s, errors="coerce")

    audit = pd.DataFrame({"Acc_ID": general["Acc_ID"]})

    for col, legal in LEGAL_CODES.items():
        audit[f"R1_{col.replace(' ', '_')}"] = check_code(
            general[col], legal, letters=(col == "Accident Severity")
        )
    audit["R1_Date"] = check_code(general["Date"], set(range(1, 32)))
    audit["R1_Time"] = general["Time"].map(bad_time)

    audit["R2_exact_duplicate"] = general.duplicated(keep=False)
    id_counts = general["Acc_ID"].value_counts()
    shared = general["Acc_ID"].map(id_counts) > 1
    audit["R2_ID_collision"] = shared & ~audit["R2_exact_duplicate"]

    ok_ids = ~shared
    veh_rows = veh.groupby("Acc_ID").size()
    pas_rows = pas.groupby("Acc_ID").size()
    ped_rows = ped.groupby("Acc_ID").size()
    decl_v = num(general["No of Vehicles"])
    decl_p = num(general["No of Passenger Casualties"])
    decl_d = num(general["No of Pedestrian Casualties"])
    actual_v = general["Acc_ID"].map(veh_rows).fillna(0)
    actual_p = general["Acc_ID"].map(pas_rows).fillna(0)
    actual_d = general["Acc_ID"].map(ped_rows).fillna(0)
    audit["R3_vehicle_count_mismatch"] = ok_ids & decl_v.notna() & (decl_v != actual_v)
    audit["R3_passenger_count_mismatch"] = ok_ids & decl_p.notna() & (decl_p != actual_p)
    audit["R3_pedestrian_count_mismatch"] = ok_ids & decl_d.notna() & (decl_d != actual_d)

    y, m, d_, wd = num(general["Year"]), num(general["Month"]), num(general["Date"]), num(general["Day"])
    audit["R4_weekday_mismatch"] = pd.DataFrame({"y": y, "m": m, "d": d_, "w": wd}).apply(
        weekday_mismatch, axis=1
    )

    sev = general["Accident Severity"].astype(str).str.strip().str.upper()
    total_casualties = num(general["No of Driver Casualties"]).fillna(0) + decl_p.fillna(0) + decl_d.fillna(0)
    audit["R4_fatal_but_zero_casualties"] = (sev == "F") & (total_casualties == 0)

    def has_death(df):
        return df[df["Injury"].astype(str).str.strip().str.upper() == "F"].groupby("Acc_ID").size()

    death_ids = set(has_death(veh).index) | set(has_death(pas).index) | set(has_death(ped).index)
    audit["R4_death_recorded_but_not_fatal"] = (
        ok_ids & general["Acc_ID"].isin(death_ids) & (sev != "F") & sev.isin(list("FGSM"))
    )

    dr_age = num(veh["Age"])
    imp_ids = set(veh.loc[dr_age < 10, "Acc_ID"]) | set(veh.loc[dr_age > 100, "Acc_ID"])
    sus_ids = set(veh.loc[(dr_age >= 10) & (dr_age < 18), "Acc_ID"])
    audit["R4_driver_age_impossible"] = general["Acc_ID"].isin(imp_ids)
    audit["R4_driver_age_under18"] = general["Acc_ID"].isin(sus_ids)

    flag_cols = [c for c in audit.columns if c != "Acc_ID"]
    audit["Room1_total_flags"] = audit[flag_cols].sum(axis=1)
    tier1 = [c for c in flag_cols if c.startswith(("R1_", "R2_", "R3_"))] + [
        "R4_weekday_mismatch",
        "R4_driver_age_impossible",
    ]
    tier2 = ["R4_fatal_but_zero_casualties", "R4_death_recorded_but_not_fatal", "R4_driver_age_under18"]
    audit["Tier1_flags"] = audit[tier1].sum(axis=1)
    audit["Tier2_flags"] = audit[tier2].sum(axis=1)

    audit.to_csv(out, index=False)
    return audit


if __name__ == "__main__":
    result = run()
    print(f"Records: {len(result)}")
    print(f"Tier-1 defects: {(result['Tier1_flags'] > 0).sum()}")
    print(f"Any defect: {(result['Room1_total_flags'] > 0).sum()}")
