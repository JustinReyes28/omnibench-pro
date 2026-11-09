import React from 'react';
import { SourcesMetadataMap } from '../lib/schema';

interface Props {
  metadata: SourcesMetadataMap;
  generatedAt: string;
}

export const SourceAttributionBar: React.FC<Props> = ({ metadata, generatedAt }) => {
  return (
    <div className="border-b border-[#D8D4C8] bg-[#111317] px-4 py-1.5 text-xs text-[#F4F2ED]">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 font-mono text-[10px]">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5 font-semibold text-[#C84B31]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#C84B31]" />
            4-SOURCE SYNTHESIS ENGINE
          </span>
          <a href={metadata.artificial_analysis.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 bg-[#255C99]" /> AA Intelligence v5.0
          </a>
          <a href={metadata.livebench.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 bg-[#C57B18]" /> LiveBench ({metadata.livebench.release})
          </a>
          <a href={metadata.arena.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 bg-[#C84B31]" /> Arena.ai Crowd-BT
          </a>
          <a href={metadata.vals.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[#D8D4C8] hover:text-white">
            <span className="inline-block h-2 w-2 bg-[#1F7A63]" /> Vals Enterprise v2.2
          </a>
        </div>
        <div className="text-[#EBE8E0]">
          Snapshot: <span className="font-semibold text-white">{generatedAt.slice(0, 10)}</span>
        </div>
      </div>
    </div>
  );
};
