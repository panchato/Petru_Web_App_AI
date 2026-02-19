import qrcode
import base64
from flask import render_template, redirect, url_for, flash, send_file, request, jsonify, abort
from urllib.parse import urlparse, urljoin
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm, AddUserForm, EditUserForm, AddRoleForm, AddAreaForm, AssignRoleForm, AssignAreaForm, AddClientForm, AddGrowerForm, AddVarietyForm, AddRawMaterialPackagingForm, CreateRawMaterialReceptionForm, CreateLotForm, FullTruckWeightForm, LotQCForm, SampleQCForm, FumigationForm, StartFumigationForm, CompleteFumigationForm
from app.models import User, Role, Area, Client, Grower, Variety, RawMaterialPackaging, RawMaterialReception, Lot, LotQC, SampleQC, Fumigation
from app import app, db, bcrypt, cache
from app.upload_security import UploadValidationError, resolve_upload_path, save_uploaded_file
from app.permissions import (
    admin_required,
    area_role_required,
    dashboard_required,
    can_access_lot_lists,
    can_execute_operational_actions,
    can_view_operational_dashboard,
)
from app.services import (
    FumigationService,
    LotService,
    LotValidationError,
    QCService,
    QCValidationError,
    can_transition,
    get_cached_pdf,
    save_pdf_to_cache,
    invalidate_cached_pdf,
)
from io import BytesIO
from datetime import datetime, timezone, date, timedelta, time
from weasyprint import HTML
from sqlalchemy import func, case, and_, or_, text
from sqlalchemy.orm import joinedload, selectinload


def is_safe_redirect_url(target):
    base_url = urlparse(request.host_url)
    target_url = urlparse(urljoin(request.host_url, target))
    return base_url.scheme == target_url.scheme and base_url.netloc == target_url.netloc

def _parse_date_arg(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _qc_payload_from_form(form, include_lot=False):
    payload = {
        "analyst": form.analyst.data,
        "date": form.date.data,
        "time": form.time.data,
        "inshell_weight": form.inshell_weight.data,
        "lessthan30": form.lessthan30.data,
        "between3032": form.between3032.data,
        "between3234": form.between3234.data,
        "between3436": form.between3436.data,
        "morethan36": form.morethan36.data,
        "broken_walnut": form.broken_walnut.data,
        "split_walnut": form.split_walnut.data,
        "light_stain": form.light_stain.data,
        "serious_stain": form.serious_stain.data,
        "adhered_hull": form.adhered_hull.data,
        "shrivel": form.shrivel.data,
        "empty": form.empty.data,
        "insect_damage": form.insect_damage.data,
        "inactive_fungus": form.inactive_fungus.data,
        "active_fungus": form.active_fungus.data,
        "extra_light": form.extra_light.data,
        "light": form.light.data,
        "light_amber": form.light_amber.data,
        "amber": form.amber.data,
        "yellow": form.yellow.data,
    }
    if include_lot:
        payload["lot_id"] = form.lot_id.data
    return payload


def _paginate_query(query):
    default_per_page = int(app.config.get("DEFAULT_PAGE_SIZE", 50))
    max_per_page = int(app.config.get("MAX_PAGE_SIZE", 200))

    page = request.args.get("page", default=1, type=int) or 1
    requested_per_page = request.args.get("per_page", type=int)
    per_page = requested_per_page if requested_per_page and requested_per_page > 0 else default_per_page
    per_page = min(per_page, max_per_page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    page_args = request.args.to_dict(flat=True)
    page_args.pop("page", None)
    if requested_per_page:
        page_args["per_page"] = str(per_page)
    else:
        page_args.pop("per_page", None)
    return pagination.items, pagination, page_args


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


def _apply_lot_alert_filter(query, alert_key, now_local):
    if alert_key not in DASHBOARD_ALERTS:
        return query

    hours = DASHBOARD_ALERTS[alert_key]["hours"]
    cutoff = _alert_cutoff_utc_naive(now_local, hours)
    base_conditions = [Lot.created_at.isnot(None), Lot.created_at < cutoff]

    if alert_key == "no_qc_over_24h":
        return query.outerjoin(LotQC, LotQC.lot_id == Lot.id).filter(
            *base_conditions,
            LotQC.id.is_(None),
        )
    if alert_key == "missing_net_weight_over_12h":
        return query.filter(
            *base_conditions,
            or_(Lot.net_weight.is_(None), Lot.net_weight <= 0),
        )
    if alert_key == "no_fumigation_over_48h":
        return query.filter(
            *base_conditions,
            Lot.fumigation_status == "1",
        )
    return query


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

    alerts = [
        {
            "key": "no_qc_over_24h",
            "label": DASHBOARD_ALERTS["no_qc_over_24h"]["label"],
            "count": int(no_qc_count),
            "link": url_for("list_lots", alert="no_qc_over_24h"),
        },
        {
            "key": "missing_net_weight_over_12h",
            "label": DASHBOARD_ALERTS["missing_net_weight_over_12h"]["label"],
            "count": int(no_net_weight_count),
            "link": url_for("list_lots", alert="missing_net_weight_over_12h"),
        },
        {
            "key": "no_fumigation_over_48h",
            "label": DASHBOARD_ALERTS["no_fumigation_over_48h"]["label"],
            "count": int(no_fumigation_count),
            "link": url_for("list_lots", alert="no_fumigation_over_48h"),
        },
    ]

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
        "alerts": alerts,
    }


def _upload_path_to_file_uri(stored_path):
    upload_path = resolve_upload_path(stored_path)
    if not upload_path:
        return None
    return upload_path.resolve().as_uri()


def _upload_mimetype_for_path(upload_path):
    suffix = upload_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _send_private_upload(stored_path):
    upload_path = resolve_upload_path(stored_path)
    if not upload_path:
        abort(404)
    return send_file(upload_path, mimetype=_upload_mimetype_for_path(upload_path), as_attachment=False)


def _build_operational_summary_for_user(user):
    summary = _build_dashboard_summary()
    if not can_access_lot_lists(user):
        for alert in summary["alerts"]:
            alert["link"] = None
    return summary


@app.route('/')
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


@app.route('/api/index/summary')
@login_required
# Cache dashboard summary per user; timeout is controlled by CACHE_TIMEOUT_DASHBOARD (default 60s) to reduce repeated polling queries.
@cache.cached(timeout=None, key_prefix=lambda: f"api:index:summary:{current_user.get_id() or 'anon'}")
def index_summary_api():
    if not can_view_operational_dashboard(current_user):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(_build_operational_summary_for_user(current_user))

@app.route('/dashboard/tv')
@login_required
@dashboard_required
def dashboard_tv():
    return render_template('dashboard_tv.html')

@app.route('/api/dashboard/summary')
@login_required
@dashboard_required
# Cache dashboard TV summary per user; timeout is controlled by CACHE_TIMEOUT_DASHBOARD (default 60s) to reduce repeated polling queries.
@cache.cached(timeout=None, key_prefix=lambda: f"api:dashboard:summary:{current_user.get_id() or 'anon'}")
def dashboard_summary_api():
    return jsonify(_build_dashboard_summary())


@app.route('/healthz')
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Usuario ya se encuentra conectado.')
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user is None:
            flash('Usuario incorrecto.')
            return redirect(url_for('login'))
        
        if not user.is_active:
            flash('Cuenta no activa. Por favor, contacte al administrador.')
            return redirect(url_for('login'))
        
        if bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            # Prevent open redirects by allowing only same-host relative URLs
            if next_page and is_safe_redirect_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Contraseña incorrecta.')
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Usuario se ha desconectado exitosamente.')
    return redirect(url_for('login'))

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone_number=form.phone_number.data,
            password_hash=bcrypt.generate_password_hash(form.password.data),
        ) # type: ignore
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('list_users'))
    return render_template('add_user.html', title='Add User', form=form)

@app.route('/list_users')
@login_required
@admin_required
def list_users():
    users_query = User.query.options(
        selectinload(User.roles),
        selectinload(User.areas),
    ).order_by(User.created_at.desc(), User.id.desc())
    users, pagination, pagination_args = _paginate_query(users_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_users.html',
        users=users,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        user.name = form.name.data
        user.last_name = form.last_name.data
        user.email = form.email.data
        user.phone_number = form.phone_number.data
        db.session.commit()
        flash('Usuario actualizado exitosamente.', 'success')
        return redirect(url_for('list_users'))
    return render_template('edit_user.html', form=form, user=user)

@app.route('/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    estado = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario {user.name} {estado}.', 'success')
    return redirect(url_for('list_users'))

@app.route('/add_role', methods=['GET', 'POST'])
@login_required
@admin_required
def add_role():
    form = AddRoleForm()
    if form.validate_on_submit():
        role = Role(name=form.name.data, description=form.description.data) # type: ignore
        db.session.add(role)
        db.session.commit()
        return redirect(url_for('list_roles'))
    return render_template('add_role.html', form=form)

@app.route('/assign_role', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_role():
    form = AssignRoleForm()
    if form.validate_on_submit():
        user = db.session.get(User, form.user_id.data)
        role = db.session.get(Role, form.role_id.data)
        if user is None or role is None:
            flash('Usuario o rol no encontrado.', 'error')
            return redirect(url_for('assign_role'))
        if role not in user.roles:
            user.roles.append(role)
            db.session.commit()
        else:
            flash('Este usuario ya tiene el rol asignado.', 'warning')
        return redirect(url_for('assign_role'))
    return render_template('assign_role.html', form=form)

@app.route('/list_roles')
@login_required
@admin_required
def list_roles():
    roles_query = Role.query.order_by(Role.name.asc(), Role.id.asc())
    roles, pagination, pagination_args = _paginate_query(roles_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_roles.html',
        roles=roles,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_role/<int:role_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_role(role_id):
    role = Role.query.get_or_404(role_id)
    form = AddRoleForm(obj=role)
    if form.validate_on_submit():
        role.name = form.name.data
        role.description = form.description.data
        db.session.commit()
        flash('Rol actualizado exitosamente.', 'success')
        return redirect(url_for('list_roles'))
    return render_template('edit_role.html', form=form, role=role)

@app.route('/toggle_role/<int:role_id>', methods=['POST'])
@login_required
@admin_required
def toggle_role(role_id):
    role = Role.query.get_or_404(role_id)
    role.is_active = not role.is_active
    db.session.commit()
    estado = 'activado' if role.is_active else 'desactivado'
    flash(f'Rol {role.name} {estado}.', 'success')
    return redirect(url_for('list_roles'))

@app.route('/add_area', methods=['GET', 'POST'])
@login_required
@admin_required
def add_area():
    form = AddAreaForm()
    if form.validate_on_submit():
        area = Area(name=form.name.data, description=form.description.data) # type: ignore
        db.session.add(area)
        db.session.commit()
        return redirect(url_for('list_areas'))
    return render_template('add_area.html', form=form)

@app.route('/assign_area', methods=['GET', 'POST'])
@login_required
@admin_required
def assign_area():
    form = AssignAreaForm()
    if form.validate_on_submit():
        user = db.session.get(User, form.user_id.data)
        area = db.session.get(Area, form.area_id.data)
        if user is None or area is None:
            flash('Usuario o área no encontrada.', 'error')
            return redirect(url_for('assign_area'))
        if area not in user.areas:
            user.areas.append(area)
            db.session.commit()
        else:
            flash('Este usuario ya tiene el área asignada.', 'warning')
        return redirect(url_for('assign_area'))
    return render_template('assign_area.html', form=form)

@app.route('/list_areas')
@login_required
@admin_required
def list_areas():
    areas_query = Area.query.order_by(Area.name.asc(), Area.id.asc())
    areas, pagination, pagination_args = _paginate_query(areas_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_areas.html',
        areas=areas,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_area/<int:area_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_area(area_id):
    area = Area.query.get_or_404(area_id)
    form = AddAreaForm(obj=area)
    if form.validate_on_submit():
        area.name = form.name.data
        area.description = form.description.data
        db.session.commit()
        flash('Área actualizada exitosamente.', 'success')
        return redirect(url_for('list_areas'))
    return render_template('edit_area.html', form=form, area=area)

@app.route('/toggle_area/<int:area_id>', methods=['POST'])
@login_required
@admin_required
def toggle_area(area_id):
    area = Area.query.get_or_404(area_id)
    area.is_active = not area.is_active
    db.session.commit()
    estado = 'activada' if area.is_active else 'desactivada'
    flash(f'Área {area.name} {estado}.', 'success')
    return redirect(url_for('list_areas'))

@app.route('/add_client', methods=['GET', 'POST'])
@login_required
@admin_required
def add_client():
    form = AddClientForm()
    if form.validate_on_submit():
        client = Client(
            name=form.name.data,
            tax_id=form.tax_id.data,
            address=form.address.data,
            comuna=form.comuna.data) # type: ignore
        db.session.add(client)
        db.session.commit()
        return redirect(url_for('list_clients'))
    return render_template('add_client.html', title='Add Client', form=form)

@app.route('/list_clients')
@login_required
@admin_required
def list_clients():
    clients_query = Client.query.order_by(Client.name.asc(), Client.id.asc())
    clients, pagination, pagination_args = _paginate_query(clients_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_clients.html',
        clients=clients,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = AddClientForm(obj=client)
    if form.validate_on_submit():
        client.name = form.name.data
        client.tax_id = form.tax_id.data
        client.address = form.address.data
        client.comuna = form.comuna.data
        db.session.commit()
        flash('Cliente actualizado exitosamente.', 'success')
        return redirect(url_for('list_clients'))
    return render_template('edit_client.html', form=form, client=client)

@app.route('/toggle_client/<int:client_id>', methods=['POST'])
@login_required
@admin_required
def toggle_client(client_id):
    client = Client.query.get_or_404(client_id)
    client.is_active = not client.is_active
    db.session.commit()
    estado = 'activado' if client.is_active else 'desactivado'
    flash(f'Cliente {client.name} {estado}.', 'success')
    return redirect(url_for('list_clients'))

@app.route('/add_grower', methods=['GET', 'POST'])
@login_required
@admin_required
def add_grower():
    form = AddGrowerForm()
    if form.validate_on_submit():
        grower = Grower(
            name=form.name.data,
            tax_id=form.tax_id.data,
            csg_code=form.csg_code.data) # type: ignore
        db.session.add(grower)
        db.session.commit()
        return redirect(url_for('list_growers'))
    return render_template('add_grower.html', form=form)

@app.route('/list_growers')
@login_required
@admin_required
def list_growers():
    growers_query = Grower.query.order_by(Grower.name.asc(), Grower.id.asc())
    growers, pagination, pagination_args = _paginate_query(growers_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_growers.html',
        growers=growers,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_grower/<int:grower_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_grower(grower_id):
    grower = Grower.query.get_or_404(grower_id)
    form = AddGrowerForm(obj=grower)
    if form.validate_on_submit():
        grower.name = form.name.data
        grower.tax_id = form.tax_id.data
        grower.csg_code = form.csg_code.data
        db.session.commit()
        flash('Productor actualizado exitosamente.', 'success')
        return redirect(url_for('list_growers'))
    return render_template('edit_grower.html', form=form, grower=grower)

@app.route('/toggle_grower/<int:grower_id>', methods=['POST'])
@login_required
@admin_required
def toggle_grower(grower_id):
    grower = Grower.query.get_or_404(grower_id)
    grower.is_active = not grower.is_active
    db.session.commit()
    estado = 'activado' if grower.is_active else 'desactivado'
    flash(f'Productor {grower.name} {estado}.', 'success')
    return redirect(url_for('list_growers'))

@app.route('/add_variety', methods=['GET', 'POST'])
@login_required
@admin_required
def add_variety():
    form = AddVarietyForm()
    if form.validate_on_submit():
        variety = Variety(
            name=form.name.data) # type: ignore
        db.session.add(variety)
        db.session.commit()
        return redirect(url_for('list_varieties'))
    return render_template('add_variety.html', form=form)

@app.route('/list_varieties')
@login_required
@admin_required
def list_varieties():
    varieties_query = Variety.query.order_by(Variety.name.asc(), Variety.id.asc())
    varieties, pagination, pagination_args = _paginate_query(varieties_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_varieties.html',
        varieties=varieties,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_variety/<int:variety_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_variety(variety_id):
    variety = Variety.query.get_or_404(variety_id)
    form = AddVarietyForm(obj=variety)
    if form.validate_on_submit():
        variety.name = form.name.data
        db.session.commit()
        flash('Variedad actualizada exitosamente.', 'success')
        return redirect(url_for('list_varieties'))
    return render_template('edit_variety.html', form=form, variety=variety)

@app.route('/toggle_variety/<int:variety_id>', methods=['POST'])
@login_required
@admin_required
def toggle_variety(variety_id):
    variety = Variety.query.get_or_404(variety_id)
    variety.is_active = not variety.is_active
    db.session.commit()
    estado = 'activada' if variety.is_active else 'desactivada'
    flash(f'Variedad {variety.name} {estado}.', 'success')
    return redirect(url_for('list_varieties'))

@app.route('/add_raw_material_packaging', methods=['GET', 'POST'])
@login_required
@admin_required
def add_raw_material_packaging():
    form = AddRawMaterialPackagingForm()
    if form.validate_on_submit():
        rmp = RawMaterialPackaging(
            name=form.name.data,
            tare=form.tare.data) # type: ignore
        db.session.add(rmp)
        db.session.commit()
        return redirect(url_for('list_raw_material_packagings'))
    return render_template('add_raw_material_packaging.html', form=form)

@app.route('/list_raw_material_packagings')
@login_required
@admin_required
def list_raw_material_packagings():
    rmps_query = RawMaterialPackaging.query.order_by(RawMaterialPackaging.name.asc(), RawMaterialPackaging.id.asc())
    rmps, pagination, pagination_args = _paginate_query(rmps_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_raw_material_packagings.html',
        rmps=rmps,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/edit_raw_material_packaging/<int:rmp_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_raw_material_packaging(rmp_id):
    rmp = RawMaterialPackaging.query.get_or_404(rmp_id)
    form = AddRawMaterialPackagingForm(obj=rmp)
    if form.validate_on_submit():
        rmp.name = form.name.data
        rmp.tare = form.tare.data
        db.session.commit()
        flash('Envase actualizado exitosamente.', 'success')
        return redirect(url_for('list_raw_material_packagings'))
    return render_template('edit_raw_material_packaging.html', form=form, rmp=rmp)

@app.route('/toggle_raw_material_packaging/<int:rmp_id>', methods=['POST'])
@login_required
@admin_required
def toggle_raw_material_packaging(rmp_id):
    rmp = RawMaterialPackaging.query.get_or_404(rmp_id)
    rmp.is_active = not rmp.is_active
    db.session.commit()
    estado = 'activado' if rmp.is_active else 'desactivado'
    flash(f'Envase {rmp.name} {estado}.', 'success')
    return redirect(url_for('list_raw_material_packagings'))

@app.route('/create_raw_material_reception', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def create_raw_material_reception():
    form = CreateRawMaterialReceptionForm()
    reception_id = None
    if form.validate_on_submit():
        reception = RawMaterialReception(
            waybill=form.waybill.data,
            date=form.date.data,
            time=form.time.data,
            truck_plate=form.truck_plate.data,
            trucker_name=form.trucker_name.data,
            observations=form.observations.data
        ) # type: ignore

        selected_grower = db.session.get(Grower, form.grower_id.data)
        selected_client = db.session.get(Client, form.client_id.data)
        if selected_grower:
            reception.growers.append(selected_grower)
        if selected_client:
            reception.clients.append(selected_client)

        db.session.add(reception)
        db.session.commit()
        reception_id = reception.id
        flash('Recepción de Materia Prima creada exitosamente.', 'success')

    return render_template('create_raw_material_reception.html', form=form, reception_id=reception_id)

@app.route('/list_rmrs')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def list_rmrs():
    receptions_query = RawMaterialReception.query.options(
        selectinload(RawMaterialReception.clients),
        selectinload(RawMaterialReception.growers),
        selectinload(RawMaterialReception.lots),
    ).order_by(
        RawMaterialReception.date.desc(),
        RawMaterialReception.time.desc(),
        RawMaterialReception.id.desc(),
    )
    receptions, pagination, pagination_args = _paginate_query(receptions_query)
    return render_template(
        'list_rmrs.html',
        receptions=receptions,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/create_lot/<int:reception_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def create_lot(reception_id):
    form = CreateLotForm()
    reception = RawMaterialReception.query.get_or_404(reception_id)
    labels_url = None

    if not reception.is_open:
        flash('Esta recepción ya está cerrada y no acepta más lotes.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'GET':
        form.grower_name.data = ', '.join(grower.name for grower in reception.growers)
        form.client_name.data = ', '.join(client.name for client in reception.clients)
        form.waybill.data = reception.waybill

    if form.validate_on_submit():
        try:
            lot = LotService.create_lot(
                reception=reception,
                variety_id=form.variety_id.data,
                rawmaterialpackaging_id=form.rawmaterialpackaging_id.data,
                packagings_quantity=form.packagings_quantity.data,
                lot_number=form.lot_number.data,
                close_reception=bool(form.is_last_lot.data),
            )
        except LotValidationError as exc:
            flash(str(exc), 'warning')
            return render_template('create_lot.html', form=form, reception_id=reception_id, labels_url=labels_url)

        flash(f'Lote {form.lot_number.data} creado exitosamente.', 'success')
        labels_url = url_for('lot_labels_pdf', lot_id=lot.id)

        if form.is_last_lot.data:
            flash('Recepción cerrada. Último lote registrado.', 'success')
            return redirect(url_for('list_lots', labels_url=labels_url))

    return render_template('create_lot.html', form=form, reception_id=reception_id, labels_url=labels_url)

@app.route('/list_lots')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def list_lots():
    alert_key = request.args.get('alert')
    now_local = _server_now_local()
    status_filter = request.args.get('status', '').strip().lower()
    client_filter = request.args.get('client', '').strip()
    grower_filter = request.args.get('grower', '').strip()
    date_from = _parse_date_arg(request.args.get('date_from'))
    date_to = _parse_date_arg(request.args.get('date_to'))
    sort = request.args.get('sort', 'lot_number_asc')

    lots_query = Lot.query.options(
        joinedload(Lot.variety),
        joinedload(Lot.raw_material_packaging),
        joinedload(Lot.raw_material_reception).selectinload(RawMaterialReception.clients),
        joinedload(Lot.raw_material_reception).selectinload(RawMaterialReception.growers),
    )
    lots_query = _apply_lot_alert_filter(lots_query, alert_key, now_local)

    status_map = {
        "disponible": "1",
        "asignada": "2",
        "en_fumigacion": "3",
        "finalizada": "4",
    }
    if status_filter in status_map:
        lots_query = lots_query.filter(Lot.fumigation_status == status_map[status_filter])

    if client_filter:
        lots_query = lots_query.filter(
            Lot.raw_material_reception.has(
                RawMaterialReception.clients.any(Client.name.ilike(f"%{client_filter}%"))
            )
        )
    if grower_filter:
        lots_query = lots_query.filter(
            Lot.raw_material_reception.has(
                RawMaterialReception.growers.any(Grower.name.ilike(f"%{grower_filter}%"))
            )
        )
    if date_from:
        lots_query = lots_query.filter(
            Lot.raw_material_reception.has(RawMaterialReception.date >= date_from)
        )
    if date_to:
        lots_query = lots_query.filter(
            Lot.raw_material_reception.has(RawMaterialReception.date <= date_to)
        )

    if sort == 'lot_number_desc':
        lots_query = lots_query.order_by(Lot.lot_number.desc(), Lot.id.desc())
    elif sort == 'created_desc':
        lots_query = lots_query.order_by(Lot.created_at.desc(), Lot.id.desc())
    elif sort == 'created_asc':
        lots_query = lots_query.order_by(Lot.created_at.asc(), Lot.id.asc())
    else:
        sort = 'lot_number_asc'
        lots_query = lots_query.order_by(Lot.lot_number.asc(), Lot.id.asc())

    lots, pagination, pagination_args = _paginate_query(lots_query)

    active_alert = None
    if alert_key in DASHBOARD_ALERTS:
        active_alert = {
            "key": alert_key,
            "label": DASHBOARD_ALERTS[alert_key]["label"],
        }
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()

    labels_url = request.args.get('labels_url')
    return render_template(
        'list_lots.html',
        lots=lots,
        labels_url=labels_url,
        active_alert=active_alert,
        pagination=pagination,
        pagination_args=pagination_args,
        csrf_form=csrf_form,
        current_query_string=request.query_string.decode("utf-8"),
        filters={
            "status": status_filter if status_filter in status_map else "",
            "client": client_filter,
            "grower": grower_filter,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "sort": sort,
        },
    )

@app.route('/register_full_truck_weight/<int:lot_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def register_full_truck_weight(lot_id):
    lot = Lot.query.options(joinedload(Lot.raw_material_packaging)).get_or_404(lot_id)
    form = FullTruckWeightForm()

    if form.validate_on_submit():
        try:
            computation = LotService.register_full_truck_weight(
                lot=lot,
                loaded_truck_weight=form.loaded_truck_weight.data,
                empty_truck_weight=form.empty_truck_weight.data,
            )
        except LotValidationError as exc:
            flash(str(exc), 'error')
            return render_template('register_full_truck_weight.html', form=form, lot=lot)

        invalidate_cached_pdf("lot_labels", lot.id)
        flash(
            f'Peso de camión registrado. Peso neto calculado: {computation.net_weight:.2f} kg.',
            'success',
        )
        return redirect(url_for('list_lots'))

    return render_template('register_full_truck_weight.html', form=form, lot=lot)


@app.route('/lots/<int:lot_id>/inline_weight', methods=['POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def update_lot_weight_inline(lot_id):
    lot = Lot.query.options(joinedload(Lot.raw_material_packaging)).get_or_404(lot_id)
    loaded_truck_weight = request.form.get('loaded_truck_weight', type=float)
    empty_truck_weight = request.form.get('empty_truck_weight', type=float)

    try:
        computation = LotService.register_full_truck_weight(
            lot=lot,
            loaded_truck_weight=loaded_truck_weight,
            empty_truck_weight=empty_truck_weight,
        )
    except LotValidationError as exc:
        flash(str(exc), 'error')
    else:
        invalidate_cached_pdf("lot_labels", lot.id)
        flash(
            f'Lote {lot.lot_number:03d} actualizado. Peso neto: {computation.net_weight:.2f} kg.',
            'success',
        )

    next_url = request.form.get('next')
    if next_url and is_safe_redirect_url(next_url):
        return redirect(next_url)
    return redirect(url_for('list_lots'))

@app.route('/generate_qr')
@login_required
def generate_qr():
    # Receive the reception_id from the query parameters
    reception_id = request.args.get('reception_id', 'default')

    # Dynamically generate the URL for lot creation within an existing reception
    # _external=True generates an absolute URL, including the domain
    url = url_for('create_lot', reception_id=reception_id, _external=True)
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4) # type: ignore
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/lots/<int:lot_id>/labels.pdf')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def lot_labels_pdf(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers
    lot_number = f"{lot.lot_number:03d}"
    cache_key_updated_at = lot.updated_at or lot.created_at

    cached_pdf = get_cached_pdf("lot_labels", lot.id, cache_key_updated_at)
    if cached_pdf:
        return send_file(
            cached_pdf,
            mimetype='application/pdf',
            download_name=f'lot_labels_{lot_number}.pdf',
            as_attachment=True,
        )

    # QR data for the lot (can be adjusted later)
    qr_payload = f"LOT-{lot.lot_number:03d}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)  # type: ignore
    qr.add_data(qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    qr_data_uri = f"data:image/png;base64,{base64.b64encode(img_io.read()).decode('ascii')}"

    labels = list(range(lot.packagings_quantity))
    html = render_template(
        'lot_labels_pdf.html',
        lot=lot,
        reception=reception,
        clients=clients,
        growers=growers,
        qr_data_uri=qr_data_uri,
        labels=labels,
    )
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    cached_pdf = save_pdf_to_cache("lot_labels", lot.id, cache_key_updated_at, pdf)
    return send_file(
        cached_pdf,
        mimetype='application/pdf',
        download_name=f'lot_labels_{lot_number}.pdf',
        as_attachment=True,
    )

@app.route('/create_lot_qc', methods=['GET', 'POST'])
@login_required
@area_role_required('Calidad', ['Contribuidor'])
def create_lot_qc():
    form = LotQCForm()

    if form.validate_on_submit():
        payload = _qc_payload_from_form(form, include_lot=True)
        try:
            computed_metrics = QCService.validate_payload(payload)
        except QCValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_lot_qc.html', form=form)

        form.units.data = computed_metrics["units"]
        form.shelled_weight.data = computed_metrics["shelled_weight"]
        form.yieldpercentage.data = computed_metrics["yieldpercentage"]

        try:
            inshell_image_path = save_uploaded_file(form.inshell_image.data, "image")
            shelled_image_path = save_uploaded_file(form.shelled_image.data, "image")
        except UploadValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_lot_qc.html', form=form)

        try:
            lot_qc = QCService.create_lot_qc(
                payload=payload,
                inshell_image_path=inshell_image_path,
                shelled_image_path=shelled_image_path,
            )
        except QCValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_lot_qc.html', form=form)

        invalidate_cached_pdf("lot_qc_report", lot_qc.id)
        invalidate_cached_pdf("lot_labels", payload["lot_id"])
        flash('Registro de QC de lote creado exitosamente.', 'success')

        return redirect(url_for('index'))
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{err}', 'error')

    return render_template('create_lot_qc.html', form=form)

@app.route('/create_sample_qc', methods=['GET', 'POST'])
@login_required
@area_role_required('Calidad', ['Contribuidor'])
def create_sample_qc():
    form = SampleQCForm()
    if form.validate_on_submit():
        payload = _qc_payload_from_form(form)
        payload["grower"] = form.grower.data
        payload["brought_by"] = form.brought_by.data

        try:
            computed_metrics = QCService.validate_payload(payload)
        except QCValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_sample_qc.html', form=form)

        form.units.data = computed_metrics["units"]
        form.shelled_weight.data = computed_metrics["shelled_weight"]
        form.yieldpercentage.data = computed_metrics["yieldpercentage"]

        try:
            inshell_image_path = save_uploaded_file(form.inshell_image.data, "image")
            shelled_image_path = save_uploaded_file(form.shelled_image.data, "image")
        except UploadValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_sample_qc.html', form=form)

        try:
            sample_qc = QCService.create_sample_qc(
                payload=payload,
                inshell_image_path=inshell_image_path,
                shelled_image_path=shelled_image_path,
            )
        except QCValidationError as exc:
            flash(str(exc), 'error')
            return render_template('create_sample_qc.html', form=form)

        invalidate_cached_pdf("sample_qc_report", sample_qc.id)
        return redirect(url_for('index'))
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{err}', 'error')

    return render_template('create_sample_qc.html', form=form)

@app.route('/list_lot_qc_reports')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def list_lot_qc_reports():
    lot_qc_query = LotQC.query.order_by(LotQC.date.desc(), LotQC.time.desc(), LotQC.id.desc())
    lot_qc_reports, pagination, pagination_args = _paginate_query(lot_qc_query)
    return render_template(
        'list_lot_qc_reports.html',
        lot_qc_records=lot_qc_reports,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/list_sample_qc_reports')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def list_sample_qc_reports():
    sample_qc_query = SampleQC.query.order_by(SampleQC.date.desc(), SampleQC.time.desc(), SampleQC.id.desc())
    sample_qc_reports, pagination, pagination_args = _paginate_query(sample_qc_query)
    return render_template(
        'list_sample_qc_reports.html',
        sample_qc_records=sample_qc_reports,
        pagination=pagination,
        pagination_args=pagination_args,
    )

@app.route('/view_lot_qc_report/<int:report_id>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report(report_id):
    report = LotQC.query.get_or_404(report_id)
    lot = report.lot
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers

    return render_template('view_lot_qc_report.html', report=report, reception=reception, clients=clients, growers=growers)


@app.route('/view_lot_qc_report/<int:report_id>/image/<string:image_kind>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report_image(report_id, image_kind):
    report = LotQC.query.get_or_404(report_id)
    if image_kind == "inshell":
        return _send_private_upload(report.inshell_image_path)
    if image_kind == "shelled":
        return _send_private_upload(report.shelled_image_path)
    abort(404)


@app.route('/view_lot_qc_report/<int:report_id>/pdf')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report_pdf(report_id):
    report = LotQC.query.get_or_404(report_id)
    lot = report.lot
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers
    cache_key_updated_at = report.updated_at or report.created_at
    lot_number = f"{report.lot_id:03d}"

    cached_pdf = get_cached_pdf("lot_qc_report", report.id, cache_key_updated_at)
    if cached_pdf:
        return send_file(
            cached_pdf,
            mimetype='application/pdf',
            download_name=f'lot_qc_report_{lot_number}.pdf',
            as_attachment=True,
        )

    inshell_image_url = _upload_path_to_file_uri(report.inshell_image_path)
    shelled_image_url = _upload_path_to_file_uri(report.shelled_image_path)

    html = render_template(
        'view_lot_qc_report_pdf.html',
        report=report,
        reception=reception,
        clients=clients,
        growers=growers,
        inshell_image_url=inshell_image_url,
        shelled_image_url=shelled_image_url,
    )
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    cached_pdf = save_pdf_to_cache("lot_qc_report", report.id, cache_key_updated_at, pdf)
    return send_file(
        cached_pdf,
        mimetype='application/pdf',
        download_name=f'lot_qc_report_{lot_number}.pdf',
        as_attachment=True,
    )

@app.route('/view_sample_qc_report/<int:report_id>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report(report_id):
    report = SampleQC.query.get_or_404(report_id)

    return render_template('view_sample_qc_report.html', report=report)


@app.route('/view_sample_qc_report/<int:report_id>/image/<string:image_kind>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report_image(report_id, image_kind):
    report = SampleQC.query.get_or_404(report_id)
    if image_kind == "inshell":
        return _send_private_upload(report.inshell_image_path)
    if image_kind == "shelled":
        return _send_private_upload(report.shelled_image_path)
    abort(404)


@app.route('/view_sample_qc_report/<int:report_id>/pdf')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report_pdf(report_id):
    report = SampleQC.query.get_or_404(report_id)
    cache_key_updated_at = report.updated_at or report.created_at

    cached_pdf = get_cached_pdf("sample_qc_report", report.id, cache_key_updated_at)
    if cached_pdf:
        return send_file(
            cached_pdf,
            mimetype='application/pdf',
            download_name=f'sample_qc_report_{report_id}.pdf',
            as_attachment=True,
        )

    inshell_image_url = _upload_path_to_file_uri(report.inshell_image_path)
    shelled_image_url = _upload_path_to_file_uri(report.shelled_image_path)

    html = render_template(
        'view_sample_qc_report_pdf.html',
        report=report,
        inshell_image_url=inshell_image_url,
        shelled_image_url=shelled_image_url,
    )
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    cached_pdf = save_pdf_to_cache("sample_qc_report", report.id, cache_key_updated_at, pdf)
    return send_file(
        cached_pdf,
        mimetype='application/pdf',
        download_name=f'sample_qc_report_{report_id}.pdf',
        as_attachment=True,
    )

@app.route('/create_fumigation', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def create_fumigation():
    form = FumigationForm()

    if form.validate_on_submit():
        try:
            FumigationService.assign_fumigation(
                work_order=form.work_order.data,
                lot_ids=form.lot_selection.data,
            )
        except ValueError as exc:
            flash(str(exc), 'error')
            return render_template('create_fumigation.html', form=form)
        flash('Fumigación creada con éxito.', 'success')
        return redirect(url_for('list_fumigations'))

    return render_template('create_fumigation.html', form=form)

@app.route('/list_fumigations')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def list_fumigations():
    status_filter = request.args.get('status', '').strip().lower()
    work_order_filter = request.args.get('work_order', '').strip()
    date_from = _parse_date_arg(request.args.get('date_from'))
    date_to = _parse_date_arg(request.args.get('date_to'))
    sort = request.args.get('sort', 'created_desc')

    fumigations_query = Fumigation.query.options(
        selectinload(Fumigation.lots),
    )

    if work_order_filter:
        fumigations_query = fumigations_query.filter(Fumigation.work_order.ilike(f"%{work_order_filter}%"))

    if date_from:
        fumigations_query = fumigations_query.filter(Fumigation.real_start_date.isnot(None), Fumigation.real_start_date >= date_from)
    if date_to:
        fumigations_query = fumigations_query.filter(Fumigation.real_start_date.isnot(None), Fumigation.real_start_date <= date_to)

    if status_filter == 'finalizada':
        fumigations_query = fumigations_query.filter(Fumigation.real_end_date.isnot(None))
    elif status_filter == 'en_fumigacion':
        fumigations_query = fumigations_query.filter(
            Fumigation.real_end_date.is_(None),
            Fumigation.lots.any(Lot.fumigation_status == '3'),
        )
    elif status_filter == 'asignada':
        fumigations_query = fumigations_query.filter(
            Fumigation.real_end_date.is_(None),
            ~Fumigation.lots.any(Lot.fumigation_status == '3'),
            Fumigation.lots.any(Lot.fumigation_status == '2'),
        )
    else:
        status_filter = ''

    if sort == 'work_order_asc':
        fumigations_query = fumigations_query.order_by(Fumigation.work_order.asc(), Fumigation.id.asc())
    elif sort == 'start_date_asc':
        fumigations_query = fumigations_query.order_by(Fumigation.real_start_date.asc(), Fumigation.id.asc())
    elif sort == 'start_date_desc':
        fumigations_query = fumigations_query.order_by(Fumigation.real_start_date.desc(), Fumigation.id.desc())
    else:
        sort = 'created_desc'
        fumigations_query = fumigations_query.order_by(Fumigation.created_at.desc(), Fumigation.id.desc())

    fumigations, pagination, pagination_args = _paginate_query(fumigations_query)
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template(
        'list_fumigations.html',
        fumigations=fumigations,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
        filters={
            "status": status_filter,
            "work_order": work_order_filter,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "sort": sort,
        },
    )


@app.route('/fumigation/<int:fumigation_id>/document/<string:document_kind>')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def view_fumigation_document(fumigation_id, document_kind):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    if document_kind == "sign":
        return _send_private_upload(fumigation.fumigation_sign_path)
    if document_kind == "work_order":
        return _send_private_upload(fumigation.work_order_path)
    if document_kind == "certificate":
        return _send_private_upload(fumigation.certificate_path)
    abort(404)


@app.route('/start_fumigation/<int:fumigation_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def start_fumigation(fumigation_id):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    form = StartFumigationForm()
    if fumigation.real_end_date is not None:
        flash("Esta fumigación ya fue completada.", 'error')
        return redirect(url_for('list_fumigations'))
    for lot in fumigation.lots:
        if not can_transition(lot, FumigationService.STARTED):
            flash(
                f'Lote {lot.lot_number} no puede pasar de estado {lot.fumigation_status} a {FumigationService.STARTED}.',
                'error',
            )
            return redirect(url_for('list_fumigations'))

    if form.validate_on_submit():
        try:
            fumigation_sign_path = save_uploaded_file(form.fumigation_sign.data, "image") if form.fumigation_sign.data else None
            work_order_path = save_uploaded_file(form.work_order_doc.data, "pdf") if form.work_order_doc.data else None
        except UploadValidationError as exc:
            flash(str(exc), 'error')
            return render_template('start_fumigation.html', form=form, fumigation=fumigation)
        try:
            FumigationService.start_fumigation(
                fumigation=fumigation,
                real_start_date=form.real_start_date.data,
                real_start_time=form.real_start_time.data,
                fumigation_sign_path=fumigation_sign_path,
                work_order_path=work_order_path,
            )
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('list_fumigations'))
        flash('Fumigación iniciada con éxito.', 'success')
        return redirect(url_for('list_fumigations'))

    return render_template('start_fumigation.html', form=form, fumigation=fumigation)

@app.route('/complete_fumigation/<int:fumigation_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def complete_fumigation(fumigation_id):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    form = CompleteFumigationForm()
    if fumigation.real_end_date is not None:
        flash("Esta fumigación ya fue completada.", 'error')
        return redirect(url_for('list_fumigations'))
    for lot in fumigation.lots:
        if not can_transition(lot, FumigationService.COMPLETED):
            flash(
                f'Lote {lot.lot_number} no puede pasar de estado {lot.fumigation_status} a {FumigationService.COMPLETED}.',
                'error',
            )
            return redirect(url_for('list_fumigations'))

    if form.validate_on_submit():
        try:
            certificate_path = save_uploaded_file(form.certificate_doc.data, "pdf") if form.certificate_doc.data else None
        except UploadValidationError as exc:
            flash(str(exc), 'error')
            return render_template('complete_fumigation.html', form=form, fumigation=fumigation)
        try:
            FumigationService.complete_fumigation(
                fumigation=fumigation,
                real_end_date=form.real_end_date.data,
                real_end_time=form.real_end_time.data,
                certificate_path=certificate_path,
            )
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('list_fumigations'))
        flash('Fumigación completada con éxito.', 'success')
        return redirect(url_for('list_fumigations'))

    return render_template('complete_fumigation.html', form=form, fumigation=fumigation)


@app.errorhandler(403)
def handle_403(_error):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def handle_404(_error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def handle_500(_error):
    db.session.rollback()
    return render_template('errors/500.html'), 500
