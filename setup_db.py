import logging
import os
from flask_migrate import init, migrate as migrate_function, upgrade
from sqlalchemy import text
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
        except BaseException as e:
            logging.warning(f"Migration skipped or failed: {e}")

        try:
            upgrade(directory='migrations')
            logging.info("Database upgraded successfully.")
        except BaseException as e:
            logging.warning(f"Database upgrade skipped or failed: {e}")


def create_tables():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        logging.info("Database tables created.")


def ensure_operational_indexes():
    """Ensure indexes required by operational dashboard queries exist."""
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_lots_created_at ON lots (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_lots_fumigation_status ON lots (fumigation_status)",
        # lot_number is already covered by UNIQUE constraint; avoid duplicate index.
        "CREATE INDEX IF NOT EXISTS ix_rawmaterialreceptions_date ON rawmaterialreceptions (date)",
        "CREATE INDEX IF NOT EXISTS ix_lots_rawmaterialreception_id ON lots (rawmaterialreception_id)",
        "CREATE INDEX IF NOT EXISTS ix_lots_variety_id ON lots (variety_id)",
        "CREATE INDEX IF NOT EXISTS ix_lots_rawmaterialpackaging_id ON lots (rawmaterialpackaging_id)",
        "CREATE INDEX IF NOT EXISTS ix_fulltruckweights_lot_id ON fulltruckweights (lot_id)",
        "CREATE INDEX IF NOT EXISTS ix_lotsqc_lot_id ON lotsqc (lot_id)",
        "CREATE INDEX IF NOT EXISTS ix_lotsqc_date ON lotsqc (date)",
        "CREATE INDEX IF NOT EXISTS ix_samplesqc_date ON samplesqc (date)",
        "CREATE INDEX IF NOT EXISTS ix_area_user_user_id ON area_user (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_role_user_user_id ON role_user (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_client_user_user_id ON client_user (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_rawmaterialreception_client_client_id ON rawmaterialreception_client (client_id)",
        "CREATE INDEX IF NOT EXISTS ix_rawmaterialreception_grower_grower_id ON rawmaterialreception_grower (grower_id)",
        "CREATE INDEX IF NOT EXISTS ix_fumigation_lot_lot_id ON fumigation_lot (lot_id)",
    ]
    with app.app_context():
        with db.engine.connect() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
        logging.info("Operational dashboard indexes ensured.")


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
        # Clients
        clients = [
            {"name": "EXPORTADORA BRIX LTDA", "tax_id": "9100000001", "address": "Ruta 5 Sur Km 1", "comuna": "Rengo"},
            {"name": "EXPORTADORA ALNUEZ SPA", "tax_id": "9100000002", "address": "Camino Interior 220", "comuna": "San Fernando"},
            {"name": "ATACAMA DRIED FRUIT SPA", "tax_id": "9100000003", "address": "Av. Las Industrias 455", "comuna": "Copiapo"},
        ]

        # Growers
        growers = [
            {"name": "SOC AGRICOLA EL CARMEN DE PUCALAN LIMITADA", "tax_id": "9200000001", "csg_code": "CSG0000001"},
            {"name": "AGRICOLA LOS ALPES SPA", "tax_id": "9200000002", "csg_code": "CSG0000002"},
            {"name": "AGRICOLA HUERTOS DEL VALLE S A", "tax_id": "9200000003", "csg_code": "CSG0000003"},
            {"name": "AGRICOLA LA ARBOLEDA LIMITADA", "tax_id": "9200000004", "csg_code": "CSG0000004"},
            {"name": "AGRICOLA LOMA LINDA LIMITADA", "tax_id": "9200000005", "csg_code": "CSG0000005"},
            {"name": "SUC GABRIEL MESQUIDA RIERA", "tax_id": "9200000006", "csg_code": "CSG0000006"},
            {"name": "AURELIO SAN NICOLAS ROSIQUE", "tax_id": "9200000007", "csg_code": "CSG0000007"},
            {"name": "AGRICOLA EL CASTILLO LIMITADA", "tax_id": "9200000008", "csg_code": "CSG0000008"},
            {"name": "AGRICOLA FORESTAL Y GANADERA SANTA INES DE CUNCUMEN LIMITADA", "tax_id": "9200000009", "csg_code": "CSG0000009"},
            {"name": "AGRICOLA S.P. LIMITADA", "tax_id": "9200000010", "csg_code": "CSG0000010"},
        ]

        # Varieties
        varieties = [
            {"name": "CHANDLER"},
            {"name": "SERR"},
            {"name": "HOWARD"},
        ]

        # Packagings (kept as-is)
        packagings = [
            {"name": "Bins Plásticos IFCO", "tare": 42.0},
            {"name": "Maxisaco Polipropileno", "tare": 2.5},
        ]

        for client_data in clients:
            client = Client.query.filter_by(name=client_data["name"]).first()
            if client is None:
                client = Client.query.filter_by(tax_id=client_data["tax_id"]).first()
            if client is None:
                db.session.add(Client(**client_data))
            else:
                client.tax_id = client_data["tax_id"]
                client.address = client_data["address"]
                client.comuna = client_data["comuna"]
                client.is_active = True

        for grower_data in growers:
            grower = Grower.query.filter_by(name=grower_data["name"]).first()
            if grower is None:
                grower = Grower.query.filter_by(tax_id=grower_data["tax_id"]).first()
            if grower is None:
                db.session.add(Grower(**grower_data))
            else:
                grower.tax_id = grower_data["tax_id"]
                grower.csg_code = grower_data["csg_code"]
                grower.is_active = True

        for variety_data in varieties:
            variety = Variety.query.filter_by(name=variety_data["name"]).first()
            if variety is None:
                db.session.add(Variety(**variety_data))

        for packaging_data in packagings:
            packaging = RawMaterialPackaging.query.filter_by(name=packaging_data["name"]).first()
            if packaging is None:
                db.session.add(RawMaterialPackaging(**packaging_data))
            else:
                packaging.tare = packaging_data["tare"]

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
    ensure_operational_indexes()
    create_admin_user()
    populate_test_data()
    logging.info("=== Database Setup Complete ===")


if __name__ == "__main__":
    setup()
