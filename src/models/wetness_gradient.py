#!/usr/bin/env python3
"""Does transferability fall along a drainage gradient inside one terrestrial database?

The cross-biome result contrasts mineral upland soils with carbon-dense wetland soils, but
those come from different databases. This test stays inside WoSIS and splits classified
profiles by field drainage class (terrestrial_test.wetness_stratum: well-drained,
fluvic, hydromorphic, organic), so the split never conditions on measured carbon. Each
stratum runs the unchanged biome_transfer protocol on 0-30 cm SOC concentration, and three
controls guard the reading:
  pH          the same profiles and protocol on pH, so a carbon-specific failure in wet
              soils is separated from "nothing transfers in wet soils"
  size-match  well-drained profiles subsampled to each wet stratum's size (several draws),
              so a lower wet-soil correlation is not just fewer or smaller regions
  ceiling     the replicate-profile noise ceiling per stratum (from biome_transfer)

Requires data/processed/biome_wosis_classed_d30_training.parquet from
  python3 src/models/biome_transfer.py wosis_classed --target-cm 30
Output: data/processed/wetness_gradient.json + console table.
"""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data/processed"
BT = ROOT / "src/models/biome_transfer.py"
STRATA = ["well_drained", "fluvic", "hydromorphic", "organic"]
N_DRAWS = 10
WORKERS = 3


def variants(sizes):
    v = [(s, "soc", 0, 0) for s in STRATA] + [(s, "ph", 0, 0) for s in STRATA if s != "organic"]
    for wet in ("hydromorphic", "fluvic"):
        v += [("well_drained", "soc", sizes[wet], k) for k in range(N_DRAWS)]
    return v


def tag(stratum, target, n, seed):
    return f"_{stratum}_{target}" + (f"_n{n}_s{seed}" if n else "")


def run(v):
    stratum, target, n, seed = v
    t = tag(*v)
    out = PROC / f"biome_wosis_classed_d30{t}_results.json"
    if not out.exists():
        cmd = [sys.executable, str(BT), "wosis_classed", "--target-cm", "30", "--tag", t,
               "--stratum", stratum, "--target", target]
        if n:
            cmd += ["--subsample", str(n), "--seed", str(seed)]
        with open(PROC / f"_wetness{t}.log", "w") as log:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        if rc != 0 or not out.exists():
            return v, None
    return v, json.loads(out.read_text())["summary"]


def main():
    base = pd.read_parquet(PROC / "biome_wosis_classed_d30_training.parquet", columns=["stratum"])
    sizes = base.stratum.value_counts().to_dict()
    with ThreadPoolExecutor(WORKERS) as ex:
        res = list(ex.map(run, variants(sizes)))
    rows = []
    for (stratum, target, n, seed), s in res:
        if s is None:
            print(f"FAILED {stratum} {target} n={n} seed={seed}", flush=True)
            continue
        nc = s["noise_ceiling"]
        frac = (round(s["loro_median_pearson"] / nc["median_r_max"], 3)
                if nc.get("median_r_max") else None)
        rows.append(dict(stratum=stratum, target=target, size_matched_to=n or None, seed=seed if n else None,
                         n=s["n_cores"], n_regions=s["n_regions"], n_continents=s["n_continents"],
                         median_target=s["median_soc_Mgha"], random_cv_r2=s["t1_random_r2"],
                         grouped_cv_r2=s["t1_grouped_r2"], loro_median_r=s["loro_median_pearson"],
                         loro_median_r_ci=s["loro_median_pearson_ci"],
                         aoa_inside=s["median_aoa_inside"], r_max=nc.get("median_r_max"),
                         n_regions_ceiling=nc.get("n_regions_with_ceiling"), frac_of_ceiling=frac))
    R = pd.DataFrame(rows)
    main_rows = R[R.size_matched_to.isna()]
    matched = (R[R.size_matched_to.notna()].groupby("size_matched_to")
               .agg(draws=("loro_median_r", "size"), median_r=("loro_median_r", "median"),
                    min_r=("loro_median_r", "min"), max_r=("loro_median_r", "max"),
                    median_regions=("n_regions", "median")).reset_index())
    (PROC / "wetness_gradient.json").write_text(json.dumps(
        dict(strata=main_rows.to_dict("records"), size_matched=matched.to_dict("records"),
             sizes=sizes), indent=1, default=str))
    pd.set_option("display.width", 220)
    print(main_rows.drop(columns=["size_matched_to", "seed"]).to_string(index=False))
    print("\nwell-drained profiles subsampled to the wet-stratum size:")
    print(matched.to_string(index=False))
    print("wrote data/processed/wetness_gradient.json")


if __name__ == "__main__":
    main()
