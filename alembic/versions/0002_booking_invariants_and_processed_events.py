"""Align booking limits and remember processed Telegram events.

Revision ID: 0002_booking_invariants_and_processed_events
Revises: 0001_initial
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_booking_invariants_and_processed_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE client_requests "
        "DROP CONSTRAINT IF EXISTS ck_client_requests_guests"
    )
    op.create_check_constraint(
        "ck_client_requests_guests",
        "client_requests",
        "guests IS NULL OR (guests > 0 AND guests <= 1000)",
    )
    op.create_table(
        "processed_events",
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_key"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_processed_events_created_at",
        "processed_events",
        ["created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.execute(
        "ALTER TABLE client_requests "
        "DROP CONSTRAINT IF EXISTS ck_client_requests_guests"
    )
    op.create_check_constraint(
        "ck_client_requests_guests",
        "client_requests",
        "guests IS NULL OR (guests > 0 AND guests <= 50)",
    )
