"""
MVP Historical Data Collector
Uses mock data for quick validation of the training pipeline.
"""

import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import XHSNote, XHSMetrics, XHSCover, XHSAnalysis, Pattern, PatternSample


class HistoricalDataCollectorMVP:
    """
    MVP version: Collect mock viral notes for testing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def collect_bootstrap_data(
        self,
        target_count: int = 100,
        category: str = "美妆"
    ) -> Dict[str, Any]:
        """
        Collect mock viral notes for bootstrapping.

        Args:
            target_count: Number of notes to collect
            category: Category to use

        Returns:
            {
                "collected": int,
                "analyzed": int,
                "patterns_extracted": int,
                "errors": List[str]
            }
        """
        print(f"Starting data collection: target={target_count}, category={category}")

        collected = 0
        analyzed = 0
        patterns_extracted = 0
        errors = []

        # Mock data templates
        hook_types = ["question", "story", "shock", "benefit", "curiosity"]
        body_types = ["list", "tutorial", "comparison", "story", "tips"]
        cta_types = ["like", "collect", "follow", "comment", "share"]

        try:
            for i in range(target_count):
                try:
                    note_id = f"mock_{uuid.uuid4().hex[:12]}"

                    # Check if already exists
                    existing = await self.db.execute(
                        select(XHSNote).where(XHSNote.note_id == note_id)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Generate mock data
                    hook_type = random.choice(hook_types)
                    body_type = random.choice(body_types)
                    cta_type = random.choice(cta_types)

                    # Create note
                    note = XHSNote(
                        note_id=note_id,
                        title=f"Mock {category} Note {i+1}",
                        text=f"This is a mock {category} note with {hook_type} hook, {body_type} body, and {cta_type} CTA.",
                        cover_url=f"https://example.com/cover_{note_id}.jpg",
                        image_urls=[f"https://example.com/img_{note_id}_1.jpg"],
                        author_id=f"author_{random.randint(1, 100)}",
                        publish_time=datetime.now() - timedelta(days=random.randint(1, 90)),
                        category=category,
                        tags=[category, hook_type, body_type],
                        is_viral=True,
                        analysis_status="pending"
                    )
                    self.db.add(note)

                    # Create metrics (mock viral performance)
                    views = random.randint(50000, 500000)
                    likes = int(views * random.uniform(0.05, 0.15))
                    comments = int(views * random.uniform(0.01, 0.05))
                    collects = int(views * random.uniform(0.03, 0.10))
                    shares = int(views * random.uniform(0.005, 0.02))

                    metrics = XHSMetrics(
                        note_id=note_id,
                        views=views,
                        likes=likes,
                        comments=comments,
                        collects=collects,
                        shares=shares,
                        follows=random.randint(10, 100)
                    )

                    # Calculate engagement rate
                    metrics.engagement_rate = (likes + comments + collects) / views if views > 0 else 0

                    # Calculate viral score (simple formula)
                    metrics.viral_score = min(1.0, (
                        metrics.engagement_rate * 5 +
                        (likes / 10000) * 0.3 +
                        (collects / 5000) * 0.2
                    ))

                    self.db.add(metrics)

                    # Create cover record
                    cover = XHSCover(
                        note_id=note_id,
                        download_status="pending",
                        layout="center",
                        dominant_color="#FF6B6B"
                    )
                    self.db.add(cover)

                    await self.db.commit()
                    collected += 1
                    print(f"Collected note {collected}/{target_count}: {note_id}")

                    # Create analysis
                    analysis = XHSAnalysis(
                        note_id=note_id,
                        hook_type=hook_type,
                        body_structure=body_type,
                        cta_type=cta_type,
                        keywords=[category, hook_type, body_type],
                        emotion_curve=[0.5, 0.7, 0.9, 0.8],
                        cover_layout="center",
                        dominant_color="#FF6B6B",
                        visual_elements=["text", "product", "person"]
                    )
                    self.db.add(analysis)
                    await self.db.commit()
                    analyzed += 1

                    # Extract pattern
                    pattern = await self._extract_pattern(note, metrics, analysis)
                    if pattern:
                        patterns_extracted += 1
                        print(f"Extracted pattern: {pattern.id}")

                except Exception as e:
                    errors.append(f"Failed to process note {i}: {str(e)}")
                    print(f"Error: {str(e)}")
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

    async def _extract_pattern(
        self,
        note: XHSNote,
        metrics: XHSMetrics,
        analysis: XHSAnalysis
    ) -> Pattern:
        """
        Extract reusable pattern from analyzed note.
        """
        # Check if similar pattern exists
        existing = await self.db.execute(
            select(Pattern).where(
                Pattern.hook_template == analysis.hook_type,
                Pattern.body_structure == analysis.body_structure,
                Pattern.cta_template == analysis.cta_type
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
            # Update Thompson Sampling priors (assume success if viral)
            pattern.thompson_alpha += 1
            pattern.success_rate = pattern.thompson_alpha / (
                pattern.thompson_alpha + pattern.thompson_beta
            )
        else:
            # Create new pattern
            pattern = Pattern(
                hook_template=analysis.hook_type,
                body_structure=analysis.body_structure,
                cta_template=analysis.cta_type,
                keywords=analysis.keywords or [],
                emotion_curve=analysis.emotion_curve or [],
                cover_layout=analysis.cover_layout,
                dominant_color=analysis.dominant_color,
                visual_elements=analysis.visual_elements or [],
                success_rate=1.0,  # Initial success (it's viral)
                sample_size=1,
                avg_viral_score=metrics.viral_score,
                avg_views=metrics.views,
                avg_engagement_rate=metrics.engagement_rate,
                thompson_alpha=2.0,  # Prior: 1 success + 1 pseudo-count
                thompson_beta=1.0,   # Prior: 0 failures + 1 pseudo-count
                version=1
            )
            self.db.add(pattern)

        await self.db.commit()

        # Create pattern sample link
        sample = PatternSample(
            pattern_id=pattern.id,
            note_id=note.note_id,
            contribution_score=1.0  # Full contribution for now
        )
        self.db.add(sample)
        await self.db.commit()

        return pattern
