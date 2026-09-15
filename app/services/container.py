from dataclasses import dataclass

from app.ai.openai_client import OpenAIClient
from app.services.conversations import ConversationService
from app.services.notifications import AdminNotificationService
from app.services.requests import RequestService
from app.services.users import UserService


@dataclass(slots=True)
class ServiceContainer:
    users: UserService
    conversations: ConversationService
    requests: RequestService
    notifications: AdminNotificationService
    ai: OpenAIClient
