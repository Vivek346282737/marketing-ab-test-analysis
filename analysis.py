"""Marketing A/B test: did showing ads (treatment) convert better than a public service announcement (control)?

Run:  python analysis.py
"""
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "marketing_AB.csv"
OUT = ROOT / "outputs"
ALPHA, POWER = 0.05, 0.80
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

QUERIES = {
    "conversion_by_group": """
        SELECT test_group, COUNT(*) AS users, SUM(converted) AS conversions,
               ROUND(100.0 * AVG(converted), 3) AS conversion_rate_pct, ROUND(AVG(total_ads), 1) AS avg_ads_seen
        FROM ab GROUP BY test_group""",
    "conversion_by_day": """
        SELECT most_ads_day, COUNT(*) AS users, ROUND(100.0 * AVG(converted), 3) AS conversion_rate_pct,
               RANK() OVER (ORDER BY AVG(converted) DESC) AS day_rank
        FROM ab WHERE test_group = 'ad' GROUP BY most_ads_day ORDER BY day_rank""",
    "conversion_by_ad_exposure": """
        WITH bucketed AS (
            SELECT *, CASE WHEN total_ads <= 10 THEN '1. 1-10' WHEN total_ads <= 50 THEN '2. 11-50'
                           WHEN total_ads <= 100 THEN '3. 51-100' ELSE '4. 100+' END AS ads_bucket
            FROM ab WHERE test_group = 'ad')
        SELECT ads_bucket, COUNT(*) AS users, ROUND(100.0 * AVG(converted), 3) AS conversion_rate_pct,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_of_users_pct
        FROM bucketed GROUP BY ads_bucket ORDER BY ads_bucket""",
}


def load():
    df = pd.read_csv(DATA).drop(columns=["Unnamed: 0"])
    df.columns = [c.replace(" ", "_") for c in df.columns]
    df["converted"] = df["converted"].astype(int)
    return df


def ab_test(df):
    ctrl, treat = df[df.test_group == "psa"].converted, df[df.test_group == "ad"].converted
    n_c, n_t, p_c, p_t = len(ctrl), len(treat), ctrl.mean(), treat.mean()
    pooled = (ctrl.sum() + treat.sum()) / (n_c + n_t)
    z = (p_t - p_c) / np.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
    p_value = 2 * stats.norm.sf(abs(z))
    se_diff = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    ci = (p_t - p_c) + np.array([-1, 1]) * stats.norm.ppf(1 - ALPHA / 2) * se_diff
    chi2, chi_p, _, _ = stats.chi2_contingency(pd.crosstab(df.test_group, df.converted))
    # sample size per group needed to detect the observed lift with 80% power (equal groups)
    z_a, z_b = stats.norm.ppf(1 - ALPHA / 2), stats.norm.ppf(POWER)
    needed = (z_a + z_b) ** 2 * (p_c * (1 - p_c) + p_t * (1 - p_t)) / (p_t - p_c) ** 2
    achieved_power = stats.norm.cdf(abs(p_t - p_c) / se_diff - z_a)
    return dict(n_c=n_c, n_t=n_t, p_c=p_c, p_t=p_t, z=z, p_value=p_value, ci=ci, chi2=chi2, chi_p=chi_p,
                needed=needed, power=achieved_power)


def charts(df, r):
    sns.set_theme(style="whitegrid")
    rates = np.array([r["p_c"], r["p_t"]]) * 100
    errs = 1.96 * np.sqrt(rates / 100 * (1 - rates / 100) / np.array([r["n_c"], r["n_t"]])) * 100
    plt.figure(figsize=(6, 4.5))
    plt.bar(["Control (PSA)", "Treatment (Ad)"], rates, yerr=errs, capsize=8, color=["#9CA3AF", "#1F4E79"])
    plt.ylabel("Conversion rate (%)")
    plt.title("Conversion rate with 95% confidence intervals")
    plt.tight_layout()
    plt.savefig(OUT / "conversion_by_group.png", dpi=150)
    plt.close()

    ads = df[df.test_group == "ad"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    (ads.groupby("most_ads_day").converted.mean().reindex(DAYS) * 100).plot(kind="bar", ax=axes[0], color="#1F4E79")
    axes[0].set(title="Ad group: conversion rate by day", xlabel="", ylabel="Conversion rate (%)")
    (ads.groupby("most_ads_hour").converted.mean() * 100).plot(ax=axes[1], marker="o", color="#1F4E79")
    axes[1].set(title="Ad group: conversion rate by hour", xlabel="Hour of day", ylabel="Conversion rate (%)")
    plt.tight_layout()
    plt.savefig(OUT / "conversion_by_day_hour.png", dpi=150)
    plt.close()


def main():
    OUT.mkdir(exist_ok=True)
    df = load()
    r = ab_test(df)
    lift = (r["p_t"] - r["p_c"]) / r["p_c"] * 100
    lines = [
        "MARKETING A/B TEST - SUMMARY", "=" * 60,
        f"Users: {len(df):,}   duplicates: {df.user_id.duplicated().sum()}   missing values: {int(df.isna().sum().sum())}",
        f"Control (PSA)  : {r['n_c']:>8,} users   conversion {100 * r['p_c']:.3f}%",
        f"Treatment (Ad) : {r['n_t']:>8,} users   conversion {100 * r['p_t']:.3f}%",
        f"Traffic split  : {100 * r['n_t'] / len(df):.1f}% ad / {100 * r['n_c'] / len(df):.1f}% psa (unequal by design)",
        "",
        f"Absolute lift  : {100 * (r['p_t'] - r['p_c']):.3f} percentage points",
        f"Relative lift  : {lift:.1f}%",
        f"95% CI (diff)  : {100 * r['ci'][0]:.3f} to {100 * r['ci'][1]:.3f} percentage points",
        f"Two-proportion z-test : z = {r['z']:.2f}, p = {r['p_value']:.3g}",
        f"Chi-square test       : chi2 = {r['chi2']:.1f}, p = {r['chi_p']:.3g}",
        f"Statistical power     : {100 * r['power']:.1f}%",
        f"Sample needed per group for 80% power at this lift: {r['needed']:,.0f}",
        f"Decision at alpha = {ALPHA}: {'REJECT' if r['p_value'] < ALPHA else 'FAIL TO REJECT'} the null hypothesis",
        "",
    ]
    with sqlite3.connect(":memory:") as con:
        df.to_sql("ab", con, index=False)
        for name, query in QUERIES.items():
            result = pd.read_sql_query(query, con)
            result.to_csv(OUT / f"{name}.csv", index=False)
            lines += [f"SQL: {name}", result.to_string(index=False), ""]
    charts(df, r)
    text = "\n".join(lines)
    (OUT / "summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
