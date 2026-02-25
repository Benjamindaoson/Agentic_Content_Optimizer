"""
Advanced RAG Algorithms
先进的 RAG 算法 (2025-2026 前沿研究)

算法:
1. Self-RAG (自我检索增强生成)
2. CRAG (Corrective RAG)
3. Adaptive RAG (自适应 RAG)
4. Graph RAG (图检索增强生成)
5. Multi-Hop RAG (多跳推理)
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from enum import Enum
import hashlib

from app.engine.rag.retrievers.hybrid_retriever import HybridRetriever
from app.engine.rag.graph_store import GraphStore
from app.engine.llm.unified import UnifiedLLM
from app.engine.llm.cost_router import get_llm_params
from app.core.semantic_cache import SemanticCache, semantic_cached

logger = logging.getLogger(__name__)


class RAGMode(str, Enum):
    """RAG 模式"""
    STANDARD = "standard"  # 标准 RAG
    SELF_RAG = "self_rag"  # 自我检索
    CRAG = "crag"  # 纠正性 RAG
    ADAPTIVE = "adaptive"  # 自适应 RAG
    GRAPH = "graph"  # 图 RAG
    MULTI_HOP = "multi_hop"  # 多跳 RAG


class SelfRAG:
    """
    Self-RAG (自我检索增强生成)

    论文: Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection

    核心思想:
    1. 判断是否需要检索
    2. 检索相关文档
    3. 生成答案
    4. 自我评估答案质量
    5. 如果质量不佳，重新检索或生成
    """

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.llm = UnifiedLLM()

    @semantic_cached
    async def generate(
        self,
        query: str,
        context: Dict[str, Any],
        max_iterations: int = 3
    ) -> str:
        """
        Self-RAG 生成

        Args:
            query: 查询
            context: 上下文
            max_iterations: 最大迭代次数

        Returns:
            生成结果
        """
        iterations = []

        for i in range(max_iterations):
            # 1. 判断是否需要检索
            need_retrieval = await self._should_retrieve(query, context, iterations)

            if need_retrieval:
                # 2. 检索文档
                documents = await self.retriever.hybrid_search(
                    query=query,
                    limit=5,
                    use_query_expansion=True,
                    use_reranking=True
                )
            else:
                documents = []

            # 3. 生成答案
            answer = await self._generate_answer(query, documents, context)

            # 4. 自我评估
            evaluation = await self._self_evaluate(query, answer, documents)

            # 5. 记录迭代
            iterations.append({
                "iteration": i + 1,
                "need_retrieval": need_retrieval,
                "num_documents": len(documents),
                "answer": answer,
                "evaluation": evaluation
            })

            # 6. 检查是否满意
            if evaluation.get("is_supported", False) and evaluation.get("is_relevant", False):
                break

        return {
            "query": query,
            "final_answer": iterations[-1]["answer"],
            "iterations": iterations,
            "num_iterations": len(iterations)
        }

    async def _should_retrieve(
        self,
        query: str,
        context: Dict[str, Any],
        previous_iterations: List[Dict[str, Any]]
    ) -> bool:
        """
        规则引擎判断是否需要检索（零 LLM 调用）。
        原来用一次 LLM 调用来做一个布尔判断，ROI 极低。
        """
        if not previous_iterations:
            return True

        last_eval = previous_iterations[-1].get("evaluation", {})
        if not last_eval.get("is_supported", False):
            return True
        if not last_eval.get("is_relevant", False):
            return True
        if last_eval.get("confidence", 0) < 0.6:
            return True

        return False

    async def _generate_answer(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        context: Dict[str, Any],
        max_context_length: int = 8000  # 最大上下文长度（字符数）
    ) -> str:
        """生成答案（带上下文长度限制）"""
        if documents:
            # 构建上下文，添加长度限制
            doc_texts = []
            current_length = 0

            for i, doc in enumerate(documents):
                doc_text = f"Document {i+1}:\n{doc.get('content', '')}"
                doc_length = len(doc_text)

                # 检查是否超过限制
                if current_length + doc_length > max_context_length:
                    # 截断最后一个文档
                    remaining = max_context_length - current_length
                    if remaining > 100:  # 至少保留100字符
                        doc_text = doc_text[:remaining] + "...[truncated]"
                        doc_texts.append(doc_text)
                    break

                doc_texts.append(doc_text)
                current_length += doc_length

            doc_context = "\n\n".join(doc_texts)

            # 记录截断信息
            if len(doc_texts) < len(documents):
                logger.warning(
                    f"Context truncated: {len(documents)} documents -> {len(doc_texts)} documents "
                    f"(max_length={max_context_length}, actual_length={current_length})"
                )

            prompt = f"""Query: {query}

Context: {context}

Retrieved documents:
{doc_context}

Based on the retrieved documents, generate a comprehensive answer to the query.

Answer:"""
        else:
            prompt = f"""Query: {query}

Context: {context}

Generate an answer to the query based on your knowledge.

Answer:"""

        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("content_generation"),
            )

            return answer

        except Exception as e:
            logger.error(f"Generate answer error: {e}")
            return "Error generating answer"

    async def _self_evaluate(
        self,
        query: str,
        answer: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """自我评估答案质量"""
        doc_context = "\n\n".join([
            f"Document {i+1}:\n{doc.get('content', '')[:500]}"
            for i, doc in enumerate(documents)
        ]) if documents else "No documents"

        prompt = f"""Query: {query}

Answer: {answer}

Retrieved documents:
{doc_context}

Evaluate the answer on these criteria:
1. Is the answer supported by the retrieved documents? (is_supported)
2. Is the answer relevant to the query? (is_relevant)
3. Is the answer complete? (is_complete)
4. What is the confidence level? (confidence: 0-1)

Respond in JSON format:
{{
  "is_supported": true/false,
  "is_relevant": true/false,
  "is_complete": true/false,
  "confidence": 0.0-1.0,
  "issues": ["..."]
}}"""

        try:
            evaluation = await self.llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={
                    "is_supported": "boolean",
                    "is_relevant": "boolean",
                    "is_complete": "boolean",
                    "confidence": "number",
                    "issues": "array"
                },
                **get_llm_params("quality_evaluation"),
            )

            return evaluation

        except Exception as e:
            logger.error(f"Self-evaluate error: {e}")
            return {
                "is_supported": True,
                "is_relevant": True,
                "is_complete": True,
                "confidence": 0.5,
                "issues": []
            }


class CorrectiveRAG:
    """
    CRAG (Corrective RAG)

    论文: Corrective Retrieval Augmented Generation

    核心思想:
    1. 检索文档
    2. 评估文档相关性
    3. 如果相关性低，使用 Web 搜索补充
    4. 提取关键信息
    5. 生成答案
    """

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.llm = UnifiedLLM()

    async def generate(
        self,
        query: str,
        context: Dict[str, Any],
        relevance_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        CRAG 生成

        Args:
            query: 查询
            context: 上下文
            relevance_threshold: 相关性阈值

        Returns:
            生成结果
        """
        # 1. 检索文档
        documents = await self.retriever.hybrid_search(
            query=query,
            limit=5,
            use_query_expansion=True,
            use_reranking=True
        )

        # 2. 评估文档相关性
        relevance_scores = await self._evaluate_relevance(query, documents)

        # 3. 过滤低相关性文档
        relevant_docs = [
            doc for doc, score in zip(documents, relevance_scores)
            if score >= relevance_threshold
        ]

        # 4. 如果相关文档不足，使用 Web 搜索
        if len(relevant_docs) < 3:
            web_docs = await self._web_search(query)
            relevant_docs.extend(web_docs)

        # 5. 提取关键信息
        key_information = await self._extract_key_information(query, relevant_docs)

        # 6. 生成答案
        answer = await self._generate_answer(query, key_information, context)

        return {
            "query": query,
            "answer": answer,
            "num_retrieved_docs": len(documents),
            "num_relevant_docs": len(relevant_docs),
            "relevance_scores": relevance_scores,
            "key_information": key_information
        }

    async def _evaluate_relevance(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[float]:
        """
        批量评估文档相关性（单次 LLM 调用替代 N 次顺序调用）。
        原来逐个调用 LLM 评估相关性，N 篇文档就要 N 次网络往返，
        现在合并为一次调用，延迟从 N*1s 降到 ~1s。
        """
        if not documents:
            return []

        doc_texts = "\n---\n".join([
            f"[Doc {i+1}]: {doc.get('content', '')[:300]}"
            for i, doc in enumerate(documents)
        ])

        prompt = f"""Query: {query}

Evaluate the relevance of EACH document below to the query.

{doc_texts}

Return a JSON array of relevance scores (0.0-1.0), one per document, in order.
Example for 3 docs: [0.8, 0.3, 0.9]"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("relevance_check"),
            )

            import json, re
            match = re.search(r'\[[\d.,\s]+\]', response)
            if match:
                scores = json.loads(match.group())
                if len(scores) == len(documents):
                    return [max(0.0, min(1.0, float(s))) for s in scores]

            logger.warning("Relevance scores parse failed, using defaults")
            return [0.5] * len(documents)

        except Exception as e:
            logger.error(f"Batch evaluate relevance error: {e}")
            return [0.5] * len(documents)

    async def _web_search(self, query: str) -> List[Dict[str, Any]]:
        """Web search using configurable search API (Tavily or SerpAPI)."""
        import httpx
        from app.core.config import get_settings
        settings = get_settings()

        logger.info(f"Web search for: {query}")

        # Try Tavily first, then SerpAPI, then fallback
        tavily_key = getattr(settings, 'TAVILY_API_KEY', None)
        serp_key = getattr(settings, 'SERPAPI_KEY', None)

        try:
            if tavily_key:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={"api_key": tavily_key, "query": query, "max_results": 3},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return [
                        {"content": r.get("content", ""), "source": "web", "url": r.get("url", "")}
                        for r in data.get("results", [])
                    ]

            elif serp_key:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://serpapi.com/search",
                        params={"q": query, "api_key": serp_key, "num": 3},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return [
                        {"content": r.get("snippet", ""), "source": "web", "url": r.get("link", "")}
                        for r in data.get("organic_results", [])[:3]
                    ]

        except Exception as e:
            logger.warning(f"Web search failed: {e}")

        # Fallback: use LLM knowledge
        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": f"Provide key facts about: {query}"}],
                **get_llm_params("relevance_check"),
            )
            return [{"content": answer, "source": "llm_knowledge", "url": ""}]
        except Exception:
            return []

    async def _extract_key_information(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """提取关键信息"""
        doc_context = "\n\n".join([
            f"Document {i+1}:\n{doc.get('content', '')}"
            for i, doc in enumerate(documents)
        ])

        prompt = f"""Query: {query}

Documents:
{doc_context}

Extract the key information from these documents that is relevant to answering the query.
Return a list of key facts or statements.

Respond in JSON format:
{{
  "key_information": ["fact 1", "fact 2", ...]
}}"""

        try:
            response = await self.llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"key_information": "array"},
                **get_llm_params("trend_extraction"),
            )

            return response.get("key_information", [])

        except Exception as e:
            logger.error(f"Extract key information error: {e}")
            return []

    async def _generate_answer(
        self,
        query: str,
        key_information: List[str],
        context: Dict[str, Any]
    ) -> str:
        """生成答案"""
        info_text = "\n".join([f"- {info}" for info in key_information])

        prompt = f"""Query: {query}

Context: {context}

Key information:
{info_text}

Based on the key information, generate a comprehensive and accurate answer to the query.

Answer:"""

        try:
            answer = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("content_generation"),
            )

            return answer

        except Exception as e:
            logger.error(f"Generate answer error: {e}")
            return "Error generating answer"


class AdaptiveRAG:
    """
    Adaptive RAG (自适应 RAG)

    核心思想:
    根据查询复杂度自动选择最佳 RAG 策略
    """

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.llm = UnifiedLLM()
        self.self_rag = SelfRAG(retriever)
        self.crag = CorrectiveRAG(retriever)

    @semantic_cached
    async def generate(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> str:
        """
        自适应生成

        Args:
            query: 查询
            context: 上下文

        Returns:
            生成结果
        """
        # 1. 分析查询复杂度
        complexity = await self._analyze_query_complexity(query)

        # 2. 选择策略
        if complexity["level"] == "simple":
            # 简单查询：标准 RAG
            strategy = "standard"
            result = await self._standard_rag(query, context)
        elif complexity["level"] == "medium":
            # 中等复杂度：CRAG
            strategy = "crag"
            result = await self.crag.generate(query, context)
        else:
            # 高复杂度：Self-RAG
            strategy = "self_rag"
            result = await self.self_rag.generate(query, context)

        return {
            "query": query,
            "complexity": complexity,
            "strategy": strategy,
            "result": result
        }

    async def _analyze_query_complexity(self, query: str) -> Dict[str, Any]:
        """
        规则引擎判断查询复杂度（零 LLM 调用）。
        替代原来的 LLM 调用，节省 ~$0.001/次 且延迟从 ~1s 降到 <1ms。
        """
        words = len(query)
        has_comparison = any(w in query for w in [
            "对比", "区别", "哪个", "vs", "还是", "好还是", "比较"
        ])
        has_multi_step = any(w in query for w in [
            "怎么", "如何", "步骤", "流程", "方法", "教程", "指南"
        ])
        has_reasoning = any(w in query for w in [
            "为什么", "原因", "分析", "影响", "趋势", "预测"
        ])
        is_ambiguous = words < 5

        if words < 10 and not has_comparison and not has_multi_step and not has_reasoning:
            level = "simple"
        elif has_comparison or has_reasoning or (has_multi_step and words > 20):
            level = "complex"
        else:
            level = "medium"

        return {
            "level": level,
            "requires_multi_step": has_multi_step,
            "requires_reasoning": has_reasoning or has_comparison,
            "is_ambiguous": is_ambiguous,
            "requires_expertise": False,
        }

    async def _standard_rag(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """标准 RAG"""
        # 检索
        documents = await self.retriever.hybrid_search(
            query=query,
            limit=5
        )

        # 生成
        doc_context = "\n\n".join([
            f"Document {i+1}:\n{doc.get('content', '')}"
            for i, doc in enumerate(documents)
        ])

        prompt = f"""Query: {query}

Context: {context}

Retrieved documents:
{doc_context}

Answer:"""

        answer = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            **get_llm_params("content_generation"),
        )

        return {
            "answer": answer,
            "documents": documents
        }


class GraphRAG:
    """
    Graph RAG — Knowledge graph-based retrieval augmented generation.

    1. Build knowledge graph from documents using LLM entity extraction
    2. Store relationships in networkx graph
    3. Traverse graph for multi-hop context retrieval
    4. Combine with vector search for hybrid results
    """

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.llm = UnifiedLLM()
        self.graph_store = GraphStore()
        try:
            import networkx as nx
            self.graph = nx.DiGraph()
        except ImportError:
            self.graph = None
            logger.warning("networkx not available for GraphRAG")

    async def generate(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Graph RAG generation."""
        # 1. Retrieve documents via vector search
        documents = await self.retriever.hybrid_search(query=query, limit=5, use_reranking=True)

        # 2. Extract entities and relationships from documents
        entities = await self._extract_entities(documents)

        # 3. Build/update knowledge graph（内存 + 持久化）
        await self._update_graph(query=query, entity_results=entities)

        # 4. Traverse graph for related context
        graph_context = await self._traverse_graph(query, entities)

        # 5. Combine vector results with graph context
        combined_context = self._merge_contexts(documents, graph_context)

        # 6. Generate answer
        answer = await self._generate_with_graph(query, combined_context, context)

        return {
            "query": query,
            "answer": answer,
            "num_documents": len(documents),
            "num_entities": len(entities),
            "graph_nodes": self.graph.number_of_nodes() if self.graph else 0,
            "graph_edges": self.graph.number_of_edges() if self.graph else 0,
        }

    async def _extract_entities(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract entities and relationships from documents using LLM."""
        all_entities = []
        for doc in documents[:3]:  # Limit to avoid excessive LLM calls
            content = doc.get("content", "")[:1500]
            prompt = f"""Extract key entities and their relationships from this text.

Text: {content}

Return JSON:
{{
  "entities": [
    {{"name": "entity_name", "type": "person/concept/metric/strategy", "description": "brief description"}},
    ...
  ],
  "relationships": [
    {{"from": "entity_a", "to": "entity_b", "relation": "causes/improves/part_of/related_to"}},
    ...
  ]
}}"""
            try:
                result = await self.llm.structured_output(
                    messages=[{"role": "user", "content": prompt}],
                    schema={"entities": "array", "relationships": "array"},
                    **get_llm_params("trend_extraction"),
                )
                all_entities.append(result)
            except Exception as e:
                logger.warning(f"Entity extraction failed: {e}")

        return all_entities

    async def _update_graph(self, query: str, entity_results: List[Dict[str, Any]]):
        """Add extracted entities and relationships to graph and persistent store."""
        namespace = f"rag:{hashlib.md5(query[:200].encode('utf-8')).hexdigest()}"
        if not self.graph:
            # 即使没有 networkx，也落持久化图谱
            for result in entity_results:
                await self.graph_store.upsert_entity_result(
                    namespace=namespace,
                    entities=result.get("entities", []),
                    relationships=result.get("relationships", []),
                )
            return
        for result in entity_results:
            for entity in result.get("entities", []):
                self.graph.add_node(
                    entity.get("name", ""),
                    type=entity.get("type", ""),
                    description=entity.get("description", ""),
                )
            for rel in result.get("relationships", []):
                self.graph.add_edge(
                    rel.get("from", ""),
                    rel.get("to", ""),
                    relation=rel.get("relation", "related_to"),
                )
            await self.graph_store.upsert_entity_result(
                namespace=namespace,
                entities=result.get("entities", []),
                relationships=result.get("relationships", []),
            )

    async def _traverse_graph(self, query: str, entities: List[Dict[str, Any]]) -> List[str]:
        """Traverse the knowledge graph for related context."""
        namespace = f"rag:{hashlib.md5(query[:200].encode('utf-8')).hexdigest()}"
        persisted_context = await self.graph_store.query_context(namespace=namespace, query=query, limit=10)
        if not self.graph or self.graph.number_of_nodes() == 0:
            return persisted_context

        import networkx as nx

        # Find query-related nodes
        query_words = set(query.lower().split())
        seed_nodes = [
            n for n in self.graph.nodes()
            if any(w in str(n).lower() for w in query_words)
        ]

        if not seed_nodes:
            seed_nodes = list(self.graph.nodes())[:3]

        # BFS from seed nodes (2-hop)
        context_items = []
        visited = set()
        for seed in seed_nodes[:5]:
            for neighbor in nx.bfs_tree(self.graph, seed, depth_limit=2):
                if neighbor not in visited:
                    visited.add(neighbor)
                    node_data = self.graph.nodes[neighbor]
                    desc = node_data.get("description", "")
                    # Get edges info
                    edges_info = []
                    for _, target, data in self.graph.edges(neighbor, data=True):
                        edges_info.append(f"{neighbor} --{data.get('relation', '')}-> {target}")
                    context_items.append(f"{neighbor}: {desc}. Relations: {'; '.join(edges_info[:3])}")

        return (context_items + persisted_context)[:12]

    def _merge_contexts(
        self, documents: List[Dict[str, Any]], graph_context: List[str]
    ) -> str:
        """Merge vector search results with graph traversal context."""
        parts = []
        for i, doc in enumerate(documents[:3]):
            parts.append(f"[Doc {i+1}] {doc.get('content', '')[:500]}")
        if graph_context:
            parts.append("\n[Knowledge Graph Context]")
            parts.extend(graph_context)
        return "\n\n".join(parts)

    async def _generate_with_graph(
        self, query: str, combined_context: str, context: Dict[str, Any]
    ) -> str:
        """Generate answer using combined vector + graph context."""
        prompt = f"""Query: {query}

Context: {context}

Retrieved information (documents + knowledge graph):
{combined_context}

Generate a comprehensive answer using both the retrieved documents and the knowledge graph relationships.

Answer:"""
        try:
            return await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("content_generation"),
            )
        except Exception as e:
            logger.error(f"Graph RAG generation failed: {e}")
            return "Error generating answer"


class MultiHopRAG:
    """
    Multi-Hop RAG — Iterative retrieval with intermediate reasoning.

    1. Decompose complex queries into sub-queries
    2. Iterative retrieval with intermediate reasoning
    3. Answer aggregation from multiple retrieval steps
    """

    def __init__(self, retriever: HybridRetriever, max_hops: int = 3):
        self.retriever = retriever
        self.llm = UnifiedLLM()
        self.max_hops = max_hops

    async def generate(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Multi-hop RAG generation."""
        # 1. Decompose query into sub-queries
        sub_queries = await self._decompose_query(query)

        # 2. Iterative retrieval and reasoning
        hop_results = []
        accumulated_knowledge = ""

        for i, sub_query in enumerate(sub_queries[:self.max_hops]):
            # Retrieve for this sub-query (incorporating previous knowledge)
            enhanced_query = f"{sub_query} (context: {accumulated_knowledge[:300]})" if accumulated_knowledge else sub_query
            documents = await self.retriever.hybrid_search(
                query=enhanced_query, limit=3, use_reranking=True,
            )

            # Intermediate reasoning
            reasoning = await self._intermediate_reasoning(
                sub_query, documents, accumulated_knowledge,
            )

            hop_results.append({
                "hop": i + 1,
                "sub_query": sub_query,
                "num_docs": len(documents),
                "reasoning": reasoning,
            })

            accumulated_knowledge += f"\nHop {i+1}: {reasoning}"

        # 3. Final answer aggregation
        final_answer = await self._aggregate_answer(query, hop_results, context)

        return {
            "query": query,
            "answer": final_answer,
            "num_hops": len(hop_results),
            "sub_queries": [h["sub_query"] for h in hop_results],
            "hop_results": hop_results,
        }

    async def _decompose_query(self, query: str) -> List[str]:
        """Decompose a complex query into simpler sub-queries."""
        prompt = f"""Decompose this complex query into 2-4 simpler sub-queries that can be answered step by step.

Query: {query}

Return JSON:
{{
  "sub_queries": ["sub-query 1", "sub-query 2", ...]
}}"""
        try:
            result = await self.llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                schema={"sub_queries": "array"},
                **get_llm_params("query_expansion"),
            )
            sub_queries = result.get("sub_queries", [query])
            return sub_queries if sub_queries else [query]
        except Exception as e:
            logger.warning(f"Query decomposition failed: {e}")
            return [query]

    async def _intermediate_reasoning(
        self,
        sub_query: str,
        documents: List[Dict[str, Any]],
        accumulated_knowledge: str,
    ) -> str:
        """Perform intermediate reasoning for one hop."""
        doc_text = "\n".join([
            f"- {doc.get('content', '')[:400]}" for doc in documents
        ])
        prompt = f"""Sub-query: {sub_query}

Previous knowledge: {accumulated_knowledge[:500] if accumulated_knowledge else 'None'}

Retrieved documents:
{doc_text}

Based on the retrieved documents and previous knowledge, provide a concise answer to the sub-query.

Answer:"""
        try:
            return await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("multi_hop_reasoning"),
            )
        except Exception as e:
            logger.warning(f"Intermediate reasoning failed: {e}")
            return ""

    async def _aggregate_answer(
        self,
        original_query: str,
        hop_results: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """Aggregate all hop results into a final answer."""
        reasoning_chain = "\n".join([
            f"Step {h['hop']} ({h['sub_query']}): {h['reasoning']}"
            for h in hop_results
        ])
        prompt = f"""Original query: {original_query}

Context: {context}

Multi-step reasoning:
{reasoning_chain}

Now synthesize all the intermediate findings into a comprehensive final answer.

Final Answer:"""
        try:
            return await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                **get_llm_params("multi_hop_reasoning"),
            )
        except Exception as e:
            logger.error(f"Answer aggregation failed: {e}")
            return hop_results[-1]["reasoning"] if hop_results else "Error generating answer"


# Factory function
def create_advanced_rag(retriever: HybridRetriever, mode: RAGMode = RAGMode.ADAPTIVE):
    """Create an advanced RAG instance."""
    if mode == RAGMode.SELF_RAG:
        return SelfRAG(retriever)
    elif mode == RAGMode.CRAG:
        return CorrectiveRAG(retriever)
    elif mode == RAGMode.ADAPTIVE:
        return AdaptiveRAG(retriever)
    elif mode == RAGMode.GRAPH:
        return GraphRAG(retriever)
    elif mode == RAGMode.MULTI_HOP:
        return MultiHopRAG(retriever)
    else:
        return AdaptiveRAG(retriever)
