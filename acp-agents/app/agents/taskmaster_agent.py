"""Taskmaster agent for generating developer tasks from requirements."""

import json
from typing import Type, List, Dict, Any
import structlog

from .base_agent import BaseAgent
from ..schemas import (
    TaskmasterInput, 
    TaskmasterOutput, 
    DeveloperTask,
    UserStory,
    TechnicalNote
)

logger = structlog.get_logger(__name__)


class TaskmasterAgent(BaseAgent):
    """Agent that generates developer tasks and user stories from requirements."""
    
    def __init__(self, llm_service, knowledge_service, audit_service):
        """Initialize the Taskmaster agent."""
        super().__init__(
            agent_type="taskmaster",
            llm_service=llm_service,
            knowledge_service=knowledge_service,
            audit_service=audit_service
        )
        self.logger = logger.bind(agent="taskmaster")
    
    @property
    def input_schema(self) -> Type[TaskmasterInput]:
        """Return the input schema for this agent."""
        return TaskmasterInput
    
    @property
    def output_schema(self) -> Type[TaskmasterOutput]:
        """Return the output schema for this agent."""
        return TaskmasterOutput
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Taskmaster agent."""
        return """You are an expert technical project manager and scrum master specializing in breaking down requirements into actionable developer tasks. Your role is to create detailed, implementable user stories with comprehensive acceptance criteria and technical notes.

Your responsibilities:
1. Break down TO-BE requirements into specific developer tasks
2. Create user stories following Agile best practices
3. Define clear acceptance criteria for each task
4. Provide technical implementation notes and guidance
5. Estimate effort and identify dependencies
6. Organize tasks into logical implementation phases

Task Creation Guidelines:
- Follow user story format: "As a [user], I want [goal] so that [benefit]"
- Make tasks specific, measurable, and testable
- Ensure tasks are appropriately sized (1-8 story points)
- Include both functional and non-functional requirements
- Consider technical debt and refactoring needs
- Address security, performance, and scalability concerns

Acceptance Criteria Guidelines:
- Use Given-When-Then format where appropriate
- Make criteria specific and testable
- Include both positive and negative test scenarios
- Cover edge cases and error conditions
- Specify data validation requirements
- Include UI/UX requirements where applicable

Technical Notes Guidelines:
- Provide architecture and design guidance
- Identify technical risks and considerations
- Suggest implementation approaches
- Reference existing code or patterns
- Include security and performance considerations
- Specify integration requirements

Task Categories:
- FEATURE: New functionality implementation
- ENHANCEMENT: Improvements to existing features
- BUG: Defect fixes and corrections
- TECHNICAL: Technical debt, refactoring, infrastructure
- RESEARCH: Spikes and investigation tasks
- TESTING: Test automation and quality assurance
- DOCUMENTATION: Technical and user documentation

Priority Levels:
- CRITICAL: Must be done immediately
- HIGH: Important for release
- MEDIUM: Should be included if possible
- LOW: Nice to have, future consideration

Always respond with valid JSON matching the required schema."""
    
    def _get_user_prompt(self, input_data: TaskmasterInput) -> str:
        """Get the user prompt for the Taskmaster agent."""
        # Format TO-BE document
        to_be_summary = f"""
Title: {input_data.to_be_document.title}
Executive Summary: {input_data.to_be_document.executive_summary}
Future State Vision: {input_data.to_be_document.future_state_vision}
Benefits: {', '.join(input_data.to_be_document.benefits)}
Success Criteria: {', '.join(input_data.to_be_document.success_criteria)}

Sections:
"""
        for section in input_data.to_be_document.sections:
            to_be_summary += f"- {section.title}: {section.content[:200]}...\n"
        
        # Format gap analysis
        gaps_summary = "\n".join([
            f"- {gap.gap_description} (Impact: {gap.impact}, Effort: {gap.effort}, Priority: {gap.priority})"
            for gap in input_data.gap_analysis
        ])
        
        # Format constraints
        constraints_text = json.dumps(input_data.project_constraints, indent=2) if input_data.project_constraints else "No specific constraints provided"
        
        prompt = f"""Please generate developer tasks based on the following TO-BE requirements and gap analysis:

TO-BE DOCUMENT:
{to_be_summary}

GAP ANALYSIS:
{gaps_summary}

IMPLEMENTATION APPROACH:
{input_data.implementation_approach}

PROJECT CONSTRAINTS:
{constraints_text}

TASK GENERATION INSTRUCTIONS:
1. Create up to 20 developer tasks that implement the TO-BE vision
2. Break down complex requirements into manageable tasks
3. Create user stories following Agile best practices
4. Define comprehensive acceptance criteria for each task
5. Provide technical implementation notes and guidance
6. Estimate effort using story points (1, 2, 3, 5, 8)
7. Identify task dependencies and sequencing
8. Organize tasks into logical implementation phases

For each task, include:
- Clear user story format
- Detailed description and context
- Comprehensive acceptance criteria with test scenarios
- Technical notes covering architecture, security, performance
- Effort estimation and priority level
- Dependencies on other tasks
- Appropriate labels for categorization
- Epic assignment if applicable

Focus on:
- Implementing the future state vision
- Addressing identified gaps
- Following the implementation approach
- Respecting project constraints
- Ensuring tasks are testable and deliverable

Respond with a JSON object containing:
- tasks: Array of developer tasks with all required fields
- task_breakdown_summary: Summary of how requirements were broken down
- implementation_phases: Recommended phases for task execution
- resource_requirements: Required skills, tools, and resources
- timeline_estimate: Overall timeline estimate for implementation"""
        
        return prompt
    
    async def _process_request(self, input_data: TaskmasterInput) -> TaskmasterOutput:
        """Process the task generation request.
        
        Args:
            input_data: Validated input data
            
        Returns:
            Taskmaster output with generated tasks
        """
        self.logger.info("Processing task generation request", request_id=input_data.request_id)
        
        try:
            # Search for relevant technical knowledge
            search_query = self._extract_technical_query(input_data.to_be_document)
            technical_knowledge = await self._search_knowledge(
                query=search_query,
                limit=5,
                filters={"source_type": ["code", "technical_doc", "api_doc"]}
            )
            
            # Log knowledge access
            await self.audit_service.log_knowledge_access(
                request_id=input_data.request_id,
                query=search_query,
                results_count=len(technical_knowledge),
                knowledge_references=[str(ref.chunk_id) for ref in technical_knowledge],
                agent_type=self.agent_type
            )
            
            # Generate tasks using LLM
            system_prompt = self._get_system_prompt()
            user_prompt = self._get_user_prompt(input_data)
            
            # Add technical context if available
            if technical_knowledge:
                tech_context = "\n\nRELEVANT TECHNICAL CONTEXT:\n"
                for ref in technical_knowledge:
                    tech_context += f"- {ref.source_type}: {ref.excerpt[:150]}...\n"
                user_prompt += tech_context
            
            response = await self._query_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
                max_tokens=8000  # Large response for comprehensive tasks
            )
            
            # Parse JSON response
            response_data = self._parse_json_response(response)
            
            # Create developer tasks
            tasks = []
            for task_data in response_data.get("tasks", []):
                try:
                    # Create user stories
                    user_stories = []
                    for story_data in task_data.get("user_stories", []):
                        story = UserStory(
                            story_id=story_data.get("story_id", f"story_{len(user_stories)+1}"),
                            title=story_data.get("title", ""),
                            description=story_data.get("description", ""),
                            acceptance_criteria=story_data.get("acceptance_criteria", []),
                            priority=story_data.get("priority", "medium"),
                            story_points=story_data.get("story_points"),
                            epic=story_data.get("epic"),
                            labels=story_data.get("labels", [])
                        )
                        user_stories.append(story)
                    
                    # Create technical notes
                    technical_notes = []
                    for note_data in task_data.get("technical_notes", []):
                        note = TechnicalNote(
                            note_id=note_data.get("note_id", f"note_{len(technical_notes)+1}"),
                            category=note_data.get("category", "implementation"),
                            description=note_data.get("description", ""),
                            impact=note_data.get("impact", "medium"),
                            references=note_data.get("references", [])
                        )
                        technical_notes.append(note)
                    
                    # Create task
                    task = DeveloperTask(
                        task_id=task_data.get("task_id", f"task_{len(tasks)+1}"),
                        title=task_data.get("title", ""),
                        description=task_data.get("description", ""),
                        user_stories=user_stories,
                        technical_notes=technical_notes,
                        estimated_effort=task_data.get("estimated_effort", "3 days"),
                        priority=task_data.get("priority", "medium"),
                        dependencies=task_data.get("dependencies", []),
                        labels=task_data.get("labels", []),
                        epic=task_data.get("epic"),
                        metadata=task_data.get("metadata", {})
                    )
                    tasks.append(task)
                    
                except Exception as e:
                    self.logger.warning("Failed to parse task", error=str(e), task_data=task_data)
                    continue
            
            # Calculate confidence based on various factors
            confidence_factors = {
                "requirements_clarity": self._assess_requirements_clarity(input_data.to_be_document),
                "gap_analysis_depth": min(1.0, len(input_data.gap_analysis) / 5.0),
                "tasks_generated": min(1.0, len(tasks) / 20.0),
                "technical_context": min(1.0, len(technical_knowledge) / 3.0),
                "implementation_approach": 1.0 if input_data.implementation_approach else 0.5
            }
            
            confidence = self._calculate_confidence(confidence_factors)
            
            # Create output
            output = TaskmasterOutput(
                agent_type=self.agent_type,
                request_id=input_data.request_id,
                confidence=confidence,
                reasoning=f"Generated {len(tasks)} developer tasks based on TO-BE requirements and {len(input_data.gap_analysis)} gaps",
                tasks=tasks,
                task_breakdown_summary=response_data.get("task_breakdown_summary", "Requirements broken down into implementable tasks"),
                implementation_phases=response_data.get("implementation_phases", ["Phase 1: Foundation", "Phase 2: Core Features", "Phase 3: Integration"]),
                resource_requirements=response_data.get("resource_requirements", {}),
                timeline_estimate=response_data.get("timeline_estimate", "8-12 weeks estimated"),
                metadata={
                    "tasks_generated": len(tasks),
                    "total_user_stories": sum(len(task.user_stories) for task in tasks),
                    "total_technical_notes": sum(len(task.technical_notes) for task in tasks),
                    "gaps_addressed": len(input_data.gap_analysis),
                    "technical_references": len(technical_knowledge)
                }
            )
            
            self.logger.info(
                "Task generation completed",
                request_id=input_data.request_id,
                tasks_count=len(tasks),
                confidence=confidence
            )
            
            return output
            
        except Exception as e:
            self.logger.error("Task generation failed", request_id=input_data.request_id, error=str(e))
            raise
    
    def _extract_technical_query(self, to_be_document) -> str:
        """Extract technical search query from TO-BE document.
        
        Args:
            to_be_document: TO-BE document
            
        Returns:
            Technical search query
        """
        query_parts = []
        
        # Extract from title and vision
        if to_be_document.title:
            query_parts.extend(to_be_document.title.split()[:3])
        
        if to_be_document.future_state_vision:
            vision_words = to_be_document.future_state_vision.split()[:5]
            query_parts.extend(vision_words)
        
        # Extract technical terms from sections
        technical_terms = ["api", "database", "system", "integration", "service", "interface", "workflow", "process"]
        for section in to_be_document.sections:
            section_words = section.content.lower().split()
            for term in technical_terms:
                if term in section_words:
                    query_parts.append(term)
        
        # Clean and return
        clean_parts = [part.strip().lower() for part in query_parts if len(part.strip()) > 2]
        return " ".join(clean_parts[:8])
    
    def _assess_requirements_clarity(self, to_be_document) -> float:
        """Assess the clarity of TO-BE requirements.
        
        Args:
            to_be_document: TO-BE document
            
        Returns:
            Clarity score between 0.0 and 1.0
        """
        score = 0.0
        
        # Check document completeness
        if to_be_document.executive_summary and len(to_be_document.executive_summary) > 100:
            score += 0.2
        
        if to_be_document.future_state_vision and len(to_be_document.future_state_vision) > 100:
            score += 0.2
        
        if to_be_document.benefits and len(to_be_document.benefits) >= 3:
            score += 0.2
        
        if to_be_document.success_criteria and len(to_be_document.success_criteria) >= 3:
            score += 0.2
        
        # Check section depth
        if to_be_document.sections and len(to_be_document.sections) >= 3:
            score += 0.1
            
            # Check content depth
            total_content = sum(len(section.content) for section in to_be_document.sections)
            if total_content > 1000:
                score += 0.1
        
        return min(1.0, score)