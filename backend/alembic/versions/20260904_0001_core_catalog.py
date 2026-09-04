"""core catalog

Revision ID: 0001_core_catalog
Revises:
Create Date: 2026-09-04

Tables: categories, addons, admin_users, foods, food_addons, site_settings.
Enum types: day_of_week, admin_role.
Hand-reviewed after autogenerate: bare check-constraint names (naming convention
prepends ``ck_<table>_``), timezone-aware timestamps, explicit enum create/drop.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_core_catalog"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Each enum type is referenced by exactly one table in this revision, so
    # ``op.create_table`` creates the type implicitly. ``downgrade`` drops them.
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "display_order", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index(op.f("ix_categories_slug"), "categories", ["slug"])

    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column(
            "is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_global", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
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
        sa.CheckConstraint("price >= 0", name=op.f("ck_addons_price_nonneg")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_addons")),
    )

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "staff", name="admin_role"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("email", name="uq_admin_users_email"),
    )
    op.create_index(op.f("ix_admin_users_email"), "admin_users", ["email"])

    op.create_table(
        "foods",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("price", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "min_order_quantity",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "is_single_serving",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "requires_advance_order",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "day_of_week",
            sa.Enum("mon", "tue", "wed", "thu", "fri", name="day_of_week"),
            nullable=True,
        ),
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
        sa.CheckConstraint("price > 0", name=op.f("ck_foods_price_positive")),
        sa.CheckConstraint(
            "min_order_quantity >= 1", name=op.f("ck_foods_min_qty")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_foods_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_foods")),
    )
    op.create_index(op.f("ix_foods_category_id"), "foods", ["category_id"])
    op.create_index(op.f("ix_foods_day_of_week"), "foods", ["day_of_week"])

    op.create_table(
        "food_addons",
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("addon_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["addon_id"],
            ["addons.id"],
            name=op.f("fk_food_addons_addon_id_addons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_food_addons_food_id_foods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("food_id", "addon_id", name=op.f("pk_food_addons")),
    )

    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("business_name", sa.String(length=120), nullable=False),
        sa.Column("tagline", sa.String(length=200), nullable=True),
        sa.Column("about_text", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=False),
        sa.Column("whatsapp_number", sa.String(length=20), nullable=False),
        sa.Column("instagram_handle", sa.String(length=60), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("opening_hours", sa.String(length=300), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_site_settings_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_settings")),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
    op.drop_table("food_addons")
    op.drop_index(op.f("ix_foods_day_of_week"), table_name="foods")
    op.drop_index(op.f("ix_foods_category_id"), table_name="foods")
    op.drop_table("foods")
    op.drop_index(op.f("ix_admin_users_email"), table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_table("addons")
    op.drop_index(op.f("ix_categories_slug"), table_name="categories")
    op.drop_table("categories")
    op.execute("DROP TYPE IF EXISTS admin_role")
    op.execute("DROP TYPE IF EXISTS day_of_week")
