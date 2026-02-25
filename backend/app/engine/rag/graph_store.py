"""GraphRAG 持久化存储。"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import Column, DateTime, Index, String, Text, and_, delete, select

from app.core.database import Base, async_session_factory


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _id(namespace: str, *parts: str) -> str:
    raw = "|".join([namespace, *[_norm(p) for p in parts]])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (
        Index("idx_graph_nodes_namespace_name", "namespace", "name"),
        Index("idx_graph_nodes_namespace_updated", "namespace", "updated_at"),
    )
    id = Column(String, primary_key=True)
    namespace = Column(String(128), index=True, nullable=False)
    name = Column(String(256), index=True, nullable=False)
    node_type = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (
        Index("idx_graph_edges_namespace_source", "namespace", "source_name"),
        Index("idx_graph_edges_namespace_target", "namespace", "target_name"),
        Index("idx_graph_edges_namespace_updated", "namespace", "updated_at"),
    )
    id = Column(String, primary_key=True)
    namespace = Column(String(128), index=True, nullable=False)
    source_name = Column(String(256), index=True, nullable=False)
    target_name = Column(String(256), index=True, nullable=False)
    relation = Column(String(128), nullable=False, default="related_to")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GraphStore:
    """基于 PostgreSQL 的轻量知识图谱持久层。"""

    async def upsert_entity_result(
        self,
        namespace: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> None:
        async with async_session_factory() as db:
            for e in entities:
                name = (e.get("name") or "").strip()
                if not name:
                    continue
                node_id = _id(namespace, "node", name)
                existing = await db.get(GraphNode, node_id)
                if existing:
                    existing.node_type = e.get("type") or existing.node_type
                    existing.description = e.get("description") or existing.description
                else:
                    db.add(
                        GraphNode(
                            id=node_id,
                            namespace=namespace,
                            name=name,
                            node_type=e.get("type", ""),
                            description=e.get("description", ""),
                        )
                    )

            for r in relationships:
                source = (r.get("from") or "").strip()
                target = (r.get("to") or "").strip()
                if not source or not target:
                    continue
                relation = (r.get("relation") or "related_to").strip()
                edge_id = _id(namespace, "edge", source, target, relation)
                existing = await db.get(GraphEdge, edge_id)
                if not existing:
                    db.add(
                        GraphEdge(
                            id=edge_id,
                            namespace=namespace,
                            source_name=source,
                            target_name=target,
                            relation=relation,
                        )
                    )
            await db.commit()

    async def query_context(self, namespace: str, query: str, limit: int = 12) -> List[str]:
        words = [w.strip().lower() for w in query.split() if w.strip()]
        if not words:
            return []
        async with async_session_factory() as db:
            # 节点命中
            ctx: List[str] = []
            for w in words[:6]:
                stmt_nodes = (
                    select(GraphNode)
                    .where(
                        and_(
                            GraphNode.namespace == namespace,
                            GraphNode.name.ilike(f"%{w}%"),
                        )
                    )
                    .limit(max(2, limit // 3))
                )
                nodes = (await db.execute(stmt_nodes)).scalars().all()
                for n in nodes:
                    ctx.append(f"{n.name}: {n.description or ''}".strip())

                stmt_edges = (
                    select(GraphEdge)
                    .where(
                        and_(
                            GraphEdge.namespace == namespace,
                            (GraphEdge.source_name.ilike(f"%{w}%") | GraphEdge.target_name.ilike(f"%{w}%")),
                        )
                    )
                    .limit(max(2, limit // 3))
                )
                edges = (await db.execute(stmt_edges)).scalars().all()
                for e in edges:
                    ctx.append(f"{e.source_name} --{e.relation}-> {e.target_name}")

            # 去重保序
            seen = set()
            unique = []
            for item in ctx:
                if item not in seen:
                    seen.add(item)
                    unique.append(item)
            return unique[:limit]

    async def prune_stale_data(self, max_age_days: int = 30, namespace: str | None = None) -> dict:
        """清理过期图谱数据。"""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        async with async_session_factory() as db:
            edge_stmt = delete(GraphEdge).where(GraphEdge.updated_at < cutoff)
            node_stmt = delete(GraphNode).where(GraphNode.updated_at < cutoff)
            if namespace:
                edge_stmt = edge_stmt.where(GraphEdge.namespace == namespace)
                node_stmt = node_stmt.where(GraphNode.namespace == namespace)

            edge_res = await db.execute(edge_stmt)
            node_res = await db.execute(node_stmt)
            await db.commit()
            return {
                "deleted_edges": edge_res.rowcount or 0,
                "deleted_nodes": node_res.rowcount or 0,
                "max_age_days": max_age_days,
                "namespace": namespace or "all",
            }

