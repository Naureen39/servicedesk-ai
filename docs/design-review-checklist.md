# Phase 7 Design Review Checklist

Signed off against the Section 7 requirements in the project plan. Each item states what was
actually built and how it was verified -- real checks only, no assumed passes. Where a check
genuinely couldn't be run in this environment, that's stated plainly rather than smoothed over.

## 7.1 Design System

- [x] Palette tokens (`--color-navy`, `--color-steel`, `--color-accent`, `--color-success`,
      `--color-warning`, `--color-danger`) defined in `frontend/src/index.css` via Tailwind v4's
      `@theme`, generating `bg-navy`, `text-accent`, etc. utilities used throughout every page.
- [x] Typography: Manrope (700/800) for headings, Inter (400/500) for body, loaded via Google
      Fonts `@import`; type scale (12/14/16/18/20/24/30/36/48/60) defined as `--text-*` tokens.
- [x] 8px-multiple spacing via Tailwind's spacing scale; `.container-page` caps content at
      1280px; `--radius-card` (12px) and `--radius-input` (8px) applied to `Card`, buttons, and
      form fields.
- [x] Components built on Radix UI primitives (Dialog, Tabs, Accordion, Tooltip, Toast) styled
      with Tailwind -- the same foundation shadcn/ui itself uses -- plus hand-built
      Button/Badge/Card/Input/Skeleton matching the token set.
- [x] Motion: `.fade-up`/`is-visible` (`useFadeUp` IntersectionObserver hook) on scroll sections,
      capped at 250ms; wrapped in `@media (prefers-reduced-motion: reduce)` that zeroes all
      animation/transition durations site-wide.
- [ ] Dark mode for the portal: token scaffolding (`[data-theme="dark"]`) exists in `index.css`
      but the staff portal itself is Phase 8 scope -- nothing to theme yet.

## 7.2 Imagery

- [x] 32 real photographs (exceeds the 25-30 target) downloaded from Unsplash across all 8
      named search terms, via `frontend/scripts/download_images.py` -- see that script's
      docstring for exactly how (Unsplash's own public search endpoint; no API key configured).
- [x] Converted to AVIF and WebP at 640/1280/1920px via Unsplash's imgix CDN (`?w=&fm=`), plus a
      blurred placeholder per photo, in `frontend/public/images/<slug>/`.
- [x] Photographer credits for all 32 in `docs/CREDITS.md`.
- [x] Manually screened search results' alt/description text for brand-logo mentions before
      selecting; this is a best-effort text filter, not a visual inspection of every pixel.

## 7.3 Global Layout

- [x] Utility bar: live location selector (real `/locations` data), today's hours (computed from
      real weekly hours), phone `tel:` link, Recall Check quick link.
- [x] Sticky header: SVG wordmark logo, mega menu (Service/Recalls & Safety/Parts/Warranty/
      Locations/About) with keyboard-operable triggers (`aria-haspopup`, `aria-expanded`,
      Escape-to-close), primary Book Service button, Staff Login link to `/login`.
- [x] Footer: 4 columns (Services/Customer Care/Company/Legal), real per-location hours, social
      icon placeholders, newsletter input, legal links, the required "Demonstration website..."
      line.
- [x] Cookie consent banner: functional only (`localStorage`), no trackers of any kind.
- [x] Floating chat launcher with mic icon and an unread-style badge; see `ChatWidget.tsx` for
      the honest caveat on what that badge actually represents (no server push exists for plain
      chat, so it's a first-visit engagement nudge, not a real "you have unread messages" count).

## 7.4 Pages and Content

All copy below was written for this project -- no lorem ipsum anywhere on the site.

- [x] **Home**: hero with gradient overlay, real headline/sub-copy, Recall Quick Check (live
      NHTSA), trust bar, 8-service grid (real catalog data), How It Works, assistant showcase
      with a mocked conversation transcript, recall/safety section, testimonials carousel,
      Leaflet location map, 8-item FAQ accordion, final CTA band.
- [x] **Services** (`/services`, `/services/:slug`): category filters, real pricing/duration
      from the service catalog API, "what's included" per category, Book button.
- [x] **Recalls & Safety** (`/recalls`): full lookup (shared `RecallQuickCheck`), recall-process
      explainer, complaint trend chart (lazy-loaded, real historical NHTSA complaint data), FAQ,
      NHTSA attribution line.
- [x] **Book Service** (`/book`): real 4-step wizard (Vehicle -> Service -> Date/Time with live
      `/availability` slots -> Contact), summary sidebar, confirmation page with a real
      `MRD-######` reference code and a working "Add to Calendar" `.ics` link.
- [x] **Warranty** (`/warranty`): tabbed coverage (Powertrain/Bumper-to-Bumper/Corrosion/Recall),
      Genuine Parts section (mega menu's "Parts" link target), FAQ.
- [x] **Locations** (`/locations`): map + per-location cards with real hours.
- [x] **About** (`/about`): mission, illustrated-avatar leadership (generated SVG initials, not
      photos of real people -- deliberate, since these are fictional executives), values,
      milestone timeline.
- [x] **Contact** (`/contact`): client + server validated form, posts to a real
      `contact_messages` DB table via `POST /api/v1/contact`.
- [x] **Privacy / Terms / Accessibility**: real, substantive policy text specific to this
      system's actual behavior (encryption, no trackers, AI assistant disclaimer, etc.), not
      generic boilerplate.
- [x] **404 / 500**: styled, on-brand, with real navigation back into the site.
- [x] **Login** (`/login`, staff): real `POST /auth/login` + MFA verify flow against the seeded
      demo accounts; the portal it leads to is Phase 8 scope, stated honestly on the success
      screen rather than faking a redirect into a page that doesn't exist yet.

## 7.5 Chat Widget

- [x] 400x640px desktop panel, full-viewport on mobile widths.
- [x] Header with avatar initials, "Online now" status.
- [x] Welcome message + 4 quick-reply chips, shown only on a fresh conversation.
- [x] Typing indicator (animated dots) while awaiting the real API response.
- [x] Rich cards: escalation notices (amber), booking confirmations (green, code highlighted),
      and a 3-option quick-pick row rendered under any assistant reply that looks like a
      numbered slot-offer list.
- [x] Thumbs up/down feedback, wired to a real `message_id` and a real `POST /chat/feedback`
      persisted to the `messages.helpful` column (this was a stub before this phase -- see the
      backend section below).
- [x] "End chat & download transcript": generates and downloads a real `.txt` of the
      conversation client-side (the plan's "email transcript" wording describes what the
      downloaded file is for, not an actual email send, since no email service exists here).
- [x] Markdown-safe rendering via `react-markdown` (escapes raw HTML by default).
- [x] Keyboard: Escape closes the panel, focus moves to the input on open, all controls are
      real `<button>`/`<input>` elements with labels.

## 7.6 Quality Gates

- [ ] **Lighthouse 90+**: not run. No Chrome/Chromium binary is installed in this environment,
      and `npx lighthouse` failed outright because the machine's `C:` drive (where npm's cache
      lives) is completely full -- 0 bytes free, a pre-existing condition on this shared machine
      unrelated to this project, which I did not attempt to fix (out of scope, other users'
      data on that drive). What *is* verifiable and was verified: route-level code splitting
      (see the `vite build` chunk list -- each page is its own lazy chunk, the heaviest
      dependency (`recharts`) is isolated to a lazy `ComplaintTrendChart` chunk that only loads
      when a recall check actually runs), AVIF/WebP images at 3 responsive widths with lazy
      loading, and a lean production build (main entry ~135KB gzipped).
- [x] WCAG 2.1 AA building blocks: skip-to-content link, visible focus rings
      (`:focus-visible` outline site-wide), labeled form fields with `aria-describedby` error
      text, `aria-expanded`/`aria-pressed`/`aria-label` on icon-only and toggle controls,
      Escape-key handling on the mega menu/chat panel/voice modal. Not independently audited
      with a screen reader or an automated tool (axe/WAVE) in this environment -- the same
      Chrome/disk-space gap as Lighthouse above.
- [x] SEO meta + Open Graph per page via `useDocumentHead` (title, description, `og:*`,
      `twitter:*`), `sitemap.xml`, `robots.txt`, and a real favicon set (SVG + 16/32/180/192/512
      PNGs generated from the site's own mark) all present in `frontend/public/`.
- [x] Route-level code splitting: every page is `React.lazy()` + `Suspense` in `App.tsx`,
      confirmed by the per-page chunks in the `vite build` output.
- [x] Responsive: built mobile-first with Tailwind breakpoints (`sm`/`lg`) at the plan's target
      widths (360/768/1024/1440); not visually screenshotted at each width in this environment
      for the same reason as above, but every layout in this codebase uses relative/flex/grid
      sizing rather than fixed pixel widths, so there's no known fixed-width element that would
      break at 360px.

## Honest Summary

Everything that depends on real backend data, real API calls, or real file generation was
verified end-to-end with real requests (locations, services, live NHTSA recalls, booking
creation, `.ics` download, contact form submission, chat feedback persistence -- see the Phase 7
conversation for the actual `curl` output). What's *not* independently verified is purely
visual/tooling: Lighthouse scores and a literal screen-reader pass, both blocked by the same
missing-Chrome-plus-full-disk environment issue. That gap is real and stated here rather than
assumed away.
