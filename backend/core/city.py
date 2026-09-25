"""The digital-twin city — Gachibowli / NH-44 corridor, Hyderabad.

WHAT IS REAL AND WHAT IS NOT. Read this before quoting anything on stage.

REAL: the coordinates. Every node below sits at a real-world latitude and
longitude in the Gachibowli area of Hyderabad, so the basemap underneath is a
true map and the corridor geometry is geographically coherent. Junction and
locality names are the ones people actually use for that area.

SIMULATED: everything operational. Camera IDs, signal-controller state, hospital
bay availability, the ambulance, and the road graph's edge weights are invented
for this prototype. No ID below addresses a real municipal asset, and no
capacity figure came from the named facility.

One real facility name appears (Sunshine Hospital, Gachibowli) because the demo
brief asked for it. Its bay count is simulated and the UI labels it as such. If
you would rather name no real facility at all, set USE_REAL_FACILITY_NAMES to
False: the twin then falls back to clearly synthetic names and nothing else
changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Flip to False (or set AURASHIELD_REAL_FACILITY_NAMES=0) to remove every real
# facility name from the UI in one step.
USE_REAL_FACILITY_NAMES = os.getenv("AURASHIELD_REAL_FACILITY_NAMES", "1") == "1"

BBOX_LABEL = ("Gachibowli / NH-44 corridor, Hyderabad · real coordinates · "
              "simulated infrastructure state")

# Demo viewport. Used by the map and by tools/prefetch_tiles.py so the cached
# tile set and the rendered view always agree.
VIEW_CENTER = (17.4426, 78.3505)
VIEW_ZOOM = 15
TILE_BBOX = {"min_lat": 17.4230, "max_lat": 17.4560,
             "min_lon": 78.3330, "max_lon": 78.3640}

# Primary incident site, per the demo brief.
INCIDENT_LAT, INCIDENT_LON = 17.4401, 78.3489
INCIDENT_LABEL = "NH-44 Gachibowli Junction, Hyderabad"
CAMERA_ID = "CAM-HYD-NH44-Z04"


@dataclass
class Node:
    node_id: str
    name: str
    lat: float
    lon: float
    kind: str                      # junction | hospital | camera | strobe | depot


@dataclass
class Junction:
    junction_id: str
    name: str
    lat: float
    lon: float
    controller_online: bool = True
    state: str = "NORMAL"          # NORMAL | PRIORITY_GREEN | RELEASED
    priority_seq: Optional[int] = None


@dataclass
class Hospital:
    hospital_id: str
    name: str
    lat: float
    lon: float
    trauma_capable: bool
    bays_free: int                 # SIMULATED — see module docstring


@dataclass
class Streetlight:
    strobe_id: str
    name: str
    lat: float
    lon: float
    mode: str = "OFF"              # OFF | AMBER | RED_STROBE

# ---- graph -----------------------------------------------------------------
# Hand-authored, deliberately NOT a routing engine: a fixed graph cannot fail at
# 3am, and the demo needs determinism more than it needs shortest-path
# generality.
#
# Node coordinates are real Gachibowli locations, so the route drawn over the
# basemap follows the real corridor. Edge weights are straight-line distance
# times a 1.18 urban road factor, rounded to 5 m — every weight is therefore
# greater than the great-circle distance between its endpoints, which
# tools/check_geometry.py asserts.
#
# Primary corridor (incident -> Sunshine) crosses FOUR signalised junctions:
#     N_CAM4 -> J1 -> J2 -> J3 -> J4 -> H_ALPHA
# Southern bypass (used when a controller is offline, and for the re-plan):
#     J1 -> J5 -> J6  ->  J3/J4 or H_BETA

_H1 = ("Sunshine Hospital, Gachibowli" if USE_REAL_FACILITY_NAMES
       else "Gachibowli Trauma Centre (simulated facility)")
_H2 = "Nanakramguda Trauma Annexe (simulated facility)"

NODES: Dict[str, Node] = {
    "N_CAM4":  Node("N_CAM4",  f"{CAMERA_ID} · NH-44 Gachibowli Junction",
                    INCIDENT_LAT, INCIDENT_LON, "camera"),
    "J1":      Node("J1",      "Gachibowli Flyover Junction",   17.4409, 78.3494, "junction"),
    "J2":      Node("J2",      "ISB Road Junction",             17.4421, 78.3502, "junction"),
    "J3":      Node("J3",      "Gachibowli Stadium Junction",   17.4436, 78.3511, "junction"),
    "J4":      Node("J4",      "Hospital Approach Junction",    17.4446, 78.3518, "junction"),
    "J5":      Node("J5",      "Nanakramguda Junction",         17.4381, 78.3531, "junction"),
    "J6":      Node("J6",      "Financial District Junction",   17.4418, 78.3572, "junction"),
    "H_ALPHA": Node("H_ALPHA", _H1,                             17.4450, 78.3520, "hospital"),
    "H_BETA":  Node("H_BETA",  _H2,                             17.4402, 78.3601, "hospital"),
    "D_AMB":   Node("D_AMB",   "Ambulance AMB-117 (simulated)", 17.4340, 78.3430, "depot"),
}

EDGES: Dict[str, List[Tuple[str, int]]] = {
    "D_AMB":   [("N_CAM4", 1090)],
    "N_CAM4":  [("D_AMB", 1090), ("J1", 120)],
    "J1":      [("N_CAM4", 120), ("J2", 185), ("J5", 590)],
    "J2":      [("J1", 185), ("J3", 225)],
    "J3":      [("J2", 225), ("J4", 160), ("J5", 765)],
    "J4":      [("J3", 160), ("H_ALPHA", 60), ("J6", 770)],
    "H_ALPHA": [("J4", 60)],
    "J5":      [("J1", 590), ("J6", 705), ("J3", 765)],
    "J6":      [("J5", 705), ("H_BETA", 420), ("J4", 770)],
    "H_BETA":  [("J6", 420)],
}


def default_junctions() -> Dict[str, Junction]:
    return {
        n.node_id: Junction(n.node_id, n.name, n.lat, n.lon)
        for n in NODES.values() if n.kind == "junction"
    }


def default_hospitals() -> Dict[str, Hospital]:
    # bays_free is SIMULATED. It is not sourced from the named facility, and the
    # UI carries that label next to the figure. See KNOWN_LIMITATIONS.md.
    return {
        "H_ALPHA": Hospital("H_ALPHA", _H1, 17.4450, 78.3520, True, 2),
        "H_BETA":  Hospital("H_BETA",  _H2, 17.4402, 78.3601, False, 4),
    }


def default_streetlights() -> Dict[str, Streetlight]:
    return {
        "SL_NH44_A": Streetlight("SL_NH44_A", "Smart streetlight SL-NH44-A",
                                 17.4406, 78.3492),
        "SL_NH44_B": Streetlight("SL_NH44_B", "Smart streetlight SL-NH44-B",
                                 17.4394, 78.3484),
    }


@dataclass
class CityTwin:
    """Mutable twin state. One instance per running demo."""
    junctions: Dict[str, Junction] = field(default_factory=default_junctions)
    hospitals: Dict[str, Hospital] = field(default_factory=default_hospitals)
    streetlights: Dict[str, Streetlight] = field(default_factory=default_streetlights)
    ambulance_node: str = "D_AMB"

    def reset(self) -> None:
        self.junctions = default_junctions()
        self.hospitals = default_hospitals()
        self.streetlights = default_streetlights()
        self.ambulance_node = "D_AMB"

    def set_controller_online(self, junction_id: str, online: bool) -> None:
        if junction_id in self.junctions:
            self.junctions[junction_id].controller_online = online

    # ---- routing ----------------------------------------------------------
    def shortest_path(self, src: str, dst: str,
                      avoid: Optional[set] = None) -> Optional[List[str]]:
        """Dijkstra over the fixed graph, optionally avoiding nodes.

        Returns None when no path exists, which is a real outcome the Route
        Agent has to handle rather than an error to swallow.
        """
        avoid = avoid or set()
        if src in avoid or dst in avoid:
            return None
        dist = {src: 0}
        prev: Dict[str, str] = {}
        seen: set = set()
        while True:
            frontier = {n: d for n, d in dist.items() if n not in seen}
            if not frontier:
                return None
            cur = min(frontier, key=frontier.get)
            if cur == dst:
                break
            seen.add(cur)
            for nxt, w in EDGES.get(cur, []):
                if nxt in avoid:
                    continue
                nd = dist[cur] + w
                if nd < dist.get(nxt, 1 << 30):
                    dist[nxt] = nd
                    prev[nxt] = cur
        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        return list(reversed(path))

    def path_cost(self, path: List[str]) -> int:
        total = 0
        for a, b in zip(path, path[1:]):
            for nxt, w in EDGES.get(a, []):
                if nxt == b:
                    total += w
                    break
        return total

    def junctions_on(self, path: List[str]) -> List[str]:
        return [n for n in path if n in self.junctions]

    def offline_junctions(self) -> set:
        return {j.junction_id for j in self.junctions.values() if not j.controller_online}

    def snapshot(self) -> Dict:
        return {
            "bbox_label": BBOX_LABEL,
            "view": {"center": list(VIEW_CENTER), "zoom": VIEW_ZOOM, "bbox": TILE_BBOX},
            "camera_id": CAMERA_ID,
            "incident_label": INCIDENT_LABEL,
            "real_facility_names": USE_REAL_FACILITY_NAMES,
            "nodes": [
                {"id": n.node_id, "name": n.name, "lat": n.lat, "lon": n.lon, "kind": n.kind}
                for n in NODES.values()
            ],
            "junctions": [
                {"id": j.junction_id, "name": j.name, "lat": j.lat, "lon": j.lon,
                 "online": j.controller_online, "state": j.state, "seq": j.priority_seq}
                for j in self.junctions.values()
            ],
            "hospitals": [
                {"id": h.hospital_id, "name": h.name, "lat": h.lat, "lon": h.lon,
                 "trauma": h.trauma_capable, "bays_free": h.bays_free,
                 "capacity_source": "SIMULATED — not sourced from the named facility"}
                for h in self.hospitals.values()
            ],
            "streetlights": [
                {"id": s.strobe_id, "name": s.name, "lat": s.lat, "lon": s.lon, "mode": s.mode}
                for s in self.streetlights.values()
            ],
            "ambulance_node": self.ambulance_node,
        }

    def choose_hospital(self, severity: str, exclude: Optional[set] = None) -> str:
        return choose_hospital(self, severity, exclude)

    def plan_route(self, hospital_id: str, incident_node: str = "N_CAM4") -> Dict:
        return plan_route(self, hospital_id, incident_node)


TWIN_SPEED_MPS = 8.0


class NoRouteAvailable(RuntimeError):
    pass


def choose_hospital(twin: CityTwin, severity: str, exclude: Optional[set] = None) -> str:
    """Trauma capability first for serious severities, then free bays, then proximity.
    Matches original AuraShield hospital selection logic."""
    exclude = exclude or set()
    options = [h for h in twin.hospitals.values() if h.hospital_id not in exclude and h.bays_free > 0]
    if not options:
        options = list(twin.hospitals.values())
    needs_trauma = severity in ("HIGH", "CRITICAL")
    options.sort(key=lambda h: (
        0 if (h.trauma_capable and needs_trauma) else 1,
        -h.bays_free,
        h.hospital_id,
    ))
    return options[0].hospital_id


def plan_route(twin: CityTwin, hospital_id: str, incident_node: str = "N_CAM4") -> Dict:
    """Computes shortest path from ambulance node to hospital over CityTwin graph."""
    avoid = twin.offline_junctions()
    path = twin.shortest_path(twin.ambulance_node, hospital_id, avoid=avoid)
    degraded = False
    if path is None:
        path = twin.shortest_path(twin.ambulance_node, hospital_id)
        degraded = True
        if path is None:
            # Fallback path if graph completely severed
            path = [twin.ambulance_node, incident_node, hospital_id]

    junctions = twin.junctions_on(path)
    controllable = [j for j in junctions if twin.junctions[j].controller_online]
    cost = twin.path_cost(path)
    return {
        "path": path,
        "junctions": junctions,
        "controllable_junctions": controllable,
        "avoided": sorted(avoid),
        "degraded": degraded,
        "cost_m": cost,
        "eta_seconds": int(round(cost / TWIN_SPEED_MPS)),
    }
