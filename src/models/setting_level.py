#!/usr/bin/env python3
"""Does river influence explain the mangrove regional carbon level the covariates miss?

The variance partition shows that a mangrove region's mean soil-carbon level cannot be
predicted from the 28 global covariates (leave-one-region-out R2 <= 0.03). This test asks
whether one physically interpretable setting variable, the share of a region's mangroves
that are estuarine (river-fed) rather than marine, carries that level. Each benchmark core
is labelled by the nearest polygon of the global estuarine/marine mangrove map of Zhang et
al. (2024, Nat. Commun. 15, 8994; figshare 27129174) within MAX_KM; a region's estuarine
share is the fraction of its labelled cores that are estuarine. Region means of
log(1+stock) are then predicted leave-one-region-out by ridge regression from
  (a) region-mean covariates            (the variance_partition baseline)
  (b) estuarine share alone
  (c) both
and the residual of (a) is correlated with the estuarine share. A permutation test
(shuffling the share across regions) gives the null for the gain of (c) over (a).

Output: data/processed/setting_level.json + console.
"""
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data/processed"
Z = ROOT / "data/external/zhang2024"
MAX_KM = 5.0
N_PERM = 2000
ALPHA = 10.0


def label_cores(df):
    import geopandas as gpd
    pts = gpd.GeoDataFrame(df[["lat", "lon"]].copy(),
                           geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326")
    best = np.full(len(df), np.inf); lab = np.full(len(df), None, dtype=object)
    for name, shp in (("estuarine", Z / "est/Estuarine mangroves/Estuarine_mangroves.shp"),
                      ("marine", Z / "mar/Marine mangroves/Marine_mangroves.shp")):
        bbox = tuple(pts.total_bounds + np.array([-0.5, -0.5, 0.5, 0.5]))
        poly = gpd.read_file(shp, bbox=bbox).to_crs("EPSG:4326")
        poly = poly[["geometry"]].to_crs(6933); p = pts.to_crs(6933)
        j = gpd.sjoin_nearest(p, poly, how="left", max_distance=MAX_KM * 1000, distance_col="d")
        d = j.groupby(level=0).d.min().reindex(range(len(df))).to_numpy()
        better = np.nan_to_num(d, nan=np.inf) < best
        best[better] = d[better]; lab[better] = name
        print(f"{name}: {len(poly)} polygons, {int(np.isfinite(d).sum())} cores within {MAX_KM} km", flush=True)
    return lab, best / 1000.0


def loro_r2(Xm, yv):
    from sklearn.linear_model import Ridge
    from sklearn.metrics import r2_score
    pred = np.empty(len(yv))
    for i in range(len(yv)):
        tr = np.arange(len(yv)) != i
        mu, sd = Xm[tr].mean(0), Xm[tr].std(0) + 1e-9
        pred[i] = Ridge(alpha=ALPHA).fit((Xm[tr] - mu) / sd, yv[tr]).predict(((Xm[i] - mu) / sd)[None])[0]
    return float(r2_score(yv, pred)), pred


def main():
    from scipy.stats import spearmanr
    df = pd.read_parquet(PROC / "soc_training.parquet").dropna(subset=["region_id"]).reset_index(drop=True)
    feats = [c for c in df.columns if c.startswith(("chelsa_", "sg_", "gsoc_", "lulc_", "dist_", "tidal_"))]
    lab, dkm = label_cores(df)
    df["setting"] = lab; df["setting_km"] = dkm
    df[["core_id", "region_id", "setting", "setting_km"]].to_csv(PROC / "setting_level_cores.csv", index=False)
    y = np.log1p(df.soc_0_100_Mgha); reg = df.region_id
    share = (df.assign(e=(df.setting == "estuarine").astype(float).where(df.setting.notna()))
               .groupby("region_id").e.mean())
    Xm = df[feats].groupby(reg).mean(); Xm = Xm.fillna(Xm.mean())
    ym = y.groupby(reg).mean()
    keep = share.dropna().index.intersection(ym.index)
    Xm, ym, sh = Xm.loc[keep].to_numpy(float), ym.loc[keep].to_numpy(), share.loc[keep].to_numpy()
    r2_cov, pred_cov = loro_r2(Xm, ym)
    r2_set, _ = loro_r2(sh[:, None], ym)
    r2_both, _ = loro_r2(np.column_stack([Xm, sh]), ym)
    rho_lvl, p_lvl = spearmanr(sh, ym); rho_res, p_res = spearmanr(sh, ym - pred_cov)
    rng = np.random.default_rng(0); gain = r2_both - r2_cov; null = []
    for _ in range(N_PERM):
        null.append(loro_r2(np.column_stack([Xm, rng.permutation(sh)]), ym)[0] - r2_cov)
    p_gain = float((np.sum(np.array(null) >= gain) + 1) / (N_PERM + 1))
    null_set = [loro_r2(rng.permutation(sh)[:, None], ym)[0] for _ in range(N_PERM)]
    p_set = float((np.sum(np.array(null_set) >= r2_set) + 1) / (N_PERM + 1))
    out = dict(n_cores=int(len(df)), n_cores_labelled=int(df.setting.notna().sum()),
               cores_by_setting=df.setting.value_counts().to_dict(), n_regions=int(len(keep)),
               max_km=MAX_KM, ridge_alpha=ALPHA,
               loro_r2_region_mean=dict(covariates=round(r2_cov, 3), estuarine_share=round(r2_set, 3),
                                        both=round(r2_both, 3)),
               gain_of_share_over_covariates=round(gain, 3), p_gain_permutation=round(p_gain, 4),
               p_share_alone_permutation=round(p_set, 4),
               spearman_share_vs_level=[round(float(rho_lvl), 3), round(float(p_lvl), 4)],
               spearman_share_vs_covariate_residual=[round(float(rho_res), 3), round(float(p_res), 4)],
               per_region=pd.DataFrame(dict(region=keep, estuarine_share=sh.round(3), level=ym.round(3),
                                            pred_covariates=pred_cov.round(3))).to_dict("records"))
    (PROC / "setting_level.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "per_region"}, indent=1))


if __name__ == "__main__":
    main()
