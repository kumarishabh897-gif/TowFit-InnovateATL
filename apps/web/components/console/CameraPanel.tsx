"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { classifyFrame, useCameraFrames } from "@/lib/api/hooks";
import { imageUrl } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { ProvenanceChip } from "@/components/ui/ProvenanceChip";
import { useConsole } from "@/lib/store";

export const SIM_LABEL = "SIM classification (demo fixture, not a live model)";

/**
 * The camera stub (brief section 5.6): canned frames mapped by hand to a vehicle. No computer vision runs here,
 * and everything it fills in is tagged SIM.
 */
export function CameraPanel({ onDone }: { onDone: () => void }) {
  const frames = useCameraFrames(true);
  const apply = useConsole((s) => s.applyProfile);
  const mutation = useMutation({
    mutationFn: classifyFrame,
    onSuccess: (result) => {
      apply(result.vehicle);
      toast.success("Vehicle filled from a demo frame", { description: SIM_LABEL });
      onDone();
    },
    onError: (error) => toast.error("Could not classify the frame", { description: error.message }),
  });

  return (
    <div className="rounded-panel border border-line bg-sunken p-3">
      <p className="mb-2.5 flex items-center gap-2 text-xs text-ink-2">
        <ProvenanceChip provenance="SIM" />
        Demo fixtures, not a live camera. Pick a frame to fill the vehicle fields.
      </p>
      {frames.isPending && <p className="text-sm text-ink-3">Loading frames</p>}
      {frames.isError && <p className="text-sm text-stop-ink">Frames unavailable: {frames.error.message}</p>}
      <ul className="grid grid-cols-2 gap-2.5">
        {frames.data?.map((frame) => (
          <li key={frame.id} className="overflow-hidden rounded-control border border-line bg-surface">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={imageUrl(frame.image_url)} alt={frame.caption} className="aspect-video w-full object-cover" />
            <div className="flex items-center justify-between gap-2 px-2.5 py-2">
              <span className="text-xs text-ink-2">{frame.caption.replace("Demo frame ", "Frame ")}</span>
              <Button size="sm" variant="secondary" disabled={mutation.isPending} onClick={() => mutation.mutate(frame.id)}>
                Classify
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
