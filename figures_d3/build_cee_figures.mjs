// Communications Earth & Environment figures (RewriteCEE), server-side D3 -> SVG.
// House style as build_journal_figures.mjs: Helvetica, 6-7 pt type, bold lower-case panel
// letters, red for what does not transfer, charcoal for what does, no blue or teal.
// Data: data/processed/figure_data_cee.json (src/figure_data_cee.py), figure_data.json,
// tier1_inventory.json, fewshot_calibration.json, published_map_test.json. No number is
// computed here.
import { JSDOM } from "jsdom";
import * as d3 from "d3";
import { feature } from "topojson-client";
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { createRequire } from "module";
const require = createRequire(import.meta.url);

const DATA = JSON.parse(readFileSync("../data/processed/figure_data.json", "utf8"));
const C = JSON.parse(readFileSync("../data/processed/figure_data_cee.json", "utf8"));
const T1 = JSON.parse(readFileSync("../data/processed/tier1_inventory.json", "utf8"));
const FS = JSON.parse(readFileSync("../data/processed/fewshot_calibration.json", "utf8"));
const PM = JSON.parse(readFileSync("../data/processed/published_map_test.json", "utf8"));
// Two finishes from one code path: FIG_STYLE=subtle (submission, default) or showcase
// (talks, cover letter, press). Every effect is pure vector: shadows are stacked offset
// translucent copies, fades are stacked translucent bands (rsvg-convert rasterises SVG
// filters and its gradient shadings do not survive \includegraphics).
const STYLE = process.env.FIG_STYLE === "showcase" ? "showcase" : "subtle";
const FX = STYLE === "showcase"
  ? { layers: 8, step: 0.62, alpha: 0.06, halo: 2.0, hi: 0.6, ocean: "#EEF3F5", land: "#E3E3E3", landEdge: 0.7, extrude: 7, card: 1.7 }
  : { layers: 3, step: 0.34, alpha: 0.055, halo: 1.6, hi: 0.4, ocean: "#F1F5F7", land: "#E3E3E3", landEdge: 0.5, extrude: 0, card: 1.5 };
const OUT = STYLE === "showcase" ? "svg_cee/showcase" : "svg_cee";

const FONT = "Helvetica, Arial, sans-serif";
// One palette for every figure: red against charcoal, with amber, brown and the greys for
// secondary series. No blue and no teal anywhere, and no red/green pairing.
const PAL = { red: "#C62828", charcoal: "#37474F", amber: "#F9A825", orange: "#E65100",
              brown: "#5D4037", greygreen: "#607D63",
              ink: "#212121", grey: "#424242", mid: "#9E9E9E", light: "#E0E0E0" };
// Red carries what does not transfer, charcoal what transfers or is attainable.
const FAIL = PAL.red, HOLD = PAL.charcoal;
const INK = PAL.ink, AXIS = PAL.ink, MUTE = PAL.grey, LIGHT = PAL.light;
const FS_T = 7, FS_S = 6, FS_L = 8;
d3.formatDefaultLocale({ decimal: ".", thousands: ",", grouping: [3], currency: ["", ""], minus: "\u2013" });     // text, small, panel letter
const TW = 454;                          // text width in pt

function svgRoot(w, h) {
  const dom = new JSDOM("<!DOCTYPE html><body></body>");
  const svg = d3.select(dom.window.document.body).append("svg")
    .attr("xmlns", "http://www.w3.org/2000/svg").attr("width", w).attr("height", h)
    .attr("viewBox", `0 0 ${w} ${h}`).attr("font-family", FONT).attr("font-size", FS_T);
  svg.append("rect").attr("width", w).attr("height", h).attr("fill", "white");
  return { dom, svg };
}
function save(dom, name) {
  mkdirSync(OUT, { recursive: true });
  writeFileSync(`${OUT}/${name}.svg`, dom.window.document.body.innerHTML);
  console.log("  wrote", `${OUT}/${name}.svg`);
}
function letter(svg, x, y, t) {
  svg.append("text").attr("x", x).attr("y", y).attr("font-size", FS_L).attr("font-weight", "bold")
     .attr("fill", INK).text(t);
}
function axis(g, ax, { size = FS_T, color = AXIS } = {}) {
  g.call(ax);
  g.selectAll("path,line").attr("stroke", color).attr("stroke-width", 0.5);
  g.selectAll("text").attr("fill", INK).attr("font-size", size).attr("font-family", FONT);
  g.select(".domain").attr("stroke", color);
  return g;
}
function txt(g, x, y, t, { size = FS_T, anchor = "start", color = INK, weight = "normal", rotate = 0, style = "normal", halo = false } = {}) {
  const mk = () => {
    const e = g.append("text").attr("x", x).attr("y", y).attr("font-size", size).attr("text-anchor", anchor)
       .attr("fill", color).attr("font-weight", weight).attr("font-style", style).text(t);
    if (rotate) e.attr("transform", `rotate(${rotate},${x},${y})`);
    return e;
  };
  // halo: a white stroked copy underneath keeps labels legible where they sit on data
  if (halo) mk().attr("fill", "white").attr("stroke", "white").attr("stroke-width", FX.halo).attr("stroke-linejoin", "round");
  return mk();
}
function ylabel(g, x, y, t) { txt(g, x, y, t, { anchor: "middle", rotate: -90 }); }
function hline(g, x1, x2, y, color = AXIS, dash = null, w = 0.5) {
  const l = g.append("line").attr("x1", x1).attr("x2", x2).attr("y1", y).attr("y2", y)
     .attr("stroke", color).attr("stroke-width", w);
  if (dash) l.attr("stroke-dasharray", dash);
  return l;
}
// soft drop shadow: `make(parent)` appends the silhouette; copies are offset down-right,
// widened by a growing stroke and drawn at low opacity, largest first
function dropShadow(g, make, k = 1) {
  const L = Math.max(1, Math.round(FX.layers * Math.min(1, 0.35 + k * 0.65)));
  for (let i = L; i >= 1; i--) {
    const d = i * FX.step * k;
    const grp = g.append("g").attr("transform", `translate(${(d * 0.45).toFixed(2)},${d.toFixed(2)})`).attr("opacity", FX.alpha);
    const e = make(grp), open = e.attr("fill") === "none";
    const sw = open ? (parseFloat(e.attr("data-w") || 1) + d * 0.9) : d * 0.9;
    e.attr("fill", open ? "none" : INK).attr("stroke", INK).attr("stroke-width", sw.toFixed(2))
      .attr("stroke-linejoin", "round").attr("stroke-linecap", "round").attr("opacity", null).attr("fill-opacity", null);
  }
}
// thin light line along the top edge of a filled shape
function topHighlight(g, x, y, w, alpha = FX.hi) {
  if (w <= 1.2) return;
  g.append("line").attr("x1", x + 0.5).attr("x2", x + w - 0.5).attr("y1", y + 0.45).attr("y2", y + 0.45)
    .attr("stroke", "white").attr("stroke-width", 0.7).attr("opacity", alpha);
}
// interval band that deepens toward its centre value (nested translucent rects)
function nestedBand(g, x, w, yTop, yBot, yMid, color, total, n = 18) {
  g.append("rect").attr("x", x).attr("y", yTop).attr("width", w).attr("height", yBot - yTop).attr("fill", color).attr("opacity", total * 0.45);
  for (let i = 1; i <= n; i++) {
    const t = i / (n + 1), y1 = yTop + (yMid - yTop) * t, y2 = yBot + (yMid - yBot) * t;
    g.append("rect").attr("x", x).attr("y", y1).attr("width", w).attr("height", Math.max(0.2, y2 - y1)).attr("fill", color).attr("opacity", total * 0.55 / n);
  }
}
// vertical fade inside an arbitrary area (clip path + stacked bands, strongest at the top)
let CLIP = 0;
function areaFade(svg, g, d, yTop, yBot, x0, x1, color, alpha, n = 18) {
  const id = `clip${STYLE}${++CLIP}`;
  svg.append("defs").append("clipPath").attr("id", id).append("path").attr("d", d);
  const cg = g.append("g").attr("clip-path", `url(#${id})`);
  for (let i = 0; i < n; i++)
    cg.append("rect").attr("x", x0).attr("y", yTop).attr("width", x1 - x0).attr("height", (yBot - yTop) * (i + 1) / n)
      .attr("fill", color).attr("opacity", alpha / n);
}
const fmt2 = d3.format("+.2f"), fmt1 = d3.format(".1f");
// signed two-decimal value with a true minus and no "+" (protocol text); -0.00 prints as 0.00
const fmtS = v => { const t = d3.format(".2f")(Math.abs(v) < 0.005 ? 0 : v); return t.replace("-", "\u2013"); };
const rng = d3.randomLcg(7);
const DELTA_NAME = Object.fromEntries(DATA.deltas.map(d => [d.id, d.name]));

// ===================================================================== Fig. 1
// a  random cross-validation R2 per system; b out-of-region within-region r per system,
//    with the pH and clay of the same mineral profiles as controls
function fig1() {
  const W = TW, H = 222, { dom, svg } = svgRoot(W, H);
  const S = C.systems, K = C.controls;
  // ---- a
  const aw = 128, pa = { l: 58, r: 8, t: 22, b: 40 };
  letter(svg, 2, 9, "a");
  const ga = svg.append("g");
  const ya = d3.scaleBand().domain(S.map(s => s.key)).range([pa.t, H - pa.b]).padding(0.32);
  const xa = d3.scaleLinear().domain([0, 1]).range([pa.l, aw - pa.r]);
  axis(ga.append("g").attr("transform", `translate(0,${H - pa.b})`), d3.axisBottom(xa).ticks(3).tickSize(2.5).tickPadding(2));
  txt(ga, (xa.range()[0] + xa.range()[1]) / 2, H - pa.b + 17, "random cross-validation R²", { anchor: "middle", size: FS_S });
  S.forEach(s => {
    const y = ya(s.key), h = ya.bandwidth();
    txt(ga, pa.l - 4, y + h / 2 + 2.2, s.label.replace("Mineral, well-drained", "Mineral"), { anchor: "end", size: FS_S, color: s.cls === "mineral" ? HOLD : FAIL });
    dropShadow(ga, g => g.append("rect").attr("x", xa(0)).attr("y", y).attr("width", xa(s.random_r2) - xa(0)).attr("height", h), 0.7);
    ga.append("rect").attr("x", xa(0)).attr("y", y).attr("width", xa(s.random_r2) - xa(0)).attr("height", h).attr("fill", PAL.mid);
    topHighlight(ga, xa(0), y, xa(s.random_r2) - xa(0));
    txt(ga, xa(s.random_r2) + 2, y + h / 2 + 2.2, d3.format(".2f")(s.random_r2), { size: FS_S });
  });
  ga.append("line").attr("x1", pa.l).attr("x2", pa.l).attr("y1", pa.t - 4).attr("y2", H - pa.b).attr("stroke", AXIS).attr("stroke-width", 0.5);

  // ---- b
  const bx0 = aw + 12, pb = { l: 30, r: 6, t: 22, b: 40 };
  letter(svg, bx0 - 6, 9, "b");
  const gb = svg.append("g").attr("transform", `translate(${bx0},0)`), bw = W - bx0;
  const keys = [...S.map(s => s.key), "gap", ...K.map(k => k.key)];
  const xb = d3.scaleBand().domain(keys).range([pb.l, bw - pb.r]).paddingInner(0.22).paddingOuter(0.1);
  const yb = d3.scaleLinear().domain([-0.6, 1]).range([H - pb.b, pb.t]);
  axis(gb.append("g").attr("transform", `translate(${pb.l},0)`), d3.axisLeft(yb).ticks(8).tickSize(2.5).tickPadding(2).tickFormat(d3.format("+.1f")));
  ylabel(gb, 8, (yb.range()[0] + yb.range()[1]) / 2, "within-region r, held-out region");
  hline(gb, pb.l, bw - pb.r, yb(0), AXIS, null, 0.5);
  const xd0 = xb(S[1].key) - xb.step() * xb.paddingInner() / 2, xd1 = xb(S[S.length - 1].key) + xb.bandwidth() + xb.step() * xb.paddingInner() / 2;
  gb.append("rect").attr("x", xd0).attr("y", pb.t - 16).attr("width", xd1 - xd0).attr("height", H - pb.b - pb.t + 16).attr("fill", FAIL).attr("opacity", 0.06);
  txt(gb, (xd0 + xd1) / 2, pb.t - 9, "carbon, carbon-dense soils", { anchor: "middle", size: FS_S, color: FAIL });
  txt(gb, xb("mineral") + xb.bandwidth() / 2, pb.t - 9, "carbon", { anchor: "middle", size: FS_S, color: HOLD });
  const xk0 = xb(K[0].key), xk1 = xb(K[K.length - 1].key) + xb.bandwidth();
  txt(gb, (xk0 + xk1) / 2, pb.t - 9, "pH and clay, same profiles", { anchor: "middle", size: FS_S, color: MUTE });
  [...S, ...K].forEach(b => {
    const x0 = xb(b.key), w = xb.bandwidth(), xc = x0 + w / 2;
    const col = b.cls === "dense" ? FAIL : b.cls === "mineral" ? HOLD : PAL.brown;
    const rsz = d3.scaleSqrt().domain([10, d3.max(b.regions, r => r.n)]).range([1.1, 3.6]);
    nestedBand(gb, x0 + 3, w - 6, yb(b.ci[1]), yb(b.ci[0]), yb(b.median_r), col, 0.3);
    b.regions.forEach((r, i) => {
      const jx = xc + ((i * 7919) % 100 / 100 - 0.5) * (w - 12), y = Math.max(yb.domain()[0], r.r);
      gb.append("circle").attr("cx", jx).attr("cy", yb(y)).attr("r", rsz(r.n)).attr("fill", col).attr("opacity", 0.7).attr("stroke", "white").attr("stroke-width", 0.3);
    });
    hline(gb, x0 + 3, x0 + w - 3, yb(b.median_r), "white", null, 2.2);
    hline(gb, x0 + 3, x0 + w - 3, yb(b.median_r), INK, null, 1.2);
    gb.append("line").attr("x1", xc).attr("x2", xc).attr("y1", yb(b.median_r)).attr("y2", yb(b.ceiling)).attr("stroke", MUTE).attr("stroke-width", 0.5).attr("stroke-dasharray", "1.5,1.5");
    const dia = d3.symbol(d3.symbolDiamond, 16)(), dt = `translate(${xc},${yb(b.ceiling)})`;
    dropShadow(gb, s => s.append("path").attr("d", dia).attr("transform", dt), 0.6);
    gb.append("path").attr("d", dia).attr("transform", dt).attr("fill", "white").attr("stroke", HOLD).attr("stroke-width", 0.7);
    txt(gb, x0 + w - 3, yb(Math.max(b.ci[1], b.median_r)) - 2.5, (Math.abs(b.median_r) < 0.005 ? "0.00" : fmt2(b.median_r)), { anchor: "end", size: FS_S, weight: "bold", halo: true });
    txt(gb, xc, H - pb.b + 9, b.label.replace("Mineral, well-drained", "Mineral"), { anchor: "middle", size: FS_S });
    txt(gb, xc, H - pb.b + 16.5, `${d3.format(",")(b.n)}`, { anchor: "middle", size: FS_S, color: MUTE });
    txt(gb, xc, H - pb.b + 24, `${b.n_regions} regions`, { anchor: "middle", size: FS_S, color: MUTE });
  });
  const lg = gb.append("g").attr("transform", `translate(${xb("gap") - 4},${yb(-0.38)})`);
  lg.append("path").attr("d", d3.symbol(d3.symbolDiamond, 16)()).attr("transform", "translate(3,0)").attr("fill", "white").attr("stroke", INK).attr("stroke-width", 0.7);
  txt(lg, 9, 2.2, "replicate ceiling", { size: FS_S });
  lg.append("line").attr("x1", 0).attr("x2", 6).attr("y1", 8).attr("y2", 8).attr("stroke", INK).attr("stroke-width", 1.2);
  txt(lg, 9, 10.2, "median, 95% CI", { size: FS_S });
  lg.append("circle").attr("cx", 3).attr("cy", 16).attr("r", 1.8).attr("fill", MUTE);
  txt(lg, 9, 18.2, "held-out region", { size: FS_S });
  save(dom, "cee_fig1");
}

// ===================================================================== Fig. 2
// rows run from well-drained mineral soils through wetter WoSIS profiles to the
// carbon-dense systems; a variance partition, b held-out R2 of the regional mean,
// c held-out within-region r (pattern)
function fig2() {
  const W = TW, H = 196, G = C.gradient, { dom, svg } = svgRoot(W, H);
  const pt = 22, pbm = 30;
  const y = d3.scaleBand().domain(G.map(g => g.key)).range([pt, H - pbm]).padding(0.28);
  const split = (y(G.find(g => g.src === "dense").key) + y(G.filter(g => g.src === "wosis").slice(-1)[0].key) + y.bandwidth()) / 2;
  const colOf = g => g.src === "dense" ? FAIL : HOLD;
  // ---- a: variance partition
  const aw = 190, la = 64;
  letter(svg, 2, 9, "a");
  const ga = svg.append("g");
  const xa = d3.scaleLinear().domain([0, 1]).range([la, aw - 6]);
  axis(ga.append("g").attr("transform", `translate(0,${H - pbm})`), d3.axisBottom(xa).ticks(5, "%").tickSize(2.5).tickPadding(2));
  txt(ga, (xa.range()[0] + xa.range()[1]) / 2, H - pbm + 17, "share of variance of log carbon", { anchor: "middle", size: FS_S });
  const comps = [["between_regions", FAIL, "between regions"], ["between_sites_within", PAL.amber, "between sites"], ["replicate", PAL.mid, "replicates"]];
  G.forEach(g => {
    let x = 0; const yy = y(g.key), h = y.bandwidth();
    txt(ga, la - 4, yy + h / 2 + 2.2, g.label, { anchor: "end", size: FS_S, color: colOf(g) });
    dropShadow(ga, s => s.append("rect").attr("x", xa(0)).attr("y", yy).attr("width", xa(1) - xa(0)).attr("height", h), 0.7);
    comps.forEach(([k, col]) => {
      ga.append("rect").attr("x", xa(x)).attr("y", yy).attr("width", xa(x + g[k]) - xa(x)).attr("height", h).attr("fill", col);
      if (k === "between_regions") txt(ga, xa(x + g[k] / 2), yy + h / 2 + 2, `${Math.round(g[k] * 100)}%`, { anchor: "middle", size: FS_S, color: "white" });
      x += g[k];
    });
    topHighlight(ga, xa(0), yy, xa(1) - xa(0));
  });
  comps.forEach(([k, col, lab], i) => {
    const xo = la + [0, 54, 102][i];
    ga.append("rect").attr("x", xo).attr("y", pt - 12).attr("width", 6).attr("height", 5).attr("fill", col);
    txt(ga, xo + 8, pt - 7.5, lab, { size: FS_S });
  });
  hline(ga, 20, aw - 6, split, MUTE, "2,1.5", 0.5);

  // shared drawing for b and c
  function dotPanel(x0, w, letterTxt, dom_, xlab, valKey, ciKey, phKey, phCiKey) {
    const p = { l: 8, r: 8 };
    letter(svg, x0 - 4, 9, letterTxt);
    const g = svg.append("g").attr("transform", `translate(${x0},0)`);
    const xs = d3.scaleLinear().domain(dom_).range([p.l, w - p.r]);
    axis(g.append("g").attr("transform", `translate(0,${H - pbm})`), d3.axisBottom(xs).tickValues([-0.4, 0, 0.4, 0.8]).tickSize(2.5).tickPadding(2).tickFormat(d3.format(".1f")));
    txt(g, (xs.range()[0] + xs.range()[1]) / 2, H - pbm + 17, xlab, { anchor: "middle", size: FS_S });
    g.append("line").attr("x1", xs(0)).attr("x2", xs(0)).attr("y1", pt - 4).attr("y2", H - pbm).attr("stroke", AXIS).attr("stroke-width", 0.5);
    hline(g, p.l, w - p.r, split, MUTE, "2,1.5", 0.5);
    G.forEach(r => {
      const yc = y(r.key) + y.bandwidth() / 2, col = colOf(r);
      const clip = v => Math.max(dom_[0], v);
      const off = r[phKey] !== undefined ? -2 : 0;
      if (ciKey && r[ciKey]) g.append("line").attr("x1", xs(clip(r[ciKey][0]))).attr("x2", xs(r[ciKey][1])).attr("y1", yc + off).attr("y2", yc + off).attr("stroke", col).attr("stroke-width", 0.8);
      dropShadow(g, s => s.append("circle").attr("cx", xs(clip(r[valKey]))).attr("cy", yc + off).attr("r", 2.5), 0.55);
      g.append("circle").attr("cx", xs(clip(r[valKey]))).attr("cy", yc + off).attr("r", 2.5).attr("fill", col).attr("stroke", "white").attr("stroke-width", 0.35);
      if (r[valKey] < dom_[0]) txt(g, xs(dom_[0]) + 5, yc + off + 2.2, d3.format("+.2f")(r[valKey]).replace("-", "–"), { size: FS_S, color: MUTE });
      if (r[phKey] !== undefined) {
        if (phCiKey) g.append("line").attr("x1", xs(r[phCiKey][0])).attr("x2", xs(r[phCiKey][1])).attr("y1", yc + 2.5).attr("y2", yc + 2.5).attr("stroke", PAL.brown).attr("stroke-width", 0.5).attr("stroke-dasharray", "1.5,1");
        g.append("path").attr("d", d3.symbol(d3.symbolDiamond, 14)()).attr("transform", `translate(${xs(r[phKey])},${yc + 2.5})`).attr("fill", "white").attr("stroke", PAL.brown).attr("stroke-width", 0.7);
      }
    });
    const lg = g.append("g").attr("transform", `translate(${p.l + 2},${pt - 9})`);
    lg.append("circle").attr("cx", 2.5).attr("cy", -1.5).attr("r", 2.3).attr("fill", HOLD);
    txt(lg, 7, 0.7, "carbon", { size: FS_S });
    lg.append("path").attr("d", d3.symbol(d3.symbolDiamond, 14)()).attr("transform", "translate(35,-1.5)").attr("fill", "white").attr("stroke", PAL.brown).attr("stroke-width", 0.7);
    txt(lg, 40, 0.7, "pH, same profiles", { size: FS_S });
    return g;
  }
  const bw = (W - aw - 14) / 2;
  dotPanel(aw + 14, bw, "b", [-0.4, 1], "held-out R² of the regional mean (level)", "level_r2", null, "ph_level_r2", null);
  dotPanel(aw + 18 + bw, bw, "c", [-0.4, 1], "held-out within-region r (pattern)", "pattern_r", "pattern_ci", "ph_pattern_r", "ph_pattern_ci");
  save(dom, "cee_fig2");
}

// ===================================================================== Fig. 3
// a national core medians against the IPCC Tier 1 mangrove soil default; b delta means of
// the published 30 m map against the cores; c local cores added to a global model
function fig3() {
  const W = TW, H = 300, { dom, svg } = svgRoot(W, H);
  const lw = 220;
  // ---- a: Tier 1
  const pa = { l: 62, r: 8, t: 22, b: 26 };
  letter(svg, 2, 9, "a");
  const ga = svg.append("g");
  const pc = T1.per_country.slice().sort((a, b) => d3.descending(a.ratio_obs_to_tier1, b.ratio_obs_to_tier1));
  const t1 = T1.summary.tier1_Mgha;
  const xa = d3.scaleLog().domain([0.1, 2]).range([pa.l, lw - pa.r]);
  const ya = d3.scaleBand().domain(pc.map(c => c.iso3)).range([pa.t, H - pa.b]).padding(0.2);
  axis(ga.append("g").attr("transform", `translate(0,${H - pa.b})`), d3.axisBottom(xa).tickValues([0.1, 0.2, 0.5, 1, 2]).tickFormat(d3.format(".1~f")).tickSize(2.5).tickPadding(2));
  txt(ga, (xa.range()[0] + xa.range()[1]) / 2, H - pa.b + 17, "national median core stock / IPCC Tier 1 default", { anchor: "middle", size: FS_S });
  ga.append("line").attr("x1", xa(1)).attr("x2", xa(1)).attr("y1", pa.t).attr("y2", H - pa.b).attr("stroke", AXIS).attr("stroke-width", 0.6);
  const rs = d3.scaleSqrt().domain([0, d3.max(pc, c => c.mangrove_km2)]).range([0.8, 4.5]);
  pc.forEach(c => {
    const yc = ya(c.iso3) + ya.bandwidth() / 2;
    txt(ga, pa.l - 3, yc + 2, c.country.replace("United Republic of Tanzania", "Tanzania").replace("Federated States of Micronesia", "Micronesia").replace("United States of America", "USA"), { anchor: "end", size: FS_S });
    ga.append("line").attr("x1", xa(c.stock_ci_Mgha[0] / t1)).attr("x2", xa(c.stock_ci_Mgha[1] / t1)).attr("y1", yc).attr("y2", yc).attr("stroke", INK).attr("stroke-width", 0.5);
    const rsplit = c.median_stock_Mgha / c.tier1_split_Mgha;
    ga.append("line").attr("x1", xa(rsplit)).attr("x2", xa(rsplit)).attr("y1", yc - 3).attr("y2", yc + 3).attr("stroke", PAL.brown).attr("stroke-width", 0.9);
    dropShadow(ga, s => s.append("circle").attr("cx", xa(c.ratio_obs_to_tier1)).attr("cy", yc).attr("r", rs(c.mangrove_km2)), 0.55);
    ga.append("circle").attr("cx", xa(c.ratio_obs_to_tier1)).attr("cy", yc).attr("r", rs(c.mangrove_km2))
      .attr("fill", c.ratio_obs_to_tier1 < 1 ? FAIL : HOLD).attr("stroke", "white").attr("stroke-width", 0.4);
  });
  const lA = ga.append("g").attr("transform", `translate(${pa.l},${pa.t - 12})`);
  lA.append("circle").attr("cx", 3).attr("cy", -1.5).attr("r", 2.4).attr("fill", MUTE);
  txt(lA, 8, 0.7, `against the aggregated default (${t1} t C per ha)`, { size: FS_S });
  lA.append("line").attr("x1", 3).attr("x2", 3).attr("y1", 4).attr("y2", 10).attr("stroke", PAL.brown).attr("stroke-width", 0.9);
  txt(lA, 8, 9.2, "against the soil-type default (286 estuarine, 471 other)", { size: FS_S });

  // ---- b: published map, delta means
  const bx0 = lw + 16, bw = W - bx0, bh = 140, pb = { l: 30, r: 8, t: 10, b: 24 };
  letter(svg, bx0 - 6, 9, "b");
  const gb = svg.append("g").attr("transform", `translate(${bx0},0)`);
  const ov = PM.training_overlap.per_delta_share_within_indep_km;
  const xs = d3.scaleLinear().domain([0, 600]).range([pb.l, bw - pb.r]), ys = d3.scaleLinear().domain([0, 600]).range([bh - pb.b, pb.t]);
  axis(gb.append("g").attr("transform", `translate(0,${bh - pb.b})`), d3.axisBottom(xs).ticks(6).tickSize(2.5).tickPadding(2));
  axis(gb.append("g").attr("transform", `translate(${pb.l},0)`), d3.axisLeft(ys).ticks(6).tickSize(2.5).tickPadding(2));
  txt(gb, (xs.range()[0] + xs.range()[1]) / 2, bh - pb.b + 17, "median core stock, Mg C per ha", { anchor: "middle", size: FS_S });
  ylabel(gb, 6, (ys.range()[0] + ys.range()[1]) / 2, "median mapped stock");
  gb.append("line").attr("x1", xs(0)).attr("x2", xs(600)).attr("y1", ys(0)).attr("y2", ys(600)).attr("stroke", MUTE).attr("stroke-width", 0.5).attr("stroke-dasharray", "2,1.5");
  const rsz = d3.scaleSqrt().domain([0, d3.max(PM.per_delta, d => d.n)]).range([1.2, 4.5]);
  const LAB = { amazon_amapa: [3, -5, "start"], rufiji: [-4, -5, "end"], zambezi: [-5, 2.2, "end"], saloum_gambia: [5, 7, "start"], sundarbans: [-4, 8, "end"], mekong: [7, -3, "start"] };
  PM.per_delta.forEach(d => {
    const cx = xs(d.obs_med), cy = ys(d.map_med), inT = (ov[d.delta_id] || 0) >= 0.5;
    gb.append("line").attr("x1", cx).attr("x2", cx).attr("y1", ys(d.obs_med)).attr("y2", cy).attr("stroke", FAIL).attr("stroke-width", 0.5).attr("opacity", 0.6);
    dropShadow(gb, s => s.append("circle").attr("cx", cx).attr("cy", cy).attr("r", rsz(d.n)), 0.5);
    gb.append("circle").attr("cx", cx).attr("cy", cy).attr("r", rsz(d.n)).attr("fill", inT ? "white" : HOLD).attr("stroke", HOLD).attr("stroke-width", inT ? 0.8 : 0.4);
    const [dx, dy, an] = LAB[d.delta_id] || [rsz(d.n) + 2, 2.2, "start"];
    txt(gb, cx + dx, cy + dy, (DELTA_NAME[d.delta_id] || d.delta_id).split(" ")[0], { size: FS_S, color: MUTE, halo: true, anchor: an });
  });
  const lB = gb.append("g").attr("transform", `translate(${pb.l + 6},${pb.t + 4})`);
  lB.append("circle").attr("cx", 2.5).attr("cy", -1.5).attr("r", 2.3).attr("fill", HOLD);
  txt(lB, 7, 0.7, "delta (area proportional to cores)", { size: FS_S });
  lB.append("circle").attr("cx", 2.5).attr("cy", 6.5).attr("r", 2.3).attr("fill", "white").attr("stroke", HOLD).attr("stroke-width", 0.8);
  txt(lB, 7, 8.7, "most cores within 1 km of map training", { size: FS_S });

  // ---- c: few-shot
  const cy0 = bh + 10, ch = H - cy0, pcm = { l: 30, r: 8, t: 10, b: 26 };
  letter(svg, bx0 - 6, cy0 + 1, "c");
  const gc = svg.append("g").attr("transform", `translate(${bx0},${cy0})`);
  const ks = FS.ks, xc = d3.scaleLinear().domain([0, 25]).range([pcm.l, bw - pcm.r]);
  const yc = d3.scaleLinear().domain([-0.4, 0.8]).range([ch - pcm.b, pcm.t]);
  axis(gc.append("g").attr("transform", `translate(0,${ch - pcm.b})`), d3.axisBottom(xc).tickValues(ks).tickSize(2.5).tickPadding(2));
  axis(gc.append("g").attr("transform", `translate(${pcm.l},0)`), d3.axisLeft(yc).ticks(5).tickSize(2.5).tickPadding(2).tickFormat(d3.format("+.1f")));
  txt(gc, (xc.range()[0] + xc.range()[1]) / 2, ch - pcm.b + 17, "local cores added to training, k", { anchor: "middle", size: FS_S });
  ylabel(gc, 6, (yc.range()[0] + yc.range()[1]) / 2, "within-delta r");
  hline(gc, pcm.l, bw - pcm.r, yc(0), AXIS, null, 0.5);
  const ceil = DATA.biomes.find(b => b.tag === "mangrove").ceiling;
  hline(gc, pcm.l, bw - pcm.r, yc(ceil / 2), MUTE, "2,1.5", 0.5);
  txt(gc, xc(19), yc(ceil / 2) + 7, "half the replicate ceiling", { anchor: "end", size: FS_S, color: MUTE, halo: true });
  Object.values(FS.per_delta).forEach(s => {
    const pts = ks.filter(k => s[k] && Number.isFinite(s[k].pearson)).map(k => [xc(k), yc(s[k].pearson)]);
    gc.append("path").attr("d", d3.line()(pts)).attr("fill", "none").attr("stroke", HOLD).attr("stroke-width", 0.5).attr("opacity", 0.35);
  });
  const med = ks.map(k => [k, FS.summary[k].median_pearson]), loc = ks.filter(k => FS.summary[k].median_pearson_localonly !== null).map(k => [k, FS.summary[k].median_pearson_localonly]);
  const medD = d3.line().x(d => xc(d[0])).y(d => yc(d[1]))(med), locD = d3.line().x(d => xc(d[0])).y(d => yc(d[1]))(loc);
  gc.append("path").attr("d", medD).attr("fill", "none").attr("stroke", HOLD).attr("stroke-width", 1.4);
  med.forEach(d => gc.append("circle").attr("cx", xc(d[0])).attr("cy", yc(d[1])).attr("r", 2.1).attr("fill", HOLD).attr("stroke", "white").attr("stroke-width", 0.5));
  gc.append("path").attr("d", locD).attr("fill", "none").attr("stroke", PAL.amber).attr("stroke-width", 1.2).attr("stroke-dasharray", "3,2");
  loc.forEach(d => gc.append("path").attr("d", d3.symbol(d3.symbolSquare, 12)()).attr("transform", `translate(${xc(d[0])},${yc(d[1])})`).attr("fill", PAL.amber).attr("stroke", "white").attr("stroke-width", 0.4));
  const lC = gc.append("g").attr("transform", `translate(${pcm.l + 6},${yc(-0.18)})`);
  lC.append("line").attr("x1", 0).attr("x2", 8).attr("y1", 0).attr("y2", 0).attr("stroke", HOLD).attr("stroke-width", 1.4);
  txt(lC, 11, 2.2, "global model + k local cores (median)", { size: FS_S });
  lC.append("line").attr("x1", 0).attr("x2", 8).attr("y1", 8).attr("y2", 8).attr("stroke", PAL.amber).attr("stroke-width", 1.2).attr("stroke-dasharray", "3,2");
  txt(lC, 11, 10.2, "ridge on the k local cores alone", { size: FS_S });
  save(dom, "cee_fig3");
}

fig1(); fig2(); fig3();
