import { useEffect, useMemo, useRef, useState } from "react";

import Card from "../../../components/Card.tsx";
import { ChartSkeleton } from "../../../components/charts/Chart.tsx";
import { fmtR } from "../../../lib/journal.ts";
import type { MonteCarloResult } from "../../../lib/montecarlo.ts";
import { MonteCarloChart } from "./charts.tsx";

const PATHS = 1000;
const SEED = 20261106;

/** 1,000 bootstrap paths of the R sequence, computed in a Web Worker so the page never stalls. */
export function MonteCarloCard({ rs }: { rs: number[] }) {
  const [threshold, setThreshold] = useState(5);
  const [result, setResult] = useState<MonteCarloResult | null>(null);
  const worker = useRef<Worker | null>(null);
  const seq = useRef(0);
  const key = useMemo(() => rs.join(","), [rs]);

  useEffect(() => {
    const w = new Worker(new URL("../../../lib/montecarlo.worker.ts", import.meta.url), { type: "module" });
    w.onmessage = (e: MessageEvent<{ id: number; result: MonteCarloResult }>) => {
      if (e.data.id === seq.current) setResult(e.data.result);
    };
    worker.current = w;
    return () => w.terminate();
  }, []);

  useEffect(() => {
    const w = worker.current;
    if (!w || !key) return;
    const values = key.split(",").map(Number);
    if (values.length < 2) return;
    seq.current += 1;
    w.postMessage({ id: seq.current, rs: values, paths: PATHS, seed: SEED, ddThreshold: threshold });
  }, [key, threshold]);

  return (
    <Card title="Monte Carlo" subtitle={`${PATHS.toLocaleString("en-GB")} reshuffles of the R sequence: the range of results the same edge could have produced`}>
      {rs.length < 2 ? (
        <p className="text-body text-muted">Needs at least two trades with an R.</p>
      ) : !result ? (
        <ChartSkeleton height={260} />
      ) : (
        <div className="flex flex-col gap-4" data-testid="monte-carlo">
          <MonteCarloChart result={result} />
          <div className="flex flex-col gap-2 tablet:flex-row tablet:items-center tablet:gap-4">
            <label className="flex flex-wrap items-center gap-2 text-body">
              <span>Chance of a drawdown of at least</span>
              <input
                type="number"
                inputMode="decimal"
                min={0.5}
                max={100}
                step={0.5}
                value={threshold}
                onChange={(e) => setThreshold(Math.max(0.5, Number(e.target.value) || 0.5))}
                className="input num min-h-11 w-20 text-center"
                aria-describedby="mc-prob"
              />
              <span>R</span>
            </label>
            <p id="mc-prob" className="num text-body" aria-live="polite">
              <b className="text-title">{Math.round(result.probDrawdown * 100)}%</b> <span className="text-muted">of paths. Typical worst drawdown {fmtR(-result.maxDrawdown.p50)}; 1 in 20 is {fmtR(-result.maxDrawdown.p95)} or deeper; {Math.round(result.probNegative * 100)}% finish below zero.</span>
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
