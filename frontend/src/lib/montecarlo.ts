/** Monte Carlo of the R sequence: bootstrap paths (resample trades with replacement), seeded so the same
 * inputs always give the same answer. Pure: used by the Web Worker and by the Node test. */

/** mulberry32: small, fast, good enough for resampling. Same seed → same paths. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface MonteCarloInput {
  rs: number[];
  paths?: number;
  seed?: number;
  /** Probability of a drawdown at least this deep (positive R). */
  ddThreshold?: number;
  /** Path length; defaults to the number of trades. */
  length?: number;
}

export interface MonteCarloResult {
  paths: number;
  length: number;
  /** Percentile bands of cumulative R after each trade (index 0 = after trade 1). */
  bands: { p5: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[] };
  final: { p5: number; p50: number; p95: number };
  maxDrawdown: { p50: number; p95: number; worst: number };
  probDrawdown: number;
  probNegative: number;
  ddThreshold: number;
}

function percentile(sorted: Float64Array | number[], p: number): number {
  if (!sorted.length) return 0;
  const idx = (sorted.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

const round = (v: number) => Math.round(v * 1000) / 1000;

export function monteCarlo({ rs, paths = 1000, seed = 20261106, ddThreshold = 5, length }: MonteCarloInput): MonteCarloResult {
  const n = length ?? rs.length;
  const empty = { p5: [], p25: [], p50: [], p75: [], p95: [] };
  if (!rs.length || !n) {
    return { paths: 0, length: 0, bands: empty, final: { p5: 0, p50: 0, p95: 0 }, maxDrawdown: { p50: 0, p95: 0, worst: 0 }, probDrawdown: 0, probNegative: 0, ddThreshold };
  }
  const next = rng(seed);
  // cum[step * paths + path]: column-major so each step's values sort in one slice.
  const cum = new Float64Array(n * paths);
  const maxDd = new Float64Array(paths);
  for (let p = 0; p < paths; p++) {
    let total = 0;
    let peak = 0;
    let worst = 0;
    for (let s = 0; s < n; s++) {
      total += rs[Math.floor(next() * rs.length)];
      if (total > peak) peak = total;
      if (total - peak < worst) worst = total - peak;
      cum[s * paths + p] = total;
    }
    maxDd[p] = Math.abs(worst); // positive depth
  }
  const bands = { p5: [] as number[], p25: [] as number[], p50: [] as number[], p75: [] as number[], p95: [] as number[] };
  const column = new Float64Array(paths);
  for (let s = 0; s < n; s++) {
    column.set(cum.subarray(s * paths, (s + 1) * paths));
    column.sort();
    bands.p5.push(round(percentile(column, 0.05)));
    bands.p25.push(round(percentile(column, 0.25)));
    bands.p50.push(round(percentile(column, 0.5)));
    bands.p75.push(round(percentile(column, 0.75)));
    bands.p95.push(round(percentile(column, 0.95)));
  }
  const lastCol = cum.subarray((n - 1) * paths, n * paths);
  const finals = Float64Array.from(lastCol).sort();
  const dds = Float64Array.from(maxDd).sort();
  let hit = 0;
  let negative = 0;
  for (let p = 0; p < paths; p++) {
    if (maxDd[p] >= ddThreshold) hit++;
    if (lastCol[p] < 0) negative++;
  }
  return {
    paths,
    length: n,
    bands,
    final: { p5: round(percentile(finals, 0.05)), p50: round(percentile(finals, 0.5)), p95: round(percentile(finals, 0.95)) },
    maxDrawdown: { p50: round(percentile(dds, 0.5)), p95: round(percentile(dds, 0.95)), worst: round(dds[dds.length - 1]) },
    probDrawdown: hit / paths,
    probNegative: negative / paths,
    ddThreshold,
  };
}
