from openroyale_sim import CARDS, Game, OpenRoyaleEnv, Vector2


def test_game_starts_with_six_towers():
    game = Game(seed=1)
    game.start()
    assert len(game.entities) == 6
    assert sum(1 for entity in game.entities if entity.team == "blue") == 3
    assert sum(1 for entity in game.entities if entity.team == "red") == 3


def test_knight_moves_in_headless_simulation():
    game = Game(seed=1)
    game.start()
    knight = game.add_entity_by_id("knight", "blue", Vector2(9, 25))
    assert knight is not None
    start_y = knight.pos.y

    for _ in range(120):
        game.update(1 / 60)

    assert knight.pos.y < start_y


def test_swarm_card_spawns_multiple_entities():
    game = Game(seed=1)
    game.add_entity(CARDS["skeletons"], "blue", Vector2(9, 20))
    assert len(game.entities) == 3
    assert len({entity.clone_group_id for entity in game.entities}) == 1


def test_env_step_deploys_and_returns_gymnasium_tuple():
    env = OpenRoyaleEnv(frame_skip=4)
    obs, info = env.reset(seed=1)
    assert len(obs["entities"]) == 6
    assert info["seed"] == 1
    assert obs["elixir"] == {"blue": 5.0, "red": 5.0}

    obs, reward, terminated, truncated, info = env.step({"type": "deploy", "card": "knight", "team": "blue", "x": 9, "y": 24})
    assert any(entity["card"] == "knight" for entity in obs["entities"])
    assert isinstance(reward, float)
    assert terminated is False
    assert truncated is False
    assert info["invalid_actions"] == []
    assert info["elixir"]["blue"] < 3


def test_elixir_rejects_expensive_card_and_regenerates():
    env = OpenRoyaleEnv(frame_skip=60)
    env.reset(seed=1)

    _, _, _, _, info = env.step({"type": "deploy", "card": "pekka", "team": "blue", "x": 9, "y": 24})
    assert info["invalid_actions"][0]["reason"] == "not enough elixir"
    assert info["elixir"]["blue"] > 5


def test_deploy_position_must_be_legal():
    env = OpenRoyaleEnv()
    env.reset(seed=1)

    obs, _, _, _, info = env.step({"type": "deploy", "card": "knight", "team": "blue", "x": 9, "y": 12})
    assert info["invalid_actions"][0]["reason"] == "deploy position is not legal"
    assert not any(entity["card"] == "knight" for entity in obs["entities"])


def test_destroyed_princess_tower_unlocks_matching_advanced_zone():
    env = OpenRoyaleEnv()
    env.reset(seed=1)
    red_left_tower = next(entity for entity in env.game.entities if entity.team == "red" and entity.stats.id == "princess_tower" and entity.pos.x < 9)
    red_left_tower.take_damage(99999)
    env.game.update(1 / 60)

    assert env.is_legal_deploy_position("blue", 3, 12)
    assert not env.is_legal_deploy_position("blue", 15, 12)

    obs, _, _, _, info = env.step({"type": "deploy", "card": "knight", "team": "blue", "x": 3, "y": 12})
    assert info["invalid_actions"] == []
    assert any(entity["card"] == "knight" and entity["team"] == "blue" for entity in obs["entities"])


def test_destroying_enemy_king_tower_ends_game_with_winner():
    env = OpenRoyaleEnv()
    env.reset(seed=1)
    red_king = next(entity for entity in env.game.entities if entity.team == "red" and entity.stats.id == "king_tower")
    red_king.take_damage(99999)
    env.game.update(1 / 60)

    _, _, terminated, truncated, info = env.step({"type": "noop"})
    assert terminated is True
    assert truncated is False
    assert info["winner"] == "blue"
