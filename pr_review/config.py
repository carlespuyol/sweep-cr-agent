"""Global agent model configuration.

Maps each agent (graph node) to the LLM model it uses.
To change a model, update the value here — no node code needs to change.

All models are accessed via Together.ai using langchain-openai.
See https://docs.together.ai/docs/inference-models for available models.
"""


class AgentName:
    """String constants for all graph node names."""

    PARSE_PR = "parse_pr"
    TRIAGE = "triage"
    FILE_ANALYZER = "file_analyzer"
    ARCH_ANALYSIS = "arch_analysis"
    SECURITY_ANALYSIS = "security_analysis"
    SYNTHESIZE = "synthesize"
    FORMAT_OUTPUT = "format_output"


class Complexity:
    """String constants for PR complexity classifications."""

    SIMPLE = "simple"
    COMPLEX = "complex"


# Default model used as fallback when an agent name is not found in AGENT_MODELS.
DEFAULT_MODEL = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"

# Per-agent model assignments.
# Keys must match the AgentName constants above.
AGENT_MODELS: dict[str, str] = { #TODO: adapt each agent to model that best suits their task
    AgentName.TRIAGE: DEFAULT_MODEL,
    AgentName.FILE_ANALYZER: DEFAULT_MODEL,
    AgentName.ARCH_ANALYSIS: DEFAULT_MODEL,
    AgentName.SECURITY_ANALYSIS: DEFAULT_MODEL,
    AgentName.SYNTHESIZE: DEFAULT_MODEL,
}
