import React from 'react';
import { ScoredModelEntry } from './LeaderboardTable';

interface Props {
  models: ScoredModelEntry[];
  onRemove: (id: string) => void;
}

export const ModelComparisonModal: React.FC<Props> = ({ models, onRemove }) => {
  if (models.length === 0) return null;

  return (
    <div className="border border-[#111317] bg-[#FFFFFF] p-5">
      <h3 className="mb-3 font-heading text-lg font-bold text-[#111317]">
        Head-to-Head Model Comparison ({models.length}/4)
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {models.map((m) => (
          <div key={m.id} className="border border-[#111317] bg-[#F4F2ED] p-3.5 text-xs">
            <div className="flex items-center justify-between border-b border-[#D8D4C8] pb-1.5">
              <span className="font-heading text-sm font-bold text-[#111317]">{m.display_name}</span>
              <button
                type="button"
                onClick={() => onRemove(m.id)}
                className="font-mono text-[10px] uppercase text-[#C84B31] hover:underline"
              >
                Remove
              </button>
            </div>
            <div className="mt-2 space-y-1 font-mono text-[11px] text-[#373C44]">
              <div className="flex justify-between">
                <span>Unified Score:</span>
                <span className="font-bold text-[#C84B31]">
                  {m.dynamicScore.toFixed(2)}
                  {m.composite.sources_present < 4 ? ` (${m.composite.sources_present}/4)` : ''}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Vals Index:</span>
                <span>{m.benchmarks.vals ? `${m.benchmarks.vals.vals_index}%` : '—'}</span>
              </div>
              <div className="flex justify-between">
                <span>AA Intelligence:</span>
                <span>
                  {m.benchmarks.artificial_analysis
                    ? `${m.benchmarks.artificial_analysis.intelligence_index}%`
                    : '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>LiveBench Avg:</span>
                <span>{m.benchmarks.livebench ? `${m.benchmarks.livebench.global_average}%` : '—'}</span>
              </div>
              <div className="flex justify-between">
                <span>Arena Text Elo:</span>
                <span>{m.benchmarks.arena?.text_elo ?? '—'}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
