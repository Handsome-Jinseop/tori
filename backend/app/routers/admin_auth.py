from __future__ import annotations

import json
from typing import Any

import webauthn
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import get_settings
from app.core.ids import new_id
from app.core.security import (
    create_session_token,
    generate_recovery_codes,
    get_current_admin,
    hash_token,
    read_session_token,
)
from app.core.serialize import doc_out
from app.core.time import now_utc
from app.db import get_database

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


def _challenge_cookie_kwargs() -> dict[str, Any]:
    return dict(httponly=True, samesite="lax", secure=False, max_age=300, path="/")


def _session_cookie_kwargs() -> dict[str, Any]:
    settings = get_settings()
    return dict(
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_max_age_seconds,
        path="/",
    )


async def _get_owner(db) -> dict | None:
    return await db.admin_users.find_one({"role": "owner"})


@router.get("/state")
async def auth_state():
    db = get_database()
    owner = await _get_owner(db)
    return {"setup_required": owner is None}


@router.get("/register/options")
async def register_options(response: Response, session: str | None = Cookie(default=None)):
    db = get_database()
    owner = await _get_owner(db)
    settings = get_settings()

    if owner is None:
        user_id = new_id()
        display_name = "사장님"
        exclude: list[PublicKeyCredentialDescriptor] = []
    else:
        data = read_session_token(session) if session else None
        if not data:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요해요.")
        user_id = owner["_id"]
        display_name = owner.get("display_name", "사장님")
        exclude = [
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(pk["credential_id"]))
            for pk in owner.get("passkeys", [])
        ]

    options = webauthn.generate_registration_options(
        rp_id=settings.rp_id,
        rp_name=settings.rp_name,
        user_id=user_id.encode(),
        user_name="owner",
        user_display_name=display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=exclude,
    )
    response.set_cookie(
        "webauthn_reg_challenge", bytes_to_base64url(options.challenge), **_challenge_cookie_kwargs()
    )
    response.set_cookie("webauthn_reg_user_id", user_id, **_challenge_cookie_kwargs())
    return {"options": json.loads(webauthn.options_to_json(options))}


class RegisterVerifyBody(BaseModel):
    credential: dict
    device_name: str = "새 기기"


@router.post("/register/verify")
async def register_verify(
    body: RegisterVerifyBody,
    response: Response,
    webauthn_reg_challenge: str | None = Cookie(default=None),
    webauthn_reg_user_id: str | None = Cookie(default=None),
):
    if not webauthn_reg_challenge or not webauthn_reg_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "등록 세션이 만료됐어요. 다시 시도해 주세요.")
    settings = get_settings()
    db = get_database()

    verification = webauthn.verify_registration_response(
        credential=body.credential,
        expected_challenge=base64url_to_bytes(webauthn_reg_challenge),
        expected_rp_id=settings.rp_id,
        expected_origin=settings.origin,
    )

    passkey = {
        "credential_id": bytes_to_base64url(verification.credential_id),
        "public_key": bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "device_name": body.device_name,
        "created_at": now_utc(),
    }

    owner = await _get_owner(db)
    if owner is None:
        recovery_codes = generate_recovery_codes()
        admin_id = webauthn_reg_user_id
        await db.admin_users.insert_one(
            {
                "_id": admin_id,
                "login_id": "owner",
                "display_name": "사장님",
                "role": "owner",
                "passkeys": [passkey],
                "recovery_codes_hashed": [hash_token(c) for c in recovery_codes],
                "recovery_codes_used": [],
                "created_at": now_utc(),
            }
        )
        session_admin_id = admin_id
        first_recovery_codes = recovery_codes
    else:
        await db.admin_users.update_one({"_id": owner["_id"]}, {"$push": {"passkeys": passkey}})
        session_admin_id = owner["_id"]
        first_recovery_codes = None

    response.delete_cookie("webauthn_reg_challenge", path="/")
    response.delete_cookie("webauthn_reg_user_id", path="/")
    response.set_cookie(
        get_settings().session_cookie_name,
        create_session_token(session_admin_id),
        **_session_cookie_kwargs(),
    )
    return {"ok": True, "recovery_codes": first_recovery_codes}


@router.get("/login/options")
async def login_options(response: Response):
    settings = get_settings()
    options = webauthn.generate_authentication_options(
        rp_id=settings.rp_id,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    response.set_cookie(
        "webauthn_login_challenge", bytes_to_base64url(options.challenge), **_challenge_cookie_kwargs()
    )
    return {"options": json.loads(webauthn.options_to_json(options))}


class LoginVerifyBody(BaseModel):
    credential: dict


@router.post("/login/verify")
async def login_verify(
    body: LoginVerifyBody,
    response: Response,
    webauthn_login_challenge: str | None = Cookie(default=None),
):
    if not webauthn_login_challenge:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "로그인 세션이 만료됐어요. 다시 시도해 주세요.")
    settings = get_settings()
    db = get_database()

    cred_id = body.credential.get("id") or body.credential.get("rawId")
    owner = await db.admin_users.find_one({"passkeys.credential_id": cred_id})
    if not owner:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "등록되지 않은 기기예요.")
    passkey = next(pk for pk in owner["passkeys"] if pk["credential_id"] == cred_id)

    verification = webauthn.verify_authentication_response(
        credential=body.credential,
        expected_challenge=base64url_to_bytes(webauthn_login_challenge),
        expected_rp_id=settings.rp_id,
        expected_origin=settings.origin,
        credential_public_key=base64url_to_bytes(passkey["public_key"]),
        credential_current_sign_count=passkey["sign_count"],
    )

    await db.admin_users.update_one(
        {"_id": owner["_id"], "passkeys.credential_id": cred_id},
        {"$set": {"passkeys.$.sign_count": verification.new_sign_count}},
    )
    response.delete_cookie("webauthn_login_challenge", path="/")
    response.set_cookie(
        settings.session_cookie_name, create_session_token(owner["_id"]), **_session_cookie_kwargs()
    )
    return {"ok": True}


class RecoveryLoginBody(BaseModel):
    code: str


@router.post("/recovery/login")
async def recovery_login(body: RecoveryLoginBody, response: Response):
    db = get_database()
    owner = await _get_owner(db)
    if not owner:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "설정된 계정이 없어요.")
    code_hash = hash_token(body.code.strip())
    if code_hash not in owner.get("recovery_codes_hashed", []):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "복구 코드가 올바르지 않아요.")
    if code_hash in owner.get("recovery_codes_used", []):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이미 사용한 복구 코드예요.")
    await db.admin_users.update_one({"_id": owner["_id"]}, {"$push": {"recovery_codes_used": code_hash}})
    response.set_cookie(
        get_settings().session_cookie_name,
        create_session_token(owner["_id"]),
        **_session_cookie_kwargs(),
    )
    return {"ok": True}


@router.post("/recovery/regenerate")
async def recovery_regenerate(admin: dict = Depends(get_current_admin)):
    db = get_database()
    codes = generate_recovery_codes()
    await db.admin_users.update_one(
        {"_id": admin["_id"]},
        {"$set": {"recovery_codes_hashed": [hash_token(c) for c in codes], "recovery_codes_used": []}},
    )
    return {"recovery_codes": codes}


@router.get("/me")
async def me(session: str | None = Cookie(default=None)):
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요해요.")
    data = read_session_token(session)
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 만료됐어요.")
    db = get_database()
    admin = await db.admin_users.find_one({"_id": data["admin_id"]})
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 만료됐어요.")
    admin.pop("recovery_codes_hashed", None)
    admin.pop("recovery_codes_used", None)
    for pk in admin.get("passkeys", []):
        pk.pop("public_key", None)
    return doc_out(admin)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"ok": True}


@router.delete("/passkeys/{credential_id}")
async def delete_passkey(credential_id: str, session: str | None = Cookie(default=None)):
    data = read_session_token(session) if session else None
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요해요.")
    db = get_database()
    admin = await db.admin_users.find_one({"_id": data["admin_id"]})
    if not admin or len(admin.get("passkeys", [])) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "마지막 패스키는 삭제할 수 없어요.")
    await db.admin_users.update_one(
        {"_id": admin["_id"]}, {"$pull": {"passkeys": {"credential_id": credential_id}}}
    )
    return {"ok": True}


# --- QR login (PC <-> phone) ---


@router.post("/qr/start")
async def qr_start():
    db = get_database()
    req_id = new_id()
    await db.login_requests.insert_one(
        {"_id": req_id, "status": "pending", "admin_id": None, "created_at": now_utc()}
    )
    return {"request_id": req_id}


@router.get("/qr/{request_id}/status")
async def qr_status(request_id: str, response: Response):
    db = get_database()
    req = await db.login_requests.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "요청을 찾을 수 없어요.")
    if req["status"] == "approved":
        settings = get_settings()
        response.set_cookie(
            settings.session_cookie_name, create_session_token(req["admin_id"]), **_session_cookie_kwargs()
        )
        await db.login_requests.update_one({"_id": request_id}, {"$set": {"status": "consumed"}})
        return {"status": "approved"}
    return {"status": req["status"]}


@router.post("/qr/{request_id}/approve")
async def qr_approve(request_id: str, session: str | None = Cookie(default=None)):
    data = read_session_token(session) if session else None
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요해요.")
    db = get_database()
    req = await db.login_requests.find_one({"_id": request_id})
    if not req or req["status"] != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "만료된 요청이에요.")
    await db.login_requests.update_one(
        {"_id": request_id}, {"$set": {"status": "approved", "admin_id": data["admin_id"]}}
    )
    return {"ok": True}
