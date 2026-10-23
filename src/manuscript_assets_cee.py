#!/usr/bin/env python3
"""Supplementary tables added for the Communications Earth & Environment build (RewriteCEE).

Reads result JSONs only and writes LaTeX fragments to RewriteCEE/tables/:
  tab_gradient.tex          WoSIS drainage strata: transfer of carbon and pH, ceilings, size-matched draws
  tab_variance_cee.tex      nested variance partition for the WoSIS strata and the carbon-dense systems
  tab_sensitivity_cee.tex   cross-biome sensitivity with the well-drained stratum and its pH and clay
  tab_publishedmap_cee.tex  published map per delta, with the share of cores near its training points
  tab_tier1_soiltype.tex    national-inventory difference under the IPCC soil-type defaults
"""
import json
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data/processed"
OUT = ROOT / "RewriteCEE/tables"


def load(name):
    return json.loads((PROC / name).read_text())


def f2(v):
    return "n/a" if v is None or v != v else f"{v:+.2f}".replace("-", "$-$")


def ci(c):
    return f"[{f2(c[0])}, {f2(c[1])}]"


def foot(ncol, lines):
    return "".join(f"\\multicolumn{{{ncol}}}{{@{{}}p{{0.97\\linewidth}}@{{}}}}{{\\footnotesize {l}}}\\\\\n" for l in lines)


def wrap(cols, head, rows, ncol, notes):
    return (f"\\begin{{adjustbox}}{{max width=\\linewidth}}\\begin{{tabular}}{{{cols}}}\n\\toprule\n{head}\n\\midrule\n"
            + "\n".join(rows) + "\n\\bottomrule\n" + foot(ncol, notes) + "\\end{tabular}\\end{adjustbox}\n")


def summary(tag):
    p = PROC / f"biome_wosis_classed_d30{tag}_results.json"
    return json.loads(p.read_text())["summary"] if p.exists() else None


def tab_gradient():
    wg = load("wetness_gradient.json")
    rows = []
    name = dict(well_drained="Well-drained", hydromorphic="Hydromorphic", fluvic="Fluvic", organic="Organic")
    base = [r for r in wg["strata"] if r["size_matched_to"] != r["size_matched_to"] or r["size_matched_to"] is None]
    for s in ("well_drained", "hydromorphic", "fluvic", "organic"):
        for t in ("soc", "ph"):
            r = next((x for x in base if x["stratum"] == s and x["target"] == t), None)
            if r is None:
                continue
            rows.append(f"{name[s]} & {'carbon' if t == 'soc' else 'pH'} & {r['n']:,} & {r['n_regions']} & "
                        f"{r['random_cv_r2']:.2f} & {f2(r['loro_median_r'])} {ci(r['loro_median_r_ci'])} & "
                        f"{r['r_max']:.2f} \\\\")
    rows.append("\\midrule")
    for size, s in (("5426", "hydromorphic"), ("1613", "fluvic")):
        rs = [summary(f"_well_drained_soc_n{size}_s{k}") for k in range(10)]
        med = [x["loro_median_pearson"] for x in rs if x]
        rows.append(f"Well-drained, size of {name[s].lower()} & carbon & {int(size):,} & & & "
                    f"{f2(st.median(med))} [{f2(min(med))}, {f2(max(med))}] & \\\\")
    head = ("Stratum & Target & Profiles & Regions & Random-CV & Within-region $r$, held-out & Replicate \\\\\n"
            " & & & & $R^2$ & region (95\\% CI) & ceiling \\\\")
    return wrap("llrrrlr", head, rows, 7, [
        "WoSIS profiles split by field drainage class, never by measured carbon; 0--30\\,cm, the identical protocol of the cross-biome benchmark.",
        "Size-matched rows: well-drained profiles subsampled to the size of the wetter stratum, median and range over ten draws.",
        "Organic profiles populate two regions and are reported but not interpreted."])


def tab_variance_cee():
    vp = {r["biome"]: r for f in ("variance_partition.json", "variance_partition_wetness.json",
                                  "variance_partition_fluvic_ph.json") for r in load(f)["rows"]}
    order = [("well_drained", "Well-drained, carbon"), ("well_drained_ph", "Well-drained, pH"),
             ("hydromorphic", "Hydromorphic, carbon"), ("hydromorphic_ph", "Hydromorphic, pH"),
             ("fluvic", "Fluvic, carbon"), ("fluvic_ph", "Fluvic, pH"),
             ("terrestrial_conc", "Random WoSIS subsample, carbon"), ("mangrove", "Mangrove"),
             ("marsh", "Salt marsh"), ("seagrass", "Seagrass"), ("permafrost", "Permafrost")]
    try:
        for r in load("variance_partition_well_drained_extra.json")["rows"]:
            vp[r["biome"]] = r
        order.insert(2, ("well_drained_clay", "Well-drained, clay"))
    except FileNotFoundError:
        pass
    rows = []
    for k, lab in order:
        r = vp[k]
        rows.append(f"{lab} & {r['n_regions']} & {100 * r['between_regions']:.0f} & {100 * r['between_sites_within']:.0f} & "
                    f"{100 * r['replicate']:.0f} & {f2(r['r2_between_regions'])} \\\\")
        if k == "fluvic_ph" or k == "terrestrial_conc":
            rows.append("\\midrule")
    head = ("System & Regions & \\multicolumn{3}{c}{Share of variance (\\%)} & $R^2$ of region mean \\\\\n"
            " & & regions & sites & replicates & (held-out region) \\\\")
    return wrap("lrrrrr", head, rows, 6, [
        "Nested variance components of the log target. Region means predicted from region-mean covariates by leave-one-region-out",
        "ridge regression. The random WoSIS subsample (all drainage classes) is the mineral-soil set of Supplementary Table 1."])


def tab_sensitivity_cee():
    def row(lab, base, variants):
        cells = []
        for t in [base] + variants:
            s = summary(t)
            cells.append("n/a" if s is None else f"{f2(s['loro_median_pearson'])} ({s['n_regions']})")
        return f"{lab} & " + " & ".join(cells) + " \\\\"
    wd = "_well_drained_soc"
    rows = [row("Well-drained, carbon", wd, [wd + "_e150", wd + "_e500", wd + "_climate", wd + "_ridge"])]
    old = (OUT / "tab_sensitivity.tex").read_text().splitlines()
    body = [l for l in old if "&" in l and not l.lstrip().startswith(("Biome", "\\multicolumn"))]
    rows += [l.replace("Terr. mineral, conc.", "Random WoSIS subsample, carbon")
              .replace("Terr. mineral, stock", "Random WoSIS subsample, stock") for l in body]
    head = "System & 250 km (base) & 150 km & 500 km & climate only & ridge \\\\"
    return wrap("lrrrrr", head, rows, 6, [
        "Median held-out within-region $r$ (number of regions). Variants change the region radius, restrict covariates to the",
        "nineteen CHELSA bioclimate layers, or replace gradient boosting with ridge regression."])


def tab_publishedmap_cee():
    pm = load("published_map_test.json")
    names = {d["id"]: d["name"] for d in load("figure_data.json")["deltas"]}
    ov = pm["training_overlap"]
    ind = {d["delta_id"]: d for d in ov["per_delta_independent"]}
    rows = []
    for d in pm["per_delta"]:
        i = ind.get(d["delta_id"])
        rows.append(f"{names.get(d['delta_id'], d['delta_id'])} & {d['n']:.0f} & {d['obs_med']:.0f} & {d['map_med']:.0f} & "
                    f"{('%+.0f' % d['bias']).replace('-', '$-$')} & {f2(d['pearson'])} & {100 * ov['per_delta_share_within_indep_km'].get(d['delta_id'], 0):.0f}\\% & "
                    f"{(i['n'] if i else 0):.0f} & {f2(i['pearson']) if i else 'n/a'} \\\\")
    g = pm["global"]
    rows.append("\\midrule")
    rows.append(f"\\textbf{{All deltas}} & {g['n']} & & & {g['median_abs_bias']:.0f}$^{{*}}$ & {f2(g['median_within_delta_pearson'])} & "
                f"{100 * ov['share_within_indep_km']:.0f}\\% & {ov['n_independent']} & {f2(ov['median_within_delta_pearson_independent'])} \\\\")
    head = ("Delta & $n$ & Obs. & Map & Bias & $r$ & Within 1\\,km & \\multicolumn{2}{c}{Cores $>$1\\,km} \\\\\n"
            " & & \\multicolumn{3}{c}{(Mg\\,ha$^{-1}$)} & within & of training & $n$ & $r$ \\\\")
    return wrap("lrrrrrrrr", head, rows, 9, [
        "Mean layer of the v1.2 map (Zenodo 7727569, 2000--2002 epoch) at the benchmark cores. Within 1\\,km of training: share of cores",
        f"within 1\\,km of a point of the map's own training compilation ({100 * ov['share_within_100m']:.0f}\\% lie within 100\\,m). $^{{*}}$median of $|$per-delta bias$|$."])


def tab_tier1_soiltype():
    s = load("tier1_inventory.json")["summary"]
    rows = [f"Aggregated default, 386 t\\,C\\,ha$^{{-1}}$ (as reported) & {s['sum_tier1_TgC'] / 1000:.2f} & {s['sum_observed_TgC'] / 1000:.2f} & "
            f"{-s['net_diff_TgCO2e'] / 1000:.1f} \\\\"]
    lab = {"default split by soil type (estuarine mineral 286, other organic 471)": "Soil-type defaults, estuarine share from the setting map",
           "every country on the mineral default 286": "Mineral-soil default, 286, everywhere",
           "every country on the organic default 471": "Organic-soil default, 471, everywhere"}
    for k, v in s["tier1_soil_type"].items():
        rows.append(f"{lab[k]} & {v['sum_tier1_TgC'] / 1000:.2f} & {v['sum_observed_TgC'] / 1000:.2f} & {-v['net_diff_TgCO2e'] / 1000:.1f} \\\\")
    head = "Tier 1 default applied & Tier 1 (Pg C) & Cores (Pg C) & Difference (Pg CO$_2$e) \\\\"
    return wrap("lrrr", head, rows, 4, [
        "IPCC 2013 Wetlands Supplement, Table 4.11: 471 (organic), 286 (mineral) and 386 t\\,C\\,ha$^{-1}$ (aggregated, for soils that cannot be",
        "disaggregated). The soil-type split assigns each country's estuarine share of mangrove extent (Zhang et al. 2024) to the mineral default."])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("tab_gradient", tab_gradient), ("tab_variance_cee", tab_variance_cee),
                     ("tab_sensitivity_cee", tab_sensitivity_cee), ("tab_publishedmap_cee", tab_publishedmap_cee),
                     ("tab_tier1_soiltype", tab_tier1_soiltype)]:
        (OUT / f"{name}.tex").write_text(fn())
        print("wrote", OUT / f"{name}.tex")


if __name__ == "__main__":
    main()
