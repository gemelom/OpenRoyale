# Clash Royale Assets Guidance

This document explains the asset format and how to replicate the interactive animation viewer for the Clash Royale engine.

## File Format Overview

The game assets are extracted from Supercell's `.sc` files into a standard JSON format, accompanied by one or more texture atlases.

For each character or building (e.g. `chr_princess`, `building_tower`), you will find:
1. `[name].json`
2. `[name]_tex.png` or `[name]_tex_0.png`

### JSON Structure
The JSON contains several key objects:
- `textures`: An array of texture file names associated with this asset.
- `matrices`: 2D transformation matrices `{a, b, c, d, tx, ty}`. Note: `tx` and `ty` are usually pre-divided by 20 during extraction.
- `colors`: Color transform objects `{r_mul, g_mul, b_mul, a_mul, r_add, g_add, b_add}`. An `a_mul` of `< 0.01` means the element is hidden.
- `shapes`: The building blocks. Each shape is an array of sub-shapes. Sub-shapes have `points` with `x, y` (spatial) and `u, v` (texture mapping).
- `movieclips`: Complex animations or grouped elements. They contain:
  - `binds`: Maps a local index to a child `shapeId` or `movieclipId`.
  - `frames`: An array of frames. Each frame has `elements` that specify which `bind` index to render, and which `matrix` or `color` to apply.
- `exports`: A map linking human-readable animation names (like `princess_tower_red_idle1_5`) to a root `movieclip` ID.

## Replicating the Animation Page

To render these assets using PIXI.js, follow this recursive approach:

1. **Initialize PIXI**: Set up a PIXI Application or Geometry mesh renderer.
2. **Load Assets**: Load the JSON and the corresponding `.png` textures into PIXI.
3. **Parse Global Transform**: Set up your parent container or global matrix.
4. **Recursive Rendering**:
   Create a function `renderMovieClip(exportId, parentContainer, globalMatrix, frameIdx)`:
   - Fetch the movieclip using `exportId` from `data.movieclips`.
   - Modulo the `frameIdx` by `mc.frames.length` to get the current frame.
   - Loop through `frame.elements`.
   - Apply the element's `matrix` to the `globalMatrix`.
   - Apply the element's `color` transform.
   - Look up the `bind.id`. If it's another movieclip, call `renderMovieClip` recursively. If it's a shape, render it.
5. **Shape Rendering**:
   - Extract the `points`.
   - Use `earcut` or another triangulator on the flat `[x, y]` array to generate indices.
   - Transform the `x, y` by the global matrix.
   - Apply `u, v` to the texture. If `is_normalized` is false, divide by the actual power-of-two texture dimensions.
   - Create a `PIXI.Mesh` and add it to the parent container.

### Handling Specific Towers

- **Princess Tower**: 
  Requires rendering the base tower (`StarTower_base_red` or `blue`) and then rendering the Princess (`princess_tower_red_idle1_...` from `chr_princess.json`) separately. Apply a `translate(0, -30)` to the Princess matrix to place her correctly on top of the tower base.
- **King Tower**: 
  The King is integrated into the tower's movieclip (`KingTower_red` or `blue`). 
  - For the **idle/asleep** state, use `frameIndex = 0`.
  - The activation animation plays from frames `1` to `96`.
  - For the **awake/attack** state, use `frameIndex = 97` and beyond.
