import { createFileRoute } from "@tanstack/react-router";
import { ControlRoom } from "@/components/ControlRoom";

const title = "AuraShield — Incident Verification Control Room";
const description =
  "Real-time control room for AI-verified traffic incidents: agent scoring, operator dispatch clearance, and a tamper-evident audit ledger.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ControlRoom,
});
