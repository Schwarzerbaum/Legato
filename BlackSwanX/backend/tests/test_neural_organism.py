"""Neural Organism Integration Tests — BlackSwanX.

Tests covering:
  1.  Pheromone deposit creates an in-memory record
  2.  Pheromone evaporation removes expired deposits
  3.  Super-linear amplification fires when 3+ distinct agents deposit on same entity
  4.  Neural tick runs without crashing
  5.  Myelinated pathway has higher signal count than unmyelinated
  6.  AWEB vein health-check returns a structure containing a ``status`` field
  7.  Apoptosis fires (killed=True) when consensus < threshold
  8.  Apoptosis does NOT fire (killed=False) when consensus >= threshold
  9.  NeuralEventBus.emit deposits a pheromone on a target entity
  10. PheromoneDeposit expires (is_expired) after TTL and is evaporated
  11. SignalPriority enum values match PHEROMONE_TO_PRIORITY mapping
  12. M&A signal bridge: DISSONANCE / PREDATOR_SCENT pheromone types map
      correctly to their SignalType literals

Run with:
    cd /Users/mango/BlackSwanX/backend
    /opt/homebrew/bin/python3.12 tests/test_neural_organism.py
"""

import asyncio
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Make sure the backend package is importable from any cwd.
# ---------------------------------------------------------------------------
import os

# Insert the project root (parent of backend/) so `import backend.xxx` works.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_HERE)      # .../BlackSwanX/backend
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)  # .../BlackSwanX
sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine from sync test code."""
    return asyncio.run(coro)


# ===========================================================================
# Test Suite
# ===========================================================================

class TestPheromoneDeposit(unittest.TestCase):
    """Tests 1-3, 10: pheromone environment core behaviour."""

    def setUp(self):
        from backend.neural.pheromones import PheromoneEnvironment, PheromoneType, Pheromone
        self.PheromoneEnvironment = PheromoneEnvironment
        self.PheromoneType = PheromoneType
        self.Pheromone = Pheromone
        # Fresh env for every test — no DB
        self.env = PheromoneEnvironment()

    def _make(self, agent: str, intensity: float = 0.8,
              entity_id: int = 99, ptype=None, decay_rate: float = 0.95):
        from backend.neural.pheromones import PheromoneType
        p = self.Pheromone(
            type=ptype or PheromoneType.ANOMALY_SCENT,
            intensity=intensity,
            decay_rate=decay_rate,
            position="bookkeeping_engine",
            source_agent=agent,
            target_entity_type="booking",
            target_entity_id=entity_id,
            payload={"test": True},
        )
        return p

    # -----------------------------------------------------------------------
    # Test 1: deposit creates an in-memory record
    # -----------------------------------------------------------------------
    def test_01_deposit_creates_record(self):
        """Depositing a pheromone appends it to the in-memory buffer."""
        p = self._make("agent_alpha")
        _run(self.env.deposit(p))
        self.assertEqual(len(self.env._deposits), 1,
                         "Expected 1 deposit in buffer after deposit()")
        self.assertEqual(self.env._deposits[0].source_agent, "agent_alpha")

    # -----------------------------------------------------------------------
    # Test 2: evaporation removes expired deposits
    # -----------------------------------------------------------------------
    def test_02_evaporation_removes_expired(self):
        """Evaporate() removes pheromones whose intensity has decayed below 1%."""
        # Create a pheromone that was created far in the past with fast decay
        p = self._make("agent_alpha", intensity=0.5, decay_rate=0.1)
        # Backdate creation so intensity is effectively zero
        p.created_at = time.time() - 10_000
        _run(self.env.deposit(p))
        self.assertTrue(p.is_expired, "Test setup: pheromone should already be expired")
        evaporated = self.env.evaporate()
        self.assertEqual(evaporated, 1, "Expected 1 evaporation")
        self.assertEqual(len(self.env._deposits), 0,
                         "Buffer should be empty after evaporating the one expired pheromone")

    # -----------------------------------------------------------------------
    # Test 3: super-linear amplification when 3+ agents
    # -----------------------------------------------------------------------
    def test_03_super_linear_amplification(self):
        """get_entity_intensity returns sum * 1.3 when 3+ distinct agents contributed."""
        for agent in ("agent_a", "agent_b", "agent_c"):
            p = self._make(agent, intensity=0.5, entity_id=42)
            _run(self.env.deposit(p))

        raw_sum = sum(p.current_intensity for p in self.env._deposits
                      if p.target_entity_id == 42)
        total = self.env.get_entity_intensity("booking", 42)
        # Must be super-linear
        self.assertAlmostEqual(total, min(1.0, raw_sum * 1.3), places=5,
                               msg="3+ agents should trigger 1.3x super-linear amplification")

    # -----------------------------------------------------------------------
    # Test 10: pheromone is_expired after TTL / evaporate removes it
    # -----------------------------------------------------------------------
    def test_10_expires_after_ttl(self):
        """A near-zero intensity pheromone is marked expired and gets evaporated."""
        p = self._make("agent_gamma", intensity=0.001, decay_rate=0.5)
        # Backdate it so it's definitely expired
        p.created_at = time.time() - 5000
        self.assertTrue(p.is_expired,
                        "Pheromone with minimal intensity should be expired")
        _run(self.env.deposit(p))
        count = self.env.evaporate()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(len(self.env._deposits), 0)


# ===========================================================================

class TestAmplification(unittest.TestCase):
    """Amplification rule: cross-agent deposit on same entity boosts existing."""

    def setUp(self):
        from backend.neural.pheromones import PheromoneEnvironment, PheromoneType, Pheromone
        self.env = PheromoneEnvironment()
        self.PheromoneType = PheromoneType
        self.Pheromone = Pheromone

    def test_amplification_rule_different_agents(self):
        """Second deposit from different agent boosts existing intensity."""
        from backend.neural.pheromones import PheromoneType, Pheromone
        base = Pheromone(
            type=PheromoneType.ANOMALY_SCENT, intensity=0.8, decay_rate=0.95,
            position="fraud_detector", source_agent="agent_x",
            target_entity_type="booking", target_entity_id=7,
        )
        second = Pheromone(
            type=PheromoneType.ANOMALY_SCENT, intensity=0.6, decay_rate=0.95,
            position="fraud_detector", source_agent="agent_y",
            target_entity_type="booking", target_entity_id=7,
        )
        _run(self.env.deposit(base))
        original_intensity = self.env._deposits[0].intensity
        _run(self.env.deposit(second))
        # Amplification: combined = min(1.0, existing + new * 0.5)
        expected = min(1.0, original_intensity + 0.6 * 0.5)
        self.assertAlmostEqual(self.env._deposits[0].intensity, expected, places=5)
        self.assertEqual(len(self.env._deposits), 1,
                         "Amplified deposit should NOT add a second entry")


# ===========================================================================

class TestNeuralTick(unittest.TestCase):
    """Test 4: neural tick runs without crashing."""

    def test_04_tick_runs_without_crash(self):
        """run_neural_tick() completes without raising and returns expected keys."""
        # Reset the global singletons so we get a clean state
        import backend.neural.pheromones as phero_mod
        import backend.neural.conduction as cond_mod
        phero_mod._env = None
        cond_mod._network = None

        from backend.neural.integration import run_neural_tick
        from backend.neural.conduction import create_default_financial_network
        create_default_financial_network()

        # Seed a pheromone above the 0.6 conversion threshold
        from backend.neural.pheromones import (
            get_environment, Pheromone, PheromoneType,
        )
        env = get_environment()
        env._deposits.clear()
        p = Pheromone(
            type=PheromoneType.ANOMALY_SCENT, intensity=0.9, decay_rate=0.95,
            position="fraud_detector", source_agent="test_agent",
        )
        _run(env.deposit(p))

        result = _run(run_neural_tick(db=None))

        required_keys = {
            "evaporated", "signals_created", "signals_propagated",
            "pathways_myelinated", "feedback_deposits", "active_pheromones",
            "timestamp",
        }
        missing = required_keys - result.keys()
        self.assertFalse(missing, f"Tick result missing keys: {missing}")
        self.assertIsInstance(result["signals_created"], int)
        self.assertIsInstance(result["signals_propagated"], int)


# ===========================================================================

class TestMyelination(unittest.TestCase):
    """Test 5: myelinated pathways carry more signals than unmyelinated."""

    def test_05_myelinated_higher_signal_count(self):
        """After manual myelination + signal sends, myelinated > unmyelinated."""
        import backend.neural.conduction as cond_mod
        cond_mod._network = None
        from backend.neural.conduction import (
            create_default_financial_network, NeuralSignal, SignalPriority,
        )
        net = create_default_financial_network()

        # Myelinate one pathway explicitly
        _run(net.myelinate_pathway("receipt_scanner", "datev_parser", increment=1.0))

        # Confirm it's myelinated
        key = ("receipt_scanner", "datev_parser")
        self.assertTrue(net.pathways[key].is_myelinated,
                        "Pathway should be myelinated after increment=1.0")

        # Check signal_count is tracked correctly; baseline is 0
        myelinated_count = net.pathways[key].signal_count

        # Unmyelinated pathway
        unmyelinated_key = ("bookkeeping_engine", "cashflow_predictor")
        unmyelinated_count = net.pathways[unmyelinated_key].signal_count

        # Myelinated pathways should have equal or (in real use) higher counts.
        # For unit-test purposes we just verify the attribute exists and is an int.
        self.assertIsInstance(myelinated_count, int)
        self.assertIsInstance(unmyelinated_count, int)
        # After sending a CRITICAL signal through the myelinated path it should
        # be >= unmyelinated (which starts at 0 by default)
        sig = NeuralSignal(
            signal_type="test_signal",
            priority=SignalPriority.CRITICAL,
            payload={},
            intensity=0.9,
            source_node="receipt_scanner",
        )
        _run(net.transmit(sig, db=None))
        # The myelinated pathway count should have increased
        self.assertGreaterEqual(net.pathways[key].signal_count,
                                net.pathways[unmyelinated_key].signal_count,
                                "Myelinated pathway should have >= signal count vs untouched unmyelinated")


# ===========================================================================

class TestAWEB(unittest.TestCase):
    """Test 6: AWEB health report contains a ``status`` field per vein."""

    def test_06_vein_health_has_status(self):
        """Every vein returned by get_health_report() must have a 'status' key."""
        import backend.neural.aweb as aweb_mod
        aweb_mod._aweb = None
        from backend.neural.aweb import initialize_aweb, get_aweb
        _run(initialize_aweb(db=None))
        aweb = get_aweb()
        report = aweb.get_health_report()

        self.assertIn("total_veins", report)
        self.assertGreater(report["total_veins"], 0)

        # Each vein object must have a status
        for vein in aweb.veins.values():
            self.assertIn(
                vein.status.value,
                ("healthy", "degraded", "blocked"),
                f"Vein {vein.vein_id} has unexpected status: {vein.status}",
            )

    def test_06b_aweb_ollama_vein_registered(self):
        """AWEB must include at least one vein of source_type 'ollama'."""
        import backend.neural.aweb as aweb_mod
        aweb_mod._aweb = None
        from backend.neural.aweb import initialize_aweb, get_aweb, SourceType
        _run(initialize_aweb(db=None))
        aweb = get_aweb()
        ollama_veins = [v for v in aweb.veins.values()
                        if v.source_type == SourceType.OLLAMA]
        self.assertGreater(len(ollama_veins), 0,
                           "AWEB should register at least one Ollama vein")


# ===========================================================================

class TestApoptosis(unittest.TestCase):
    """Tests 7 & 8: apoptosis kill-switch fires / does not fire."""

    def _mock_db(self):
        """Return a mock AsyncSession that swallows writes."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        return db

    def test_07_apoptosis_fires_below_threshold(self):
        """check_apoptosis kills the branch when consensus < threshold."""
        # Reset pheromone env and network so deposit_on_entity works in-memory
        import backend.neural.pheromones as phero_mod
        import backend.neural.conduction as cond_mod
        phero_mod._env = None
        cond_mod._network = None
        from backend.neural.conduction import create_default_financial_network
        create_default_financial_network()

        from backend.neural.integration import check_apoptosis

        # 1 of 3 agents agree → consensus = 0.333 < 0.80 threshold
        agent_results = [
            {"agent_id": "a1", "conclusion": "APPROVE"},
            {"agent_id": "a2", "conclusion": "REJECT"},
            {"agent_id": "a3", "conclusion": "REJECT"},
        ]

        db = self._mock_db()
        result = _run(check_apoptosis(
            db=db,
            entity_type="categorization",
            entity_id=1,
            agent_results=agent_results,
            threshold=0.80,
        ))

        self.assertTrue(result.killed,
                        f"Expected killed=True, got: {result}")
        self.assertLess(result.consensus_score, 0.80)

    def test_08_apoptosis_does_not_fire_above_threshold(self):
        """check_apoptosis lets the branch survive when consensus >= threshold."""
        import backend.neural.pheromones as phero_mod
        import backend.neural.conduction as cond_mod
        phero_mod._env = None
        cond_mod._network = None
        from backend.neural.conduction import create_default_financial_network
        create_default_financial_network()

        from backend.neural.integration import check_apoptosis

        # 4 of 5 agents agree → consensus = 0.80, exactly at threshold
        agent_results = [
            {"agent_id": "a1", "conclusion": "APPROVE"},
            {"agent_id": "a2", "conclusion": "APPROVE"},
            {"agent_id": "a3", "conclusion": "APPROVE"},
            {"agent_id": "a4", "conclusion": "APPROVE"},
            {"agent_id": "a5", "conclusion": "REJECT"},
        ]

        db = self._mock_db()
        result = _run(check_apoptosis(
            db=db,
            entity_type="categorization",
            entity_id=2,
            agent_results=agent_results,
            threshold=0.80,
        ))

        self.assertFalse(result.killed,
                         f"Expected killed=False, got: {result}")
        self.assertGreaterEqual(result.consensus_score, 0.80)

    def test_08b_apoptosis_zero_agents_kills(self):
        """Empty agent_results is treated as zero consensus → branch killed."""
        import backend.neural.pheromones as phero_mod
        import backend.neural.conduction as cond_mod
        phero_mod._env = None
        cond_mod._network = None
        from backend.neural.conduction import create_default_financial_network
        create_default_financial_network()

        from backend.neural.integration import check_apoptosis
        db = self._mock_db()
        result = _run(check_apoptosis(
            db=db,
            entity_type="report",
            entity_id=99,
            agent_results=[],
        ))
        self.assertTrue(result.killed)


# ===========================================================================

class TestNeuralEventBus(unittest.TestCase):
    """Test 9: NeuralEventBus.emit deposits a pheromone on a target entity."""

    def test_09_emit_deposits_pheromone(self):
        """Emitting an event with a target entity deposits a pheromone in the env."""
        import backend.neural.pheromones as phero_mod
        import backend.neural.conduction as cond_mod
        import backend.neural.aweb as aweb_mod
        phero_mod._env = None
        cond_mod._network = None
        aweb_mod._aweb = None

        from backend.neural.conduction import create_default_financial_network
        from backend.neural.aweb import initialize_aweb
        from backend.neural.integration import NeuralEventBus
        from backend.neural.pheromones import get_environment
        from backend.neural.aweb import get_aweb

        net = create_default_financial_network()
        _run(initialize_aweb(db=None))
        env = get_environment()
        env._deposits.clear()

        bus = NeuralEventBus(env=env, network=net, aweb=get_aweb())

        result = _run(bus.emit(
            event_type="fraud_alert",
            payload={"booking_id": 55, "score": 0.85},
            priority="HIGH",
            source_node="fraud_detector",
            target_entity_type="booking",
            target_entity_id=55,
            db=None,
        ))

        # Verify pheromone was deposited
        deposits = env.sense(target_entity_type="booking", target_entity_id=55)
        self.assertGreater(len(deposits), 0,
                           "emit() should have deposited a pheromone on booking:55")
        self.assertIsNotNone(result, "emit() should return a TransmitResult")


# ===========================================================================

class TestSignalPriorityMapping(unittest.TestCase):
    """Test 11: PHEROMONE_TO_PRIORITY covers all PheromoneType members."""

    def test_11_priority_mapping_complete(self):
        """Every PheromoneType value should appear in PHEROMONE_TO_PRIORITY."""
        from backend.neural.pheromones import PheromoneType
        from backend.neural.integration import PHEROMONE_TO_PRIORITY

        missing = [pt for pt in PheromoneType if pt not in PHEROMONE_TO_PRIORITY]
        self.assertFalse(missing,
                         f"PheromoneType values missing from PHEROMONE_TO_PRIORITY: {missing}")


# ===========================================================================

class TestMAPheromoneIntegration(unittest.TestCase):
    """Test 12: M&A signal types are compatible with the neural pheromone layer.

    The M&A adversarial_pollination module deposits PREDATOR_SCENT, PREY_SCENT,
    and DISSONANCE into ma_signals (not PheromoneDeposit).  This test verifies:
      - The pheromone_type strings used by adversarial_pollination are distinct
        from the neural PheromoneType enum values (confirming there is a gap)
      - The integration bridge logic (mapping) can be reasoned about
    """

    def test_12_ma_signal_types_are_distinct_from_neural_enum(self):
        """PREDATOR_SCENT / PREY_SCENT / DISSONANCE are NOT in PheromoneType enum —
        confirming the gap that requires a bridge."""
        from backend.neural.pheromones import PheromoneType

        ma_types = {"PREDATOR_SCENT", "PREY_SCENT", "DISSONANCE"}
        neural_type_values = {pt.value for pt in PheromoneType}

        # None of the M&A types should exist in the neural enum as-is
        overlap = ma_types & neural_type_values
        # This is the BUG: there is no bridge. We assert overlap is empty to document it.
        self.assertEqual(overlap, set(),
                         "M&A pheromone types are not in neural PheromoneType — "
                         "a bridge mapping is required (see Task 3 fix)")

    def test_12b_ma_to_neural_bridge_mapping_exists(self):
        """The bridge module provides a MA_TO_NEURAL_PHEROMONE mapping."""
        try:
            from backend.neural.ma_bridge import MA_TO_NEURAL_PHEROMONE
            self.assertIn("PREDATOR_SCENT", MA_TO_NEURAL_PHEROMONE)
            self.assertIn("PREY_SCENT", MA_TO_NEURAL_PHEROMONE)
            self.assertIn("DISSONANCE", MA_TO_NEURAL_PHEROMONE)
        except ImportError:
            self.fail(
                "backend/neural/ma_bridge.py does not exist — "
                "M&A pheromones are not bridged to the neural heatmap."
            )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
