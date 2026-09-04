"use client";

import { create } from "zustand";

export type Lang = "en" | "ne";

interface LangState {
  lang: Lang;
  toggle: () => void;
}

export const useLang = create<LangState>((set) => ({
  lang: "en",
  toggle: () => set((state) => ({ lang: state.lang === "en" ? "ne" : "en" })),
}));

const DICT: Record<string, { en: string; ne: string }> = {
  status: { en: "Status", ne: "स्थिति" },
  lastChecked: { en: "Last checked", ne: "अन्तिम जाँच" },
  whatAgentFound: { en: "What the agent found", ne: "एजेन्टले फेला पारेको कुरा" },
  why: { en: "Why", ne: "किन" },
  nationalPicture: { en: "National picture", ne: "राष्ट्रिय चित्र" },
  preparedness: { en: "Preparedness", ne: "तयारी" },
  leadTime: { en: "Lead time", ne: "पहुँच समय" },
  confidence: { en: "Confidence", ne: "विश्वास" },
  population: { en: "Population", ne: "जनसंख्या" },
  buildings: { en: "Buildings", ne: "भवनहरू" },
  bridges: { en: "Bridges", ne: "पुलहरू" },
  costPerRun: { en: "Cost per run", ne: "प्रति चालन लागत" },
  gate: { en: "Approval gate", ne: "स्वीकृति गेट" },
  trace: { en: "Trace", ne: "ट्रेस" },
  ask: { en: "Ask a follow-up question", ne: "थप प्रश्न सोध्नुहोस्" },
  counterfactuals: { en: "Counterfactuals", ne: "काल्पनिक परिस्थिति" },
  flipPoints: { en: "Flip points", ne: "फ्लिप बिन्दुहरू" },
  whatWouldChangeMyMind: { en: "What would change my mind", ne: "मेरो विचार के ले बदल्छ" },
  vetoed: { en: "No claim issued — insufficient evidence", ne: "कुनै दाबी जारी गरिएन — अपर्याप्त प्रमाण" },
  source: { en: "Source", ne: "स्रोत" },
  vintage: { en: "Vintage", ne: "मिति" },
  replay: { en: "REPLAY — NOT A REAL ALERT", ne: "रिप्ले — वास्तविक चेतावनी होइन" },
};

export function t(key: keyof typeof DICT, lang: Lang): string {
  return DICT[key]?.[lang] ?? key;
}
