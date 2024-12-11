from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models here to ensure they're registered
from .user import User
from .task import Task
from .meeting import Meeting
from .department import Department
from .category import Category
from .project import Project 