import React, { useEffect, useMemo, useState } from 'react';
import { loadUnifiedBenchmarkData } from './lib/dataLoader';
import { UnifiedDataset } from './lib/schema';
import { computeDynamicCompositeScore, recomputeParetoFlags } from './lib/scoring';
import { useUrlFilterState } from './hooks/useUrlFilterState';
import { SourceAttributionBar } from './components/SourceAttributionBar';
import { WeightMixer } from './components/WeightMixer';
import { LeaderboardTable, ScoredModelEntry } from './components/LeaderboardTable';
import { ParetoChart } from './components/ParetoChart';
import { ModelComparisonModal } from './components/ModelComparisonModal';
import { ReleaseTimelinePage } from './components/ReleaseTimelinePage';

export const App: React.FC = () => {
  const [payload, setPayload] = useState<UnifiedDataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { state, setState } = useUrlFilterState();

  useEffect(() => {
    loadUnifiedBenchmarkData()
      .then(setPayload)
      .catch((err: Error) => setError(err.message));
  }, []);

  const allProviders = useMemo(() => {
    if (!payload) return [];
    return Array.from(new Set(payload.models.map((m) => m.provider))).sort();
  }, [payload]);

  // All models with dynamic scores and dynamic Pareto frontier flags
  const allScoredModels: ScoredModelEntry[] = useMemo(() => {
    if (!payload) return [];
    const list = payload.models.map((m) => ({
      ...m,
      dynamicScore:
        computeDynamicCompositeScore(m.normalized_pillars, state.weights) ||
        m.composite.unified_quality_score,
      isDynamicPareto: false,
    }));

    const paretoFlags = recomputeParetoFlags(
      list.map((m) => ({
        id: m.id,
        score: m.dynamicScore,
        blendedPrice: m.pricing.blended_per_1m_usd,
        provisional: Boolean(m.composite.provisional_ranking),
      }))
    );

    return list.map((m) => ({ ...m, isDynamicPareto: Boolean(paretoFlags[m.id]) }));
  }, [payload, state.weights]);

  // Models filtered according to search, provider, effort, and flags
  const filteredModels: ScoredModelEntry[] = useMemo(() => {
    return allScoredModels
      .filter((m) => {
        if (state.openWeightsOnly && !m.is_open_weights) return false;
        if (state.paretoOnly && !m.isDynamicPareto) return false;
        if (state.providerFilter !== 'ALL' && m.provider !== state.providerFilter) return false;
        if (state.effortFilter !== 'ALL' && (m.thinking_effort || 'standard') !== state.effortFilter)
          return false;
        if (state.searchQuery) {
          const q = state.searchQuery.toLowerCase();
          const target = `${m.display_name} ${m.provider} ${m.thinking_effort || ''} ${m.license}`.toLowerCase();
          if (!target.includes(q)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const provA = Boolean(a.composite.provisional_ranking);
        const provB = Boolean(b.composite.provisional_ranking);
        if (provA !== provB) return provA ? 1 : -1;
        return b.dynamicScore - a.dynamicScore;
      });
  }, [allScoredModels, state]);

  const comparedModels = useMemo(
    () => allScoredModels.filter((m) => state.comparedModelIds.includes(m.id)),
    [allScoredModels, state.comparedModelIds]
  );

  const toggleCompare = (modelId: string) => {
    setState((prev) => {
      const exists = prev.comparedModelIds.includes(modelId);
      const next = exists
        ? prev.comparedModelIds.filter((id) => id !== modelId)
        : [...prev.comparedModelIds.slice(-3), modelId];
      return { ...prev, comparedModelIds: next };
    });
  };

  if (error) {
    return <div className="p-8 text-[#C84B31]">Failed to load benchmark data: {error}</div>;
  }
  if (!payload) {
    return (
      <div className="p-8 font-mono text-xs text-[#68707C]">
        Loading benchmarks...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F4F2ED] text-[#111317]">
      <SourceAttributionBar metadata={payload.sources_metadata} generatedAt={payload.generated_at} />
      <header className="sticky top-0 z-30 border-b-2 border-[#111317] bg-[#F4F2ED]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 px-3 py-2 sm:px-6 sm:py-3">
          <button
            type="button"
            onClick={() => setState((prev) => ({ ...prev, activePage: 'leaderboard' }))}
            className="flex shrink-0 items-center gap-2 sm:gap-3 text-left"
          >
            <div className="grid h-6 w-6 sm:h-7 sm:w-7 grid-cols-2 grid-rows-2 gap-0.5 border-2 border-[#111317] bg-[#111317] p-0.5">
              <span className="bg-[#255C99]" />
              <span className="bg-[#C57B18]" />
              <span className="bg-[#C84B31]" />
              <span className="bg-[#1F7A63]" />
            </div>
            <span className="font-heading text-sm sm:text-lg font-bold tracking-tight text-[#111317]">
              OMNIBENCH
            </span>
          </button>

          <div className="flex items-center gap-2 sm:gap-4">
            <span className="hidden font-mono text-[11px] uppercase tracking-wider text-[#68707C] lg:inline">
              {payload.models.length} Models · {allProviders.length} Labs
            </span>

            <nav
              className="inline-flex items-center border-2 border-[#111317] bg-[#FFFFFF] font-mono text-[10px] sm:text-[11px] font-bold uppercase tracking-wider shadow-[2px_2px_0_#111317]"
              aria-label="Primary page navigation"
            >
              <button
                id="nav-leaderboard"
                type="button"
                aria-current={state.activePage === 'leaderboard' ? 'page' : undefined}
                onClick={() => setState((prev) => ({ ...prev, activePage: 'leaderboard' }))}
                className={`px-2 py-1 sm:px-3 sm:py-1.5 uppercase transition whitespace-nowrap ${
                  state.activePage === 'leaderboard'
                    ? 'bg-[#111317] text-white'
                    : 'bg-[#FFFFFF] text-[#111317] hover:bg-[#EBE8E0]'
                }`}
              >
                Leaderboard
              </button>
              <button
                id="nav-release-timeline"
                type="button"
                aria-current={state.activePage === 'timeline' ? 'page' : undefined}
                onClick={() => setState((prev) => ({ ...prev, activePage: 'timeline' }))}
                className={`border-l-2 border-[#111317] px-2 py-1 sm:px-3 sm:py-1.5 uppercase transition whitespace-nowrap ${
                  state.activePage === 'timeline'
                    ? 'bg-[#C84B31] text-white'
                    : 'bg-[#FFFFFF] text-[#111317] hover:bg-[#EBE8E0]'
                }`}
              >
                Release Timeline
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 sm:space-y-10 px-3 py-5 sm:px-6 sm:py-8">
        {state.activePage === 'timeline' ? (
          <ReleaseTimelinePage
            models={allScoredModels}
            allProviders={allProviders}
            onBackToLeaderboard={() => setState((prev) => ({ ...prev, activePage: 'leaderboard' }))}
          />
        ) : (
          <>
            <section className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]">
              <div className="p-4 sm:p-6 bg-[#F4F2ED]">
                <div className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#C84B31]">
                  COMPOSITE BENCHMARK INDEX
                </div>
                <h1 className="mt-1 font-display text-2xl sm:text-5xl font-normal leading-tight text-[#111317]">
                  Four Independent Benchmarks. One Weighted Frontier.
                </h1>
                <p className="mt-2 sm:mt-3 max-w-3xl text-xs sm:text-sm leading-relaxed text-[#373C44]">
                  OmniBench aggregates Artificial Analysis, LiveBench 2.0, Arena.ai, and Vals.ai across{' '}
                  {payload.models.length} models and thinking effort tiers into a calibrated 0–100 quality score.
                </p>
              </div>
              <WeightMixer
                weights={state.weights}
                onChange={(weights) => setState((prev) => ({ ...prev, weights }))}
              />
            </section>

            {/* Pareto Chart with Frontier Line, Log/Linear Scale Switcher, and Lab Palette */}
            <ParetoChart
              models={allScoredModels}
              selectedProvider={state.providerFilter}
              onSelectProvider={(provider) => setState((prev) => ({ ...prev, providerFilter: provider }))}
              scaleMode={state.paretoScale}
              onScaleModeChange={(paretoScale) => setState((prev) => ({ ...prev, paretoScale }))}
            />

            {/* Head-to-Head Comparison Drawer */}
            <ModelComparisonModal models={comparedModels} onRemove={toggleCompare} />

            {/* Model Leaderboard & Stacked Contribution Table */}
            <LeaderboardTable
              models={filteredModels}
              totalModelsCount={payload.models.length}
              allProviders={allProviders}
              filterState={state}
              onFilterChange={(patch) => setState((prev) => ({ ...prev, ...patch }))}
              comparedIds={state.comparedModelIds}
              onToggleCompare={toggleCompare}
            />
          </>
        )}
      </main>
    </div>
  );
};

export default App;
