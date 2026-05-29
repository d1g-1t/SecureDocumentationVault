from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import Any

from cryptography import x509

from src.core.logging import get_logger
from src.domain.value_objects import SignatureStatus, SignatureType

logger = get_logger(__name__)


class CmsVerifier:

    def verify(
        self,
        document_bytes: bytes,
        signature_b64: str,
        signature_type: SignatureType = SignatureType.CMS,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "signature_type": signature_type.value,
            "verified_at": datetime.now(UTC).isoformat(),
            "status": SignatureStatus.UNKNOWN.value,
        }

        try:
            sig_bytes = base64.b64decode(signature_b64)
        except Exception as exc:
            report["error"] = f"Base64 decode failed: {exc}"
            report["status"] = SignatureStatus.INVALID.value
            return report

        try:
            from cryptography.hazmat.primitives.serialization.pkcs7 import (
                load_der_pkcs7_certificates,
            )

            certs = load_der_pkcs7_certificates(sig_bytes)
            if not certs:
                report["error"] = "No certificates found in signature blob"
                report["status"] = SignatureStatus.INVALID.value
                return report

            cert = certs[0]
            report.update(self._extract_cert_info(cert))

            now = datetime.now(UTC)
            not_before = cert.not_valid_before_utc
            not_after = cert.not_valid_after_utc

            if now < not_before or now > not_after:
                report["status"] = SignatureStatus.EXPIRED_CERT.value
                report["cert_expired"] = True
            else:
                report["status"] = SignatureStatus.VALID.value
                report["cert_expired"] = False

            report["document_sha256"] = hashlib.sha256(document_bytes).hexdigest()

        except Exception as exc:
            logger.warning("cms_verification_error", error=str(exc))
            report["status"] = SignatureStatus.INVALID.value
            report["error"] = str(exc)

        return report

    @staticmethod
    def _extract_cert_info(cert: x509.Certificate) -> dict[str, Any]:
        info: dict[str, Any] = {}

        try:
            subject = cert.subject
            info["certificate_subject"] = subject.rfc4514_string()

            cn_attrs = subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn_attrs:
                info["signer_name"] = cn_attrs[0].value

            INN_OID = x509.ObjectIdentifier("1.2.643.3.131.1.1")
            try:
                inn_attrs = subject.get_attributes_for_oid(INN_OID)
                if inn_attrs:
                    info["signer_inn"] = inn_attrs[0].value
            except Exception:
                pass

            issuer = cert.issuer
            info["certificate_issuer"] = issuer.rfc4514_string()
            info["certificate_serial"] = str(cert.serial_number)
            info["not_before"] = cert.not_valid_before_utc.isoformat()
            info["not_after"] = cert.not_valid_after_utc.isoformat()

        except Exception as exc:
            info["cert_parse_error"] = str(exc)

        return info
