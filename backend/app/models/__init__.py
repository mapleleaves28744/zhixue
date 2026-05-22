"""SQLAlchemy ORM models.

Model modules define database table mappings only. Keep business rules in
services and database query composition in repositories.
"""

from app.models.course import Course
from app.models.material import CourseMaterial
from app.models.profile import LearningPreference, StudentProfile
from app.models.prompt import PromptVersion
from app.models.user import User

__all__ = [
    "Course",
    "CourseMaterial",
    "LearningPreference",
    "PromptVersion",
    "StudentProfile",
    "User",
]
