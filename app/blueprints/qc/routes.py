from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from weasyprint import HTML

from app.blueprints.qc import bp
from app.forms import LotQCForm, SampleQCForm
from app.http_helpers import _paginate_query, _send_private_upload, _upload_path_to_file_uri
from app.models import LotQC, SampleQC
from app.permissions import area_role_required
from app.services import (
    QCService,
    QCValidationError,
    get_cached_pdf,
    invalidate_cached_pdf,
    save_pdf_to_cache,
)
from app.upload_security import UploadValidationError, save_uploaded_file


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


@bp.route('/create_lot_qc', methods=['GET', 'POST'])
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


@bp.route('/create_sample_qc', methods=['GET', 'POST'])
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


@bp.route('/list_lot_qc_reports')
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


@bp.route('/list_sample_qc_reports')
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


@bp.route('/view_lot_qc_report/<int:report_id>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report(report_id):
    report = LotQC.query.get_or_404(report_id)
    lot = report.lot
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers

    return render_template('view_lot_qc_report.html', report=report, reception=reception, clients=clients, growers=growers)


@bp.route('/view_lot_qc_report/<int:report_id>/image/<string:image_kind>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_lot_qc_report_image(report_id, image_kind):
    report = LotQC.query.get_or_404(report_id)
    if image_kind == "inshell":
        return _send_private_upload(report.inshell_image_path)
    if image_kind == "shelled":
        return _send_private_upload(report.shelled_image_path)
    abort(404)


@bp.route('/view_lot_qc_report/<int:report_id>/pdf')
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
        return send_file(cached_pdf, mimetype='application/pdf', download_name=f'lot_qc_report_{lot_number}.pdf', as_attachment=True)

    inshell_image_url = _upload_path_to_file_uri(report.inshell_image_path)
    shelled_image_url = _upload_path_to_file_uri(report.shelled_image_path)

    html = render_template('view_lot_qc_report_pdf.html', report=report, reception=reception, clients=clients, growers=growers, inshell_image_url=inshell_image_url, shelled_image_url=shelled_image_url)
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    cached_pdf = save_pdf_to_cache("lot_qc_report", report.id, cache_key_updated_at, pdf)
    return send_file(cached_pdf, mimetype='application/pdf', download_name=f'lot_qc_report_{lot_number}.pdf', as_attachment=True)


@bp.route('/view_sample_qc_report/<int:report_id>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report(report_id):
    report = SampleQC.query.get_or_404(report_id)
    return render_template('view_sample_qc_report.html', report=report)


@bp.route('/view_sample_qc_report/<int:report_id>/image/<string:image_kind>')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report_image(report_id, image_kind):
    report = SampleQC.query.get_or_404(report_id)
    if image_kind == "inshell":
        return _send_private_upload(report.inshell_image_path)
    if image_kind == "shelled":
        return _send_private_upload(report.shelled_image_path)
    abort(404)


@bp.route('/view_sample_qc_report/<int:report_id>/pdf')
@login_required
@area_role_required('Calidad', ['Contribuidor', 'Lector'])
def view_sample_qc_report_pdf(report_id):
    report = SampleQC.query.get_or_404(report_id)
    cache_key_updated_at = report.updated_at or report.created_at

    cached_pdf = get_cached_pdf("sample_qc_report", report.id, cache_key_updated_at)
    if cached_pdf:
        return send_file(cached_pdf, mimetype='application/pdf', download_name=f'sample_qc_report_{report_id}.pdf', as_attachment=True)

    inshell_image_url = _upload_path_to_file_uri(report.inshell_image_path)
    shelled_image_url = _upload_path_to_file_uri(report.shelled_image_path)
    html = render_template('view_sample_qc_report_pdf.html', report=report, inshell_image_url=inshell_image_url, shelled_image_url=shelled_image_url)
    pdf = HTML(string=html, base_url=request.url_root).write_pdf()
    cached_pdf = save_pdf_to_cache("sample_qc_report", report.id, cache_key_updated_at, pdf)
    return send_file(cached_pdf, mimetype='application/pdf', download_name=f'sample_qc_report_{report_id}.pdf', as_attachment=True)
