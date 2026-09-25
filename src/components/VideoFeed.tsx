import { useState, useEffect } from "react";
import { AlertTriangle, Radio } from "lucide-react";
import crashPoster from "@/assets/crash_zone04.jpg";
import falseAlarmPoster from "@/assets/false_alarm.jpg";
import type { Incident, IncidentState } from "@/lib/aurashield/types";

const POSTERS: Record<string, string> = {
  "traffic_crash_zone04.mp4": crashPoster,
  "traffic_false_alarm.mp4": falseAlarmPoster,
};

function formatStateLabel(state: IncidentState): string {
  switch (state) {
    case "OBSERVED":
      return "Observed";
    case "CANDIDATE":
      return "Candidate";
    case "VERIFIED":
      return "Verified";
    case "RESPONSE_PROPOSED":
      return "Response proposed";
    case "OPERATOR_APPROVED":
      return "Operator approved";
    case "COORDINATION_IN_PROGRESS":
      return "Coordination in progress";
    case "ACKNOWLEDGED":
      return "Acknowledged";
    case "EN_ROUTE":
      return "En route";
    case "ON_SCENE":
      return "On scene";
    case "HANDED_OVER":
      return "Handed over";
    case "CLOSED":
      return "Closed";
    case "REJECTED":
      return "Rejected";
    default:
      return state;
  }
}

function getStateBadgeClass(state: IncidentState): string {
  switch (state) {
    case "OBSERVED":
    case "CANDIDATE":
      return "border-signal-pending text-signal-pending bg-signal-pending/10";
    case "VERIFIED":
    case "RESPONSE_PROPOSED":
    case "OPERATOR_APPROVED":
    case "COORDINATION_IN_PROGRESS":
      return "border-signal-verified text-signal-verified bg-signal-verified/10";
    case "REJECTED":
      return "border-signal-rejected text-signal-rejected bg-signal-rejected/10";
    case "ACKNOWLEDGED":
    case "EN_ROUTE":
    case "ON_SCENE":
    case "HANDED_OVER":
      return "border-emerald-500 text-emerald-400 bg-emerald-500/10";
    case "CLOSED":
      return "border-signal-closed text-text-muted bg-signal-closed/10";
    default:
      return "border-line text-text-muted bg-bg-panel-raised";
  }
}

export function VideoFeed({ incident }: { incident: Incident | null }) {
  const mediaFile = incident?.media_file;
  const poster = mediaFile ? POSTERS[mediaFile] : undefined;
  const [videoError, setVideoError] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    setVideoError(false);
    setIsPlaying(false);
  }, [mediaFile]);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded bg-bg-panel border border-line">
      {mediaFile ? (
        videoError ? (
          <img
            key={`poster-${mediaFile}`}
            src={poster}
            alt={incident?.zone ?? "Camera Feed"}
            className="h-full w-full object-cover opacity-80"
          />
        ) : (
          <video
            key={mediaFile}
            className="h-full w-full object-cover"
            src={`/media/${mediaFile}`}
            poster={poster}
            autoPlay
            muted
            loop
            playsInline
            onError={() => {
              setVideoError(true);
              setIsPlaying(false);
            }}
            onPlaying={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          />
        )
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center p-6 text-center">
          <p className="font-sans text-body text-text-muted">
            No active incident. Trigger a scenario to begin verification.
          </p>
        </div>
      )}

      {/* Subtle scanline overlay for camera sensor texture */}
      <div className="pointer-events-none absolute inset-0 scanlines opacity-50" />

      {/* Top-Left: System state badge & Live/No Signal Status */}
      <div className="absolute left-3 top-3 flex items-center gap-2">
        {incident && (
          <span
            className={`flex items-center gap-1.5 rounded border px-2 py-0.5 font-sans text-label font-medium ${getStateBadgeClass(
              incident.state
            )}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                incident.state === "REJECTED"
                  ? "bg-signal-rejected"
                  : incident.state === "OBSERVED" || incident.state === "CANDIDATE"
                  ? "bg-signal-pending animate-pulse"
                  : incident.state === "CLOSED" || incident.state === "ACKNOWLEDGED"
                  ? "bg-signal-closed"
                  : "bg-signal-verified animate-pulse"
              }`}
            />
            {formatStateLabel(incident.state)}
          </span>
        )}

        {/* Live feed vs NO SIGNAL fallback badge */}
        {mediaFile && (
          videoError || !isPlaying ? (
            <span className="flex items-center gap-1 rounded border border-signal-pending/60 bg-signal-pending/15 px-2 py-0.5 font-mono text-label font-medium text-signal-pending">
              <AlertTriangle className="h-3 w-3" />
              <span>NO SIGNAL · STILL POSTER</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded border border-signal-verified/60 bg-signal-verified/15 px-2 py-0.5 font-mono text-label font-medium text-signal-verified">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-verified animate-pulse" />
              <span>LIVE</span>
            </span>
          )
        )}
      </div>

      {/* Top-Right: Zone Telemetry */}
      <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded border border-line bg-bg-panel/90 px-2 py-0.5 font-mono text-label text-text-primary">
        <Radio className="h-3 w-3 text-text-muted" />
        <span>{incident?.zone ?? "Standby"}</span>
      </div>

      {/* Bottom telemetry overlay */}
      {incident && (
        <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded border border-line bg-bg-panel/90 px-2.5 py-1 font-mono text-label text-text-muted">
          <span className="text-text-primary">{incident.id}</span>
          <span className="text-line">|</span>
          <span>{new Date(incident.timestamp).toISOString().replace("T", " ").slice(0, 19)} UTC</span>
        </div>
      )}
    </div>
  );
}
