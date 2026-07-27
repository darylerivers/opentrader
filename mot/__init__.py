"""MoT — Model of Traders coordinator."""
from .coordinator import MoTCoordinator, MoTState, CARTOGRAPHER_NAMES, REVIEW_HOURS
from .scoring import AgentScorer, AgentRecord
from .reflection import ReflectionLog
from .agents import DebateEngine, DebateResult, AdirDebateEngine
from .adapter_registry import AdapterRegistry, AdapterRecord
from .finetuned_agent import FineTunedAgent
from .pool import ModelPool
from .coach import TrainingCoach
from .ensemble import Ensemble
from .lifecycle import ATDL, Phase, PHASE_LABELS

__all__ = [
    "MoTCoordinator", "MoTState", "CARTOGRAPHER_NAMES", "REVIEW_HOURS",
    "AgentScorer", "AgentRecord",
    "ReflectionLog",
    "DebateEngine", "DebateResult", "AdirDebateEngine",
    "AdapterRegistry", "AdapterRecord",
    "FineTunedAgent",
    "ModelPool",
    "TrainingCoach",
    "Ensemble",
    "ATDL", "Phase", "PHASE_LABELS",
]
