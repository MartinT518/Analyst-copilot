"""Verifier agent for validating outputs against knowledge base and constraints."""

from typing import List, Type

import structlog

from ..schemas.agent_schemas import (
    ConsistencyCheck,
    VerificationCheck,
    VerifierInput,
    VerifierOutput,
)
from ..schemas.common_schemas import AgentType, ValidationResult
from .base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class VerifierAgent(BaseAgent):
    """Agent that verifies and validates outputs from other agents."""

    def __init__(self, llm_service, knowledge_service, audit_service):
        """Initialize the Verifier agent."""
        super().__init__(
            agent_type=AgentType.VERIFIER,
            llm_service=llm_service,
            knowledge_service=knowledge_service,
            audit_service=audit_service,
        )
        self.logger = logger.bind(agent="verifier")

    @property
    def input_schema(self) -> Type[VerifierInput]:
        """Return the input schema for this agent."""
        return VerifierInput

    @property
    def output_schema(self) -> Type[VerifierOutput]:
        """Return the output schema for this agent."""
        return VerifierOutput

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Verifier agent."""
        return """You are an expert quality assurance analyst and technical reviewer specializing in validating AI-generated outputs. Your role is to verify the accuracy, consistency, and completeness of agent outputs against knowledge base content, code repositories, and database schemas.

Your responsibilities:
1. Verify outputs against knowledge base content for accuracy
2. Check consistency between different agent outputs
3. Validate against code repositories and database schemas
4. Identify potential issues, gaps, or inconsistencies
5. Provide recommendations for improvement
6. Assign confidence scores and approval status

Verification Categories:
- ACCURACY: Information matches knowledge base and factual sources
- CONSISTENCY: Outputs align with each other and don't contradict
- COMPLETENESS: All required elements are present and detailed
- FEASIBILITY: Proposed solutions are technically implementable
- COMPLIANCE: Outputs meet security, regulatory, and business requirements
- QUALITY: Content is well-structured, clear, and professional

Consistency Checks:
- Requirements alignment between clarifier and synthesizer outputs
- Implementation feasibility between synthesizer and taskmaster outputs
- Technical accuracy against code and schema context
- Business value alignment across all outputs

Validation Criteria:
- Knowledge base references are accurate and relevant
- Technical specifications are implementable
- Business requirements are clearly defined
- Success criteria are measurable
- Dependencies are properly identified
- Risks are adequately addressed

Confidence Levels:
- VERY_HIGH (0.9-1.0): Fully verified, no issues found
- HIGH (0.75-0.89): Minor issues that don't affect core validity
- MEDIUM (0.5-0.74): Some concerns that should be addressed
- LOW (0.25-0.49): Significant issues requiring revision
- VERY_LOW (0.0-0.24): Major problems, output needs rework

Approval Status:
- APPROVED: Output meets all quality standards
- NEEDS_REVIEW: Minor issues, human review recommended
- REJECTED: Significant issues, requires agent rework

Always respond with valid JSON matching the required schema."""

    def _get_user_prompt(self, input_data: VerifierInput) -> str:
        """Get the user prompt for the Verifier agent."""
        prompt = "Please verify and validate the following agent outputs:\n\n"

        # Add clarifier output if present
        if input_data.clarifier_output:
            prompt += f"CLARIFIER OUTPUT:\n"
            prompt += f"Questions Generated: {len(input_data.clarifier_output.questions)}\n"
            prompt += f"Analysis Summary: {input_data.clarifier_output.analysis_summary}\n"
            prompt += f"Identified Gaps: {', '.join(input_data.clarifier_output.identified_gaps)}\n"
            prompt += f"Confidence: {input_data.clarifier_output.confidence}\n\n"

        # Add synthesizer output if present
        if input_data.synthesizer_output:
            prompt += f"SYNTHESIZER OUTPUT:\n"
            prompt += f"AS-IS Document: {input_data.synthesizer_output.as_is_document.title}\n"
            prompt += f"TO-BE Document: {input_data.synthesizer_output.to_be_document.title}\n"
            prompt += (
                f"Gap Analysis: {len(input_data.synthesizer_output.gap_analysis)} gaps identified\n"
            )
            prompt += f"Implementation Approach: {input_data.synthesizer_output.implementation_approach[:200]}...\n"
            prompt += f"Confidence: {input_data.synthesizer_output.confidence}\n\n"

        # Add taskmaster output if present
        if input_data.taskmaster_output:
            prompt += f"TASKMASTER OUTPUT:\n"
            prompt += f"Tasks Generated: {len(input_data.taskmaster_output.tasks)}\n"
            prompt += f"Implementation Phases: {', '.join(input_data.taskmaster_output.implementation_phases)}\n"
            prompt += f"Timeline Estimate: {input_data.taskmaster_output.timeline_estimate}\n"
            prompt += f"Confidence: {input_data.taskmaster_output.confidence}\n\n"

        # Add knowledge base context
        if input_data.knowledge_base_context:
            prompt += f"KNOWLEDGE BASE CONTEXT:\n"
            for ref in input_data.knowledge_base_context[:5]:  # Limit for prompt size
                prompt += f"- {ref.source_type} (Score: {ref.similarity_score:.2f}): {ref.excerpt[:100]}...\n"
            prompt += "\n"

        # Add code context if available
        if input_data.code_context:
            prompt += f"CODE CONTEXT:\n"
            for code_ref in input_data.code_context[:3]:  # Limit for prompt size
                prompt += f"- {code_ref.get('file_path', 'Unknown')}: {code_ref.get('description', 'No description')}\n"
            prompt += "\n"

        # Add schema context if available
        if input_data.schema_context:
            prompt += f"DATABASE SCHEMA CONTEXT:\n"
            for schema_ref in input_data.schema_context[:3]:  # Limit for prompt size
                prompt += f"- {schema_ref.get('table_name', 'Unknown')}: {schema_ref.get('description', 'No description')}\n"
            prompt += "\n"

        prompt += f"""VERIFICATION INSTRUCTIONS:
1. Perform comprehensive verification checks on each output
2. Check consistency between different agent outputs
3. Validate against knowledge base, code, and schema context
4. Identify any issues, gaps, or inconsistencies
5. Provide specific recommendations for improvement
6. Assign confidence scores based on verification results
7. Determine overall approval status

For each verification check, include:
- Check type and description
- Verification result (pass/fail)
- Confidence level in the verification
- Detailed explanation of findings
- Supporting references from knowledge base

For consistency checks, compare:
- Clarifier questions vs synthesizer requirements
- Synthesizer gaps vs taskmaster tasks
- Technical feasibility across all outputs
- Business value alignment

Minimum confidence threshold: {self.settings.verifier_confidence_threshold}

Respond with a JSON object containing:
- verification_checks: Array of individual verification results
- consistency_checks: Array of consistency check results
- overall_validation: Overall validation result with score
- recommendations: List of improvement recommendations
- flagged_issues: Critical issues that need attention
- approval_status: Final approval status (approved/needs_review/rejected)"""

        return prompt

    async def _process_request(self, input_data: VerifierInput) -> VerifierOutput:
        """Process the verification request.

        Args:
            input_data: Validated input data

        Returns:
            Verifier output with validation results
        """
        self.logger.info("Processing verification request", request_id=input_data.request_id)

        try:
            # Perform additional knowledge searches for verification
            verification_queries = self._extract_verification_queries(input_data)
            verification_knowledge = []

            for query in verification_queries:
                refs = await self._search_knowledge(query=query, limit=3)
                verification_knowledge.extend(refs)

            # Log knowledge access
            await self.audit_service.log_knowledge_access(
                request_id=input_data.request_id,
                query=" | ".join(verification_queries),
                results_count=len(verification_knowledge),
                knowledge_references=[str(ref.chunk_id) for ref in verification_knowledge],
                agent_type=self.agent_type,
            )

            # Generate verification using LLM
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(input_data)

            # Add verification knowledge context
            if verification_knowledge:
                verification_context = "\n\nADDITIONAL VERIFICATION CONTEXT:\n"
                for ref in verification_knowledge:
                    verification_context += f"- {ref.source_type}: {ref.excerpt[:150]}...\n"
                user_prompt += verification_context

            response = await self._query_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
                max_tokens=6000,
            )

            # Parse JSON response
            response_data = self._parse_json_response(response)

            # Create verification checks
            verification_checks = []
            for check_data in response_data.get("verification_checks", []):
                try:
                    # Find supporting references
                    references = []
                    ref_ids = check_data.get("reference_ids", [])
                    for ref_id in ref_ids:
                        matching_refs = [
                            ref
                            for ref in input_data.knowledge_base_context + verification_knowledge
                            if str(ref.chunk_id) == ref_id
                        ]
                        references.extend(matching_refs)

                    check = VerificationCheck(
                        check_id=check_data.get(
                            "check_id", f"check_{len(verification_checks) + 1}"
                        ),
                        check_type=check_data.get("check_type", "general"),
                        description=check_data.get("description", ""),
                        result=check_data.get("result", False),
                        confidence=check_data.get("confidence", 0.5),
                        details=check_data.get("details", ""),
                        references=references,
                    )
                    verification_checks.append(check)

                except Exception as e:
                    self.logger.warning(
                        "Failed to parse verification check", error=str(e), check_data=check_data
                    )
                    continue

            # Create consistency checks
            consistency_checks = []
            for consistency_data in response_data.get("consistency_checks", []):
                try:
                    check = ConsistencyCheck(
                        source_a=consistency_data.get("source_a", ""),
                        source_b=consistency_data.get("source_b", ""),
                        consistency_score=consistency_data.get("consistency_score", 0.5),
                        inconsistencies=consistency_data.get("inconsistencies", []),
                        recommendations=consistency_data.get("recommendations", []),
                    )
                    consistency_checks.append(check)

                except Exception as e:
                    self.logger.warning(
                        "Failed to parse consistency check",
                        error=str(e),
                        consistency_data=consistency_data,
                    )
                    continue

            # Create overall validation result
            overall_validation = ValidationResult(
                is_valid=response_data.get("overall_validation", {}).get("is_valid", False),
                errors=response_data.get("overall_validation", {}).get("errors", []),
                warnings=response_data.get("overall_validation", {}).get("warnings", []),
                score=response_data.get("overall_validation", {}).get("score", 0.5),
            )

            # Calculate confidence based on verification results
            confidence_factors = {
                "verification_pass_rate": self._calculate_pass_rate(verification_checks),
                "consistency_score": self._calculate_avg_consistency(consistency_checks),
                "knowledge_coverage": min(1.0, len(verification_knowledge) / 5.0),
                "overall_validation_score": overall_validation.score,
            }

            confidence = self._calculate_confidence(confidence_factors)

            # Determine approval status
            approval_status = self._determine_approval_status(
                overall_validation.score, verification_checks, consistency_checks
            )

            # Create output
            output = VerifierOutput(
                agent_type=self.agent_type,
                request_id=input_data.request_id,
                confidence=confidence,
                reasoning=f"Performed {len(verification_checks)} verification checks and {len(consistency_checks)} consistency checks",
                verification_checks=verification_checks,
                consistency_checks=consistency_checks,
                overall_validation=overall_validation,
                recommendations=response_data.get("recommendations", []),
                flagged_issues=response_data.get("flagged_issues", []),
                approval_status=approval_status,
                metadata={
                    "verification_checks_count": len(verification_checks),
                    "consistency_checks_count": len(consistency_checks),
                    "verification_pass_rate": self._calculate_pass_rate(verification_checks),
                    "avg_consistency_score": self._calculate_avg_consistency(consistency_checks),
                    "knowledge_references_verified": len(verification_knowledge),
                },
            )

            self.logger.info(
                "Verification completed",
                request_id=input_data.request_id,
                approval_status=approval_status,
                confidence=confidence,
                validation_score=overall_validation.score,
            )

            return output

        except Exception as e:
            self.logger.error("Verification failed", request_id=input_data.request_id, error=str(e))
            raise

    def _extract_verification_queries(self, input_data: VerifierInput) -> List[str]:
        """Extract queries for additional verification knowledge.

        Args:
            input_data: Verifier input data

        Returns:
            List of verification queries
        """
        queries = []

        # Extract from clarifier output
        if input_data.clarifier_output:
            for gap in input_data.clarifier_output.identified_gaps[:2]:
                queries.append(gap)

        # Extract from synthesizer output
        if input_data.synthesizer_output:
            for gap in input_data.synthesizer_output.gap_analysis[:2]:
                queries.append(gap.gap_description)

        # Extract from taskmaster output
        if input_data.taskmaster_output:
            for task in input_data.taskmaster_output.tasks[:2]:
                queries.append(task.title)

        return queries[:5]  # Limit to 5 queries

    def _calculate_pass_rate(self, verification_checks: List[VerificationCheck]) -> float:
        """Calculate the pass rate of verification checks.

        Args:
            verification_checks: List of verification checks

        Returns:
            Pass rate between 0.0 and 1.0
        """
        if not verification_checks:
            return 0.0

        passed = sum(1 for check in verification_checks if check.result)
        return passed / len(verification_checks)

    def _calculate_avg_consistency(self, consistency_checks: List[ConsistencyCheck]) -> float:
        """Calculate average consistency score.

        Args:
            consistency_checks: List of consistency checks

        Returns:
            Average consistency score
        """
        if not consistency_checks:
            return 1.0  # No inconsistencies found

        total_score = sum(check.consistency_score for check in consistency_checks)
        return total_score / len(consistency_checks)

    def _determine_approval_status(
        self,
        validation_score: float,
        verification_checks: List[VerificationCheck],
        consistency_checks: List[ConsistencyCheck],
    ) -> str:
        """Determine approval status based on verification results.

        Args:
            validation_score: Overall validation score
            verification_checks: Verification check results
            consistency_checks: Consistency check results

        Returns:
            Approval status string
        """
        # Check for critical failures
        critical_failures = [
            check
            for check in verification_checks
            if not check.result and check.check_type in ["accuracy", "feasibility", "compliance"]
        ]

        if critical_failures:
            return "rejected"

        # Check validation score
        if validation_score >= 0.8:
            return "approved"
        elif validation_score >= 0.6:
            return "needs_review"
        else:
            return "rejected"
