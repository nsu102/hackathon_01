# Study Signal — Midnight product page

2026-11-08. English, local static software product page. Primary action: **View the app**, which opens the actual desktop screenshot. No external hosting was requested or performed.

## Design and active skill

Only the project installation of **Taste Skill 2.5.0** remains active. The additional `frontend-design` and `web-design-guidelines` project directories were removed at the user's request. Global skill installations were untouched.

The user supplied the reference and palette: Midnight Black `#080b0d`, Pure White `#ffffff`, Lime Green `#c7ff3e`. This overrides the previous palette and random hero selection. Centred Instrument Serif regular/italic headings, lime emphasis, static lime light, Outfit body text, and pill actions follow that reference. Taste's system and hover/press motion layer remain. No WebGL, scrolling effects, automatic tabs, tilted panels, invented metrics, customer logos, prices or testimonials were added. The existing Study Signal working name remains; no new brand or trademark availability claim was made.

The hero is one viewport, the product section one desktop viewport (two on tablet/mobile), and the closing footer one viewport. At 1024×768, content sizing expands the product section slightly to keep its contents visible. The reference's fake business statistics were replaced with real default reminder settings: 8 seconds visual and 20 seconds spoken, verified in the app's focus engine. These are configuration defaults, not accuracy measurements.

## Actual product asset

`product/assets/screenshots/study-signal-desktop.png` is an **unedited native Electron window capture**, 880×1602, taken through CUA on 2026-11-08. Its SHA-256 is `48e9f5af87aa774d7dfe61b197c877e72b8df9a8a1b07adb65868c88c65bb1b8`. The native Korean labels, timer and unavailable tracking status are preserved. It contains no face video or unrelated desktop content. The hero crop is CSS only; the product section and dialog show the complete same image. No generated UI or replacement screenshot values were used.

This is the user's own app asset, with no external photo stand-ins or pending client asset slots. Outfit and Instrument Serif regular/italic fonts and OFL licences are local. The website does not access camera/microphone data or call an AI service. English setup notes distinguish the website from the development app and explain opt-in audio/screen transmission. Device tracking accuracy and actual voice/model behavior were not validated by website tests.

## Browser checks

Taste's scripts ran sequentially using Node 24 and system Chrome. Final screenshots were inspected at 1440×900, 1024×768, 820×1180, 768×1024 and 390×844.

- **43 interaction checks passed, 0 failed:** screenshot loading/dimensions, all five opener controls, closing and focus restoration, backdrop dismissal, section containment and no horizontal overflow at five sizes, viewport-filling hero, fitting dialog, mobile navigation/inert content/Escape, shared original image and local resources.
- Layout check: **no horizontal overflow at any of the five sizes**. Ten `edge-left` findings remain: two footer second-column starts use an intentional 48px column gap; eight tablet feature headings/paragraphs belong to a three-column nested grid rather than the checker's global 12-column line list. Images confirm aligned nested columns and no clipping. These are documented grid exceptions, not missing content.
- Performance, one run at each of 1440 and 390: **0 FAIL / 6 WARN**, approximately 424 KiB transferred, CLS 0, broken requests 0, long tasks 0, WebGL contexts 0. Warnings: local fonts total 247 KiB, the tiny repeated logo's eager/lazy attribution, and the original screenshot being larger than its display width. The original is retained for native-resolution enlargement. These are local headless measurements, not real-network promises.
- Consistency: **13 FAIL / 14 WARN** at 1440/390; first-screen stress checks at 1280/1152/1024/896/768 returned **0 FAIL / 0 WARN**. The checker was not edited and an all-style-checks pass is not claimed.

Remaining consistency FAILs are recorded by rule:

1. `one-heading` (2): the checker counts the hero's `8s` definition-list value as a neighbouring section heading while scrolling. It is factual hero content, not another section; actual sections do not overlap.
2. `container-edges` (10): the centred hero headline, lead, factual values and contained 300px mobile screenshot follow the user's centred reference. They are deliberately not aligned to the left text edge; actual outer margins and overflow were independently checked.
3. `split-pair` (1): the desktop product uses a five-column text block and a six-column image block with an intentional empty column. This provides space around the tall native app capture rather than forcing adjacent text/image edges.

WARNs are preserved in the raw report: visual-area heuristic for the cropped hero, action-style feature heading, Product navigation label, pseudo-element chevron causing label-centre measurements, secondary-button fill contrast, unused DM Mono fallback token, mobile nav icon's inner padding, smaller mobile body text and different gaps around the tall screenshot. Button text and general text contrast checks pass. The actual screenshot remains available at original resolution for reading the native UI.

[Desktop](qa/product-midnight-desktop.png) · [Mobile](qa/product-midnight-mobile.png) · [Tablet](qa/product-midnight-820.png) · [43 interaction checks](qa/product-midnight-interactions.png) · [Layout](qa/product-midnight-layout.json) · [Performance](qa/product-midnight-performance.json) · [Consistency](qa/product-midnight-consistency.txt)
