"""Initial schema — create all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-03-31 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # api_users
    op.create_table(
        "api_users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_api_users_tenant", "api_users", ["tenant_id"])

    # retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("retention_mode", sa.String(32), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("allow_delete_after_expiry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # storage_objects
    op.create_table(
        "storage_objects",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("bucket_name", sa.String(128), nullable=False),
        sa.Column("storage_class", sa.String(32), nullable=False),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("object_size", sa.BigInteger(), nullable=False),
        sa.Column("object_checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )

    # documents (without current_version_id FK first — deferred)
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'ACTIVE'")),

        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("current_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("retention_policy_id", UUID(as_uuid=True), nullable=True),
        sa.Column("legal_hold_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'")),

        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'"))
,
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["api_users.id"]),
        sa.ForeignKeyConstraint(["retention_policy_id"], ["retention_policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_documents_tenant_status", "documents", ["tenant_id", "status"])

    # document_versions
    op.create_table(
        "document_versions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("storage_object_id", UUID(as_uuid=True), nullable=True),
        sa.Column("encryption_key_id", sa.String(128), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["storage_object_id"], ["storage_objects.id"], name="fk_versions_storage_object", use_alter=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["api_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number"),
    )
    op.create_index("idx_document_versions_doc", "document_versions", ["document_id", "version_number"])

    # Now add current_version_id FK (deferred)
    op.create_foreign_key(
        "fk_documents_current_version",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        use_alter=True,
    )

    # signature_records
    op.create_table(
        "signature_records",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("signature_type", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("signer_name", sa.String(255), nullable=True),
        sa.Column("signer_inn", sa.String(12), nullable=True),
        sa.Column("certificate_subject", sa.Text(), nullable=True),
        sa.Column("certificate_issuer", sa.Text(), nullable=True),
        sa.Column("certificate_serial", sa.String(255), nullable=True),
        sa.Column("signing_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signature_hash", sa.String(64), nullable=True),
        sa.Column("raw_report", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_signature_records_status", "signature_records", ["verification_status"])

    # share_links
    op.create_table(
        "share_links",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_downloads", sa.Integer(), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("watermark_on_download", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["api_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_share_links_expiry", "share_links", ["expires_at", "revoked_at"])

    # legal_holds
    op.create_table(
        "legal_holds",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("placed_by", UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("placed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["placed_by"], ["api_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_legal_holds_active", "legal_holds", ["document_id", "active"])

    # watermark_profiles
    op.create_table(
        "watermark_profiles",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("ip_address", INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("prev_event_hash", sa.String(64), nullable=True),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["api_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_events_resource", "audit_events", ["resource_type", "resource_id", "created_at"])
    op.create_index("idx_audit_events_trace", "audit_events", ["trace_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("watermark_profiles")
    op.drop_table("legal_holds")
    op.drop_table("share_links")
    op.drop_table("signature_records")
    op.drop_constraint("fk_documents_current_version", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("storage_objects")
    op.drop_table("retention_policies")
    op.drop_table("api_users")
    op.drop_table("tenants")
