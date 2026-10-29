"""Multi-agent investigation (PRD §17)."""

from .orchestrator import InvestigationConfig, InvestigationResult, compose_answer, investigate
from .roles import ClaimSpec, EvidenceBundle, HypothesisSet, ProposedHypothesis
from .runtime import AgentRun, AgentRunner, AgentTurn
from .tools import TOOLS, ScopeError, ToolContext

__all__ = [
    "TOOLS",
    "AgentRun",
    "AgentRunner",
    "AgentTurn",
    "ClaimSpec",
    "EvidenceBundle",
    "HypothesisSet",
    "InvestigationConfig",
    "InvestigationResult",
    "ProposedHypothesis",
    "ScopeError",
    "ToolContext",
    "compose_answer",
    "investigate",
]
