"""
Real data collector using XHS crawler.
Replaces mock data with actual viral content from Xiaohongshu.
"""

import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import XHSNote, XHSMetrics, XHSCover, XHSAnalysis, Pattern, PatternSample
from app.data.crawlers.xhs_crawler import SpiderXHSAdapter, XiaohongshuNote


class RealDataCollector:
    """
    Real data collector using XHS crawler.
    """

    def __init__(self, db: AsyncSession, use_real_crawler: bool = False):
        self.db = db
        self.use_real_crawler = use_real_crawler
        self.crawler = SpiderXHSAdapter(use_mediacrawler=use_real_crawler, headless=True)

    async def collect_viral_notes(
        self,
        category: str = "美妆",
        target_count: int = 1000,
        min_likes: int = 10000
    ) -> Dict[str, Any]:
        """
        Collect real viral notes from Xiaohongshu.

        Args:
            category: Category to crawl
            target_count: Number of notes to collect
            min_likes: Minimum likes threshold for viral content

        Returns:
            {
                "collected": int,
                "analyzed": int,
                "patterns_extracted": int,
                "errors": List[str]
            }
        """
        print(f"Starting real data collection: category={category}, target={target_count}")

        collected = 0
        analyzed = 0
        patterns_extracted = 0
        errors = []

        try:
            # Crawl notes in batches
            batch_size = 100
            batches = (target_count + batch_size - 1) // batch_size

            for batch_num in range(batches):
                print(f"\nBatch {batch_num + 1}/{batches}")

                try:
                    # Crawl batch
                    notes = await self.crawler.crawl_notes(
                        category=category,
                        time_window="30d",
                        limit=min(batch_size, target_count - collected)
                    )

                    # Process each note
                    for note_data in notes:
                        try:
                            # Filter by likes
                            if note_data.likes < min_likes:
                                continue

                            # Check if already exists
                            existing = await self.db.execute(
                                select(XHSNote).where(XHSNote.note_id == note_data.note_id)
                            )
                            if existing.scalar_one_or_none():
                                print(f"  Note {note_data.note_id} already exists, skipping")
                                continue

                            # Create note
                            note = XHSNote(
                                note_id=note_data.note_id,
                                title=note_data.title,
                                text=note_data.text,
                                cover_url=note_data.cover_url,
                                image_urls=note_data.image_urls,
                                author_id=note_data.author_id,
                                author_name=note_data.author_name,
                                publish_time=note_data.publish_time,
                                category=category,
                                tags=note_data.tags,
                                is_viral=True,
                                analysis_status="pending",
                                raw_metadata=note_data.raw_metadata
                            )
                            self.db.add(note)

                            # Create metrics
                            metrics = XHSMetrics(
                                note_id=note_data.note_id,
                                views=note_data.views,
                                likes=note_data.likes,
                                comments=note_data.comments,
                                collects=note_data.collects,
                                shares=note_data.shares,
                                follows=note_data.follows
                            )

                            # Calculate engagement rate
                            if metrics.views > 0:
                                metrics.engagement_rate = (
                                    metrics.likes + metrics.comments + metrics.collects
                                ) / metrics.views

                            # Calculate viral score
                            metrics.viral_score = min(1.0, (
                                metrics.engagement_rate * 5 +
                                (metrics.likes / 10000) * 0.3 +
                                (metrics.collects / 5000) * 0.2
                            ))

                            self.db.add(metrics)

                            # Create cover record
                            cover = XHSCover(
                                note_id=note_data.note_id,
                                download_status="pending",
                                layout="unknown",
                                dominant_color="#FFFFFF"
                            )
                            self.db.add(cover)

                            await self.db.commit()
                            collected += 1
                            print(f"  Collected note {collected}/{target_count}: {note_data.note_id}")

                            # Analyze note (simplified for now)
                            analysis = await self._analyze_note(note_data)
                            if analysis:
                                self.db.add(analysis)
                                await self.db.commit()
                                analyzed += 1

                                # Extract pattern
                                pattern = await self._extract_pattern(note, metrics, analysis)
                                if pattern:
                                    patterns_extracted += 1
                                    print(f"  Extracted pattern: {pattern.pattern_id}")

                            if collected >= target_count:
                                break

                        except Exception as e:
                            errors.append(f"Failed to process note: {str(e)}")
                            print(f"  Error: {str(e)}")
                            continue

                    if collected >= target_count:
                        break

                    # Rate limiting between batches
                    await asyncio.sleep(5)

                except Exception as e:
                    errors.append(f"Batch {batch_num + 1} failed: {str(e)}")
                    print(f"  Batch error: {str(e)}")
                    continue

        except Exception as e:
            errors.append(f"Collection error: {str(e)}")
            print(f"Collection error: {str(e)}")

        result = {
            "collected": collected,
            "analyzed": analyzed,
            "patterns_extracted": patterns_extracted,
            "errors": errors
        }

        print(f"\nCollection complete:")
        print(f"   Collected: {collected}")
        print(f"   Analyzed: {analyzed}")
        print(f"   Patterns: {patterns_extracted}")
        print(f"   Errors: {len(errors)}")

        return result

    async def _analyze_note(self, note_data: XiaohongshuNote) -> XHSAnalysis:
        """
        Analyze note structure (simplified version).
        In production, this would use LLM for deep analysis.
        """
        # Simple heuristic analysis
        text = note_data.text.lower()

        # Detect hook type
        hook_type = "unknown"
        if "?" in note_data.title or "吗" in note_data.title:
            hook_type = "question"
        elif "故事" in text or "经历" in text:
            hook_type = "story"
        elif "!" in note_data.title or "震惊" in text:
            hook_type = "shock"
        elif "教程" in text or "方法" in text:
            hook_type = "benefit"

        # Detect body type
        body_type = "unknown"
        if "1." in text or "①" in text or "第一" in text:
            body_type = "list"
        elif "步骤" in text or "教程" in text:
            body_type = "tutorial"
        elif "vs" in text or "对比" in text:
            body_type = "comparison"

        # Detect CTA type
        cta_type = "unknown"
        if "点赞" in text:
            cta_type = "like"
        elif "收藏" in text:
            cta_type = "collect"
        elif "关注" in text:
            cta_type = "follow"
        elif "评论" in text:
            cta_type = "comment"

        analysis = XHSAnalysis(
            note_id=note_data.note_id,
            structure={
                "hook": hook_type,
                "body": body_type,
                "cta": cta_type
            },
            emotion={
                "primary": "positive",
                "intensity": 0.7
            },
            topics={
                "main": note_data.category or "unknown",
                "keywords": note_data.tags
            },
            visual={
                "layout": "unknown",
                "color": "#FFFFFF"
            },
            timing={
                "publish_hour": note_data.publish_time.hour if note_data.publish_time else 0
            },
            audience={
                "age_range": "18-35"
            }
        )

        return analysis

    async def _extract_pattern(
        self,
        note: XHSNote,
        metrics: XHSMetrics,
        analysis: XHSAnalysis
    ) -> Pattern:
        """
        Extract reusable pattern from analyzed note.
        """
        structure = analysis.structure or {}
        hook_type = structure.get("hook", "unknown")
        body_type = structure.get("body", "unknown")
        cta_type = structure.get("cta", "unknown")

        # Check if similar pattern exists
        existing = await self.db.execute(
            select(Pattern).where(
                Pattern.hook_template == hook_type,
                Pattern.body_structure == {"type": body_type},
                Pattern.cta_template == cta_type
            )
        )
        pattern = existing.scalar_one_or_none()

        if pattern:
            # Update existing pattern
            pattern.sample_size += 1
            pattern.avg_viral_score = (
                (pattern.avg_viral_score * (pattern.sample_size - 1) + metrics.viral_score)
                / pattern.sample_size
            )
            pattern.avg_engagement_rate = (
                (pattern.avg_engagement_rate * (pattern.sample_size - 1) + metrics.engagement_rate)
                / pattern.sample_size
            )
            pattern.thompson_alpha += 1
            pattern.success_rate = pattern.thompson_alpha / (
                pattern.thompson_alpha + pattern.thompson_beta
            )
        else:
            # Create new pattern
            pattern_id = f"pattern_{uuid.uuid4().hex[:8]}"
            pattern = Pattern(
                pattern_id=pattern_id,
                category=note.category,
                name=f"{hook_type}-{body_type}-{cta_type}",
                hook_template=hook_type,
                body_structure={"type": body_type},
                cta_template=cta_type,
                keywords=note.tags or [],
                emotion_curve=[0.5, 0.7, 0.9],
                cover_layout="unknown",
                dominant_color="#FFFFFF",
                visual_elements=["text"],
                success_rate=1.0,
                sample_size=1,
                avg_viral_score=metrics.viral_score,
                avg_views=float(metrics.views),
                avg_engagement_rate=metrics.engagement_rate,
                thompson_alpha=2.0,
                thompson_beta=1.0,
                version=1
            )
            self.db.add(pattern)

        await self.db.commit()

        # Create pattern sample link
        sample = PatternSample(
            pattern_id=pattern.pattern_id,
            note_id=note.note_id,
            contribution_score=1.0
        )
        self.db.add(sample)
        await self.db.commit()

        return pattern
