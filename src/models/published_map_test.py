#!/usr/bin/env python3
"""Direct test of a PUBLISHED blue-carbon map against in-situ cores, per delta.
We sample the updated Sanderman et al. (2018) global 30 m mangrove SOC stock map (Zenodo
record 7727569, v1.2, epoch 2000-2002, 0-100 cm, t/ha) at the CCN core locations and compare
map-predicted vs observed SOC for each core delta. If the product shows the same per-delta
failures (large bias, low within-delta correlation) as our model, the transferability problem
is a property of operational maps, not just of our re-implementation.
The record ships, per epoch, the mean prediction (`typology_m`) and the lower and upper 95%
prediction-interval bounds (`typology_l.std`, `typology_u.std`), the naming documented by
Maxwell et al. (2023) for the same product family. The MEAN layer is the map value; the
bounds are used only to report the empirical coverage of the map's own 95% interval.
Where the mean is valid but the lower bound is nodata, the lower bound is taken as 0.
COGs are read remotely via /vsicurl/ (no full download).
Sanderman's model was trained on a global core compilation that overlaps these cores. The
training locations ship with the record (soil_points_mangroves.csv.gz for v1.2 and
mangroves_SOC_points.gpkg for the 2018 original), so each benchmark core is tagged with its
distance to the nearest training location and the statistics are repeated on the cores more
than INDEP_KM from any of them, the subset on which the map is evaluated out of sample.
Output: data/processed/published_map_test.json + console table.
"""
import os, json
from pathlib import Path
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MULTIRANGE", "YES")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "90")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "10")
import numpy as np, pandas as pd, rasterio

ROOT = Path(__file__).resolve().parents[2]
REC = "https://zenodo.org/records/7727569/files"
TRAIN = ROOT / "data/external/sanderman_v12_points"
INDEP_KM = 1.0
COGS = {
    "mean": "soc.tha_tnc.mangroves.typology_m_30m_b0..100cm_2000_2002_go_epsg.4326_v1.2.tif",
    "lower": "soc.tha_tnc.mangroves.typology_l.std_30m_b0..100cm_2000_2002_go_epsg.4326_v1.2.tif",
    "upper": "soc.tha_tnc.mangroves.typology_u.std_30m_b0..100cm_2000_2002_go_epsg.4326_v1.2.tif",
}


def sample_map(lons, lats):
    """Mean map SOC and its 95% prediction bounds (t/ha) at points; nan where nodata."""
    pts = list(zip(lons, lats)); out = {}
    for t, fn in COGS.items():
        with rasterio.open(f"/vsicurl/{REC}/{fn}?download=1") as ds:
            v = np.array([x[0] for x in ds.sample(pts)], dtype="float64")
            out[t] = np.where((v == ds.nodata) | ~np.isfinite(v), np.nan, v)
        print(f"  {t}: {int(np.isfinite(out[t]).sum())}/{len(pts)} cores with a value", flush=True)
    mean = np.where(out["mean"] > 0, out["mean"], np.nan)
    ok = np.isfinite(mean)
    n_fill = int((ok & ~np.isfinite(out["lower"])).sum())
    lower = np.where(ok & ~np.isfinite(out["lower"]), 0.0, out["lower"])
    print(f"  lower bound nodata where mean valid (set to 0): {n_fill}", flush=True)
    return mean, lower, out["upper"]


def training_distance_km(lats, lons):
    """Distance from each point to the nearest location in the map's training data."""
    import geopandas as gpd
    from sklearn.neighbors import BallTree
    c = pd.read_csv(TRAIN / "soil_points_mangroves.csv.gz",
                    usecols=["latitude_decimal_degrees", "longitude_decimal_degrees"])
    c.columns = ["lat", "lon"]
    g = gpd.read_file(TRAIN / "mangroves_SOC_points.gpkg").to_crs(4326)
    g = pd.DataFrame(dict(lat=g.geometry.y, lon=g.geometry.x))
    t = pd.concat([c, g]).dropna().round(5).drop_duplicates()
    print(f"  {len(t)} distinct training locations", flush=True)
    tree = BallTree(np.radians(t[["lat", "lon"]].to_numpy()), metric="haversine")
    d, _ = tree.query(np.radians(np.c_[lats, lons]), k=1)
    return d[:, 0] * 6371.0


def main():
    soc = pd.read_parquet(ROOT / "data/processed/soc_labels.parquet")
    reg = pd.read_csv(ROOT / "data/processed/delta_registry.csv")
    core = set(reg[reg.role == "core"].id)
    df = soc[soc.delta_id.isin(core)].dropna(subset=["lat", "lon", "soc_0_100_Mgha"]).copy()
    print(f"sampling Sanderman map at {len(df)} core-delta cores (remote COGs)...")
    df["map_soc"], df["map_lo"], df["map_hi"] = sample_map(df.lon.to_numpy(), df.lat.to_numpy())
    df["train_km"] = training_distance_km(df.lat.to_numpy(), df.lon.to_numpy())
    m = df.dropna(subset=["map_soc"]).copy()
    print(f"resolved {len(m)}/{len(df)} cores with a published-map value")
    m[["core_id", "delta_id", "lat", "lon", "soc_0_100_Mgha", "map_soc", "map_lo", "map_hi",
       "train_km"]].to_csv(ROOT / "data/processed/published_map_cores.csv", index=False)

    def stats(g):
        o, p = g.soc_0_100_Mgha.to_numpy(), g.map_soc.to_numpy()
        r = float(np.corrcoef(o, p)[0, 1]) if len(g) > 2 and o.std() > 0 and p.std() > 0 else np.nan
        return pd.Series(dict(n=len(g), obs_med=round(float(np.median(o)), 0),
                              map_med=round(float(np.median(p)), 0),
                              bias=round(float(np.mean(p - o)), 0),
                              rmse=round(float(np.sqrt(np.mean((p - o) ** 2))), 0),
                              pearson=round(r, 2),
                              pi95_coverage=round(float(np.mean((o >= g.map_lo) & (o <= g.map_hi))), 2),
                              pi95_rel_width=round(float(np.median((g.map_hi - g.map_lo) / p)), 2)))
    per = m.groupby("delta_id").apply(stats).reset_index()
    # global agreement
    o, p = m.soc_0_100_Mgha.to_numpy(), m.map_soc.to_numpy()
    glob = dict(n=len(m), pearson=round(float(np.corrcoef(o, p)[0, 1]), 2),
                bias=round(float(np.mean(p - o)), 1),
                rmse=round(float(np.sqrt(np.mean((p - o) ** 2))), 1),
                median_within_delta_pearson=round(float(per.pearson.median()), 2),
                median_abs_bias=round(float(per.bias.abs().median()), 1),
                pi95_coverage=round(float(np.mean((o >= m.map_lo.to_numpy()) & (o <= m.map_hi.to_numpy()))), 2),
                pi95_median_rel_width=round(float(np.median((m.map_hi - m.map_lo) / m.map_soc)), 2),
                layer="typology_m (mean), Zenodo 7727569 v1.2, epoch 2000-2002")
    ind = m[m.train_km > INDEP_KM]
    per_ind = ind.groupby("delta_id").apply(stats).reset_index()
    overlap = dict(indep_km=INDEP_KM,
                   share_within_100m=round(float((m.train_km <= 0.1).mean()), 3),
                   share_within_indep_km=round(float((m.train_km <= INDEP_KM).mean()), 3),
                   per_delta_share_within_indep_km={k: round(float(v), 2) for k, v in
                                                    (m.train_km <= INDEP_KM).groupby(m.delta_id).mean().items()},
                   n_independent=int(len(ind)),
                   median_within_delta_pearson_independent=(round(float(per_ind[per_ind.n >= 5].pearson.median()), 2)
                                                            if len(per_ind) else None),
                   per_delta_independent=per_ind.to_dict("records"))
    out = {"global": glob, "per_delta": per.to_dict("records"), "training_overlap": overlap}
    (ROOT / "data/processed/published_map_test.json").write_text(json.dumps(out, indent=1))

    print("\n=== Sanderman 2018 published map vs in-situ, per delta ===")
    print(per.to_string(index=False))
    print(f"\nGLOBAL: n={glob['n']} pearson={glob['pearson']} bias={glob['bias']} rmse={glob['rmse']} t/ha")
    print(f"median within-delta pearson={glob['median_within_delta_pearson']}, "
          f"median |per-delta bias|={glob['median_abs_bias']} t/ha")
    print("\n=== overlap with the map's training locations ===")
    print(json.dumps({k: v for k, v in overlap.items() if k != "per_delta_independent"}, indent=1))
    print(per_ind.to_string(index=False))
    print("\nwrote data/processed/published_map_test.json")


if __name__ == "__main__":
    main()
