# Design Guidelines

Living design corrections, requested 23 October 2026. Append subsequent requests here.

## Required patterns

- No default outlines on cards, text containers, fields, upload areas or buttons. Use background and spacing. Grey fields, black text, white page. Red rings only for focus, selection and validation. Preserve keyboard focus.
- Generous rounding: 28 px panels, 22 px choices, 16 px fields, 16 px buttons.
- Use official Alfa-Bank font and exact SVG logo once source assets are obtained and verified. Never label approximations as official assets.
- Consistent number typography: grouped amounts, tabular figures, readable weight, aligned rates. Visually group INN/OGRN without modifying identifiers. Grouping is a project convention, not a bank-verified standard.
- Purpose choices: grey/black by default, black/white when selected; short colour transitions.
- Product cards: grey surface, red emphasis on selection or keyboard focus.
- Four-step numbered cards with a dark current step: Задача / Условия / Данные о бизнесе / Отправка. Mark current step accessibly.
- Amount: grouped editable number at 20 px in the same 58 px field as other inputs, separate ₽ suffix. Thick rounded slider with round thumb and subtle interaction shadow. Support keyboard and reduced motion.
- Checkbox: rounded grey default surface, red checked state, white tick, keyboard focus.

## Screen corrections

- My applications: remove company-name heading and explanatory subtitle; use Мои заявки. Remove duplicate red financing button on the right. Keep top financing navigation and empty-state Подобрать кредит (latest clarified instruction).
- Cleaner 24 px notification bell SVG.
- Company identifiers: grouping and wider label/value spacing.
- Dashboard/business data: shared horizontally scrollable turnover chart with arrows, month/year labels, scale, grid and values. Use actual returned data only. Additional history requires backend data; do not fabricate months or amounts.
- Product recommendations: aligned rates, amounts and terms, without decorative number typography.
- Submission: same borderless style and rounded checkbox.

## Pending brand verification

Official site https://alfabank.ru/ attempted: browser certificate error, terminal DNS unavailable.
Official Alfa Laboratory typography documentation identifies Styrene UI:
https://alfa-laboratory.github.io/core-components/0505b8ef8ce6078ed566f305ce2a1e67fd6a1a39/?path=/story/гайдлайны-типографика--page
Verified font source: https://github.com/alfa-laboratory/core-components/blob/master/docs/6.typography.stories.mdx
UI typeface: Styrene UI, Regular 400 / Medium 500–600 / Bold 700; enable ss01.
Brand context (Styrene A and B): https://type.today/ru/journal/styrene-alfa
`frontend/scripts/prepare-fonts.mjs` downloads the official WOFF2 files from alfabank.gcdn.co before dev/build, validates the file signature and caches them under public/fonts. The built app serves them locally; no runtime font CDN. System UI is the loading fallback. Font files could not be downloaded in this execution environment (ENOTFOUND), so an actual Styrene render is not yet verified.
Six screenshot references are in the chat, but their image bytes could not yet be inspected. Reference-specific visual comparison remains pending.

The placeholder logo has been replaced with the original SVG path from Alfa Laboratory:
https://github.com/alfa-laboratory/icons/blob/master/packages/logotype/src/AlfaBankLogoMIcon.tsx
Source revision: 9ffde4b1d37abdacce63e45121a3fa9ce8d44b22; package declares MIT. No geometry has been redrawn. Matching the particular screenshot variant remains unverified.

## Validation status

Implemented: shared surfaces/radii, dashboard text/actions, identifier grouping, bell, step strip, choices, amount/slider, checkbox and chart.
Pending: official local font assets, screenshot comparison, successful frontend build/typecheck and browser visual review of the changed build.
Dependency installation attempted offline; npm cache lacked required packages. Docker socket is inaccessible from this ChatGPT environment.

## Follow-up verification, 23 October 2026

- Source: direct user instructions in this conversation. Related backlog: HACK-021, GitHub issue #22; this correction pass does not claim the entire issue is complete.
- Local port 8081 serves the existing login screen; it does not prove the edited source is deployed.
- Fixed chart arrow availability after viewport resizing, aligned scale/grid with the actual bar plot, and kept zero turnover at zero height.
- Keyboard focus uses the red accent; forced-colors mode restores visible control boundaries.
- Official site retry failed with ERR_CERT_AUTHORITY_INVALID; no browser warning was bypassed.
- Rebuild the web service with `WEB_PORT=8081 docker compose up -d --build web` to review these local changes.

## Latest requested corrections

- Active top navigation: dark pill, white text on desktop and mobile.
- Favicon: official Alfa Laboratory mark, cache-busted URL; same shared mark on login and in the cabinet.
- INN/OGRN: larger tabular numbers with fewer visual groups; original identifier digits remain unchanged.
- Turnover chart: muted blue-grey bars, all corners rounded, zero aligned to the baseline. Axis marks use 1/2/5 multiples (a 2.6 million peak yields 0/1/2/3 million).
- Steps: numbered cards, checkmarks for completed steps, dark current step; two columns on phones.
- Conditions: smaller amount text and matching input dimensions.
- Bell: original filled BellMIcon from Alfa Laboratory, quiet hover surface.
- Financing sidebar: intentionally deferred by user until this correction pass is reviewed and committed; no sidebar content added.

Validation: node --check passed for the font preparation script; executable assertions passed for rounded chart bounds, zero ticks, finite scale and preserving INN/OGRN digits. git diff --check passed. Frontend typecheck is blocked by missing tsc; Docker is blocked by socket permission. Browser documentation access was declined by the origin approval gate. No claim of build/E2E or screenshot verification.

## Font build regression fix

The official CDN returned ERR_SSL_TLSV1_ALERT_INTERNAL_ERROR during Docker build.
Normal dev/build preparation now only checks local font files and never fetches.
Missing Styrene weights fall back to bundled Onest. Explicit download remains
available through npm run download:fonts; TLS verification stays enabled.
Five node:test regression cases pass: offline build, cached files, TLS rejection,
invalid download rejection and successful explicit download. The actual prebuild
hook passes without network access. Full Docker build remains unverified here.
This supersedes the earlier automatic-download description.

## Company, input and live-summary corrections

- Company identifiers now display original digits without inserted spacing. Dedicated label/value columns wrap long activity and director text without overlap.
- Text fields share a grey rectangular surface with a small label inside at the top and the value below; currency suffixes remain aligned on the right. Applied to financing and login inputs.
- Financing sidebar is now authorized and implemented: purpose, product, preliminary rate, live amount/term/payment, financial data and document count. Previous sections have edit links. Mobile/tablet uses a collapsible summary before the form.
- Steps use one horizontal row for number and title. Earlier steps are keyboard-accessible buttons; future steps remain disabled. Returning does not clear entered state, and edits reset submission consent.
- Browser icon assets include ICO, 32 px PNG, SVG and Apple touch PNG using the same original Alfa Laboratory geometry (white mark on red). New asset names invalidate the previous SVG URL.
- Verified TS/TSX syntax transpilation for every frontend source file using the available TypeScript compiler. This is not a full semantic typecheck or production build. Raster icon inspected visually; PNG/ICO dimensions checked. Docker/browser review of this build is still pending.

## Selection, navigation and amount typography refinement

- Removed the "Собираем условия по шагам" summary caption.
- Purpose and product selections toggle off on a second click. Selecting a product stays on the task step; Continue activates only after task and product selection.
- Grey small "← Назад" actions sit beside the main action on conditions, business and review steps.
- Header navigation permits forward steps when their prerequisites are valid. Moving from edited task/conditions into business/review saves the current draft first, preventing submission of stale terms. Submission consent resets during navigation.
- Overdraft uses the shared labelled amount input and a matching read-only fixed-term field.
- Prominent amounts use the calculator typeface with bold tabular numerals, including the summary payment and amount, editable money fields and final review.
- Turnover bars have rounded tops and square bottoms. Month columns are wider and the business chart viewport is capped so the returned six months remain scrollable on desktop. Uploaded statement figures use the same chart.
- Two component-handler regressions pass: toggle/manual continuation/back navigation; invalid amount blocking and persisting changed terms before forward review. These exercise the real page handlers with mocked React/API; they are not browser E2E. Full frontend syntax transpilation passes; production build remains unverified in this environment.

## Application list, editing and reuse

- Step buttons are content-sized pills with fully rounded ends; they no longer stretch across the form width.
- One grey plus/create action sits below the applications panel, whether the list is empty or populated.
- Applications are paginated locally in groups of eight, with previous/next controls and the current/total page count. API response remains unchanged.
- Draft details include an edit action opening the wizard at /new?edit=ID with existing values and attachments. Saving updates the same ID with its current version; only DRAFT is accepted for editing, in addition to server authorization/state checks.
- The details header includes Create based on (/new?copy=ID). It prefills purpose, product, amount, term and collateral, but creates a separate draft. Documents, decisions, agreements and consent are not copied. The form explicitly says to attach documents again.
- Initialization uses the authorized original application and current product catalog, without requiring the recommendation service. Original selection is not labelled as the best recommendation.
- Seven mocked-component regression cases pass, covering the existing wizard, edit/version handling, copy isolation, non-draft edit rejection, 8/8/1 pagination and a single create action. Full frontend syntax transpilation passed; full production build/browser review remains unverified here.
