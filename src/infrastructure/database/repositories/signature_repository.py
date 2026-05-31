from __future__ import annotations

import uuid

from sqlalchemy import select

from src.domain.entities.signature_record import SignatureRecord
from src.domain.repositories import ISignatureRepository
from src.domain.value_objects import SignatureStatus, SignatureType
from src.infrastructure.database.models import SignatureRecordModel
from src.infrastructure.database.session import AsyncSessionFactory


class SignatureRepository(ISignatureRepository):
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._sf = session_factory

    @staticmethod
    def _to_entity(m: SignatureRecordModel) -> SignatureRecord:
        return SignatureRecord(
            id=m.id,
            document_version_id=m.document_version_id,
            signature_type=SignatureType(m.signature_type),
            verification_status=SignatureStatus(m.verification_status),
            signer_name=m.signer_name,
            signer_inn=m.signer_inn,
            certificate_subject=m.certificate_subject,
            certificate_issuer=m.certificate_issuer,
            certificate_serial=m.certificate_serial,
            signing_time=m.signing_time,
            signature_hash=m.signature_hash,
            raw_report=dict(m.raw_report or {}),
            verified_at=m.verified_at,
        )

    async def create(self, record: SignatureRecord) -> SignatureRecord:
        async with self._sf.session() as session:
            model = SignatureRecordModel(
                id=record.id,
                document_version_id=record.document_version_id,
                signature_type=record.signature_type.value,
                verification_status=record.verification_status.value,
                signer_name=record.signer_name,
                signer_inn=record.signer_inn,
                certificate_subject=record.certificate_subject,
                certificate_issuer=record.certificate_issuer,
                certificate_serial=record.certificate_serial,
                signing_time=record.signing_time,
                signature_hash=record.signature_hash,
                raw_report=record.raw_report,
                verified_at=record.verified_at,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            return self._to_entity(model)

    async def get_by_version(self, version_id: uuid.UUID) -> list[SignatureRecord]:
        async with self._sf.session() as session:
            result = await session.execute(
                select(SignatureRecordModel).where(
                    SignatureRecordModel.document_version_id == version_id
                )
            )
            return [self._to_entity(m) for m in result.scalars().all()]

    async def get_by_id(self, record_id: uuid.UUID) -> SignatureRecord | None:
        async with self._sf.session() as session:
            result = await session.execute(
                select(SignatureRecordModel).where(SignatureRecordModel.id == record_id)
            )
            m = result.scalars().first()
            return self._to_entity(m) if m else None
