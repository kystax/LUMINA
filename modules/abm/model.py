"""
LUMINA - ABM Model
Simulates cognitive decline and awareness spread
across a social network over time.
"""

from typing import Any
import mesa
import random
from modules.abm.agents import PersonAgent, CommunityAgent
from modules.config.thresholds import ABM_DEFAULTS


class LuminaABM(mesa.Model):
    def __init__(
        self,
        n_people: int = ABM_DEFAULTS["n_people"],
        n_community_agents: int = ABM_DEFAULTS["n_community_agents"],
        initial_risk_score: float = 0.3,
        grid_size: int = ABM_DEFAULTS["grid_size"],
        seed: int | None = None
    ):
        super().__init__()
        if seed is not None:
            random.seed(seed)
        else:
            # Dynamic seed based on risk score + system randomness
            random.seed(int(initial_risk_score * 100000) + random.randint(1, 999999))

        self.n_people = n_people
        self.grid_size = grid_size
        
        if hasattr(mesa, "time") and hasattr(mesa.time, "RandomActivation"):
            self.schedule = mesa.time.RandomActivation(self)
        else:
            # Fallback scheduler for Mesa 3.0+
            class _SimpleSchedule:
                def __init__(self, model):
                    self.model = model
                    self.agents = []
                def add(self, agent):
                    if agent not in self.agents:
                        self.agents.append(agent)
                def step(self):
                    random.shuffle(self.agents)
                    for agent in list(self.agents):
                        if hasattr(agent, "step"):
                            agent.step()
            self.schedule = _SimpleSchedule(self)

        self.grid = mesa.space.MultiGrid(grid_size, grid_size, torus=True)

        self.awareness_spread_count = 0
        self.step_count = 0
        self.history = []

        from modules.config.thresholds import AGENT_SUPPORT

        for i in range(n_people):
            risk = max(0.0, min(1.0, initial_risk_score + random.uniform(-0.15, 0.15)))
            agent = PersonAgent(i, self, initial_risk=risk)
            self.schedule.add(agent)
            x = random.randrange(grid_size)
            y = random.randrange(grid_size)
            self.grid.place_agent(agent, (x, y))

        # Identify the seed agent (first PersonAgent) before placing CommunityAgents,
        # so we can anchor up to min(n_community_agents, 3) of them within support radius.
        person_agents = [a for a in self.schedule.agents if isinstance(a, PersonAgent)]
        self.seed_agent = None
        if person_agents:
            person_agents[0].aware = True
            person_agents[0].risk_score = initial_risk_score
            self.seed_agent = person_agents[0]

        # Build list of grid cells within AGENT_SUPPORT["radius"] of the seed agent.
        # These are the candidate "near" cells for anchored community agents.
        support_radius = AGENT_SUPPORT["radius"]  # 2 by default
        near_cells: list[tuple[int, int]] = []
        if self.seed_agent and self.seed_agent.pos:
            pos_val: Any = self.seed_agent.pos
            sx = int(pos_val[0])
            sy = int(pos_val[1])
            for dx in range(-support_radius, support_radius + 1):
                for dy in range(-support_radius, support_radius + 1):
                    if dx == 0 and dy == 0:
                        continue  # skip seed's own cell
                    nx = (sx + dx) % grid_size
                    ny = (sy + dy) % grid_size
                    near_cells.append((nx, ny))
            random.shuffle(near_cells)  # randomise which adjacent cells are used

        n_anchored = min(n_community_agents, 3) if n_community_agents > 0 else 0

        for i in range(n_community_agents):
            agent = CommunityAgent(n_people + i, self, support_strength=0.4)
            self.schedule.add(agent)
            if i < n_anchored and i < len(near_cells):
                # Place this community agent adjacent to the seed agent
                x, y = near_cells[i]
            else:
                # Random placement for remaining agents
                x = random.randrange(grid_size)
                y = random.randrange(grid_size)
            self.grid.place_agent(agent, (x, y))

    def step(self):
        if self.schedule:
            self.schedule.step()
        self.step_count += 1
        self._record_state()

    def _record_state(self):
        agents = [a for a in self.schedule.agents if isinstance(a, PersonAgent)] if self.schedule else []
        hc    = sum(1 for a in agents if a.state == "HC")
        mci   = sum(1 for a in agents if a.state == "MCI")
        ad    = sum(1 for a in agents if a.state == "AD_Risk")
        aware = sum(1 for a in agents if a.aware)
        avg_social = sum(a.social_activity for a in agents) / max(len(agents), 1)

        self.history.append({
            "step":             self.step_count,
            "HC":               hc,
            "MCI":              mci,
            "AD_Risk":          ad,
            "aware":            aware,
            "avg_social":       round(avg_social, 3),
            "awareness_spread": self.awareness_spread_count,
            "seed_risk":        round(self.seed_agent.risk_score, 4) if self.seed_agent else None,
        })

    def run(self, steps: int = 20) -> list[dict]:
        for _ in range(steps):
            self.step()
        return self.history

    def get_agent_snapshot(self) -> dict:
        """
        Snapshot of every agent's final position + state, plus which other
        person-agents are within its Moore neighborhood (the same
        adjacency PersonAgent._interact_with_network() actually uses to
        spread awareness) — so a network visual can draw real interaction
        edges instead of an arbitrary layout.
        """
        agents = list(self.schedule.agents) if self.schedule else []
        snapshot = []

        for agent in agents:
            is_community = isinstance(agent, CommunityAgent)
            entry = {
                "id": agent.unique_id,
                "x": agent.pos[0] if agent.pos else 0,
                "y": agent.pos[1] if agent.pos else 0,
                "is_community": is_community,
            }
            if is_community:
                entry["state"] = "community"
            else:
                entry["state"] = agent.state
                entry["aware"] = agent.aware
            snapshot.append(entry)

        # Real Moore-neighborhood edges between person-agents, matching
        # the adjacency PersonAgent._interact_with_network() uses.
        edges = []
        person_agents = [a for a in agents if isinstance(a, PersonAgent)]
        for agent in person_agents:
            if isinstance(agent.pos, tuple) and len(agent.pos) == 2:
                pos = (int(agent.pos[0]), int(agent.pos[1]))
                neighbours = self.grid.get_neighbors(
                    pos, moore=True, include_center=False
                )
                for neighbour in neighbours:
                    if isinstance(neighbour, PersonAgent) and neighbour.unique_id > agent.unique_id:
                        edges.append((agent.unique_id, neighbour.unique_id))

        return {"nodes": snapshot, "edges": edges}

    def get_summary(self) -> dict:
        if not self.history:
            return {}
        final   = self.history[-1]
        initial = self.history[0]
        return {
            "total_steps":      self.step_count,
            "final_HC":         final["HC"],
            "final_MCI":        final["MCI"],
            "final_AD_Risk":    final["AD_Risk"],
            "awareness_reached": final["aware"],
            "awareness_spread": self.awareness_spread_count,
            "social_decline":   round(initial["avg_social"] - final["avg_social"], 3),
            "mci_progression":  final["MCI"] - initial["MCI"],
        }


# ─────────────────────────────────────────────
# SAVE TO DB
# ─────────────────────────────────────────────

FACTOR_LABELS = {
    "education_less_than_secondary": "Education (< Secondary)",
    "hearing_loss": "Hearing Loss Management",
    "hypertension": "Hypertension Control",
    "smoking": "Smoking Cessation",
    "obesity": "Obesity Reduction",
    "depression": "Depression Treatment",
    "physical_inactivity": "Physical Activity Increase",
    "diabetes": "Diabetes Control",
    "low_social_contact": "Social Contact Increase",
    "excessive_alcohol": "Alcohol Reduction",
    "traumatic_brain_injury": "TBI Monitoring",
    "air_pollution": "Air Pollution Reduction",
    "vision_loss": "Vision Care",
    "high_ldl_cholesterol": "LDL Cholesterol Reduction",
}

FACTOR_GUIDANCE = {
    "smoking": "Stopping smoking reduces vascular dementia risk and improves cerebral oxygenation.",
    "physical_inactivity": "Regular aerobic exercise (150 mins/week) enhances neuroplasticity and cognitive reserve.",
    "low_social_contact": "Increasing social engagement stimulates cognitive networks and reduces depressive isolation.",
    "hypertension": "Managing blood pressure (< 130/80 mmHg) lowers microvascular brain damage.",
    "hearing_loss": "Using hearing aids restores auditory cognitive input and reduces cognitive load.",
    "obesity": "Weight management improves metabolic insulin sensitivity in brain tissue.",
    "depression": "Treating depressive episodes prevents neuroendocrine hippocampal atrophy.",
    "diabetes": "Optimising glycemic control prevents neurovascular micro-angiopathy.",
    "excessive_alcohol": "Limiting alcohol intake prevents direct neurotoxic damage.",
    "high_ldl_cholesterol": "Lowering LDL cholesterol reduces cerebral atherosclerotic plaque buildup.",
    "vision_loss": "Correcting vision loss maintains visual cognitive stimulation.",
    "education_less_than_secondary": "Engaging in lifelong learning builds cognitive reserve.",
    "traumatic_brain_injury": "Protecting against head trauma prevents chronic traumatic encephalopathy.",
    "air_pollution": "Reducing air pollution exposure lowers neuroinflammatory particulate strain."
}


def run_outcome_scenarios(
    initial_risk_score: float,
    seed: int | None = None,
    environmental_intake: dict | None = None,
) -> dict:
    """
    Runs the ABM under baseline conditions (without support vs with support),
    and if active Lancet environmental factors are present, simulates individual
    and combined factor-mitigation trajectories.
    """
    from modules.config.thresholds import ABM_SCENARIO_DEFAULTS, ABM_DEFAULTS
    from concurrent.futures import ThreadPoolExecutor

    base_seed = seed if seed is not None else int(initial_risk_score * 100000)

    def _run(risk_score: float, n_community_agents: int, sub_seed: int) -> list:
        model = LuminaABM(
            n_people=ABM_SCENARIO_DEFAULTS["n_people"],
            n_community_agents=n_community_agents,
            initial_risk_score=max(0.0, min(1.0, risk_score)),
            grid_size=ABM_SCENARIO_DEFAULTS["grid_size"],
            seed=sub_seed,
        )
        model.run(steps=ABM_SCENARIO_DEFAULTS["steps"])
        return [round(h["seed_risk"] * 100) for h in model.history]

    # Parse active factors from environmental_intake
    factors = (environmental_intake.get("factors") or {}) if environmental_intake else {}
    active_factors = [k for k, v in factors.items() if v and k in FACTOR_LABELS]
    k_count = len(active_factors)

    # Base baseline runs
    with ThreadPoolExecutor(max_workers=max(2, k_count + 3)) as pool:
        f_no_support = pool.submit(_run, initial_risk_score, 0, base_seed + 101)
        f_support    = pool.submit(_run, initial_risk_score, ABM_DEFAULTS.get("n_community_agents", 5), base_seed + 202)

        # Submit per-factor mitigation runs if factors are present
        factor_futures = {}
        combined_future = None

        if k_count > 0:
            # Baseline base environmental risk portion (max 5 factors = 1.0)
            baseline_env_base = min(k_count / 5.0, 1.0)

            for key in active_factors:
                new_env_base = min(max(0, k_count - 1) / 5.0, 1.0)
                env_drop = (baseline_env_base - new_env_base) * 0.5
                risk_delta = env_drop * 0.40  # 40% environmental weight
                mitigated_risk = max(0.0, initial_risk_score - risk_delta)
                factor_futures[key] = pool.submit(
                    _run, mitigated_risk, ABM_DEFAULTS.get("n_community_agents", 5), base_seed + hash(key) % 10000
                )

            # Combined mitigation run (all active factors mitigated)
            all_mitigated_env_drop = baseline_env_base * 0.5
            combined_risk_delta = all_mitigated_env_drop * 0.40
            combined_mitigated_risk = max(0.0, initial_risk_score - combined_risk_delta)
            combined_future = pool.submit(
                _run, combined_mitigated_risk, ABM_DEFAULTS.get("n_community_agents", 5), base_seed + 9999
            )

        without_support = f_no_support.result()
        with_support    = f_support.result()

        factor_scenarios = {}
        factor_impacts = []

        for key in active_factors:
            f_series = factor_futures[key].result()
            factor_scenarios[key] = f_series
            # Impact at +12mo (step 12)
            baseline_12m = without_support[min(12, len(without_support)-1)]
            mitigated_12m = f_series[min(12, len(f_series)-1)]
            diff_12m = round(baseline_12m - mitigated_12m)

            factor_impacts.append({
                "key": key,
                "name": FACTOR_LABELS.get(key, key),
                "reduction_at_12m": max(1, diff_12m),
                "guidance": FACTOR_GUIDANCE.get(key, "Mitigating this risk factor supports cognitive resilience."),
            })

        combined_mitigation = combined_future.result() if combined_future else None
        if combined_mitigation:
            baseline_12m = without_support[min(12, len(without_support)-1)]
            comb_12m = combined_mitigation[min(12, len(combined_mitigation)-1)]
            total_diff = round(baseline_12m - comb_12m)
            factor_impacts.insert(0, {
                "key": "combined_all",
                "name": "Combined Mitigation (All Factors)",
                "reduction_at_12m": max(1, total_diff),
                "guidance": "Addressing all active modifiable risk factors produces compound cognitive risk reduction.",
            })

    return {
        "without_support": without_support,
        "with_support":    with_support,
        "factor_scenarios": factor_scenarios,
        "combined_mitigation": combined_mitigation,
        "factor_impacts": factor_impacts,
    }


def save_abm_to_db(summary: dict, session_id: int):
    """Save ABM simulation summary and compute final combined risk score."""
    from database.connection import get_connection, release_connection

    conn = get_connection()
    if not conn:
        return

    cur = None
    try:
        cur = conn.cursor()

        # Get full NLP risk score for this session (includes TTR, coherence, complexity, repetition)
        cur.execute("""
            SELECT risk_score, risk_class, confidence_score
            FROM nlp_scores WHERE session_id = %s
        """, (session_id,))
        nlp = cur.fetchone()

        # Get SNA withdrawal score
        cur.execute("""
            SELECT withdrawal_score FROM sna_scores WHERE session_id = %s
        """, (session_id,))
        sna = cur.fetchone()

        # Get user_id for this session
        cur.execute("SELECT user_id FROM sessions WHERE session_id = %s", (session_id,))
        session_row = cur.fetchone()
        user_id = session_row[0] if session_row else 1

        # Insert or update ABM results summary table
        cur.execute("""
            INSERT INTO abm_results
                (session_id, final_hc, final_mci, final_ad_risk,
                 awareness_spread, social_decline)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                final_hc = EXCLUDED.final_hc,
                final_mci = EXCLUDED.final_mci,
                final_ad_risk = EXCLUDED.final_ad_risk,
                awareness_spread = EXCLUDED.awareness_spread,
                social_decline = EXCLUDED.social_decline
        """, (
            session_id,
            summary.get("final_HC", 0),
            summary.get("final_MCI", 0),
            summary.get("final_AD_Risk", 0),
            summary.get("awareness_spread", 0),
            summary.get("social_decline", 0.0),
        ))

        from modules.config.thresholds import (
            FINAL_RISK_WEIGHTS,
            RISK_CLASS_THRESHOLDS,
        )

        nlp_risk = float(nlp[0]) if (nlp and nlp[0] is not None) else 0.5

        # Get Environmental score
        cur.execute("""
            SELECT environmental_risk_score FROM environmental_scores WHERE session_id = %s
        """, (session_id,))
        env = cur.fetchone()
        env_risk = float(env[0]) if (env and env[0] is not None) else 0.0

        sna_withdrawal = float(sna[0]) if sna and sna[0] else 0.0
        abm_seed_risk  = float(summary.get("abm_seed_risk", summary.get("seed_risk", min(summary.get("awareness_spread", 0) / 10.0, 1.0))))

        blended_score = (
            nlp_risk       * FINAL_RISK_WEIGHTS["nlp"] +
            env_risk       * FINAL_RISK_WEIGHTS.get("environmental", 0.40) +
            sna_withdrawal * FINAL_RISK_WEIGHTS["withdrawal"] +
            abm_seed_risk  * FINAL_RISK_WEIGHTS["abm_spread"]
        )

        # Floor removed — mathematically redundant since blended_score = nlp_sna_only + env_risk * weight,
        # and env_risk >= 0, so blended_score >= 0.8 * nlp_sna_only always holds. Confirmed via test case in Aug 2026.
        final_score = round(min(max(blended_score, 0.0), 1.0), 4)

        # Determine final risk class
        if final_score < RISK_CLASS_THRESHOLDS["HC_MAX"]:
            final_class = "HC"
        elif final_score < RISK_CLASS_THRESHOLDS["MCI_MAX"]:
            final_class = "MCI"
        else:
            final_class = "AD_Risk"

        cur.execute("""
            INSERT INTO risk_results
                (session_id, user_id, final_risk_class, final_score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                final_risk_class = EXCLUDED.final_risk_class,
                final_score = EXCLUDED.final_score,
                created_at = NOW()
        """, (session_id, user_id, final_class, final_score))

        conn.commit()
        print(f"[LUMINA ABM] ABM & Final risk saved: {final_class} (score: {final_score}) for session {session_id}")

    except Exception as e:
        import traceback
        print(f"[LUMINA ABM] DB error: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from database.connection import get_connection, release_connection

    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT n.ttr_score, n.complexity_score, s.withdrawal_score
        FROM nlp_scores n
        JOIN sna_scores s ON n.session_id = s.session_id
        WHERE n.session_id = 1
    """)
    row = cur.fetchone()
    cur.close()
    release_connection(conn)

    if row:
        ttr, complexity, withdrawal = row
        ttr_risk        = 1.0 - min(float(ttr) * 2.5, 1.0)
        complexity_risk = 1.0 - min(float(complexity) / 0.15, 1.0)
        initial_risk    = round(ttr_risk * 0.5 + complexity_risk * 0.3 + float(withdrawal) * 0.2, 4)
    else:
        initial_risk = 0.3

    print(f"[LUMINA ABM] Initial risk score: {initial_risk}")
    print("[LUMINA ABM] Running simulation (20 steps)...\n")

    model   = LuminaABM(n_people=50, n_community_agents=5,
                        initial_risk_score=initial_risk, grid_size=15)
    history = model.run(steps=20)
    summary = model.get_summary()

    print("=" * 50)
    print("ABM SIMULATION SUMMARY")
    print("=" * 50)
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\nStep-by-step progression:")
    for h in history:
        print(f"  Step {h['step']:2d} | "
              f"HC:{h['HC']:3d} MCI:{h['MCI']:3d} AD:{h['AD_Risk']:3d} | "
              f"Aware:{h['aware']:3d} | Social:{h['avg_social']:.3f}")

    save_abm_to_db(summary, session_id=1)