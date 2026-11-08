# English product-page report

The site is now English throughout: marketing copy, the PDF example, demo responses, generated calibration labels, accessibility labels, setup notes, and README. The desktop app itself has not been translated. Its current Korean speech/tutor configuration is disclosed in the setup guide.

## Direction and skills

Type: software. Primary action: **Try the demo**. The page introduces the Study Signal macOS study companion through its actual subject: a probability problem, a small assistant window, and gaze calibration.

Two official-source skills were installed and read: [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) and [Vercel web-design-guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines). Installation details and source checks are in [frontend-skills.md](frontend-skills.md). They are installed in the workspace's `.agents/skills` and available in following turns.

The first cream/serif/terracotta idea was rejected after reading the fresh frontend-design instructions, which identify that combination as a common default. The implemented direction uses cool paper (#f3f6f8), blue pencil (#2859b8), white pages, and dark ink (#233443). Whole headings use local Instrument Serif; body and controls use local Outfit. Both fonts have OFL licences beside them. The blue document margin is the main visual detail. Headings do not pick out a single italic or coloured word. Feature numbers, all-caps labels, glow backgrounds, repeated feature cards, and fabricated testimonials are absent. The reference's earlier orange treatment has been replaced under the user's new request.

The existing Taste Skill button-motion layer is retained. New sections follow their content instead of imposing a fixed one- or two-screen height. This keeps translated explanations and selected paragraphs readable on small screens. Headings use sentence case according to the chosen frontend-design direction; this is intentional where the generic Vercel checklist prefers title case.

No stock imagery, invented metrics, customer quotes, pricing assumptions, or replacement image slots were used. Product surfaces are HTML. The demo does not use a camera, microphone, AI endpoint, or third-party resource.

## Verified behavior

**53 browser checks passed, zero failed.** This includes scenarios, opacity, progressive hints, contextual highlighting, keyboard tabs, keyboard focus after selecting calibration targets, the 9-target/5-check sequence, mobile menu state and viewport coverage, inert background content while the menu is open, Escape, local resources, and opening a `?demo=help` deep link.

At widths **1440, 1024, 820, 768, and 390**, checks found no horizontal overflow or overlapping page sections. They also verify that the hero assistant leaves its formula readable, the question leaves its selected paragraph readable, and the answer stays inside the study window. The first pass found four real overlaps at narrow widths; these were fixed by stacking the tablet layout and letting the mobile assistant follow its paragraph in the document flow.

Body text was darkened for stronger reading contrast, including the stricter body-copy target used by the legacy checker. The translucent assistant's principal text colours were checked at the minimum opacity of 72% over a conservative white background: approximately **4.65:1–5.08:1**, including the light question bubble. Focus rings are visible on both light and dark surfaces. Native action buttons, calibration targets, the menu toggle, and the opacity field have 44px touch areas.

All public HTML/JS strings were checked for remaining Korean, including generated labels. HTML IDs, local files, and cross-page anchors were checked. Images have dimensions and alt handling. Math-card illustrations have image roles and descriptions. Code tokens in setup notes are marked against automatic translation. Reduced motion is supported and the only scrolling animation follows a user action.

## Performance

One local CPU-headless run per desktop/mobile size reported roughly **240 KiB transferred**, **CLS 0**, **zero failed requests**, and **zero WebGL contexts**. The performance checker returned **0 FAIL / 4 WARN**. Warnings are the two local font files totaling about 177 KiB, plus a tiny repeated logo without a lazy attribute, once per tested size. These are local measurements, not a real-network speed guarantee.

## What this does not validate

This is website/UI verification. It does not validate real webcam gaze accuracy, false-alarm rates, macOS global key release, Apple Watch delivery, or English voice support in the desktop prototype. Physical Safari/iOS and assistive-technology testing have not been performed. The page is served locally, not deployed to external hosting.

## Evidence

[53 interaction checks](qa/product-en-interactions.png) · [Desktop](qa/product-en-desktop.png) · [Mobile](qa/product-en-mobile.png) · [1024px](qa/product-en-1024.png) · [820px](qa/product-en-820.png) · [768px](qa/product-en-768.png) · [Performance JSON](qa/product-en-performance.json)

## Strict Taste Skill diagnostics

The last legacy-format check returned **45 FAIL / 11 WARN**. Its checker was not modified or disabled. These are retained in [the raw report](qa/product-en-style-checks.json); a global style pass is not claimed. The new page deliberately follows the user's English redesign request and the newly installed frontend-design direction instead of the former fixed-screen template.

Every remaining FAIL falls into the following recorded exceptions:

- **Literal headline/fact rules:** the category and Mac platform appear in the opening sentence; the headline is the study-specific phrase “Stay with the hard part.” Problem and calibration headings are meaningful in their actual UI context. No number, price, or fake proof was added to satisfy a keyword detector.
- **Hero strip interpretation:** the second direct child of the hero grid is a full product window alongside the copy, not a docked strip. It is intentionally taller than the kit's 96px strip limit.
- **Fixed screen heights and section peeks:** sections have natural lengths. The mobile answer can grow after a user asks a question, keeping the target paragraph readable. The checker requires one/two exact viewport heights, unchanged after interaction, and no adjacent section visible; these constraints are intentionally not used.
- **Footer padding:** the checker subtracts its global 72px/48px padding targets; this footer uses 32px/28px. The actual content remains within the footer with clear bottom padding, as verified by the interaction test.
- **Template structure and grids:** the footer has a call, privacy information, and legal row; the ordered list has an intentional number indent; hero/demo/calibration columns use their own useful proportions. The checker requires exactly two footer children and one fixed 12-column split alignment. Vertical centering in the hero is intentional.

No horizontal overflow, actual page-section overlap, selected-text occlusion, or answer-window overflow remained in the final five-size browser tests. Real tablet overlaps identified in the initial test were fixed rather than treated as stylistic exceptions.

Tablet images show the responsive composition before the final contrast/footer refinement; the linked desktop and mobile images show the final design. The performance figures were measured before the small final contrast/focus changes, which do not add resources or change the font payload.
