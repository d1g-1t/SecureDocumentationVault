from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

documents_uploaded_total = Counter(
    "vault_documents_uploaded_total",
    "Total documents uploaded",
    ["tenant_id", "document_type"],
)

document_versions_total = Counter(
    "vault_document_versions_total",
    "Total document versions created",
    ["tenant_id"],
)

signature_verifications_total = Counter(
    "vault_signature_verifications_total",
    "Total signature verifications",
    ["tenant_id", "signature_type", "status"],
)

signature_verification_duration = Histogram(
    "vault_signature_verification_duration_seconds",
    "Time spent verifying a signature",
    ["signature_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

share_links_created_total = Counter(
    "vault_share_links_created_total",
    "Total share links created",
    ["tenant_id"],
)

share_downloads_total = Counter(
    "vault_share_downloads_total",
    "Total share link downloads",
    ["tenant_id"],
)

retention_expiry_total = Counter(
    "vault_retention_expiry_total",
    "Documents reaching retention expiry",
    ["action"],
)

legal_holds_active = Gauge(
    "vault_legal_holds_active",
    "Currently active legal holds",
    ["tenant_id"],
)

audit_events_total = Counter(
    "vault_audit_events_total",
    "Total audit events written",
    ["tenant_id", "event_type"],
)

audit_package_generation_duration = Histogram(
    "vault_audit_package_generation_duration_seconds",
    "Time to generate an audit export package",
    buckets=(1, 5, 10, 30, 60, 120),
)

storage_consistency_failures_total = Counter(
    "vault_storage_consistency_failures_total",
    "Storage objects missing or corrupt",
    ["tenant_id"],
)

encryption_duration = Histogram(
    "vault_encryption_duration_seconds",
    "Time to encrypt a document",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

download_duration = Histogram(
    "vault_download_duration_seconds",
    "Time to serve a document download",
    buckets=(0.1, 0.5, 1, 2.5, 5, 10),
)
