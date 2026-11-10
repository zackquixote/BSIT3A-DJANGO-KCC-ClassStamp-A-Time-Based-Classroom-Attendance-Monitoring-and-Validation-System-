# Interface system

The product surface is a working console for registrars and faculty, not a
marketing page. The visual system is therefore deliberately quiet: one accent,
hairline structure, and colour that means something.

Reference renders: `docs/ui/before-admin-dashboard.png` →
`docs/ui/after-admin-dashboard.png`, `docs/ui/before-login.png` →
`docs/ui/after-login.png`.

## Rules

1. **One accent.** Gold (`--accent-gold`) marks primary actions, focus rings and
   the active navigation item. Nothing else is gold.
2. **Colour is semantic.** Green = present/approved/live, amber = attention,
   red = absent/danger, blue = informational. A colour never appears just to
   decorate a card.
3. **Structure is a hairline.** `--border` (7.5 % white) separates most things.
   Shadows exist only on floating layers: menus, modals, dropdowns, toasts.
4. **One radius family.** 4px for chips/indicators, 6px for controls,
   8px for buttons and inputs, 10px for surfaces, 12px for modals.
5. **Type.** Inter. Page titles 1.3rem/600 with −0.02em tracking; section titles
   0.86rem/600; body 0.9rem; uppercase micro-labels only at 0.69rem/600 with
   0.05em tracking. Numbers use tabular figures.
6. **Icons.** 16px monochrome line icons at `--text-dim`. No icon chips, no
   icons inside table headers, no icons inside badges, no emoji.
7. **Density.** 4px spacing grid; 36px controls; 10px table rows; 14–18px card
   padding.

## Where it lives

| File | Role |
| --- | --- |
| `static/css/variables.css` | Tokens: canvas, borders, accent, status, text, radii, spacing, motion |
| `static/css/refine.css` | The enforcement layer. Loaded last in `classstamp.bundle.css`. Restates the system for cards, KPI strips, panels, tables, forms, badges, buttons, sidebar, auth pages, and phone widths |
| `static/css/base.css` | Reset, layout, utilities (canvas gradient removed) |
| `static/css/dashboard.css` | Admin dashboard composition, restyled by the layer |
| `static/css/components.css` | Shared primitives, restyled by the layer |

`apps/core/services/asset_bundles.py` lists `css/refine.css` after every other
sheet, so page-specific rules can never win over the system by accident.

## What changed in the redesign pass

- Removed gradient headline ink (`.dash-page-title span`), the glowing card
  hover, the pulsing "action needed" border, and every `box-shadow` on resting
  cards.
- Rebuilt the KPI strip: label above value, tabular figures, delta as plain
  text, "Action needed"/"Live" as quiet uppercase flags on their own line.
- Recoloured the KPI and stat icons from four decorative accents to one muted
  ink; neutralised the coloured icon chips on Classes, Teachers, Directory.
- Converted the Quick Launcher from eight bordered tiles to one menu column.
- Flattened the calendar agenda, department list and approval list: hairlines
  between rows instead of a card per row, and no per-row "Approved" repetition.
- Made the bento row equal-height and removed the clipped fifth approval row.
- Unified badges (4px radius, sentence case, no icons), buttons (36px, one
  primary), inputs (36px, gold focus ring), tables (11px muted headers, no
  header icons, 10px rows).
- Rebuilt the sidebar: flat rail, 2px gold marker for the active item, 16px
  muted icons, tighter group labels. Brand wordmark now fits the rail.
- The login page's decorative grid, radial glows and rings are suppressed by the
  layer (the markup is inert decoration, kept in case a future hero needs it).
- Header "ribbons" above page titles are now plain metadata text.
- Phone widths: header metadata stacks, KPI strip goes two-up, panels go
  single-column.

## Intentional structural fixes

- `templates/core/admin/dashboard.html` and `templates/core/admin/calendar.html`
  linked `dashboard.css` / `calendar.css` a second time even though both are in
  the bundle. That cost an extra request and, worse, re-ordered the cascade so
  page rules overrode the design system. The duplicate links are gone.
- `templates/core/teacher/dashboard.html` styled the live-session strip with
  inline green colours. It now uses `.session-live-card`, so the strip is a
  neutral card with one green marker and the icon no longer spins.

## Student surface

The student portal is read on a phone, in a corridor, between classes. It gets
its own hierarchy rather than a smaller copy of the admin console:

- **Header** — one primary action (“Show my QR”), one secondary (“Join a class”),
  and a text link to the attendance log. Excuse slips and the profile live in the
  sidebar and the mobile tab bar.
- **Attendance summary** — a single strip with four figures and hairline
  dividers, instead of four cards with coloured icon chips. On phones the strip
  collapses behind an “Attendance stats” bar that expands in place.
- **Two columns** — the working column (attendance by subject, then excuse
  slips) and a reference rail (this week, exam windows, my classes, college
  calendar). The calendar no longer occupies a third of the page to say nothing.
- **Rows, not boxes** — subjects, slips, meetings, classes, events and schedule
  days are hairline rows. The coloured left borders, tinted tiles and nested
  cards are gone; one figure per row carries the status colour.
- **Honest empty and failure states** — the excuse calendar now says when it
  cannot load instead of leaving a blank card; “nothing overdue” is one line of
  text, not a dashed panel with a 2rem tick.

Student pages touched: `student/dashboard.html` (body rebuilt),
`student/attendance_log.html`, `student/excuse_slips.html`, `student/profile.html`,
`student/qr_badge.html`, `excuse_calendar.html` (failure state).

## The leave & excuse calendar

The page was a stock FullCalendar dropped into the shell: its runtime-injected
light theme painted the header band white and its default emerald blocks fought
the status palette. For a read-only month view it was also the wrong tool, so it
is now a small renderer of our own (`templates/core/excuse_calendar.html`, no
library):

- Header: month, ‹ › Today, and two segmented controls — All / Excuses / Dates
  and Month / List. The view is kept in the URL hash (`#list`, `#excuses`), so a
  refresh or a shared link holds its state.
- Summary strip: pending / approved / rejected / institutional dates.
- Legend and chips: a status dot plus a label instead of a filled block;
  institutional dates are neutral labels, excuse chips link to the slip queue.
- List view follows the visible month, matching the grid.
- A failed fetch now says so instead of leaving an empty card.
- The API stopped baking `[PENDING]` into titles; it sends name, section,
  subject and status separately.

## Student dashboard, checked against the live MySQL data

Signed in as the enrolled student account and fixed what the real data exposed:

- A section with no meetings printed “—”, “No meetings yet” **and** four zeros.
  It now says one sentence: “No meetings recorded for this section yet.”
- The timetable panel and the class list disagreed (“No schedule yet” above a
  listed class). The copy now names the real cause (no meeting times published).
- The calendar rail grew to six multi-line holidays and dwarfed the page. It
  shows the next three dates, one line of description each, and links to the
  full calendar.
- `verify_*` student profiles in MySQL carried `approval_status = NULL`, unlike
  the SQLite copy, so the documented QA logins landed on the approval-waiting
  page. They are APPROVED again (except `verify_pending`, which stays PENDING).

## Checks

- Rendered pages verified at 1440×1000 and 760×1000 through headless Chrome
  against a live server: login, admin dashboard, class sections, academic years,
  teacher dashboard, attendance matrix, excuse slips, and the student surface
  (dashboard, attendance log, excuse slips, profile, QR, term record, calendar).
- Full suite after the student rewrite: **899 tests, OK** (572 s). Two dashboard
  copy assertions were updated with the redesign — the weekly panel is now
  “This week” and the slip tracker reads “My excuse slips”, “Pending review”.
- The stats toggle was exercised in a real browser: hidden on desktop, opens the
  KPI strip on narrow viewports and sets `aria-expanded`.
- The enforced CSP still reports zero violations: no inline scripts were added
  (the calendar's new failure path is inside the existing nonced script).
