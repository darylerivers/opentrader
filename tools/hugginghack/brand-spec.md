# HuggingHack brand spec

> Collected: 2026-07-23
> Reference sources: official Hugging Face brand, Models catalog, and model-detail pages
> Completeness: complete for this local application

## Core assets

### Logo

- Primary: `frontend/public/hugginghack-mark.svg`
- Dark-background version: `frontend/public/hugginghack-mark-dark.svg`
- The terminal-face mark is an original HuggingHack asset. Do not present it as the official Hugging Face logo.
- Keep the mark square, do not stretch it, and pair it with the `HuggingHack` wordmark.

### Digital-product UI references

Ten official candidates were reviewed: `/`, `/models`, `/datasets`, `/spaces`, `/brand`, a model detail page, its Files tab, the Hub API docs, download docs, and gated-model docs.

- Selected reference A (9/10): `https://huggingface.co/models` — strongest catalog hierarchy and filter behavior.
- Selected reference B (9/10): `https://huggingface.co/google/gemma-3-4b-it` — strongest repository metadata and action hierarchy.
- Other official pages were used only to cross-check navigation, brand tokens, empty states, and documentation language. No third-party screenshots or copied interface assets are bundled.

## Palette

- Primary amber: `#FFD21E` — official HF reference, used sparingly for the logo and active state.
- Warm action: `#FF9D00` — official HF reference, used for download emphasis.
- Ink: `#111827`
- Muted ink: `#6B7280` — official HF reference.
- Canvas: `#FFFFFF`
- Subtle canvas: `#F7F7F8`
- Border: `#E5E7EB`
- Success: `#15803D`
- Danger: `#B42318`

## Typography

- Display/wordmark: `Bricolage Grotesque`, with a sans fallback.
- Body: `IBM Plex Sans`, with a sans fallback.
- Data and paths: `IBM Plex Mono`, with a monospace fallback.

## Layout signature

- Compact 64px header, flat 1px separators, narrow left filter rail, and a responsive grid of metadata-driven model cards.
- Rounded pills are reserved for real model metadata, not decoration.
- Model-card visuals encode real task and parameter metadata; they do not imply generated previews or benchmark results.
- Download progress is the 120% detail: precise byte counts, speed, target path, cancellation, and persistent recovery state.

## Prohibited

- Do not use the official Hugging Face wordmark or claim affiliation.
- No purple AI gradients, glass cards, fake model statistics, decorative charts, or invented endorsements.
- Do not execute downloaded code or deserialize model artifacts.

## Tone

- Familiar, practical, local-first, technically honest, storage-aware.
