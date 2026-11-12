import React from 'react';
import { SourcesMetadataMap } from '../lib/schema';

interface Props {
  metadata: SourcesMetadataMap;
  generatedAt: string;
}

export const SourceAttributionBar: React.FC<Props> = ({ metadata, generatedAt }) => {
  return (
    <div className="border-b border-[#D8D4C8] bg-[#111317] px-3 py-1 sm:px-4 sm:py-1.5 text-xs text-[#F4F2ED]">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-2 font-mono text-[10px] overflow-x-auto no-scrollbar whitespace-nowrap">
        <div className="flex items-center gap-2.5 sm:gap-3">
          <span className="hidden sm:inline-flex items-center gap-1.5 font-semibold text-[#C84B31]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#C84B31]" />
            BENCHMARK SOURCES
          </span>
          <a href={metadata.artificial_analysis.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 shrink-0 bg-[#255C99]" />
            <span>AA<span className="hidden md:inline"> Intelligence v5.0</span></span>
          </a>
          <a href={metadata.livebench.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 shrink-0 bg-[#C57B18]" />
            <span>LiveBench<span className="hidden md:inline"> ({metadata.livebench.release})</span></span>
          </a>
          <a href={metadata.arena.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 shrink-0 bg-[#C84B31]" />
            <span>Arena<span className="hidden md:inline">.ai Crowd-BT</span></span>
          </a>
          <a href={metadata.vals.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 shrink-0 bg-[#1F7A63]" />
            <span>Vals<span className="hidden md:inline"> Enterprise v2.2</span></span>
          </a>
        </div>
        <div className="text-[#EBE8E0] shrink-0">
          <span className="hidden sm:inline">Snapshot: </span>
          <span className="font-semibold text-white">{generatedAt.slice(0, 10)}</span>
        </div>
      </div>
    </div>
  );
};
