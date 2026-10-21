
from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError

from .config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_MINUTES,
    COOKIE_NAME,
    COOKIE_SECURE,
)
from .database import get_users_collection

router = APIRouter(prefix="/auth", tags=["Authentication"])

password_hash = PasswordHash.recommended()


class SignupData(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginData(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def set_session(response: Response, user_id: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_token(user_id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )


async def current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Please log in.",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Missing subject")

        object_id = ObjectId(user_id)

    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in.",
        )

    users = get_users_collection()
    user = await users.find_one({"_id": object_id})

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User no longer exists.",
        )

    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
    }


@router.post("/signup", status_code=201)
async def signup(data: SignupData, response: Response):
    email = str(data.email).strip().lower()
    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Name is required.",
        )

    users = get_users_collection()

    user = {
        "name": name,
        "email": email,
        "password_hash": password_hash.hash(data.password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = await users.insert_one(user)

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    set_session(response, str(result.inserted_id))

    return {
        "message": "Account created successfully.",
        "user": {
            "id": str(result.inserted_id),
            "name": user["name"],
            "email": user["email"],
        },
    }


@router.post("/login")
async def login(data: LoginData, response: Response):
    email = str(data.email).strip().lower()

    users = get_users_collection()
    user = await users.find_one({"email": email})

    if not user or not password_hash.verify(
        data.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    set_session(response, str(user["_id"]))

    return {
        "message": "Login successful.",
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
        },
    }


@router.get("/me")
async def get_me(user: dict = Depends(current_user)):
    return {"user": user}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return {"message": "Logged out successfully."}
