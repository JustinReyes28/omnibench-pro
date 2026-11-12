export interface LabStyle {
  bg: string;
  text: string;
  badgeBg: string;
  badgeText: string;
  short: string;
}

export const LAB_PALETTE: Record<string, LabStyle> = {
  'OpenAI': { bg: '#181A1F', text: '#FFFFFF', badgeBg: '#181A1F', badgeText: '#FFFFFF', short: 'OA' },
  'Anthropic': { bg: '#C84B31', text: '#FFFFFF', badgeBg: '#C84B31', badgeText: '#FFFFFF', short: 'AN' },
  'Google': { bg: '#255C99', text: '#FFFFFF', badgeBg: '#255C99', badgeText: '#FFFFFF', short: 'GO' },
  'DeepSeek': { bg: '#1F7A63', text: '#FFFFFF', badgeBg: '#1F7A63', badgeText: '#FFFFFF', short: 'DS' },
  'Meta': { bg: '#3B6E8C', text: '#FFFFFF', badgeBg: '#3B6E8C', badgeText: '#FFFFFF', short: 'MT' },
  'Moonshot AI': { bg: '#6C4B8B', text: '#FFFFFF', badgeBg: '#6C4B8B', badgeText: '#FFFFFF', short: 'KM' },
  'Alibaba': { bg: '#C57B18', text: '#FFFFFF', badgeBg: '#C57B18', badgeText: '#FFFFFF', short: 'QW' },
  'Alibaba Cloud': { bg: '#C57B18', text: '#FFFFFF', badgeBg: '#C57B18', badgeText: '#FFFFFF', short: 'QW' },
  'Z.AI': { bg: '#4F6478', text: '#FFFFFF', badgeBg: '#4F6478', badgeText: '#FFFFFF', short: 'ZA' },
  'Xiaomi': { bg: '#D96B27', text: '#FFFFFF', badgeBg: '#D96B27', badgeText: '#FFFFFF', short: 'XM' },
  'MiniMax': { bg: '#5B4B8A', text: '#FFFFFF', badgeBg: '#5B4B8A', badgeText: '#FFFFFF', short: 'MM' },
  'StepFun': { bg: '#2B7A78', text: '#FFFFFF', badgeBg: '#2B7A78', badgeText: '#FFFFFF', short: 'SF' },
  'Tencent': { bg: '#1E56A0', text: '#FFFFFF', badgeBg: '#1E56A0', badgeText: '#FFFFFF', short: 'TC' },
  'Thinking Machines': { bg: '#3A506B', text: '#FFFFFF', badgeBg: '#3A506B', badgeText: '#FFFFFF', short: 'TM' },
  'Reflection AI': { bg: '#7A4988', text: '#FFFFFF', badgeBg: '#7A4988', badgeText: '#FFFFFF', short: 'RF' },
  'Inception': { bg: '#8C4A27', text: '#FFFFFF', badgeBg: '#8C4A27', badgeText: '#FFFFFF', short: 'IN' },
  'IFM': { bg: '#2D6A4F', text: '#FFFFFF', badgeBg: '#2D6A4F', badgeText: '#FFFFFF', short: 'IF' },
  'InclusionAI': { bg: '#6D597A', text: '#FFFFFF', badgeBg: '#6D597A', badgeText: '#FFFFFF', short: 'IC' },
  'xAI': { bg: '#485058', text: '#FFFFFF', badgeBg: '#485058', badgeText: '#FFFFFF', short: 'XA' },
  'Mistral AI': { bg: '#B45B28', text: '#FFFFFF', badgeBg: '#B45B28', badgeText: '#FFFFFF', short: 'MI' },
  'NVIDIA': { bg: '#2E6F40', text: '#FFFFFF', badgeBg: '#2E6F40', badgeText: '#FFFFFF', short: 'NV' },
  'Cohere': { bg: '#8B3A62', text: '#FFFFFF', badgeBg: '#8B3A62', badgeText: '#FFFFFF', short: 'CO' },
  'IBM': { bg: '#0F62FE', text: '#FFFFFF', badgeBg: '#0F62FE', badgeText: '#FFFFFF', short: 'IB' },
  'LG AI Research': { bg: '#A50034', text: '#FFFFFF', badgeBg: '#A50034', badgeText: '#FFFFFF', short: 'LG' },
  'China Mobile': { bg: '#0068B7', text: '#FFFFFF', badgeBg: '#0068B7', badgeText: '#FFFFFF', short: 'CM' },
  'Upstage': { bg: '#5B21B6', text: '#FFFFFF', badgeBg: '#5B21B6', badgeText: '#FFFFFF', short: 'UP' },
  'Sapiens AI': { bg: '#9F1239', text: '#FFFFFF', badgeBg: '#9F1239', badgeText: '#FFFFFF', short: 'SA' },
  'Nanbeige': { bg: '#0E7490', text: '#FFFFFF', badgeBg: '#0E7490', badgeText: '#FFFFFF', short: 'NB' },
  'Apodex': { bg: '#4338CA', text: '#FFFFFF', badgeBg: '#4338CA', badgeText: '#FFFFFF', short: 'AP' },
};

export function getLabStyle(provider: string): LabStyle {
  return (
    LAB_PALETTE[provider] || {
      bg: '#485058',
      text: '#FFFFFF',
      badgeBg: '#485058',
      badgeText: '#FFFFFF',
      short: (provider || 'AI').slice(0, 2).toUpperCase(),
    }
  );
}
