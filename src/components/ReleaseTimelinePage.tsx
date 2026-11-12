import React, { useMemo, useState } from 'react';
import { ScoredModelEntry } from './LeaderboardTable';
import { getLabStyle } from '../lib/labPalette';

interface Props {
  models: ScoredModelEntry[];
  allProviders: string[];
  onBackToLeaderboard: () => void;
}

interface TimelineReleaseGroup {
  key: string;
  baseName: string;
  provider: string;
  releaseDate: string;
  isOpenWeights: boolean;
  license: string;
  contextWindow: number;
  isPareto: boolean;
  topModel: ScoredModelEntry;
  variants: ScoredModelEntry[];
}

const EFFORT_SUFFIX_RE =
  /\s*\((?:max|xhigh|high|medium|low|minimal|none|non-reasoning|standard|reasoning|thinking)\)\s*$/i;

function getBaseModelName(displayName: string): string {
  return displayName.replace(EFFORT_SUFFIX_RE, '').trim();
}

function formatHumanDate(isoDate: string): string {
  const parts = isoDate.split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return isoDate;
  const [year, month, day] = parts;
  const dateObj = new Date(Date.UTC(year, month - 1, day));
  return dateObj.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function formatMonthLabel(yearMonth: string): string {
  const parts = yearMonth.split('-').map(Number);
  if (parts.length !== 2 || parts.some(Number.isNaN)) return yearMonth;
  const [year, month] = parts;
  const dateObj = new Date(Date.UTC(year, month - 1, 1));
  return dateObj.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function formatShortMonth(yearMonth: string): string {
  const parts = yearMonth.split('-').map(Number);
  if (parts.length !== 2 || parts.some(Number.isNaN)) return yearMonth;
  const [year, month] = parts;
  const dateObj = new Date(Date.UTC(year, month - 1, 1));
  return dateObj.toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}

export const ReleaseTimelinePage: React.FC<Props> = ({
  models,
  allProviders,
  onBackToLeaderboard,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [providerFilter, setProviderFilter] = useState<string>('ALL');
  const [monthFilter, setMonthFilter] = useState<string>('ALL');
  const [openWeightsOnly, setOpenWeightsOnly] = useState<boolean>(false);
  const [paretoOnly, setParetoOnly] = useState<boolean>(false);
  const [groupVariants, setGroupVariants] = useState<boolean>(true);
  const [newestFirst, setNewestFirst] = useState<boolean>(true);

  // Build release items (either grouped by base model + release date, or individual variants)
  const allReleaseItems: TimelineReleaseGroup[] = useMemo(() => {
    const nonProv = models.filter((m) => !m.composite.provisional_ranking);

    if (!groupVariants) {
      return nonProv.map((m) => ({
        key: m.id,
        baseName: m.display_name,
        provider: m.provider,
        releaseDate: m.release_date,
        isOpenWeights: m.is_open_weights,
        license: m.license,
        contextWindow: m.context_window,
        isPareto: m.isDynamicPareto,
        topModel: m,
        variants: [m],
      }));
    }

    const map = new Map<string, ScoredModelEntry[]>();
    for (const m of nonProv) {
      const base = getBaseModelName(m.display_name);
      const groupKey = `${m.provider}::${base.toLowerCase()}::${m.release_date}`;
      const list = map.get(groupKey) ?? [];
      list.push(m);
      map.set(groupKey, list);
    }

    const groups: TimelineReleaseGroup[] = [];
    for (const [key, list] of map.entries()) {
      const sorted = [...list].sort((a, b) => b.dynamicScore - a.dynamicScore);
      const top = sorted[0];
      const baseName = list.length > 1 ? getBaseModelName(top.display_name) : top.display_name;
      groups.push({
        key,
        baseName,
        provider: top.provider,
        releaseDate: top.release_date,
        isOpenWeights: sorted.some((v) => v.is_open_weights),
        license: top.license,
        contextWindow: Math.max(...sorted.map((v) => v.context_window)),
        isPareto: sorted.some((v) => v.isDynamicPareto),
        topModel: top,
        variants: sorted,
      });
    }
    return groups;
  }, [models, groupVariants]);

  // Monthly counts for the cadence bar strip (computed before monthFilter so user can switch months)
  const monthlyCadence = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of allReleaseItems) {
      if (openWeightsOnly && !item.isOpenWeights) continue;
      if (paretoOnly && !item.isPareto) continue;
      if (providerFilter !== 'ALL' && item.provider !== providerFilter) continue;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const target = `${item.baseName} ${item.provider} ${item.license} ${item.releaseDate}`.toLowerCase();
        if (!target.includes(q)) continue;
      }
      const ym = item.releaseDate.slice(0, 7);
      counts.set(ym, (counts.get(ym) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([ym, count]) => ({ ym, count }))
      .sort((a, b) => (newestFirst ? b.ym.localeCompare(a.ym) : a.ym.localeCompare(b.ym)));
  }, [allReleaseItems, openWeightsOnly, paretoOnly, providerFilter, searchQuery, newestFirst]);

  // Filtered and sorted release items
  const filteredReleases = useMemo(() => {
    return allReleaseItems
      .filter((item) => {
        if (openWeightsOnly && !item.isOpenWeights) return false;
        if (paretoOnly && !item.isPareto) return false;
        if (providerFilter !== 'ALL' && item.provider !== providerFilter) return false;
        if (monthFilter !== 'ALL' && item.releaseDate.slice(0, 7) !== monthFilter) return false;
        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          const target = `${item.baseName} ${item.provider} ${item.license} ${item.releaseDate}`.toLowerCase();
          if (!target.includes(q)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const dateCmp = newestFirst
          ? b.releaseDate.localeCompare(a.releaseDate)
          : a.releaseDate.localeCompare(b.releaseDate);
        if (dateCmp !== 0) return dateCmp;
        return b.topModel.dynamicScore - a.topModel.dynamicScore;
      });
  }, [allReleaseItems, openWeightsOnly, paretoOnly, providerFilter, monthFilter, searchQuery, newestFirst]);

  // Group filtered releases by Month -> Date
  const groupedByMonth = useMemo(() => {
    const months: Array<{
      yearMonth: string;
      totalReleases: number;
      dates: Array<{
        releaseDate: string;
        items: TimelineReleaseGroup[];
      }>;
    }> = [];

    for (const item of filteredReleases) {
      const ym = item.releaseDate.slice(0, 7);
      let monthBucket = months[months.length - 1];
      if (!monthBucket || monthBucket.yearMonth !== ym) {
        monthBucket = { yearMonth: ym, totalReleases: 0, dates: [] };
        months.push(monthBucket);
      }
      monthBucket.totalReleases += 1;

      let dateBucket = monthBucket.dates[monthBucket.dates.length - 1];
      if (!dateBucket || dateBucket.releaseDate !== item.releaseDate) {
        dateBucket = { releaseDate: item.releaseDate, items: [] };
        monthBucket.dates.push(dateBucket);
      }
      dateBucket.items.push(item);
    }

    return months;
  }, [filteredReleases]);

  const hasActiveFilters =
    Boolean(searchQuery) ||
    providerFilter !== 'ALL' ||
    monthFilter !== 'ALL' ||
    openWeightsOnly ||
    paretoOnly;

  const resetFilters = () => {
    setSearchQuery('');
    setProviderFilter('ALL');
    setMonthFilter('ALL');
    setOpenWeightsOnly(false);
    setParetoOnly(false);
  };

  return (
    <div className="space-y-8">
      {/* Page Hero Card */}
      <section className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-[#111317] bg-[#F4F2ED] p-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#C84B31]">
                MODEL RELEASE TIMELINE
              </span>
            </div>
            <h1 className="mt-1 font-display text-4xl font-normal leading-tight text-[#111317] sm:text-5xl">
              Model Release Timeline
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[#373C44]">
              A chronological view of when each frontier and open-weights AI model was released across{' '}
              {allProviders.length} research labs, paired with its quality score and token pricing.
            </p>
          </div>

          <button
            id="back-to-leaderboard-btn"
            type="button"
            onClick={onBackToLeaderboard}
            className="border-2 border-[#111317] bg-[#FFFFFF] px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-[#111317] shadow-[2px_2px_0_#111317] transition hover:bg-[#111317] hover:text-white"
          >
            ← Back to Leaderboard
          </button>
        </div>

        {/* Filter & Controls Strip */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-[#EBE8E0] px-5 py-3.5">
          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <input
              id="timeline-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search model, lab, or date (e.g. 2026-10)..."
              className="w-64 border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-xs text-[#111317] placeholder-[#68707C] focus:border-[#C84B31] focus:outline-none"
            />

            {/* Lab Filter Select */}
            <select
              id="timeline-provider-select"
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-xs text-[#111317] focus:border-[#C84B31] focus:outline-none"
            >
              <option value="ALL">All Labs ({allProviders.length})</option>
              {allProviders.map((prov) => (
                <option key={prov} value={prov}>
                  {prov}
                </option>
              ))}
            </select>

            {/* Group Multi-Effort Toggle */}
            <button
              id="timeline-group-variants-btn"
              type="button"
              onClick={() => setGroupVariants(!groupVariants)}
              className={`border border-[#111317] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition ${
                groupVariants
                  ? 'bg-[#111317] font-bold text-white'
                  : 'bg-[#FFFFFF] text-[#373C44] hover:bg-[#111317] hover:text-white'
              }`}
              title="Group multi-effort variants released on the same day into a single model card"
            >
              {groupVariants ? 'Grouped by Release' : 'All Effort Variants'}
            </button>

            {/* Open-Weights Toggle */}
            <button
              id="timeline-open-weights-btn"
              type="button"
              onClick={() => setOpenWeightsOnly(!openWeightsOnly)}
              className={`border border-[#111317] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition ${
                openWeightsOnly
                  ? 'bg-[#1F7A63] font-bold text-white'
                  : 'bg-[#FFFFFF] text-[#373C44] hover:bg-[#111317] hover:text-white'
              }`}
            >
              Open-Weights
            </button>

            {/* Pareto Frontier Toggle */}
            <button
              id="timeline-pareto-btn"
              type="button"
              onClick={() => setParetoOnly(!paretoOnly)}
              className={`border border-[#111317] px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition ${
                paretoOnly
                  ? 'bg-[#C84B31] font-bold text-white'
                  : 'bg-[#FFFFFF] text-[#373C44] hover:bg-[#111317] hover:text-white'
              }`}
            >
              Pareto Frontier
            </button>

            {/* Sort Order Toggle */}
            <button
              id="timeline-sort-order-btn"
              type="button"
              onClick={() => setNewestFirst(!newestFirst)}
              className="border border-[#111317] bg-[#FFFFFF] px-3 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-[#111317] transition hover:bg-[#111317] hover:text-white"
            >
              {newestFirst ? 'Newest First ↓' : 'Oldest First ↑'}
            </button>

            {hasActiveFilters && (
              <button
                id="timeline-reset-btn"
                type="button"
                onClick={resetFilters}
                className="border border-[#C84B31] bg-[#FFFFFF] px-2.5 py-1.5 font-mono text-[11px] font-semibold text-[#C84B31] hover:bg-[#C84B31] hover:text-white"
              >
                Reset
              </button>
            )}
          </div>

          <div className="font-mono text-xs font-semibold text-[#111317]">
            Showing {filteredReleases.length} {groupVariants ? 'releases' : 'model variants'}
          </div>
        </div>

        {/* Monthly Release Cadence Strip */}
        {monthlyCadence.length > 0 && (
          <div className="border-t border-[#D8D4C8] bg-[#FDFCFB] px-5 py-3">
            <div className="mb-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-[#68707C]">
              <span>Monthly Release Cadence (Click month to filter)</span>
              {monthFilter !== 'ALL' && (
                <button
                  type="button"
                  onClick={() => setMonthFilter('ALL')}
                  className="font-bold text-[#C84B31] hover:underline"
                >
                  Clear Month Filter ({monthFilter})
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {monthlyCadence.map(({ ym, count }) => {
                const isSelected = monthFilter === ym;
                return (
                  <button
                    key={ym}
                    type="button"
                    onClick={() => setMonthFilter(isSelected ? 'ALL' : ym)}
                    className={`inline-flex items-center gap-1.5 border px-2 py-1 font-mono text-[10px] transition ${
                      isSelected
                        ? 'border-[#111317] bg-[#C84B31] font-bold text-white'
                        : 'border-[#D8D4C8] bg-[#F4F2ED] text-[#111317] hover:border-[#111317] hover:bg-[#EBE8E0]'
                    }`}
                  >
                    <span>{formatShortMonth(ym)}</span>
                    <span
                      className={`px-1 text-[9px] font-bold ${
                        isSelected ? 'bg-[#111317] text-white' : 'bg-[#FFFFFF] text-[#68707C]'
                      }`}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

      {/* Chronological Timeline Stream */}
      {groupedByMonth.length === 0 ? (
        <div className="border-2 border-[#111317] bg-[#FFFFFF] p-12 text-center font-mono text-sm text-[#68707C] shadow-[4px_4px_0_#111317]">
          No model releases matched your filter criteria. Click &ldquo;Reset&rdquo; above to view all releases.
        </div>
      ) : (
        <div className="space-y-8">
          {groupedByMonth.map((monthGroup) => (
            <section
              key={monthGroup.yearMonth}
              className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]"
            >
              {/* Month Sticky Header */}
              <div className="flex items-center justify-between border-b-2 border-[#111317] bg-[#111317] px-5 py-3 font-mono text-xs text-white">
                <div className="flex items-center gap-2.5">
                  <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
                  <h2 className="font-heading text-sm font-bold uppercase tracking-wider text-white">
                    {formatMonthLabel(monthGroup.yearMonth)}
                  </h2>
                </div>
                <span className="border border-[#D8D4C8]/40 bg-[#FFFFFF]/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#EBE8E0]">
                  {monthGroup.totalReleases} {monthGroup.totalReleases === 1 ? 'Release' : 'Releases'}
                </span>
              </div>

              {/* Vertical Timeline Rail inside Month */}
              <div className="divide-y divide-[#EBE8E0] p-5">
                {monthGroup.dates.map((dateBucket) => (
                  <div
                    key={dateBucket.releaseDate}
                    className="grid grid-cols-1 gap-4 py-4 first:pt-0 last:pb-0 md:grid-cols-12"
                  >
                    {/* Left Date Column */}
                    <div className="md:col-span-3 lg:col-span-2">
                      <div className="inline-flex items-center gap-2 md:flex-col md:items-start md:gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <span className="h-2 w-2 rounded-full bg-[#C84B31]" />
                          <span className="font-mono text-xs font-bold text-[#111317]">
                            {formatHumanDate(dateBucket.releaseDate)}
                          </span>
                        </div>
                        <span className="font-mono text-[10px] text-[#68707C] md:pl-3.5">
                          {dateBucket.releaseDate}
                        </span>
                      </div>
                    </div>

                    {/* Right Models Released on Date */}
                    <div className="space-y-2.5 border-l-2 border-[#111317] pl-4 md:col-span-9 lg:col-span-10">
                      {dateBucket.items.map((item) => {
                        const labStyle = getLabStyle(item.provider);
                        const m = item.topModel;
                        const maxSources = Math.max(
                          ...item.variants.map((v) => v.composite.sources_present)
                        );
                        const efforts = Array.from(
                          new Set(item.variants.map((v) => (v.thinking_effort || 'standard').toUpperCase()))
                        );

                        return (
                          <div
                            key={item.key}
                            className="flex flex-col justify-between gap-3 border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3.5 transition hover:border-[#111317] hover:bg-[#F4F2ED] sm:flex-row sm:items-center"
                          >
                            <div className="min-w-0 space-y-1">
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span
                                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center font-mono text-[9px] font-bold"
                                  style={{ backgroundColor: labStyle.badgeBg, color: labStyle.badgeText }}
                                >
                                  {labStyle.short}
                                </span>
                                <span className="font-heading text-sm font-bold text-[#111317]">
                                  {item.baseName}
                                </span>
                                {maxSources < 4 && (
                                  <span
                                    className="border border-[#68707C] bg-[#EBE8E0] px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#373C44]"
                                    title={`Evaluated on ${maxSources} of 4 benchmark sources`}
                                  >
                                    {maxSources}/4 SRC
                                  </span>
                                )}
                                {item.isPareto && (
                                  <span className="border border-[#C84B31] bg-[#C84B31]/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-[#C84B31]">
                                    PARETO
                                  </span>
                                )}
                                {item.isOpenWeights && (
                                  <span className="border border-[#1F7A63] bg-[#1F7A63]/10 px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase text-[#1F7A63]">
                                    OPEN
                                  </span>
                                )}
                              </div>

                              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] text-[#68707C]">
                                <span className="font-semibold text-[#373C44]">{item.provider}</span>
                                <span>•</span>
                                <span>{(item.contextWindow / 1000).toFixed(0)}k ctx</span>
                                <span>•</span>
                                <span>{item.license}</span>
                                <span>•</span>
                                <span className="inline-flex flex-wrap items-center gap-1">
                                  {efforts.map((eff) => (
                                    <span
                                      key={eff}
                                      className="border border-[#255C99]/40 bg-[#255C99]/10 px-1 py-0.2 text-[9px] font-semibold text-[#255C99]"
                                    >
                                      {eff}
                                    </span>
                                  ))}
                                </span>
                              </div>
                            </div>

                            {/* Right Score & Pricing Overview */}
                            <div className="flex shrink-0 items-center gap-4 border-t border-[#D8D4C8] pt-2 font-mono sm:border-t-0 sm:pt-0">
                              <div className="text-left sm:text-right">
                                <div className="text-[9px] uppercase tracking-wider text-[#68707C]">
                                  Blended Cost
                                </div>
                                <div className="text-xs font-semibold text-[#111317]">
                                  {m.pricing.blended_per_1m_usd !== null
                                    ? `$${m.pricing.blended_per_1m_usd.toFixed(2)}/1M`
                                    : '—'}
                                </div>
                              </div>

                              <div className="border-l border-[#D8D4C8] pl-4 text-left sm:text-right">
                                <div className="text-[9px] uppercase tracking-wider text-[#68707C]">
                                  {item.variants.length > 1 ? 'Top Score' : 'Unified Score'}
                                </div>
                                <div className="text-sm font-bold text-[#C84B31]">
                                  {m.dynamicScore.toFixed(2)} pts
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
};
