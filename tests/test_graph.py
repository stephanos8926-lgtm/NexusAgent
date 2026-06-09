"""Tests for the LangGraph research workflow."""

from nexusagent.graph import create_research_graph, route_after_execute


class TestGraphRouting:
    """Test the conditional routing logic."""

    def test_route_to_execute_when_steps_remaining(self):
        state = {
            "plan": {"steps": ["step1", "step2", "step3"]},
            "current_step_index": 1,
        }
        assert route_after_execute(state) == "execute"

    def test_route_to_synthesize_when_steps_exhausted(self):
        state = {
            "plan": {"steps": ["step1", "step2"]},
            "current_step_index": 2,
        }
        assert route_after_execute(state) == "synthesize"

    def test_route_to_synthesize_when_no_steps(self):
        state = {
            "plan": {"steps": []},
            "current_step_index": 0,
        }
        assert route_after_execute(state) == "synthesize"

    def test_route_to_execute_even_with_error(self):
        """Resilience: continue to next step even if current one errored."""
        state = {
            "plan": {"steps": ["step1", "step2"]},
            "current_step_index": 0,
            "error": "Step failed",
        }
        assert route_after_execute(state) == "execute"


class TestGraphConstruction:
    """Test graph compilation and structure."""

    def test_create_research_graph_compiles(self):
        """Graph should compile without errors."""
        graph = create_research_graph()
        assert graph is not None

    def test_create_research_graph_with_db(self, tmp_path):
        """Graph should compile with a real DB path."""
        db_path = str(tmp_path / "test_checkpoints.db")
        graph = create_research_graph(db_path=db_path)
        assert graph is not None
