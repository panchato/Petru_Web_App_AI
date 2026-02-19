from app import db
from app.models import Fumigation, Lot


class FumigationTransitionError(ValueError):
    pass


class FumigationService:
    AVAILABLE = "1"
    ASSIGNED = "2"
    STARTED = "3"
    COMPLETED = "4"

    _ALLOWED_TRANSITIONS = {
        AVAILABLE: {ASSIGNED},
        ASSIGNED: {STARTED},
        STARTED: {COMPLETED},
        COMPLETED: set(),
    }

    @classmethod
    def _validate_transition(cls, lot, next_status):
        current_status = lot.fumigation_status
        allowed_next = cls._ALLOWED_TRANSITIONS.get(current_status, set())
        if next_status not in allowed_next:
            raise FumigationTransitionError(
                f"Transición inválida para lote {lot.lot_number}: {current_status} -> {next_status}."
            )

    @staticmethod
    def _load_lots_for_update(lot_ids):
        lots = (
            Lot.query.filter(Lot.id.in_(lot_ids))
            .order_by(Lot.id.asc())
            .with_for_update()
            .all()
        )
        return lots

    @staticmethod
    def _transaction_context():
        session = db.session()
        return session.begin_nested() if session.in_transaction() else session.begin()

    @classmethod
    def assign_fumigation(cls, work_order, lot_ids):
        if not lot_ids:
            raise FumigationTransitionError("Por favor, seleccione al menos un Lote para continuar.")

        if Fumigation.query.filter_by(work_order=work_order).first():
            raise FumigationTransitionError("La Orden de Fumigación ya existe. Por favor, use otra.")

        with cls._transaction_context():
            lots = cls._load_lots_for_update(lot_ids)
            if len(lots) != len(set(lot_ids)):
                raise FumigationTransitionError("Uno o más lotes seleccionados no existen.")

            fumigation = Fumigation(work_order=work_order)
            db.session.add(fumigation)

            for lot in lots:
                cls._validate_transition(lot, cls.ASSIGNED)
                lot.fumigation_status = cls.ASSIGNED
                fumigation.lots.append(lot)

            db.session.flush()
        return fumigation

    @classmethod
    def start_fumigation(
        cls,
        fumigation,
        real_start_date,
        real_start_time,
        fumigation_sign_path=None,
        work_order_path=None,
    ):
        if fumigation.real_end_date is not None:
            raise FumigationTransitionError("Esta fumigación ya fue completada.")

        with cls._transaction_context():
            for lot in fumigation.lots:
                cls._validate_transition(lot, cls.STARTED)
                lot.fumigation_status = cls.STARTED

            fumigation.real_start_date = real_start_date
            fumigation.real_start_time = real_start_time
            if fumigation_sign_path:
                fumigation.fumigation_sign_path = fumigation_sign_path
            if work_order_path:
                fumigation.work_order_path = work_order_path
            db.session.add(fumigation)

        return fumigation

    @classmethod
    def complete_fumigation(cls, fumigation, real_end_date, real_end_time, certificate_path=None):
        if fumigation.real_end_date is not None:
            raise FumigationTransitionError("Esta fumigación ya fue completada.")

        with cls._transaction_context():
            for lot in fumigation.lots:
                cls._validate_transition(lot, cls.COMPLETED)
                lot.fumigation_status = cls.COMPLETED

            fumigation.real_end_date = real_end_date
            fumigation.real_end_time = real_end_time
            if certificate_path:
                fumigation.certificate_path = certificate_path
            db.session.add(fumigation)

        return fumigation
