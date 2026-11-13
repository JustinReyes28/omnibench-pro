import type { CanonicalModel, ModelCapabilities } from './schema';

export type CapabilityAxisKey = keyof ModelCapabilities;

export interface CapabilityAxisMeta {
  key: CapabilityAxisKey;
  label: string;
  shortLabel: string;
  tableLabel: string;
  color: string;
  description: string;
}

export const CAPABILITY_AXES: CapabilityAxisMeta[] = [
  {
    key: 'coding',
    label: 'Coding & SWE',
    shortLabel: 'CODE',
    tableLabel: 'Coding',
    color: '#255C99',
    description: 'AA Coding Index, LiveBench Coding & Agentic, and Arena Coding Elo',
  },
  {
    key: 'reasoning',
    label: 'Reasoning & Math',
    shortLabel: 'REAS',
    tableLabel: 'Reason.',
    color: '#111317',
    description: 'AA Intelligence & Math Index, LiveBench Reasoning & Mathematics',
  },
  {
    key: 'agentic',
    label: 'Agentic & Tools',
    shortLabel: 'AGNT',
    tableLabel: 'Agentic',
    color: '#C57B18',
    description: 'LiveBench Agentic Coding & Instruction Following, Vals Finance Agent',
  },
  {
    key: 'enterprise',
    label: 'Enterprise & Docs',
    shortLabel: 'ENTP',
    tableLabel: 'Entpr.',
    color: '#1F7A63',
    description: 'Vals Enterprise Index (Finance, Legal, Tax) & LiveBench Data Analysis',
  },
  {
    key: 'chat',
    label: 'Human Chat & Pref.',
    shortLabel: 'CHAT',
    tableLabel: 'Chat',
    color: '#C84B31',
    description: 'Arena.ai Text Crowd-BT Elo & LiveBench Language Fluency',
  },
];

export function getCapabilityScores(model: CanonicalModel): ModelCapabilities {
  if (model.capabilities) {
    return model.capabilities;
  }
  return {
    coding: model.composite.coding_composite_score ?? null,
    reasoning: model.normalized_pillars?.aa ?? model.normalized_pillars?.lb ?? null,
    agentic: null,
    enterprise: model.composite.enterprise_agent_score ?? null,
    chat: model.normalized_pillars?.ar ?? null,
  };
}

export interface EvaluatedCapabilityItem {
  key: CapabilityAxisKey;
  shortLabel: string;
  label: string;
  score: number;
  color: string;
}

export function getTopCapabilities(model: CanonicalModel, limit = 2): EvaluatedCapabilityItem[] {
  const scores = getCapabilityScores(model);
  return CAPABILITY_AXES.map((axis) => ({
    key: axis.key,
    shortLabel: axis.shortLabel,
    label: axis.label,
    color: axis.color,
    score: scores[axis.key],
  }))
    .filter((item): item is EvaluatedCapabilityItem => typeof item.score === 'number')
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

export function formatReleaseDateShort(isoDate: string): string {
  const parts = isoDate.split('-').map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return isoDate;
  const [year, month, day] = parts;
  const d = new Date(Date.UTC(year, month - 1, day));
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
