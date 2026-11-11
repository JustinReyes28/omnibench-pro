import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ScoredModelEntry } from './LeaderboardTable';
import { getLabStyle } from '../lib/labPalette';
import { ParetoScaleMode } from '../hooks/useUrlFilterState';

interface Props {
  models: ScoredModelEntry[];
  selectedProvider?: string;
  onSelectProvider?: (provider: string) => void;
  scaleMode?: ParetoScaleMode;
  onScaleModeChange?: (mode: ParetoScaleMode) => void;
}

const CHART_HEIGHT = 420;
const MARGIN = { top: 32, right: 36, bottom: 58, left: 64 };

const COLOR_INK = '#111317';
const COLOR_GRID = '#D8D4C8';
const COLOR_FRONTIER = '#C84B31';

/** Candidate log-scale and linear-scale tick values in $/1M tokens */
const LOG_X_TICKS = [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 25];
const LINEAR_X_TICKS = [0, 5, 10, 15, 20, 25, 30, 35];
const Y_TICKS = [30, 50, 70, 90, 100];

const formatPrice = (price: number) => {
  if (price === 0) return '$0';
  if (price >= 1) return `$${price.toFixed(price % 1 === 0 ? 0 : 2)}`;
  return `$${price.toFixed(2)}`;
};

const FEATURED_LABS = [
  'OpenAI',
  'Anthropic',
  'Google',
  'DeepSeek',
  'Meta',
  'Moonshot AI',
  'Alibaba',
  'MiniMax',
  'Xiaomi',
  'Z.AI',
  'xAI',
  'Mistral AI',
];

export const ParetoChart: React.FC<Props> = ({
  models,
  selectedProvider,
  onSelectProvider,
  scaleMode,
  onScaleModeChange,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(900);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [internalScale, setInternalScale] = useState<ParetoScaleMode>('log');

  const activeScale: ParetoScaleMode = scaleMode ?? internalScale;
  const handleScaleChange = (next: ParetoScaleMode) => {
    setInternalScale(next);
    onScaleModeChange?.(next);
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const updateWidth = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) setContainerWidth(rect.width);
    };
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const priced = useMemo(
    () =>
      models.filter(
        (m): m is ScoredModelEntry & { pricing: { blended_per_1m_usd: number } } =>
          m.pricing.blended_per_1m_usd !== null &&
          m.pricing.blended_per_1m_usd > 0 &&
          !m.composite.provisional_ranking
      ),
    [models]
  );

  // Frontier points ordered by ascending price
  const frontier = useMemo(
    () =>
      priced
        .filter((m) => m.isDynamicPareto)
        .sort((a, b) => a.pricing.blended_per_1m_usd - b.pricing.blended_per_1m_usd),
    [priced]
  );

  const minLogX = Math.log10(0.045);
  const maxLogX = Math.log10(35.0);
  const minLinX = 0;
  const maxLinX = 35.0;
  const minY = 20;
  const maxY = 104;

  const plotW = Math.max(280, containerWidth - MARGIN.left - MARGIN.right);
  const plotH = CHART_HEIGHT - MARGIN.top - MARGIN.bottom;

  const activeXTicks = activeScale === 'linear' ? LINEAR_X_TICKS : LOG_X_TICKS;

  const toX = (price: number) => {
    if (activeScale === 'linear') {
      const clamped = Math.max(minLinX, Math.min(maxLinX, price));
      return MARGIN.left + ((clamped - minLinX) / (maxLinX - minLinX)) * plotW;
    }
    const lx = Math.log10(Math.max(0.045, Math.min(35.0, price)));
    return MARGIN.left + ((lx - minLogX) / (maxLogX - minLogX)) * plotW;
  };

  const toY = (score: number) => {
    const clamped = Math.max(minY, Math.min(maxY, score));
    return MARGIN.top + plotH - ((clamped - minY) / (maxY - minY)) * plotH;
  };

  // Build the frontier SVG path (connecting Pareto models from lowest cost to highest score)
  const frontierLinePath = useMemo(() => {
    if (frontier.length === 0) return '';
    return frontier
      .map((m, i) => {
        const x = toX(m.pricing.blended_per_1m_usd);
        const y = toY(m.dynamicScore);
        return i === 0 ? `M ${x.toFixed(1)} ${y.toFixed(1)}` : `L ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');
  }, [frontier, plotW, plotH, activeScale]);

  // Build the shaded efficiency hull under the frontier line
  const frontierHullPath = useMemo(() => {
    if (frontier.length < 2) return '';
    const bottomY = (MARGIN.top + plotH).toFixed(1);
    const firstX = toX(frontier[0].pricing.blended_per_1m_usd).toFixed(1);
    const lastX = toX(frontier[frontier.length - 1].pricing.blended_per_1m_usd).toFixed(1);

    const linePoints = frontier
      .map((m) => `${toX(m.pricing.blended_per_1m_usd).toFixed(1)} ${toY(m.dynamicScore).toFixed(1)}`)
      .join(' L ');

    return `M ${firstX} ${bottomY} L ${linePoints} L ${lastX} ${bottomY} Z`;
  }, [frontier, plotW, plotH, activeScale]);

  // Compute collision-free frontier label positions for both Log and Linear scale modes
  const frontierWithLabels = useMemo(() => {
    const items = frontier.map((m, idx) => {
      const cx = toX(m.pricing.blended_per_1m_usd);
      const cy = toY(m.dynamicScore);
      const flipLeft = cx > MARGIN.left + plotW - 140;
      let labelY = cy + (idx % 2 === 0 ? -8 : 14);
      let labelX = flipLeft ? cx - 12 : cx + 12;
      let anchor: 'start' | 'end' = flipLeft ? 'end' : 'start';

      if (activeScale === 'log') {
        if (m.display_name.includes('Gemini 4 Carbon')) {
          labelY = cy - 10;
          labelX = cx - 4;
          anchor = 'end';
        } else if (m.display_name.includes('Claude Sonnet 5.5')) {
          labelY = cy + 14;
          labelX = cx + 8;
          anchor = 'start';
        }
      } else {
        labelY = cy + 3;
      }

      return { m, cx, cy, labelX, labelY, anchor };
    });

    // Resolve vertical overlaps top-to-bottom when labels are horizontally proximate
    const byTop = [...items].sort((a, b) => a.cy - b.cy);
    const placed: Array<{ x: number; y: number }> = [];
    for (const item of byTop) {
      let y = Math.max(MARGIN.top + 8, Math.min(MARGIN.top + plotH - 6, item.labelY));
      for (const prev of placed) {
        if (Math.abs(item.labelX - prev.x) < 155 && Math.abs(y - prev.y) < 12) {
          y = Math.min(MARGIN.top + plotH - 4, prev.y + 12.5);
        }
      }
      item.labelY = y;
      placed.push({ x: item.labelX, y });
    }

    return items;
  }, [frontier, plotW, plotH, activeScale]);

  const hoveredModel = useMemo(
    () => (hoveredId ? priced.find((m) => m.id === hoveredId) ?? null : null),
    [hoveredId, priced]
  );

  return (
    <div className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]">
      {/* Chart Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-[#111317] bg-[#F4F2ED] px-5 py-3.5">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-[#C84B31]">
              // PARETO EFFICIENCY OBSERVATORY
            </span>
          </div>
          <h3 className="mt-0.5 font-heading text-lg font-bold text-[#111317]">
            Blended Token Price ($/1M {activeScale === 'log' ? 'Log' : 'Linear'}) vs. Unified Quality
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Log / Linear Scale Switcher */}
          <div
            className="inline-flex items-center border-2 border-[#111317] bg-[#FFFFFF] font-mono text-[10px] font-bold uppercase tracking-wider shadow-[2px_2px_0_#111317]"
            role="group"
            aria-label="Pareto X-axis scale mode"
          >
            <span className="border-r border-[#D8D4C8] bg-[#EBE8E0] px-2 py-1 text-[#68707C]">
              X-Scale
            </span>
            <button
              id="pareto-scale-log"
              type="button"
              aria-pressed={activeScale === 'log'}
              onClick={() => handleScaleChange('log')}
              className={`px-2.5 py-1 uppercase transition ${
                activeScale === 'log'
                  ? 'bg-[#111317] text-white'
                  : 'bg-[#FFFFFF] text-[#111317] hover:bg-[#EBE8E0]'
              }`}
            >
              Log
            </button>
            <button
              id="pareto-scale-linear"
              type="button"
              aria-pressed={activeScale === 'linear'}
              onClick={() => handleScaleChange('linear')}
              className={`border-l border-[#111317] px-2.5 py-1 uppercase transition ${
                activeScale === 'linear'
                  ? 'bg-[#111317] text-white'
                  : 'bg-[#FFFFFF] text-[#111317] hover:bg-[#EBE8E0]'
              }`}
            >
              Linear
            </button>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 font-mono text-[11px] text-[#373C44]">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-5 bg-[#C84B31]" />
              <span className="font-bold text-[#C84B31]">Vermilion Line = Pareto Frontier</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3.5 w-3.5 rounded-full border-2 border-[#C84B31] bg-[#111317]" />
              <span>Pareto Node</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="relative flex h-3 w-3 items-center justify-center rounded-full bg-[#1F7A63]">
                <span className="h-1 w-1 rounded-full bg-white" />
              </span>
              <span>Open-Weights</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-full bg-[#181A1F]" />
              <span>Proprietary</span>
            </span>
          </div>
        </div>
      </div>

      {/* Lab Palette Filter Strip — Including MiniMax */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-[#D8D4C8] bg-[#FDFCFB] px-5 py-2 font-mono text-[10px] text-[#373C44]">
        <span className="font-bold uppercase tracking-wider text-[#68707C]">Key Labs:</span>
        {FEATURED_LABS.map((lab) => {
          const style = getLabStyle(lab);
          const isSelected = selectedProvider === lab;
          return (
            <button
              key={lab}
              type="button"
              onClick={() => onSelectProvider?.(isSelected ? 'ALL' : lab)}
              className={`inline-flex items-center gap-1.5 rounded-none px-2 py-0.5 transition ${
                isSelected
                  ? 'border border-[#111317] bg-[#111317] text-white font-bold'
                  : 'hover:bg-[#EBE8E0] text-[#111317]'
              }`}
              title={`Filter by ${lab}`}
            >
              <span
                className="inline-flex h-3.5 w-3.5 items-center justify-center text-[8px] font-bold"
                style={{ backgroundColor: style.badgeBg, color: style.badgeText }}
              >
                {style.short}
              </span>
              <span>{lab}</span>
            </button>
          );
        })}
      </div>

      {/* SVG Canvas Area */}
      <div ref={containerRef} className="relative w-full swiss-dot-bg overflow-hidden" style={{ height: CHART_HEIGHT }}>
        <svg
          width={containerWidth}
          height={CHART_HEIGHT}
          className="block select-none"
          role="img"
          aria-label={`Scatter plot of blended token price (${activeScale} scale) versus unified quality score with Vermilion Pareto frontier`}
        >
          {/* Architectural Axis Grid Lines */}
          <g className="grid-lines">
            {/* Horizontal Y Gridlines */}
            {Y_TICKS.map((score) => {
              const y = toY(score);
              return (
                <line
                  key={`gy-${score}`}
                  x1={MARGIN.left}
                  x2={MARGIN.left + plotW}
                  y1={y}
                  y2={y}
                  stroke={COLOR_GRID}
                  strokeWidth={1}
                  strokeDasharray="3 3"
                />
              );
            })}

            {/* Vertical X Gridlines */}
            {activeXTicks.map((price) => {
              const x = toX(price);
              return (
                <line
                  key={`gx-${price}`}
                  x1={x}
                  x2={x}
                  y1={MARGIN.top}
                  y2={MARGIN.top + plotH}
                  stroke={COLOR_GRID}
                  strokeWidth={1}
                  strokeDasharray="3 3"
                />
              );
            })}
          </g>

          {/* Shaded Pareto Efficiency Hull */}
          {frontierHullPath && (
            <path
              d={frontierHullPath}
              fill="rgba(200, 75, 49, 0.08)"
              stroke="none"
              className="pointer-events-none"
            />
          )}

          {/* Vermilion Pareto Frontier Line */}
          {frontierLinePath && (
            <path
              d={frontierLinePath}
              fill="none"
              stroke={COLOR_FRONTIER}
              strokeWidth={2.5}
              strokeLinejoin="round"
              strokeLinecap="round"
              className="pointer-events-none"
            />
          )}

          {/* X and Y Axis Baseline Borders */}
          {/* X-Axis Horizontal Baseline */}
          <line
            x1={MARGIN.left}
            x2={MARGIN.left + plotW}
            y1={MARGIN.top + plotH}
            y2={MARGIN.top + plotH}
            stroke={COLOR_INK}
            strokeWidth={1.5}
          />
          {/* Y-Axis Vertical Baseline */}
          <line
            x1={MARGIN.left}
            x2={MARGIN.left}
            y1={MARGIN.top}
            y2={MARGIN.top + plotH}
            stroke={COLOR_INK}
            strokeWidth={1.5}
          />

          {/* X-Axis Ticks & Numerical Indicators */}
          <g className="x-axis-ticks">
            {activeXTicks.map((price) => {
              const x = toX(price);
              return (
                <g key={`xtick-${price}`} transform={`translate(${x}, ${MARGIN.top + plotH})`}>
                  <line y1={0} y2={6} stroke={COLOR_INK} strokeWidth={1.2} />
                  <text
                    y={19}
                    textAnchor="middle"
                    className="font-mono text-[10px] font-medium"
                    fill={COLOR_INK}
                  >
                    {formatPrice(price)}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Y-Axis Ticks & Numerical Indicators */}
          <g className="y-axis-ticks">
            {Y_TICKS.map((score) => {
              const y = toY(score);
              return (
                <g key={`ytick-${score}`} transform={`translate(${MARGIN.left}, ${y})`}>
                  <line x1={-6} x2={0} stroke={COLOR_INK} strokeWidth={1.2} />
                  <text
                    x={-9}
                    dy="0.32em"
                    textAnchor="end"
                    className="font-mono text-[10px] font-medium"
                    fill={COLOR_INK}
                  >
                    {score}pt
                  </text>
                </g>
              );
            })}
          </g>

          {/* X-Axis Title / Indicator */}
          <text
            x={MARGIN.left + plotW / 2}
            y={CHART_HEIGHT - 12}
            textAnchor="middle"
            className="font-mono text-[10px] font-bold uppercase tracking-wider"
            fill={COLOR_INK}
          >
            BLENDED TOKEN PRICE ($ / 1M TOKENS, {activeScale === 'log' ? 'LOG SCALE' : 'LINEAR SCALE'}) →
          </text>

          {/* Y-Axis Title / Indicator */}
          <text
            transform={`translate(16, ${MARGIN.top + plotH / 2}) rotate(-90)`}
            textAnchor="middle"
            className="font-mono text-[10px] font-bold uppercase tracking-wider"
            fill={COLOR_INK}
          >
            UNIFIED QUALITY SCORE (0–100) →
          </text>

          {/* Non-Pareto Dominated Models */}
          <g className="data-points-dominated">
            {priced
              .filter((m) => !m.isDynamicPareto)
              .map((m) => {
                const cx = toX(m.pricing.blended_per_1m_usd);
                const cy = toY(m.dynamicScore);
                const isHovered = hoveredId === m.id;
                const isMatchingLab = selectedProvider && selectedProvider !== 'ALL' ? m.provider === selectedProvider : true;
                const labStyle = getLabStyle(m.provider);

                return (
                  <g
                    key={m.id}
                    className="cursor-pointer transition-transform"
                    onMouseEnter={() => setHoveredId(m.id)}
                    onMouseLeave={() => setHoveredId(null)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 6.5 : 4.2}
                      fill={labStyle.bg}
                      fillOpacity={isMatchingLab ? 0.85 : 0.25}
                      stroke={isHovered ? COLOR_INK : '#FFFFFF'}
                      strokeWidth={isHovered ? 2 : 1}
                    />
                    {m.is_open_weights && (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={1.8}
                        fill="#FFFFFF"
                        className="pointer-events-none"
                      />
                    )}
                  </g>
                );
              })}
          </g>

          {/* Pareto Frontier Optimal Models (Drawn on top for visibility) */}
          <g className="data-points-pareto">
            {frontierWithLabels.map(({ m, cx, cy, labelX, labelY, anchor }) => {
              const isHovered = hoveredId === m.id;

              return (
                <g
                  key={m.id}
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredId(m.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  {/* Outer Vermilion Halo */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 10 : 8}
                    fill="rgba(200, 75, 49, 0.20)"
                    stroke="none"
                  />
                  {/* Main Pareto Circle */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 7.5 : 6}
                    fill={COLOR_INK}
                    stroke={COLOR_FRONTIER}
                    strokeWidth={2.2}
                  />
                  {/* Open Weights Dot if applicable */}
                  {m.is_open_weights && (
                    <circle cx={cx} cy={cy} r={2} fill="#FFFFFF" className="pointer-events-none" />
                  )}

                  {/* Clean Frontier Label */}
                  <text
                    x={labelX}
                    y={labelY}
                    textAnchor={anchor}
                    className="font-mono text-[10px] font-bold"
                    fill={COLOR_INK}
                    stroke="#FFFFFF"
                    strokeWidth={3.5}
                    paintOrder="stroke"
                  >
                    {m.display_name}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredModel && (
          <div
            className="pointer-events-none absolute z-30 border-2 border-[#111317] bg-[#FFFFFF] p-3 font-mono text-xs shadow-[4px_4px_0_#111317]"
            style={{
              left: Math.min(
                Math.max(16, toX(hoveredModel.pricing.blended_per_1m_usd) + 14),
                containerWidth - 250
              ),
              top: Math.max(16, Math.min(toY(hoveredModel.dynamicScore) - 40, CHART_HEIGHT - 130)),
              width: 230,
            }}
          >
            <div className="flex items-center gap-1.5 border-b border-[#D8D4C8] pb-1.5">
              <span
                className="inline-flex h-4 w-4 shrink-0 items-center justify-center font-bold text-[8px]"
                style={{
                  backgroundColor: getLabStyle(hoveredModel.provider).badgeBg,
                  color: getLabStyle(hoveredModel.provider).badgeText,
                }}
              >
                {getLabStyle(hoveredModel.provider).short}
              </span>
              <span className="truncate font-heading font-bold text-[#111317]">
                {hoveredModel.display_name}
              </span>
            </div>
            <div className="mt-1.5 space-y-1 text-[11px] text-[#373C44]">
              <div className="flex justify-between">
                <span>Provider:</span>
                <span className="font-semibold text-[#111317]">{hoveredModel.provider}</span>
              </div>
              <div className="flex justify-between">
                <span>Thinking Effort:</span>
                <span className="uppercase text-[#255C99] font-semibold">
                  {hoveredModel.thinking_effort || 'standard'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Unified Score:</span>
                <span className="font-bold text-[#C84B31]">
                  {hoveredModel.dynamicScore.toFixed(2)} pts
                </span>
              </div>
              <div className="flex justify-between">
                <span>Blended Price:</span>
                <span className="font-bold text-[#111317]">
                  ${hoveredModel.pricing.blended_per_1m_usd.toFixed(2)} / 1M
                </span>
              </div>
              {hoveredModel.performance.output_tokens_per_sec !== null && (
                <div className="flex justify-between">
                  <span>Speed:</span>
                  <span>{hoveredModel.performance.output_tokens_per_sec.toFixed(0)} tok/s</span>
                </div>
              )}
              {hoveredModel.isDynamicPareto && (
                <div className="mt-1 border-t border-[#D8D4C8] pt-1 font-bold uppercase text-[#C84B31]">
                  ★ Pareto Frontier Optimal
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Chart Footer Note */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t-2 border-[#111317] bg-[#F4F2ED] px-5 py-2 font-mono text-[10px] text-[#68707C]">
        <span>
          // SWISS ARCHIVAL TELEMETRY: Vermilion frontier connects models where no cheaper alternative achieves equal or higher quality.
        </span>
        <span className="font-semibold text-[#111317]">
          {frontier.length} Frontier Models · {priced.length} Benchmark Evaluations
        </span>
      </div>
    </div>
  );
};
