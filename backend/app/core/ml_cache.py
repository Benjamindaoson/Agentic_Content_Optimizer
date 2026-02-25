"""
ML-Powered Cache Prediction System
Provides intelligent cache warming and semantic similarity matching
"""

from typing import List, Optional, Dict, Any, Tuple
import hashlib
import json
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from app.core.redis import redis_client
from app.engine.llm.embeddings import OpenAIEmbeddingService


class MLCachePredictor:
    """ML-powered cache prediction and warming system"""

    def __init__(self):
        self.embedding_service = OpenAIEmbeddingService()
        self.similarity_threshold = 0.85
        self.cache_stats_key = "cache:stats"
        self.cache_patterns_key = "cache:patterns"
        self.warm_cache_prefix = "cache:warm:"

    async def predict_cache_hit(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], float]:
        """
        Predict if a query will hit cache using semantic similarity

        Args:
            query: Query string
            context: Additional context (user_id, project_id, etc.)

        Returns:
            Tuple of (will_hit, cache_key, confidence)
        """
        # Generate embedding for query
        query_embedding = await self.embedding_service.embed_text(query)

        # Get recent cache keys with embeddings
        pattern = "cache:query:*"
        cache_keys = await redis_client.keys(pattern)

        if not cache_keys:
            return False, None, 0.0

        # Find most similar cached query
        best_match = None
        best_similarity = 0.0

        for cache_key in cache_keys[:100]:  # Limit to recent 100
            # Get cached embedding
            cached_data = await redis_client.get(cache_key)
            if not cached_data:
                continue

            try:
                cached = json.loads(cached_data)
                if "embedding" not in cached:
                    continue

                cached_embedding = np.array(cached["embedding"])

                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_embedding, cached_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cache_key

            except (json.JSONDecodeError, KeyError):
                continue

        # Predict hit if similarity above threshold
        will_hit = best_similarity >= self.similarity_threshold
        confidence = best_similarity

        # Record prediction for learning
        await self._record_prediction(query, will_hit, confidence)

        return will_hit, best_match, confidence

    async def warm_cache(
        self,
        queries: List[str],
        executor_func,
        priority: int = 1
    ):
        """
        Warm cache with predicted queries

        Args:
            queries: List of queries to warm
            executor_func: Async function to execute query
            priority: Priority level (1=high, 2=medium, 3=low)
        """
        for query in queries:
            # Check if already cached
            cache_key = self._generate_cache_key(query)
            exists = await redis_client.exists(cache_key)

            if exists:
                continue

            # Add to warming queue
            await redis_client.zadd(
                "cache:warm:queue",
                {query: priority}
            )

        # Process warming queue in background
        asyncio.create_task(self._process_warm_queue(executor_func))

    async def learn_from_access(
        self,
        query: str,
        cache_hit: bool,
        execution_time: float,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Learn from cache access patterns

        Args:
            query: Query that was executed
            cache_hit: Whether it was a cache hit
            execution_time: Time taken to execute
            context: Additional context
        """
        # Update cache statistics
        stats_key = f"{self.cache_stats_key}:{datetime.now().strftime('%Y%m%d')}"

        await redis_client.hincrby(stats_key, "total_queries", 1)
        if cache_hit:
            await redis_client.hincrby(stats_key, "cache_hits", 1)

        # Set expiry for daily stats
        await redis_client.expire(stats_key, 86400 * 7)  # Keep for 7 days

        # Record query pattern
        pattern_key = f"{self.cache_patterns_key}:{self._hash_query(query)}"
        pattern_data = {
            "query": query,
            "last_access": datetime.now().isoformat(),
            "access_count": 1,
            "cache_hit": cache_hit,
            "avg_execution_time": execution_time
        }

        # Get existing pattern
        existing = await redis_client.get(pattern_key)
        if existing:
            try:
                existing_data = json.loads(existing)
                pattern_data["access_count"] = existing_data.get("access_count", 0) + 1

                # Update moving average
                old_avg = existing_data.get("avg_execution_time", execution_time)
                count = pattern_data["access_count"]
                pattern_data["avg_execution_time"] = (
                    (old_avg * (count - 1) + execution_time) / count
                )
            except json.JSONDecodeError:
                pass

        await redis_client.setex(
            pattern_key,
            86400 * 30,  # Keep for 30 days
            json.dumps(pattern_data)
        )

        # Predict future queries based on patterns
        await self._predict_next_queries(query, context)

    async def get_cache_recommendations(
        self,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recommended queries to cache based on patterns

        Args:
            user_id: Optional user ID filter
            project_id: Optional project ID filter
            limit: Max recommendations

        Returns:
            List of recommended queries with scores
        """
        # Get all pattern keys
        pattern_keys = await redis_client.keys(f"{self.cache_patterns_key}:*")

        recommendations = []

        for pattern_key in pattern_keys:
            pattern_data_str = await redis_client.get(pattern_key)
            if not pattern_data_str:
                continue

            try:
                pattern_data = json.loads(pattern_data_str)

                # Calculate recommendation score
                access_count = pattern_data.get("access_count", 0)
                avg_time = pattern_data.get("avg_execution_time", 0)
                last_access = datetime.fromisoformat(pattern_data.get("last_access"))
                recency = (datetime.now() - last_access).total_seconds() / 3600  # Hours

                # Score = frequency * execution_time / recency_penalty
                recency_penalty = max(1, recency / 24)  # Decay over days
                score = (access_count * avg_time) / recency_penalty

                recommendations.append({
                    "query": pattern_data.get("query"),
                    "score": score,
                    "access_count": access_count,
                    "avg_execution_time": avg_time,
                    "last_access": pattern_data.get("last_access")
                })

            except (json.JSONDecodeError, ValueError):
                continue

        # Sort by score and return top N
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:limit]

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        today = datetime.now().strftime('%Y%m%d')
        stats_key = f"{self.cache_stats_key}:{today}"

        total_queries = await redis_client.hget(stats_key, "total_queries")
        cache_hits = await redis_client.hget(stats_key, "cache_hits")

        total_queries = int(total_queries) if total_queries else 0
        cache_hits = int(cache_hits) if cache_hits else 0

        hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "cache_hits": cache_hits,
            "cache_misses": total_queries - cache_hits,
            "hit_rate": round(hit_rate, 2),
            "date": today
        }

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _generate_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"cache:query:{query_hash}"

    def _hash_query(self, query: str) -> str:
        """Generate hash for query pattern"""
        return hashlib.md5(query.encode()).hexdigest()[:16]

    async def _record_prediction(self, query: str, predicted_hit: bool, confidence: float):
        """Record prediction for model improvement"""
        prediction_key = f"cache:predictions:{datetime.now().strftime('%Y%m%d')}"

        prediction_data = {
            "query_hash": self._hash_query(query),
            "predicted_hit": predicted_hit,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }

        await redis_client.lpush(prediction_key, json.dumps(prediction_data))
        await redis_client.ltrim(prediction_key, 0, 999)  # Keep last 1000
        await redis_client.expire(prediction_key, 86400 * 7)  # 7 days

    async def _predict_next_queries(
        self,
        current_query: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Predict likely next queries based on patterns"""
        # Simple pattern: queries often follow each other
        # In production, use more sophisticated sequence models

        sequence_key = f"cache:sequences:{self._hash_query(current_query)}"

        # Record this query in sequence
        await redis_client.lpush(sequence_key, current_query)
        await redis_client.ltrim(sequence_key, 0, 9)  # Keep last 10
        await redis_client.expire(sequence_key, 86400)  # 1 day

    async def _process_warm_queue(self, executor_func):
        """Process cache warming queue in background"""
        while True:
            # Get highest priority query
            result = await redis_client.zpopmin("cache:warm:queue", 1)

            if not result:
                break

            query, priority = result[0]

            try:
                # Execute query to warm cache
                await executor_func(query)
            except Exception as e:
                # Log error but continue
                print(f"Cache warming error for query '{query}': {e}")

            # Small delay to avoid overwhelming system
            await asyncio.sleep(0.1)


# Global instance
ml_cache_predictor = MLCachePredictor()


# Decorator for automatic cache learning
def learn_cache_access(func):
    """Decorator to automatically learn from cache access patterns"""
    async def wrapper(*args, **kwargs):
        # Extract query from args/kwargs
        query = kwargs.get("query") or (args[0] if args else "")

        start_time = datetime.now()

        # Check if cache hit
        cache_key = ml_cache_predictor._generate_cache_key(str(query))
        cache_hit = await redis_client.exists(cache_key)

        # Execute function
        result = await func(*args, **kwargs)

        # Record execution time
        execution_time = (datetime.now() - start_time).total_seconds()

        # Learn from access
        await ml_cache_predictor.learn_from_access(
            query=str(query),
            cache_hit=bool(cache_hit),
            execution_time=execution_time
        )

        return result

    return wrapper
