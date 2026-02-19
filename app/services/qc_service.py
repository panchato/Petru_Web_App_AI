from decimal import Decimal, ROUND_HALF_UP

from app import db
from app.models import Lot, LotQC, SampleQC


class QCValidationError(ValueError):
    pass


class QCService:
    @staticmethod
    def _transaction_context():
        session = db.session()
        return session.begin_nested() if session.in_transaction() else session.begin()

    @staticmethod
    def _to_decimal(value):
        return Decimal(str(value or 0))

    @staticmethod
    def _build_qc_metrics(payload):
        units = (
            int(payload["lessthan30"])
            + int(payload["between3032"])
            + int(payload["between3234"])
            + int(payload["between3436"])
            + int(payload["morethan36"])
        )
        if units != 100:
            raise QCValidationError("Las unidades analizadas deben sumar exactamente 100.")

        inshell_weight = QCService._to_decimal(payload["inshell_weight"])
        if inshell_weight <= 0:
            raise QCValidationError("El peso con cáscara debe ser mayor que 0.")

        shelled_weight = (
            QCService._to_decimal(payload["extra_light"])
            + QCService._to_decimal(payload["light"])
            + QCService._to_decimal(payload["light_amber"])
            + QCService._to_decimal(payload["amber"])
        )
        if shelled_weight <= 0:
            raise QCValidationError("El peso de pulpa calculado debe ser mayor que 0.")

        yieldpercentage = ((shelled_weight / inshell_weight) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return {
            "units": units,
            "shelled_weight": float(shelled_weight),
            "yieldpercentage": float(yieldpercentage),
        }

    @staticmethod
    def validate_payload(payload):
        return QCService._build_qc_metrics(payload)

    @staticmethod
    def create_lot_qc(payload, inshell_image_path, shelled_image_path):
        metrics = QCService._build_qc_metrics(payload)
        lot = db.session.get(Lot, payload["lot_id"])
        if not lot:
            raise QCValidationError("El lote seleccionado no existe.")
        if lot.has_qc:
            raise QCValidationError("El lote seleccionado ya tiene un registro QC.")

        with QCService._transaction_context():
            lot_qc = LotQC(
                lot_id=payload["lot_id"],
                analyst=payload["analyst"],
                date=payload["date"],
                time=payload["time"],
                units=metrics["units"],
                inshell_weight=payload["inshell_weight"],
                shelled_weight=metrics["shelled_weight"],
                yieldpercentage=metrics["yieldpercentage"],
                lessthan30=payload["lessthan30"],
                between3032=payload["between3032"],
                between3234=payload["between3234"],
                between3436=payload["between3436"],
                morethan36=payload["morethan36"],
                broken_walnut=payload["broken_walnut"],
                split_walnut=payload["split_walnut"],
                light_stain=payload["light_stain"],
                serious_stain=payload["serious_stain"],
                adhered_hull=payload["adhered_hull"],
                shrivel=payload["shrivel"],
                empty=payload["empty"],
                insect_damage=payload["insect_damage"],
                inactive_fungus=payload["inactive_fungus"],
                active_fungus=payload["active_fungus"],
                extra_light=payload["extra_light"],
                light=payload["light"],
                light_amber=payload["light_amber"],
                amber=payload["amber"],
                yellow=payload["yellow"],
                inshell_image_path=inshell_image_path,
                shelled_image_path=shelled_image_path,
            )
            db.session.add(lot_qc)
            lot.has_qc = True
            db.session.add(lot)

        return lot_qc

    @staticmethod
    def create_sample_qc(payload, inshell_image_path, shelled_image_path):
        metrics = QCService._build_qc_metrics(payload)

        with QCService._transaction_context():
            sample_qc = SampleQC(
                grower=payload["grower"],
                brought_by=payload["brought_by"],
                analyst=payload["analyst"],
                date=payload["date"],
                time=payload["time"],
                units=metrics["units"],
                inshell_weight=payload["inshell_weight"],
                shelled_weight=metrics["shelled_weight"],
                yieldpercentage=metrics["yieldpercentage"],
                lessthan30=payload["lessthan30"],
                between3032=payload["between3032"],
                between3234=payload["between3234"],
                between3436=payload["between3436"],
                morethan36=payload["morethan36"],
                broken_walnut=payload["broken_walnut"],
                split_walnut=payload["split_walnut"],
                light_stain=payload["light_stain"],
                serious_stain=payload["serious_stain"],
                adhered_hull=payload["adhered_hull"],
                shrivel=payload["shrivel"],
                empty=payload["empty"],
                insect_damage=payload["insect_damage"],
                inactive_fungus=payload["inactive_fungus"],
                active_fungus=payload["active_fungus"],
                extra_light=payload["extra_light"],
                light=payload["light"],
                light_amber=payload["light_amber"],
                amber=payload["amber"],
                yellow=payload["yellow"],
                inshell_image_path=inshell_image_path,
                shelled_image_path=shelled_image_path,
            )
            db.session.add(sample_qc)

        return sample_qc
