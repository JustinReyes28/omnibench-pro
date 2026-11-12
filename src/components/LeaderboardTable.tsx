import React, { useMemo, useState } from 'react';
import { CanonicalModel } from '../lib/schema';
import { DashboardFilterState } from '../hooks/useUrlFilterState';
import { getLabStyle } from '../lib/labPalette';

export interface ScoredModelEntry extends CanonicalModel {
  dynamicScore: number;
  isDynamicPareto: boolean;
}

interface Props {
  models: ScoredModelEntry[];
  totalModelsCount: number;
  allProviders: string[];
  filterState: DashboardFilterState;
  onFilterChange: (patch: Partial<DashboardFilterState>) => void;
  comparedIds: string[];
  onToggleCompare: (modelId: string) => void;
}

type SortColumn = 'dynamicScore' | 'va' | 'aa' | 'lb' | 'ar' | 'price' | 'speed';

export const LeaderboardTable: React.FC<Props> = ({
  models,
  totalModelsCount,
  allProviders,
  filterState,
  onFilterChange,
  comparedIds,
  onToggleCompare,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [bestPerLabOnly, setBestPerLabOnly] = useState<boolean>(true);
  const [showAllInStack, setShowAllInStack] = useState<boolean>(false);
  const [sortCol, setSortCol] = useState<SortColumn>('dynamicScore');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  // 4-Pillar Stacked Contribution Leaderboard models
  const topStackModels = useMemo(() => {
    const seenLabs = new Set<string>();
    const nonProv = models.filter((m) => !m.composite.provisional_ranking);
    const pool = nonProv.filter((m) => {
      if (!bestPerLabOnly) return true;
      if (seenLabs.has(m.provider)) return false;
      seenLabs.add(m.provider);
      return true;
    });

    if (showAllInStack) return pool;
    return pool.slice(0, bestPerLabOnly ? Math.max(21, allProviders.length) : 25);
  }, [models, bestPerLabOnly, showAllInStack, allProviders.length]);

  // Master Table sorted models
  const sortedModels = useMemo(() => {
    return [...models].sort((a, b) => {
      const provA = Boolean(a.composite.provisional_ranking);
      const provB = Boolean(b.composite.provisional_ranking);
      if (provA !== provB) return provA ? 1 : -1;

      let valA = 0;
      let valB = 0;

      switch (sortCol) {
        case 'va':
          valA = a.benchmarks.vals?.vals_index ?? -1;
          valB = b.benchmarks.vals?.vals_index ?? -1;
          break;
        case 'aa':
          valA = a.benchmarks.artificial_analysis?.intelligence_index ?? -1;
          valB = b.benchmarks.artificial_analysis?.intelligence_index ?? -1;
          break;
        case 'lb':
          valA = a.benchmarks.livebench?.global_average ?? -1;
          valB = b.benchmarks.livebench?.global_average ?? -1;
          break;
        case 'ar':
          valA = a.benchmarks.arena?.text_elo ?? -1;
          valB = b.benchmarks.arena?.text_elo ?? -1;
          break;
        case 'price':
          valA = a.pricing.blended_per_1m_usd ?? 9999;
          valB = b.pricing.blended_per_1m_usd ?? 9999;
          break;
        case 'speed':
          valA = a.performance.output_tokens_per_sec ?? -1;
          valB = b.performance.output_tokens_per_sec ?? -1;
          break;
        case 'dynamicScore':
        default:
          valA = a.dynamicScore;
          valB = b.dynamicScore;
          break;
      }

      if (sortAsc) return valA - valB;
      return valB - valA;
    });
  }, [models, sortCol, sortAsc]);

  const handleHeaderSort = (col: SortColumn) => {
    if (sortCol === col) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(col);
      setSortAsc(col === 'price'); // Price defaults to ascending (cheapest first)
    }
  };

  const hasActiveFilters =
    Boolean(filterState.searchQuery) ||
    filterState.providerFilter !== 'ALL' ||
    filterState.effortFilter !== 'ALL' ||
    filterState.openWeightsOnly ||
    filterState.paretoOnly;

  const resetFilters = () => {
    onFilterChange({
      searchQuery: '',
      providerFilter: 'ALL',
      effortFilter: 'ALL',
      openWeightsOnly: false,
      paretoOnly: false,
    });
  };

  const w = filterState.weights;
  const totalW = w.aa + w.lb + w.ar + w.va;
  const shareAA = totalW > 0 ? w.aa / totalW : 0.3;
  const shareLB = totalW > 0 ? w.lb / totalW : 0.3;
  const shareAR = totalW > 0 ? w.ar / totalW : 0.15;
  const shareVA = totalW > 0 ? w.va / totalW : 0.25;
  const pctAA = Math.round(shareAA * 100);
  const pctLB = Math.round(shareLB * 100);
  const pctAR = Math.round(shareAR * 100);
  const pctVA = Math.round(shareVA * 100);

  return (
    <div className="space-y-10">
      {/* OmniBench Signature 4-Pillar Stacked Contribution Leaderboard */}
      <div className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-[#111317] bg-[#111317] px-5 py-3 font-mono text-xs text-white">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
            <span className="font-bold uppercase tracking-widest">
              BENCHMARK SCORE CONTRIBUTION BREAKDOWN
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-[10px]">
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 bg-[#255C99]" /> AA ({pctAA}%)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 bg-[#C57B18]" /> LiveBench ({pctLB}%)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 bg-[#C84B31]" /> Arena ({pctAR}%)
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 bg-[#1F7A63]" /> Vals ({pctVA}%)
            </span>

            <button
              type="button"
              onClick={() => {
                setBestPerLabOnly(!bestPerLabOnly);
                setShowAllInStack(false);
              }}
              className="border border-[#D8D4C8]/40 bg-[#FFFFFF]/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white transition hover:bg-[#C84B31]"
            >
              {bestPerLabOnly ? `Filter: Best Model Per Lab (${allProviders.length} Labs)` : 'Filter: All Ranked Models'}
            </button>

            {!bestPerLabOnly && (
              <button
                type="button"
                onClick={() => setShowAllInStack(!showAllInStack)}
                className="border border-[#D8D4C8]/40 bg-[#FFFFFF]/10 px-2 py-1 text-[10px] uppercase text-white hover:bg-white hover:text-[#111317]"
              >
                {showAllInStack
                  ? 'Show Top 25'
                  : `Show All (${models.filter((m) => !m.composite.provisional_ranking).length})`}
              </button>
            )}
          </div>
        </div>

        <div className="divide-y divide-[#EBE8E0] p-4 space-y-1 max-h-[560px] overflow-y-auto">
          {topStackModels.map((m, idx) => {
            const p = m.normalized_pillars ?? {};
            const rawAA = (p.aa ?? 0) * shareAA;
            const rawLB = (p.lb ?? 0) * shareLB;
            const rawAR = (p.ar ?? 0) * shareAR;
            const rawVA = (p.va ?? 0) * shareVA;
            const rawSum = rawAA + rawLB + rawAR + rawVA;
            const barScale = rawSum > 0 ? m.dynamicScore / rawSum : 0;
            const segAA = rawAA * barScale;
            const segLB = rawLB * barScale;
            const segAR = rawAR * barScale;
            const segVA = rawVA * barScale;
            const labStyle = getLabStyle(m.provider);
            const isCompared = comparedIds.includes(m.id);

            return (
              <div
                key={m.id}
                onClick={() => onToggleCompare(m.id)}
                title={`Click to toggle ${m.display_name} in Head-to-Head Radar`}
                className={`grid grid-cols-12 items-center gap-3 pt-2 first:pt-0 px-2 py-1.5 cursor-pointer transition ${
                  isCompared ? 'bg-[#F4F2ED] border-l-4 border-[#C84B31]' : 'hover:bg-[#F4F2ED]'
                }`}
              >
                <div className="col-span-5 sm:col-span-4 flex items-center gap-2.5 truncate">
                  <span className="w-5 shrink-0 font-mono text-[11px] font-bold text-[#68707C]">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <span
                    className="inline-flex h-5 w-5 shrink-0 items-center justify-center font-mono text-[9px] font-bold"
                    style={{ backgroundColor: labStyle.badgeBg, color: labStyle.badgeText }}
                  >
                    {labStyle.short}
                  </span>
                  <div className="truncate">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="truncate font-heading text-xs font-bold text-[#111317]">
                        {m.display_name}
                      </span>
                      {m.composite.sources_present < 4 && (
                        <span
                          className="shrink-0 border border-[#68707C] bg-[#EBE8E0] px-1 font-mono text-[8px] font-semibold text-[#373C44]"
                          title={`Evaluated on ${m.composite.sources_present} of 4 benchmark sources`}
                        >
                          {m.composite.sources_present}/4 SRC
                        </span>
                      )}
                      {m.isDynamicPareto && (
                        <span className="border border-[#C84B31] bg-[#C84B31]/10 px-1 font-mono text-[8px] font-bold text-[#C84B31]">
                          PARETO
                        </span>
                      )}
                      {m.is_open_weights && (
                        <span className="border border-[#1F7A63] bg-[#1F7A63]/10 px-1 font-mono text-[8px] font-semibold text-[#1F7A63]">
                          OPEN
                        </span>
                      )}
                    </div>
                    <div className="font-mono text-[10px] text-[#68707C]">
                      {m.provider} • {(m.thinking_effort || 'standard').toUpperCase()} •{' '}
                      {m.pricing.blended_per_1m_usd !== null
                        ? `$${m.pricing.blended_per_1m_usd.toFixed(2)}/1M`
                        : 'Price N/A'}
                    </div>
                  </div>
                </div>

                <div className="col-span-5 sm:col-span-6">
                  <div className="flex h-5 w-full overflow-hidden bg-[#EBE8E0] p-0.5 gap-0.5">
                    <div
                      className="h-full bg-[#255C99] transition-all"
                      style={{ width: `${segAA}%` }}
                      title={`Artificial Analysis Contribution: ${segAA.toFixed(1)} pts`}
                    />
                    <div
                      className="h-full bg-[#C57B18] transition-all"
                      style={{ width: `${segLB}%` }}
                      title={`LiveBench Contribution: ${segLB.toFixed(1)} pts`}
                    />
                    <div
                      className="h-full bg-[#C84B31] transition-all"
                      style={{ width: `${segAR}%` }}
                      title={`Arena Elo Contribution: ${segAR.toFixed(1)} pts`}
                    />
                    <div
                      className="h-full bg-[#1F7A63] transition-all"
                      style={{ width: `${segVA}%` }}
                      title={`Vals Index Contribution: ${segVA.toFixed(1)} pts`}
                    />
                  </div>
                </div>

                <div className="col-span-2 text-right font-mono text-xs font-bold text-[#111317]">
                  {m.dynamicScore.toFixed(2)} pts
                </div>
              </div>
            );
          })}
        </div>

        <div className="border-t border-[#D8D4C8] bg-[#F4F2ED] px-4 py-2 font-mono text-[10px] text-[#68707C] flex justify-between">
          <span>Showing {topStackModels.length} models • Click any row to compare head-to-head</span>
          <span>Weights: {pctAA}% AA · {pctLB}% LiveBench · {pctAR}% Arena · {pctVA}% Vals</span>
        </div>
      </div>

      {/* Complete Evaluation Matrix Section */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#C84B31]">
                MODEL BENCHMARK LEADERBOARD
              </span>
            </div>
            <h2 className="font-display text-3xl font-normal text-[#111317]">
              Complete Benchmark Leaderboard &amp; Model Rankings
            </h2>
          </div>
          <p className="font-mono text-xs text-[#68707C]">
            Click <strong>Subtasks</strong> on any row to inspect 4-source metric breakdowns.
          </p>
        </div>

        {/* Filter & Search Bar — Including MiniMax in Provider Select */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-2 border-[#111317] bg-[#EBE8E0] p-3 shadow-[3px_3px_0_#111317]">
          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <input
              type="text"
              value={filterState.searchQuery}
              onChange={(e) => onFilterChange({ searchQuery: e.target.value })}
              placeholder="Search model, provider (e.g. MiniMax)..."
              className="w-64 border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-xs text-[#111317] placeholder-[#68707C] focus:border-[#C84B31] focus:outline-none"
            />

            {/* Provider Filter Select — Includes MiniMax */}
            <select
              value={filterState.providerFilter}
              onChange={(e) => onFilterChange({ providerFilter: e.target.value })}
              className="border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-xs text-[#111317] focus:border-[#C84B31] focus:outline-none"
            >
              <option value="ALL">All Providers ({allProviders.length} Labs)</option>
              {allProviders.map((prov) => (
                <option key={prov} value={prov}>
                  {prov}
                </option>
              ))}
            </select>

            {/* Effort Filter Select */}
            <select
              value={filterState.effortFilter}
              onChange={(e) => onFilterChange({ effortFilter: e.target.value })}
              className="border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-xs text-[#111317] focus:border-[#C84B31] focus:outline-none"
            >
              <option value="ALL">All Thinking Efforts</option>
              <option value="max">Max Effort</option>
              <option value="xhigh">xHigh Effort</option>
              <option value="high">High Effort</option>
              <option value="medium">Medium Effort</option>
              <option value="low">Low Effort</option>
              <option value="standard">Standard / Non-Reasoning</option>
            </select>

            {/* Open-Weights Toggle */}
            <button
              type="button"
              onClick={() => onFilterChange({ openWeightsOnly: !filterState.openWeightsOnly })}
              className={`border border-[#111317] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition ${
                filterState.openWeightsOnly
                  ? 'bg-[#1F7A63] text-white font-bold'
                  : 'bg-[#FFFFFF] text-[#373C44] hover:bg-[#111317] hover:text-white'
              }`}
            >
              Open-Weights
            </button>

            {/* Pareto Frontier Toggle */}
            <button
              type="button"
              onClick={() => onFilterChange({ paretoOnly: !filterState.paretoOnly })}
              className={`border border-[#111317] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition ${
                filterState.paretoOnly
                  ? 'bg-[#C84B31] text-white font-bold'
                  : 'bg-[#FFFFFF] text-[#373C44] hover:bg-[#111317] hover:text-white'
              }`}
            >
              Pareto Frontier
            </button>

            {/* Reset Filters */}
            {hasActiveFilters && (
              <button
                type="button"
                onClick={resetFilters}
                className="border border-[#C84B31] bg-[#FFFFFF] px-2.5 py-1.5 font-mono text-[11px] font-semibold text-[#C84B31] hover:bg-[#C84B31] hover:text-white"
              >
                Reset Filters
              </button>
            )}
          </div>

          <div className="font-mono text-xs font-semibold text-[#111317]">
            Showing {sortedModels.length} of {totalModelsCount} models
          </div>
        </div>

        {/* Master Data Table */}
        <div className="overflow-x-auto border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b-2 border-[#111317] bg-[#111317] font-mono text-[10px] font-semibold uppercase tracking-wider text-white">
                <th className="py-3 pl-4 pr-2">#</th>
                <th className="px-3 py-3">Model, Provider &amp; Effort</th>
                <th
                  onClick={() => handleHeaderSort('dynamicScore')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44] text-[#F4A261]"
                  title="Click to sort by Unified Quality Score"
                >
                  Unified Score {sortCol === 'dynamicScore' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('va')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by Vals Index"
                >
                  Vals Index {sortCol === 'va' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('aa')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by AA Intelligence Index"
                >
                  AA Intell. {sortCol === 'aa' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('lb')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by LiveBench Average"
                >
                  LiveBench {sortCol === 'lb' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('ar')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by Arena Text Elo"
                >
                  Arena Elo {sortCol === 'ar' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('price')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by Blended Price $/1M"
                >
                  Cost ($/1M) {sortCol === 'price' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleHeaderSort('speed')}
                  className="px-3 py-3 text-right cursor-pointer hover:bg-[#373C44]"
                  title="Click to sort by Output Speed"
                >
                  Speed {sortCol === 'speed' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="py-3 pl-2 pr-4 text-center">Compare / Drilldown</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D8D4C8]">
              {sortedModels.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center font-mono text-sm text-[#68707C]">
                    No models matched the active filter criteria. Click "Reset Filters" above.
                  </td>
                </tr>
              ) : (
                sortedModels.map((m, idx) => {
                  const isSelected = comparedIds.includes(m.id);
                  const isExpanded = expandedId === m.id;
                  const aa = m.benchmarks.artificial_analysis;
                  const lb = m.benchmarks.livebench;
                  const ar = m.benchmarks.arena;
                  const va = m.benchmarks.vals;
                  const effort = (m.thinking_effort || 'standard').toUpperCase();
                  const labStyle = getLabStyle(m.provider);

                  return (
                    <React.Fragment key={m.id}>
                      <tr className="transition hover:bg-[#F4F2ED]">
                        <td className="py-3 pl-4 pr-2 font-mono text-xs font-bold text-[#68707C]">
                          {String(idx + 1).padStart(3, '0')}
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span
                              className="inline-flex h-4 w-4 shrink-0 items-center justify-center font-mono text-[8px] font-bold"
                              style={{ backgroundColor: labStyle.badgeBg, color: labStyle.badgeText }}
                            >
                              {labStyle.short}
                            </span>
                            <span className="font-heading font-bold text-[#111317]">
                              {m.display_name}
                            </span>
                            <span className="border border-[#255C99] bg-[#255C99]/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#255C99]">
                              {effort}
                            </span>
                            {m.composite.sources_present < 4 && (
                              <span
                                className="border border-[#68707C] bg-[#EBE8E0] px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#373C44]"
                                title={`Evaluated on ${m.composite.sources_present} of 4 benchmark sources`}
                              >
                                {m.composite.sources_present}/4 SRC
                              </span>
                            )}
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
                          <div className="mt-0.5 font-mono text-[10px] text-[#68707C]">
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
                          {m.pricing.blended_per_1m_usd !== null
                            ? `$${m.pricing.blended_per_1m_usd.toFixed(2)}`
                            : '—'}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-[#373C44]">
                          {m.performance.output_tokens_per_sec !== null
                            ? `${m.performance.output_tokens_per_sec.toFixed(0)} t/s`
                            : '—'}
                        </td>
                        <td className="py-3 pl-2 pr-4 text-center">
                          <div className="inline-flex items-center gap-1.5 font-mono">
                            <button
                              type="button"
                              onClick={() => onToggleCompare(m.id)}
                              className={`border px-2 py-1 text-[10px] uppercase transition ${
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
                              <div className="border-l-4 border-[#1F7A63] bg-[#FFFFFF] p-3 shadow-sm">
                                <div className="font-bold uppercase text-[#1F7A63] mb-1">
                                  Vals Enterprise v2.2
                                </div>
                                {va ? (
                                  <div className="space-y-1 text-[#111317]">
                                    <div>Index: {va.vals_index}%</div>
                                    <div>Finance: {va.finance_agent}% • Legal: {va.legal_bench}%</div>
                                    <div>Tax: {va.tax_agent}% • Vibe Code: {va.vibe_code}%</div>
                                    <div>Cost/Test: {va.cost_per_test_usd !== null ? `$${va.cost_per_test_usd}` : '—'}</div>
                                  </div>
                                ) : (
                                  <div className="text-[#68707C]">Not evaluated</div>
                                )}
                              </div>
                              <div className="border-l-4 border-[#255C99] bg-[#FFFFFF] p-3 shadow-sm">
                                <div className="font-bold uppercase text-[#255C99] mb-1">
                                  Artificial Analysis v5.0
                                </div>
                                {aa ? (
                                  <div className="space-y-1 text-[#111317]">
                                    <div>Intell: {aa.intelligence_index}%</div>
                                    <div>Coding: {aa.coding_index}% • Math: {aa.math_index}%</div>
                                    <div>TTFT: {m.performance.ttft_seconds !== null ? `${m.performance.ttft_seconds}s` : '—'}</div>
                                    <div>
                                      In/Out:{' '}
                                      {m.pricing.input_per_1m_usd !== null && m.pricing.output_per_1m_usd !== null
                                        ? `$${m.pricing.input_per_1m_usd}/$${m.pricing.output_per_1m_usd}`
                                        : '—'}
                                    </div>
                                  </div>
                                ) : (
                                  <div className="text-[#68707C]">Not evaluated</div>
                                )}
                              </div>
                              <div className="border-l-4 border-[#C57B18] bg-[#FFFFFF] p-3 shadow-sm">
                                <div className="font-bold uppercase text-[#C57B18] mb-1">
                                  LiveBench Subtasks
                                </div>
                                {lb ? (
                                  <div className="space-y-1 text-[#111317]">
                                    <div>Global Avg: {lb.global_average}%</div>
                                    <div>Coding: {lb.coding}% • Agentic: {lb.agentic_coding}%</div>
                                    <div>Reasoning: {lb.reasoning}% • IF: {lb.instruction_following}%</div>
                                    <div>Math: {lb.mathematics}% • Data: {lb.data_analysis}%</div>
                                  </div>
                                ) : (
                                  <div className="text-[#68707C]">Not evaluated</div>
                                )}
                              </div>
                              <div className="border-l-4 border-[#C84B31] bg-[#FFFFFF] p-3 shadow-sm">
                                <div className="font-bold uppercase text-[#C84B31] mb-1">
                                  Arena.ai Crowd-BT
                                </div>
                                {ar ? (
                                  <div className="space-y-1 text-[#111317]">
                                    <div>
                                      Text Elo: {ar.text_elo} ({ar.text_ci_lower}–{ar.text_ci_upper})
                                    </div>
                                    <div>Coding Elo: {ar.coding_elo}</div>
                                    {ar.vision_elo && <div>Vision Elo: {ar.vision_elo}</div>}
                                    <div>Votes: {ar.votes.toLocaleString()}</div>
                                  </div>
                                ) : (
                                  <div className="text-[#68707C]">Not evaluated</div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
