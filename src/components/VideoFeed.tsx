import { motion } from "framer-motion";
import { Radio } from "lucide-react";
import crashPoster from "@/assets/crash_zone04.jpg";
import falseAlarmPoster from "@/assets/false_alarm.jpg";
import type { Incident } from "@/lib/aurashield/types";

const POSTERS: Record<string, string> = {
  "traffic_crash_zone04.mp4": crashPoster,
  "traffic_false_alarm.mp4": falseAlarmPoster,
};

export function VideoFeed({ incident }: { incident: Incident | null }) {
  const mediaFile = incident?.media_file;
  const poster = mediaFile ? POSTERS[mediaFile] : undefined;

  return (
    <div className="panel relative aspect-video w-full overflow-hidden">
      {mediaFile ? (
        <video
          key={mediaFile}
          className="h-full w-full object-cover"
          src={`/media/${mediaFile}`}
          poster={poster}
          autoPlay
          muted
          loop
          playsInline
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center font-mono text-xs tracking-[0.2em] text-neutral">
          NO ACTIVE FEED
        </div>
      )}
      <div className="pointer-events-none absolute inset-0 scanlines" />

      <div className="absolute left-3 top-3 flex items-center gap-2 rounded-md border border-critical/60 bg-background/70 px-2 py-1">
        <motion.span
          className="h-2 w-2 rounded-full bg-critical"
          animate={{ opacity: [1, 0.2, 1] }}
          transition={{ duration: 1.4, repeat: Infinity }}
        />
        <span className="font-mono text-[11px] tracking-widest text-critical">LIVE</span>
      </div>

      <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md border border-border bg-background/70 px-2 py-1 font-mono text-[11px] text-foreground">
        <Radio className="h-3 w-3 text-muted-foreground" />
        {incident?.zone ?? "—"}
      </div>

      {incident && (
        <div className="absolute bottom-3 left-3 rounded-md border border-border bg-background/70 px-2 py-1 font-mono text-[10px] text-muted-foreground">
          {incident.id} · {new Date(incident.timestamp).toUTCString().slice(17, 25)} UTC
        </div>
      )}
    </div>
  );
}
