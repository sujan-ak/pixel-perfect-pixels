import { useEffect, useState } from "react";
import { History, RefreshCw } from "lucide-react";
import type { Incident, IncidentState } from "@/lib/aurashield/types";

const API_URL = (import.meta.env["VITE_API_URL"] as string | undefined) || "http://localhost:8000";

function formatStateLabel(state: IncidentState): string {
  switch (state) {
    case "CLOSED":
      return "Closed";
    case "REJECTED":
      return "Rejected";
    case "ACKNOWLEDGED":
      return "Acknowledged";
    default:
      return state;
  }
}

export function IncidentHistory({ currentIncidentState }: { currentIncidentState?: IncidentState | null }) {
  const [history, setHistory] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchHistory = async () => {
    if (!API_URL) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/incidents/history`);
      if (res.ok) {
        const data = (await res.json()) as Incident[];
        setHistory(data);
      }
    } catch {
      /* ignore fetch failure in mock mode */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [currentIncidentState]);

  return (
    <div className="rounded border border-line bg-bg-panel flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-text-muted" />
          <span className="font-sans text-panel-header text-text-primary">Incident history</span>
          <span className="font-sans text-label text-text-muted">/ terminal records</span>
        </div>

        <button
          onClick={fetchHistory}
          disabled={loading}
          className="flex items-center gap-1.5 rounded border border-line bg-bg-panel-raised px-2 py-0.5 font-sans text-label text-text-muted transition-colors hover:text-text-primary hover:border-text-muted disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Compact Table */}
      <div className="max-h-48 overflow-y-auto font-mono text-label leading-relaxed">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 border-b border-line bg-bg-panel-raised/95 backdrop-blur font-sans text-label text-text-muted">
            <tr>
              <th className="py-1.5 pl-4 pr-2 font-normal w-24">Incident ID</th>
              <th className="py-1.5 px-2 font-normal w-28">Zone</th>
              <th className="py-1.5 px-2 font-normal w-36">Scenario</th>
              <th className="py-1.5 px-2 font-normal w-28">Outcome</th>
              <th className="py-1.5 px-2 font-normal w-24">Fused</th>
              <th className="py-1.5 pl-2 pr-4 font-normal text-right">Resolved at (UTC)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/40">
            {history.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-5 text-center text-text-muted font-sans text-body">
                  No resolved incidents in history yet
                </td>
              </tr>
            ) : (
              history.map((item) => (
                <tr key={item.id} className="hover:bg-bg-panel-raised/60 transition-colors">
                  <td className="py-1.5 pl-4 pr-2 text-text-primary font-medium">{item.id}</td>
                  <td className="py-1.5 px-2 text-text-muted font-sans">{item.zone}</td>
                  <td className="py-1.5 px-2 text-text-muted font-mono">{item.scenario}</td>
                  <td className="py-1.5 px-2">
                    <span
                      className={`inline-flex items-center rounded border px-1.5 py-0.2 font-sans text-label ${
                        item.state === "CLOSED"
                          ? "border-signal-closed text-text-muted bg-signal-closed/10"
                          : "border-signal-rejected text-signal-rejected bg-signal-rejected/10"
                      }`}
                    >
                      {formatStateLabel(item.state as IncidentState)}
                    </span>
                  </td>
                  <td className="py-1.5 px-2 text-signal-data font-medium">
                    {item.fused_score > 0 ? `+${item.fused_score.toFixed(2)}` : item.fused_score.toFixed(2)}
                  </td>
                  <td className="py-1.5 pl-2 pr-4 text-right text-text-muted">
                    {new Date(item.timestamp).toISOString().replace("T", " ").slice(0, 19)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
