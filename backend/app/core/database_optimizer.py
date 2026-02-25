"""
Database Query Optimization Utilities
Provides optimized queries with eager loading and caching
"""

from typing import List, Optional, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from functools import wraps
import hashlib
import json

from app.core.redis import redis_client

T = TypeVar('T')


class QueryOptimizer:
    """Optimize database queries with eager loading and caching"""

    @staticmethod
    def with_relationships(query, model, relationships: List[str]):
        """
        Add eager loading for relationships to avoid N+1 queries

        Example:
            query = select(Project)
            query = QueryOptimizer.with_relationships(
                query, Project, ['episodes', 'user']
            )
        """
        for rel in relationships:
            if hasattr(model, rel):
                query = query.options(selectinload(getattr(model, rel)))
        return query

    @staticmethod
    def with_joined_load(query, model, relationships: List[str]):
        """
        Add joined loading for relationships (use for one-to-one)

        Example:
            query = select(Episode)
            query = QueryOptimizer.with_joined_load(
                query, Episode, ['project']
            )
        """
        for rel in relationships:
            if hasattr(model, rel):
                query = query.options(joinedload(getattr(model, rel)))
        return query

    @staticmethod
    async def get_with_cache(
        db: AsyncSession,
        model: Type[T],
        id: int,
        cache_ttl: int = 300,
        relationships: Optional[List[str]] = None
    ) -> Optional[T]:
        """
        Get entity by ID with Redis caching

        Args:
            db: Database session
            model: SQLAlchemy model class
            id: Entity ID
            cache_ttl: Cache TTL in seconds
            relationships: List of relationships to eager load
        """

        # Generate cache key
        cache_key = f"{model.__tablename__}:{id}"

        # Try to get from cache
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query database
        query = select(model).where(model.id == id)

        if relationships:
            query = QueryOptimizer.with_relationships(query, model, relationships)

        result = await db.execute(query)
        entity = result.scalar_one_or_none()

        if entity:
            # Cache the result
            await redis_client.setex(
                cache_key,
                cache_ttl,
                json.dumps(entity.dict() if hasattr(entity, 'dict') else str(entity))
            )

        return entity

    @staticmethod
    async def list_with_cache(
        db: AsyncSession,
        model: Type[T],
        filters: dict,
        cache_ttl: int = 300,
        relationships: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[T]:
        """
        List entities with caching

        Args:
            db: Database session
            model: SQLAlchemy model class
            filters: Filter conditions
            cache_ttl: Cache TTL in seconds
            relationships: List of relationships to eager load
            limit: Max results
            offset: Offset for pagination
        """

        # Generate cache key from filters
        filter_str = json.dumps(filters, sort_keys=True)
        cache_key = f"{model.__tablename__}:list:{hashlib.md5(filter_str.encode()).hexdigest()}:{offset}:{limit}"

        # Try to get from cache
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Build query
        query = select(model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(model, key):
                query = query.where(getattr(model, key) == value)

        # Add eager loading
        if relationships:
            query = QueryOptimizer.with_relationships(query, model, relationships)

        # Add pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        entities = result.scalars().all()

        # Cache the result
        await redis_client.setex(
            cache_key,
            cache_ttl,
            json.dumps([e.dict() if hasattr(e, 'dict') else str(e) for e in entities])
        )

        return entities

    @staticmethod
    async def invalidate_cache(model: Type[T], id: Optional[int] = None):
        """
        Invalidate cache for a model

        Args:
            model: SQLAlchemy model class
            id: Optional entity ID (if None, invalidates all)
        """

        if id:
            cache_key = f"{model.__tablename__}:{id}"
            await redis_client.delete(cache_key)
        else:
            # Invalidate all list caches for this model
            pattern = f"{model.__tablename__}:list:*"
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)


def cache_query(ttl: int = 300):
    """
    Decorator to cache query results

    Usage:
        @cache_query(ttl=600)
        async def get_project_stats(db, project_id):
            # ... query logic
            return stats
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)
            cache_key = f"query:{hashlib.md5(cache_key.encode()).hexdigest()}"

            # Try to get from cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Execute function
            result = await func(*args, **kwargs)

            # Cache the result
            await redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )

            return result

        return wrapper

    return decorator


# Example usage in API endpoints:
"""
from app.core.database_optimizer import QueryOptimizer, cache_query

# In your API endpoint:
@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db)
):
    # Use optimized query with eager loading and caching
    project = await QueryOptimizer.get_with_cache(
        db=db,
        model=Project,
        id=project_id,
        cache_ttl=600,
        relationships=['episodes', 'user']  # Avoid N+1 queries
    )
    return project

# Or use decorator for complex queries:
@cache_query(ttl=600)
async def get_project_stats(db: AsyncSession, project_id: int):
    # Complex aggregation query
    query = select(
        func.count(Episode.id),
        func.avg(Episode.total_reward)
    ).where(Episode.project_id == project_id)

    result = await db.execute(query)
    return result.first()
"""
