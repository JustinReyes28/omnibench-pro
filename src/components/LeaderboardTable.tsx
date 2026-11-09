import React, { useState } from 'react';
import { CanonicalModel } from '../lib/schema';

export interface ScoredModelEntry extends CanonicalModel {
  dynamicScore: number;
  isDynamicPareto: boolean;
}

interface Props {
  models: ScoredModelEntry[];
  comparedIds: string[];
  onToggleCompare: (modelId: string) => void;
}

export const LeaderboardTable: React.FC<Props> = ({ models, comparedIds, onToggleCompare }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [bestPerLabOnly, setBestPerLabOnly] = useState<boolean>(true);

  const seenLabs = new Set<string>();
  const topStackModels = models.filter((m) => {
    if (m.composite.provisional_ranking) return false;
    if (!bestPerLabOnly) return true;
    if (seenLabs.has(m.provider)) return false;
    seenLabs.add(m.provider);
    return true;
  }).slice(0, 18);

  return (
    <div className="space-y-8">
      {/* OmniBench Signature 4-Pillar Stacked Contribution Leaderboard */}
      <div className="border border-[#111317] bg-[#FFFFFF]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#111317] bg-[#111317] px-5 py-3 font-mono text-xs text-white">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
            <span className="font-bold uppercase tracking-widest">4-PILLAR STACKED CONTRIBUTION LEADERBOARD</span>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="inline-flex items-center gap-1"><span className="h-2 w-2 bg-[#255C99]" /> AA</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-2 bg-[#C57B18]" /> LiveBench</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-2 bg-[#C84B31]" /> Arena</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-2 bg-[#1F7A63]" /> Vals</span>
            <button
              type="button"
              onClick={() => setBestPerLabOnly(!bestPerLabOnly)}
              className="border border-[#D8D4C8]/40 bg-[#FFFFFF]/10 px-2.5 py-0.5 text-[10px] uppercase tracking-wider text-white hover:bg-[#C84B31]"
            >
              {bestPerLabOnly ? 'Filter: Best Model Per Lab' : 'Filter: Top 18 Models'}
            </button>
          </div>
        </div>
        <div className="divide-y divide-[#EBE8E0] p-4 space-y-2">
          {topStackModels.map((m, idx) => {
            const p = m.normalized_pillars ?? {};
            const segAA = (p.aa ?? 0) * 0.30;
            const segLB = (p.lb ?? 0) * 0.30;
            const segAR = (p.ar ?? 0) * 0.15;
            const segVA = (p.va ?? 0) * 0.25;
            return (
              <div
                key={m.id}
                onClick={() => onToggleCompare(m.id)}
                className="grid grid-cols-12 items-center gap-3 pt-2 first:pt-0 hover:bg-[#F4F2ED] px-2 py-1.5 cursor-pointer transition"
              >
                <div className="col-span-4 flex items-center gap-2.5 truncate">
                  <span className="w-5 font-mono text-[11px] font-bold text-[#68707C]">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <div className="truncate">
                    <div className="truncate font-heading text-xs font-bold text-[#111317]">{m.display_name}</div>
                    <div className="font-mono text-[10px] text-[#68707C]">
                      {m.provider} • {(m.thinking_effort || 'standard').toUpperCase()} EFFORT
                    </div>
                  </div>
                </div>
                <div className="col-span-6">
                  <div className="flex h-5 w-full overflow-hidden bg-[#EBE8E0] p-0.5 gap-0.5">
                    <div className="h-full bg-[#255C99]" style={{ width: `${segAA}%` }} title={`AA: ${segAA.toFixed(1)}`} />
                    <div className="h-full bg-[#C57B18]" style={{ width: `${segLB}%` }} title={`LiveBench: ${segLB.toFixed(1)}`} />
                    <div className="h-full bg-[#C84B31]" style={{ width: `${segAR}%` }} title={`Arena: ${segAR.toFixed(1)}`} />
                    <div className="h-full bg-[#1F7A63]" style={{ width: `${segVA}%` }} title={`Vals: ${segVA.toFixed(1)}`} />
                  </div>
                </div>
                <div className="col-span-2 text-right font-mono text-xs font-bold text-[#111317]">
                  {m.dynamicScore.toFixed(2)} pts
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Complete Evaluation Matrix Table */}
      <div className="overflow-x-auto border border-[#111317] bg-[#FFFFFF]">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-[#111317] bg-[#111317] font-mono text-[10px] font-semibold uppercase tracking-wider text-white">
              <th className="py-3 pl-4 pr-2">#</th>
              <th className="px-3 py-3">Model, Provider &amp; Thinking Effort</th>
              <th className="px-3 py-3 text-right text-[#F4A261]">Unified Score</th>
              <th className="px-3 py-3 text-right">Vals Index</th>
              <th className="px-3 py-3 text-right">AA Intell.</th>
              <th className="px-3 py-3 text-right">LiveBench</th>
              <th className="px-3 py-3 text-right">Arena Elo</th>
              <th className="px-3 py-3 text-right">Cost ($/1M)</th>
              <th className="px-3 py-3 text-right">Speed</th>
              <th className="py-3 pl-2 pr-4 text-center">Compare / Drilldown</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#D8D4C8]">
            {models.map((m, idx) => {
              const isSelected = comparedIds.includes(m.id);
              const isExpanded = expandedId === m.id;
              const aa = m.benchmarks.artificial_analysis;
              const lb = m.benchmarks.livebench;
              const ar = m.benchmarks.arena;
              const va = m.benchmarks.vals;
              const effort = (m.thinking_effort || 'standard').toUpperCase();

              return (
                <React.Fragment key={m.id}>
                  <tr className="transition hover:bg-[#F4F2ED]">
                    <td className="py-3 pl-4 pr-2 font-mono text-xs font-bold text-[#68707C]">
                      {String(idx + 1).padStart(3, '0')}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-heading font-bold text-[#111317]">{m.display_name}</span>
                        <span className="border border-[#255C99] bg-[#255C99]/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#255C99]">
                          {effort}
                        </span>
                        {m.isDynamicPareto && (
                          <span className="border border-[#C84B31] bg-[#C84B31]/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-[#C84B31]">
                            PARETO
                          </span>
                        )}
                        {m.is_open_weights && (
                          <span className="border border-[#1F7A63] bg-[#1F7A63]/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#1F7A63]">
                            OPEN
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-[#68707C]">
                        {m.provider} • {(m.context_window / 1000).toFixed(0)}k ctx • {m.license}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs font-bold text-[#C84B31]">
                      {m.dynamicScore.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#111317]">
                      {va ? `${va.vals_index.toFixed(2)}%` : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#111317]">
                      {aa ? `${aa.intelligence_index.toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#111317]">
                      {lb ? `${lb.global_average.toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#111317]">
                      {ar ? ar.text_elo : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#111317]">
                      {m.pricing.blended_per_1m_usd !== null ? `$${m.pricing.blended_per_1m_usd.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-[#373C44]">
                      {m.performance.output_tokens_per_sec !== null ? `${m.performance.output_tokens_per_sec.toFixed(0)} t/s` : '—'}
                    </td>
                    <td className="py-3 pl-2 pr-4 text-center">
                      <div className="inline-flex items-center gap-1.5 font-mono">
                        <button
                          type="button"
                          onClick={() => onToggleCompare(m.id)}
                          className={`border px-2 py-1 text-[10px] uppercase ${
                            isSelected
                              ? 'border-[#C84B31] bg-[#C84B31] text-white font-semibold'
                              : 'border-[#111317] bg-[#FFFFFF] text-[#111317] hover:bg-[#EBE8E0]'
                          }`}
                        >
                          {isSelected ? 'In Radar' : '+ Radar'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setExpandedId(isExpanded ? null : m.id)}
                          className="border border-[#111317] bg-[#F4F2ED] px-2 py-1 text-[10px] uppercase text-[#111317] hover:bg-[#111317] hover:text-white"
                        >
                          {isExpanded ? 'Close' : 'Subtasks'}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-[#F4F2ED]">
                      <td colSpan={10} className="px-6 py-4">
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4 text-xs font-mono">
                          <div className="border-l-4 border-[#1F7A63] bg-[#FFFFFF] p-3">
                            <div className="font-bold uppercase text-[#1F7A63] mb-1">Vals Enterprise v2.2</div>
                            {va ? (
                              <div className="space-y-1 text-[#111317]">
                                <div>Finance: {va.finance_agent}% • Legal: {va.legal_bench}%</div>
                                <div>Tax: {va.tax_agent}% • Vibe Code: {va.vibe_code}%</div>
                              </div>
                            ) : <div>Not evaluated</div>}
                          </div>
                          <div className="border-l-4 border-[#255C99] bg-[#FFFFFF] p-3">
                            <div className="font-bold uppercase text-[#255C99] mb-1">Artificial Analysis v5.0</div>
                            {aa ? (
                              <div className="space-y-1 text-[#111317]">
                                <div>Coding: {aa.coding_index}% • Math: {aa.math_index}%</div>
                                <div>TTFT: {m.performance.ttft_seconds}s</div>
                              </div>
                            ) : <div>Not evaluated</div>}
                          </div>
                          <div className="border-l-4 border-[#C57B18] bg-[#FFFFFF] p-3">
                            <div className="font-bold uppercase text-[#C57B18] mb-1">LiveBench Subtasks</div>
                            {lb ? (
                              <div className="space-y-1 text-[#111317]">
                                <div>Coding: {lb.coding}% • Agentic: {lb.agentic_coding}%</div>
                                <div>Reasoning: {lb.reasoning}% • IF: {lb.instruction_following}%</div>
                              </div>
                            ) : <div>Not evaluated</div>}
                          </div>
                          <div className="border-l-4 border-[#C84B31] bg-[#FFFFFF] p-3">
                            <div className="font-bold uppercase text-[#C84B31] mb-1">Arena.ai Crowd-BT</div>
                            {ar ? (
                              <div className="space-y-1 text-[#111317]">
                                <div>Text Elo: {ar.text_elo} ({ar.text_ci_lower}–{ar.text_ci_upper})</div>
                                <div>Coding Elo: {ar.coding_elo} • Votes: {ar.votes.toLocaleString()}</div>
                              </div>
                            ) : <div>Not evaluated</div>}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
