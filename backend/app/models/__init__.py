"""SQLAlchemy ORM models.

Model modules define database table mappings only. Keep business rules in
services and database query composition in repositories.
"""

from app.models.ab_test import ABTest, ABTestAssignment
from app.models.agent import AgentRun
from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent
from app.models.agent_task import AgentTask, AgentTaskStep
from app.models.chunk import DocumentChunk
from app.models.course import Course
from app.models.diagnosis import DiagnosisReport
from app.models.evolution import EvolutionEvent, EvolutionStrategy
from app.models.feedback import UserFeedback
from app.models.knowledge import KnowledgePoint
from app.models.knowledge_relation import KnowledgeRelation
from app.models.student_knowledge_mastery import StudentKnowledgeMastery
from app.models.learning_path import LearningPath, LearningPathItem
from app.models.learning_record import LearningRecord
from app.models.material import CourseMaterial
from app.models.llm_log import LLMCallLog
from app.models.media import MediaAsset, MediaJob
from app.models.memory import StudentMemory
from app.models.profile import LearningPreference, StudentProfile
from app.models.prompt import PromptVersion
from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz
from app.models.recommendation import Recommendation
from app.models.resource import GeneratedResource
from app.models.user import User
from app.models.wiki import WikiLink, WikiPage, WikiPageVersion, WikiSource

__all__ = [
    "ABTest",
    "ABTestAssignment",
    "AgentRun",
    "AgentConversation",
    "AgentMessage",
    "AgentTaskEvent",
    "AgentTask",
    "AgentTaskStep",
    "Course",
    "CourseMaterial",
    "DiagnosisReport",
    "DocumentChunk",
    "EvolutionEvent",
    "EvolutionStrategy",
    "GeneratedResource",
    "KnowledgePoint",
    "KnowledgeRelation",
    "StudentKnowledgeMastery",
    "LearningPath",
    "LearningPathItem",
    "LearningRecord",
    "LearningPreference",
    "LLMCallLog",
    "MediaAsset",
    "MediaJob",
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
