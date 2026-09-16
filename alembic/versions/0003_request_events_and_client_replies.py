"""Add request audit events and durable client replies.

Revision ID: 0003_request_events_and_client_replies
Revises: 0002_booking_invariants_and_processed_events
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_request_events_and_client_replies"
down_revision = "0002_booking_invariants_and_processed_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "notification_deliveries",
        "delivery_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("message_text", sa.Text(), nullable=True),
    )
    op.create_table(
        "request_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["client_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_request_events_request_id",
        "request_events",
        ["request_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_request_events_request_created",
        "request_events",
        ["request_id", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("request_events")
    op.drop_column("notification_deliveries", "message_text")
    op.alter_column(
        "notification_deliveries",
        "delivery_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
