from flask_login import UserMixin
from datetime import datetime, date
from app import db, login_manager
from app.basemodel import BaseModel

class QCMixin(object):
    date = db.Column(db.Date, default=date.today, index=True)
    time = db.Column(db.Time, default=lambda: datetime.now().time())
    units = db.Column(db.Integer, nullable=False, default=0)
    inshell_weight = db.Column(db.Float, nullable=False)
    shelled_weight = db.Column(db.Float, nullable=False)
    yieldpercentage = db.Column(db.Float, nullable=False)
    lessthan30 = db.Column(db.Integer, nullable=False)
    between3032 = db.Column(db.Integer, nullable=False)
    between3234 = db.Column(db.Integer, nullable=False)
    between3436 = db.Column(db.Integer, nullable=False)
    morethan36 = db.Column(db.Integer, nullable=False)
    broken_walnut = db.Column(db.Integer, nullable=False)
    split_walnut = db.Column(db.Integer, nullable=False)
    light_stain = db.Column(db.Integer, nullable=False)
    serious_stain = db.Column(db.Integer, nullable=False)
    adhered_hull = db.Column(db.Integer, nullable=False)
    shrivel = db.Column(db.Integer, nullable=False)
    empty = db.Column(db.Integer, nullable=False)
    insect_damage = db.Column(db.Integer, nullable=False)
    inactive_fungus = db.Column(db.Integer, nullable=False)
    active_fungus = db.Column(db.Integer, nullable=False)
    extra_light = db.Column(db.Float, nullable=False)
    light = db.Column(db.Float, nullable=False)
    light_amber = db.Column(db.Float, nullable=False)
    amber = db.Column(db.Float, nullable=False)
    yellow = db.Column(db.Float, nullable=False)
    inshell_image_path = db.Column(db.String(255), nullable=True)
    shelled_image_path = db.Column(db.String(255), nullable=True)

# Association tables for many-to-many relationships
area_user = db.Table('area_user',
    db.Column('area_id', db.Integer, db.ForeignKey('areas.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, index=True)
)

role_user = db.Table('role_user',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, index=True)
)

client_user = db.Table('client_user',
    db.Column('client_id', db.Integer, db.ForeignKey('clients.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True, index=True)
)

class User(UserMixin, BaseModel):
    __tablename__ = 'users'
    name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(64), unique=True, nullable=False)
    phone_number = db.Column(db.String(9), nullable=False)
    password_hash = db.Column(db.String(128))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_external = db.Column(db.Boolean, default=False, nullable=False)

    roles = db.relationship('Role', secondary=role_user, backref=db.backref('users', lazy='dynamic'))
    areas = db.relationship('Area', secondary=area_user, backref=db.backref('users', lazy='dynamic'))
    clients = db.relationship('Client', secondary=client_user, backref=db.backref('users', lazy='dynamic'))

    def __str__(self):
        return self.email

    def has_role(self, role_name):
        return any(role.name == role_name for role in self.roles)
    
    def from_area(self, area_name):
        return any(area.name == area_name for area in self.areas)
    
    def from_client(self, client_name):
        return any(client.name == client_name for client in self.clients)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Role(BaseModel):
    __tablename__ = 'roles'
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

class Area(BaseModel):
    __tablename__ = 'areas'
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

class Variety(BaseModel):
    __tablename__ = 'varieties'
    name = db.Column(db.String(64), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    lots = db.relationship('Lot', backref='variety', lazy='dynamic')

    def __str__(self):
        return self.name

class RawMaterialPackaging(BaseModel):
    __tablename__ = 'rawmaterialpackagings'
    name = db.Column(db.String(64), nullable=False, unique=True)
    tare = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    lots = db.relationship('Lot', backref='raw_material_packaging', lazy='dynamic')

    def __str__(self):
        return self.name

rawmaterialreception_grower = db.Table('rawmaterialreception_grower',
    db.Column('reception_id', db.Integer, db.ForeignKey('rawmaterialreceptions.id'), primary_key=True),
    db.Column('grower_id', db.Integer, db.ForeignKey('growers.id'), primary_key=True, index=True)
)

class Grower(BaseModel):
    __tablename__ = 'growers'
    name = db.Column(db.String(128), nullable=False)
    tax_id = db.Column(db.String(10), nullable=False, unique=True)
    csg_code = db.Column(db.String(10), default="", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __str__(self):
        return self.name

rawmaterialreception_client = db.Table('rawmaterialreception_client',
    db.Column('reception_id', db.Integer, db.ForeignKey('rawmaterialreceptions.id'), primary_key=True),
    db.Column('client_id', db.Integer, db.ForeignKey('clients.id'), primary_key=True, index=True)
)

class Client(BaseModel):
    __tablename__ = 'clients'
    name = db.Column(db.String(128), nullable=False)
    tax_id = db.Column(db.String(10), nullable=False, unique=True)
    address = db.Column(db.String(128), nullable=False)
    comuna = db.Column(db.String(64), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __str__(self):
        return self.name

class RawMaterialReception(BaseModel):
    __tablename__ = 'rawmaterialreceptions'
    __table_args__ = (
        db.Index('ix_rawmaterialreceptions_date', 'date'),
    )
    waybill = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    time = db.Column(db.Time, default=lambda: datetime.utcnow().time(), nullable=False)
    truck_plate = db.Column(db.String(6), nullable=False)
    trucker_name = db.Column(db.String(64), nullable=True)
    observations = db.Column(db.String(255), nullable=True)
    is_open = db.Column(db.Boolean, default=True, nullable=False)

    # One-to-Many relationships
    lots = db.relationship('Lot', backref=db.backref('raw_material_reception', lazy=True))

    # Many-to-many relationships
    growers = db.relationship('Grower', secondary=rawmaterialreception_grower, 
                              backref=db.backref('raw_material_receptions', lazy='dynamic'))
    clients = db.relationship('Client', secondary=rawmaterialreception_client, 
                              backref=db.backref('raw_material_receptions', lazy='dynamic'))

class Lot(BaseModel):
    __tablename__ = 'lots'
    __table_args__ = (
        db.CheckConstraint("fumigation_status IN ('1', '2', '3', '4')", name='ck_lots_fumigation_status_valid'),
        db.Index('ix_lots_created_at', 'created_at'),
        db.Index('ix_lots_fumigation_status', 'fumigation_status'),
        db.Index('ix_lots_rawmaterialreception_id', 'rawmaterialreception_id'),
        db.Index('ix_lots_variety_id', 'variety_id'),
        db.Index('ix_lots_rawmaterialpackaging_id', 'rawmaterialpackaging_id'),
    )
    lot_number = db.Column(db.Integer, unique=True, nullable=False)
    packagings_quantity = db.Column(db.Integer, nullable=False)
    net_weight = db.Column(db.Float, nullable=True, default=0)
    has_qc = db.Column(db.Boolean, default=False, nullable=False)
    fumigation_status = db.Column(db.String(1), default='1', nullable=False)
    on_warehouse = db.Column(db.Boolean, default=True, nullable=False)

    #One-to-One relationship
    full_truck_weight = db.relationship('FullTruckWeight', backref='lot', uselist=False, lazy=True)
    lotqc = db.relationship('LotQC', backref='lot', uselist=False, lazy=True)

    # One-to-Many relationships
    rawmaterialreception_id = db.Column(db.Integer, db.ForeignKey('rawmaterialreceptions.id'), nullable=False)
    variety_id = db.Column(db.Integer, db.ForeignKey('varieties.id'), nullable=False)
    rawmaterialpackaging_id = db.Column(db.Integer, db.ForeignKey('rawmaterialpackagings.id'), nullable=False)

class FullTruckWeight(BaseModel):
    __tablename__ = 'fulltruckweights'
    __table_args__ = (
        db.CheckConstraint('loaded_truck_weight > 0', name='ck_fulltruckweights_loaded_positive'),
        db.CheckConstraint('empty_truck_weight >= 0', name='ck_fulltruckweights_empty_non_negative'),
    )
    loaded_truck_weight = db.Column(db.Float, nullable=False)
    empty_truck_weight = db.Column(db.Float, nullable=False, default=0)

    # One-to-One relationship
    lot_id = db.Column(db.Integer, db.ForeignKey('lots.id'), index=True)

class LotQC(BaseModel, QCMixin):
    __tablename__ = 'lotsqc'
    __table_args__ = (
        db.CheckConstraint(
            'units = lessthan30 + between3032 + between3234 + between3436 + morethan36',
            name='ck_lotsqc_units_breakdown',
        ),
        db.CheckConstraint('inshell_weight > 0', name='ck_lotsqc_inshell_positive'),
    )
    lot_id = db.Column(db.Integer, db.ForeignKey('lots.id'), index=True)
    analyst = db.Column(db.String(64), nullable=True)

class SampleQC(BaseModel, QCMixin):
    __tablename__ = 'samplesqc'
    __table_args__ = (
        db.CheckConstraint(
            'units = lessthan30 + between3032 + between3234 + between3436 + morethan36',
            name='ck_samplesqc_units_breakdown',
        ),
        db.CheckConstraint('inshell_weight > 0', name='ck_samplesqc_inshell_positive'),
    )
    grower = db.Column(db.String(64), unique=False, nullable=True)
    brought_by = db.Column(db.String(64), unique=False, nullable=True)
    analyst = db.Column(db.String(64), unique=False, nullable=True)

fumigation_lot = db.Table('fumigation_lot',
    db.Column('fumigation_id', db.Integer, db.ForeignKey('fumigations.id'), primary_key=True),
    db.Column('lot_id', db.Integer, db.ForeignKey('lots.id'), primary_key=True, index=True)
)

class Fumigation(BaseModel):
    __tablename__ = 'fumigations'
    work_order = db.Column(db.String(64), unique=True, nullable=False)
    real_start_date = db.Column(db.Date, nullable=True)
    real_start_time = db.Column(db.Time, nullable=True)
    real_end_date = db.Column(db.Date, nullable=True)
    real_end_time = db.Column(db.Time, nullable=True)
    work_order_path = db.Column(db.String(255), nullable=True)
    certificate_path = db.Column(db.String(255), nullable=True)
    fumigation_sign_path = db.Column(db.String(255), nullable=True)

    # Many-to-Many relationships
    lots = db.relationship('Lot', secondary=fumigation_lot, backref=db.backref('fumigations', lazy='dynamic'))
