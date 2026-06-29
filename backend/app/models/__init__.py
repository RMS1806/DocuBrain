# Re-export all models so existing code using `from app.models import User` keeps working.
from app.models.user import User, ProfessionalLink
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from app.models.audit_log import AuditLog
from app.models.quiz import Quiz, QuizItem, QuizAttempt

__all__ = ["User", "ProfessionalLink", "Document", "ChatSession", "ChatMessage", "AuditLog", "Quiz", "QuizItem", "QuizAttempt"]
