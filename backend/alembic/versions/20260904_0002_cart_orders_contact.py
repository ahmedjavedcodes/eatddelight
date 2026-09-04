"""cart, orders, contact

Revision ID: 0002_cart_orders_contact
Revises: 0001_core_catalog
Create Date: 2026-09-04

Tables: carts, cart_items, cart_item_addons, favourites, orders, order_items,
order_item_addons, contact_messages.
Enum types: order_source, order_status.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_cart_orders_contact"
down_revision: str | None = "0001_core_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # order_source / order_status are each used by exactly one table (orders), so
    # ``op.create_table`` creates the types implicitly. ``downgrade`` drops them.
    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carts")),
    )
    op.create_index(
        op.f("ix_carts_session_token"), "carts", ["session_token"], unique=True
    )

    op.create_table(
        "favourites",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_favourites_food_id_foods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_favourites")),
        sa.UniqueConstraint(
            "session_token", "food_id", name="uq_favourites_session_food"
        ),
    )
    op.create_index(
        op.f("ix_favourites_session_token"), "favourites", ["session_token"]
    )

    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("cart_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity >= 1", name=op.f("ck_cart_items_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["carts.id"],
            name=op.f("fk_cart_items_cart_id_carts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_cart_items_food_id_foods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cart_items")),
    )
    op.create_index(op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"])

    op.create_table(
        "cart_item_addons",
        sa.Column("cart_item_id", sa.Integer(), nullable=False),
        sa.Column("addon_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 1", name=op.f("ck_cart_item_addons_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["addon_id"],
            ["addons.id"],
            name=op.f("fk_cart_item_addons_addon_id_addons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cart_item_id"],
            ["cart_items.id"],
            name=op.f("fk_cart_item_addons_cart_item_id_cart_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "cart_item_id", "addon_id", name=op.f("pk_cart_item_addons")
        ),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("invoice_number", sa.String(length=24), nullable=False),
        sa.Column("lookup_token", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=False),
        sa.Column(
            "order_source",
            sa.Enum("catalog", "custom_request", name="order_source"),
            nullable=False,
        ),
        sa.Column("requested_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "confirmed", "completed", "cancelled", name="order_status"
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("subtotal", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("total", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column(
            "is_custom", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("custom_description", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "whatsapp_link_sent_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("budget_range", sa.String(length=60), nullable=True),
        sa.Column("occasion", sa.String(length=120), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("invoice_number", name="uq_orders_invoice_number"),
    )
    op.create_index(op.f("ix_orders_lookup_token"), "orders", ["lookup_token"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=True),
        sa.Column("food_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "quantity >= 1", name=op.f("ck_order_items_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_order_items_food_id_foods"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])

    op.create_table(
        "order_item_addons",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("addon_id", sa.Integer(), nullable=True),
        sa.Column("addon_name", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.CheckConstraint(
            "quantity >= 1", name=op.f("ck_order_item_addons_quantity_positive")
        ),
        sa.ForeignKeyConstraint(
            ["addon_id"],
            ["addons.id"],
            name=op.f("fk_order_item_addons_addon_id_addons"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_order_item_addons_order_item_id_order_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_item_addons")),
        sa.UniqueConstraint(
            "order_item_id", "addon_id", name="uq_order_item_addons_item_addon"
        ),
    )

    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone_or_email", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_messages")),
    )


def downgrade() -> None:
    op.drop_table("contact_messages")
    op.drop_table("order_item_addons")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index(op.f("ix_orders_lookup_token"), table_name="orders")
    op.drop_table("orders")
    op.drop_table("cart_item_addons")
    op.drop_index(op.f("ix_cart_items_cart_id"), table_name="cart_items")
    op.drop_table("cart_items")
    op.drop_index(op.f("ix_favourites_session_token"), table_name="favourites")
    op.drop_table("favourites")
    op.drop_index(op.f("ix_carts_session_token"), table_name="carts")
    op.drop_table("carts")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS order_source")
