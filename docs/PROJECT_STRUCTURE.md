# Project Structure

OpenRoyale is split by purpose so runtime code, experiments, and generated files stay easy to navigate.

```text
src/
  main.ts            Browser entry point for the playable app.
  viewer.ts          Standalone viewer entry.
  style.css          App styling.
  engine/            Core simulation, card data, entities, vectors, and Pixi renderer.

public/
  assets/sc/         Runtime sprite data and textures served by Vite.

tests/
  simulation/        Headless TypeScript simulation checks.
  browser/           Playwright/Puppeteer browser smoke and screenshot scripts.
  assets/            Asset inspection scripts.

tools/               One-off asset generation, analysis, and patching utilities.

artifacts/
  screenshots/       Local screenshot output and visual debugging captures.
```

## Current Refactor Boundaries

- `src/engine/Game.ts` owns simulation state, entity spawning, projectiles, effects, collision constraints, and update order.
- `src/engine/Entity.ts` owns per-unit targeting, movement, attacks, and ability behavior.
- `src/engine/SCRenderer.ts` owns Supercell-style JSON/texture loading and Pixi drawing.
- `src/main.ts` still owns several browser concerns at once: app boot, loading UI, card picker UI, arena DOM, render loop, and input handling. This is the next high-value file to split.

## Recommended Next Split

When changing UI behavior, prefer extracting from `src/main.ts` in this order:

1. `src/app/assets.ts` for preload character IDs and loading overlay.
2. `src/app/cardPanel.ts` for card list rendering and card/team selection.
3. `src/app/arenaView.ts` for DOM arena elements, ability buttons, and entity/projectile/effect rendering.
4. `src/app/bootstrap.ts` for wiring `Game`, `SCRenderer`, input handlers, and the animation loop.

Keep `src/engine` free of browser DOM dependencies except the renderer.
