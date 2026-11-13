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

export interface CapabilityStrengthProfile {
  badgeLabel: string;
  badgeColor: string;
  topAxes: Array<{ key: CapabilityAxisKey; shortLabel: string; score: number; color: string }>;
  evaluatedCount: number;
}

const AXIS_LEAD_LABELS: Record<CapabilityAxisKey, string> = {
  coding: 'Coding Specialist',
  reasoning: 'Reasoning & Math',
  agentic: 'Agentic Execution',
  enterprise: 'Enterprise Specialist',
  chat: 'Human Chat Favorite',
};

export function getCapabilityStrengthProfile(
  model: CanonicalModel,
  options?: { isPareto?: boolean; score?: number }
): CapabilityStrengthProfile {
  const scores = getCapabilityScores(model);
  const evaluated = CAPABILITY_AXES.map((axis) => ({
    key: axis.key,
    shortLabel: axis.shortLabel,
    color: axis.color,
    score: scores[axis.key],
  }))
    .filter((item): item is { key: CapabilityAxisKey; shortLabel: string; color: string; score: number } =>
      typeof item.score === 'number'
    )
    .sort((a, b) => b.score - a.score);

  const topAxes = evaluated.slice(0, 2);
  if (evaluated.length === 0) {
    return {
      badgeLabel: 'Pending Profile',
      badgeColor: '#68707C',
      topAxes: [],
      evaluatedCount: 0,
    };
  }

  const peak = evaluated[0];
  const floor = evaluated[evaluated.length - 1];
  const median = evaluated[Math.floor(evaluated.length / 2)].score;
  const effectiveScore = options?.score ?? model.composite.unified_quality_score;
  const price = model.pricing.blended_per_1m_usd;

  if (evaluated.length >= 4 && floor.score >= 85 && peak.score >= 92) {
    return {
      badgeLabel: 'All-Round Frontier',
      badgeColor: '#C84B31',
      topAxes,
      evaluatedCount: evaluated.length,
    };
  }

  if (
    typeof scores.coding === 'number' &&
    typeof scores.reasoning === 'number' &&
    scores.coding >= 82 &&
    scores.reasoning >= 82 &&
    typeof scores.chat === 'number' &&
    scores.reasoning - scores.chat >= 7
  ) {
    return {
      badgeLabel: 'STEM & Coding Lead',
      badgeColor: '#255C99',
      topAxes,
      evaluatedCount: evaluated.length,
    };
  }

  if (peak.score - median >= 7 && peak.score >= 55) {
    return {
      badgeLabel: AXIS_LEAD_LABELS[peak.key],
      badgeColor: peak.color,
      topAxes,
      evaluatedCount: evaluated.length,
    };
  }

  if (options?.isPareto && price !== null && price <= 1.25 && effectiveScore >= 45) {
    return {
      badgeLabel: 'Efficiency Frontier',
      badgeColor: '#1F7A63',
      topAxes,
      evaluatedCount: evaluated.length,
    };
  }

  if (evaluated.length < 4) {
    return {
      badgeLabel: `Partial · ${peak.shortLabel} ${peak.score.toFixed(0)}`,
      badgeColor: '#68707C',
      topAxes,
      evaluatedCount: evaluated.length,
    };
  }

  return {
    badgeLabel: effectiveScore >= 70 ? 'Balanced Tier-1' : 'Balanced Generalist',
    badgeColor: '#373C44',
    topAxes,
    evaluatedCount: evaluated.length,
  };
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
