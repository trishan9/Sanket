"use client";

import { Layers, MoveHorizontal } from "lucide-react";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_SANKET_API || "http://127.0.0.1:5000";

const BOOKMARKS: { id: string; label: string; hint: string }[] = [
  { id: "overlap_extent", label: "Full comparable extent", hint: "everywhere both scenes cover" },
  { id: "syapru_besi", label: "Syapru Besi", hint: "settlement inside the overlap" },
  { id: "upper_reach", label: "Upper reach", hint: "northern edge of the overlap" },
];

export function GeoLibreEmbed({ height = 520 }: { height?: number }) {
  const [bookmark, setBookmark] = useState(BOOKMARKS[1]!.id);

  const projectUrl = `${API_BASE}/data/sanket.${bookmark}.geolibre.json`;
  const iframeSrc = `${API_BASE}/geolibre/?project_url=${encodeURIComponent(projectUrl)}`;

  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <div>
          <div className="label flex items-center gap-1.5">
            <MoveHorizontal size={11} /> Drag the handle to swipe
          </div>
          <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
            Before and after, with our modelled inundation on top
          </div>
        </div>
        <div className="flex flex-wrap gap-1 rounded-md border p-1">
          {BOOKMARKS.map((item) => (
            <button
              key={item.id}
              onClick={() => setBookmark(item.id)}
              title={item.hint}
              className={`rounded px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
                bookmark === item.id ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <iframe
        key={bookmark}
        src={iframeSrc}
        title="GeoLibre corridor map"
        className="w-full border-0"
        style={{ height }}
        allow="fullscreen"
      />

      <div className="card-note">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="inline-flex items-center gap-1.5 font-semibold">
            <Layers size={12} /> 4 layers
          </span>
          <span>Vantor WorldView pre-event 2023-09-17 and post-event 2026-08-27, streamed from S3</span>
          <span>our modelled peak rise, 1.0 Mm3 over 30 min</span>
          <span>60 ICIMOD glacial lake polygons</span>
        </div>
        <p className="mt-1.5">
          The two scenes only overlap between 85.27 and 85.41 east, 28.11 and 28.26 north, so every
          bookmark sits inside that box. The Lhende barrier at 28.271 north falls outside the
          pre-event scene entirely and cannot be compared before and after with this imagery.
          Both post-event scenes also carry 79 percent cloud. Neither limitation is hidden here,
          because they are the monsoon blindness argument this system rests on. GeoLibre by
          Qiusheng Wu and opengeos, self hosted so this panel keeps working offline.
        </p>
      </div>
    </section>
  );
}
