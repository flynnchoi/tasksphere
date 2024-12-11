from . import db

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    # Relationships
    department = db.relationship('Department', backref='projects')

    def __repr__(self):
        return f'<Project {self.name}>' 