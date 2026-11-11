import { useState, useEffect } from "react";
import { WEIGHT_PRESETS, type PillarWeights } from "../lib/scoring";

export type ActivePage = "leaderboard" | "timeline";
export type ParetoScaleMode = "log" | "linear";

export interface DashboardFilterState {
  activePage: ActivePage;
  paretoScale: ParetoScaleMode;
  weights: PillarWeights;
  searchQuery: string;
  openWeightsOnly: boolean;
  paretoOnly: boolean;
  providerFilter: string;
  effortFilter: string;
  comparedModelIds: string[];
}

export function useUrlFilterState() {
  const [state, setState] = useState<DashboardFilterState>(() => {
    const params = new URLSearchParams(window.location.search);
    const wParam = params.get("weights");
    let weights = WEIGHT_PRESETS.frontier.weights;
    if (wParam) {
      const parts = wParam.split(",").map(Number);
      if (parts.length === 4 && parts.every((n) => !Number.isNaN(n) && n >= 0)) {
        weights = { aa: parts[0], lb: parts[1], ar: parts[2], va: parts[3] };
      }
    }
    const compareParam = params.get("compare");
    const pageParam = params.get("page");
    const hashPage = window.location.hash.replace(/^#\/?/, "").toLowerCase();
    const activePage: ActivePage =
      pageParam === "timeline" || hashPage === "timeline" ? "timeline" : "leaderboard";
    const paretoScale: ParetoScaleMode = params.get("scale") === "linear" ? "linear" : "log";

    return {
      activePage,
      paretoScale,
      weights,
      searchQuery: params.get("q") || "",
      openWeightsOnly: params.get("open") === "1",
      paretoOnly: params.get("pareto") === "1",
      providerFilter: params.get("provider") || "ALL",
      effortFilter: params.get("effort") || "ALL",
      comparedModelIds: compareParam
        ? compareParam.split(",").filter(Boolean).slice(0, 4)
        : [
            "google-gemini-4-carbon-high",
            "anthropic-claude-opus-5-5",
            "openai-gpt-6-astra-max",
            "deepseek-v4-1-flash-1017",
          ],
    };
  });

  useEffect(() => {
    const params = new URLSearchParams();
    if (state.activePage === "timeline") params.set("page", "timeline");
    if (state.paretoScale === "linear") params.set("scale", "linear");
    const { aa, lb, ar, va } = state.weights;
    params.set("weights", `${aa},${lb},${ar},${va}`);
    if (state.searchQuery) params.set("q", state.searchQuery);
    if (state.openWeightsOnly) params.set("open", "1");
    if (state.paretoOnly) params.set("pareto", "1");
    if (state.providerFilter !== "ALL") params.set("provider", state.providerFilter);
    if (state.effortFilter !== "ALL") params.set("effort", state.effortFilter);
    if (state.comparedModelIds.length > 0) params.set("compare", state.comparedModelIds.join(","));
    const nextUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", nextUrl);
  }, [state]);

  return { state, setState };
}
