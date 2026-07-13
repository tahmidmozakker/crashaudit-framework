"""
Shield 3: External comparison.

Compares the database's own yearly recorded deaths and accident counts
against three independent references: the Global Burden of Disease
(GBD) study, WHO Global Status Report anchors, and official police FIR
statistics from the national transport authority (same-source
completeness check).

Input : ARI workbook (sheets General, Veh, Pass, Ped); GBD results CSV;
        WHO estimates (hard-coded constants, see WHO_ESTIMATES below);
        official police series (hard-coded constants, see
        POLICE_SERIES below -- verify against the source portal before use)
Output: printed comparison tables
"""

import pandas as pd

PATH = "2006_to_2015.xlsx"
GBD_PATH = "gbd_results.csv"

# WHO Global Status Report on Road Safety 2023: point estimate,
# lower bound, upper bound (95% uncertainty interval).
WHO_ESTIMATES = {
    2010: (25697, 22134, 29261),
    2016: (24944, 21613, 28275),
    2021: (31578, 27441, 35716),
}

# Official Bangladesh Police (FIR) statistics, Bangladesh Safety Portal
# (bsp.brta.gov.bd/roadSafety). Verify against the live portal before
# use in publication.
POLICE_SERIES = pd.DataFrame({
    "year": [2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014],
    "police_accidents": [3794, 4869, 4427, 3381, 2827, 2667, 2636, 2029, 2027],
    "police_deaths": [3193, 3749, 3765, 2958, 2646, 2546, 2538, 1957, 2067],
})


def internal_series(path=PATH):
    general = pd.read_excel(path, sheet_name="General", header=1)
    general = general.rename(columns={general.columns[0]: "Acc_ID"})
    general["Acc_ID"] = general["Acc_ID"].astype(str).str.strip()
    veh = pd.read_excel(path, sheet_name="Veh")
    pas = pd.read_excel(path, sheet_name="Pass")
    ped = pd.read_excel(path, sheet_name="Ped")
    for df in (veh, pas, ped):
        df["Acc_ID"] = df["Acc_ID"].astype(str).str.strip()

    yr = pd.to_numeric(general["Year"], errors="coerce")
    ok = yr.between(6, 15)
    subset = general[ok].copy()
    subset["year"] = (2000 + yr[ok]).astype(int)

    def deaths(df):
        return df[df["Injury"].astype(str).str.strip().str.upper() == "F"].groupby("Acc_ID").size()

    death_sum = deaths(veh).add(deaths(pas), fill_value=0).add(deaths(ped), fill_value=0)
    subset["deaths"] = subset["Acc_ID"].map(death_sum).fillna(0)

    return subset.groupby("year").agg(
        db_accidents=("Acc_ID", "size"),
        db_deaths=("deaths", "sum"),
    ).reset_index()


def compare_gbd(internal, gbd_path=GBD_PATH):
    gbd = pd.read_csv(gbd_path)
    gbd = gbd[gbd["year"].between(2006, 2015)][["year", "val", "lower", "upper"]]
    gbd.columns = ["year", "gbd_est", "gbd_lo", "gbd_hi"]
    merged = internal.merge(gbd, on="year")
    merged["capture_pct"] = merged["db_deaths"] / merged["gbd_est"] * 100
    return merged


def compare_who(internal, year=2010):
    est, lo, hi = WHO_ESTIMATES[year]
    db_deaths = int(internal.loc[internal["year"] == year, "db_deaths"].iloc[0])
    return {
        "year": year, "db_deaths": db_deaths, "who_estimate": est,
        "who_lower": lo, "who_upper": hi,
        "capture_pct": db_deaths / est * 100,
    }


def compare_police(internal):
    merged = internal.merge(POLICE_SERIES, on="year")
    merged["completeness_pct"] = merged["db_accidents"] / merged["police_accidents"] * 100
    return merged


if __name__ == "__main__":
    series = internal_series()

    gbd_comparison = compare_gbd(series)
    print(gbd_comparison[["year", "db_deaths", "gbd_est", "capture_pct"]].round(1).to_string(index=False))
    total_capture = gbd_comparison["db_deaths"].sum() / gbd_comparison["gbd_est"].sum() * 100
    print(f"Decade capture rate vs. GBD: {total_capture:.1f}%\n")

    who_2010 = compare_who(series, 2010)
    print(f"2010 capture vs. WHO: {who_2010['capture_pct']:.1f}%\n")

    police_comparison = compare_police(series)
    print(police_comparison[["year", "db_accidents", "police_accidents", "completeness_pct"]].round(1).to_string(index=False))
    total_completeness = (
        police_comparison["db_accidents"].sum() / police_comparison["police_accidents"].sum() * 100
    )
    print(f"2006-2014 completeness vs. police FIR: {total_completeness:.1f}%")
