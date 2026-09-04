"use client";

import {
  Activity,
  Bot,
  BellRing,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  Layers,
  ListTree,
  Radar,
  ShieldCheck,
  SplitSquareHorizontal,
  Waypoints,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchSnapshot } from "@/lib/api";
import type { BoardSnapshot } from "@/lib/types";

type IconType = typeof Radar;

interface NavItem {
  href: string;
  label: string;
  hint: string;
  Icon: IconType;
}

const PRIMARY: NavItem[] = [
  { href: "/", label: "Standing watch", hint: "Live corridor status", Icon: Radar },
  { href: "/alerts", label: "Alerts", hint: "Multi-step escalation", Icon: BellRing },
  { href: "/predict", label: "Prediction", hint: "Hazard probability", Icon: Activity },
  { href: "/analysis", label: "Root cause", hint: "Attribution graph", Icon: Waypoints },
  { href: "/simulate", label: "Simulate", hint: "Run a breach", Icon: FlaskConical },
  { href: "/agents", label: "Agents", hint: "What each agent does", Icon: Bot },
  { href: "/imagery", label: "Imagery", hint: "Before and after swipe", Icon: SplitSquareHorizontal },
];

const SECONDARY: NavItem[] = [
  { href: "/preparedness", label: "Preparedness", hint: "Exposure and lead time", Icon: ShieldCheck },
  { href: "/gov", label: "Technical", hint: "Risk engine dashboard", Icon: LayoutDashboard },
  { href: "/pipeline", label: "How it works", hint: "Data and agents", Icon: Workflow },
  { href: "/trace", label: "Trace", hint: "Agent runs", Icon: ListTree },
  { href: "/gate", label: "Approvals", hint: "Human in the loop", Icon: GitBranch },
  { href: "/build", label: "Build", hint: "Phase log", Icon: Layers },
];

const LEVEL_DOT: Record<string, string> = {
  NORMAL: "bg-level-green",
  GREEN: "bg-level-green",
  WATCH: "bg-level-yellow",
  YELLOW: "bg-level-yellow",
  ORANGE: "bg-level-orange",
  ALERT: "bg-level-red",
  RED: "bg-level-red",
  INSUFFICIENT: "bg-level-grey",
  GREY: "bg-level-grey",
};

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const { Icon } = item;
  return (
    <Link
      href={item.href}
      className={`group flex items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
        active ? "bg-accent text-white shadow-sm" : "text-ink-soft hover:bg-[--surface-sunken]"
      }`}
    >
      <Icon
        size={17}
        strokeWidth={active ? 2.2 : 1.8}
        className={active ? "text-white" : "text-ink-faint group-hover:text-ink-muted"}
      />
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-medium leading-tight">{item.label}</span>
        <span
          className={`block truncate text-[10.5px] leading-tight ${
            active ? "text-white/75" : "text-ink-faint"
          }`}
        >
          {item.hint}
        </span>
      </span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [snapshot, setSnapshot] = useState<BoardSnapshot | null>(null);

  useEffect(() => {
    const load = () => void fetchSnapshot().then(setSnapshot);
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  const level = snapshot?.corridor_level ?? null;

  return (
    <aside className="sticky top-0 hidden h-screen w-[236px] shrink-0 flex-col border-r bg-[--surface] xl:flex">
      <div className="border-b px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-white">
            <Radar size={16} strokeWidth={2.2} />
          </span>
          <span className="text-[16px] font-semibold tracking-[-0.01em]">SANKET</span>
          <span className="nepali text-[14px] text-ink-muted">संकेत</span>
        </div>
      </div>

      <div className="border-b px-5 py-3.5">
        <div className="label">Corridor status</div>
        <div className="mt-1.5 flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              level ? (LEVEL_DOT[level] ?? "bg-level-grey") : "bg-[--line-strong]"
            }`}
          />
          <span className="text-[14px] font-semibold">{level ?? "connecting"}</span>
        </div>
        <div className="mt-1 text-[10.5px] text-ink-faint">
          Bhotekoshi Trishuli, {snapshot?.settlements.length ?? 0} settlements
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        <div className="space-y-0.5">
          {PRIMARY.map((item) => (
            <NavLink key={item.href} item={item} active={pathname === item.href} />
          ))}
        </div>
        <div className="mt-4 px-3 pb-1.5">
          <div className="label">Operations</div>
        </div>
        <div className="space-y-0.5">
          {SECONDARY.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname === item.href || pathname.startsWith(`${item.href}/`)}
            />
          ))}
        </div>
      </nav>

      <div className="border-t px-5 py-3.5">
        <p className="text-[10px] leading-relaxed text-ink-faint">
          No human input path exists to start a run. Nothing above WATCH is released without a
          named district officer.
        </p>
      </div>
    </aside>
  );
}
