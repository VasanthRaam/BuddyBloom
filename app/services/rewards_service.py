"""
XP Rewards Service

Handles all point operations:
- award_quiz_points: Called after quiz submission; idempotent via unique constraint on quiz_attempt_id
- teacher_give_points: Deducts from teacher wallet and credits to student
- get_student_summary: Computes current balance, rank, level, lifetime totals
- reset_teacher_wallets: Resets all teacher wallets to 1000 on 1st of month
- get_or_create_teacher_wallet: Ensures every teacher has a wallet row
"""

import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from fastapi import HTTPException

from app.db.models import (
    PointTransaction, TeacherWallet, Student, User,
    RewardCatalog, RewardRedemption
)

POINTS_PER_CORRECT_ANSWER = 10
TEACHER_MONTHLY_ALLOWANCE = 1000

# Level thresholds: (min_pts, label, next_threshold)
LEVELS = [
    (0,     "Beginner",     500),
    (500,   "Explorer",    1500),
    (1500,  "Achiever",    3000),
    (3000,  "Scholar",     6000),
    (6000,  "Champion",   12000),
    (12000, "Legend",     25000),
    (25000, "Grand Master", 50000),
    (50000, "XP Elite", None),
]


def _compute_level(lifetime_points: int) -> tuple[int, str, int, float]:
    """Returns (level_number, level_label, next_level_pts, progress_pct)."""
    level_num = 1
    level_label = "Beginner"
    next_pts = 500
    prev_pts = 0

    for i, (threshold, label, nxt) in enumerate(LEVELS):
        if lifetime_points >= threshold:
            level_num = i + 1
            level_label = label
            next_pts = nxt if nxt else threshold  # capped at Elite
            prev_pts = threshold
        else:
            break

    if LEVELS[level_num - 1][2] is None:
        # Max level reached
        progress_pct = 1.0
        next_pts = prev_pts
    else:
        span = next_pts - prev_pts
        progress_pct = min(1.0, (lifetime_points - prev_pts) / span) if span > 0 else 1.0

    return level_num, level_label, next_pts, round(progress_pct, 3)


async def get_student_balance(db: AsyncSession, student_id: uuid.UUID) -> int:
    """Returns current XP balance (sum of all point transactions)."""
    result = await db.execute(
        select(func.coalesce(func.sum(PointTransaction.points), 0))
        .where(PointTransaction.student_id == student_id)
    )
    return result.scalar() or 0


async def get_student_lifetime(db: AsyncSession, student_id: uuid.UUID) -> int:
    """Returns lifetime points (sum of all positive credits only)."""
    result = await db.execute(
        select(func.coalesce(func.sum(PointTransaction.points), 0))
        .where(PointTransaction.student_id == student_id)
        .where(PointTransaction.points > 0)
    )
    return result.scalar() or 0


async def award_quiz_points(
    db: AsyncSession,
    student_id: uuid.UUID,
    quiz_attempt_id: uuid.UUID,
    correct_answers: int
) -> Optional[PointTransaction]:
    """
    Awards XP points after quiz completion.
    Safe to call multiple times — idempotent via unique (student_id, quiz_attempt_id) constraint.
    Returns None if points were already awarded for this attempt.
    """
    # Check if points already awarded for this quiz attempt
    existing = await db.execute(
        select(PointTransaction).where(
            PointTransaction.student_id == student_id,
            PointTransaction.quiz_attempt_id == quiz_attempt_id,
            PointTransaction.source == "quiz"
        )
    )
    if existing.scalars().first():
        return None  # Already awarded

    points = correct_answers * POINTS_PER_CORRECT_ANSWER
    if points <= 0:
        return None

    txn = PointTransaction(
        id=uuid.uuid4(),
        student_id=student_id,
        points=points,
        source="quiz",
        reason=f"{correct_answers} correct answers × {POINTS_PER_CORRECT_ANSWER} pts each",
        quiz_attempt_id=quiz_attempt_id,
    )
    db.add(txn)
    await db.flush()
    return txn


async def get_or_create_teacher_wallet(db: AsyncSession, teacher_id: uuid.UUID) -> TeacherWallet:
    """
    Returns the teacher's wallet. Creates one if it doesn't exist yet,
    and resets it if the stored month_year is in the past.
    """
    from calendar import monthrange

    result = await db.execute(
        select(TeacherWallet).where(TeacherWallet.teacher_id == teacher_id)
    )
    wallet = result.scalars().first()
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")

    # Calculate expiry: last day of current month at 23:59:59 UTC
    last_day = monthrange(now.year, now.month)[1]
    expires_at = datetime(now.year, now.month, last_day, 23, 59, 59)

    if wallet is None:
        wallet = TeacherWallet(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            total_points=TEACHER_MONTHLY_ALLOWANCE,
            remaining_points=TEACHER_MONTHLY_ALLOWANCE,
            distributed_points=0,
            month_year=current_month,
            expires_at=expires_at,
            last_reset_at=now,
        )
        db.add(wallet)
        await db.flush()
    elif wallet.month_year != current_month:
        # New month — reset wallet
        wallet.total_points = TEACHER_MONTHLY_ALLOWANCE
        wallet.remaining_points = TEACHER_MONTHLY_ALLOWANCE
        wallet.distributed_points = 0
        wallet.month_year = current_month
        wallet.expires_at = expires_at
        wallet.last_reset_at = now
        await db.flush()

    return wallet


async def teacher_give_points(
    db: AsyncSession,
    teacher_id: uuid.UUID,
    student_id: uuid.UUID,
    points: int,
    reason: str
) -> PointTransaction:
    """
    Deducts points from teacher's monthly wallet and credits them to a student.
    Raises 400 if wallet is exhausted.
    """
    if points <= 0:
        raise HTTPException(status_code=400, detail="Points must be a positive number.")

    wallet = await get_or_create_teacher_wallet(db, teacher_id)

    if wallet.remaining_points < points:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance. You have {wallet.remaining_points} pts remaining."
        )

    # Deduct from wallet
    wallet.remaining_points -= points
    wallet.distributed_points += points

    # Credit to student
    txn = PointTransaction(
        id=uuid.uuid4(),
        student_id=student_id,
        points=points,
        source="teacher",
        reason=reason,
        given_by=teacher_id,
    )
    db.add(txn)
    await db.flush()
    return txn


async def get_student_summary(db: AsyncSession, student_id: uuid.UUID, student_name: str) -> dict:
    """
    Returns full XP summary for a student: balance, lifetime pts, breakdown by source, level, rank.
    """
    # Get all transactions
    txns_result = await db.execute(
        select(PointTransaction).where(PointTransaction.student_id == student_id)
    )
    txns = txns_result.scalars().all()

    current_points = sum(t.points for t in txns)
    lifetime_points = sum(t.points for t in txns if t.points > 0)
    quiz_points = sum(t.points for t in txns if t.source == "quiz" and t.points > 0)
    teacher_bonus = sum(t.points for t in txns if t.source == "teacher" and t.points > 0)

    level_num, level_label, next_pts, progress = _compute_level(lifetime_points)

    # Rank: how many students have strictly more current points
    rank_result = await db.execute(
        text("""
            SELECT COUNT(DISTINCT pt.student_id) + 1 AS rank
            FROM point_transactions pt
            WHERE (
                SELECT COALESCE(SUM(pts.points), 0)
                FROM point_transactions pts
                WHERE pts.student_id = pt.student_id
            ) > :my_pts
        """),
        {"my_pts": current_points}
    )
    rank = rank_result.scalar() or 1

    return {
        "student_id": str(student_id),
        "student_name": student_name,
        "current_points": current_points,
        "lifetime_points": lifetime_points,
        "quiz_points": quiz_points,
        "teacher_bonus_points": teacher_bonus,
        "rank": rank,
        "level": level_num,
        "level_label": level_label,
        "next_level_points": next_pts,
        "progress_pct": progress,
    }


async def reset_all_teacher_wallets(db: AsyncSession):
    """
    Resets all teacher wallets to 1000 points. Called on the 1st of the month.
    """
    from calendar import monthrange
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
    last_day = monthrange(now.year, now.month)[1]
    expires_at = datetime(now.year, now.month, last_day, 23, 59, 59)

    result = await db.execute(select(TeacherWallet))
    wallets = result.scalars().all()
    for w in wallets:
        if w.month_year != current_month:
            w.total_points = TEACHER_MONTHLY_ALLOWANCE
            w.remaining_points = TEACHER_MONTHLY_ALLOWANCE
            w.distributed_points = 0
            w.month_year = current_month
            w.expires_at = expires_at
            w.last_reset_at = now
    await db.commit()


async def redeem_reward(db: AsyncSession, student_id: uuid.UUID, reward_id: uuid.UUID) -> RewardRedemption:
    """
    Redeems a reward for a student. Checks balance, deducts points, creates redemption record.
    """
    # Fetch reward
    r_res = await db.execute(select(RewardCatalog).where(RewardCatalog.id == reward_id, RewardCatalog.is_active == True))
    reward = r_res.scalars().first()
    if not reward:
        raise HTTPException(status_code=404, detail="Reward not found or unavailable.")

    balance = await get_student_balance(db, student_id)
    if balance < reward.points_required:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient points. You need {reward.points_required} pts but have {balance} pts."
        )

    # Check no pending/approved redemption for same reward
    dup = await db.execute(
        select(RewardRedemption).where(
            RewardRedemption.student_id == student_id,
            RewardRedemption.reward_id == reward_id,
            RewardRedemption.status.in_(["pending", "approved"])
        )
    )
    if dup.scalars().first():
        raise HTTPException(status_code=400, detail="You already have a pending or approved redemption for this reward.")

    # Deduct points
    debit = PointTransaction(
        id=uuid.uuid4(),
        student_id=student_id,
        points=-reward.points_required,
        source="redemption",
        reason=f"Redeemed: {reward.title}",
    )
    db.add(debit)

    # Create redemption
    redemption = RewardRedemption(
        id=uuid.uuid4(),
        student_id=student_id,
        reward_id=reward_id,
        points_spent=reward.points_required,
        status="pending",
    )
    db.add(redemption)
    await db.flush()
    return redemption
