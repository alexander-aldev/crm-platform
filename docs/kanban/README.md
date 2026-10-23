# Másquetú: kanban board design reference

For Alex. This is the board shown on masquetu.ai. The deal data is fictional. Open `kanban-board.html` in a browser to inspect the live CSS. All values below are also defined there as CSS variables.

## Files

| File | What it is |
|---|---|
| `kanban-board.html` | Source of truth: desktop board, phone board and a single card, in plain HTML/CSS |
| `kanban-board-desktop@2x.png` | Desktop board, 4 columns (2× resolution) |
| `kanban-board-mobile@2x.png` | Phone board, 2 columns visible (2× resolution) |
| `deal-card@2x.png` | One deal card on the column background |


## Fonts

- **Manrope** (Google Fonts CDN) for all UI text: variable, 400 to 800
- **JetBrains Mono** (Google Fonts CDN) 500 for money values and counts

## Colours

| Token | Hex | Used for |
|---|---|---|
| ink | `#121212` | Card titles, values, board title |
| ink-2 | `#3A3835` | Column headers |
| muted | `#55524E` | Company name, next step (normal), board meta |
| overdue | `#B4500F` | Next step due today or overdue (readable on white) |
| accent | `#FF8A2B` | Brand accent for buttons and highlights. Not for text on white (too little contrast) |
| board-bg | `#FFFFFF` | Board |
| column-bg | `#F3F3F2` | Column |
| card-bg | `#FFFFFF` | Card |
| line | `#E4E4E2` | Board and card borders (card hover: `#A8A39D`) |

## Board

- Board: padding 20px, radius 14px, 1px border
- Header: title Manrope 700 17px; meta JetBrains Mono 500 13px, muted
- Columns: 4 equal columns, 12px gap, min width 200px, radius 10px, padding 12px, 10px between cards
- Column header: stage name Manrope 700 13px (ink-2); stage total JetBrains Mono 500 13px, right-aligned

## Deal card (top to bottom)

1. **Title**: Manrope 600 14px, ink
2. **Company**: Manrope 400 13px, muted
3. **Footer row**: value on the left (JetBrains Mono 500 12px, ink), next step on the right (Manrope 12px, muted, or overdue colour when due today or late, e.g. "Call · Today", "Overdue 2d")

Card: white, 1px `#E4E4E2` border, radius 8px, padding 12px, 6px between lines. Drag cursor on hover.

## Phone (under 768px)

- Board padding 12px
- Two columns fill the width; the rest scroll sideways with snap (`scroll-snap-type: x mandatory`)
- Meta text shortens to "€48,300 · 14 deals"

## Brand context

Site colours: near-black `#0E0D0C` and `#0B0A09` for dark sections, white content sections, flame orange `#FF8A2B` as the single accent. Copy style: plain, direct statements, no wordplay.
