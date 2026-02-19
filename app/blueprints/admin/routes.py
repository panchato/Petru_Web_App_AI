from flask import flash, redirect, render_template, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from sqlalchemy.orm import selectinload

from app import bcrypt, db
from app.blueprints.admin import bp
from app.forms import (
    AddAreaForm,
    AddClientForm,
    AddGrowerForm,
    AddRawMaterialPackagingForm,
    AddRoleForm,
    AddUserForm,
    AddVarietyForm,
    AssignAreaForm,
    AssignRoleForm,
    EditUserForm,
)
from app.http_helpers import _paginate_query
from app.models import Area, Client, Grower, RawMaterialPackaging, Role, User, Variety
from app.permissions import admin_required


@bp.route('/add_user', methods=['GET', 'POST'])
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


@bp.route('/list_users')
@login_required
@admin_required
def list_users():
    users_query = User.query.options(
        selectinload(User.roles),
        selectinload(User.areas),
    ).order_by(User.created_at.desc(), User.id.desc())
    users, pagination, pagination_args = _paginate_query(users_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_users.html',
        users=users,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    estado = 'activado' if user.is_active else 'desactivado'
    flash(f'Usuario {user.name} {estado}.', 'success')
    return redirect(url_for('list_users'))


@bp.route('/add_role', methods=['GET', 'POST'])
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


@bp.route('/assign_role', methods=['GET', 'POST'])
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


@bp.route('/list_roles')
@login_required
@admin_required
def list_roles():
    roles_query = Role.query.order_by(Role.name.asc(), Role.id.asc())
    roles, pagination, pagination_args = _paginate_query(roles_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_roles.html',
        roles=roles,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_role/<int:role_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_role/<int:role_id>', methods=['POST'])
@login_required
@admin_required
def toggle_role(role_id):
    role = Role.query.get_or_404(role_id)
    role.is_active = not role.is_active
    db.session.commit()
    estado = 'activado' if role.is_active else 'desactivado'
    flash(f'Rol {role.name} {estado}.', 'success')
    return redirect(url_for('list_roles'))


@bp.route('/add_area', methods=['GET', 'POST'])
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


@bp.route('/assign_area', methods=['GET', 'POST'])
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


@bp.route('/list_areas')
@login_required
@admin_required
def list_areas():
    areas_query = Area.query.order_by(Area.name.asc(), Area.id.asc())
    areas, pagination, pagination_args = _paginate_query(areas_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_areas.html',
        areas=areas,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_area/<int:area_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_area/<int:area_id>', methods=['POST'])
@login_required
@admin_required
def toggle_area(area_id):
    area = Area.query.get_or_404(area_id)
    area.is_active = not area.is_active
    db.session.commit()
    estado = 'activada' if area.is_active else 'desactivada'
    flash(f'Área {area.name} {estado}.', 'success')
    return redirect(url_for('list_areas'))


@bp.route('/add_client', methods=['GET', 'POST'])
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


@bp.route('/list_clients')
@login_required
@admin_required
def list_clients():
    clients_query = Client.query.order_by(Client.name.asc(), Client.id.asc())
    clients, pagination, pagination_args = _paginate_query(clients_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_clients.html',
        clients=clients,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_client/<int:client_id>', methods=['POST'])
@login_required
@admin_required
def toggle_client(client_id):
    client = Client.query.get_or_404(client_id)
    client.is_active = not client.is_active
    db.session.commit()
    estado = 'activado' if client.is_active else 'desactivado'
    flash(f'Cliente {client.name} {estado}.', 'success')
    return redirect(url_for('list_clients'))


@bp.route('/add_grower', methods=['GET', 'POST'])
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


@bp.route('/list_growers')
@login_required
@admin_required
def list_growers():
    growers_query = Grower.query.order_by(Grower.name.asc(), Grower.id.asc())
    growers, pagination, pagination_args = _paginate_query(growers_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_growers.html',
        growers=growers,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_grower/<int:grower_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_grower/<int:grower_id>', methods=['POST'])
@login_required
@admin_required
def toggle_grower(grower_id):
    grower = Grower.query.get_or_404(grower_id)
    grower.is_active = not grower.is_active
    db.session.commit()
    estado = 'activado' if grower.is_active else 'desactivado'
    flash(f'Productor {grower.name} {estado}.', 'success')
    return redirect(url_for('list_growers'))


@bp.route('/add_variety', methods=['GET', 'POST'])
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


@bp.route('/list_varieties')
@login_required
@admin_required
def list_varieties():
    varieties_query = Variety.query.order_by(Variety.name.asc(), Variety.id.asc())
    varieties, pagination, pagination_args = _paginate_query(varieties_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_varieties.html',
        varieties=varieties,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_variety/<int:variety_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_variety/<int:variety_id>', methods=['POST'])
@login_required
@admin_required
def toggle_variety(variety_id):
    variety = Variety.query.get_or_404(variety_id)
    variety.is_active = not variety.is_active
    db.session.commit()
    estado = 'activada' if variety.is_active else 'desactivada'
    flash(f'Variedad {variety.name} {estado}.', 'success')
    return redirect(url_for('list_varieties'))


@bp.route('/add_raw_material_packaging', methods=['GET', 'POST'])
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


@bp.route('/list_raw_material_packagings')
@login_required
@admin_required
def list_raw_material_packagings():
    rmps_query = RawMaterialPackaging.query.order_by(RawMaterialPackaging.name.asc(), RawMaterialPackaging.id.asc())
    rmps, pagination, pagination_args = _paginate_query(rmps_query)
    csrf_form = FlaskForm()
    return render_template(
        'list_raw_material_packagings.html',
        rmps=rmps,
        csrf_form=csrf_form,
        pagination=pagination,
        pagination_args=pagination_args,
    )


@bp.route('/edit_raw_material_packaging/<int:rmp_id>', methods=['GET', 'POST'])
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


@bp.route('/toggle_raw_material_packaging/<int:rmp_id>', methods=['POST'])
@login_required
@admin_required
def toggle_raw_material_packaging(rmp_id):
    rmp = RawMaterialPackaging.query.get_or_404(rmp_id)
    rmp.is_active = not rmp.is_active
    db.session.commit()
    estado = 'activado' if rmp.is_active else 'desactivado'
    flash(f'Envase {rmp.name} {estado}.', 'success')
    return redirect(url_for('list_raw_material_packagings'))
