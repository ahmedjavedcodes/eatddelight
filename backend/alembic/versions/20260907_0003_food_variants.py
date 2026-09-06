"""food variants

Revision ID: 0003_food_variants
Revises: 0002_cart_orders_contact
Create Date: 2026-09-07

Adds the optional food_variants table (named size/quantity options with their
own price, e.g. Chicken Karahi "500g" -> 800, "1kg" -> 2000, "2kg" -> 3000) and
wires it into the ordering path: cart_items.variant_id (CASCADE, carts are
ephemeral) and order_items.variant_id/variant_label (SET NULL + denormalized
label, matching the existing food_id/food_name snapshot pattern so historical
orders survive a variant being edited or removed later).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_food_variants"
down_revision: str | None = "0002_cart_orders_contact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_variants",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("price", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.CheckConstraint("price > 0", name=op.f("ck_food_variants_price_positive")),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_food_variants_food_id_foods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_variants")),
        sa.UniqueConstraint("food_id", "label", name="uq_food_variants_food_id_label"),
        sa.UniqueConstraint("food_id", "price", name="uq_food_variants_food_id_price"),
    )
    op.create_index(op.f("ix_food_variants_food_id"), "food_variants", ["food_id"])

    op.add_column("cart_items", sa.Column("variant_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_cart_items_variant_id_food_variants"),
        "cart_items",
        "food_variants",
        ["variant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("order_items", sa.Column("variant_id", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("variant_label", sa.String(length=60), nullable=True))
    op.create_foreign_key(
        op.f("fk_order_items_variant_id_food_variants"),
        "order_items",
        "food_variants",
        ["variant_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_order_items_variant_id_food_variants"), "order_items", type_="foreignkey"
    )
    op.drop_column("order_items", "variant_label")
    op.drop_column("order_items", "variant_id")

    op.drop_constraint(
        op.f("fk_cart_items_variant_id_food_variants"), "cart_items", type_="foreignkey"
    )
    op.drop_column("cart_items", "variant_id")

    op.drop_index(op.f("ix_food_variants_food_id"), table_name="food_variants")
    op.drop_table("food_variants")
