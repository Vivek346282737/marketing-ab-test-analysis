"""Build the interactive HTML dashboard (docs/index.html, served by GitHub Pages).

Run:  python build_dashboard.py     (after analysis.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from analysis import DAYS, ab_test, load

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "index.html"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Marketing A/B Test Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root { --navy: #1F4E79; --grey: #8A94A3; --ink: #1F2937; --muted: #5B6573; --line: #E1E5EA; --bg: #F3F4F6; --card: #FFFFFF; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 "Segoe UI", system-ui, sans-serif; }
  header { background: var(--navy); color: #fff; padding: 18px 24px; }
  header h1 { margin: 0; font-size: 22px; }
  header p { margin: 4px 0 0; opacity: .9; }
  main { max-width: 1200px; margin: 0 auto; padding: 16px; display: grid; gap: 16px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
  .kpi b { display: block; font-size: 26px; color: var(--navy); font-variant-numeric: tabular-nums; }
  .kpi span { color: var(--muted); font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
  h2 { margin: 0 0 2px; font-size: 16px; }
  .note { margin: 0 0 8px; color: var(--muted); font-size: 13px; }
  .chart { position: relative; height: 280px; }
  .verdict { border-left: 5px solid var(--navy); }
  footer { color: var(--muted); font-size: 13px; padding: 0 16px 24px; max-width: 1200px; margin: 0 auto; }
  a { color: var(--navy); }
</style>
</head>
<body>
<header>
  <h1>Marketing A/B Test Dashboard</h1>
  <p>Did showing product ads convert better than a public service announcement? __USERS__ users.</p>
</header>
<main>
  <section class="kpis">
    <div class="card kpi"><b>__P_C__%</b><span>Control (PSA) conversion</span></div>
    <div class="card kpi"><b>__P_T__%</b><span>Treatment (Ad) conversion</span></div>
    <div class="card kpi"><b>+__LIFT__%</b><span>Relative lift</span></div>
    <div class="card kpi"><b>__CI__</b><span>95% CI of difference (points)</span></div>
    <div class="card kpi"><b>__P__</b><span>p-value (z = __Z__)</span></div>
  </section>
  <section class="card verdict">
    <h2>Result: the ads increased conversion</h2>
    <p class="note" style="margin:0">Two-proportion z-test and chi-square test both reject the null hypothesis at alpha = 0.05.
    The test needed about __NEEDED__ users per group for 80% power; the smaller group had __N_C__.</p>
  </section>
  <section class="grid">
    <div class="card"><h2>Conversion rate by group</h2><p class="note">Error bars show 95% confidence intervals.</p><div class="chart"><canvas id="group"></canvas></div></div>
    <div class="card"><h2>Conversion rate by ad exposure</h2><p class="note">Ad group. Correlation only: heavy browsers see more ads.</p><div class="chart"><canvas id="ads"></canvas></div></div>
    <div class="card"><h2>Conversion rate by day of week</h2><p class="note">Ad group. Monday and Tuesday convert best.</p><div class="chart"><canvas id="day"></canvas></div></div>
    <div class="card"><h2>Conversion rate by hour of day</h2><p class="note">Ad group, hour in which the user saw the most ads.</p><div class="chart"><canvas id="hour"></canvas></div></div>
  </section>
</main>
<footer>Data: Marketing A/B Testing dataset (Kaggle). Analysis and code:
  <a href="https://github.com/Vivek346282737/marketing-ab-test-analysis">github.com/Vivek346282737/marketing-ab-test-analysis</a></footer>
<script>
const D = __DATA__;
const NAVY = "#1F4E79", GREY = "#8A94A3";
const pct = { callback: v => v + "%" };
const base = (title) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.parsed.y.toFixed(2) + "% conversion" } } },
  scales: { y: { beginAtZero: true, ticks: pct, title: { display: true, text: "Conversion rate" } },
            x: { title: { display: !!title, text: title }, grid: { display: false } } }
});
const errorBars = { id: "errorBars", afterDatasetsDraw(chart) {
  const { ctx, scales: { y } } = chart;
  chart.getDatasetMeta(0).data.forEach((bar, i) => {
    const [lo, hi] = D.group.ci[i];
    ctx.save(); ctx.strokeStyle = "#111827"; ctx.lineWidth = 1.5; ctx.beginPath();
    ctx.moveTo(bar.x, y.getPixelForValue(lo)); ctx.lineTo(bar.x, y.getPixelForValue(hi));
    ctx.moveTo(bar.x - 8, y.getPixelForValue(lo)); ctx.lineTo(bar.x + 8, y.getPixelForValue(lo));
    ctx.moveTo(bar.x - 8, y.getPixelForValue(hi)); ctx.lineTo(bar.x + 8, y.getPixelForValue(hi));
    ctx.stroke(); ctx.restore();
  });
}};
new Chart("group", { type: "bar", plugins: [errorBars],
  data: { labels: D.group.labels, datasets: [{ data: D.group.rates, backgroundColor: [GREY, NAVY], maxBarThickness: 110 }] }, options: base("") });
new Chart("ads", { type: "bar",
  data: { labels: D.ads.labels, datasets: [{ data: D.ads.rates, backgroundColor: NAVY }] }, options: base("Ads seen per user") });
new Chart("day", { type: "bar",
  data: { labels: D.day.labels, datasets: [{ data: D.day.rates, backgroundColor: NAVY }] }, options: base("") });
new Chart("hour", { type: "line",
  data: { labels: D.hour.labels, datasets: [{ data: D.hour.rates, borderColor: NAVY, backgroundColor: NAVY, pointRadius: 3, tension: 0.25 }] },
  options: base("Hour of day") });
</script>
</body>
</html>
"""


def main():
    df = load()
    r = ab_test(df)
    ads = df[df.test_group == "ad"]
    buckets = pd.cut(ads.total_ads, [0, 10, 50, 100, 10**6], labels=["1-10", "11-50", "51-100", "100+"])
    ci = lambda p, n: [round(100 * (p - 1.96 * np.sqrt(p * (1 - p) / n)), 3), round(100 * (p + 1.96 * np.sqrt(p * (1 - p) / n)), 3)]
    data = {
        "group": {"labels": ["Control (PSA)", "Treatment (Ad)"], "rates": [round(100 * r["p_c"], 4), round(100 * r["p_t"], 4)],
                  "ci": [ci(r["p_c"], r["n_c"]), ci(r["p_t"], r["n_t"])]},
        "ads": {"labels": list(buckets.cat.categories),
                "rates": (ads.groupby(buckets, observed=True).converted.mean() * 100).round(3).tolist()},
        "day": {"labels": [d[:3] for d in DAYS],
                "rates": (ads.groupby("most_ads_day").converted.mean().reindex(DAYS) * 100).round(3).tolist()},
        "hour": {"labels": [f"{h:02d}" for h in range(24)],
                 "rates": (ads.groupby("most_ads_hour").converted.mean().reindex(range(24)) * 100).round(3).tolist()},
    }
    fills = {
        "__USERS__": f"{len(df):,}", "__P_C__": f"{100 * r['p_c']:.2f}", "__P_T__": f"{100 * r['p_t']:.2f}",
        "__LIFT__": f"{(r['p_t'] - r['p_c']) / r['p_c'] * 100:.1f}", "__CI__": f"{100 * r['ci'][0]:.2f} to {100 * r['ci'][1]:.2f}",
        "__P__": "< 0.001" if r["p_value"] < 0.001 else f"{r['p_value']:.3f}", "__Z__": f"{r['z']:.2f}",
        "__NEEDED__": f"{r['needed']:,.0f}", "__N_C__": f"{r['n_c']:,}", "__DATA__": json.dumps(data),
    }
    html = TEMPLATE
    for key, value in fills.items():
        html = html.replace(key, value)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Dashboard written: {OUT}")
    print(json.dumps(data["group"]), data["ads"]["rates"], data["day"]["rates"])


if __name__ == "__main__":
    main()
