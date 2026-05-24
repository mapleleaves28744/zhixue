"""SQLAlchemy ORM models.

Model modules define database table mappings only. Keep business rules in
services and database query composition in repositories.
"""

from app.models.agent import AgentRun
from app.models.chunk import DocumentChunk
from app.models.course import Course
from app.models.evolution import EvolutionEvent, EvolutionStrategy
from app.models.knowledge import KnowledgePoint
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.learning_record import LearningRecord
from app.models.llm_log import LLMCallLog
from app.models.material import CourseMaterial
from app.models.memory import StudentMemory
from app.models.profile import LearningPreference, StudentProfile
from app.models.prompt import PromptVersion
from app.models.quiz import Quiz, QuizAttempt
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.wiki import WikiLink, WikiPage, WikiPageVersion, WikiSource

__all__ = [
    "AgentRun",
    "Course",
    "CourseMaterial",
    "DocumentChunk",
    "EvolutionEvent",
    "EvolutionStrategy",
    "GeneratedResource",
    "KnowledgePoint",
    "LearningPath",
    "LearningPathItem",
    "LearningRecord",
    "LearningPreference",
    "LLMCallLog",
    "PromptVersion",
    "Quiz",
    "QuizAttempt",
    "StudentMemory",
    "StudentProfile",
    "User",
    "WikiLink",
    "WikiPage",
    "WikiPageVersion",
    "WikiSource",
]
