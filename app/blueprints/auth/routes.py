from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import bcrypt
from app.forms import LoginForm
from app.http_helpers import is_safe_redirect_url
from app.models import User
from app.blueprints.auth import bp


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('Usuario ya se encuentra conectado.')
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user is None:
            flash('Usuario incorrecto.')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Cuenta no activa. Por favor, contacte al administrador.')
            return redirect(url_for('auth.login'))

        if bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            # Prevent open redirects by allowing only same-host relative URLs
            if next_page and is_safe_redirect_url(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Contraseña incorrecta.')
            return redirect(url_for('auth.login'))

    return render_template('login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Usuario se ha desconectado exitosamente.')
    return redirect(url_for('auth.login'))
