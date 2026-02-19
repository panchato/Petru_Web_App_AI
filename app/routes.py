import qrcode
import os
import uuid
import base64
from pathlib import Path
from flask import render_template, redirect, url_for, flash, send_file, request, session, jsonify
from urllib.parse import urlparse, urljoin
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from app.forms import LoginForm, AddUserForm, EditUserForm, AddRoleForm, AddAreaForm, AssignRoleForm, AssignAreaForm, AddClientForm, AddGrowerForm, AddVarietyForm, AddRawMaterialPackagingForm, CreateRawMaterialReceptionForm, CreateLotForm, FullTruckWeightForm, LotQCForm, SampleQCForm, FumigationForm, StartFumigationForm, CompleteFumigationForm
from app.models import User, Role, Area, Client, Grower, Variety, RawMaterialPackaging, RawMaterialReception, Lot, FullTruckWeight, LotQC, SampleQC, Fumigation
from app import app, db, bcrypt
from io import BytesIO
from datetime import datetime, timezone, date, timedelta, time
from werkzeug.utils import secure_filename
from weasyprint import HTML
from sqlalchemy import func


def is_safe_redirect_url(target):
    base_url = urlparse(request.host_url)
    target_url = urlparse(urljoin(request.host_url, target))
    return base_url.scheme == target_url.scheme and base_url.netloc == target_url.netloc


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_role('Admin'):
            flash('Acceso restringido.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


def area_role_required(area_name, roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Acceso restringido.', 'error')
                return redirect(url_for('login'))
            if current_user.has_role('Admin'):
                return f(*args, **kwargs)
            if not current_user.from_area(area_name) or not any(current_user.has_role(r) for r in roles):
                flash('Acceso restringido.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def dashboard_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acceso restringido.', 'error')
            return redirect(url_for('login'))
        if current_user.has_role('Admin') or current_user.has_role('Dashboard'):
            return f(*args, **kwargs)
        flash('Acceso restringido.', 'error')
        return redirect(url_for('index'))
    return wrapper

def _fmt_number(value):
    return f"{int(round(value)):,.0f}".replace(",", ".")

def _dashboard_date_range(days=7):
    end_day = date.today()
    start_day = end_day - timedelta(days=days - 1)
    labels = [(start_day + timedelta(days=i)) for i in range(days)]
    return start_day, end_day, labels

def _as_float(value):
    return float(value) if value is not None else 0.0

def _build_dashboard_summary():
    today = date.today()
    seven_days_ago = today - timedelta(days=6)
    qc_min_yield = 45.0
    qc_max_yield = 60.0

    recepciones_hoy = db.session.query(func.count(RawMaterialReception.id)).filter(
        RawMaterialReception.date == today
    ).scalar() or 0

    lots_today_query = db.session.query(func.count(Lot.id)).filter(func.date(Lot.created_at) == str(today))
    lotes_hoy = lots_today_query.scalar() or 0

    kg_netos_hoy = db.session.query(func.sum(Lot.net_weight)).filter(
        func.date(Lot.created_at) == str(today),
        Lot.net_weight.isnot(None)
    ).scalar() or 0.0

    lot_qcs_hoy = db.session.query(func.count(LotQC.id)).filter(LotQC.date == today).scalar() or 0
    sample_qcs_hoy = db.session.query(func.count(SampleQC.id)).filter(SampleQC.date == today).scalar() or 0
    qcs_hoy = lot_qcs_hoy + sample_qcs_hoy

    fumigaciones = Fumigation.query.all()
    fumigaciones_activas = sum(
        1 for fum in fumigaciones
        if fum.real_end_date is None and any(lot.fumigation_status in ('2', '3') for lot in fum.lots)
    )

    fumigaciones_completadas_hoy = db.session.query(func.count(Fumigation.id)).filter(
        Fumigation.real_end_date == today
    ).scalar() or 0

    recepciones_abiertas = db.session.query(func.count(RawMaterialReception.id)).filter(
        RawMaterialReception.is_open.is_(True)
    ).scalar() or 0

    lotes_sin_qc = db.session.query(func.count(Lot.id)).filter(
        Lot.has_qc.is_(False)
    ).scalar() or 0

    status_rows = db.session.query(
        Lot.fumigation_status,
        func.count(Lot.id)
    ).group_by(Lot.fumigation_status).all()
    status_map = {'1': 0, '2': 0, '3': 0, '4': 0}
    for status, count in status_rows:
        if status in status_map:
            status_map[status] = int(count)

    avg_lot_yield = db.session.query(func.avg(LotQC.yieldpercentage)).filter(
        LotQC.date >= seven_days_ago
    ).scalar() or 0.0
    avg_sample_yield = db.session.query(func.avg(SampleQC.yieldpercentage)).filter(
        SampleQC.date >= seven_days_ago
    ).scalar() or 0.0

    lot_qc_7d = LotQC.query.filter(LotQC.date >= seven_days_ago).all()
    sample_qc_7d = SampleQC.query.filter(SampleQC.date >= seven_days_ago).all()
    all_qc_records = lot_qc_7d + sample_qc_7d
    total_qc_7d = len(all_qc_records)
    out_of_range_qc = sum(
        1 for qc in all_qc_records
        if qc.yieldpercentage < qc_min_yield or qc.yieldpercentage > qc_max_yield
    )
    qc_fuera_rango_pct = round((out_of_range_qc / total_qc_7d) * 100, 2) if total_qc_7d else 0.0

    defect_fields = [
        "broken_walnut",
        "split_walnut",
        "light_stain",
        "serious_stain",
        "adhered_hull",
        "shrivel",
        "empty",
        "insect_damage",
        "inactive_fungus",
        "active_fungus",
    ]
    defect_totals = {field: 0 for field in defect_fields}
    for qc in all_qc_records:
        for field in defect_fields:
            defect_totals[field] += int(getattr(qc, field) or 0)
    top_defectos = sorted(defect_totals.items(), key=lambda item: item[1], reverse=True)[:5]

    threshold_lot_qc = datetime.utcnow() - timedelta(hours=24)
    lotes_sin_qc_24h = db.session.query(func.count(Lot.id)).filter(
        Lot.has_qc.is_(False),
        Lot.created_at <= threshold_lot_qc
    ).scalar() or 0

    threshold_fum = datetime.utcnow() - timedelta(hours=48)
    fumigaciones_retrasadas = 0
    for fum in fumigaciones:
        if fum.real_end_date is not None or fum.real_start_date is None:
            continue
        start_dt = datetime.combine(fum.real_start_date, fum.real_start_time or time.min)
        if start_dt <= threshold_fum:
            fumigaciones_retrasadas += 1

    return {
        "kpis": {
            "recepciones_hoy": int(recepciones_hoy),
            "lotes_hoy": int(lotes_hoy),
            "kg_netos_hoy": round(_as_float(kg_netos_hoy), 2),
            "kg_netos_hoy_fmt": _fmt_number(_as_float(kg_netos_hoy)),
            "qcs_hoy": int(qcs_hoy),
            "fumigaciones_activas": int(fumigaciones_activas),
            "fumigaciones_completadas_hoy": int(fumigaciones_completadas_hoy),
            "recepciones_abiertas": int(recepciones_abiertas),
            "lotes_sin_qc": int(lotes_sin_qc),
            "avg_lot_yield_7d": round(_as_float(avg_lot_yield), 2),
            "avg_sample_yield_7d": round(_as_float(avg_sample_yield), 2),
            "qc_fuera_rango_pct_7d": qc_fuera_rango_pct,
        },
        "pipeline": {
            "status_1_pendiente": status_map['1'],
            "status_2_asignado": status_map['2'],
            "status_3_en_proceso": status_map['3'],
            "status_4_completado": status_map['4'],
        },
        "alerts": {
            "lotes_sin_qc_24h": int(lotes_sin_qc_24h),
            "fumigaciones_retrasadas_48h": int(fumigaciones_retrasadas),
        },
        "top_defectos_7d": [
            {"defecto": name, "total": int(total)} for name, total in top_defectos
        ],
        "meta": {
            "generated_at": datetime.utcnow().isoformat(),
            "qc_target_yield_min": qc_min_yield,
            "qc_target_yield_max": qc_max_yield,
        }
    }

def _build_dashboard_timeseries():
    start_day, _end_day, labels = _dashboard_date_range(7)
    label_keys = [d.isoformat() for d in labels]

    lot_rows = db.session.query(
        func.date(Lot.created_at),
        func.count(Lot.id)
    ).filter(
        Lot.created_at >= datetime.combine(start_day, time.min)
    ).group_by(func.date(Lot.created_at)).all()
    lotes_by_day = {day: int(count) for day, count in lot_rows if day}

    kg_rows = db.session.query(
        func.date(Lot.created_at),
        func.sum(Lot.net_weight)
    ).filter(
        Lot.created_at >= datetime.combine(start_day, time.min),
        Lot.net_weight.isnot(None)
    ).group_by(func.date(Lot.created_at)).all()
    kg_by_day = {day: round(_as_float(total), 2) for day, total in kg_rows if day}

    lot_qcs = LotQC.query.filter(LotQC.date >= start_day).all()
    sample_qcs = SampleQC.query.filter(SampleQC.date >= start_day).all()
    yield_acc = {key: {"sum": 0.0, "count": 0} for key in label_keys}
    for qc in lot_qcs:
        key = qc.date.isoformat()
        if key in yield_acc:
            yield_acc[key]["sum"] += _as_float(qc.yieldpercentage)
            yield_acc[key]["count"] += 1
    for qc in sample_qcs:
        key = qc.date.isoformat()
        if key in yield_acc:
            yield_acc[key]["sum"] += _as_float(qc.yieldpercentage)
            yield_acc[key]["count"] += 1

    return {
        "labels": [d.strftime("%d-%m") for d in labels],
        "series": {
            "lotes_por_dia": [lotes_by_day.get(key, 0) for key in label_keys],
            "kg_netos_por_dia": [kg_by_day.get(key, 0.0) for key in label_keys],
            "yield_promedio_por_dia": [
                round((yield_acc[key]["sum"] / yield_acc[key]["count"]), 2) if yield_acc[key]["count"] else 0.0
                for key in label_keys
            ],
        },
        "meta": {
            "start_date": label_keys[0],
            "end_date": label_keys[-1],
            "generated_at": datetime.utcnow().isoformat(),
        }
    }

def _dashboard_version():
    table_models = [
        User, Role, Area, Client, Grower, Variety, RawMaterialPackaging,
        RawMaterialReception, Lot, FullTruckWeight, LotQC, SampleQC, Fumigation
    ]
    latest_db_ts = None
    for model in table_models:
        candidate = db.session.query(func.max(model.updated_at)).scalar()
        if candidate and (latest_db_ts is None or candidate > latest_db_ts):
            latest_db_ts = candidate
    db_version = latest_db_ts.isoformat() if latest_db_ts else "no-data"
    commit_version = app.config.get("DASHBOARD_LAST_COMMIT_AT", "no-commit")
    return f"{db_version}|{commit_version}"

@app.route('/')
def index():
    dashboard = None
    if current_user.is_authenticated:
        dashboard = {
            'total_lots': Lot.query.count(),
            'pending_qc_lots': Lot.query.filter_by(has_qc=False).count(),
            'open_receptions': RawMaterialReception.query.filter_by(is_open=True).count(),
            'active_fumigations': Fumigation.query.filter_by(is_active=True).count(),
            'fumigation_stage_1': Lot.query.filter_by(fumigation_status='1').count(),
            'fumigation_stage_2': Lot.query.filter_by(fumigation_status='2').count(),
            'fumigation_stage_3': Lot.query.filter_by(fumigation_status='3').count(),
            'fumigation_stage_4': Lot.query.filter_by(fumigation_status='4').count(),
        }

    return render_template('index.html', dashboard=dashboard)

@app.route('/dashboard/tv')
@login_required
@dashboard_required
def dashboard_tv():
    return render_template('dashboard_tv.html')

@app.route('/api/dashboard/summary')
@login_required
@dashboard_required
def dashboard_summary_api():
    return jsonify(_build_dashboard_summary())

@app.route('/api/dashboard/timeseries')
@login_required
@dashboard_required
def dashboard_timeseries_api():
    return jsonify(_build_dashboard_timeseries())

@app.route('/api/dashboard/version')
@login_required
@dashboard_required
def dashboard_version_api():
    return jsonify({"version": _dashboard_version()})

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
    users = User.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_users.html', users=users, csrf_form=csrf_form)

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
        user = User.query.get(form.user_id.data)
        role = Role.query.get(form.role_id.data)
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
    roles = Role.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_roles.html', roles=roles, csrf_form=csrf_form)

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
        user = User.query.get(form.user_id.data)
        area = Area.query.get(form.area_id.data)
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
    areas = Area.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_areas.html', areas=areas, csrf_form=csrf_form)

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
    clients = Client.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_clients.html', clients=clients, csrf_form=csrf_form)

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
    growers = Grower.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_growers.html', growers=growers, csrf_form=csrf_form)

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
    varieties = Variety.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_varieties.html', varieties=varieties, csrf_form=csrf_form)

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

@app.route('/list_raw_material_packagins')
@login_required
@admin_required
def list_raw_material_packagings():
    rmps = RawMaterialPackaging.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_raw_material_packagings.html', rmps=rmps, csrf_form=csrf_form)

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

        selected_grower = Grower.query.get(form.grower_id.data)
        selected_client = Client.query.get(form.client_id.data)
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
    receptions = RawMaterialReception.query.all()
    return render_template('list_rmrs.html', receptions=receptions)

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
        if Lot.query.filter_by(lot_number=form.lot_number.data).first():
            flash(f'El Lote {form.lot_number.data:03} ya existe. Por favor, use un Lote distinto.', 'warning')
        else:
            lot = Lot(
                rawmaterialreception_id=reception_id,
                variety_id=form.variety_id.data,
                rawmaterialpackaging_id=form.rawmaterialpackaging_id.data,
                packagings_quantity=form.packagings_quantity.data,
                lot_number=form.lot_number.data
            ) # type: ignore
            db.session.add(lot)
            db.session.commit()
            flash(f'Lote {form.lot_number.data} creado exitosamente.', 'success')
            labels_url = url_for('lot_labels_pdf', lot_id=lot.id)

            if form.is_last_lot.data:
                reception.is_open = False
                db.session.commit()
                flash('Recepción cerrada. Último lote registrado.', 'success')
                return redirect(url_for('list_lots', labels_url=labels_url))

    return render_template('create_lot.html', form=form, reception_id=reception_id, labels_url=labels_url)

@app.route('/list_lots')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def list_lots():
    lots = Lot.query.order_by(Lot.lot_number.asc()).all()
    labels_url = request.args.get('labels_url')
    return render_template('list_lots.html', lots=lots, labels_url=labels_url)

@app.route('/register_full_truck_weight/<int:lot_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def register_full_truck_weight(lot_id):
    lot = Lot.query.get_or_404(lot_id)
    form = FullTruckWeightForm()

    if form.validate_on_submit():
        full_truck_weight = FullTruckWeight(
            loaded_truck_weight=form.loaded_truck_weight.data,
            empty_truck_weight=form.empty_truck_weight.data,
            lot_id=lot_id
        ) # type: ignore
        db.session.add(full_truck_weight)
        
        packaging = RawMaterialPackaging.query.get(lot.rawmaterialpackaging_id)
        if packaging is None:
            flash('No se encontró el tipo de envase para este lote.', 'error')
            db.session.rollback()
            return redirect(url_for('register_full_truck_weight', lot_id=lot_id))

        packaging_tare = packaging.tare

        lot.net_weight = (
            full_truck_weight.loaded_truck_weight - 
            full_truck_weight.empty_truck_weight - 
            (packaging_tare * lot.packagings_quantity)
        )
        
        db.session.commit()

        flash('Peso de camión completo registrado exitosamente.', 'success')
        return redirect(url_for('list_lots'))

    return render_template('register_full_truck_weight.html', form=form, lot=lot)

@app.route('/generate_qr')
@login_required
def generate_qr():
    # Receive the reception_id from the query parameters
    reception_id = request.args.get('reception_id', 'default')

    # Dynamically generate the URL for 'lot_net_details' route
    # _external=True generates an absolute URL, including the domain
    url = url_for('lot_net_details', reception_id=reception_id, _external=True)
    
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
    lot_number = f"{lot.lot_number:03d}"
    return send_file(
        BytesIO(pdf),
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
        if not form.inshell_weight.data or form.inshell_weight.data == 0:
            flash('El peso con cáscara debe ser mayor que 0 para calcular el porcentaje de pulpa.', 'error')
            return render_template('create_lot_qc.html', form=form)

        units = (
            form.lessthan30.data +
            form.between3032.data +
            form.between3234.data +
            form.between3436.data +
            form.morethan36.data
        )
        if units != 100:
            flash('Las unidades analizadas deben sumar 100.', 'error')
            return render_template('create_lot_qc.html', form=form)
        shelled_weight = (
            form.extra_light.data +
            form.light.data +
            form.light_amber.data +
            form.amber.data
        )
        yieldpercentage = round((shelled_weight / form.inshell_weight.data) * 100, 2)
        new_lot_qc = LotQC(
            lot_id=form.lot_id.data,
            analyst=form.analyst.data,
            date=form.date.data,
            time=form.time.data,
            units=units,
            inshell_weight=form.inshell_weight.data,
            shelled_weight=shelled_weight,
            yieldpercentage=yieldpercentage,
            lessthan30=form.lessthan30.data,
            between3032=form.between3032.data,
            between3234=form.between3234.data,
            between3436=form.between3436.data,
            morethan36=form.morethan36.data,
            broken_walnut=form.broken_walnut.data,
            split_walnut=form.split_walnut.data,
            light_stain=form.light_stain.data,
            serious_stain=form.serious_stain.data,
            adhered_hull=form.adhered_hull.data,
            shrivel=form.shrivel.data,
            empty=form.empty.data,
            insect_damage=form.insect_damage.data,
            inactive_fungus=form.inactive_fungus.data,
            active_fungus=form.active_fungus.data,
            extra_light=form.extra_light.data,
            light=form.light.data,
            light_amber=form.light_amber.data,
            amber=form.amber.data,
            yellow=form.yellow.data
        ) # type: ignore

        def save_image(uploaded_file):
            if uploaded_file:
                original_name = secure_filename(uploaded_file.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('images', unique_name).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_PATH_IMAGE'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    flash('Imagen guardada correctamente.', 'info')
                    return relative_path
                except Exception as e:
                    app.logger.error("Error al guardar imagen: %s", e)
                    flash("No se pudo guardar el archivo.", 'error')
                    return None
            else:
                flash('No se cargó ningún archivo.', 'warning')
                return None

        # Image upload handling
        inshell_image_path = save_image(form.inshell_image.data)
        shelled_image_path = save_image(form.shelled_image.data)
        
        if inshell_image_path and shelled_image_path:
            new_lot_qc.inshell_image_path = inshell_image_path
            new_lot_qc.shelled_image_path = shelled_image_path
            db.session.add(new_lot_qc)
            
            # Update Lot status
            lot = Lot.query.get(form.lot_id.data)
            if lot:
                lot.has_qc = True
                
            db.session.commit()
            flash('Registro de QC de lote creado exitosamente.', 'success')
        else:
            flash('No se pudieron guardar las imágenes. Por favor, intente nuevamente.', 'error')

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
        if not form.inshell_weight.data or form.inshell_weight.data == 0:
            flash('El peso con cáscara debe ser mayor que 0 para calcular el porcentaje de pulpa.', 'error')
            return render_template('create_sample_qc.html', form=form)

        shelled_weight = (
            form.extra_light.data +
            form.light.data +
            form.light_amber.data +
            form.amber.data
        )
        units = (
            form.lessthan30.data +
            form.between3032.data +
            form.between3234.data +
            form.between3436.data +
            form.morethan36.data
        )
        if units != 100:
            flash('Las unidades analizadas deben sumar 100.', 'error')
            return render_template('create_sample_qc.html', form=form)
        yieldpercentage = round((shelled_weight / form.inshell_weight.data) * 100, 2)
        new_sample_qc = SampleQC(
            grower=form.grower.data,
            brought_by=form.brought_by.data,
            analyst=form.analyst.data,
            date=form.date.data,
            time=form.time.data,
            units=units,
            inshell_weight=form.inshell_weight.data,
            shelled_weight=shelled_weight,
            yieldpercentage=yieldpercentage,
            lessthan30=form.lessthan30.data,
            between3032=form.between3032.data,
            between3234=form.between3234.data,
            between3436=form.between3436.data,
            morethan36=form.morethan36.data,
            broken_walnut=form.broken_walnut.data,
            split_walnut=form.split_walnut.data,
            light_stain=form.light_stain.data,
            serious_stain=form.serious_stain.data,
            adhered_hull=form.adhered_hull.data,
            shrivel=form.shrivel.data,
            empty=form.empty.data,
            insect_damage=form.insect_damage.data,
            inactive_fungus=form.inactive_fungus.data,
            active_fungus=form.active_fungus.data,
            extra_light=form.extra_light.data,
            light=form.light.data,
            light_amber=form.light_amber.data,
            amber=form.amber.data,
            yellow=form.yellow.data
        ) # type: ignore

        def save_image(uploaded_file, sample_type, grower_name):
            if uploaded_file:
                original_name = secure_filename(uploaded_file.filename)
                grower_name = form.grower.data
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                sanitized_grower_name = secure_filename(grower_name).replace(' ', '_')
                unique_name = f"{sanitized_grower_name}_{sample_type}_{timestamp}"
                relative_path = os.path.join('images', unique_name).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_PATH_IMAGE'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    return relative_path
                except Exception as e:
                    app.logger.error(f"Failed to save image: {e}")
                    return None
            else:
                return None


        # Image upload handling
        inshell_image_path = save_image(form.inshell_image.data, "inshell", form.grower.data)
        shelled_image_path = save_image(form.shelled_image.data, "shelled", form.grower.data)

        
        if inshell_image_path and shelled_image_path:
            new_sample_qc.inshell_image_path = inshell_image_path
            new_sample_qc.shelled_image_path = shelled_image_path
            db.session.add(new_sample_qc)
            db.session.commit()
        else:
            flash('No se pudieron guardar las imágenes. Por favor, intente nuevamente.', 'error')

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
    lot_qc_reports = LotQC.query.all()
    return render_template('list_lot_qc_reports.html', lot_qc_records=lot_qc_reports)

@app.route('/list_sample_qc_reports')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def list_sample_qc_reports():
    sample_qc_reports = SampleQC.query.all()
    return render_template('list_sample_qc_reports.html', sample_qc_records=sample_qc_reports)

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


@app.route('/view_lot_qc_report/<int:report_id>/pdf')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report_pdf(report_id):
    report = LotQC.query.get_or_404(report_id)
    lot = report.lot
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers

    def to_file_uri(rel_path):
        if not rel_path:
            return None
        rel_path = rel_path.replace('\\', '/')
        full_path = Path(app.static_folder) / rel_path
        if not full_path.exists():
            return None
        return full_path.resolve().as_uri()

    inshell_image_url = to_file_uri(report.inshell_image_path)
    shelled_image_url = to_file_uri(report.shelled_image_path)

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
    lot_number = f"{report.lot_id:03d}"
    return send_file(
        BytesIO(pdf),
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


@app.route('/view_sample_qc_report/<int:report_id>/pdf')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report_pdf(report_id):
    report = SampleQC.query.get_or_404(report_id)

    def to_file_uri(rel_path):
        if not rel_path:
            return None
        rel_path = rel_path.replace('\\', '/')
        full_path = Path(app.static_folder) / rel_path
        if not full_path.exists():
            return None
        return full_path.resolve().as_uri()

    inshell_image_url = to_file_uri(report.inshell_image_path)
    shelled_image_url = to_file_uri(report.shelled_image_path)

    html = render_template(
        'view_sample_qc_report_pdf.html',
        report=report,
        inshell_image_url=inshell_image_url,
        shelled_image_url=shelled_image_url,
    )
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    return send_file(
        BytesIO(pdf),
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

        existing_work_order = Fumigation.query.filter_by(work_order=form.work_order.data).first()
        if existing_work_order:
            flash('La Orden de Fumigación ya existe. Por favor, use otra', 'warning')
            return redirect(url_for('create_fumigation'))

        if not form.lot_selection.data:
            flash('Por favor, seleccione al menos un Lote para continuar.', 'warning')
            return redirect(url_for('create_fumigation'))

        selected_lots = Lot.query.filter(Lot.id.in_(form.lot_selection.data))
        if any(lot.fumigation_status != '1' for lot in selected_lots):
            flash('Uno o más lotes seleccionados ya han sido fumigados', 'warning')
            return redirect(url_for('create_fumigation'))
        
        fumigation = Fumigation(
            work_order=form.work_order.data,
        )# type: ignore

        for lot in selected_lots:
            lot.fumigation_status = '2'
            fumigation.lots.append(lot)

        db.session.add(fumigation)
        db.session.commit()
        flash('Fumigación creada con éxito.', 'success')
        return redirect(url_for('list_fumigations'))

    return render_template('create_fumigation.html', form=form)

@app.route('/list_fumigations')
@login_required
@area_role_required('Materia Prima', ['Contribuidor', 'Lector'])
def list_fumigations():
    fumigations = Fumigation.query.all()
    from flask_wtf import FlaskForm
    csrf_form = FlaskForm()
    return render_template('list_fumigations.html', fumigations=fumigations, csrf_form=csrf_form)

@app.route('/start_fumigation/<int:fumigation_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def start_fumigation(fumigation_id):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    form = StartFumigationForm()

    if fumigation.real_end_date is not None:
        flash('Esta fumigación ya fue completada.', 'warning')
        return redirect(url_for('list_fumigations'))

    if any(lot.fumigation_status != '2' for lot in fumigation.lots):
        flash('Uno o más lotes no se encuentran en estado "Asignado a Fumigación".', 'warning')
        return redirect(url_for('list_fumigations'))

    if form.validate_on_submit():
        def save_image(uploaded_file):
            if uploaded_file:
                original_name = secure_filename(uploaded_file.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('images', unique_name).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_PATH_IMAGE'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    return relative_path
                except Exception as e:
                    app.logger.error("Error al guardar imagen de fumigacion: %s", e)
                    flash("No se pudo guardar el archivo.", 'error')
                    return None
            else:
                flash('No se cargó ningún archivo.', 'warning')
                return None

        if form.fumigation_sign.data:
            fumigation_sign_path = save_image(form.fumigation_sign.data)
        else:
            fumigation_sign_path = None

        if form.work_order_doc.data:
            def save_pdf(uploaded_file):
                original_name = secure_filename(uploaded_file.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('pdf', unique_name).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_PATH_PDF'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    return relative_path
                except Exception as e:
                    app.logger.error("Error al guardar PDF de orden de trabajo: %s", e)
                    flash("No se pudo guardar el archivo.", 'error')
                    return None
            work_order_path = save_pdf(form.work_order_doc.data)
        else:
            work_order_path = None

        fumigation.real_start_date = form.real_start_date.data
        fumigation.real_start_time = form.real_start_time.data
        if fumigation_sign_path:
            fumigation.fumigation_sign_path = fumigation_sign_path
        if work_order_path:
            fumigation.work_order_path = work_order_path
        for lot in fumigation.lots:
            lot.fumigation_status = '3'
        db.session.commit()
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
        flash('Esta fumigación ya fue completada.', 'warning')
        return redirect(url_for('list_fumigations'))

    if any(lot.fumigation_status != '3' for lot in fumigation.lots):
        flash('Uno o más lotes no se encuentran en estado "En Fumigación".', 'warning')
        return redirect(url_for('list_fumigations'))

    if form.validate_on_submit():
        def save_pdf(uploaded_file):
            if uploaded_file:
                original_name = secure_filename(uploaded_file.filename)
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('pdf', unique_name).replace('\\', '/')
                full_path = os.path.join(app.config['UPLOAD_PATH_PDF'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    flash('PDF guardado correctamente.', 'info')
                    return relative_path
                except Exception as e:
                    app.logger.error("Error al guardar PDF de certificado: %s", e)
                    flash("No se pudo guardar el archivo.", 'error')
                    return None
            else:
                flash('No se cargó ningún archivo.', 'warning')
                return None

        if form.certificate_doc.data:
            certificate_path = save_pdf(form.certificate_doc.data)
        else:
            certificate_path = None

        fumigation.real_end_date = form.real_end_date.data
        fumigation.real_end_time = form.real_end_time.data
        if certificate_path:
            fumigation.certificate_path = certificate_path
        for lot in fumigation.lots:
            lot.fumigation_status = '4'
        db.session.commit()
        flash('Fumigación completada con éxito.', 'success')
        return redirect(url_for('list_fumigations'))

    return render_template('complete_fumigation.html', form=form, fumigation=fumigation)
