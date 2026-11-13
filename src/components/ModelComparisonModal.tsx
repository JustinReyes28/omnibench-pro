import React from 'react';
import { ScoredModelEntry } from './LeaderboardTable';
import {
  CAPABILITY_AXES,
  formatReleaseDateShort,
  getCapabilityScores,
  getCapabilityStrengthProfile,
} from '../lib/capabilities';
import { getLabStyle } from '../lib/labPalette';

interface Props {
  models: ScoredModelEntry[];
  onRemove: (id: string) => void;
}

const SERIES_COLORS = ['#C84B31', '#255C99', '#1F7A63', '#C57B18'];

const RADAR_CX = 170;
const RADAR_CY = 148;
const RADAR_R = 88;
const RINGS = [20, 40, 60, 80, 100];

function polarPoint(axisIdx: number, totalAxes: number, value0to100: number): [number, number] {
  const angle = -Math.PI / 2 + (axisIdx * 2 * Math.PI) / totalAxes;
  const r = (Math.max(0, Math.min(100, value0to100)) / 100) * RADAR_R;
  return [RADAR_CX + r * Math.cos(angle), RADAR_CY + r * Math.sin(angle)];
}

export const ModelComparisonModal: React.FC<Props> = ({ models, onRemove }) => {
  if (models.length === 0) return null;

  const hasPartialModel = models.some((m) => m.composite.sources_present < 4);
  const totalAxes = CAPABILITY_AXES.length;

  return (
    <section
      aria-label="Head-to-head model capability comparison"
      className="border-2 border-[#111317] bg-[#FFFFFF] shadow-[4px_4px_0_#111317]"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-[#111317] bg-[#111317] px-5 py-3 font-mono text-xs text-white">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 bg-[#C84B31]" />
          <h3 className="font-bold uppercase tracking-widest">
            HEAD-TO-HEAD CAPABILITY RADAR ({models.length}/4)
          </h3>
        </div>
        <span className="text-[10px] text-[#D8D4C8]">
          Click &ldquo;+ Radar&rdquo; on any table row or click a bar above to swap models
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 p-5 lg:grid-cols-12 lg:items-start">
        {/* Left: 5-Axis SVG Capability Radar */}
        <div className="border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3 lg:col-span-4">
          <div className="mb-1 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-[#68707C]">
            <span>5-Axis Capability Fingerprint</span>
            <span>0–100 Scale</span>
          </div>
          <svg
            viewBox="0 0 340 292"
            className="mx-auto block w-full max-w-[340px]"
            role="img"
            aria-label="5-axis capability radar comparing Coding, Reasoning, Agentic, Enterprise, and Chat scores"
          >
            {/* Concentric pentagon reference rings */}
            {RINGS.map((ringVal) => {
              const pts = CAPABILITY_AXES.map((_, idx) => {
                const [x, y] = polarPoint(idx, totalAxes, ringVal);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
              }).join(' ');
              const [, topY] = polarPoint(0, totalAxes, ringVal);
              return (
                <g key={`ring-${ringVal}`}>
                  <polygon
                    points={pts}
                    fill="none"
                    stroke={ringVal === 100 ? '#111317' : '#D8D4C8'}
                    strokeWidth={ringVal === 100 ? 1.2 : 1}
                    strokeDasharray={ringVal === 100 ? undefined : '2 2'}
                  />
                  <text
                    x={RADAR_CX + 3}
                    y={topY + 9}
                    className="font-mono text-[8px]"
                    fill="#68707C"
                  >
                    {ringVal}
                  </text>
                </g>
              );
            })}

            {/* Spokes & Axis Labels */}
            {CAPABILITY_AXES.map((axis, idx) => {
              const [outerX, outerY] = polarPoint(idx, totalAxes, 100);
              const [lblX, lblY] = polarPoint(idx, totalAxes, 124);
              const anchor =
                Math.abs(lblX - RADAR_CX) < 12 ? 'middle' : lblX > RADAR_CX ? 'start' : 'end';
              return (
                <g key={axis.key}>
                  <line
                    x1={RADAR_CX}
                    y1={RADAR_CY}
                    x2={outerX}
                    y2={outerY}
                    stroke="#C8C3B4"
                    strokeWidth={1}
                  />
                  <text
                    x={lblX}
                    y={lblY}
                    dy={idx === 0 ? '-0.2em' : '0.35em'}
                    textAnchor={anchor}
                    className="font-mono text-[10px] font-bold uppercase"
                    fill="#111317"
                  >
                    {axis.shortLabel}
                  </text>
                </g>
              );
            })}

            {/* Plotted Model Series (drawn back-to-front so primary stays clear) */}
            {[...models].reverse().map((m, revIdx) => {
              const origIdx = models.length - 1 - revIdx;
              const color = SERIES_COLORS[origIdx % SERIES_COLORS.length];
              const caps = getCapabilityScores(m);
              const evaluatedPts = CAPABILITY_AXES.map((axis, axisIdx) => {
                const val = caps[axis.key];
                if (typeof val !== 'number') return null;
                const [x, y] = polarPoint(axisIdx, totalAxes, val);
                return { x, y, val, axis: axis.shortLabel };
              }).filter((pt): pt is { x: number; y: number; val: number; axis: string } => pt !== null);

              const allFive = evaluatedPts.length === totalAxes;
              const polyPoints = evaluatedPts.map((pt) => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');

              return (
                <g key={`radar-${m.id}`}>
                  {evaluatedPts.length >= 3 && (
                    <polygon
                      points={polyPoints}
                      fill={color}
                      fillOpacity={allFive ? 0.11 : 0.06}
                      stroke={color}
                      strokeWidth={2.2}
                      strokeDasharray={allFive ? undefined : '4 2'}
                      strokeLinejoin="round"
                    />
                  )}
                  {evaluatedPts.length === 2 && (
                    <line
                      x1={evaluatedPts[0].x}
                      y1={evaluatedPts[0].y}
                      x2={evaluatedPts[1].x}
                      y2={evaluatedPts[1].y}
                      stroke={color}
                      strokeWidth={2.2}
                      strokeDasharray="4 2"
                    />
                  )}
                  {evaluatedPts.map((pt) => (
                    <circle
                      key={`${m.id}-${pt.axis}`}
                      cx={pt.x}
                      cy={pt.y}
                      r={3.2}
                      fill={allFive ? color : '#FFFFFF'}
                      stroke={color}
                      strokeWidth={1.8}
                    >
                      <title>{`${m.display_name} · ${pt.axis}: ${pt.val.toFixed(1)}`}</title>
                    </circle>
                  ))}
                </g>
              );
            })}
          </svg>

          {/* Compact Radar Series Legend */}
          <div className="mt-1 space-y-1 border-t border-[#D8D4C8] pt-2 font-mono text-[10px]">
            {models.map((m, idx) => (
              <div key={`leg-${m.id}`} className="flex items-center justify-between gap-2">
                <span className="inline-flex min-w-0 items-center gap-1.5 font-semibold text-[#111317]">
                  <span
                    className="h-2.5 w-2.5 shrink-0"
                    style={{ backgroundColor: SERIES_COLORS[idx % SERIES_COLORS.length] }}
                  />
                  <span className="truncate">{m.display_name}</span>
                </span>
                <span className="shrink-0 font-bold text-[#373C44]">
                  {m.dynamicScore.toFixed(1)} pts
                </span>
              </div>
            ))}
            {hasPartialModel && (
              <div className="pt-1 text-[9px] text-[#68707C]">
                Dashed polygon marks 2/4 models with pending benchmark axes.
              </div>
            )}
          </div>
        </div>

        {/* Right: Detailed Side-by-Side Capability Profile Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:col-span-8">
          {models.map((m, idx) => {
            const color = SERIES_COLORS[idx % SERIES_COLORS.length];
            const labStyle = getLabStyle(m.provider);
            const caps = getCapabilityScores(m);
            const profile = getCapabilityStrengthProfile(m, {
              isPareto: m.isDynamicPareto,
              score: m.dynamicScore,
            });

            return (
              <div
                key={m.id}
                className="flex flex-col justify-between border border-[#111317] bg-[#F4F2ED]/75 p-3.5 text-xs"
                style={{ borderTopWidth: '4px', borderTopColor: color }}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 border-b border-[#D8D4C8] pb-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span
                          className="inline-flex h-4 w-4 shrink-0 items-center justify-center font-mono text-[8px] font-bold"
                          style={{ backgroundColor: labStyle.badgeBg, color: labStyle.badgeText }}
                        >
                          {labStyle.short}
                        </span>
                        <span className="truncate font-heading text-sm font-bold text-[#111317]">
                          {m.display_name}
                        </span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1 font-mono text-[9px]">
                        <span className="border border-[#255C99]/50 bg-[#255C99]/10 px-1 font-semibold uppercase text-[#255C99]">
                          {m.thinking_effort || 'standard'}
                        </span>
                        {m.composite.sources_present < 4 && (
                          <span className="border border-[#68707C] bg-[#EBE8E0] px-1 font-semibold text-[#373C44]">
                            {m.composite.sources_present}/4 SRC
                          </span>
                        )}
                        <span
                          className="px-1.5 font-semibold text-white"
                          style={{ backgroundColor: profile.badgeColor }}
                        >
                          {profile.badgeLabel}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove(m.id)}
                      className="shrink-0 font-mono text-[10px] font-semibold uppercase text-[#C84B31] hover:underline"
                    >
                      Remove
                    </button>
                  </div>

                  {/* Unified Score Headline */}
                  <div className="mt-2.5 flex items-baseline justify-between font-mono">
                    <span className="text-[10px] uppercase tracking-wider text-[#68707C]">
                      Unified Score
                    </span>
                    <span className="text-sm font-bold text-[#C84B31]">
                      {m.dynamicScore.toFixed(2)} pts
                    </span>
                  </div>

                  {/* 5 Capability Dimension Bars */}
                  <div className="mt-2 space-y-1.5 font-mono text-[10px]">
                    {CAPABILITY_AXES.map((axis) => {
                      const val = caps[axis.key];
                      const evaluated = typeof val === 'number';
                      return (
                        <div key={`${m.id}-${axis.key}`} className="grid grid-cols-12 items-center gap-2">
                          <span className="col-span-4 truncate text-[#373C44]" title={axis.description}>
                            {axis.label.split(' & ')[0]}
                          </span>
                          <div className="col-span-6 h-2.5 overflow-hidden bg-[#E2DFD5]">
                            {evaluated ? (
                              <div
                                className="h-full transition-all"
                                style={{
                                  width: `${Math.max(4, val)}%`,
                                  backgroundColor: axis.color,
                                }}
                              />
                            ) : (
                              <div className="h-full w-full border border-dashed border-[#B7B2A3]" />
                            )}
                          </div>
                          <span className="col-span-2 text-right font-bold text-[#111317]">
                            {evaluated ? val.toFixed(1) : '—'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Telemetry & Source Summary Footer */}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-x-2 gap-y-1 border-t border-[#D8D4C8] pt-2 font-mono text-[10px] text-[#68707C]">
                  <span>
                    {m.pricing.blended_per_1m_usd !== null
                      ? `$${m.pricing.blended_per_1m_usd.toFixed(2)}/1M`
                      : 'Price N/A'}
                  </span>
                  <span>
                    {m.performance.output_tokens_per_sec !== null
                      ? `${m.performance.output_tokens_per_sec.toFixed(0)} tok/s`
                      : 'Speed N/A'}
                  </span>
                  <span>{(m.context_window / 1000).toFixed(0)}k ctx</span>
                  <span>{formatReleaseDateShort(m.release_date)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
