import { UnifiedDatasetSchema, type UnifiedDataset } from "./schema";

export async function loadUnifiedDataset(): Promise<UnifiedDataset> {
  const baseUrl = import.meta.env.BASE_URL || "./";
  const normalizedBase = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  const response = await fetch(`${normalizedBase}data/models_unified.json`);
  if (!response.ok) {
    throw new Error(`Failed to fetch models_unified.json: HTTP ${response.status}`);
  }
  const rawJson = await response.json();
  return UnifiedDatasetSchema.parse(rawJson);
}

export const loadUnifiedBenchmarkData = loadUnifiedDataset;
