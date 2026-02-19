from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def is_admin(user):
    return bool(user and user.is_authenticated and user.has_role("Admin"))


def has_area_role(user, area_name, roles):
    if not user or not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if not user.from_area(area_name):
        return False
    return any(user.has_role(role_name) for role_name in roles)


def can_view_operational_dashboard(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and not user.is_external
        and (
            user.has_role("Admin")
            or user.has_role("Dashboard")
            or user.from_area("Materia Prima")
            or user.from_area("Calidad")
        )
    )


def can_access_lot_lists(user):
    return has_area_role(user, "Materia Prima", ["Contribuidor", "Lector"])


def can_execute_operational_actions(user):
    return has_area_role(user, "Materia Prima", ["Contribuidor"])


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin(current_user):
            flash("Acceso restringido.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return wrapper


def area_role_required(area_name, roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Acceso restringido.", "error")
                return redirect(url_for("login"))
            if not has_area_role(current_user, area_name, roles):
                flash("Acceso restringido.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)

        return wrapper

    return decorator


def dashboard_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Acceso restringido.", "error")
            return redirect(url_for("login"))
        if current_user.has_role("Admin") or current_user.has_role("Dashboard"):
            return f(*args, **kwargs)
        flash("Acceso restringido.", "error")
        return redirect(url_for("index"))

    return wrapper
