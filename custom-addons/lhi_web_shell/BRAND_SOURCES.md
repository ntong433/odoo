# LHI brand palette sources

Extracted from the live `https://lhinigeria.org/` authored CSS and original logo
asset on 2026-07-18. Values are centralized in `static/src/scss/tokens.scss`.

| Token/source element | HEX | RGB |
|---|---:|---:|
| Original logo red | `#ED3237` | `237, 50, 55` |
| Original logo orange | `#F58634` | `245, 134, 52` |
| Header/submenu navigation background | `#343877` | `52, 56, 119` |
| Active navigation underline / filled CTA | `#EFC940` | `239, 201, 64` |
| Filled CTA hover | `#E9BA13` | `233, 186, 19` |
| Deep-red site button | `#931704` | `147, 23, 4` |
| Red navigation/link accent and hover | `#DA0102` | `218, 1, 2` |
| Main body and heading text | `#000000` | `0, 0, 0` |
| Secondary text | `#515266` | `81, 82, 102` |
| Main surface | `#FFFFFF` | `255, 255, 255` |
| Muted section surface | `#F9F7F6` | `249, 247, 246` |
| Neutral border found in live theme CSS | `#D4DAD7` | `212, 218, 215` |
| Footer background | `#20212B` | `32, 33, 43` |
| Footer muted text/links | `#97979E` | `151, 151, 158` |

Status colors are intentionally not derived from the brand palette: Odoo's
success, warning, danger, and informational semantics remain distinct.

`#931704` is the semantic primary because white text has a 8.88:1 contrast
ratio on it. The brighter logo red remains available as `$lhi-red-600` but is
not used behind small white button text (4.11:1).
