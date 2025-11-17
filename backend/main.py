from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationInfo
from sqlalchemy.orm import Session
from datetime import datetime
from horoscope_generator import generate_horoscope
from email_sender import send_email
from zodiac_calculator import get_zodiac_sign
from database import init_db, get_db, User
from scheduler import start_scheduler
import time
import secrets
import os


app = FastAPI(title="Zodiac_API")

ALLOWED_ORIGINS = [
    "https://frontend.norkfor.xyz",
    "https://backend.norkfor.xyz",
    "http://localhost",
    "http://localhost:2000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "backend.norkfor.xyz",
        "frontend.norkfor.xyz",
        "localhost",
        "127.0.0.1",
    ],
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Basic security headers – backend only serves API/HTML snippets
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def verify_admin(
    admin_token: str = Header(..., alias="X-Admin-Token"),
):
    """
    Simple API-key style protection for admin endpoints.
    The real secret is stored in ADMIN_API_KEY (env).
    """
    if not ADMIN_API_KEY:
        # Fail closed if misconfigured
        raise HTTPException(status_code=500, detail="Admin API key not configured")

    # Constant-time comparison to avoid timing attacks
    if not secrets.compare_digest(admin_token, ADMIN_API_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")

    return True


init_db()
start_scheduler()


def generate_unsubscribe_token() -> str:
    return secrets.token_hex(32)


class HoroscopeRequest(BaseModel):
    name: str
    email: EmailStr
    birth_month: int = Field(..., ge=1, le=12, description="Birth month (1-12)")
    birth_day: int = Field(..., ge=1, le=31, description="Birth day (1-31)")

    @field_validator("birth_day")
    @classmethod
    def validate_day_in_month(cls, day: int, info: ValidationInfo) -> int:
        """Validate that the day is valid for the given month"""
        if "birth_month" not in info.data:
            return day

        birth_month = info.data["birth_month"]

        days_in_month = {
            1: 31,
            2: 29,
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }

        if day > days_in_month.get(birth_month, 31):
            raise ValueError(f"Day {day} is invalid for month {birth_month}")

        return day


class HoroscopeRequestNoEmail(BaseModel):
    name: str
    birth_month: int = Field(..., ge=1, le=12, description="Birth month (1-12)")
    birth_day: int = Field(..., ge=1, le=31, description="Birth day (1-31)")

    @field_validator("birth_day")
    @classmethod
    def validate_day_in_month(cls, day: int, info: ValidationInfo) -> int:
        if "birth_month" not in info.data:
            return day

        birth_month = info.data["birth_month"]

        days_in_month = {
            1: 31,
            2: 29,
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }

        if day > days_in_month.get(birth_month, 31):
            raise ValueError(f"Day {day} is invalid for month {birth_month}")

        return day


@app.get("/")
def root():
    return {"message": "API is working! Scheduler active."}


@app.post("/api/get-horoscope", response_class=HTMLResponse)
def get_horoscope(request: HoroscopeRequestNoEmail):
    try:
        zodiac_sign = get_zodiac_sign(request.birth_month, request.birth_day)
        horoscope_html = generate_horoscope(zodiac_sign, request.name)
        return horoscope_html
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log internal error but don't leak details to client
        print(f"Internal error in /api/get-horoscope: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.post("/api/send-horoscope")
def send_horoscope_endpoint(
    request: HoroscopeRequest, db: Session = Depends(get_db)
):
    try:
        zodiac_sign = get_zodiac_sign(request.birth_month, request.birth_day)

        existing_user = db.query(User).filter(User.email == request.email).first()

        if existing_user:
            existing_user.name = request.name
            existing_user.birth_month = request.birth_month
            existing_user.birth_day = request.birth_day
            existing_user.zodiac_sign = zodiac_sign
            existing_user.last_horoscope_sent = datetime.now()
            if not existing_user.unsubscribe_token:
                existing_user.unsubscribe_token = generate_unsubscribe_token()
            existing_user.is_subscribed = 1
            existing_user.unsubscribed_at = None
            db.commit()
            user = existing_user
        else:
            new_user = User(
                name=request.name,
                email=request.email,
                birth_month=request.birth_month,
                birth_day=request.birth_day,
                zodiac_sign=zodiac_sign,
                last_horoscope_sent=datetime.now(),
                unsubscribe_token=generate_unsubscribe_token(),
                is_subscribed=1,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user

        horoscope_html = generate_horoscope(zodiac_sign, request.name)
        send_email(request.email, zodiac_sign, horoscope_html, user.unsubscribe_token)

        return {
            "success": True,
            "zodiac_sign": zodiac_sign,
            "message": f"Horoscope sent to {request.name} ({zodiac_sign}) at {request.email}!",
            "user_id": user.id,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"Internal error in /api/send-horoscope: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


class SendHoroscopeByEmailRequest(BaseModel):
    email: EmailStr


@app.post("/api/send-horoscope-by-email")
def send_horoscope_by_email(
    request: SendHoroscopeByEmailRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    try:
        user = db.query(User).filter(User.email == request.email).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"User with email {request.email} not found. "
                    "Please register first using /api/send-horoscope"
                ),
            )

        if not user.is_subscribed:
            raise HTTPException(
                status_code=403,
                detail="Ez az email cím le van iratkozva a napi horoszkópról.",
            )

        horoscope_html = generate_horoscope(user.zodiac_sign, user.name)
        send_email(user.email, user.zodiac_sign, horoscope_html, user.unsubscribe_token)

        user.last_horoscope_sent = datetime.now()
        db.commit()

        return {
            "success": True,
            "zodiac_sign": user.zodiac_sign,
            "message": f"Horoscope sent to {user.name} ({user.zodiac_sign}) at {user.email}!",
            "user_id": user.id,
            "sent_at": user.last_horoscope_sent.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Internal error in /api/send-horoscope-by-email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.post("/api/send-all-horoscopes")
def send_all_horoscopes(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    try:
        users = db.query(User).filter(User.is_subscribed == 1).all()

        if not users:
            return {
                "success": False,
                "message": "No subscribed users in database",
            }

        results = {
            "total_users": len(users),
            "sent": 0,
            "failed": 0,
            "details": [],
        }

        for user in users:
            try:
                if not user.unsubscribe_token:
                    user.unsubscribe_token = generate_unsubscribe_token()
                    db.commit()
                    db.refresh(user)

                horoscope_html = generate_horoscope(user.zodiac_sign, user.name)
                send_email(
                    user.email,
                    user.zodiac_sign,
                    horoscope_html,
                    user.unsubscribe_token,
                )

                user.last_horoscope_sent = datetime.now()
                db.commit()

                results["sent"] += 1
                results["details"].append(
                    {
                        "email": user.email,
                        "name": user.name,
                        "status": "success",
                    }
                )

                time.sleep(1)

            except Exception as e:
                db.rollback()
                results["failed"] += 1
                results["details"].append(
                    {
                        "email": user.email,
                        "name": user.name,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return {
            "success": True,
            "message": f"Sent {results['sent']} horoscopes, {results['failed']} failed",
            "results": results,
        }

    except Exception as e:
        print(f"Internal error in /api/send-all-horoscopes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.delete("/api/user/{email}")
def delete_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    try:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with email {email} not found",
            )

        db.delete(user)
        db.commit()

        return {
            "success": True,
            "message": f"User {user.name} ({email}) successfully deleted",
            "deleted_user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "zodiac_sign": user.zodiac_sign,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Internal error in /api/user/{{email}} delete: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


@app.get("/api/users")
def get_all_users(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    users = db.query(User).all()
    return {
        "total": len(users),
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "birth_month": user.birth_month,
                "birth_day": user.birth_day,
                "zodiac_sign": user.zodiac_sign,
                "subscribed_at": user.subscribed_at,
                "last_horoscope_sent": user.last_horoscope_sent,
                "unsubscribed_at": user.unsubscribed_at,
                "is_subscribed": user.is_subscribed,
                "unsubscribe_token": user.unsubscribe_token,
            }
            for user in users
        ],
    }


@app.get("/api/unsubscribe")
def api_unsubscribe_get(token: str, db: Session = Depends(get_db)):
    return _api_unsubscribe_common(token, db)


@app.post("/api/unsubscribe")
def api_unsubscribe_post(token: str, db: Session = Depends(get_db)):
    return _api_unsubscribe_common(token, db)


def _api_unsubscribe_common(token: str, db: Session):
    if not token:
        raise HTTPException(status_code=400, detail="Hiányzó token")

    user = db.query(User).filter(User.unsubscribe_token == token).first()

    if not user:
        return {
            "success": False,
            "message": "Érvénytelen vagy lejárt leiratkozási link.",
        }

    if not user.is_subscribed:
        return {
            "success": True,
            "already_unsubscribed": True,
            "message": f"A(z) {user.email} cím már korábban leiratkozott.",
        }

    user.is_subscribed = 0
    user.unsubscribed_at = datetime.now().isoformat()
    db.commit()

    return {
        "success": True,
        "already_unsubscribed": False,
        "message": f"A(z) {user.email} cím sikeresen leiratkozott a napi horoszkópról.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6100)
