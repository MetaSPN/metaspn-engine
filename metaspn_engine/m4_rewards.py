"""Reference M4 attention/pool/staker deterministic reward pipeline for Season 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .core import Emission, Signal
from .pipeline import Pipeline, StepResult


@dataclass(frozen=True)
class StakerPosition:
    """Single staker position within a game reward pool."""

    staker_id: str
    stake_weight: float
    conviction_days: int = 0


@dataclass(frozen=True)
class GameRewardInput:
    """Per-game input used to compute reward attention and allocations."""

    game_id: str
    attention_weight: float
    stakers: tuple[StakerPosition, ...]


@dataclass(frozen=True)
class M4RewardSignal:
    """Season-level reward input payload for deterministic pipeline execution."""

    season_id: str
    total_reward_pool: float
    games: tuple[GameRewardInput, ...]


@dataclass(frozen=True)
class M4RewardConfig:
    """Configurable controls for reward experiments."""

    enable_early_conviction_multiplier: bool = False
    early_conviction_multiplier: float = 1.25
    early_conviction_days_threshold: int = 30


@dataclass
class M4RewardState:
    """State threaded through attention -> pool -> staker allocation stages."""

    seasons_processed: int = 0
    latest_season_id: str = ""
    latest_attention_share_by_game: dict[str, float] = field(default_factory=dict)
    latest_game_pool_by_game: dict[str, float] = field(default_factory=dict)
    latest_staker_rewards_by_game: dict[str, dict[str, float]] = field(default_factory=dict)
    total_distributed: float = 0.0


def _attention_share_stage(signal: Signal[M4RewardSignal], state: M4RewardState) -> StepResult:
    games_sorted = sorted(signal.payload.games, key=lambda item: item.game_id)
    total_attention = sum(max(item.attention_weight, 0.0) for item in games_sorted)

    if not games_sorted:
        shares: dict[str, float] = {}
    elif total_attention > 0:
        shares = {
            item.game_id: round(max(item.attention_weight, 0.0) / total_attention, 6)
            for item in games_sorted
        }
    else:
        equal_share = round(1.0 / len(games_sorted), 6)
        shares = {item.game_id: equal_share for item in games_sorted}

    emission = Emission(
        emission_id=f"{signal.signal_id}:attention",
        emission_type="m4.rewards.attention.computed",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "season_id": signal.payload.season_id,
            "attention_share_by_game": shares,
            "total_attention": round(total_attention, 6),
        },
        metadata={
            "trace": {
                "stage": "attention_share",
                "caused_by": signal.signal_id,
                "formula": "game_attention / sum(game_attention)",
            }
        },
    )

    def updater(_: M4RewardState) -> M4RewardState:
        return M4RewardState(
            seasons_processed=state.seasons_processed,
            latest_season_id=signal.payload.season_id,
            latest_attention_share_by_game=shares,
            latest_game_pool_by_game=dict(state.latest_game_pool_by_game),
            latest_staker_rewards_by_game=dict(state.latest_staker_rewards_by_game),
            total_distributed=state.total_distributed,
        )

    return [emission], updater


def _game_pool_stage(signal: Signal[M4RewardSignal], state: M4RewardState) -> StepResult:
    pool_by_game = {
        game_id: round(signal.payload.total_reward_pool * share, 6)
        for game_id, share in sorted(state.latest_attention_share_by_game.items())
    }

    emission = Emission(
        emission_id=f"{signal.signal_id}:pool",
        emission_type="m4.rewards.pool.allocated",
        caused_by=signal.signal_id,
        timestamp=signal.timestamp,
        payload={
            "season_id": signal.payload.season_id,
            "total_reward_pool": round(signal.payload.total_reward_pool, 6),
            "reward_pool_by_game": pool_by_game,
        },
        metadata={
            "trace": {
                "stage": "game_reward_pool_allocation",
                "caused_by": signal.signal_id,
                "formula": "total_reward_pool * attention_share",
            }
        },
    )

    def updater(_: M4RewardState) -> M4RewardState:
        return M4RewardState(
            seasons_processed=state.seasons_processed,
            latest_season_id=state.latest_season_id,
            latest_attention_share_by_game=dict(state.latest_attention_share_by_game),
            latest_game_pool_by_game=pool_by_game,
            latest_staker_rewards_by_game=dict(state.latest_staker_rewards_by_game),
            total_distributed=state.total_distributed,
        )

    return [emission], updater


def _make_staker_allocation_stage(config: M4RewardConfig):
    def _staker_allocation_stage(signal: Signal[M4RewardSignal], state: M4RewardState) -> StepResult:
        reward_by_game: dict[str, dict[str, float]] = {}

        for game in sorted(signal.payload.games, key=lambda item: item.game_id):
            game_pool = state.latest_game_pool_by_game.get(game.game_id, 0.0)
            stakers_sorted = sorted(game.stakers, key=lambda item: item.staker_id)

            effective_weights: list[tuple[str, float]] = []
            for staker in stakers_sorted:
                multiplier = 1.0
                if (
                    config.enable_early_conviction_multiplier
                    and staker.conviction_days >= config.early_conviction_days_threshold
                ):
                    multiplier = config.early_conviction_multiplier
                effective_weights.append((staker.staker_id, max(staker.stake_weight, 0.0) * multiplier))

            total_effective_weight = sum(weight for _, weight in effective_weights)
            if total_effective_weight <= 0:
                allocations = {staker_id: 0.0 for staker_id, _ in effective_weights}
            else:
                allocations = {
                    staker_id: round(game_pool * (weight / total_effective_weight), 6)
                    for staker_id, weight in effective_weights
                }

            reward_by_game[game.game_id] = allocations

        total_distributed = round(
            sum(sum(staker_alloc.values()) for staker_alloc in reward_by_game.values()),
            6,
        )
        emission = Emission(
            emission_id=f"{signal.signal_id}:staker",
            emission_type="m4.rewards.staker.allocated",
            caused_by=signal.signal_id,
            timestamp=signal.timestamp,
            payload={
                "season_id": signal.payload.season_id,
                "staker_reward_by_game": reward_by_game,
                "total_distributed": total_distributed,
                "config": {
                    "enable_early_conviction_multiplier": config.enable_early_conviction_multiplier,
                    "early_conviction_multiplier": config.early_conviction_multiplier,
                    "early_conviction_days_threshold": config.early_conviction_days_threshold,
                },
            },
            metadata={
                "trace": {
                    "stage": "staker_share_allocation",
                    "caused_by": signal.signal_id,
                    "formula": "game_pool * (effective_stake / sum(effective_stake))",
                }
            },
        )

        def updater(_: M4RewardState) -> M4RewardState:
            return M4RewardState(
                seasons_processed=state.seasons_processed + 1,
                latest_season_id=state.latest_season_id,
                latest_attention_share_by_game=dict(state.latest_attention_share_by_game),
                latest_game_pool_by_game=dict(state.latest_game_pool_by_game),
                latest_staker_rewards_by_game=reward_by_game,
                total_distributed=state.total_distributed + total_distributed,
            )

        return [emission], updater

    return _staker_allocation_stage


def build_m4_reward_pipeline(config: M4RewardConfig | None = None) -> Pipeline:
    """Create deterministic M4 attention -> pool -> staker allocation composition."""

    effective_config = config or M4RewardConfig()
    return Pipeline(
        steps=[
            _attention_share_stage,
            _game_pool_stage,
            _make_staker_allocation_stage(effective_config),
        ],
        name="m4_attention_pool_staker",
    )


def make_m4_signal(
    *,
    signal_id: str,
    timestamp: datetime,
    source: str,
    season_id: str,
    total_reward_pool: float,
    games: tuple[GameRewardInput, ...],
) -> Signal[M4RewardSignal]:
    """Construct stable-ID M4 reward signals for reference orchestration."""

    return Signal(
        signal_id=signal_id,
        timestamp=timestamp,
        source=source,
        payload=M4RewardSignal(
            season_id=season_id,
            total_reward_pool=total_reward_pool,
            games=games,
        ),
    )


# Backward-compatible aliases retained for downstream imports.
GameAttentionInput = GameRewardInput
StakerStakeInput = StakerPosition
Season1RewardSignal = M4RewardSignal
RewardPipelineConfig = M4RewardConfig
