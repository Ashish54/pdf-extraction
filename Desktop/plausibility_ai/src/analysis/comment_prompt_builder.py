from typing import Tuple, List
from ..models import BreachRecord, DocumentChunk

SYSTEM_PROMPT = """You are a senior model validation expert at a financial institution.
You are reviewing plausibility test results for risk models.

Your task: For each breached validation rule, provide an expert assessment.

You MUST respond in valid JSON with this exact structure:
{
    "severity": "Critical" | "Major" | "Moderate" | "Minor" | "Informational",
    "comment": "A concise, expert-style explanation (2-4 sentences). Write as a model validation SME would.",
    "root_cause": "The most likely technical cause of the breach (1-2 sentences).",
    "evidence": [
        {
            "source": "documentation",
            "reference": "Human-readable reference",
            "excerpt": "Relevant quoted text from the source"
        }
    ],
    "confidence": "high" | "medium" | "low",
    "uncertainty_notes": "What you are unsure about, if anything. Empty string if confident.",
    "expected_behavior": true | false,
    "requires_investigation": true | false
}

SEVERITY GUIDELINES:
- Critical: Model produces results opposite to expected direction, or fundamental logic error suspected.
- Major: Significant deviation from expectations that may indicate a material issue.
- Moderate: Threshold exceeded but model behavior is directionally correct. Review recommended.
- Minor: Small exceedance, likely within acceptable tolerance. Low risk.
- Informational: Technical flag with no material concern.

IMPORTANT RULES:
1. Always cite specific evidence from the provided context.
2. If context does not contain enough info, set confidence to "low" and explain in uncertainty_notes.
3. Do NOT fabricate references. Only cite text that appears in the CONTEXT section.
4. Consider scenario shocks - extreme shocks may explain large but expected deviations.
5. Be concise. Reviewers are experts.
"""

class PromptBuilder:
    def build(self, breach: BreachRecord, context_chunks: List[DocumentChunk]) -> Tuple[str, str]:
        """
        Build system + user prompts for a single breach analysis.
        Returns (system_prompt, user_prompt).
        """
        user_prompt = self._build_user_prompt(breach, context_chunks)
        return (SYSTEM_PROMPT, user_prompt)
        
    def _build_user_prompt(self, breach: BreachRecord, context_chunks: List[DocumentChunk]) -> str:
        sections = []
        
        if context_chunks:
            sections.append("=== RETRIEVED CONTEXT ===")
            for i, chunk in enumerate(context_chunks, 1):
                sections.append(f"--- Source [{i}]: {chunk.citation_string()} ---")
                sections.append(chunk.text)
                sections.append("")
                
        sections.append("=== BREACH TO ANALYZE ===")
        sections.append(f"Sheet/Category: {breach.sheet_name}")
        sections.append(f"Model: {breach.model_name}")
        sections.append(f"Rule: {breach.rule_name}")
        sections.append(f"Mnemonic: {breach.mnemonic}")
        sections.append(f"Breach Type: {breach.breach_type}")
        sections.append(f"Observed Value: {breach.breach_value}")
        sections.append(f"Threshold: {breach.threshold_value}")
        
        if breach.scenario_shocks:
            sections.append("Scenario Shocks:")
            for k, v in breach.scenario_shocks.items():
                sections.append(f"  - {k}: {v}")
                
        if breach.additional_columns:
            sections.append("Additional Data:")
            for k, v in breach.additional_columns.items():
                sections.append(f"  - {k}: {v}")
                
        sections.append("\nAnalyze this breach and respond in JSON format.")
        
        return "\n".join(sections)
