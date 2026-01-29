"""
Example: Podcast Listening Game

This shows how to build a domain-specific game on top of the MetaSPN Engine.
The podcast game tracks listening behavior and computes influence signals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

# Import from the engine
from . import Signal, Emission, Pipeline, Engine
from .protocols import GameSignature


# =============================================================================
# DOMAIN TYPES (Podcast-specific)
# =============================================================================

@dataclass(frozen=True)
class PodcastListen:
    """A podcast listening event."""
    episode_id: str
    podcast_id: str
    podcast_name: str
    episode_title: str
    duration_seconds: int
    listened_seconds: int
    completed: bool
    host_name: Optional[str] = None
    guest_names: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    
    @property
    def completion_rate(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return min(1.0, self.listened_seconds / self.duration_seconds)


@dataclass
class ListeningStats:
    """Aggregated listening statistics."""
    total_episodes: int = 0
    total_seconds: int = 0
    completed_count: int = 0
    by_podcast: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_topic: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def completion_rate(self) -> float:
        if self.total_episodes == 0:
            return 0.0
        return self.completed_count / self.total_episodes
    
    @property
    def average_duration(self) -> float:
        if self.total_episodes == 0:
            return 0.0
        return self.total_seconds / self.total_episodes


@dataclass
class PodcastState:
    """State for the podcast listening game."""
    # Listening history
    stats: ListeningStats = field(default_factory=ListeningStats)
    recent_episodes: List[str] = field(default_factory=list)
    
    # Influence tracking
    host_exposure: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    topic_exposure: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    # Trajectory
    listening_velocity: float = 0.0  # episodes per week
    topic_entropy: float = 0.0  # diversity of topics
    depth_score: float = 0.0  # completion * consistency
    
    # Time tracking
    last_listen_at: Optional[datetime] = None
    streak_days: int = 0


# =============================================================================
# PIPELINE STEPS (Pure functions)
# =============================================================================

def track_listening(signal: Signal[PodcastListen], state: PodcastState):
    """Track basic listening statistics."""
    payload = signal.payload
    
    # Update stats
    new_stats = ListeningStats(
        total_episodes=state.stats.total_episodes + 1,
        total_seconds=state.stats.total_seconds + payload.listened_seconds,
        completed_count=state.stats.completed_count + (1 if payload.completed else 0),
        by_podcast=dict(state.stats.by_podcast),
        by_topic=dict(state.stats.by_topic),
    )
    new_stats.by_podcast[payload.podcast_id] = (
        state.stats.by_podcast.get(payload.podcast_id, 0) + 1
    )
    for topic in payload.topics:
        new_stats.by_topic[topic] = state.stats.by_topic.get(topic, 0) + 1
    
    # Update recent episodes (keep last 100)
    recent = state.recent_episodes[-99:] + [payload.episode_id]
    
    def updater(s: PodcastState) -> PodcastState:
        return PodcastState(
            stats=new_stats,
            recent_episodes=recent,
            host_exposure=s.host_exposure,
            topic_exposure=s.topic_exposure,
            listening_velocity=s.listening_velocity,
            topic_entropy=s.topic_entropy,
            depth_score=s.depth_score,
            last_listen_at=signal.timestamp,
            streak_days=s.streak_days,
        )
    
    return [], updater


def compute_influence(signal: Signal[PodcastListen], state: PodcastState):
    """Compute influence signals from hosts and topics."""
    payload = signal.payload
    influence_weight = payload.completion_rate  # More completion = more influence
    
    # Update host exposure
    new_host_exposure = dict(state.host_exposure)
    if payload.host_name:
        new_host_exposure[payload.host_name] = (
            state.host_exposure.get(payload.host_name, 0) + influence_weight
        )
    for guest in payload.guest_names:
        new_host_exposure[guest] = (
            state.host_exposure.get(guest, 0) + influence_weight * 0.5  # Guests have less weight
        )
    
    # Update topic exposure
    new_topic_exposure = dict(state.topic_exposure)
    for topic in payload.topics:
        new_topic_exposure[topic] = (
            state.topic_exposure.get(topic, 0) + influence_weight
        )
    
    def updater(s: PodcastState) -> PodcastState:
        return PodcastState(
            stats=s.stats,
            recent_episodes=s.recent_episodes,
            host_exposure=new_host_exposure,
            topic_exposure=new_topic_exposure,
            listening_velocity=s.listening_velocity,
            topic_entropy=s.topic_entropy,
            depth_score=s.depth_score,
            last_listen_at=s.last_listen_at,
            streak_days=s.streak_days,
        )
    
    return [], updater


def emit_influence_signal(signal: Signal[PodcastListen], state: PodcastState):
    """Emit influence detection when exposure crosses threshold."""
    emissions = []
    
    # Check for significant host influence
    for host, exposure in state.host_exposure.items():
        if exposure >= 5.0:  # Threshold: 5 full episodes worth
            emissions.append(Emission(
                payload={
                    "type": "host_influence",
                    "host": host,
                    "exposure": exposure,
                    "episode_count": state.stats.total_episodes,
                },
                caused_by=signal.signal_id,
                emission_type="influence_detected",
            ))
    
    return emissions, None


def emit_milestone(signal: Signal[PodcastListen], state: PodcastState):
    """Emit milestone events."""
    emissions = []
    
    # Episode milestones
    milestones = [10, 25, 50, 100, 250, 500, 1000]
    if state.stats.total_episodes in milestones:
        emissions.append(Emission(
            payload={
                "type": "episode_milestone",
                "count": state.stats.total_episodes,
                "total_hours": state.stats.total_seconds / 3600,
            },
            caused_by=signal.signal_id,
            emission_type="milestone_reached",
        ))
    
    # Streak milestones
    streak_milestones = [7, 30, 100, 365]
    if state.streak_days in streak_milestones:
        emissions.append(Emission(
            payload={
                "type": "streak_milestone",
                "days": state.streak_days,
            },
            caused_by=signal.signal_id,
            emission_type="milestone_reached",
        ))
    
    return emissions, None


def compute_trajectory(signal: Signal[PodcastListen], state: PodcastState):
    """Compute trajectory metrics (velocity, entropy, depth)."""
    import math
    
    # Compute topic entropy (diversity)
    total_topic_exposure = sum(state.topic_exposure.values())
    if total_topic_exposure > 0:
        entropy = 0.0
        for exposure in state.topic_exposure.values():
            p = exposure / total_topic_exposure
            if p > 0:
                entropy -= p * math.log2(p)
        # Normalize to 0-1 (assuming max ~5 bits of entropy)
        topic_entropy = min(1.0, entropy / 5.0)
    else:
        topic_entropy = 0.0
    
    # Compute depth score (completion * consistency)
    completion = state.stats.completion_rate
    # For simplicity, consistency = 1.0 if listened recently
    consistency = 1.0 if state.stats.total_episodes > 0 else 0.0
    depth_score = completion * consistency
    
    def updater(s: PodcastState) -> PodcastState:
        return PodcastState(
            stats=s.stats,
            recent_episodes=s.recent_episodes,
            host_exposure=s.host_exposure,
            topic_exposure=s.topic_exposure,
            listening_velocity=s.listening_velocity,
            topic_entropy=topic_entropy,
            depth_score=depth_score,
            last_listen_at=s.last_listen_at,
            streak_days=s.streak_days,
        )
    
    return [], updater


# =============================================================================
# GAME IMPLEMENTATION
# =============================================================================

class PodcastGame:
    """
    Podcast Listening Game built on MetaSPN Engine.
    
    This game tracks podcast listening behavior and emits
    influence signals when patterns are detected.
    """
    
    name = "podcast"
    version = "1.0.0"
    
    def create_signal(self, data: dict) -> Signal[PodcastListen]:
        """Create a signal from raw listening data."""
        return Signal(
            payload=PodcastListen(
                episode_id=data["episode_id"],
                podcast_id=data["podcast_id"],
                podcast_name=data["podcast_name"],
                episode_title=data["episode_title"],
                duration_seconds=data["duration_seconds"],
                listened_seconds=data["listened_seconds"],
                completed=data.get("completed", False),
                host_name=data.get("host_name"),
                guest_names=data.get("guest_names", []),
                topics=data.get("topics", []),
            ),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "unknown"),
        )
    
    def initial_state(self) -> PodcastState:
        """Return initial game state."""
        return PodcastState()
    
    def pipeline(self) -> Pipeline:
        """Build the processing pipeline."""
        return Pipeline([
            track_listening,
            compute_influence,
            compute_trajectory,
            emit_influence_signal,
            emit_milestone,
        ], name="podcast_game")
    
    def create_engine(self, state_file: Optional[str] = None) -> Engine:
        """Create a configured engine for this game."""
        from .engine import EngineConfig
        from pathlib import Path
        
        config = EngineConfig(
            persist_state=state_file is not None,
            state_file=Path(state_file) if state_file else None,
            track_emission_history=True,
        )
        
        return Engine(
            pipeline=self.pipeline(),
            initial_state=self.initial_state(),
            config=config,
        )
    
    def compute_game_signature(self, state: PodcastState) -> GameSignature:
        """
        Compute game signature for a listener.
        
        Podcast listening primarily develops G3 (Models) through
        exposure to frameworks and mental models from hosts.
        """
        # Podcast listening primarily develops certain games
        # This is a simplified heuristic
        
        # G3 (Models) - Most podcast content is about understanding
        g3 = min(1.0, state.depth_score * 0.8)
        
        # G2 (Idea Mining) - If topics are diverse
        g2 = min(1.0, state.topic_entropy * 0.6)
        
        # G1 (Identity) - If following specific hosts deeply
        max_host = max(state.host_exposure.values()) if state.host_exposure else 0
        g1 = min(1.0, max_host / 20.0)  # 20 episodes = full G1 weight
        
        # G5 (Meaning) - Reflected in completion rate
        g5 = state.stats.completion_rate * 0.4
        
        return GameSignature(G1=g1, G2=g2, G3=g3, G4=0.0, G5=g5, G6=0.0)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Create the game
    game = PodcastGame()
    
    # Create engine
    engine = game.create_engine()
    
    # Sample listening events
    events = [
        {
            "episode_id": "ep_001",
            "podcast_id": "founders",
            "podcast_name": "Founders",
            "episode_title": "#328 - Steve Jobs",
            "duration_seconds": 3600,
            "listened_seconds": 3600,
            "completed": True,
            "host_name": "David Senra",
            "guest_names": [],
            "topics": ["entrepreneurship", "apple", "biography"],
            "timestamp": "2024-01-15T08:00:00Z",
            "source": "overcast",
        },
        {
            "episode_id": "ep_002",
            "podcast_id": "founders",
            "podcast_name": "Founders",
            "episode_title": "#329 - Estee Lauder",
            "duration_seconds": 4200,
            "listened_seconds": 4200,
            "completed": True,
            "host_name": "David Senra",
            "guest_names": [],
            "topics": ["entrepreneurship", "cosmetics", "biography"],
            "timestamp": "2024-01-16T08:00:00Z",
            "source": "overcast",
        },
    ]
    
    # Process events
    for event_data in events:
        signal = game.create_signal(event_data)
        emissions = engine.process(signal)
        
        print(f"Processed: {event_data['episode_title']}")
        for emission in emissions:
            print(f"  Emission: {emission.emission_type} - {emission.payload}")
    
    # Get final state
    state = engine.get_state()
    print("\nFinal State:")
    print(f"  Total episodes: {state.stats.total_episodes}")
    print(f"  Total hours: {state.stats.total_seconds / 3600:.1f}")
    print(f"  Completion rate: {state.stats.completion_rate:.1%}")
    print(f"  Host exposure: {dict(state.host_exposure)}")
    print(f"  Topic entropy: {state.topic_entropy:.2f}")
    
    # Compute game signature
    signature = game.compute_game_signature(state)
    print("\nGame Signature:")
    print(f"  G1 (Identity): {signature.G1:.2f}")
    print(f"  G2 (Ideas): {signature.G2:.2f}")
    print(f"  G3 (Models): {signature.G3:.2f}")
    print(f"  G5 (Meaning): {signature.G5:.2f}")
    print(f"  Primary game: {signature.primary_game()}")
