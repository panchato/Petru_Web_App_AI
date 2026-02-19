import qrcode
import os
import uuid
from flask import render_template, redirect, url_for, flash, send_file, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm, AddUserForm, AddRoleForm, AddAreaForm, AssignRoleForm, AssignAreaForm, AddClientForm, AddGrowerForm, AddVarietyForm, AddRawMaterialPackagingForm, CreateRawMaterialReceptionForm, CreateLotForm, FullTruckWeightForm, LotQCForm, SampleQCForm, FumigationForm
from app.models import User, Role, Area, Client, Grower, Variety, RawMaterialPackaging, RawMaterialReception, Lot, FullTruckWeight, LotQC, SampleQC, Fumigation
from app import app, db, bcrypt
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename

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
            return redirect(next_page or url_for('index'))
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
def list_users():
    users = User.query.all()  # Fetch all users from the database
    return render_template('list_users.html', users=users)

@app.route('/add_role', methods=['GET', 'POST'])
@login_required
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
def assign_role():
    form = AssignRoleForm()
    if form.validate_on_submit():
        user = User.query.get(form.user_id.data)
        role = Role.query.get(form.role_id.data)
        if role not in user.roles:
            user.roles.append(role)
            db.session.commit()
        else:
            flash('This user already has the assigned role.', 'warning')
        return redirect(url_for('assign_role'))
    return render_template('assign_role.html', form=form)

@app.route('/list_roles')
@login_required
def list_roles():
    roles = Role.query.all()
    return render_template('list_roles.html', roles=roles)

@app.route('/add_area', methods=['GET', 'POST'])
@login_required
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
def assign_area():
    form = AssignAreaForm()
    if form.validate_on_submit():
        user = User.query.get(form.user_id.data)
        area = Area.query.get(form.area_id.data)
        if area not in user.areas:
            user.areas.append(area)
            db.session.commit()
        else:
            flash('This user already has the assigned Area.', 'warning')
        return redirect(url_for('assign_area'))
    return render_template('assign_area.html', form=form)

@app.route('/list_areas')
@login_required
def list_areas():
    areas = Area.query.all()
    return render_template('list_areas.html', areas=areas)

@app.route('/add_client', methods=['GET', 'POST'])
@login_required
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
def list_clients():
    clients = Client.query.all()
    return render_template('list_clients.html', clients=clients)

@app.route('/add_grower', methods=['GET', 'POST'])
@login_required
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
def list_growers():
    growers = Grower.query.all()
    return render_template('list_growers.html', growers=growers)

@app.route('/add_variety', methods=['GET', 'POST'])
@login_required
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
def list_varieties():
    varieties = Variety.query.all()
    return render_template('list_varieties.html', varieties=varieties)

@app.route('/add_raw_material_packaging', methods=['GET', 'POST'])
@login_required
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
def list_raw_material_packagings():
    rmps = RawMaterialPackaging.query.all()
    return render_template('list_raw_material_packagings.html', rmps=rmps)

@app.route('/create_raw_material_reception', methods=['GET', 'POST'])
@login_required
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
def list_rmrs():
    receptions = RawMaterialReception.query.all()
    return render_template('list_rmrs.html', receptions=receptions)

@app.route('/create_lot/<int:reception_id>', methods=['GET', 'POST'])
@login_required
def create_lot(reception_id):
    form = CreateLotForm()
    reception = RawMaterialReception.query.get_or_404(reception_id)

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

            if form.is_last_lot.data:
                reception.is_open = False
                db.session.commit()
                flash('Recepción cerrada. Último lote registrado.', 'success')
                return redirect(url_for('list_lots'))

    return render_template('create_lot.html', form=form, reception_id=reception_id)

@app.route('/list_lots')
@login_required
def list_lots():
    lots = Lot.query.order_by(Lot.lot_number.asc()).all()
    return render_template('list_lots.html', lots=lots)

@app.route('/register_full_truck_weight/<int:lot_id>', methods=['GET', 'POST'])
@login_required
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
        
        packaging_tare = RawMaterialPackaging.query.get(lot.rawmaterialpackaging_id).tare # type: ignore

        lot.net_weight = (
            full_truck_weight.loaded_truck_weight - 
            full_truck_weight.empty_truck_weight - 
            (packaging_tare * lot.packagings_quantity)
        )
        
        db.session.commit()

        flash('Full truck weight registered successfully!', 'success')
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

@app.route('/create_lot_qc', methods=['GET', 'POST'])
@login_required
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
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('images', unique_name)
                full_path = os.path.join(app.config['UPLOAD_PATH_IMAGE'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    flash(f'Image saved: {unique_name}', 'info')
                    return relative_path
                except Exception as e:
                    flash(f"Error saving file: {str(e)}", 'error')
                    return None
            else:
                flash('No file uploaded', 'warning')
                return None

        # Image upload handling
        inshell_image_path = save_image(form.inshell_image.data)
        shelled_image_path = save_image(form.shelled_image.data)
        
        if inshell_image_path and shelled_image_path:
            new_lot_qc.inshell_image_path = inshell_image_path
            new_lot_qc.shelled_image_path = shelled_image_path
            db.session.add(new_lot_qc)
            db.session.commit()
            flash('Lot QC record created successfully!', 'success')
        else:
            flash('Failed to save images. Please try again.', 'error')

        return redirect(url_for('index'))
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{err}', 'error')

    return render_template('create_lot_qc.html', form=form)

@app.route('/create_sample_qc', methods=['GET', 'POST'])
@login_required
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
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                sanitized_grower_name = secure_filename(grower_name).replace(' ', '_')
                unique_name = f"{sanitized_grower_name}_{sample_type}_{timestamp}"
                relative_path = os.path.join('images', unique_name)
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
            flash('Failed to save images. Please try again.', 'error')

        return redirect(url_for('index'))
    else:
        for fieldName, errorMessages in form.errors.items():
            for err in errorMessages:
                flash(f'{err}', 'error')

    return render_template('create_sample_qc.html', form=form)

@app.route('/list_lot_qc_reports')
@login_required
def list_lot_qc_reports():
    lot_qc_reports = LotQC.query.all()
    return render_template('list_lot_qc_reports.html', lot_qc_records=lot_qc_reports)

@app.route('/list_sample_qc_reports')
@login_required
def list_sample_qc_reports():
    sample_qc_reports = SampleQC.query.all()
    return render_template('list_sample_qc_reports.html', sample_qc_records=sample_qc_reports)

@app.route('/view_lot_qc_report/<int:report_id>')
@login_required
def view_lot_qc_report(report_id):
    report = LotQC.query.get_or_404(report_id)
    lot = report.lot
    reception = lot.raw_material_reception
    clients = reception.clients
    growers = reception.growers

    return render_template('view_lot_qc_report.html', report=report, reception=reception, clients=clients, growers=growers)

@app.route('/view_sample_qc_report/<int:report_id>')
@login_required
def view_sample_qc_report(report_id):
    report = SampleQC.query.get_or_404(report_id)

    return render_template('view_sample_qc_report.html', report=report)

@app.route('/create_fumigation', methods=['GET', 'POST'])
@login_required
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
            start_date=form.start_date.data,
            start_time=form.start_time.data,
        )# type: ignore 

        for lot in selected_lots:
            lot.fumigation_status = '2'
            fumigation.lots.append(lot)

        def save_pdf(uploaded_file):
            if uploaded_file:
                original_name = secure_filename(uploaded_file.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                unique_name = f"{uuid.uuid4()}_{timestamp}_{original_name}"
                relative_path = os.path.join('pdf', unique_name)
                full_path = os.path.join(app.config['UPLOAD_PATH_PDF'], unique_name)
                try:
                    uploaded_file.save(full_path)
                    flash(f'PDF saved: {unique_name}', 'info')
                    return relative_path
                except Exception as e:
                    flash(f"Error saving file: {str(e)}", 'error')
                    return None
            else:
                flash('No file uploaded', 'warning')
                return None

        work_order_path = save_pdf(form.work_order_doc.data)
        
        if work_order_path:
            fumigation.work_order_path = work_order_path
            db.session.add(fumigation)
            db.session.commit()
            flash('Fumigación creada con éxito.', 'success')
            return redirect(url_for('index'))

    return render_template('create_fumigation.html', form=form)
