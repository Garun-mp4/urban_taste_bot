"""Create the initial Urban Taste schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
        if_not_exists=True,
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False, if_not_exists=True)

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversation_messages_user_id",
        "conversation_messages",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_conversation_messages_user_created",
        "conversation_messages",
        ["user_id", "created_at"],
        if_not_exists=True,
    )

    op.create_table(
        "client_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="NEW"),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("guests", sa.Integer(), nullable=True),
        sa.Column("reservation_date", sa.Date(), nullable=True),
        sa.Column("reservation_time", sa.Time(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "guests IS NULL OR (guests > 0 AND guests <= 50)",
            name="ck_client_requests_guests",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_client_requests_user_id",
        "client_requests",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_client_requests_request_type",
        "client_requests",
        ["request_type"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_client_requests_status_created",
        "client_requests",
        ["status", "created_at"],
        if_not_exists=True,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("destination_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["client_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "destination_chat_id",
            "delivery_type",
            name="uq_notification_delivery_request_destination_type",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_notification_deliveries_request_id",
        "notification_deliveries",
        ["request_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_notification_deliveries_status_next_attempt",
        "notification_deliveries",
        ["status", "next_attempt_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("client_requests")
    op.drop_table("conversation_messages")
    op.drop_table("users")
