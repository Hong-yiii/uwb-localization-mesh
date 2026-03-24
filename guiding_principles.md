# 🧭 Guiding Principles — Architecture & Build Rules

This document captures the **design rules** that keep the system predictable, testable, and demo‑ready across multiple devices.

**Product vs example apps:** **UWB localization** (packages + anchor/server bring-ups) is the **core**. The **Unified Demo** and other `Demos/*` are **optional compositions** that import that core; they illustrate how an application layer can embed the laptop server and attach a UI—they are not the definition of the core architecture.

---

## 1) Packages: purity & boundaries

- **No side effects on import.** Importing a package must *not* mutate global state.
- **Typed, minimal public APIs.** Prefer dataclasses/Pydantic for inputs/outputs, keep `__all__` small.
- **Dependency direction:** Apps/bring‑ups depend on packages; packages do **not** import demos or bring‑ups.
- **Configuration via parameters**, not globals. Use dependency injection for clients/servers.
- **Determinism:** Same inputs → same outputs (especially for localization & PGO). Seed any randomness.

---

## 2) Concurrency, ordering & race conditions

- **Thread model:**  
  - MQTT client callbacks are **producer** threads.  
  - A single **aggregator thread** (or event loop) reads from a thread‑safe queue and performs **binning** + **localization** + **PGO** in order.
- **Do not mutate shared structures without locks.** Use `queue.Queue` or `asyncio` channels; protect maps like `data[phone_id]` with a `Lock`.
- **Backpressure:** If the queue grows beyond N, log a warning and shed oldest items first.

---

## 3) Time & synchronization

- **Canonical clock = NTP.** All hosts (server + RPis) use NTP time as the ground truth.  
- **NTP sync at bring-up.** On startup, each host performs an NTP synchronization to align its system clock, and then continues background NTP syncing to minimize drift.  
- **Drift tracking.** Each host tracks its drift relative to NTP; if drift > threshold, emit a warning.  
- **Timestamps.** Always record timestamps as **float seconds since epoch (UTC)**. When serialized across systems, include timezone information at the boundaries.  

---

## 4) Data types & contracts

Keep schemas in a shared module (or within `localization_algos` for now).

```python
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

@dataclass(frozen=True)
class Measurement:
    timestamp: float          # server-corrected seconds
    anchor_id: int
    phone_node_id: int
    local_vector: np.ndarray  # [x, y, z] in cm, phone-local frame

@dataclass
class BinnedData:
    bin_start_time: float     # inclusive
    bin_end_time: float       # exclusive
    phone_node_id: int
    measurements: Dict[int, List[np.ndarray]]  # anchor_id -> vectors

    def averaged_edges(self) -> List[Tuple[int, int, np.ndarray]]:
        """(anchor_id, phone_node_id, avg_vector) per anchor in this bin."""
```

---

## 5) Binning policy (sliding windows, 1 s default)

- **Windowing = sliding window (Δ = 1.0 s by default).**  
  Maintain a deque of recent measurements; the window is `[now - Δ, now]` where *now* is NTP-synced time (UTC).
- **Aggregation per (phone, anchor).**  
  For each bin, group by `(phone_node_id, anchor_id)` and compute the **average vector**. Keep **count** and (optionally) **variance** for downstream weighting.
- **Late data policy.**  
  Accept measurements whose `timestamp ≥ window_start`.  
  Drop anything with `timestamp < window_start` (i.e., landing in already **sealed** bins); increment a `late_drop` metric.
- **Seal & emit.**  
  When you materialize the current window, create a new `phone_node_id` (e.g., `phone_bin_k`), compute averaged anchor-phone edges, add **anchor-anchor** edges, and send to `localization_algos → PGO`. One bin ⇒ one solve tick.
- **Metrics.**  
  Per bin: `num_measurements`, `per_anchor_counts`, `late_drop_count`, `window_span_sec`, `solve_time_sec`.

---

## 6) Frames, angles & corrections

- **Local phone frame → global grid** happens via edges + PGO.  
- Phone **0° azimuth faces the center** of the square: apply a yaw rotation to each `local_vector` before creating edges, if needed:
```python
def rotate_yaw(vec_cm: np.ndarray, yaw_deg: float) -> np.ndarray:
    # rotate around +Z
    ...
```
- Keep anchor ground truth in server (`nodes = {id: [x,y,z]}`) and version it.
- Document axis conventions: `+X` to the right, `+Y` forward, `+Z` up (right‑handed).

---

## 7) MQTT topics & QoS (suggested)

- Measurements (from RPi): `uwb/v1/measurements/{phone_node_id}` – QoS 1  
  Payload: `timestamp, anchor_id, phone_node_id, local_vector`
- Graph solution (server → demos): `uwb/v1/graph/solution` – QoS 0/1  
  Payload: `nodes_global_cm, user_position_cm`
- Audio commands (server → clients/players): `audio/v1/commands` – QoS 0/1

**Version topics** with `/v1/` so we can evolve payloads safely.

---

## 8) Error handling & validation

- Validate incoming payloads (shape, units, ranges). Reject nonsense (e.g., `NaN`, absurd magnitudes).
- Treat **missing anchors** as lower weight; log consistently missing anchors.
- If `PGO.solve()` fails or diverges, **fallback** to last known good solution and mark it stale.

---

## 9) Logging, metrics, testing

- **Structured logs** (JSON or clear prefixes). Include node_id, bin, counts, and solve time.  
- **Unit tests** per package + **integration tests** that spin a local MQTT broker and verify end‑to‑end bin→solve→publish.  
- Record minimal artifacts for repro (seed, bin window, counts).

---

## 10) Run/ops conventions

- Bring‑ups are single‑purpose scripts: **Server first → Clients → Demo**.  
- Use `argparse` flags: `--node-id`, `--broker`, `--topic-prefix`, `--bin-s`, `--lateness-ms`.
- Keep **state** in objects passed to loops (avoid module‑level globals).

---

## 11) Naming & style

- Python: `snake_case` for modules/vars, `CapWords` for classes, `lowercase` console scripts.
- Keep file names short and descriptive (`Server_bring_up.py`, `Demos/UnifiedDemo/server_bring_up_with_audio.py`, `Demos/UnifiedDemo/main_demo.py`).
- Docstrings for public APIs; keep README examples runnable.

---

## 12) Security & safety (lightweight for demos)

- Don’t hardcode credentials. Allow env‑vars if auth is enabled on the broker.
- Input sanitize any command paths for audio players.
- If exposing a web UI, bind to localhost by default during dev.

---

### ✅ Summary

- **Pure packages**, **bring‑ups** for runtime wiring, **demos** for scenarios.  
- Handle **ordering**, **lateness**, and **race conditions** via a queue + single aggregator.  
- **Binning → edges → PGO → outputs** is the canonical pipeline.  
- Stable **schemas**, versioned **topics**, and clear **metrics** keep everything debuggable.
