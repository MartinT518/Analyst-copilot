"""Synthesizer agent for producing AS-IS and TO-BE documentation."""

import json
from typing import Any, Dict, Type

import structlog

from ..schemas.agent_schemas import (
    AsIsDocument,
    DocumentSection,
    GapAnalysis,
    SynthesizerInput,
    SynthesizerOutput,
    ToBeDocument,
)
from ..schemas.common_schemas import AgentType
from .base_agent import BaseAgent

logger = structlog.get_logger(__name__)


class SynthesizerAgent(BaseAgent):
    """Agent that synthesizes AS-IS and TO-BE documentation from requirements."""

    def __init__(self, llm_service, knowledge_service, audit_service):
        """Initialize the Synthesizer agent."""
        super().__init__(
            agent_type=AgentType.SYNTHESIZER,
            llm_service=llm_service,
            knowledge_service=knowledge_service,
            audit_service=audit_service,
        )
        self.logger = logger.bind(agent="synthesizer")

    @property
    def input_schema(self) -> Type[SynthesizerInput]:
        """Return the input schema for this agent."""
        return SynthesizerInput

    @property
    def output_schema(self) -> Type[SynthesizerOutput]:
        """Return the output schema for this agent."""
        return SynthesizerOutput

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Synthesizer agent."""
        return """You are an expert business analyst and technical writer specializing in creating comprehensive AS-IS and TO-BE documentation. Your role is to synthesize clarified requirements into structured documentation that clearly describes the current state, desired future state, and the gaps between them.

Your responsibilities:
1. Create detailed AS-IS documentation describing the current state
2. Create comprehensive TO-BE documentation describing the desired future state
3. Perform gap analysis identifying differences and required changes
4. Provide implementation recommendations and risk assessments

AS-IS Documentation Guidelines:
- Describe current processes, systems, and workflows
- Identify existing pain points and limitations
- Document current constraints and dependencies
- Include stakeholder roles and responsibilities
- Describe current data flows and integrations
- Highlight inefficiencies and bottlenecks

TO-BE Documentation Guidelines:
- Describe the desired future state in detail
- Define new processes and improved workflows
- Specify system requirements and capabilities
- Include success criteria and measurable outcomes
- Define new stakeholder roles and responsibilities
- Describe improved data flows and integrations
- Highlight expected benefits and value

Gap Analysis Guidelines:
- Identify specific differences between AS-IS and TO-BE
- Categorize gaps by type (process, technology, people, data)
- Assess impact and effort for each gap
- Prioritize gaps based on business value and complexity
- Provide recommendations for addressing each gap

Document Structure:
- Executive Summary
- Current State Analysis (AS-IS)
- Future State Vision (TO-BE)
- Gap Analysis
- Implementation Recommendations
- Risk Assessment
- Success Criteria

Always respond with valid JSON matching the required schema."""

    def _get_user_prompt(self, input_data: SynthesizerInput) -> str:
        """Get the user prompt for the Synthesizer agent."""
        # Format clarified requirements
        requirements_text = json.dumps(input_data.clarified_requirements, indent=2)

        # Format knowledge context
        knowledge_context = ""
        if input_data.knowledge_context:
            knowledge_context = "\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n"
            for ref in input_data.knowledge_context:
                knowledge_context += (
                    f"- Source: {ref.source_type} (Score: {ref.similarity_score:.2f})\n"
                )
                knowledge_context += f"  Content: {ref.excerpt}\n\n"

        scope_text = (
            f"\n\nSCOPE BOUNDARIES:\n{input_data.scope_boundaries}"
            if input_data.scope_boundaries
            else ""
        )

        prompt = f"""Please create comprehensive AS-IS and TO-BE documentation based on the following clarified requirements:

CLARIFIED REQUIREMENTS:
{requirements_text}

{knowledge_context}

{scope_text}

SYNTHESIS INSTRUCTIONS:
1. Create detailed AS-IS documentation describing the current state
2. Create comprehensive TO-BE documentation describing the desired future state
3. Perform thorough gap analysis between current and future states
4. Provide implementation recommendations and risk assessment

For AS-IS Documentation:
- Analyze the current state based on the requirements and knowledge context
- Identify existing processes, systems, and workflows
- Document current pain points and limitations
- Include stakeholder analysis and current responsibilities
- Describe current data flows and system integrations

For TO-BE Documentation:
- Define the desired future state based on requirements
- Describe new or improved processes and workflows
- Specify system capabilities and technical requirements
- Define success criteria and measurable outcomes
- Include stakeholder roles in the future state
- Describe improved data flows and integrations

For Gap Analysis:
- Identify specific gaps between AS-IS and TO-BE states
- Categorize gaps by type and assess impact/effort
- Prioritize gaps based on business value and complexity
- Provide specific recommendations for addressing each gap

Create {self.settings.synthesizer_max_sections} sections maximum for each document to ensure comprehensive but focused documentation.

Respond with a JSON object containing:
- as_is_document: Complete AS-IS documentation with sections
- to_be_document: Complete TO-BE documentation with sections
- gap_analysis: Array of identified gaps with analysis
- implementation_approach: Recommended approach for implementation
- risks_and_mitigation: List of risks and mitigation strategies"""

        return prompt

    async def _process_request(self, input_data: SynthesizerInput) -> SynthesizerOutput:
        """Process the synthesis request.

        Args:
            input_data: Validated input data

        Returns:
            Synthesizer output with AS-IS/TO-BE docs and gap analysis
        """
        self.logger.info("Processing synthesis request", request_id=input_data.request_id)

        try:
            # Search for additional relevant knowledge
            search_query = self._extract_search_query(input_data.clarified_requirements)
            additional_knowledge = await self._search_knowledge(query=search_query, limit=8)

            # Combine with provided knowledge context
            all_knowledge = input_data.knowledge_context + additional_knowledge

            # Log knowledge access
            await self.audit_service.log_knowledge_access(
                request_id=input_data.request_id,
                query=search_query,
                results_count=len(additional_knowledge),
                knowledge_references=[str(ref.chunk_id) for ref in additional_knowledge],
                agent_type=self.agent_type,
            )

            # Update input with additional knowledge
            enhanced_input = SynthesizerInput(
                request_id=input_data.request_id,
                user_id=input_data.user_id,
                context=input_data.context,
                metadata=input_data.metadata,
                clarified_requirements=input_data.clarified_requirements,
                knowledge_context=all_knowledge,
                scope_boundaries=input_data.scope_boundaries,
            )

            # Generate documentation using LLM
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(enhanced_input)

            response = await self._query_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
                max_tokens=6000,  # Larger response for comprehensive docs
            )

            # Parse JSON response
            response_data = self._parse_json_response(response)

            # Create AS-IS document
            as_is_doc = self._create_document(
                response_data.get("as_is_document", {}), "AS-IS State Analysis"
            )

            # Create TO-BE document
            to_be_doc = self._create_document(
                response_data.get("to_be_document", {}), "TO-BE State Vision"
            )

            # Create gap analysis
            gap_analysis = []
            for gap_data in response_data.get("gap_analysis", []):
                try:
                    gap = GapAnalysis(
                        gap_id=gap_data.get("gap_id", f"gap_{len(gap_analysis)+1}"),
                        gap_description=gap_data.get("gap_description", ""),
                        impact=gap_data.get("impact", "medium"),
                        effort=gap_data.get("effort", "medium"),
                        priority=gap_data.get("priority", "medium"),
                        recommendations=gap_data.get("recommendations", []),
                    )
                    gap_analysis.append(gap)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse gap analysis", error=str(e), gap_data=gap_data
                    )
                    continue

            # Calculate confidence based on various factors
            confidence_factors = {
                "requirements_completeness": self._assess_requirements_completeness(
                    input_data.clarified_requirements
                ),
                "knowledge_availability": min(1.0, len(all_knowledge) / 5.0),
                "scope_clarity": 1.0 if input_data.scope_boundaries else 0.7,
                "documentation_quality": self._assess_documentation_quality(as_is_doc, to_be_doc),
                "gap_analysis_depth": min(1.0, len(gap_analysis) / 5.0),
            }

            confidence = self._calculate_confidence(confidence_factors)

            # Create output
            output = SynthesizerOutput(
                agent_type=self.agent_type,
                request_id=input_data.request_id,
                confidence=confidence,
                reasoning=f"Synthesized AS-IS and TO-BE documentation with {len(gap_analysis)} gaps identified, using {len(all_knowledge)} knowledge references",
                as_is_document=as_is_doc,
                to_be_document=to_be_doc,
                gap_analysis=gap_analysis,
                implementation_approach=response_data.get(
                    "implementation_approach", "Phased implementation approach recommended"
                ),
                risks_and_mitigation=response_data.get("risks_and_mitigation", []),
                metadata={
                    "knowledge_references_used": len(all_knowledge),
                    "gaps_identified": len(gap_analysis),
                    "as_is_sections": len(as_is_doc.sections),
                    "to_be_sections": len(to_be_doc.sections),
                    "scope_defined": bool(input_data.scope_boundaries),
                },
            )

            self.logger.info(
                "Synthesis completed",
                request_id=input_data.request_id,
                gaps_count=len(gap_analysis),
                confidence=confidence,
            )

            return output

        except Exception as e:
            self.logger.error("Synthesis failed", request_id=input_data.request_id, error=str(e))
            raise

    def _extract_search_query(self, requirements: Dict[str, Any]) -> str:
        """Extract search query from clarified requirements.

        Args:
            requirements: Clarified requirements data

        Returns:
            Search query string
        """
        # Extract key terms from requirements for knowledge search
        query_parts = []

        # Look for common requirement fields
        if isinstance(requirements, dict):
            for key, value in requirements.items():
                if isinstance(value, str) and len(value) > 10:
                    # Extract first few words as potential search terms
                    words = value.split()[:5]
                    query_parts.extend(words)
                elif isinstance(value, list):
                    for item in value[:3]:  # Limit to first 3 items
                        if isinstance(item, str):
                            words = item.split()[:3]
                            query_parts.extend(words)

        # Clean and join query parts
        clean_parts = [part.strip().lower() for part in query_parts if len(part.strip()) > 2]
        return " ".join(clean_parts[:10])  # Limit query length

    def _create_document(self, doc_data: Dict[str, Any], default_title: str) -> AsIsDocument:
        """Create a document from response data.

        Args:
            doc_data: Document data from LLM response
            default_title: Default title if not provided

        Returns:
            Document object (AsIsDocument or ToBeDocument)
        """
        # Create sections
        sections = []
        for i, section_data in enumerate(doc_data.get("sections", [])):
            try:
                section = DocumentSection(
                    section_id=section_data.get("section_id", f"section_{i+1}"),
                    title=section_data.get("title", f"Section {i+1}"),
                    content=section_data.get("content", ""),
                    section_type=section_data.get("section_type", "general"),
                    order=section_data.get("order", i + 1),
                    subsections=[],  # Simplified for now
                )
                sections.append(section)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse document section", error=str(e), section_data=section_data
                )
                continue

        # Determine document type and create appropriate object
        if "as_is" in default_title.lower() or "current" in default_title.lower():
            return AsIsDocument(
                title=doc_data.get("title", default_title),
                executive_summary=doc_data.get(
                    "executive_summary", "Executive summary not provided"
                ),
                sections=sections,
                current_state_analysis=doc_data.get(
                    "current_state_analysis", "Current state analysis not provided"
                ),
                pain_points=doc_data.get("pain_points", []),
                constraints=doc_data.get("constraints", []),
            )
        else:
            return ToBeDocument(
                title=doc_data.get("title", default_title),
                executive_summary=doc_data.get(
                    "executive_summary", "Executive summary not provided"
                ),
                sections=sections,
                future_state_vision=doc_data.get(
                    "future_state_vision", "Future state vision not provided"
                ),
                benefits=doc_data.get("benefits", []),
                success_criteria=doc_data.get("success_criteria", []),
            )

    def _assess_requirements_completeness(self, requirements: Dict[str, Any]) -> float:
        """Assess the completeness of clarified requirements.

        Args:
            requirements: Clarified requirements data

        Returns:
            Completeness score between 0.0 and 1.0
        """
        score = 0.5  # Base score

        if not requirements:
            return 0.0

        # Check for key requirement categories
        key_categories = [
            "functional_requirements",
            "non_functional_requirements",
            "business_requirements",
            "technical_requirements",
            "stakeholders",
            "constraints",
            "success_criteria",
        ]

        category_count = 0
        for category in key_categories:
            if category in requirements and requirements[category]:
                category_count += 1

        score += (category_count / len(key_categories)) * 0.4

        # Check overall data richness
        total_content = str(requirements)
        if len(total_content) > 500:
            score += 0.1
        if len(total_content) > 1000:
            score += 0.1

        return min(1.0, score)

    def _assess_documentation_quality(
        self, as_is_doc: AsIsDocument, to_be_doc: ToBeDocument
    ) -> float:
        """Assess the quality of generated documentation.

        Args:
            as_is_doc: AS-IS document
            to_be_doc: TO-BE document

        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0

        # Check AS-IS document quality
        if as_is_doc.sections and len(as_is_doc.sections) >= 3:
            score += 0.2
        if as_is_doc.executive_summary and len(as_is_doc.executive_summary) > 100:
            score += 0.1
        if as_is_doc.pain_points:
            score += 0.1

        # Check TO-BE document quality
        if to_be_doc.sections and len(to_be_doc.sections) >= 3:
            score += 0.2
        if to_be_doc.executive_summary and len(to_be_doc.executive_summary) > 100:
            score += 0.1
        if to_be_doc.benefits:
            score += 0.1
        if to_be_doc.success_criteria:
            score += 0.1

        # Check content depth
        total_content_length = sum(
            len(section.content) for section in as_is_doc.sections + to_be_doc.sections
        )
        if total_content_length > 1000:
            score += 0.1

        return min(1.0, score)
