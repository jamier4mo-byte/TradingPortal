/** Runs the Monte Carlo off the main thread so 1,000 paths never stall a chart morph. */
import { type MonteCarloInput, monteCarlo } from "./montecarlo.ts";

self.onmessage = (event: MessageEvent<MonteCarloInput & { id: number }>) => {
  const { id, ...input } = event.data;
  self.postMessage({ id, result: monteCarlo(input) });
};
