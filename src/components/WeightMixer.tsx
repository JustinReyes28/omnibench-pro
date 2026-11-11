import React from 'react';
import { PillarWeights, WEIGHT_PRESETS } from '../lib/scoring';

interface Props {
  weights: PillarWeights;
  onChange: (next: PillarWeights) => void;
}

export const WeightMixer: React.FC<Props> = ({ weights, onChange }) => {
  const sum = weights.aa + weights.lb + weights.ar + weights.va || 1;
  const pctAA = Math.round((weights.aa / sum) * 100);
  const pctLB = Math.round((weights.lb / sum) * 100);
  const pctAR = Math.round((weights.ar / sum) * 100);
  const pctVA = Math.max(0, 100 - pctAA - pctLB - pctAR);

  const handleSlider = (key: keyof PillarWeights, val: number) => {
    onChange({ ...weights, [key]: val });
  };

  return (
    <div className="border-t border-[#D8D4C8] bg-[#FFFFFF] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#D8D4C8] pb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#111317]">
            Interactive Weight Mixer
          </span>
          <span className="font-mono text-[11px] text-[#68707C]">
            — Adjust sliders or apply a preset to recompute scores &amp; Pareto frontier
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(WEIGHT_PRESETS).map(([presetKey, presetConfig]) => (
            <button
              key={presetKey}
              type="button"
              onClick={() => onChange(presetConfig.weights)}
              title={presetConfig.description}
              className="border border-[#111317] bg-[#F4F2ED] px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-wider text-[#111317] transition hover:bg-[#111317] hover:text-white"
            >
              {presetConfig.label}
            </button>
          ))}
        </div>
      </div>

      {/* Live 4-Color Proportional Weight Allocation Bar */}
      <div className="mt-4">
        <div className="flex h-3 w-full overflow-hidden border border-[#111317] bg-[#EBE8E0]">
          <div className="h-full bg-[#255C99] transition-all duration-200" style={{ width: `${(weights.aa / sum) * 100}%` }} />
          <div className="h-full bg-[#C57B18] transition-all duration-200" style={{ width: `${(weights.lb / sum) * 100}%` }} />
          <div className="h-full bg-[#C84B31] transition-all duration-200" style={{ width: `${(weights.ar / sum) * 100}%` }} />
          <div className="h-full bg-[#1F7A63] transition-all duration-200" style={{ width: `${(weights.va / sum) * 100}%` }} />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3">
          <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#111317]">
              <span className="h-2.5 w-2.5 bg-[#255C99]" /> ARTIFICIAL ANALYSIS
            </span>
            <span className="bg-[#255C99] px-1.5 py-0.5 text-[10px] font-bold text-white">{pctAA}%</span>
          </div>
          <input type="range" min={0} max={100} value={weights.aa} onChange={(e) => handleSlider('aa', Number(e.target.value))} className="w-full accent-[#111317]" />
          <div className="mt-1 font-mono text-[10px] text-[#68707C]">Intelligence v5.0, Coding, Math</div>
        </div>

        <div className="border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3">
          <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#111317]">
              <span className="h-2.5 w-2.5 bg-[#C57B18]" /> LIVEBENCH 2.0
            </span>
            <span className="bg-[#C57B18] px-1.5 py-0.5 text-[10px] font-bold text-white">{pctLB}%</span>
          </div>
          <input type="range" min={0} max={100} value={weights.lb} onChange={(e) => handleSlider('lb', Number(e.target.value))} className="w-full accent-[#111317]" />
          <div className="mt-1 font-mono text-[10px] text-[#68707C]">Contamination-Free Agentic &amp; Coding</div>
        </div>

        <div className="border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3">
          <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#111317]">
              <span className="h-2.5 w-2.5 bg-[#C84B31]" /> ARENA.AI ELO
            </span>
            <span className="bg-[#C84B31] px-1.5 py-0.5 text-[10px] font-bold text-white">{pctAR}%</span>
          </div>
          <input type="range" min={0} max={100} value={weights.ar} onChange={(e) => handleSlider('ar', Number(e.target.value))} className="w-full accent-[#111317]" />
          <div className="mt-1 font-mono text-[10px] text-[#68707C]">Human Text + Coding Elo Composite</div>
        </div>

        <div className="border border-[#D8D4C8] bg-[#F4F2ED]/60 p-3">
          <div className="mb-1.5 flex items-center justify-between font-mono text-[11px]">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#111317]">
              <span className="h-2.5 w-2.5 bg-[#1F7A63]" /> VALS.AI INDEX
            </span>
            <span className="bg-[#1F7A63] px-1.5 py-0.5 text-[10px] font-bold text-white">{pctVA}%</span>
          </div>
          <input type="range" min={0} max={100} value={weights.va} onChange={(e) => handleSlider('va', Number(e.target.value))} className="w-full accent-[#111317]" />
          <div className="mt-1 font-mono text-[10px] text-[#68707C]">Finance, Legal, Tax &amp; Vibe Code</div>
        </div>
      </div>
    </div>
  );
};
