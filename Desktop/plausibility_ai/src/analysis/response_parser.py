import json
import logging
from pydantic import BaseModel, ValidationError
from ..models import AnalysisResult, BreachRecord, Severity, Confidence, Evidence, SimpleAnalysisResult

logger = logging.getLogger(__name__)

class LLMResponse(BaseModel):
    severity: Severity
    comment: str
    root_cause: str
    evidence: list[Evidence]
    confidence: Confidence
    uncertainty_notes: str
    expected_behavior: bool
    requires_investigation: bool

class SimpleLLMResponse(BaseModel):
    severity: Severity
    comment: str


class ResponseParser:
    def parse(self, raw_response: str, breach: BreachRecord) -> AnalysisResult:
        """
        Parse and validate the JSON response from the LLM.
        """
        if raw_response is None:
            logger.error("LLM returned None response")
            return self._error_result(breach, "", "LLM returned None response")
        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}\nRaw: {raw_response}")
            return self._error_result(breach, raw_response, f"JSON parse error: {e}")
            
        try:
            # Pydantic validation
            validated = LLMResponse(**data)
            
            return AnalysisResult(
                breach=breach,
                severity=validated.severity,
                comment=validated.comment,
                root_cause=validated.root_cause,
                evidence=validated.evidence,
                confidence=validated.confidence,
                uncertainty_notes=validated.uncertainty_notes,
                raw_llm_response=raw_response,
                expected_behavior=validated.expected_behavior,
                requires_investigation=validated.requires_investigation
            )
            
        except ValidationError as e:
            logger.error(f"LLM response failed schema validation: {e}\nRaw: {raw_response}")
            return self._error_result(breach, raw_response, f"Validation error: {e}")
            
    def _error_result(self, breach: BreachRecord, raw: str, error_msg: str) -> AnalysisResult:
        return AnalysisResult(
            breach=breach,
            severity=Severity.INFORMATIONAL,
            comment=f"AI Analysis Failed: {error_msg}",
            root_cause="Parsing or Validation Error",
            evidence=[],
            confidence=Confidence.LOW,
            uncertainty_notes=error_msg,
            raw_llm_response=raw,
            expected_behavior=False,
            requires_investigation=True
        )
    def parse_simple(self, raw_response: str, breach: BreachRecord) -> SimpleAnalysisResult:
        """
        Parse and validate the JSON response from the LLM for simple analysis.
        """
        if raw_response is None:
            logger.error("LLM returned None response")
            return self._error_result_simple(breach, "", "LLM returned None response")
        if not raw_response or not raw_response.strip():
            logger.error("LLM returned empty response")
            return self._error_result_simple(breach, "", "LLM returned empty response")
        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            if "unterminated string" in str(e) or "Expecting value" in str(e):
                logger.error(f"LLM response appears truncated (likely hit token limit). " 
                f"Error: {e} \n Raw response length: {len(raw_response)} chars"
                f"First 200 chars: {raw_response[:200]}"
                f"Last 200 chars: {raw_response[-200:]}")
                if "severity" in clean_text and "Minor" in clean_text:
                    logger.info("Attempting to use partial response with Minor Severity")
                    return SimpleAnalysisResult(
                        breach=breach,
                        severity=Severity.INFORMATIONAL,
                        comment=f"AI Analysis Failed: {e}\nRaw: {raw_response}",
                        raw_llm_response=raw_response
                    )
            logger.error(f"Failed to parse LLM response as JSON: {e}\nRaw: {raw_response}")
            return self._error_result_simple(breach, raw_response, f"JSON parse error: {e}")
        try:
            # Pydantic validation
            validated = SimpleLLMResponse(**data)
            if len(validated.comment) > 500:
                logger.warning(
                    f" Comment is very long({len(validated.comment)} chars)"
                    f" Consider making prompts more concise"
                )
            
            return SimpleAnalysisResult(
                breach=breach,
                severity=validated.severity,
                comment=validated.comment,
                raw_llm_response=raw_response,
            )
        except ValidationError as e:
            logger.error(f"LLM response failed schema validation: {e}\nRaw: {raw_response}")
            return self._error_result_simple(breach, raw_response, f"Validation error: {e}")

    def _error_result_simple(self, breach: BreachRecord, raw: str, error_msg: str) -> SimpleAnalysisResult:
        return SimpleAnalysisResult(
            breach=breach,
            severity=Severity.INFORMATIONAL,
            comment=f"AI Analysis Failed: {error_msg}",
            raw_llm_response=raw
        )
        