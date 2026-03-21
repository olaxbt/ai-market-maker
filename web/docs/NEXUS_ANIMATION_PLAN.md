# Nexus Centric UI & Animation Plan

## Goals
- Nexus is **≥50% of the viewport** (dominant center).
- **Zoom**: enlarge / minimize with smooth animation (user or auto “breathing”).
- **Viewing angle**: 3D tilt / rotation (perspective + rotateX/Y) so the hub feels spatial.
- **Socket-driven signals**: when an event arrives, **particles / “stars”** move from the rim **toward the center** (nuclear/electronic feel); nexus reacts in real time.

---

## 1. Layout — Nexus 50% centric
- **Main grid**: Center column reserved for nexus with **min 50% of viewport width** (e.g. `minmax(50vw, 1fr)` or center = 50%, sides = 25% each).
- **Nexus size**: Hub circle = **min(50vmin, 72vh)** so it’s at least half the “screen” (smaller of width/height) and responsive.
- Side panels (event stream, topology) share the remaining space (e.g. `1fr` each).

---

## 2. Enlarge / Minimize (Zoom)
- **Option A – User control**: Slider or +/- buttons; scale the nexus wrapper with `transform: scale(s)` (e.g. 0.6 → 1.2). Animate with Framer Motion or CSS transition.
- **Option B – Auto “breathing”**: Loop scale between 0.92 and 1.08 over ~3s for a subtle live feel.
- **Option C – Both**: Default breathing + optional user override (slider) that pauses breathing and uses manual scale.
- **Implementation**: One wrapper `div` around the nexus canvas; apply `transform: scale(var)` and optional `perspective` + `rotateX/Y` there. State: `scale: number`; Framer Motion `animate={{ scale }}` or CSS custom property + transition.

---

## 3. Viewing Angle (3D / D3-style)
- **Approach**: Use **CSS 3D** (no D3/Three.js for v1) so the disc has depth:
  - Parent: `perspective: 1200px`, `transform-style: preserve-3d`.
  - Nexus wrapper: `rotateX(8deg) rotateY(-5deg)` (or dynamic from mouse/slider). Optional: slow `rotateY` animation for a gentle spin.
- **D3 later**: If we want data-driven nodes on the nexus (e.g. agents as points on the disc), we can replace the center graphic with D3 SVG + zoom/rotate. For “viewing angle” only, CSS 3D is enough and keeps the bundle small.
- **Interaction**: Optional “orbit” control: drag or two sliders (tilt X, spin Y) to change angle; Framer Motion `useMotionValue` + `useTransform` for smooth follow.

---

## 4. Socket-Driven “Stars” / Signals to Center
- **Effect**: When a **signal** is received (WebSocket or mock):
  - Spawn **particles** (“stars”) at the **outer edge** of the nexus (random angle).
  - Move them **inward** toward the center over ~0.4–0.8s.
  - Style: small bright dots or short streaks with glow; fade out near center or on impact.
- **Implementation**:
  - **Canvas layer**: Keep current nexus canvas for the rings/dots; add a **second canvas** (or same canvas, drawn after rings) for particles. Each particle: `{ x, y, fromX, fromY, progress, opacity }`; update in `requestAnimationFrame`, draw as circle or line with `ctx.shadowBlur` for glow.
  - **Trigger**: Prop or context, e.g. `onSignal?: () => void` or `signalCount: number`. When `signalCount` increments (or socket message), spawn 5–12 particles. Mock: `setInterval` or “simulate signal” button; later: WebSocket in `page.tsx` that increments and passes to nexus.
- **Variants**:
  - **Radial in**: Particles at R_max, move to (cx, cy).
  - **Nuclear pulse**: Ring that shrinks from outer to center, then flash at center.
  - **Electronic**: Short line segments that “travel” along radius toward center (dash animation).

---

## 5. Tech Choices
| Feature        | Choice              | Rationale                          |
|----------------|---------------------|------------------------------------|
| Layout         | CSS Grid            | Center 50%, sides flexible         |
| Nexus drawing  | Canvas (existing)   | Already have rings/dots            |
| Particles      | Canvas (same or 2nd)| Performant, full control          |
| Zoom / scale   | Framer Motion       | Already in project, smooth         |
| 3D angle       | CSS transform       | Lightweight, no extra lib          |
| Socket         | Mock first, then WS | Same component API (`signalCount`) |

---

## 6. Implementation Order
1. **Layout**: Adjust grid so center column is 50% min-width; set nexus size to 50vmin (or min(50vmin, 72vh)).
2. **Zoom**: Add scale state + Framer Motion animate; optional breathing loop or slider.
3. **3D angle**: Add perspective + rotateX/Y on nexus wrapper; optional sliders/drag.
4. **Particles to center**: Particle system in canvas; spawn on signal; draw and update in rAF.
5. **Signal trigger**: Mock `signalCount` in page (interval or on new trace); pass to nexus; later replace with WebSocket.

---

## 7. File Changes (summary)
- **`NexusStarSystem.tsx`**: Orbital hub — central core, agent stars + labels (static layout for readability), SVG mesh edges. **Default: no hub motion**; `signalCount` reserved for optional future particles (see plan above). (Standalone `NexusHub.tsx` removed — ring geometry lives here.)
- **`page.tsx`**: Composes `NexusDeskView` / `AgentsConsoleView`; data via `useNexusPayload` + `useNexusSignalCount`; center column `NexusStarSystem`; `activeNodeId` = selected topology node or first `ACTIVE` node.
- **`globals.css`**: Nexus glow utilities.
- **Future**: WebSocket increments `signalCount` on trace/reasoning events; optional D3/Three.js for deeper 3D.
