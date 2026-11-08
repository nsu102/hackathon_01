# Web Interface Guidelines review

Source read for this review: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md

## product/index.html

✓ Applicable semantic, navigation, image, label, and live-response checks pass. Main actions are links/buttons, the main content has a skip link, brand text is marked against translation, and the sensor-free example is disclosed.

## product/product.css

✓ Focus, reading contrast, touch sizing, responsive containment, and reduced-motion checks pass within the browser-tested sizes. Dark surfaces have a separate light focus-ring colour. Mobile explanations follow the selected paragraph without covering it. Sections use natural height by design.

## product/product.mjs

✓ Keyboard controls and generated labels remain English. Calibration target selection restores focus. Menu state changes its accessible name and makes background content inert. Demo tab state is reflected in the URL; opening a help deep link is verified.

## product/setup.html

✓ Setup, limits, transmission, and storage are explained in English. Code identifiers are protected against automatic translation. Prototype language and the lack of validated English speech support are stated.

## Scope and intentional choices

Sentence-case headings follow frontend-design's copy direction. Literal math and small demo counters use fixed English notation. No forms, currency, calendar dates, destructive actions, large lists, or server hydration apply. This review is not an accessibility certification or a physical-device test.
