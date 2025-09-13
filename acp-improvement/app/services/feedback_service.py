"""Service for capturing and processing human feedback on agent performance."""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.orm import Session

from .. import models, schemas

logger = structlog.get_logger(__name__)


class FeedbackService:
    """Service for managing human feedback on agent outputs."""

    def __init__(self, db_session: Session):
        """Initialize the feedback service.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.logger = logger.bind(service="feedback_service")

    async def submit_feedback(self, feedback_data: schemas.FeedbackCreate) -> models.Feedback:
        """Submit feedback for an agent-generated output.

        Args:
            feedback_data: Feedback data

        Returns:
            Created feedback record
        """
        self.logger.info("Submitting feedback", workflow_id=feedback_data.workflow_id)

        try:
            # Create feedback record
            db_feedback = models.Feedback(**feedback_data.dict())
            self.db.add(db_feedback)
            self.db.commit()
            self.db.refresh(db_feedback)

            self.logger.info("Feedback submitted successfully", feedback_id=db_feedback.id)
            return db_feedback

        except Exception as e:
            self.logger.error("Failed to submit feedback", error=str(e))
            self.db.rollback()
            raise

    async def get_feedback_for_workflow(
        self, workflow_id: str, skip: int = 0, limit: int = 100
    ) -> List[models.Feedback]:
        """Get all feedback for a specific workflow.

        Args:
            workflow_id: Workflow ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of feedback records
        """
        self.logger.info("Fetching feedback for workflow", workflow_id=workflow_id)

        try:
            return (
                self.db.query(models.Feedback)
                .filter(models.Feedback.workflow_id == workflow_id)
                .offset(skip)
                .limit(limit)
                .all()
            )
        except Exception as e:
            self.logger.error("Failed to fetch feedback", error=str(e))
            raise

    async def get_feedback_summary(
        self,
        agent_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of feedback for analysis.

        Args:
            agent_name: Filter by agent name
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Feedback summary statistics
        """
        self.logger.info("Generating feedback summary")

        try:
            query = self.db.query(models.Feedback)

            if agent_name:
                query = query.filter(models.Feedback.agent_name == agent_name)
            if start_date:
                query = query.filter(models.Feedback.created_at >= start_date)
            if end_date:
                query = query.filter(models.Feedback.created_at <= end_date)

            feedback_records = query.all()

            if not feedback_records:
                return {"message": "No feedback found for the given criteria"}

            # Calculate summary statistics
            total_feedback = len(feedback_records)
            average_rating = sum(f.rating for f in feedback_records) / total_feedback
            acceptance_rate = sum(1 for f in feedback_records if f.accepted) / total_feedback

            # Group by agent
            agent_summary = {}
            for record in feedback_records:
                if record.agent_name not in agent_summary:
                    agent_summary[record.agent_name] = {
                        "count": 0,
                        "total_rating": 0,
                        "accepted_count": 0,
                    }

                agent_summary[record.agent_name]["count"] += 1
                agent_summary[record.agent_name]["total_rating"] += record.rating
                agent_summary[record.agent_name]["accepted_count"] += 1 if record.accepted else 0

            for agent, data in agent_summary.items():
                data["average_rating"] = data["total_rating"] / data["count"]
                data["acceptance_rate"] = data["accepted_count"] / data["count"]

            return {
                "total_feedback_records": total_feedback,
                "overall_average_rating": average_rating,
                "overall_acceptance_rate": acceptance_rate,
                "agent_summary": agent_summary,
            }

        except Exception as e:
            self.logger.error("Failed to generate feedback summary", error=str(e))
            raise
