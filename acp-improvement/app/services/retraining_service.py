"""Service for retraining and tuning agent prompts and models based on feedback."""

import asyncio
import json
from typing import Dict, List, Any, Optional
import structlog
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Embedding, GlobalAveragePooling1D
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import keras_tuner as kt

from ..models import Feedback
from ..schemas import RetrainingJobCreate

logger = structlog.get_logger(__name__)


class RetrainingService:
    """Service for managing model and prompt retraining pipelines."""

    def __init__(self, db_session):
        """Initialize the retraining service.

        Args:
            db_session: Database session
        """
        self.db = db_session
        self.logger = logger.bind(service="retraining_service")

    async def start_retraining_job(self, job_config: RetrainingJobCreate) -> Dict[str, Any]:
        """Start a new retraining job.

        Args:
            job_config: Retraining job configuration

        Returns:
            Retraining job results
        """
        self.logger.info("Starting retraining job", job_config=job_config)

        try:
            # Fetch feedback data
            feedback_data = await self._fetch_feedback_data(job_config)
            if not feedback_data:
                return {"message": "No feedback data found for retraining"}

            # Prepare data for training
            X_train, X_test, y_train, y_test, tokenizer = await self._prepare_data(feedback_data)

            # Tune model hyperparameters
            best_hps = await self._tune_model(X_train, y_train)

            # Train final model
            model, history = await self._train_model(X_train, y_train, best_hps)

            # Evaluate model
            evaluation_results = await self._evaluate_model(model, X_test, y_test)

            # Save model and tokenizer
            await self._save_artifacts(model, tokenizer, job_config.agent_name)

            # Generate report
            report = await self._generate_report(
                job_config, len(feedback_data), evaluation_results, history.history
            )

            self.logger.info("Retraining job completed successfully")
            return report

        except Exception as e:
            self.logger.error("Retraining job failed", error=str(e))
            raise

    async def _fetch_feedback_data(self, job_config: RetrainingJobCreate) -> List[Feedback]:
        """Fetch feedback data from the database.

        Args:
            job_config: Job configuration

        Returns:
            List of feedback records
        """
        query = self.db.query(Feedback).filter(
            Feedback.agent_name == job_config.agent_name, Feedback.rating.isnot(None)
        )

        if job_config.start_date:
            query = query.filter(Feedback.created_at >= job_config.start_date)
        if job_config.end_date:
            query = query.filter(Feedback.created_at <= job_config.end_date)

        return query.all()

    async def _prepare_data(self, feedback_data: List[Feedback]):
        """Prepare data for model training.

        Args:
            feedback_data: List of feedback records

        Returns:
            Training and testing data splits
        """
        # Create DataFrame from feedback
        df = pd.DataFrame(
            [{"text": f.original_output, "label": 1 if f.accepted else 0} for f in feedback_data]
        )

        # Tokenize text
        tokenizer = Tokenizer(num_words=10000, oov_token="<unk>")
        tokenizer.fit_on_texts(df["text"])

        # Convert text to sequences
        sequences = tokenizer.texts_to_sequences(df["text"])
        padded_sequences = pad_sequences(sequences, maxlen=256, padding="post", truncating="post")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            padded_sequences, df["label"].values, test_size=0.2, random_state=42
        )

        return X_train, X_test, y_train, y_test, tokenizer

    async def _tune_model(self, X_train, y_train):
        """Tune model hyperparameters using Keras Tuner.

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Best hyperparameters
        """

        def build_model(hp):
            model = Sequential(
                [
                    Embedding(
                        input_dim=10000, output_dim=hp.Int("embedding_dim", 16, 128, step=16)
                    ),
                    GlobalAveragePooling1D(),
                    Dense(units=hp.Int("dense_units", 32, 256, step=32), activation="relu"),
                    Dropout(rate=hp.Float("dropout", 0.1, 0.5, step=0.1)),
                    Dense(1, activation="sigmoid"),
                ]
            )

            model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            return model

        tuner = kt.Hyperband(
            build_model,
            objective="val_accuracy",
            max_epochs=10,
            factor=3,
            directory="/tmp/keras_tuner",
            project_name="analyst_copilot_tuning",
        )

        tuner.search(X_train, y_train, epochs=10, validation_split=0.2)

        return tuner.get_best_hyperparameters(num_trials=1)[0]

    async def _train_model(self, X_train, y_train, best_hps):
        """Train the final model with best hyperparameters.

        Args:
            X_train: Training features
            y_train: Training labels
            best_hps: Best hyperparameters

        Returns:
            Trained model and history
        """
        model = Sequential(
            [
                Embedding(input_dim=10000, output_dim=best_hps.get("embedding_dim")),
                GlobalAveragePooling1D(),
                Dense(units=best_hps.get("dense_units"), activation="relu"),
                Dropout(rate=best_hps.get("dropout")),
                Dense(1, activation="sigmoid"),
            ]
        )

        model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])

        history = model.fit(
            X_train, y_train, epochs=10, batch_size=32, validation_split=0.2, verbose=0
        )

        return model, history

    async def _evaluate_model(self, model, X_test, y_test):
        """Evaluate the trained model.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels

        Returns:
            Evaluation results
        """
        loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
        y_pred = (model.predict(X_test) > 0.5).astype("int32")

        report = classification_report(y_test, y_pred, output_dict=True)

        return {"loss": loss, "accuracy": accuracy, "classification_report": report}

    async def _save_artifacts(self, model, tokenizer, agent_name: str):
        """Save trained model and tokenizer.

        Args:
            model: Trained model
            tokenizer: Tokenizer
            agent_name: Agent name
        """
        model_path = f"/app/models/{agent_name}_model.h5"
        tokenizer_path = f"/app/models/{agent_name}_tokenizer.json"

        model.save(model_path)

        with open(tokenizer_path, "w") as f:
            f.write(json.dumps(tokenizer.to_json()))

        self.logger.info("Model and tokenizer saved", model_path=model_path)

    async def _generate_report(
        self,
        job_config: RetrainingJobCreate,
        num_records: int,
        eval_results: Dict[str, Any],
        history: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a report for the retraining job.

        Args:
            job_config: Job configuration
            num_records: Number of feedback records used
            eval_results: Evaluation results
            history: Training history

        Returns:
            Retraining job report
        """
        return {
            "job_config": job_config.dict(),
            "status": "completed",
            "num_feedback_records": num_records,
            "evaluation_results": eval_results,
            "training_history": history,
            "model_path": f"/app/models/{job_config.agent_name}_model.h5",
            "tokenizer_path": f"/app/models/{job_config.agent_name}_tokenizer.json",
        }
