"""
Langfuse Agent Prompts & Observability Instruction Catalog

This module contains standardized prompts used to configure, instrument,
evaluate, and manage Langfuse skills and tracing workflows across EchoStack.
"""

# Official prompt used to install and configure the Langfuse AI Skill in agentic workflows
LANGFUSE_SKILL_INSTALL_PROMPT = (
    "Install the Langfuse AI skill from github.com/langfuse/skills and use it "
    "to add tracing to this application with Langfuse following best practices."
)

# Standard prompt for auditing existing application tracing against Langfuse best practices
LANGFUSE_TRACING_AUDIT_PROMPT = (
    "Audit the Langfuse tracing setup in this repository against best practices. "
    "Ensure observation types (agent, generation, retriever, span), user_id, session_id, "
    "tags, and input/output filtering are properly configured and context is flushed cleanly."
)

# Prompt for prompt management migration to Langfuse
LANGFUSE_PROMPT_MIGRATION_PROMPT = (
    "Migrate application prompts into Langfuse Prompt Management. Ensure versioning, "
    "variable compilation, and fallback defaults are configured according to Langfuse guidelines."
)

# Catalog dictionary of all Langfuse prompts
LANGFUSE_PROMPTS = {
    "skill_install": LANGFUSE_SKILL_INSTALL_PROMPT,
    "tracing_audit": LANGFUSE_TRACING_AUDIT_PROMPT,
    "prompt_migration": LANGFUSE_PROMPT_MIGRATION_PROMPT,
}
