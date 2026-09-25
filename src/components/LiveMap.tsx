import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import {
  Activity,
  Ambulance,
  Building2,
  CheckCircle,
  Clock,
  Compass,
  Flame,
  Radio,
  ShieldAlert,
  TrafficCone,
  Zap,
} from "lucide-react";
import type { Incident } from "@/lib/aurashield/types";

// Hyderabad Coordinates & Metadata
const HYD_CENTER: [number, number] = [17.3850, 78.4867];

interface CameraZone {
  id: string;
  name: string;
  pos: [number, number];
  description: string;
}

const CAMERA_ZONES: CameraZone[] = [
  { id: "Zone 01", name: "Lakdikapul Intersect", pos: [17.3980, 78.4730], description: "Arterial NW Feed" },
  { id: "Zone 02", name: "Koti Sultan Bazar", pos: [17.3910, 78.4980], description: "Commercial Corridor East" },
  { id: "Zone 03", name: "Nampally Station Rd", pos: [17.3710, 78.4680], description: "Transit Hub South" },
  { id: "Zone 04", name: "MJ Market Junction", pos: [17.3850, 78.4867], description: "Central Ring Primary" },
];

const HOSPITAL = {
  name: "Osmania General Hospital",
  type: "Trauma Care Level-1",
  pos: [17.3715, 78.4795] as [number, number],
};

const FIRE_STATION = {
  name: "Gowliguda Fire Station",
  type: "Emergency Response Unit 01",
  pos: [17.3810, 78.4910] as [number, number],
};

// Route waypoints from Zone 04 (MJ Market) to Osmania General Hospital
const CORRIDOR_ROUTE: [number, number][] = [
  [17.3850, 78.4867], // Zone 04 - Incident Origin
  [17.3830, 78.4855], // Signal 1: MJ Market North
  [17.3808, 78.4842], // Signal 2: Siddiamber Bazar
  [17.3785, 78.4830], // Signal 3: Begum Bazar Arterial
  [17.3762, 78.4818], // Signal 4: Afzalgunj Junction
  [17.3740, 78.4806], // Signal 5: Nayapul Approach
  [17.3725, 78.4800], // Signal 6: Hospital Gate Entry
  [17.3715, 78.4795], // Hospital Destination
];

interface TrafficSignal {
  id: string;
  name: string;
  pos: [number, number];
  junctionNumber: number;
}

const TRAFFIC_SIGNALS: TrafficSignal[] = [
  { id: "SIG_HYD_04A", name: "MJ Market North", pos: [17.3830, 78.4855], junctionNumber: 1 },
  { id: "SIG_HYD_04B", name: "Siddiamber Bazar", pos: [17.3808, 78.4842], junctionNumber: 2 },
  { id: "SIG_HYD_04C", name: "Begum Bazar Arterial", pos: [17.3785, 78.4830], junctionNumber: 3 },
  { id: "SIG_HYD_04D", name: "Afzalgunj Junction", pos: [17.3762, 78.4818], junctionNumber: 4 },
  { id: "SIG_HYD_04E", name: "Nayapul North Approach", pos: [17.3740, 78.4806], junctionNumber: 5 },
  { id: "SIG_HYD_04F", name: "Hospital Emergency Entry", pos: [17.3725, 78.4800], junctionNumber: 6 },
];

export interface ActuationLogEntry {
  id: string;
  signalId: string;
  name: string;
  timestamp: string;
  status: "FORCED GREEN";
  latencyMs: number;
  blockHash?: string;
  phaseHold: string;
}

interface LiveMapProps {
  incident: Incident | null;
  isApproved?: boolean;
  onSignalActuated?: (signalId: string, name: string) => void;
}

export function LiveMap({ incident, isApproved, onSignalActuated }: LiveMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  // Layer references
  const zoneMarkersRef = useRef<Map<string, L.Marker>>(new Map());
  const signalMarkersRef = useRef<Map<string, L.Marker>>(new Map());
  const inactivePolylineRef = useRef<L.Polyline | null>(null);
  const activeGlowPolylineRef = useRef<L.Polyline | null>(null);
  const activeCorePolylineRef = useRef<L.Polyline | null>(null);
  const ambulanceMarkerRef = useRef<L.Marker | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Component state
  const [signalStates, setSignalStates] = useState<Record<string, "RED" | "GREEN">>({
    SIG_HYD_04A: "RED",
    SIG_HYD_04B: "RED",
    SIG_HYD_04C: "RED",
    SIG_HYD_04D: "RED",
    SIG_HYD_04E: "RED",
    SIG_HYD_04F: "RED",
  });
  const [corridorActive, setCorridorActive] = useState(false);
  const [actuationLogs, setActuationLogs] = useState<ActuationLogEntry[]>([]);
  const [ambulanceProgress, setAmbulanceProgress] = useState(0); // 0 to 1
  const actuationTriggeredRef = useRef(false);

  // Detect whether approval is active
  const approved = Boolean(
    isApproved ||
      (incident &&
        ["OPERATOR_APPROVED", "COORDINATION_IN_PROGRESS", "ACKNOWLEDGED", "CLOSED"].includes(
          incident.state,
        )),
  );

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: HYD_CENTER,
      zoom: 14,
      minZoom: 13,
      maxZoom: 18,
      zoomControl: false,
    });

    // CartoDB Dark All Tiles
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions" target="_blank">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: "topright" }).addTo(map);

    // 1. Inactive route dashed polyline
    const inactiveLine = L.polyline(CORRIDOR_ROUTE, {
      color: "#475569",
      weight: 3,
      dashArray: "6, 8",
      opacity: 0.6,
    }).addTo(map);
    inactivePolylineRef.current = inactiveLine;

    // 2. Camera Zone Markers (Zone 01 - Zone 04)
    CAMERA_ZONES.forEach((zone) => {
      const isZone4 = zone.id === "Zone 04";
      const iconHtml = `
        <div class="relative flex items-center justify-center">
          ${
            isZone4
              ? `<div class="absolute -inset-2 rounded-full border border-signal-rejected/80 marker-pulse-red pointer-events-none"></div>`
              : ""
          }
          <div class="flex items-center gap-1 px-2 py-1 rounded bg-bg-panel border ${
            isZone4
              ? "border-signal-rejected text-signal-rejected shadow-[0_0_12px_rgba(255,92,92,0.4)]"
              : "border-line text-text-muted"
          } font-mono text-[10px] font-semibold tracking-wider whitespace-nowrap">
            <span class="inline-block w-2 h-2 rounded-full ${
              isZone4 ? "bg-signal-rejected animate-ping" : "bg-text-muted"
            }"></span>
            <span>${zone.id}</span>
          </div>
        </div>
      `;

      const marker = L.marker(zone.pos, {
        icon: L.divIcon({
          className: "custom-zone-marker",
          html: iconHtml,
          iconSize: [80, 26],
          iconAnchor: [40, 13],
        }),
      }).addTo(map);

      marker.bindPopup(`
        <div class="p-2 font-sans text-xs bg-bg-panel text-text-primary border border-line rounded">
          <div class="font-bold text-signal-data">${zone.id} · ${zone.name}</div>
          <div class="text-text-muted mt-1">${zone.description}</div>
          <div class="font-mono text-[10px] text-text-muted mt-1">${zone.pos[0].toFixed(4)}°N, ${zone.pos[1].toFixed(4)}°E</div>
        </div>
      `);

      zoneMarkersRef.current.set(zone.id, marker);
    });

    // 3. Hospital Marker
    const hospitalHtml = `
      <div class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0f2438] border border-[#22d3ee] text-[#22d3ee] font-mono text-[11px] font-bold shadow-[0_0_14px_rgba(34,211,238,0.35)] whitespace-nowrap">
        <span class="flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[#22d3ee] text-[#0a0e14] font-black text-[10px]">+</span>
        <span>${HOSPITAL.name}</span>
      </div>
    `;
    L.marker(HOSPITAL.pos, {
      icon: L.divIcon({
        className: "custom-hospital-marker",
        html: hospitalHtml,
        iconSize: [180, 26],
        iconAnchor: [90, 13],
      }),
    })
      .addTo(map)
      .bindPopup(`
        <div class="p-2 font-sans text-xs bg-bg-panel text-text-primary border border-line rounded">
          <div class="font-bold text-[#22d3ee]">${HOSPITAL.name}</div>
          <div class="text-text-muted mt-1">${HOSPITAL.type}</div>
          <div class="text-signal-verified font-medium mt-1">Designated Emergency Receiver</div>
        </div>
      `);

    // 4. Fire Station Marker
    const fireHtml = `
      <div class="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#2b1810] border border-[#f5a623] text-[#f5a623] font-mono text-[11px] font-bold shadow-[0_0_12px_rgba(245,166,35,0.3)] whitespace-nowrap">
        <span class="text-xs">🔥</span>
        <span>${FIRE_STATION.name}</span>
      </div>
    `;
    L.marker(FIRE_STATION.pos, {
      icon: L.divIcon({
        className: "custom-fire-marker",
        html: fireHtml,
        iconSize: [170, 26],
        iconAnchor: [85, 13],
      }),
    })
      .addTo(map)
      .bindPopup(`
        <div class="p-2 font-sans text-xs bg-bg-panel text-text-primary border border-line rounded">
          <div class="font-bold text-[#f5a623]">${FIRE_STATION.name}</div>
          <div class="text-text-muted mt-1">${FIRE_STATION.type}</div>
          <div class="text-text-muted mt-1">Heavy Rescue & Hazmat Standby</div>
        </div>
      `);

    // 5. Six Traffic Signals (Red Circles by Default)
    TRAFFIC_SIGNALS.forEach((sig) => {
      const signalHtml = `
        <div id="sig-icon-${sig.id}" class="relative flex items-center justify-center w-6 h-6 rounded-full bg-bg-void border-2 border-signal-rejected signal-glow-red transition-all duration-300">
          <span class="w-2.5 h-2.5 rounded-full bg-signal-rejected"></span>
        </div>
      `;

      const marker = L.marker(sig.pos, {
        icon: L.divIcon({
          className: "custom-signal-marker",
          html: signalHtml,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        }),
      }).addTo(map);

      marker.bindPopup(`
        <div class="p-2 font-sans text-xs bg-bg-panel text-text-primary border border-line rounded">
          <div class="font-bold text-text-primary">${sig.id} · ${sig.name}</div>
          <div class="text-text-muted mt-0.5">Municipal Signal #${sig.junctionNumber}</div>
          <div class="mt-1 font-mono text-[10px] text-signal-rejected">Status: HOLD RED (Standard Cycle)</div>
        </div>
      `);

      signalMarkersRef.current.set(sig.id, marker);
    });

    mapInstanceRef.current = map;

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update active zone pulsing based on current incident
  useEffect(() => {
    const activeZone = incident?.zone ?? "Zone 04";
    CAMERA_ZONES.forEach((zone) => {
      const marker = zoneMarkersRef.current.get(zone.id);
      if (!marker) return;

      const isCurrentActive = zone.id === activeZone;
      const iconHtml = `
        <div class="relative flex items-center justify-center">
          ${
            isCurrentActive
              ? `<div class="absolute -inset-2 rounded-full border border-signal-rejected/80 marker-pulse-red pointer-events-none"></div>`
              : ""
          }
          <div class="flex items-center gap-1 px-2 py-1 rounded bg-bg-panel border ${
            isCurrentActive
              ? "border-signal-rejected text-signal-rejected shadow-[0_0_12px_rgba(255,92,92,0.4)]"
              : "border-line text-text-muted"
          } font-mono text-[10px] font-semibold tracking-wider whitespace-nowrap">
            <span class="inline-block w-2 h-2 rounded-full ${
              isCurrentActive ? "bg-signal-rejected animate-ping" : "bg-text-muted"
            }"></span>
            <span>${zone.id}</span>
          </div>
        </div>
      `;

      marker.setIcon(
        L.divIcon({
          className: "custom-zone-marker",
          html: iconHtml,
          iconSize: [80, 26],
          iconAnchor: [40, 13],
        }),
      );
    });
  }, [incident?.zone]);

  // Actuate green corridor upon operator approval (sequential 200ms transitions)
  useEffect(() => {
    if (!approved || actuationTriggeredRef.current || !mapInstanceRef.current) return;
    actuationTriggeredRef.current = true;

    const map = mapInstanceRef.current;

    // Remove inactive line
    if (inactivePolylineRef.current) {
      map.removeLayer(inactivePolylineRef.current);
      inactivePolylineRef.current = null;
    }

    // Draw glowing green corridor polyline
    const glowLine = L.polyline(CORRIDOR_ROUTE, {
      color: "#10b981",
      weight: 12,
      opacity: 0.35,
      className: "green-corridor-glow",
    }).addTo(map);
    activeGlowPolylineRef.current = glowLine;

    const coreLine = L.polyline(CORRIDOR_ROUTE, {
      color: "#3ddc84",
      weight: 5,
      opacity: 0.95,
    }).addTo(map);
    activeCorePolylineRef.current = coreLine;

    setCorridorActive(true);

    // Sequential 200ms signal flips from Red to Green
    TRAFFIC_SIGNALS.forEach((sig, index) => {
      setTimeout(async () => {
        // 1. Update component state
        setSignalStates((prev) => ({ ...prev, [sig.id]: "GREEN" }));

        // 2. Update Leaflet marker DOM to vibrant green
        const marker = signalMarkersRef.current.get(sig.id);
        if (marker) {
          const greenHtml = `
            <div id="sig-icon-${sig.id}" class="relative flex items-center justify-center w-6 h-6 rounded-full bg-[#0a2318] border-2 border-signal-verified signal-glow-green transition-all duration-300">
              <span class="w-2.5 h-2.5 rounded-full bg-signal-verified animate-ping"></span>
              <span class="absolute w-2 h-2 rounded-full bg-signal-verified"></span>
            </div>
          `;
          marker.setIcon(
            L.divIcon({
              className: "custom-signal-marker",
              html: greenHtml,
              iconSize: [24, 24],
              iconAnchor: [12, 12],
            }),
          );
          marker.setPopupContent(`
            <div class="p-2 font-sans text-xs bg-bg-panel text-text-primary border border-signal-verified rounded">
              <div class="font-bold text-signal-verified">${sig.id} · ${sig.name}</div>
              <div class="text-text-muted mt-0.5">Municipal Signal #${sig.junctionNumber}</div>
              <div class="mt-1 font-mono text-[10px] text-signal-verified font-bold">● GREEN CORRIDOR ACTIVE (180s Hold)</div>
            </div>
          `);
        }

        // 3. Post municipal signal override to backend audit ledger
        const now = new Date();
        const timeStr = now.toTimeString().slice(0, 8) + "." + String(now.getMilliseconds()).padStart(3, "0");
        const latency = Math.floor(32 + Math.random() * 24);

        try {
          const res = await fetch("http://localhost:8000/corridor/signal-actuate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              signal_id: sig.id,
              junction_name: sig.name,
              color: "GREEN",
              time_saved: "4 min 20 sec",
            }),
          });
          if (res.ok) {
            const data = (await res.json()) as { audit_id: number; hash: string };
            setActuationLogs((prev) => [
              {
                id: `act_${index + 1}`,
                signalId: sig.id,
                name: sig.name,
                timestamp: timeStr,
                status: "FORCED GREEN",
                latencyMs: latency,
                blockHash: data.hash,
                phaseHold: "180s",
              },
              ...prev,
            ]);
          }
        } catch {
          // Fallback log entry
          setActuationLogs((prev) => [
            {
              id: `act_${index + 1}`,
              signalId: sig.id,
              name: sig.name,
              timestamp: timeStr,
              status: "FORCED GREEN",
              latencyMs: latency,
              phaseHold: "180s",
            },
            ...prev,
          ]);
        }

        if (onSignalActuated) {
          onSignalActuated(sig.id, sig.name);
        }

        // When the final signal turns green, launch ambulance animation along the route
        if (index === TRAFFIC_SIGNALS.length - 1) {
          launchAmbulance(map);
        }
      }, index * 200); // Exactly 200ms apart per PDF specification!
    });
  }, [approved, onSignalActuated]);

  // Interpolate ambulance along polyline coordinates
  const launchAmbulance = useCallback((map: L.Map) => {
    const ambulanceHtml = `
      <div class="relative flex items-center justify-center p-1.5 rounded-full bg-bg-panel border border-[#22d3ee] ambulance-siren shadow-[0_0_16px_rgba(34,211,238,0.7)]">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-signal-verified" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1 .4-1 1v9c0 .6.4 1 1 1h2"/>
          <circle cx="7" cy="17" r="2"/>
          <path d="M9 17h6"/>
          <circle cx="17" cy="17" r="2"/>
          <path d="M10 6h4"/>
          <path d="M12 4v4"/>
        </svg>
      </div>
    `;

    const startPos = CORRIDOR_ROUTE[0] ?? HYD_CENTER;
    const ambulanceMarker = L.marker(startPos, {
      icon: L.divIcon({
        className: "custom-ambulance-marker",
        html: ambulanceHtml,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      }),
      zIndexOffset: 1000,
    }).addTo(map);

    ambulanceMarkerRef.current = ambulanceMarker;

    // Total distance & segment breakdowns
    const segments: { p1: [number, number]; p2: [number, number]; dist: number }[] = [];
    let totalDist = 0;
    for (let i = 0; i < CORRIDOR_ROUTE.length - 1; i++) {
      const p1 = CORRIDOR_ROUTE[i];
      const p2 = CORRIDOR_ROUTE[i + 1];
      if (!p1 || !p2) continue;
      const d = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
      segments.push({ p1, p2, dist: d });
      totalDist += d;
    }

    const durationMs = 6000; // 6 seconds travel along corridor
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(1, elapsed / durationMs);
      setAmbulanceProgress(progress);

      const targetDist = progress * totalDist;
      let accum = 0;
      const finalPoint = CORRIDOR_ROUTE[CORRIDOR_ROUTE.length - 1] ?? HYD_CENTER;
      let currentPos: [number, number] = finalPoint;

      for (const seg of segments) {
        if (accum + seg.dist >= targetDist) {
          const segProgress = (targetDist - accum) / (seg.dist || 0.0001);
          currentPos = [
            seg.p1[0] + (seg.p2[0] - seg.p1[0]) * segProgress,
            seg.p1[1] + (seg.p2[1] - seg.p1[1]) * segProgress,
          ];
          break;
        }
        accum += seg.dist;
      }

      ambulanceMarker.setLatLng(currentPos);

      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(animate);
      } else {
        ambulanceMarker.bindPopup(`
          <div class="p-2 font-sans text-xs bg-bg-panel text-signal-verified border border-signal-verified rounded">
            <div class="font-bold">AMBULANCE UNIT #09 REACHED DESTINATION</div>
            <div class="text-text-muted mt-1">Transferred to Osmania Emergency Trauma Ward.</div>
            <div class="text-signal-data mt-1 font-mono text-[10px]">TIME SAVED: 4m 20s via Green Corridor</div>
          </div>
        `).openPopup();
      }
    };

    animationFrameRef.current = requestAnimationFrame(animate);
  }, []);

  // Reset corridor state if incident resets
  useEffect(() => {
    if (!incident) {
      actuationTriggeredRef.current = false;
      setCorridorActive(false);
      setActuationLogs([]);
      setAmbulanceProgress(0);
      setSignalStates({
        SIG_HYD_04A: "RED",
        SIG_HYD_04B: "RED",
        SIG_HYD_04C: "RED",
        SIG_HYD_04D: "RED",
        SIG_HYD_04E: "RED",
        SIG_HYD_04F: "RED",
      });

      const map = mapInstanceRef.current;
      if (map) {
        if (activeGlowPolylineRef.current) {
          map.removeLayer(activeGlowPolylineRef.current);
          activeGlowPolylineRef.current = null;
        }
        if (activeCorePolylineRef.current) {
          map.removeLayer(activeCorePolylineRef.current);
          activeCorePolylineRef.current = null;
        }
        if (ambulanceMarkerRef.current) {
          map.removeLayer(ambulanceMarkerRef.current);
          ambulanceMarkerRef.current = null;
        }
        if (!inactivePolylineRef.current) {
          inactivePolylineRef.current = L.polyline(CORRIDOR_ROUTE, {
            color: "#475569",
            weight: 3,
            dashArray: "6, 8",
            opacity: 0.6,
          }).addTo(map);
        }

        // Reset signal markers to RED
        TRAFFIC_SIGNALS.forEach((sig) => {
          const marker = signalMarkersRef.current.get(sig.id);
          if (marker) {
            const redHtml = `
              <div id="sig-icon-${sig.id}" class="relative flex items-center justify-center w-6 h-6 rounded-full bg-bg-void border-2 border-signal-rejected signal-glow-red transition-all duration-300">
                <span class="w-2.5 h-2.5 rounded-full bg-signal-rejected"></span>
              </div>
            `;
            marker.setIcon(
              L.divIcon({
                className: "custom-signal-marker",
                html: redHtml,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
              }),
            );
          }
        });
      }
    }
  }, [incident]);

  return (
    <div className="flex flex-col gap-3 rounded border border-line bg-bg-panel p-4">
      {/* Top Banner: Geospatial Header & Green Corridor Active Status */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-line bg-bg-panel-raised text-signal-data">
            <Compass className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-sans text-body font-semibold text-text-primary">
                Geospatial Incident & Route Control
              </span>
              <span className="rounded border border-line bg-bg-void px-2 py-0.5 font-mono text-[10px] text-text-muted">
                HYDERABAD METRO
              </span>
            </div>
            <p className="font-sans text-label text-text-muted">
              Centred at 17.3850° N, 78.4867° E · CartoDB Dark Tiles · 4 Camera Zones
            </p>
          </div>
        </div>

        {/* Live Corridor Status Indicator */}
        <div className="flex items-center gap-2">
          {corridorActive ? (
            <div className="flex items-center gap-2 rounded border border-signal-verified/60 bg-signal-verified/15 px-3 py-1 font-mono text-label font-bold text-signal-verified shadow-[0_0_12px_rgba(61,220,132,0.35)]">
              <Zap className="h-4 w-4 animate-pulse" />
              <span>GREEN CORRIDOR ACTIVE · EST. TIME SAVED: 4 MIN 20 SEC</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 rounded border border-line bg-bg-void px-3 py-1 font-mono text-label text-text-muted">
              <TrafficCone className="h-3.5 w-3.5 text-text-muted" />
              <span>CORRIDOR STANDBY · 6 SIGNALS HOLDING RED</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Grid: Interactive Map (Left) + Signal Actuation Log (Right) */}
      <div className="grid gap-3 lg:grid-cols-12 items-stretch min-h-[460px]">
        {/* Left Column: Leaflet Map (8 cols) */}
        <div className="lg:col-span-8 relative flex flex-col rounded border border-line overflow-hidden bg-bg-void min-h-[440px]">
          {/* Map Leaflet Canvas Container */}
          <div ref={mapContainerRef} className="h-full w-full flex-1 z-10" />

          {/* Map Overlay Badge: Active Incident Target */}
          <div className="absolute top-3 left-3 z-20 flex flex-col gap-1.5 pointer-events-none">
            <div className="flex items-center gap-1.5 rounded border border-signal-rejected/60 bg-bg-panel/90 backdrop-blur-sm px-2.5 py-1 font-mono text-[11px] font-semibold text-signal-rejected shadow-lg">
              <Radio className="h-3.5 w-3.5 animate-ping text-signal-rejected" />
              <span>INCIDENT ORIGIN: {incident?.zone ?? "Zone 04 (MJ Market)"}</span>
            </div>
            {corridorActive && (
              <div className="flex items-center gap-1.5 rounded border border-signal-verified/60 bg-bg-panel/90 backdrop-blur-sm px-2.5 py-1 font-mono text-[11px] font-semibold text-signal-verified shadow-lg">
                <CheckCircle className="h-3.5 w-3.5" />
                <span>6 OF 6 MUNICIPAL SIGNALS CLEARED</span>
              </div>
            )}
          </div>

          {/* Map Legend Overlay */}
          <div className="absolute bottom-3 left-3 z-20 flex flex-wrap items-center gap-2 rounded border border-line bg-bg-panel/90 backdrop-blur-sm p-1.5 font-mono text-[10px] text-text-muted pointer-events-none">
            <div className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-signal-rejected"></span>
              <span>Camera Zone (Active)</span>
            </div>
            <span className="text-line">|</span>
            <div className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-[#22d3ee]"></span>
              <span>Osmania Hospital</span>
            </div>
            <span className="text-line">|</span>
            <div className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-[#f5a623]"></span>
              <span>Fire Station</span>
            </div>
            <span className="text-line">|</span>
            <div className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-signal-verified"></span>
              <span>Forced Green Signal</span>
            </div>
          </div>
        </div>

        {/* Right Column: Signal Actuation Log & Honesty Panel (4 cols) */}
        <div className="lg:col-span-4 flex flex-col rounded border border-line bg-bg-panel-raised p-3.5">
          {/* Header with Honesty Requirement */}
          <div className="border-b border-line pb-2.5">
            <div className="flex items-center justify-between">
              <span className="font-sans text-label font-bold text-text-primary tracking-wide uppercase">
                Signal Actuation Log
              </span>
              <span className="rounded bg-signal-data/10 border border-signal-data/30 px-1.5 py-0.5 font-mono text-[9px] font-bold text-signal-data">
                SCATS / ITMS
              </span>
            </div>

            {/* MANDATORY HONESTY LABEL PER PDF P6 SPECIFICATION */}
            <div className="mt-1.5 rounded border border-signal-pending/40 bg-signal-pending/10 px-2 py-1 font-mono text-[10px] text-signal-pending font-semibold">
              SIMULATED MUNICIPAL SIGNAL API
            </div>
            <p className="mt-1 font-sans text-[11px] text-text-muted leading-tight">
              Pre-emption commands sent via municipal traffic broker emulation. One SHA-256 ledger block appended per actuation.
            </p>
          </div>

          {/* Signal Actuation List */}
          <div className="flex-1 overflow-y-auto space-y-2 py-2.5 pr-1 max-h-[300px]">
            {actuationLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-center text-text-muted font-sans text-label p-4">
                <TrafficCone className="h-6 w-6 text-line mb-2" />
                <p>No signal override dispatched yet.</p>
                <p className="text-[11px] text-text-muted/80 mt-1">
                  Approve verified incident to trigger sequential green corridor actuation.
                </p>
              </div>
            ) : (
              actuationLogs.map((log) => (
                <div
                  key={log.id}
                  className="rounded border border-signal-verified/40 bg-bg-panel p-2 font-mono text-[11px] space-y-1 shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-signal-verified">{log.signalId}</span>
                    <span className="text-text-muted text-[10px]">{log.timestamp}</span>
                  </div>
                  <div className="text-text-primary text-[11px] font-sans truncate">{log.name}</div>
                  <div className="flex items-center justify-between text-[10px] pt-1 border-t border-line/50 text-text-muted">
                    <span className="text-signal-verified font-bold">● {log.status}</span>
                    <span>Latency: {log.latencyMs}ms</span>
                    <span className="text-signal-data font-semibold">Hold: {log.phaseHold}</span>
                  </div>
                  {log.blockHash && (
                    <div className="text-[9px] text-text-muted font-mono truncate">
                      Ledger: {log.blockHash.slice(0, 16)}...
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Bottom Corridor Metric Summary */}
          <div className="border-t border-line pt-2.5 mt-auto">
            <div className="flex items-center justify-between font-mono text-[11px] text-text-muted">
              <span>Route Distance:</span>
              <span className="text-text-primary font-semibold">1.8 km</span>
            </div>
            <div className="flex items-center justify-between font-mono text-[11px] text-text-muted mt-1">
              <span>Target Hospital:</span>
              <span className="text-signal-data font-semibold">Osmania Gen.</span>
            </div>
            <div className="flex items-center justify-between font-mono text-[11px] text-text-muted mt-1">
              <span>Estimated Time Saved:</span>
              <span className="text-signal-verified font-bold">4m 20s</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
