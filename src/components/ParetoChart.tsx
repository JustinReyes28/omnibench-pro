import React from 'react';
import { ScoredModelEntry } from './LeaderboardTable';

interface Props {
  models: ScoredModelEntry[];
}

export const ParetoChart: React.FC<Props> = ({ models }) => {
  const priced = models.filter(
    (m) => m.pricing.blended_per_1m_usd !== null && m.pricing.blended_per_1m_usd > 0
  );

  const minLogX = Math.log10(0.08);
  const maxLogX = Math.log10(35);
  const minY = 24;
  const maxY = 104;

  const toX = (price: number) => ((Math.log10(Math.max(0.08, Math.min(35, price))) - minLogX) / (maxLogX - minLogX)) * 100;
  const toY = (score: number) => 100 - ((Math.max(minY, Math.min(maxY, score)) - minY) / (maxY - minY)) * 100;

  return (
    <div className="border border-[#111317] bg-[#FFFFFF]">
      <div className="flex items-center justify-between border-b border-[#D8D4C8] bg-[#F4F2ED] px-4 py-3">
        <div>
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#C84B31]">// PARETO EFFICIENCY OBSERVATORY</span>
          <h3 className="font-heading text-base font-bold text-[#111317]">Blended Price ($/1M Log) vs. Unified Quality</h3>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-[#68707C]">
          Vermilion Ring = Pareto Frontier
        </span>
      </div>
      <div className="relative h-80 w-full swiss-dot-bg overflow-hidden">
        {priced.map((m) => {
          const left = `${toX(m.pricing.blended_per_1m_usd!)}%`;
          const top = `${toY(m.dynamicScore)}%`;
          return (
            <div
              key={m.id}
              style={{ left, top }}
              title={`${m.display_name}: ${m.dynamicScore.toFixed(1)} pts @ $${m.pricing.blended_per_1m_usd}/1M`}
              className={`absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center rounded-full font-mono text-[8px] font-bold ${
                m.isDynamicPareto
                  ? 'h-4 w-4 border-2 border-[#C84B31] bg-[#111317] text-white z-10'
                  : 'h-2.5 w-2.5 bg-[#68707C] text-white'
              }`}
            />
          );
        })}
      </div>
    </div>
  );
};
