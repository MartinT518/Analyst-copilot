"""Clarifier agent for generating clarifying questions from user requests."""

import json
from typing import Dict, List, Type

import structlog

from ..schemas.agent_schemas import (
    ClarificationQuestion,
    ClarifierInput,
    ClarifierOutput,
)
from ..schemas.common_schemas import AgentType
from .base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class ClarifierAgent(BaseAgent):
    """Agent that analyzes user requests and generates clarifying questions."""

    def __init__(self, llm_service, knowledge_service, audit_service):
        """Initialize the Clarifier agent."""
        super().__init__(
            agent_type=AgentType.CLARIFIER,
            llm_service=llm_service,
            knowledge_service=knowledge_service,
            audit_service=audit_service,
        )
        self.logger = logger.bind(agent="clarifier")

    @property
    def input_schema(self) -> Type[ClarifierInput]:
        """Return the input schema for this agent."""
        return ClarifierInput

    @property
    def output_schema(self) -> Type[ClarifierOutput]:
        """Return the output schema for this agent."""
        return ClarifierOutput

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Clarifier agent."""
        return """You are an expert business analyst specializing in requirement clarification. Your role is to analyze user requests and generate insightful clarifying questions that will help gather complete and precise requirements.

Your responsibilities:
1. Analyze the user's request to identify ambiguities, gaps, and assumptions
2. Generate specific, actionable clarifying questions
3. Categorize questions by type (requirement, constraint, scope, etc.)
4. Prioritize questions by importance
5. Provide context for why each question is needed

Guidelines for generating questions:
- Ask specific, not generic questions
- Focus on business value and user needs
- Identify technical constraints and dependencies
- Clarify scope boundaries and exclusions
- Understand success criteria and acceptance criteria
- Identify stakeholders and their roles
- Understand timeline and resource constraints
- Ask about integration requirements
- Clarify data and security requirements
- Understand compliance and regulatory needs

Question types to consider:
- REQUIREMENT: What specific functionality is needed?
- CONSTRAINT: What limitations or restrictions exist?
- SCOPE: What is included/excluded from this request?
- STAKEHOLDER: Who are the users and decision makers?
- TECHNICAL: What are the technical requirements and constraints?
- BUSINESS: What is the business value and success criteria?
- TIMELINE: What are the deadlines and milestones?
- INTEGRATION: How does this connect with existing systems?
- DATA: What data is involved and how should it be handled?
- SECURITY: What security and compliance requirements exist?

Always respond with valid JSON matching the required schema."""

    def _get_user_prompt(self, input_data: ClarifierInput) -> str:
        """Get the user prompt for the Clarifier agent."""
        prompt = f"""Please analyze the following user request and generate clarifying questions:

USER REQUEST:
{input_data.user_request}

DOMAIN CONTEXT:
{input_data.domain_context or "No specific domain context provided"}

EXISTING REQUIREMENTS:
{chr(10).join(input_data.existing_requirements) if input_data.existing_requirements else "No existing requirements provided"}

ANALYSIS INSTRUCTIONS:
1. Carefully analyze the user request for ambiguities, gaps, and assumptions
2. Generate {self.settings.clarifier_max_questions} high-quality clarifying questions
3. Categorize each question by type
4. Assign importance levels (critical, high, medium, low)
5. Provide context explaining why each question is needed
6. Suggest possible answer options where appropriate
7. Identify key assumptions being made
8. Highlight potential gaps in the request

Respond with a JSON object containing:
- questions: Array of clarification questions with id, question, type, importance, context, and suggested_answers
- analysis_summary: Brief summary of your analysis
- identified_gaps: List of gaps found in the request
- assumptions: List of assumptions you identified

Ensure all questions are specific, actionable, and focused on gathering the information needed to create a complete requirements specification."""

        return prompt

    async def _process_request(self, input_data: ClarifierInput) -> ClarifierOutput:
        """Process the clarification request.

        Args:
            input_data: Validated input data

        Returns:
            Clarifier output with questions and analysis
        """
        self.logger.info("Processing clarification request", request_id=input_data.request_id)

        try:
            # Search knowledge base for relevant context
            knowledge_refs = await self._search_knowledge(query=input_data.user_request, limit=5)

            # Log knowledge access
            await self.audit_service.log_knowledge_access(
                request_id=input_data.request_id,
                query=input_data.user_request,
                results_count=len(knowledge_refs),
                knowledge_references=[str(ref.chunk_id) for ref in knowledge_refs],
                agent_type=self.agent_type,
            )

            # Generate clarifying questions using LLM
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(input_data)

            # Add knowledge context to prompt if available
            if knowledge_refs:
                knowledge_context = "\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n"
                for ref in knowledge_refs:
                    knowledge_context += f"- {ref.excerpt[:200]}...\n"
                user_prompt += knowledge_context

            response = await self._query_llm(
                system_prompt=system_prompt, user_prompt=user_prompt, json_mode=True
            )

            # Parse JSON response
            response_data = self._parse_json_response(response)

            # Validate and create questions
            questions = []
            for q_data in response_data.get("questions", []):
                try:
                    question = ClarificationQuestion(
                        question_id=q_data.get("question_id", f"q_{len(questions)+1}"),
                        question=q_data["question"],
                        question_type=q_data.get("question_type", "requirement"),
                        importance=q_data.get("importance", "medium"),
                        suggested_answers=q_data.get("suggested_answers", []),
                        context=q_data.get("context", ""),
                    )
                    questions.append(question)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse question", error=str(e), question_data=q_data
                    )
                    continue

            # Calculate confidence based on various factors
            confidence_factors = {
                "request_clarity": self._assess_request_clarity(input_data.user_request),
                "knowledge_availability": min(1.0, len(knowledge_refs) / 3.0),
                "questions_generated": min(
                    1.0, len(questions) / self.settings.clarifier_max_questions
                ),
                "domain_context": 1.0 if input_data.domain_context else 0.5,
            }

            confidence = self._calculate_confidence(confidence_factors)

            # Create output
            output = ClarifierOutput(
                agent_type=self.agent_type,
                request_id=input_data.request_id,
                confidence=confidence,
                reasoning=f"Generated {len(questions)} clarifying questions based on analysis of user request and {len(knowledge_refs)} knowledge base references",
                questions=questions,
                analysis_summary=response_data.get(
                    "analysis_summary", "Request analyzed for clarification needs"
                ),
                identified_gaps=response_data.get("identified_gaps", []),
                assumptions=response_data.get("assumptions", []),
                metadata={
                    "knowledge_references_used": len(knowledge_refs),
                    "questions_generated": len(questions),
                    "domain_context_provided": bool(input_data.domain_context),
                    "existing_requirements_count": len(input_data.existing_requirements),
                },
            )

            self.logger.info(
                "Clarification completed",
                request_id=input_data.request_id,
                questions_count=len(questions),
                confidence=confidence,
            )

            return output

        except Exception as e:
            self.logger.error(
                "Clarification failed", request_id=input_data.request_id, error=str(e)
            )
            raise

    def _assess_request_clarity(self, request: str) -> float:
        """Assess the clarity of the user request.

        Args:
            request: User request text

        Returns:
            Clarity score between 0.0 and 1.0
        """
        # Simple heuristic-based assessment
        score = 0.5  # Base score

        # Length factor
        if len(request) > 50:
            score += 0.1
        if len(request) > 200:
            score += 0.1

        # Specificity indicators
        specific_words = [
            "specific",
            "exactly",
            "must",
            "should",
            "will",
            "need",
            "require",
        ]
        specificity_count = sum(1 for word in specific_words if word.lower() in request.lower())
        score += min(0.2, specificity_count * 0.05)

        # Question words (indicate uncertainty)
        question_words = ["what", "how", "when", "where", "why", "which", "who"]
        question_count = sum(1 for word in question_words if word.lower() in request.lower())
        score -= min(0.2, question_count * 0.03)

        # Technical terms (indicate domain knowledge)
        technical_terms = [
            "system",
            "database",
            "api",
            "interface",
            "integration",
            "workflow",
        ]
        tech_count = sum(1 for term in technical_terms if term.lower() in request.lower())
        score += min(0.1, tech_count * 0.02)

        return max(0.0, min(1.0, score))

    async def _generate_follow_up_questions(
        self,
        original_questions: List[ClarificationQuestion],
        user_answers: Dict[str, str],
    ) -> List[ClarificationQuestion]:
        """Generate follow-up questions based on user answers.

        Args:
            original_questions: Original clarification questions
            user_answers: User's answers to the questions

        Returns:
            List of follow-up questions
        """
        # This would be used in an interactive clarification process
        follow_up_prompt = f"""Based on the user's answers to clarification questions, generate relevant follow-up questions:

ORIGINAL QUESTIONS AND ANSWERS:
{json.dumps({q.question_id: {"question": q.question, "answer": user_answers.get(q.question_id, "No answer")} for q in original_questions}, indent=2)}

Generate up to 3 follow-up questions that dive deeper into areas that need more clarification based on the answers provided."""

        try:
            response = await self._query_llm(
                system_prompt=self._get_system_prompt(),
                user_prompt=follow_up_prompt,
                json_mode=True,
            )

            response_data = self._parse_json_response(response)

            follow_ups = []
            for q_data in response_data.get("questions", []):
                try:
                    question = ClarificationQuestion(
                        question_id=f"followup_{len(follow_ups)+1}",
                        question=q_data["question"],
                        question_type=q_data.get("question_type", "follow_up"),
                        importance=q_data.get("importance", "medium"),
                        suggested_answers=q_data.get("suggested_answers", []),
                        context=q_data.get(
                            "context", "Follow-up question based on previous answers"
                        ),
                    )
                    follow_ups.append(question)
                except Exception as e:
                    self.logger.warning("Failed to parse follow-up question", error=str(e))
                    continue

            return follow_ups

        except Exception as e:
            self.logger.error("Failed to generate follow-up questions", error=str(e))
            return []
