from datetime import datetime, timedelta
from . import db

class Meeting(db.Model):
    __tablename__ = 'meetings'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    duration = db.Column(db.Integer, default=60)  # Duration in minutes

    def __repr__(self):
        return f'<Meeting {self.title}>' 