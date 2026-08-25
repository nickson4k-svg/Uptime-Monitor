---
name: ux-ui-agent-skills
description: Comprehensive UI/UX Design System, Design Tokens, WCAG 2.2 AA Accessibility, and Modern Aesthetics guide for Agentic AI workflows. Use when generating, reviewing, or redesigning web user interfaces, styling HTML templates, or building component libraries.
---

# UX/UI Agent Skills (Design System & Design Engineering)

> Production-grade UI/UX Design System, Token Mapping, WCAG 2.2 AA Accessibility Guidelines, and Design Patterns for Web Applications.

---

## 🎨 1. Design System Core Principles

1. **Aesthetics & Atmosphere**:
   - Deep slate/midnight dark background (`#0b0f19`, `#111827`) combined with glassmorphic cards (`rgba(17, 24, 39, 0.75)` with `backdrop-filter: blur(16px)`).
   - Vibrant accent gradients: Emerald/Cyan for healthy status (`linear-gradient(135deg, #10b981, #06b6d4)`), Rose/Amber for downtime (`linear-gradient(135deg, #ef4444, #f59e0b)`), Violet/Indigo for active elements (`linear-gradient(135deg, #6366f1, #8b5cf6)`).

2. **Typography System**:
   - Primary Font: `'Plus Jakarta Sans'`, `'Inter'`, or system-ui stack.
   - Scale: Monospaced numbers for metrics (`font-mono`), tight headings (`letter-spacing: -0.025em`).

3. **Design Tokens (CSS Variables)**:
   ```css
   :root {
     --bg-main: #0b0f17;
     --bg-card: rgba(17, 24, 39, 0.75);
     --bg-card-hover: rgba(31, 41, 55, 0.85);
     --border-card: rgba(255, 255, 255, 0.08);
     --border-glow: rgba(99, 102, 241, 0.3);
     
     --color-up: #10b981;
     --color-up-glow: rgba(16, 185, 129, 0.25);
     --color-down: #ef4444;
     --color-down-glow: rgba(239, 68, 68, 0.25);
     --color-paused: #6b7280;
     
     --accent-primary: #6366f1;
     --accent-secondary: #8b5cf6;
     --text-heading: #f9fafb;
     --text-body: #9ca3af;
     --text-muted: #6b7280;
     
     --radius-sm: 8px;
     --radius-md: 12px;
     --radius-lg: 18px;
     --shadow-glass: 0 10px 30px -5px rgba(0, 0, 0, 0.5), inset 0 1px 0 0 rgba(255, 255, 255, 0.1);
   }
   ```

4. **Component Hierarchy (Atomic Design)**:
   - **Atoms**: Badges, Pulsing Status Indicators, Inputs, Buttons, Icon Wrappers.
   - **Molecules**: Metric Cards, Monitor Item Row, Status Timeline Bar, Toast Alerts.
   - **Organisms**: Real-time Dashboard Grid, Incident History Timeline, Public Status Hero.

5. **Accessibility (WCAG 2.2 AA Compliance)**:
   - Minimum 4.5:1 contrast ratio for body text, 3:1 for large headings and UI icons.
   - Interactive elements must have clear focus rings (`outline: 2px solid var(--accent-primary)`).
   - Status indicators must use both color AND textual/icon indicators (never color alone).

---

## 🚀 2. Interaction & Micro-Animations

- **Status Pulse Animation**:
  ```css
  @keyframes statusPulse {
    0% { box-shadow: 0 0 0 0 var(--color-up-glow); }
    70% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
  }
  .status-dot-up {
    animation: statusPulse 2s infinite;
  }
  ```
- **Hover Micro-Interactions**:
  - Smooth scale on card hover (`transform: translateY(-2px); transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1)`).
  - Subtle glow shift on hover (`border-color: var(--border-glow)`).

---

## ⚡ 3. UI Guidelines for Pet-Uptime-Monitor

1. **Header & Navigation**:
   - Floating glassmorphism navbar with brand logo (glowing status pulse dot).
   - User profile badge with quick status overview.

2. **Metric Summary Grid**:
   - 4 key KPI cards: Total Monitors, Operational %, Active Incidents, Avg Response Time.
   - Glowing gradient top borders for KPI metrics.

3. **Monitor Cards / Table**:
   - Latency response time sparklines / visual bar indicators.
   - Quick action buttons (Pause, Edit, Delete, View Public Status).

4. **Public Status Page**:
   - High-impact hero header: "All Systems Operational" (emerald gradient banner) or "Partial Outage" (amber banner).
   - 90-day uptime history bars with tooltip hover stats.
