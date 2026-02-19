from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app import db
from app.models import FullTruckWeight, Lot


class LotValidationError(ValueError):
    pass


@dataclass
class NetWeightComputation:
    net_weight: float
    packaging_tare: float


class LotService:
    @staticmethod
    def _transaction_context():
        session = db.session()
        return session.begin_nested() if session.in_transaction() else session.begin()

    @staticmethod
    def _round_kg(value):
        return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @staticmethod
    def compute_net_weight(lot, loaded_truck_weight, empty_truck_weight):
        if loaded_truck_weight is None or empty_truck_weight is None:
            raise LotValidationError("Debe ingresar los pesos cargado y vacío.")
        if loaded_truck_weight <= 0:
            raise LotValidationError("El peso del camión cargado debe ser mayor que 0.")
        if empty_truck_weight < 0:
            raise LotValidationError("El peso del camión vacío no puede ser negativo.")
        if loaded_truck_weight <= empty_truck_weight:
            raise LotValidationError("El peso cargado debe ser mayor al peso vacío.")

        packaging = lot.raw_material_packaging
        if packaging is None:
            raise LotValidationError("No se encontró el tipo de envase para este lote.")

        tare_total = packaging.tare * lot.packagings_quantity
        computed = loaded_truck_weight - empty_truck_weight - tare_total
        if computed <= 0:
            raise LotValidationError("El peso neto calculado debe ser mayor que 0.")

        return NetWeightComputation(
            net_weight=LotService._round_kg(computed),
            packaging_tare=packaging.tare,
        )

    @staticmethod
    def register_full_truck_weight(lot, loaded_truck_weight, empty_truck_weight):
        with LotService._transaction_context():
            computation = LotService.compute_net_weight(
                lot=lot,
                loaded_truck_weight=loaded_truck_weight,
                empty_truck_weight=empty_truck_weight,
            )

            full_truck_weight = FullTruckWeight.query.filter_by(lot_id=lot.id).first()
            if full_truck_weight is None:
                full_truck_weight = FullTruckWeight(lot_id=lot.id)
                db.session.add(full_truck_weight)

            full_truck_weight.loaded_truck_weight = loaded_truck_weight
            full_truck_weight.empty_truck_weight = empty_truck_weight

            # Compute-on-write: keep stored net weight in sync with source weights and tare.
            lot.net_weight = computation.net_weight
            db.session.add(lot)

        return computation

    @staticmethod
    def create_lot(
        reception,
        variety_id,
        rawmaterialpackaging_id,
        packagings_quantity,
        lot_number,
        close_reception=False,
    ):
        if Lot.query.filter_by(lot_number=lot_number).first():
            raise LotValidationError(f"El Lote {lot_number:03} ya existe. Por favor, use un Lote distinto.")

        with LotService._transaction_context():
            lot = Lot(
                rawmaterialreception_id=reception.id,
                variety_id=variety_id,
                rawmaterialpackaging_id=rawmaterialpackaging_id,
                packagings_quantity=packagings_quantity,
                lot_number=lot_number,
            )
            db.session.add(lot)
            db.session.flush()

            if close_reception:
                reception.is_open = False
                db.session.add(reception)

        return lot
