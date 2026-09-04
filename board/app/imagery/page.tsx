"use client";

import { CloudOff, Radar, Satellite, SplitSquareHorizontal } from "lucide-react";
import { GeoLibreEmbed } from "@/components/GeoLibreEmbed";
import { CompletenessHeatmap } from "@/components/risk/CompletenessHeatmap";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";

const SCENES = [
  {
    label: "Pre-event",
    id: "10500100364E8400",
    date: "2023-09-17",
    sensor: "Vantor WorldView",
    cloud: "usable",
  },
  {
    label: "Post-event",
    id: "B040001100882F10",
    date: "2026-08-27",
    sensor: "Vantor WorldView",
    cloud: "79 percent cloud",
  },
];

export default function ImageryPage() {
  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Imagery"
        title="What the valley looked like before, and what it looks like now"
        lede="Real Vantor WorldView scenes either side of the 26 August 2026 event, swiped against each other, with our own modelled inundation raster and the ICIMOD lake inventory drawn on top."
      />

      <StatRow>
        <StatCard
          label="Scenes in the swipe"
          value={2}
          Icon={SplitSquareHorizontal}
          tint="blue"
          foot="streamed from S3, never downloaded"
        />
        <StatCard
          label="Cloud on post-event"
          value="79%"
          Icon={CloudOff}
          tint="amber"
          foot="the monsoon blindness argument"
        />
        <StatCard
          label="Comparable overlap"
          value="0.14 x 0.15"
          Icon={Satellite}
          tint="violet"
          foot="degrees where both scenes cover"
        />
        <StatCard
          label="Radar keeps working"
          value="always"
          Icon={Radar}
          tint="green"
          foot="which is why detection runs on it"
        />
      </StatRow>

      <div className="mt-4">
        <GeoLibreEmbed height={560} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.2fr]">
        <Section
          eyebrow="Provenance"
          title="The exact scenes used"
          note="Named on screen with their dates and cloud fraction, because a swipe that hides which scene you are looking at is not evidence."
        >
          <table className="w-full text-left text-[12.5px]">
            <thead className="bg-sunken">
              <tr>
                <th className="px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Scene
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Catalogue id
                </th>
                <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Date
                </th>
                <th className="px-5 py-2 text-right text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Usability
                </th>
              </tr>
            </thead>
            <tbody>
              {SCENES.map((scene) => (
                <tr key={scene.id} className="border-b last:border-0">
                  <td className="px-5 py-2.5 font-medium">{scene.label}</td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-ink-muted">{scene.id}</td>
                  <td className="px-3 py-2.5 font-mono text-[11.5px]">{scene.date}</td>
                  <td className="px-5 py-2.5 text-right text-ink-soft">{scene.cloud}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t px-5 py-3 text-[11.5px] leading-relaxed text-ink-muted">
            <p>
              The pre-event scene spans 28.108 to 28.261 north. The Lhende barrier sits at 28.271,
              above its top edge, so the blockage itself has post-event imagery only and cannot be
              swiped. The bookmarks are pinned to the box where both scenes actually overlap.
            </p>
            <p className="mt-1.5">
              Neither scene declares a nodata value or carries an alpha band, so the off-swath
              corners are genuine black pixels that no viewer can mask. That is a property of the
              source files, not of this rendering.
            </p>
            <p className="mt-1.5">
              Both post-event optical scenes are heavily clouded, which is the entire reason
              detection in this system runs on radar rather than optical.
            </p>
          </div>
        </Section>

        <CompletenessHeatmap />
      </div>
    </main>
  );
}
