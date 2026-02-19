from datetime import datetime, timezone
from app import db


def _utcnow_naive():
    # Keep DB columns naive while avoiding deprecated utcnow().
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseModel(db.Model):
    __abstract__ = True  # This ensures that the BaseModel itself isn't used to create a table
    
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=_utcnow_naive)
    updated_at = db.Column(db.DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()
