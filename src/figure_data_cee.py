#!/usr/bin/env python3
"""Figure data for the Communications Earth & Environment build (RewriteCEE).

Gathers, without recomputing anything, the numbers the three main figures draw:
  systems   out-of-region within-region r, its interval, the replicate ceiling and the
            random cross-validation R2 for well-drained mineral soils (carbon, plus pH and
            clay of the same profiles as controls) and the four carbon-dense systems
  gradient  per stratum along the wetness order (well-drained, hydromorphic, fluvic WoSIS
            profiles, then mangrove, salt marsh, seagrass, permafrost): the variance
            partition, the held-out R2 of the regional mean and the within-region r, for
            carbon and, in the WoSIS strata, pH
Inputs are the result JSONs of biome_transfer.py, wetness_gradient.py, variance_partition.py
and manuscript_assets.py. Output: data/processed/figure_data_cee.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data/processed"


def load(name):
    return json.loads((PROC / name).read_text())


def wosis_row(target, key, label):
    d = load(f"biome_wosis_classed_d30_well_drained_{target}_results.json")
    s = d["summary"]
    return dict(key=key, label=label, cls="mineral" if target == "soc" else "control",
                n=s["n_cores"], n_regions=s["n_regions"], random_r2=s["t1_random_r2"],
                median_r=s["loro_median_pearson"], ci=s["loro_median_pearson_ci"],
                ceiling=s["noise_ceiling"]["median_r_max"],
                regions=[dict(r=x["pearson"], n=x["n"]) for x in d["per_region"]
                         if x["pearson"] == x["pearson"]])


def main():
    fd = load("figure_data.json")
    dense = {b["tag"].split("_d")[0]: b for b in fd["biomes"]}
    labels = dict(mangrove="Mangrove", marsh="Salt marsh", seagrass="Seagrass", permafrost="Permafrost")
    systems = [wosis_row("soc", "mineral", "Mineral, well-drained")]
    for k, lab in labels.items():
        b = dense[k]
        systems.append(dict(key=k, label=lab, cls="dense", n=b["n"], n_regions=b["n_regions"],
                            random_r2=b["random_r2"], median_r=b["median_r"], ci=b["ci"],
                            ceiling=b["ceiling"], regions=b["regions"]))
    controls = [wosis_row("ph", "ph", "pH"), wosis_row("clay", "clay", "Clay")]

    vp = {r["biome"]: r for f in ("variance_partition.json", "variance_partition_wetness.json",
                                  "variance_partition_fluvic_ph.json") for r in load(f)["rows"]}
    wg = {(r["stratum"], r["target"]): r for r in load("wetness_gradient.json")["strata"]
          if r["size_matched_to"] != r["size_matched_to"] or r["size_matched_to"] is None}
    order = [("well_drained", "Well-drained", "wosis"), ("hydromorphic", "Hydromorphic", "wosis"),
             ("fluvic", "Fluvic", "wosis"), ("mangrove", "Mangrove", "dense"),
             ("marsh", "Salt marsh", "dense"), ("seagrass", "Seagrass", "dense"),
             ("permafrost", "Permafrost", "dense")]
    gradient = []
    for key, lab, src in order:
        v = vp[key]
        row = dict(key=key, label=lab, src=src, between_regions=v["between_regions"],
                   between_sites_within=v["between_sites_within"], replicate=v["replicate"],
                   level_r2=v["r2_between_regions"], n_regions=v["n_regions"])
        if src == "wosis":
            c, p = wg[(key, "soc")], wg[(key, "ph")]
            row.update(pattern_r=c["loro_median_r"], pattern_ci=c["loro_median_r_ci"],
                       ph_level_r2=vp[f"{key}_ph"]["r2_between_regions"],
                       ph_pattern_r=p["loro_median_r"], ph_pattern_ci=p["loro_median_r_ci"])
        else:
            b = dense[key]
            row.update(pattern_r=b["median_r"], pattern_ci=b["ci"])
        gradient.append(row)

    out = dict(systems=systems, controls=controls, gradient=gradient)
    (PROC / "figure_data_cee.json").write_text(json.dumps(out, indent=1))
    print("figure_data_cee ->", PROC / "figure_data_cee.json")


if __name__ == "__main__":
    main()
