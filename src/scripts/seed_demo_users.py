from __future__ import annotations

import asyncio
import uuid

from src.infrastructure.database.session import AsyncSessionFactory
from src.infrastructure.database.models import TenantModel, ApiUserModel
from src.infrastructure.security.password_hasher import PasswordHasher

DEMO_TENANT_SLUG = "demo"
DEMO_TENANT_NAME = "Демо-Организация ООО"

DEMO_USERS = [
    {"email": "superadmin@demo.local", "role": "SUPER_ADMIN", "password": "Demo1234!"},
    {"email": "admin@demo.local",      "role": "ADMIN",       "password": "Demo1234!"},
    {"email": "archivist@demo.local",  "role": "ARCHIVIST",   "password": "Demo1234!"},
    {"email": "auditor@demo.local",    "role": "AUDITOR",     "password": "Demo1234!"},
    {"email": "viewer@demo.local",     "role": "VIEWER",      "password": "Demo1234!"},
]


async def main() -> None:
    hasher = PasswordHasher()
    sf = AsyncSessionFactory()

    async with sf.session() as session:
        from sqlalchemy import select

        existing_tenant = await session.scalar(
            select(TenantModel).where(TenantModel.slug == DEMO_TENANT_SLUG)
        )
        if existing_tenant is None:
            tenant = TenantModel(
                id=uuid.uuid4(),
                slug=DEMO_TENANT_SLUG,
                name=DEMO_TENANT_NAME,
            )
            session.add(tenant)
            await session.flush()
            tenant_id = tenant.id
            print(f"[seed] Created tenant: {DEMO_TENANT_NAME} ({tenant_id})")
        else:
            tenant_id = existing_tenant.id
            print(f"[seed] Tenant already exists: {tenant_id}")

        for user_data in DEMO_USERS:
            existing_user = await session.scalar(
                select(ApiUserModel).where(ApiUserModel.email == user_data["email"])
            )
            if existing_user is not None:
                print(f"[seed] Skipping existing user: {user_data['email']}")
                continue

            hashed = hasher.hash(user_data["password"])
            user = ApiUserModel(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                email=user_data["email"],
                hashed_password=hashed,
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            print(f"[seed] Created user: {user_data['email']} ({user_data['role']})")

        await session.commit()

    print("\n[seed] Done. Demo credentials:")
    for u in DEMO_USERS:
        print(f"  {u['email']} / {u['password']}  [{u['role']}]")


if __name__ == "__main__":
    asyncio.run(main())
