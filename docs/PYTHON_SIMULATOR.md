# Python Simulator

`openroyale_sim` is a headless Python port of the current TypeScript battle
engine. It is intended for reinforcement learning, scripted evaluations, and
batch simulation without Pixi.js or browser dependencies.

## Low-Level Game API

```python
from openroyale_sim import Game, Vector2

game = Game(seed=1)
game.start()
knight = game.add_entity_by_id("knight", "blue", Vector2(9, 25))

for _ in range(60):
    game.update(1 / 60)
```

`Game` exposes entities, projectiles, effects, card spawning, targeting,
movement, bridge pathing, river constraints, projectile hits, splash damage,
collision resolution, and tower activation logic.

## RL Environment API

```python
from openroyale_sim import OpenRoyaleEnv

env = OpenRoyaleEnv(frame_skip=4, max_time=180)
obs, info = env.reset(seed=1)

obs, reward, terminated, truncated, info = env.step({
    "type": "deploy",
    "card": "knight",
    "team": "blue",
    "x": 9,
    "y": 24,
})
```

Supported action dictionaries:

- `{"type": "noop"}`
- `{"type": "deploy", "card": card_id, "team": "blue" | "red", "x": x, "y": y}`
- `{"type": "ability", "entity_id": id}`

`step()` also accepts a list of action dictionaries, so both players can act in
the same environment tick.

Deploy actions are validated by match rules:

- Each player starts with 5 elixir.
- Elixir is capped at 10.
- Elixir regenerates at 1 point every 2.8 seconds.
- A deploy action spends the card's `elixir_cost`.
- Deploying with insufficient elixir is rejected and reported in
  `info["invalid_actions"]`.
- Base deploy zones are the owner's side of the river: blue can deploy at
  `y >= 17`, red can deploy at `y <= 15`.
- Destroying an enemy princess tower unlocks the matching lane's advanced zone:
  a 9 x 5 tile rectangle on the enemy side of the river.
  - Blue left/right advanced zones: `x=0..9` or `x=9..18`, `y=10..15`.
  - Red left/right advanced zones: `x=0..9` or `x=9..18`, `y=17..22`.

Observations are plain dictionaries with:

- `time`
- `elixir`: current elixir for both players
- `entities`: id, card, team, type, position, hp, target, movement/attack state,
  ability cooldown, current effect, and elixir cost
- `projectiles`: id, source, team, position, target, and damage

The default reward is tower damage differential:

```text
damage dealt to red towers - damage dealt to blue towers
```

The episode terminates when either king tower is destroyed and truncates at
`max_time`. `info["winner"]` is `"blue"` or `"red"` when a king tower is
destroyed.

## Current Scope

The Python card table mirrors the cards currently present in
`src/engine/Cards.ts`. Some TypeScript simulation tests reference cards that are
not defined in that file, such as `evo_skeletons` and `golden_knight`; those are
not invented in the Python port. The ability hooks are present, so those cards
can be added once authoritative stats exist.
