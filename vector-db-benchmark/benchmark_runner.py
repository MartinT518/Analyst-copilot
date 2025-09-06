"""Vector database benchmark runner for comparing Chroma vs pgvector performance."""

import asyncio
import time
import json
import random
import string
from typing import Dict, List, Any, Tuple
from pathlib import Path
import numpy as np
import structlog
import psycopg2
import chromadb
from chromadb.config import Settings
import httpx

logger = structlog.get_logger(__name__)


class VectorDBBenchmark:
    """Benchmark runner for comparing vector database performance."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the benchmark runner.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config
        self.logger = logger.bind(component="vector_benchmark")
        
        # Results storage
        self.results = {
            "chroma": {"ingestion": [], "search": [], "hybrid": []},
            "pgvector": {"ingestion": [], "search": [], "hybrid": []}
        }
        
        # Test data
        self.test_chunks = []
        self.test_embeddings = []
        self.test_queries = []
    
    async def run_full_benchmark(self) -> Dict[str, Any]:
        """Run the complete benchmark suite.
        
        Returns:
            Comprehensive benchmark results
        """
        self.logger.info("Starting vector database benchmark")
        
        try:
            # Generate test data
            await self._generate_test_data()
            
            # Run Chroma benchmarks
            chroma_results = await self._benchmark_chroma()
            
            # Run pgvector benchmarks
            pgvector_results = await self._benchmark_pgvector()
            
            # Analyze results
            analysis = await self._analyze_results(chroma_results, pgvector_results)
            
            # Generate recommendation
            recommendation = await self._generate_recommendation(analysis)
            
            final_results = {
                "benchmark_config": self.config,
                "test_data_stats": {
                    "chunk_count": len(self.test_chunks),
                    "embedding_dimension": len(self.test_embeddings[0]) if self.test_embeddings else 0,
                    "query_count": len(self.test_queries)
                },
                "chroma_results": chroma_results,
                "pgvector_results": pgvector_results,
                "comparative_analysis": analysis,
                "recommendation": recommendation
            }
            
            self.logger.info("Vector database benchmark completed")
            return final_results
            
        except Exception as e:
            self.logger.error("Benchmark failed", error=str(e))
            raise
    
    async def _generate_test_data(self):
        """Generate test data for benchmarking."""
        self.logger.info("Generating test data", chunk_count=self.config["chunk_count"])
        
        # Generate synthetic text chunks
        for i in range(self.config["chunk_count"]):
            chunk = {
                "id": f"chunk_{i}",
                "content": self._generate_random_text(200, 500),
                "metadata": {
                    "source_type": random.choice(["document", "code", "wiki", "manual"]),
                    "category": random.choice(["technical", "business", "process", "reference"]),
                    "priority": random.choice(["high", "medium", "low"]),
                    "created_at": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
                }
            }
            self.test_chunks.append(chunk)
        
        # Generate synthetic embeddings (1536 dimensions like OpenAI)
        embedding_dim = self.config.get("embedding_dimension", 1536)
        for i in range(len(self.test_chunks)):
            # Generate normalized random vector
            vector = np.random.normal(0, 1, embedding_dim)
            vector = vector / np.linalg.norm(vector)
            self.test_embeddings.append(vector.tolist())
        
        # Generate test queries
        for i in range(self.config["query_count"]):
            query = {
                "id": f"query_{i}",
                "text": self._generate_random_text(10, 50),
                "embedding": (np.random.normal(0, 1, embedding_dim) / np.linalg.norm(np.random.normal(0, 1, embedding_dim))).tolist(),
                "filters": self._generate_random_filters()
            }
            self.test_queries.append(query)
    
    def _generate_random_text(self, min_words: int, max_words: int) -> str:
        """Generate random text for testing.
        
        Args:
            min_words: Minimum number of words
            max_words: Maximum number of words
            
        Returns:
            Random text string
        """
        words = [
            "system", "database", "application", "service", "interface", "process",
            "workflow", "integration", "analysis", "requirement", "specification",
            "implementation", "architecture", "design", "development", "testing",
            "deployment", "monitoring", "performance", "security", "scalability",
            "user", "customer", "business", "technical", "functional", "operational"
        ]
        
        word_count = random.randint(min_words, max_words)
        return " ".join(random.choices(words, k=word_count))
    
    def _generate_random_filters(self) -> Dict[str, Any]:
        """Generate random metadata filters for testing.
        
        Returns:
            Random filter dictionary
        """
        filters = {}
        
        if random.random() < 0.3:  # 30% chance of source_type filter
            filters["source_type"] = random.choice(["document", "code", "wiki"])
        
        if random.random() < 0.2:  # 20% chance of category filter
            filters["category"] = random.choice(["technical", "business"])
        
        if random.random() < 0.1:  # 10% chance of priority filter
            filters["priority"] = "high"
        
        return filters
    
    async def _benchmark_chroma(self) -> Dict[str, Any]:
        """Benchmark Chroma vector database.
        
        Returns:
            Chroma benchmark results
        """
        self.logger.info("Benchmarking Chroma")
        
        try:
            # Initialize Chroma client
            chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.config.get("chroma_persist_dir", "/tmp/chroma_benchmark")
            ))
            
            # Create collection
            collection_name = f"benchmark_{int(time.time())}"
            collection = chroma_client.create_collection(
                name=collection_name,
                metadata={"description": "Benchmark collection"}
            )
            
            # Benchmark ingestion
            ingestion_results = await self._benchmark_chroma_ingestion(collection)
            
            # Benchmark search
            search_results = await self._benchmark_chroma_search(collection)
            
            # Benchmark hybrid search
            hybrid_results = await self._benchmark_chroma_hybrid_search(collection)
            
            # Cleanup
            chroma_client.delete_collection(collection_name)
            
            return {
                "ingestion": ingestion_results,
                "search": search_results,
                "hybrid": hybrid_results,
                "status": "completed"
            }
            
        except Exception as e:
            self.logger.error("Chroma benchmark failed", error=str(e))
            return {
                "ingestion": {"error": str(e)},
                "search": {"error": str(e)},
                "hybrid": {"error": str(e)},
                "status": "failed"
            }
    
    async def _benchmark_chroma_ingestion(self, collection) -> Dict[str, Any]:
        """Benchmark Chroma ingestion performance.
        
        Args:
            collection: Chroma collection
            
        Returns:
            Ingestion benchmark results
        """
        batch_size = self.config.get("batch_size", 100)
        total_time = 0
        batch_times = []
        
        for i in range(0, len(self.test_chunks), batch_size):
            batch_chunks = self.test_chunks[i:i + batch_size]
            batch_embeddings = self.test_embeddings[i:i + batch_size]
            
            start_time = time.time()
            
            # Prepare batch data
            ids = [chunk["id"] for chunk in batch_chunks]
            documents = [chunk["content"] for chunk in batch_chunks]
            metadatas = [chunk["metadata"] for chunk in batch_chunks]
            
            # Add to collection
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=batch_embeddings,
                metadatas=metadatas
            )
            
            batch_time = time.time() - start_time
            batch_times.append(batch_time)
            total_time += batch_time
        
        return {
            "total_time_seconds": total_time,
            "average_batch_time": sum(batch_times) / len(batch_times),
            "throughput_docs_per_second": len(self.test_chunks) / total_time,
            "batch_count": len(batch_times),
            "batch_size": batch_size
        }
    
    async def _benchmark_chroma_search(self, collection) -> Dict[str, Any]:
        """Benchmark Chroma search performance.
        
        Args:
            collection: Chroma collection
            
        Returns:
            Search benchmark results
        """
        search_times = []
        result_counts = []
        
        for query in self.test_queries:
            start_time = time.time()
            
            results = collection.query(
                query_embeddings=[query["embedding"]],
                n_results=self.config.get("search_k", 10)
            )
            
            search_time = time.time() - start_time
            search_times.append(search_time)
            result_counts.append(len(results["ids"][0]) if results["ids"] else 0)
        
        return {
            "average_latency_ms": (sum(search_times) / len(search_times)) * 1000,
            "p95_latency_ms": np.percentile(search_times, 95) * 1000,
            "p99_latency_ms": np.percentile(search_times, 99) * 1000,
            "average_results_returned": sum(result_counts) / len(result_counts),
            "total_queries": len(self.test_queries)
        }
    
    async def _benchmark_chroma_hybrid_search(self, collection) -> Dict[str, Any]:
        """Benchmark Chroma hybrid search with filters.
        
        Args:
            collection: Chroma collection
            
        Returns:
            Hybrid search benchmark results
        """
        search_times = []
        result_counts = []
        
        for query in self.test_queries:
            if not query["filters"]:  # Skip queries without filters
                continue
            
            start_time = time.time()
            
            results = collection.query(
                query_embeddings=[query["embedding"]],
                n_results=self.config.get("search_k", 10),
                where=query["filters"]
            )
            
            search_time = time.time() - start_time
            search_times.append(search_time)
            result_counts.append(len(results["ids"][0]) if results["ids"] else 0)
        
        if not search_times:
            return {"error": "No queries with filters to test"}
        
        return {
            "average_latency_ms": (sum(search_times) / len(search_times)) * 1000,
            "p95_latency_ms": np.percentile(search_times, 95) * 1000,
            "p99_latency_ms": np.percentile(search_times, 99) * 1000,
            "average_results_returned": sum(result_counts) / len(result_counts),
            "filtered_queries_tested": len(search_times)
        }
    
    async def _benchmark_pgvector(self) -> Dict[str, Any]:
        """Benchmark pgvector database.
        
        Returns:
            pgvector benchmark results
        """
        self.logger.info("Benchmarking pgvector")
        
        try:
            # Connect to PostgreSQL
            conn = psycopg2.connect(self.config["pgvector_connection_string"])
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Setup pgvector table
            table_name = f"benchmark_{int(time.time())}"
            await self._setup_pgvector_table(cursor, table_name)
            
            # Benchmark ingestion
            ingestion_results = await self._benchmark_pgvector_ingestion(cursor, table_name)
            
            # Benchmark search
            search_results = await self._benchmark_pgvector_search(cursor, table_name)
            
            # Benchmark hybrid search
            hybrid_results = await self._benchmark_pgvector_hybrid_search(cursor, table_name)
            
            # Cleanup
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.close()
            conn.close()
            
            return {
                "ingestion": ingestion_results,
                "search": search_results,
                "hybrid": hybrid_results,
                "status": "completed"
            }
            
        except Exception as e:
            self.logger.error("pgvector benchmark failed", error=str(e))
            return {
                "ingestion": {"error": str(e)},
                "search": {"error": str(e)},
                "hybrid": {"error": str(e)},
                "status": "failed"
            }
    
    async def _setup_pgvector_table(self, cursor, table_name: str):
        """Setup pgvector table for benchmarking.
        
        Args:
            cursor: Database cursor
            table_name: Table name
        """
        embedding_dim = self.config.get("embedding_dimension", 1536)
        
        # Create table with vector column
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id TEXT PRIMARY KEY,
                content TEXT,
                embedding vector({embedding_dim}),
                source_type TEXT,
                category TEXT,
                priority TEXT,
                created_at TEXT
            )
        """)
        
        # Create vector index
        cursor.execute(f"""
            CREATE INDEX ON {table_name} 
            USING ivfflat (embedding vector_cosine_ops) 
            WITH (lists = 100)
        """)
        
        # Create metadata indexes
        cursor.execute(f"CREATE INDEX ON {table_name} (source_type)")
        cursor.execute(f"CREATE INDEX ON {table_name} (category)")
        cursor.execute(f"CREATE INDEX ON {table_name} (priority)")
    
    async def _benchmark_pgvector_ingestion(self, cursor, table_name: str) -> Dict[str, Any]:
        """Benchmark pgvector ingestion performance.
        
        Args:
            cursor: Database cursor
            table_name: Table name
            
        Returns:
            Ingestion benchmark results
        """
        batch_size = self.config.get("batch_size", 100)
        total_time = 0
        batch_times = []
        
        for i in range(0, len(self.test_chunks), batch_size):
            batch_chunks = self.test_chunks[i:i + batch_size]
            batch_embeddings = self.test_embeddings[i:i + batch_size]
            
            start_time = time.time()
            
            # Prepare batch insert
            values = []
            for j, chunk in enumerate(batch_chunks):
                embedding_str = "[" + ",".join(map(str, batch_embeddings[j])) + "]"
                values.append((
                    chunk["id"],
                    chunk["content"],
                    embedding_str,
                    chunk["metadata"]["source_type"],
                    chunk["metadata"]["category"],
                    chunk["metadata"]["priority"],
                    chunk["metadata"]["created_at"]
                ))
            
            # Execute batch insert
            cursor.executemany(f"""
                INSERT INTO {table_name} 
                (id, content, embedding, source_type, category, priority, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, values)
            
            batch_time = time.time() - start_time
            batch_times.append(batch_time)
            total_time += batch_time
        
        return {
            "total_time_seconds": total_time,
            "average_batch_time": sum(batch_times) / len(batch_times),
            "throughput_docs_per_second": len(self.test_chunks) / total_time,
            "batch_count": len(batch_times),
            "batch_size": batch_size
        }
    
    async def _benchmark_pgvector_search(self, cursor, table_name: str) -> Dict[str, Any]:
        """Benchmark pgvector search performance.
        
        Args:
            cursor: Database cursor
            table_name: Table name
            
        Returns:
            Search benchmark results
        """
        search_times = []
        result_counts = []
        
        for query in self.test_queries:
            start_time = time.time()
            
            embedding_str = "[" + ",".join(map(str, query["embedding"])) + "]"
            
            cursor.execute(f"""
                SELECT id, content, 1 - (embedding <=> %s) as similarity
                FROM {table_name}
                ORDER BY embedding <=> %s
                LIMIT %s
            """, (embedding_str, embedding_str, self.config.get("search_k", 10)))
            
            results = cursor.fetchall()
            
            search_time = time.time() - start_time
            search_times.append(search_time)
            result_counts.append(len(results))
        
        return {
            "average_latency_ms": (sum(search_times) / len(search_times)) * 1000,
            "p95_latency_ms": np.percentile(search_times, 95) * 1000,
            "p99_latency_ms": np.percentile(search_times, 99) * 1000,
            "average_results_returned": sum(result_counts) / len(result_counts),
            "total_queries": len(self.test_queries)
        }
    
    async def _benchmark_pgvector_hybrid_search(self, cursor, table_name: str) -> Dict[str, Any]:
        """Benchmark pgvector hybrid search with filters.
        
        Args:
            cursor: Database cursor
            table_name: Table name
            
        Returns:
            Hybrid search benchmark results
        """
        search_times = []
        result_counts = []
        
        for query in self.test_queries:
            if not query["filters"]:  # Skip queries without filters
                continue
            
            start_time = time.time()
            
            # Build WHERE clause from filters
            where_conditions = []
            params = []
            
            embedding_str = "[" + ",".join(map(str, query["embedding"])) + "]"
            params.extend([embedding_str, embedding_str])
            
            for key, value in query["filters"].items():
                where_conditions.append(f"{key} = %s")
                params.append(value)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT id, content, 1 - (embedding <=> %s) as similarity
                FROM {table_name}
                WHERE {where_clause}
                ORDER BY embedding <=> %s
                LIMIT %s
            """, params + [self.config.get("search_k", 10)])
            
            results = cursor.fetchall()
            
            search_time = time.time() - start_time
            search_times.append(search_time)
            result_counts.append(len(results))
        
        if not search_times:
            return {"error": "No queries with filters to test"}
        
        return {
            "average_latency_ms": (sum(search_times) / len(search_times)) * 1000,
            "p95_latency_ms": np.percentile(search_times, 95) * 1000,
            "p99_latency_ms": np.percentile(search_times, 99) * 1000,
            "average_results_returned": sum(result_counts) / len(result_counts),
            "filtered_queries_tested": len(search_times)
        }
    
    async def _analyze_results(
        self,
        chroma_results: Dict[str, Any],
        pgvector_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze benchmark results and compare performance.
        
        Args:
            chroma_results: Chroma benchmark results
            pgvector_results: pgvector benchmark results
            
        Returns:
            Comparative analysis
        """
        analysis = {
            "ingestion_comparison": {},
            "search_comparison": {},
            "hybrid_comparison": {},
            "overall_scores": {}
        }
        
        # Compare ingestion performance
        if ("error" not in chroma_results["ingestion"] and 
            "error" not in pgvector_results["ingestion"]):
            
            chroma_throughput = chroma_results["ingestion"]["throughput_docs_per_second"]
            pgvector_throughput = pgvector_results["ingestion"]["throughput_docs_per_second"]
            
            analysis["ingestion_comparison"] = {
                "chroma_throughput": chroma_throughput,
                "pgvector_throughput": pgvector_throughput,
                "performance_ratio": pgvector_throughput / chroma_throughput,
                "winner": "pgvector" if pgvector_throughput > chroma_throughput else "chroma"
            }
        
        # Compare search performance
        if ("error" not in chroma_results["search"] and 
            "error" not in pgvector_results["search"]):
            
            chroma_latency = chroma_results["search"]["average_latency_ms"]
            pgvector_latency = pgvector_results["search"]["average_latency_ms"]
            
            analysis["search_comparison"] = {
                "chroma_latency_ms": chroma_latency,
                "pgvector_latency_ms": pgvector_latency,
                "latency_ratio": chroma_latency / pgvector_latency,
                "winner": "pgvector" if pgvector_latency < chroma_latency else "chroma"
            }
        
        # Compare hybrid search performance
        if ("error" not in chroma_results["hybrid"] and 
            "error" not in pgvector_results["hybrid"]):
            
            chroma_hybrid_latency = chroma_results["hybrid"]["average_latency_ms"]
            pgvector_hybrid_latency = pgvector_results["hybrid"]["average_latency_ms"]
            
            analysis["hybrid_comparison"] = {
                "chroma_hybrid_latency_ms": chroma_hybrid_latency,
                "pgvector_hybrid_latency_ms": pgvector_hybrid_latency,
                "latency_ratio": chroma_hybrid_latency / pgvector_hybrid_latency,
                "winner": "pgvector" if pgvector_hybrid_latency < chroma_hybrid_latency else "chroma"
            }
        
        # Calculate overall scores
        chroma_score = 0
        pgvector_score = 0
        
        for comparison in ["ingestion_comparison", "search_comparison", "hybrid_comparison"]:
            if comparison in analysis and "winner" in analysis[comparison]:
                if analysis[comparison]["winner"] == "chroma":
                    chroma_score += 1
                else:
                    pgvector_score += 1
        
        analysis["overall_scores"] = {
            "chroma_wins": chroma_score,
            "pgvector_wins": pgvector_score,
            "overall_winner": "pgvector" if pgvector_score > chroma_score else "chroma"
        }
        
        return analysis
    
    async def _generate_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendation based on benchmark results.
        
        Args:
            analysis: Comparative analysis results
            
        Returns:
            Recommendation with justification
        """
        recommendation = {
            "recommended_solution": "chroma",  # Default
            "confidence": "medium",
            "justification": [],
            "considerations": [],
            "migration_effort": "low"
        }
        
        # Determine recommendation based on analysis
        overall_winner = analysis.get("overall_scores", {}).get("overall_winner", "chroma")
        
        if overall_winner == "pgvector":
            # Check if pgvector is significantly better (>15% performance difference)
            search_ratio = analysis.get("search_comparison", {}).get("latency_ratio", 1.0)
            
            if search_ratio > 1.15:  # pgvector is >15% faster
                recommendation["recommended_solution"] = "pgvector"
                recommendation["confidence"] = "high"
                recommendation["justification"].append(
                    f"pgvector shows {((search_ratio - 1) * 100):.1f}% better search performance"
                )
                recommendation["migration_effort"] = "medium"
            else:
                recommendation["justification"].append(
                    "Performance difference is within 15% threshold, staying with Chroma for simplicity"
                )
        else:
            recommendation["justification"].append(
                "Chroma performs better or equivalently to pgvector"
            )
        
        # Add considerations
        recommendation["considerations"] = [
            "Chroma provides simpler deployment and management",
            "pgvector offers better PostgreSQL integration",
            "Consider operational complexity vs performance gains",
            "Evaluate based on your specific use case and data patterns"
        ]
        
        return recommendation


async def main():
    """Run the vector database benchmark."""
    config = {
        "chunk_count": 10000,
        "query_count": 50,
        "embedding_dimension": 1536,
        "batch_size": 100,
        "search_k": 10,
        "chroma_persist_dir": "/tmp/chroma_benchmark",
        "pgvector_connection_string": "postgresql://acp_user:acp_password@localhost:5432/acp_ingest"
    }
    
    benchmark = VectorDBBenchmark(config)
    results = await benchmark.run_full_benchmark()
    
    # Save results
    output_file = Path("/tmp/vector_db_benchmark_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"Benchmark results saved to: {output_file}")
    print(f"Recommendation: {results['recommendation']['recommended_solution']}")
    print(f"Confidence: {results['recommendation']['confidence']}")


if __name__ == "__main__":
    asyncio.run(main())

