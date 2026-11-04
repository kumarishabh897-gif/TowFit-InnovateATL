"use client";

import { Moon, PlugsConnected, Sun, WifiSlash } from "@phosphor-icons/react";
import { useMutation } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { SelectField } from "@/components/ui/SelectField";
import { loadScenario, useFleet, useHealth, useScenarios } from "@/lib/api/hooks";
import { lb } from "@/lib/format";
import { SCENARIO_SHORT } from "@/lib/labels";
import { useConsole } from "@/lib/store";

type Theme = "light" | "dark";

/** The theme in effect: the saved choice on <html>, else the system setting. Follows both as they change. */
function useTheme(): Theme {
  return useSyncExternalStore(
    (notify) => {
      const observer = new MutationObserver(notify);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      const media = window.matchMedia("(prefers-color-scheme: dark)");
      media.addEventListener("change", notify);
      return () => {
        observer.disconnect();
        media.removeEventListener("change", notify);
      };
    },
    () => {
      const saved = document.documentElement.dataset.theme;
      if (saved === "dark" || saved === "light") return saved;
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    },
    () => "light",
  );
}

function ThemeToggle() {
  const theme = useTheme();
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="ghost"
      size="md"
      aria-label={`Switch to ${next} theme`}
      onClick={() => {
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("towfit-theme", next);
        } catch {}
      }}
    >
      {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </Button>
  );
}

function ApiStatus() {
  const health = useHealth();
  const ok = health.isSuccess;
  return (
    <span
      role="status"
      className={cn("inline-flex items-center gap-1.5 rounded-control px-2 py-1 text-xs font-medium", ok ? "text-ink-2" : "bg-stop-soft text-stop-ink")}
    >
      {ok ? <PlugsConnected size={16} aria-hidden /> : <WifiSlash size={16} aria-hidden />}
      {health.isPending ? "Connecting" : ok ? "API connected" : "API offline"}
    </span>
  );
}

export function TopBar() {
  const fleet = useFleet();
  const scenarios = useScenarios();
  const unitId = useConsole((s) => s.unitId);
  const scenario = useConsole((s) => s.scenario);
  const draft = useConsole((s) => s.draft);
  const selectUnit = useConsole((s) => s.selectUnit);
  const startManual = useConsole((s) => s.startManual);
  const load = useConsole((s) => s.loadScenario);
  const load_ = useMutation({
    mutationFn: loadScenario,
    onSuccess: load,
    onError: (error) => toast.error("Could not load the scenario", { description: error.message }),
  });

  return (
    <header className="flex flex-wrap items-end gap-x-6 gap-y-3 border-b border-line bg-surface px-4 py-3 lg:px-6">
      <div className="mr-2 pb-1">
        <div className="text-lg font-bold leading-none tracking-tight text-ink">TowFit</div>
        <div className="mt-1 text-xs text-ink-3">ClearanceOS</div>
      </div>

      <div className="w-56">
        <label htmlFor="unit-select" className="mb-1.5 block text-xs font-medium text-ink-2">
          Patrol unit
        </label>
        <SelectField
          id="unit-select"
          value={unitId}
          placeholder="Choose a unit"
          onChange={selectUnit}
          options={(fleet.data ?? []).map((u) => ({
            value: u.unit.unit_id,
            label: u.unit.unit_id,
            description: `Rig rated ${lb(u.unit.rig_capacity_lb)}`,
          }))}
        />
      </div>

      <div>
        <div className="mb-1.5 text-xs font-medium text-ink-2">Start from</div>
        <div role="group" aria-label="Scenario" className="flex flex-wrap gap-1.5">
          {scenarios.data?.map((s) => {
            const active = scenario?.id === s.id;
            return (
              <Button
                key={s.id}
                variant={active ? "primary" : "secondary"}
                aria-pressed={active}
                disabled={load_.isPending}
                onClick={() => load_.mutate(s.id)}
                title={s.description}
              >
                <span className="tnum font-semibold">{SCENARIO_SHORT[s.id] ?? "#"}</span>
                <span className="hidden xl:inline">{s.title.replace(/^Scenario \d+: /, "")}</span>
                <span className="sr-only xl:hidden">{s.title}</span>
              </Button>
            );
          })}
          <Button variant={draft && !scenario ? "primary" : "secondary"} aria-pressed={!!draft && !scenario} onClick={startManual}>
            Enter manually
          </Button>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-1 pb-0.5">
        <ApiStatus />
        <ThemeToggle />
      </div>
    </header>
  );
}
