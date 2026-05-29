"""SQLAlchemy ORM models.

Model modules define database table mappings only. Keep business rules in
services and database query composition in repositories.
"""

from app.models.agent import AgentRun
from app.models.chunk import DocumentChunk
from app.models.course import Course
from app.models.diagnosis import DiagnosisReport
from app.models.evolution import EvolutionEvent, EvolutionStrategy
from app.models.feedback import UserFeedback
from app.models.knowledge import KnowledgePoint
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.learning_record import LearningRecord
from app.models.llm_log import LLMCallLog
from app.models.material import CourseMaterial
from app.models.memory import StudentMemory
from app.models.profile import LearningPreference, StudentProfile
from app.models.prompt import PromptVersion
from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz
from app.models.recommendation import Recommendation
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.wiki import WikiLink, WikiPage, WikiPageVersion, WikiSource

__all__ = [
    "AgentRun",
    "Course",
    "CourseMaterial",
    "DiagnosisReport",
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
    "AnswerRecord",
    "MistakeBook",
    "Question",
    "Quiz",
    "Recommendation",
    "StudentMemory",
    "StudentProfile",
    "UserFeedback",
    "User",
    "WikiLink",
    "WikiPage",
    "WikiPageVersion",
    "WikiSource",
]
