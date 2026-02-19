from datetime import datetime, timedelta, time, timezone

from sqlalchemy import and_, case, func, or_

from app import db
from app.models import Lot, LotQC


DASHBOARD_STATUS = [
    {"code": "1", "key": "AVAILABLE", "label": "Disponible", "badge_class": "status-badge status-available"},
    {"code": "2", "key": "ASSIGNED", "label": "Asignada", "badge_class": "status-badge status-assigned"},
    {"code": "3", "key": "STARTED", "label": "En fumigación", "badge_class": "status-badge status-active"},
    {"code": "4", "key": "COMPLETED", "label": "Finalizada", "badge_class": "status-badge status-done"},
]

DASHBOARD_ALERTS = {
    "no_qc_over_24h": {"hours": 24, "label": "Lotes sin QC > 24 horas"},
    "missing_net_weight_over_12h": {"hours": 12, "label": "Lotes sin peso neto > 12 horas"},
    "no_fumigation_over_48h": {"hours": 48, "label": "Lotes sin fumigación > 48 horas"},
}


def _server_now_local():
    return datetime.now(timezone.utc).astimezone()


def _to_utc_naive(aware_dt):
    return aware_dt.astimezone(timezone.utc).replace(tzinfo=None)


def _today_window_utc_naive(now_local):
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=now_local.tzinfo)
    end_local = start_local + timedelta(days=1)
    return _to_utc_naive(start_local), _to_utc_naive(end_local)


def _alert_cutoff_utc_naive(now_local, hours):
    return _to_utc_naive(now_local - timedelta(hours=hours))


def _build_dashboard_summary(now_local=None):
    now_local = now_local or _server_now_local()
    start_utc_naive, end_utc_naive = _today_window_utc_naive(now_local)

    today_lots, today_kg = db.session.query(
        func.count(Lot.id),
        func.coalesce(
            func.sum(
                case(
                    (and_(Lot.net_weight.isnot(None), Lot.net_weight > 0), Lot.net_weight),
                    else_=0.0,
                )
            ),
            0.0,
        ),
    ).filter(
        Lot.created_at.isnot(None),
        Lot.created_at >= start_utc_naive,
        Lot.created_at < end_utc_naive,
    ).one()

    status_counts = {status["key"]: 0 for status in DASHBOARD_STATUS}
    status_rows = db.session.query(
        Lot.fumigation_status,
        func.count(Lot.id),
    ).group_by(
        Lot.fumigation_status
    ).all()
    status_code_to_key = {status["code"]: status["key"] for status in DASHBOARD_STATUS}
    for status_code, count in status_rows:
        key = status_code_to_key.get(status_code)
        if key:
            status_counts[key] = int(count)

    no_qc_count = db.session.query(func.count(Lot.id)).outerjoin(
        LotQC, LotQC.lot_id == Lot.id
    ).filter(
        Lot.created_at.isnot(None),
        Lot.created_at < _alert_cutoff_utc_naive(now_local, DASHBOARD_ALERTS["no_qc_over_24h"]["hours"]),
        LotQC.id.is_(None),
    ).scalar() or 0

    no_net_weight_count = db.session.query(func.count(Lot.id)).filter(
        Lot.created_at.isnot(None),
        Lot.created_at < _alert_cutoff_utc_naive(now_local, DASHBOARD_ALERTS["missing_net_weight_over_12h"]["hours"]),
        or_(Lot.net_weight.is_(None), Lot.net_weight <= 0),
    ).scalar() or 0

    no_fumigation_count = db.session.query(func.count(Lot.id)).filter(
        Lot.created_at.isnot(None),
        Lot.created_at < _alert_cutoff_utc_naive(now_local, DASHBOARD_ALERTS["no_fumigation_over_48h"]["hours"]),
        Lot.fumigation_status == "1",
    ).scalar() or 0

    return {
        "generated_at": now_local.isoformat(),
        "today": {
            "lots_received": int(today_lots),
            "kilograms_received": round(float(today_kg), 2),
        },
        "fumigation_status": [
            {
                "key": status["key"],
                "label": status["label"],
                "badge_class": status["badge_class"],
                "count": status_counts[status["key"]],
            }
            for status in DASHBOARD_STATUS
        ],
        "alerts": [
            {
                "key": "no_qc_over_24h",
                "label": DASHBOARD_ALERTS["no_qc_over_24h"]["label"],
                "count": int(no_qc_count),
            },
            {
                "key": "missing_net_weight_over_12h",
                "label": DASHBOARD_ALERTS["missing_net_weight_over_12h"]["label"],
                "count": int(no_net_weight_count),
            },
            {
                "key": "no_fumigation_over_48h",
                "label": DASHBOARD_ALERTS["no_fumigation_over_48h"]["label"],
                "count": int(no_fumigation_count),
            },
        ],
    }
