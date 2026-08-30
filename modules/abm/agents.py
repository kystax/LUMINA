"""
LUMINA - ABM Agents
Two agent types:
1. PersonAgent     — individual with cognitive risk level
2. CommunityAgent  — represents awareness/support in the network
"""

import mesa
import random

from modules.config.thresholds import (
    AGENT_STATE_THRESHOLDS,
    AGENT_PROGRESSION,
    AGENT_SUPPORT,
    AWARENESS_SPREAD_CHANCE,
)


from typing import Any


class PersonAgent(mesa.Agent):
    """
    Represents an individual in the social network.

    States:
    - HC       : Healthy Control
    - MCI      : Mild Cognitive Impairment  
    - AD_Risk  : High Risk
    - Aware    : Knows about their risk, seeking help
    """

    def __init__(self, unique_id, model, initial_risk: float = 0.0):
        super().__init__(unique_id, model)
        self.model: Any = model

        self.risk_score = initial_risk
        self.state = self._risk_to_state(initial_risk)
        self.social_activity = random.uniform(0.3, 1.0)  # how active socially
        self.support_received = 0.0
        self.aware = False
        self.steps_in_state = 0

    def step(self):
        """Called every simulation step (represents one time period)."""
        self._update_risk()
        self._interact_with_network()
        self._receive_support()
        self.steps_in_state += 1

    def _update_risk(self):
        """
        Risk naturally increases over time unless support is received.
        Social isolation accelerates risk progression.
        """
        # Base progression rate
        progression = AGENT_PROGRESSION["base_rate"]

        # Isolation accelerates decline
        if self.social_activity < AGENT_PROGRESSION["isolation_threshold"]:
            progression += AGENT_PROGRESSION["isolation_penalty"]

        # Support slows progression
        if self.support_received > AGENT_PROGRESSION["support_threshold"]:
            progression -= AGENT_PROGRESSION["support_relief"]

        # Apply progression
        self.risk_score = min(self.risk_score + progression, 1.0)
        self.state = self._risk_to_state(self.risk_score)

        # Social activity declines as risk increases
        if self.state == "MCI":
            self.social_activity = max(self.social_activity - 0.01, 0.0)
        elif self.state == "AD_Risk":
            self.social_activity = max(self.social_activity - 0.02, 0.0)

    def _interact_with_network(self):
        """
        Interact with nearby agents.
        High-risk agents spread awareness to neighbours.
        """
        neighbours = self.model.grid.get_neighbors(
            self.pos, moore=True, include_center=False
        )
        for neighbour in neighbours:
            if isinstance(neighbour, PersonAgent):
                # If this agent is aware, they can alert neighbours
                if self.aware and not neighbour.aware:
                    if random.random() < AWARENESS_SPREAD_CHANCE:
                        neighbour.aware = True
                        self.model.awareness_spread_count += 1

    def _receive_support(self):
        """
        Check if any CommunityAgent nearby provides support.
        """
        neighbours = self.model.grid.get_neighbors(
            self.pos, moore=True, include_center=False,
            radius=AGENT_SUPPORT["radius"]
        )
        support = sum(
            1 for n in neighbours
            if isinstance(n, CommunityAgent) and n.active
        )
        self.support_received = min(
            support * AGENT_SUPPORT["support_per_agent"],
            AGENT_SUPPORT["max_support"],
        )

    def _risk_to_state(self, score: float) -> str:
        if score < AGENT_STATE_THRESHOLDS["HC_MAX"]:
            return "HC"
        elif score < AGENT_STATE_THRESHOLDS["MCI_MAX"]:
            return "MCI"
        else:
            return "AD_Risk"


class CommunityAgent(mesa.Agent):
    """
    Represents a community support resource:
    NGO, healthcare worker, family carer, etc.

    Provides support to nearby PersonAgents.
    Becomes more active as awareness spreads.
    """

    def __init__(self, unique_id, model, support_strength: float = 0.5):
        super().__init__(unique_id, model)
        self.model: Any = model
        self.support_strength = support_strength
        self.active = True
        self.people_supported = 0

    def step(self):
        """Expand reach as more people become aware."""
        neighbours = self.model.grid.get_neighbors(
            self.pos, moore=True, include_center=False, radius=2
        )
        for neighbour in neighbours:
            if isinstance(neighbour, PersonAgent):
                if neighbour.state in ["MCI", "AD_Risk"]:
                    self.people_supported += 1
                    # Make them aware
                    if not neighbour.aware:
                        if random.random() < self.support_strength:
                            neighbour.aware = True
                            self.model.awareness_spread_count += 1
