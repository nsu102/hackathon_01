# Study Signal product page

English product introduction in Midnight Black, Pure White, and Lime Green. This revision uses **Taste Skill only**. The two other project design skills were removed at the user's request.

## Preview

Open `Start preview.command`, then visit <http://127.0.0.1:8088>. Or run this command from this folder:

```sh
python3 -m http.server 8088 --bind 127.0.0.1
```

No API key or package install is needed for this website.

## Actual app screenshot

`assets/screenshots/study-signal-desktop.png` is an unedited native capture of the developing Electron app, taken through the CUA screenshot API on 2026-11-08. The image is 880 × 1602 pixels. It contains the app window, not a generated UI, camera video, or unrelated desktop content. Its actual Korean labels and tracking status are preserved.

The hero shows a CSS crop. Choose **View the app** or select either image to view the complete capture. The source file is unchanged; capture metadata and its SHA-256 digest are in `assets/screenshots/provenance.json`.

The 8s/20s facts are the app's default reminder settings, not measured accuracy or customer metrics. Physical gaze accuracy and device integration remain development work. The website itself does not access camera/microphone data or call an AI service.

## Design

- Active project skill: `.agents/skills/design-taste-frontend` (Taste Skill 2.5.0).
- User-supplied palette: #080b0d, #ffffff, #c7ff3e.
- Local Instrument Serif regular/italic headings; Outfit body/UI text. OFL licences are included.
- Static lime lighting, quiet button hover/press, full screenshot dialog, English setup/privacy notes.
- No invented ratings, testimonials, users, performance statistics, pricing, or accounts.

`index.html`, `product.css`, and `product.mjs` make up the introduction. `setup.html` explains the prototype and data handling. `study-signal.zip` contains desktop source. This page has not been published to external hosting.
