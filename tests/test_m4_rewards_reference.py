"""Golden tests for deterministic Season 1 reward pipeline outputs."""

from datetime import datetime

from metaspn_engine import Engine
from metaspn_engine.m4_rewards import (
    GameRewardInput,
    M4RewardConfig,
    M4RewardState,
    StakerPosition,
    build_m4_reward_pipeline,
    make_m4_signal,
)


def _season_fixture_signal(signal_id: str = "sig_m4_1"):
    return make_m4_signal(
        signal_id=signal_id,
        timestamp=datetime(2026, 2, 7, 12, 0, 0),
        source="ops.m4.worker",
        season_id="season_1",
        total_reward_pool=1000.0,
        games=(
            GameRewardInput(
                game_id="g1",
                attention_weight=60.0,
                stakers=(
                    StakerPosition(staker_id="alice", stake_weight=70.0, conviction_days=10),
                    StakerPosition(staker_id="bob", stake_weight=30.0, conviction_days=45),
                ),
            ),
            GameRewardInput(
                game_id="g2",
                attention_weight=40.0,
                stakers=(
                    StakerPosition(staker_id="alice", stake_weight=20.0, conviction_days=50),
                    StakerPosition(staker_id="carol", stake_weight=80.0, conviction_days=5),
                ),
            ),
        ),
    )


def test_m4_reward_reference_flow_matches_golden_outputs_with_trace_metadata() -> None:
    engine = Engine(
        pipeline=build_m4_reward_pipeline(),
        initial_state=M4RewardState(),
    )
    signal = _season_fixture_signal()

    emissions = engine.process(signal)

    assert [item.emission_id for item in emissions] == [
        "sig_m4_1:attention",
        "sig_m4_1:pool",
        "sig_m4_1:staker",
    ]
    assert [item.emission_type for item in emissions] == [
        "m4.rewards.attention.computed",
        "m4.rewards.pool.allocated",
        "m4.rewards.staker.allocated",
    ]
    assert [item.caused_by for item in emissions] == ["sig_m4_1", "sig_m4_1", "sig_m4_1"]

    assert emissions[0].payload["attention_share_by_game"] == {"g1": 0.6, "g2": 0.4}
    assert emissions[1].payload["reward_pool_by_game"] == {"g1": 600.0, "g2": 400.0}
    assert emissions[2].payload["staker_reward_by_game"] == {
        "g1": {"alice": 420.0, "bob": 180.0},
        "g2": {"alice": 80.0, "carol": 320.0},
    }
    for emission in emissions:
        assert emission.metadata["trace"]["caused_by"] == "sig_m4_1"
        assert "stage" in emission.metadata["trace"]


def test_m4_reward_multiplier_toggle_and_reruns_are_deterministic() -> None:
    signal = _season_fixture_signal("sig_m4_2")

    base_engine = Engine(
        pipeline=build_m4_reward_pipeline(),
        initial_state=M4RewardState(),
    )
    base_emissions = base_engine.process(signal)

    boosted_engine_a = Engine(
        pipeline=build_m4_reward_pipeline(
            M4RewardConfig(
                enable_early_conviction_multiplier=True,
                early_conviction_multiplier=1.25,
                early_conviction_days_threshold=30,
            )
        ),
        initial_state=M4RewardState(),
    )
    boosted_engine_b = Engine(
        pipeline=build_m4_reward_pipeline(
            M4RewardConfig(
                enable_early_conviction_multiplier=True,
                early_conviction_multiplier=1.25,
                early_conviction_days_threshold=30,
            )
        ),
        initial_state=M4RewardState(),
    )

    boosted_a = boosted_engine_a.process(signal)
    boosted_b = boosted_engine_b.process(signal)

    assert base_emissions[2].payload["staker_reward_by_game"]["g1"]["alice"] == 420.0
    assert base_emissions[2].payload["staker_reward_by_game"]["g1"]["bob"] == 180.0

    assert boosted_a[2].payload["staker_reward_by_game"] == {
        "g1": {"alice": 390.697674, "bob": 209.302326},
        "g2": {"alice": 95.238095, "carol": 304.761905},
    }
    assert [item.to_dict() for item in boosted_a] == [item.to_dict() for item in boosted_b]
