import logging
import os
from flask_migrate import init, migrate as migrate_function, upgrade
from app import app, db, bcrypt
from app.models import User, Role, Area, Client, Grower, Variety, RawMaterialPackaging

logging.basicConfig(level=logging.INFO)

# Default admin credentials
ADMIN_EMAIL = "panchato@gmail.com"
ADMIN_PASSWORD = "dx12bb40"
ADMIN_NAME = "Francisco"
ADMIN_LAST_NAME = "Castro"
ADMIN_PHONE = "943980350"


def run_migrations():
    """Initialize and run database migrations."""
    with app.app_context():
        if not os.path.exists('migrations'):
            init(directory='migrations')
            logging.info("Migrations directory initialized.")

        try:
            migrate_function(directory='migrations', message='Auto migration')
            logging.info("Migration generated.")
        except Exception as e:
            logging.warning(f"Migration skipped or failed: {e}")

        upgrade(directory='migrations')
        logging.info("Database upgraded successfully.")


def create_tables():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        logging.info("Database tables created.")


def create_admin_user():
    """Create the default admin user and role."""
    with app.app_context():
        # Ensure base roles exist
        roles = [
            ("Admin", "Administrador del Sistema"),
            ("Contribuidor", "Puede crear y editar registros"),
            ("Lector", "Puede visualizar registros"),
            ("Dashboard", "Puede visualizar dashboard operacional"),
        ]
        for name, description in roles:
            if Role.query.filter_by(name=name).first() is None:
                db.session.add(Role(name=name, description=description))  # type: ignore
        db.session.commit()

        # Ensure base areas exist
        areas = [
            ("Materia Prima", "Gestión de recepciones, lotes y fumigaciones"),
            ("Calidad", "Control de calidad de lotes y muestras"),
        ]
        for name, description in areas:
            if Area.query.filter_by(name=name).first() is None:
                db.session.add(Area(name=name, description=description))  # type: ignore
        db.session.commit()

        admin_user = User.query.filter_by(email=ADMIN_EMAIL).first()

        if admin_user is None:
            password_hash = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf8')
            admin_user = User(
                name=ADMIN_NAME,
                last_name=ADMIN_LAST_NAME,
                email=ADMIN_EMAIL,
                phone_number=ADMIN_PHONE,
                is_active=True,
                is_external=False,
                password_hash=password_hash
            )  # type: ignore
            db.session.add(admin_user)
            try:
                db.session.commit()
                logging.info(f"Admin user '{ADMIN_EMAIL}' created.")
            except Exception as e:
                logging.error(f"Error creating admin user: {e}")
                db.session.rollback()
                return
        else:
            logging.info(f"Admin user '{ADMIN_EMAIL}' already exists.")

        admin_role = Role.query.filter_by(name='Admin').first()
        if admin_role is None:
            logging.error("Admin role not found; cannot assign to admin user.")
            return

        # Assign role to admin user
        admin_user = User.query.filter_by(email=ADMIN_EMAIL).first()
        if admin_user and admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
            try:
                db.session.commit()
                logging.info("Admin role assigned to admin user.")
            except Exception as e:
                logging.error(f"Error assigning role: {e}")
                db.session.rollback()


def populate_test_data():
    """Populate database with test data."""
    with app.app_context():
        # Check if data already exists
        if Client.query.first():
            logging.info("Test data already exists. Skipping population.")
            return

        # Clients
        clients = [
            {"name": "Cliente A", "tax_id": "1234567890", "address": "123 Main St", "comuna": "Comuna1"},
            {"name": "Cliente B", "tax_id": "0987654321", "address": "456 Side St", "comuna": "Comuna2"}
        ]
        for client_data in clients:
            db.session.add(Client(**client_data))

        # Growers
        growers = [
            {"name": "Productor A", "tax_id": "1111111111", "csg_code": "CSG1001"},
            {"name": "Productor B", "tax_id": "2222222222", "csg_code": "CSG1002"}
        ]
        for grower_data in growers:
            db.session.add(Grower(**grower_data))

        # Varieties
        varieties = [
            {"name": "Variedad A"},
            {"name": "Variedad B"}
        ]
        for variety_data in varieties:
            db.session.add(Variety(**variety_data))

        # Packagings
        packagings = [
            {"name": "Bins Plásticos IFCO", "tare": 42.0},
            {"name": "Maxisaco Polipropileno", "tare": 2.5}
        ]
        for packaging_data in packagings:
            db.session.add(RawMaterialPackaging(**packaging_data))

        try:
            db.session.commit()
            logging.info("Test data populated successfully.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error populating test data: {e}")


def setup():
    """Run complete database setup."""
    logging.info("=== Starting Database Setup ===")
    run_migrations()
    create_tables()
    create_admin_user()
    populate_test_data()
    logging.info("=== Database Setup Complete ===")


if __name__ == "__main__":
    setup()
