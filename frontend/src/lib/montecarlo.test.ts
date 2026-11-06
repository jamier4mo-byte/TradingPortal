/** node --test src/lib/montecarlo.test.ts (Node strips the types). Run by `make test`. */
import assert from "node:assert/strict";
import { test } from "node:test";

import { monteCarlo, rng } from "./montecarlo.ts";

test("the generator is seeded: same seed, same numbers", () => {
  const a = rng(42);
  const b = rng(42);
  const xs = Array.from({ length: 5 }, a);
  assert.deepEqual(xs, Array.from({ length: 5 }, b));
  assert.ok(xs.every((x) => x >= 0 && x < 1));
  assert.notDeepEqual(xs, Array.from({ length: 5 }, rng(43)));
});

test("same inputs and seed give identical results", () => {
  const rs = [2, -1, -1, 3, -1, 0, 1.5, -1];
  assert.deepEqual(monteCarlo({ rs, seed: 7 }), monteCarlo({ rs, seed: 7 }));
  assert.notDeepEqual(monteCarlo({ rs, seed: 7 }).final, monteCarlo({ rs, seed: 8 }).final);
});

test("a constant sequence has no spread and no drawdown", () => {
  const out = monteCarlo({ rs: [1, 1, 1, 1], paths: 200 });
  assert.equal(out.paths, 200);
  assert.equal(out.length, 4);
  assert.deepEqual(out.bands.p5, [1, 2, 3, 4]);
  assert.deepEqual(out.bands.p95, [1, 2, 3, 4]);
  assert.equal(out.maxDrawdown.worst, 0);
  assert.equal(out.probDrawdown, 0);
  assert.equal(out.probNegative, 0);
});

test("all losses: every path finishes at −n and draws down n", () => {
  const out = monteCarlo({ rs: [-1, -1, -1], ddThreshold: 3 });
  assert.equal(out.final.p50, -3);
  assert.equal(out.maxDrawdown.p50, 3);
  assert.equal(out.probDrawdown, 1);
  assert.equal(out.probNegative, 1);
});

test("bands are ordered and the probability is a fraction", () => {
  const rs = Array.from({ length: 60 }, (_, i) => (i % 5 === 0 ? 3 : i % 3 === 0 ? 0 : -1));
  const out = monteCarlo({ rs, paths: 1000, seed: 1, ddThreshold: 6 });
  for (let s = 0; s < out.length; s++) {
    assert.ok(out.bands.p5[s] <= out.bands.p25[s] && out.bands.p25[s] <= out.bands.p50[s]);
    assert.ok(out.bands.p50[s] <= out.bands.p75[s] && out.bands.p75[s] <= out.bands.p95[s]);
  }
  assert.ok(out.probDrawdown > 0 && out.probDrawdown < 1);
  assert.ok(out.maxDrawdown.p95 >= out.maxDrawdown.p50);
});

test("no trades gives an empty result, not a crash", () => {
  assert.equal(monteCarlo({ rs: [] }).paths, 0);
});
