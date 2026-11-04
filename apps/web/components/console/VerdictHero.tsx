"use client";

import { AnimatePresence, motion } from "motion/react";
import type { VerdictStatus } from "@/lib/api/types";
import { cn } from "@/components/ui/cn";
import { VERDICT_ACTION } from "@/lib/labels";
import { VERDICT_STYLE } from "./verdictStyle";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/**
 * The verdict, unmistakable from across a room: a big shape, the word, and what to do.
 * It crossfades only when the status changes, so re-evaluating to the same result does not flicker.
 */
export function VerdictHero({ status, computing }: { status: VerdictStatus; computing: boolean }) {
  const { Icon, solid } = VERDICT_STYLE[status];
  return (
    <div className="relative min-h-[10rem]" aria-busy={computing}>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.div
          key={status}
          role="status"
          aria-live="polite"
          aria-label={`Verdict ${status}. ${VERDICT_ACTION[status]}.`}
          initial={{ opacity: 0, scale: 0.985, filter: "blur(4px)" }}
          animate={{ opacity: computing ? 0.6 : 1, scale: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, filter: "blur(4px)", transition: { duration: 0.12 } }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
          className={cn("flex min-h-[10rem] items-center gap-6 rounded-panel px-6 py-6 sm:px-8", solid)}
        >
          <Icon weight="fill" aria-hidden className="size-16 shrink-0 sm:size-24" />
          <div className="min-w-0">
            <div className="text-6xl font-bold leading-none tracking-[-0.03em] sm:text-[5rem]">{status}</div>
            <p className="mt-2 text-lg font-semibold sm:text-xl">{VERDICT_ACTION[status]}</p>
          </div>
        </motion.div>
      </AnimatePresence>
      {computing && (
        <span className="absolute right-4 top-3 rounded-control bg-surface px-2 py-1 text-xs font-medium text-ink">Evaluating</span>
      )}
    </div>
  );
}
