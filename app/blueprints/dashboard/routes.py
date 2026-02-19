from flask import jsonify, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import text

from app import app, cache, db
from app.blueprints.dashboard import bp
from app.blueprints.dashboard.services import _build_dashboard_summary
from app.permissions import (
    can_access_lot_lists,
    can_execute_operational_actions,
    can_view_operational_dashboard,
    dashboard_required,
)


def _attach_alert_links(summary):
    for alert in summary.get("alerts", []):
        alert["link"] = url_for("materiaprima.list_lots", alert=alert["key"])
    return summary


def _build_operational_summary_for_user(user):
    summary = _attach_alert_links(_build_dashboard_summary())
    if not can_access_lot_lists(user):
        for alert in summary["alerts"]:
            alert["link"] = None
    return summary


@bp.route('/')
def index():
    dashboard_summary = None
    show_operational_dashboard = False
    can_execute_actions = False
    if can_view_operational_dashboard(current_user):
        dashboard_summary = _build_operational_summary_for_user(current_user)
        show_operational_dashboard = True
        can_execute_actions = can_execute_operational_actions(current_user)

    return render_template(
        'index.html',
        dashboard_summary=dashboard_summary,
        show_operational_dashboard=show_operational_dashboard,
        can_execute_actions=can_execute_actions,
    )


@bp.route('/api/index/summary')
@login_required
# Cache dashboard summary per user; timeout is controlled by CACHE_TIMEOUT_DASHBOARD (default 60s) to reduce repeated polling queries.
@cache.cached(timeout=None, key_prefix=lambda: f"api:index:summary:{current_user.get_id() or 'anon'}")
def index_summary_api():
    if not can_view_operational_dashboard(current_user):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(_build_operational_summary_for_user(current_user))


@bp.route('/dashboard/tv')
@login_required
@dashboard_required
def dashboard_tv():
    return render_template('dashboard_tv.html')


@bp.route('/api/dashboard/summary')
@login_required
@dashboard_required
# Cache dashboard TV summary per user; timeout is controlled by CACHE_TIMEOUT_DASHBOARD (default 60s) to reduce repeated polling queries.
@cache.cached(timeout=None, key_prefix=lambda: f"api:dashboard:summary:{current_user.get_id() or 'anon'}")
def dashboard_summary_api():
    return jsonify(_attach_alert_links(_build_dashboard_summary()))


@bp.route('/healthz')
def healthz():
    db_ok = False
    error_message = None
    try:
        db.session.execute(text('SELECT 1'))
        db_ok = True
    except Exception as exc:
        app.logger.exception('Health check database failure')
        error_message = str(exc)

    payload = {
        'status': 'ok' if db_ok else 'degraded',
        'app': 'ok',
        'database': 'ok' if db_ok else 'error',
    }
    if error_message:
        payload['error'] = error_message
    return jsonify(payload), (200 if db_ok else 503)
