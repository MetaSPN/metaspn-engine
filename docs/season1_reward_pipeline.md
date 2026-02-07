# Season 1 Reward Pipeline Reference

This document describes the deterministic M4 reward reference pipeline in `metaspn_engine.m4_rewards`.

## Stages

1. `attention_share`
- Computes normalized game attention share.
- Emission: `m4.rewards.attention.computed`.

2. `game_reward_pool_allocation`
- Allocates season pool to each game from attention share.
- Emission: `m4.rewards.pool.allocated`.

3. `staker_share_allocation`
- Allocates each game pool to stakers by effective stake share.
- Emission: `m4.rewards.staker.allocated`.

All emissions are deterministic when `signal_id` and `timestamp` are stable and include trace metadata in `emission.metadata["trace"]`.

## Early Conviction Multiplier

`M4RewardConfig` supports an optional multiplier experiment:

- `enable_early_conviction_multiplier`: toggle feature on/off.
- `early_conviction_multiplier`: weight boost applied when threshold is met.
- `early_conviction_days_threshold`: minimum conviction days required.

When disabled, allocations use raw `stake_weight` only.

## Worked Example

Input season:

- `total_reward_pool=1000`
- games:
  - `g1 attention=60` with stakers `alice=70 (10 days)`, `bob=30 (45 days)`
  - `g2 attention=40` with stakers `alice=20 (50 days)`, `carol=80 (5 days)`

Computed with multiplier disabled:

- attention share: `g1=0.6`, `g2=0.4`
- game pools: `g1=600`, `g2=400`
- staker allocation:
  - `g1`: `alice=420`, `bob=180`
  - `g2`: `alice=80`, `carol=320`

Computed with multiplier enabled (`1.25`, threshold `>=30` days):

- `g1` effective weights: `alice=70`, `bob=37.5`
- `g2` effective weights: `alice=25`, `carol=80`
- staker allocation:
  - `g1`: `alice=390.697674`, `bob=209.302326`
  - `g2`: `alice=95.238095`, `carol=304.761905`
