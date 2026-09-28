"""认证路由。"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.core.deps import get_current_user, student_only
from app.models.course import Course, CourseEnrollment
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.user import (
    RegisterIn,
    LoginIn,
    TokenOut,
    UserOut,
    UserUpdate,
    StudentSettingsUpdate,
)
from app.schemas.common import R

router = APIRouter(prefix="/api/auth", tags=["auth"])

_login_failures = SlidingWindowLimiter(
    settings.AUTH_LOGIN_MAX_FAILURES,
    settings.AUTH_LOGIN_WINDOW_SECONDS,
)
_registrations = SlidingWindowLimiter(
    settings.AUTH_REGISTER_MAX_REQUESTS,
    settings.AUTH_REGISTER_WINDOW_SECONDS,
)
# Unknown usernames still execute a real KDF verification, reducing the timing
# difference that would otherwise make account enumeration easier.
_DUMMY_PASSWORD_HASH = hash_password("xunkeflow-dummy-login-comparison")


def _peer(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many(retry_after: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(max(1, retry_after))},
    )


@router.post("/register", response_model=R)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    register_key = f"register:{_peer(request)}"
    retry_after = _registrations.retry_after(register_key)
    if retry_after:
        raise _too_many(retry_after, "注册请求过于频繁，请稍后再试")
    _registrations.hit(register_key)
    if body.role != "student":
        raise HTTPException(403, "公开注册仅支持学生账号，教师和管理员账号请联系系统管理员创建")
    if db.query(User).filter(or_(User.username == body.username, User.email == body.email)).first():
        raise HTTPException(400, detail="用户名或邮箱已存在")
    user = User(username=body.username, email=body.email, hashed_password=hash_password(body.password),
                role="student", full_name=body.full_name, student_no=body.student_no)
    db.add(user)
    db.commit()
    db.refresh(user)
    return R.ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.post("/login", response_model=R)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    normalized_login = body.username.strip().casefold()
    limiter_key = f"login:{_peer(request)}:{normalized_login}"
    retry_after = _login_failures.retry_after(limiter_key)
    if retry_after:
        raise _too_many(retry_after, "登录失败次数过多，请稍后再试")
    user = db.query(User).filter(or_(User.username == body.username, User.email == body.username)).first()
    password_hash = user.hashed_password if user else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, password_hash)
    if not user or not password_ok:
        retry_after = _login_failures.hit(limiter_key)
        if retry_after:
            raise _too_many(retry_after, "登录失败次数过多，请稍后再试")
        raise HTTPException(401, detail="用户名或密码错误")
    if not user.is_active:
        retry_after = _login_failures.hit(limiter_key)
        if retry_after:
            raise _too_many(retry_after, "登录失败次数过多，请稍后再试")
        raise HTTPException(403, detail="账号已被禁用")
    _login_failures.clear(limiter_key)
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)
        db.commit()
    token = create_access_token(user.id, {"role": user.role})
    return R.ok(TokenOut(access_token=token, role=user.role,
                         user=UserOut.model_validate(user).model_dump(mode="json")).model_dump(mode="json"))


@router.get("/me", response_model=R)
def me(user: User = Depends(get_current_user)):
    return R.ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.put("/me", response_model=R)
def update_me(body: UserUpdate, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in changes and db.query(User).filter(
        User.email == changes["email"], User.id != user.id
    ).first():
        raise HTTPException(400, "邮箱已被其他账号使用")
    # 账号启停只能由管理员操作，个人资料接口不能改变账号状态。
    allowed = {"full_name", "avatar", "email", "student_no"}
    for k, v in changes.items():
        if k not in allowed:
            continue
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return R.ok(UserOut.model_validate(user).model_dump(mode="json"))


@router.get("/me/settings", response_model=R)
def student_settings(user: User = Depends(student_only),
                     db: Session = Depends(get_db)):
    """返回账号信息、默认学习策略以及每门已选课程的实际设置。"""
    return R.ok(_student_settings_payload(db, user))


@router.put("/me/settings", response_model=R)
def update_student_settings(body: StudentSettingsUpdate,
                            user: User = Depends(student_only),
                            db: Session = Depends(get_db)):
    """事务化保存个人资料与学习策略，且绝不接受角色或账号状态字段。"""
    duplicated = db.query(User).filter(
        func.lower(User.email) == body.email.casefold(),
        User.id != user.id,
    ).first()
    if duplicated:
        raise HTTPException(400, "邮箱已被其他账号使用")

    enrollment = None
    if body.course_id is not None:
        enrollment = db.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == body.course_id,
            CourseEnrollment.student_id == user.id,
        ).first()
        if not enrollment:
            raise HTTPException(404, "尚未加入该课程，无法修改课程学习计划")

    preference_text = ",".join(body.learning_preferences)
    user.full_name = body.full_name
    user.email = body.email
    user.learning_goal = body.learning_goal
    user.weekly_hours = body.weekly_hours
    user.learning_preferences = preference_text

    if enrollment is not None:
        enrollment.goal = body.learning_goal
        enrollment.weekly_hours = body.weekly_hours
        profile = db.query(StudentProfile).filter(
            StudentProfile.student_id == user.id,
            StudentProfile.course_id == body.course_id,
        ).first()
        if profile:
            profile.goal = body.learning_goal
            profile.weekly_hours = body.weekly_hours
            profile.pref_format = preference_text[:64]
            profile.pref_style = _preference_style(body.learning_preferences)

    db.commit()
    db.refresh(user)
    return R.ok(_student_settings_payload(db, user))


def _preference_style(preferences: list[str]) -> str:
    if "实践演练" in preferences:
        return "实践型"
    if "视觉图解" in preferences:
        return "图解型"
    if "案例研讨" in preferences:
        return "探究型"
    return "理解型"


def _student_settings_payload(db: Session, user: User) -> dict:
    rows = db.query(CourseEnrollment, Course).join(
        Course, Course.id == CourseEnrollment.course_id
    ).filter(
        CourseEnrollment.student_id == user.id,
        Course.status == "active",
    ).order_by(Course.id.desc()).all()
    preferences = [
        item.strip() for item in (user.learning_preferences or "").split(",")
        if item.strip()
    ] or ["文本精读", "视觉图解", "实践演练"]
    return {
        "user": UserOut.model_validate(user).model_dump(mode="json"),
        "learning_goal": user.learning_goal or "",
        "weekly_hours": int(user.weekly_hours or 6),
        "learning_preferences": preferences,
        "courses": [
            {
                "course_id": course.id,
                "name": course.name,
                "code": course.code,
                "goal": enrollment.goal,
                "weekly_hours": enrollment.weekly_hours,
            }
            for enrollment, course in rows
        ],
    }
