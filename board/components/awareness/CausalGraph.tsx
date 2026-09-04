"use client";

export const NON_ATTRIBUTION_BANNER =
  "These are documented general mechanisms in the scientific literature. They are not an " +
  "attribution of any specific flood. Attributing a single event requires dedicated " +
  "attribution study, which we have not done.";

type Strength = "established" | "supported" | "contested" | "local observation";

interface CausalEdge {
  from: string;
  to: string;
  strength: Strength;
  citation: string;
  note: string;
}

const STRENGTH_STYLE: Record<Strength, string> = {
  established: "border-emerald-300 bg-emerald-50 text-emerald-800",
  supported: "border-sky-300 bg-[--accent-soft] text-sky-800",
  contested: "border-amber-300 bg-amber-50 text-amber-800",
  "local observation": "border-line bg-sunken text-ink-soft",
};

const EDGES: CausalEdge[] = [
  {
    from: "Atmospheric warming",
    to: "Glacier retreat and thinning",
    strength: "established",
    citation: "IPCC AR6 WGI Ch.9; Bolch et al. 2019 HKH Assessment",
    note: "Long-term mass loss across the Hindu Kush Himalaya is well documented.",
  },
  {
    from: "Glacier retreat and thinning",
    to: "Growth of glacial lakes",
    strength: "established",
    citation: "Shugar et al. 2020, Nature Climate Change 10:939",
    note: "Global glacial lake area and volume grew substantially 1990-2018.",
  },
  {
    from: "Growth of glacial lakes",
    to: "More people living below larger lakes",
    strength: "supported",
    citation: "Taylor et al. 2023, Nature Communications 14:487",
    note: "Exposure has risen because both lake extent and downstream population increased.",
  },
  {
    from: "Atmospheric warming",
    to: "More frequent GLOFs in the Himalaya",
    strength: "contested",
    citation: "Veh et al. 2019, Nature Climate Change 9:379; HMAGLOFDB documentation",
    note:
      "Veh et al. found no detectable increase in moraine-dammed GLOF frequency in the " +
      "Himalaya, and the HMAGLOFDB compilers describe the evidence as ambiguous. What is " +
      "supported instead is that exposure has increased.",
  },
  {
    from: "Permafrost degradation on steep rock walls",
    to: "Rock and ice slope failure",
    strength: "supported",
    citation: "Gruber and Haeberli 2007, JGR Earth Surface 112:F02S18",
    note: "Warming of frozen bedrock reduces slope stability at high elevation.",
  },
  {
    from: "Rock and ice slope failure",
    to: "River blockage and barrier lake",
    strength: "local observation",
    citation: "USGS ANSS event catalogue, landslide-type classification",
    note:
      "A documented mechanism by which a slope failure can impound a channel. Whether it " +
      "operated in any particular event is a question for a dedicated study, not for this panel.",
  },
  {
    from: "River blockage and barrier lake",
    to: "Outburst surge downstream",
    strength: "established",
    citation: "Costa and Schuster 1988, GSA Bulletin 100:1054",
    note: "Landslide dams are known to fail, most often by overtopping and breach incision.",
  },
];

function Edge({ edge }: { edge: CausalEdge }) {
  return (
    <li className={`rounded border p-3 ${STRENGTH_STYLE[edge.strength]}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium text-ink">{edge.from}</span>
        <span className="text-ink-faint">→</span>
        <span className="font-medium text-ink">{edge.to}</span>
        <span className="ml-auto rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
          {edge.strength}
        </span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-ink-muted">{edge.note}</p>
      <p className="mt-1 text-[10px] text-ink-faint">{edge.citation}</p>
    </li>
  );
}

export function CausalGraph() {
  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Documented mechanisms
      </h2>

      <div
        role="note"
        className="mt-2 rounded border border-amber-300 bg-amber-50 p-3 text-[11px] leading-relaxed text-amber-900"
      >
        {NON_ATTRIBUTION_BANNER}
      </div>

      <ul className="mt-3 space-y-2">
        {EDGES.map((edge) => (
          <Edge key={`${edge.from}-${edge.to}`} edge={edge} />
        ))}
      </ul>

      <p className="mt-3 border-t border-line pt-3 text-[11px] text-ink-faint">
        Edge strength is labelled, not averaged. One edge is marked contested because the
        literature genuinely disagrees, and this panel shows that disagreement rather than
        resolving it.
      </p>
    </section>
  );
}
