---
name: BiblioRef
description: Dark-sidebar audit console for reviewing extracted bibliographic references at volume.
colors:
  sidebar: "#101a30"
  sidebar-2: "#0b1322"
  sidebar-line: "#1f2c47"
  sidebar-text: "#aab3c8"
  accent: "#2f6feb"
  accent-dark: "#1f56c4"
  accent-bg: "#e9f0fe"
  canvas: "#f4f5f7"
  surface: "#ffffff"
  line: "#e2e4ea"
  ink: "#141824"
  muted: "#6b7280"
  muted-sidebar: "#7c869c"
  line-hover: "#d3d6de"
  disabled-fill: "#c7cad3"
  loader-track: "#d9dce3"
  ok: "#15803d"
  ok-bg: "#e7f6ec"
  warn: "#b45309"
  warn-bg: "#fdf1e2"
  danger: "#c0293b"
  danger-bg: "#fbe9eb"
typography:
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.03em"
rounded:
  sm: "7px"
  md: "10px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "22px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  nav-item-active:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "9px 11px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 9px"
  badge:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "3px 9px"
---

# Design System: BiblioRef

## Overview

**Creative North Star: "La Consola de Auditoría" (The Audit Console)**

BiblioRef now presents as a control room for a task that is genuinely exacting: auditing hundreds of extracted bibliographic references before they feed a published study. A fixed dark-navy sidebar anchors the four real screens (Inicio, Proyecto, Referencias por tesis, Exportar); everything to its right sits on a light neutral canvas of white, rounded, softly-shadowed cards. One blue accent — never a second decorative color — marks the active screen, primary actions, and focus states. Status is always a small pill badge in a semantic color (green = reviewed/ok, amber = needs review, red = audit-required), never a decorative flourish. This is a deliberate, user-directed replacement of the project's prior "reading room" paper identity — chosen explicitly by the user after reviewing this exact reference and confirming it over the earlier, more atmospheric direction. Nothing about the visual world is aspirational: every screen, field, and status shown is a real product capability: no fabricated confidence scores, no duplicate-detection UI, nothing PRODUCT.md doesn't back.

**Key Characteristics:**
- Persistent dark sidebar (`#101a30`) as the one wayfinding constant; content area is light and neutral.
- One accent color (`#2f6feb`, "Azul Consola") carries every primary action, active state, and focus ring — nothing else competes with it for attention.
- System sans-serif throughout (no custom font load) — a practical, honest choice for an internal audit tool, not a stylistic default.
- Cards, inputs, and popovers share one consistent radius (10px / 7px for compact controls) and one soft elevation language — no hard offset shadows, no flat brutalist edges (that belonged to the prior world and is retired with it).
- Status is always semantic-color pill badges (ok/warn/danger/neutral) tied to real data fields — never invented metrics.

## Colors

Two-register palette: a fixed dark navy sidebar plus a light, mostly-neutral content world, with exactly one accent hue doing all of the emphasis work.

### Primary
- **Azul Consola** ("Console Blue", #2f6feb): the only accent color in the system. Used for the active sidebar item, primary buttons, focus rings, the current-reference selection ring, and links. Never used decoratively.

### Neutral
- **Sidebar** (#101a30): the fixed navigation column background — the one constant across every screen.
- **Sidebar Line** (#1f2c47): sidebar-internal dividers (foot section border).
- **Sidebar Text** (#aab3c8): inactive nav-item text and sidebar meta copy; brightens to white on hover/active.
- **Lienzo** ("Canvas", #f4f5f7): the page background behind all content cards.
- **Superficie** ("Surface", #ffffff): every card, input, table, and popover surface.
- **Línea** ("Line", #e2e4ea): borders and dividers on the light side of the system.
- **Tinta** ("Ink", #141824): primary text on light surfaces.
- **Atenuado** ("Muted", #6b7280): secondary/meta text — labels, captions, timestamps.
- **Atenuado Sidebar** (#7c869c): a dimmer step below Sidebar Text, reserved for the sidebar footer's least-important line (local/version notice).
- **Línea Hover** (#d3d6de): the border a default button takes on hover, one step darker than Línea.
- **Deshabilitado** (#c7cad3): the flat fill for a disabled primary button (see Buttons, Disabled).
- **Pista de Carga** (#d9dce3): the loader spinner's track ring.

### Semantic (state colors)
- **Verde Auditoría** (#15803d, background #e7f6ec): reviewed / confirmed / ok state.
- **Ámbar Revisión** (#b45309, background #fdf1e2): needs-review / pending state.
- **Rojo Auditoría** (#c0293b, background #fbe9eb): audit-required / problem state — the reference-card left-border accent and the strongest semantic color in the system, reserved for exactly this meaning.

### Named Rules
**The One Accent Rule.** Console Blue is the only non-semantic, non-neutral color anywhere in the system. A new component that wants a second "brand" color is wrong; it wants a stronger use of blue, more white space, or a semantic state color instead.

## Typography

**Font:** system sans stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif`) — no custom webfont load. This is a deliberate practicality choice for an internal audit tool matching the user's pinned reference, not a placeholder.

**Character:** Clean, dense, functional — the typography gets out of the way of the data. Weight (700 for headings/titles, 600 for labels, 400 for body) carries hierarchy; there is no display/decorative register.

### Hierarchy
- **Headline** (700, 24px, -0.01em tracking): one per screen, the page's `.h1`.
- **Title** (700, 13–17px): card titles, table row titles, modal titles, stat-box values at the top of that range.
- **Body** (400, 12–16px, 1.4–1.6 line-height): base page text, reference text, lead paragraphs, form values — the real reading content; the base document size is 14px.
- **Label** (500–700, 9–12px, uppercase where used as an eyebrow, 0.01–0.04em tracking): table headers, stat-box labels, badges, sidebar nav, field labels — this is a genuinely wide, intentional range since it spans nav items down to the smallest field captions.

## Layout

A fixed 236px dark sidebar (icon + label nav for the four real screens, wordmark and a compact "Local / APP version" footer) sits to the left of a light content column at all desktop and tablet widths. Below 1180px the sidebar becomes a horizontal, internally-scrollable bar (no page-level horizontal overflow at any width down to 375px on Inicio, Proyecto, and Exportar). The review workspace keeps its three-column grid (250px metadata / flexible viewer / reference list) down to roughly 430px, below which it does not yet adapt further — a known, accepted limit carried over from the prior world, not something this redesign was scoped to solve.

Content sits on generous white space: 28–32px screen padding, 12–18px card gaps, cards with 14–16px internal padding. Density stays appropriate to an audit tool (the review workspace is still the densest screen) without inheriting the prior world's tight, utilitarian rhythm everywhere.

### Named Rules
**The Sidebar-Is-Truth Rule.** The active sidebar item is the only place "where am I" is answered with full confidence; the topbar's small eyebrow label is a secondary echo, never the primary wayfinding signal.

## Elevation & Depth

Soft, conventional elevation: cards and tables carry a barely-visible ambient shadow at rest (`0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)`); popovers and the modal step up to a stronger, still-soft shadow (`shadow-md`). This is a full reversal of the prior world's hard offset "stamped" shadows — deliberately conventional, because the brief that replaced the old world explicitly asked to move away from anything with a strong, idiosyncratic material signature.

### Named Rules
**The Soft-Shadow-Only Rule.** No hard offset (zero-blur) shadows anywhere in this system. Elevation is always a soft, blurred shadow at one of two strengths (ambient for resting surfaces, `shadow-md` for anything overlaid).

## Shapes

Rounded corners throughout, on a real 4-step scale: 6–7px for the smallest controls (compact `.xs` buttons, small inputs), 8px for standard buttons and sidebar nav items, 10px for cards/inputs/popovers/the modal, and full pill radius for badges, status tags, and the loader. This is the opposite of the prior world's zero-radius rule — a deliberate, named reversal, not drift.

## Components

### Sidebar Navigation
- **Style:** icon + label rows, 8px radius, transparent at rest.
- **Active:** solid Console Blue fill, white text and icon.
- **Hover (inactive):** a slightly lighter navy fill (`--sidebar-2`), white text.

### Buttons
- **Shape:** 7–8px radius, 1px border on the default variant.
- **Primary:** Console Blue fill, white text — one per screen/section at most.
- **Default:** white fill, neutral border, hover to a barely-tinted gray.
- **Disabled:** one dimming mechanism only — the primary variant swaps to a flat light-gray fill (`#c7cad3`) at full opacity rather than fading a colored fill via opacity (that combination was tried and reverted earlier in this project's history for reading as nearly invisible; the lesson carried into this world).

### Badges / Pills
- **Style:** full pill radius, no border, colored background + colored text tied strictly to the semantic palette (ok/warn/danger/neutral).

### Cards
- **Corner Style:** 10px radius.
- **Background:** white on the light canvas.
- **Shadow:** ambient at rest; no shadow change on hover for static cards.
- **Border:** 1px `--line`.

### Data Table
- **Style:** white surface, 10px-radius container, sticky uppercase label header on a barely-tinted gray, 1px row dividers, hover row tint.

### Reference Item (signature component, carried over in behavior)
- **Base:** white card, 10px radius, ambient shadow.
- **Current (selected):** Console Blue border plus a 1px Console Blue ring (`box-shadow: 0 0 0 1px var(--accent)`), replacing the prior world's thick ink border.
- **Problem (audit-required):** 3px red left-border accent — the mechanism is unchanged from the prior world, only the color and corner radius updated to this system's palette and shape language.

## Do's and Don'ts

### Do:
- **Do** keep Console Blue as the only non-semantic accent color in the system.
- **Do** use soft, blurred shadows only — ambient at rest, `shadow-md` for anything overlaid.
- **Do** round every surface (10px cards/inputs, 7px compact controls, full pill for badges/status).
- **Do** tie every badge/pill color strictly to its semantic meaning (ok/warn/danger/neutral).
- **Do** keep the sidebar as the primary, always-visible wayfinding signal.

### Don't:
- **Don't** introduce a second decorative accent color.
- **Don't** use a hard offset (zero-blur) shadow anywhere — that belongs to the retired prior world.
- **Don't** leave any corner sharp; this system's signature is soft roundedness, the opposite of its predecessor.
- **Don't** show a capability the product doesn't have (confidence scores, duplicate detection, or any other metric not backed by real data) — confirmed explicitly as out of scope for this rebuild, matching `PRODUCT.md`'s roadmap notes.



## Project entry flow (2026-09-08)

Inicio now lists saved projects only, with a New project action and project search. Thesis names and PDF previews belong to an opened project. A separate Tesis del proyecto screen preserves import folders in a right-side explorer; Resumen, Referencias por tesis and Exportar retain their existing roles. Navigation into thesis review is disabled when the selected project has no documents. The existing console palette and typography remain authoritative.

University grouping is optional, marked Experimental, and only groups loose files. Existing folders always take priority. Suggested universities remain correctable through the thesis metadata form. An empty installation has no seeded projects or theses.

### Readability and progress iteration (2026-09-09)

Project controls now use 14–17px text, thesis titles 16px and navigation 14px, with a darker muted text color (#505c70). A project search filters thesis cards and the folder explorer. Import buttons state their actions directly. An operation banner remains visible during work: actual transfer bytes drive the upload percentage, preparation is indeterminate, and batch extraction progress counts completed theses. Completed/error banners remain in document flow instead of occupying sticky space. Motion respects prefers-reduced-motion. These settings supersede the smaller project-entry typography above.

The local import reading stage now reports server events: completed PDF count, durable imported count, current filenames and elapsed time. Thesis cards and folder nodes appear on each durable document event. Transfer and PDF preparation remain separate stages; no completed batch is claimed until the terminal event arrives. A prolonged lack of server events is stated explicitly. Parallel reference processing uses the same file-and-count presentation. This supersedes the indefinitely animated reading stage.

### Adjustable project workspace (2026-09-09)

The collection screen uses a compact import toolbar above the workspace. The explorer defaults to the left and shares a tall workspace with the thesis list. Drag its header onto a left/right/top target or use Disposición; drag the separator or use its arrow keys to resize. Explorer visibility, side, width and top height are browser preferences and persist across projects/reloads. Restablecer disposición restores the default left layout. At narrow viewport widths the explorer stacks above the list without overwriting desktop preferences. Tab order follows the displayed pane order.

Explorer filenames use single-line ellipsis with their full name/title on hover. A click selects and scrolls to the corresponding central thesis card, retaining the collection view; a double click opens review. University grouping is in a collapsed details section. The import, persistence and PDF processing routes are unchanged. This iteration provides docking within the project collection, not floating desktop windows or docking of every review panel.
