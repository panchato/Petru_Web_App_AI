from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from sqlalchemy.orm import selectinload

from app.blueprints.fumigation import bp
from app.forms import CompleteFumigationForm, FumigationForm, StartFumigationForm
from app.http_helpers import _paginate_query, _parse_date_arg, _send_private_upload
from app.models import Fumigation, Lot
from app.permissions import area_role_required
from app.services import FumigationService, can_transition
from app.upload_security import UploadValidationError, save_uploaded_file


@bp.route('/create_fumigation', methods=['GET', 'POST'])
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
        return redirect(url_for('fumigation.list_fumigations'))

    return render_template('create_fumigation.html', form=form)


@bp.route('/list_fumigations')
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


@bp.route('/fumigation/<int:fumigation_id>/document/<string:document_kind>')
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


@bp.route('/start_fumigation/<int:fumigation_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def start_fumigation(fumigation_id):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    form = StartFumigationForm()
    if fumigation.real_end_date is not None:
        flash("Esta fumigación ya fue completada.", 'error')
        return redirect(url_for('fumigation.list_fumigations'))
    for lot in fumigation.lots:
        if not can_transition(lot, FumigationService.STARTED):
            flash(
                f'Lote {lot.lot_number} no puede pasar de estado {lot.fumigation_status} a {FumigationService.STARTED}.',
                'error',
            )
            return redirect(url_for('fumigation.list_fumigations'))

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
            return redirect(url_for('fumigation.list_fumigations'))
        flash('Fumigación iniciada con éxito.', 'success')
        return redirect(url_for('fumigation.list_fumigations'))

    return render_template('start_fumigation.html', form=form, fumigation=fumigation)


@bp.route('/complete_fumigation/<int:fumigation_id>', methods=['GET', 'POST'])
@login_required
@area_role_required('Materia Prima', ['Contribuidor'])
def complete_fumigation(fumigation_id):
    fumigation = Fumigation.query.get_or_404(fumigation_id)
    form = CompleteFumigationForm()
    if fumigation.real_end_date is not None:
        flash("Esta fumigación ya fue completada.", 'error')
        return redirect(url_for('fumigation.list_fumigations'))
    for lot in fumigation.lots:
        if not can_transition(lot, FumigationService.COMPLETED):
            flash(
                f'Lote {lot.lot_number} no puede pasar de estado {lot.fumigation_status} a {FumigationService.COMPLETED}.',
                'error',
            )
            return redirect(url_for('fumigation.list_fumigations'))

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
            return redirect(url_for('fumigation.list_fumigations'))
        flash('Fumigación completada con éxito.', 'success')
        return redirect(url_for('fumigation.list_fumigations'))

    return render_template('complete_fumigation.html', form=form, fumigation=fumigation)
