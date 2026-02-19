from app import db
from app.models import Fumigation, Lot


VALID_TRANSITIONS = {
    1: [2],
    2: [3],
    3: [4],
    4: [],
}


def _coerce_state(state_value, field_label):
    try:
        return int(state_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Estado de fumigación {field_label} inválido: {state_value!r}.") from exc


def transition_fumigation_status(lot, new_state):
    current_state = _coerce_state(lot.fumigation_status, "actual")
    target_state = _coerce_state(new_state, "nuevo")
    allowed_states = VALID_TRANSITIONS.get(current_state)
    if allowed_states is None:
        raise ValueError(f"Estado de fumigación actual no reconocido: {current_state}.")

    if target_state not in allowed_states:
        lot_ref = getattr(lot, "lot_number", getattr(lot, "id", "?"))
        allowed_text = ", ".join(str(state) for state in allowed_states) or "ninguno (estado terminal)"
        raise ValueError(
            f"Transición inválida para lote {lot_ref}: {current_state} -> {target_state}. "
            f"Estados permitidos: {allowed_text}."
        )

    lot.fumigation_status = str(target_state)
    return lot


def can_transition(lot, new_state):
    try:
        current_state = _coerce_state(lot.fumigation_status, "actual")
        target_state = _coerce_state(new_state, "nuevo")
    except ValueError:
        return False

    allowed_states = VALID_TRANSITIONS.get(current_state)
    if allowed_states is None:
        return False
    return target_state in allowed_states


class FumigationService:
    AVAILABLE = 1
    ASSIGNED = 2
    STARTED = 3
    COMPLETED = 4

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
            raise ValueError("Por favor, seleccione al menos un Lote para continuar.")

        if Fumigation.query.filter_by(work_order=work_order).first():
            raise ValueError("La Orden de Fumigación ya existe. Por favor, use otra.")

        with cls._transaction_context():
            lots = cls._load_lots_for_update(lot_ids)
            if len(lots) != len(set(lot_ids)):
                raise ValueError("Uno o más lotes seleccionados no existen.")

            fumigation = Fumigation(work_order=work_order)
            db.session.add(fumigation)

            for lot in lots:
                transition_fumigation_status(lot, cls.ASSIGNED)
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
            raise ValueError("Esta fumigación ya fue completada.")

        with cls._transaction_context():
            for lot in fumigation.lots:
                transition_fumigation_status(lot, cls.STARTED)

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
            raise ValueError("Esta fumigación ya fue completada.")

        with cls._transaction_context():
            for lot in fumigation.lots:
                transition_fumigation_status(lot, cls.COMPLETED)

            fumigation.real_end_date = real_end_date
            fumigation.real_end_time = real_end_time
            if certificate_path:
                fumigation.certificate_path = certificate_path
            db.session.add(fumigation)

        return fumigation
