import base64
from io import BytesIO

import qrcode
from flask import flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from weasyprint import HTML

from app import db
from app.blueprints.dashboard.services import (
    DASHBOARD_ALERTS,
    _alert_cutoff_utc_naive,
    _server_now_local,
)
from app.blueprints.materiaprima import bp
from app.forms import CreateLotForm, CreateRawMaterialReceptionForm, FullTruckWeightForm
from app.http_helpers import _paginate_query, _parse_date_arg, is_safe_redirect_url
from app.models import Client, Grower, Lot, LotQC, RawMaterialReception
from app.permissions import area_role_required
from app.services import (
    LotService,
    LotValidationError,
    get_cached_pdf,
    invalidate_cached_pdf,
    save_pdf_to_cache,
)


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


@bp.route('/create_raw_material_reception', methods=['GET', 'POST'])
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
            observations=form.observations.data,
        )  # type: ignore

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


@bp.route('/list_rmrs')
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


@bp.route('/create_lot/<int:reception_id>', methods=['GET', 'POST'])
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
        labels_url = url_for('materiaprima.lot_labels_pdf', lot_id=lot.id)

        if form.is_last_lot.data:
            flash('Recepción cerrada. Último lote registrado.', 'success')
            return redirect(url_for('materiaprima.list_lots', labels_url=labels_url))

    return render_template('create_lot.html', form=form, reception_id=reception_id, labels_url=labels_url)


@bp.route('/list_lots')
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


@bp.route('/register_full_truck_weight/<int:lot_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('materiaprima.list_lots'))

    return render_template('register_full_truck_weight.html', form=form, lot=lot)


@bp.route('/lots/<int:lot_id>/inline_weight', methods=['POST'])
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
    return redirect(url_for('materiaprima.list_lots'))


@bp.route('/generate_qr')
@login_required
def generate_qr():
    reception_id = request.args.get('reception_id', 'default')
    url = url_for('materiaprima.create_lot', reception_id=reception_id, _external=True)

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)  # type: ignore
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')


@bp.route('/lots/<int:lot_id>/labels.pdf')
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
