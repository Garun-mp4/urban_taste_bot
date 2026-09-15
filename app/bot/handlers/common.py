import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.openai_client import AIServiceError
from app.bot.handlers.booking import BOOKING_INITIAL_PROMPT, BookingStates, begin_booking
from app.bot.keyboards.main import (
    CANCEL_BUTTON,
    INFO_BUTTON,
    MENU_BUTTON,
    QUESTION_BUTTON,
    main_menu_keyboard,
)
from app.bot.utils import answer_in_chunks
from app.config import Settings
from app.database.models import MessageRole, User
from app.services.container import ServiceContainer

logger = logging.getLogger(__name__)
router = Router(name="common")

WELCOME_TEXT = (
    "Добро пожаловать в Urban Taste!\n\n"
    "Я помогу сориентироваться по ресторану, отвечу на вопросы и приму заявку "
    "на бронирование столика."
)

MENU_TEXT = (
    "Меню Urban Taste включает:\n"
    "• завтраки\n"
    "• бизнес-ланчи\n"
    "• основные блюда европейской кухни\n"
    "• десерты\n"
    "• напитки\n"
    "• вегетарианские блюда\n\n"
    "Популярные блюда: стейк Urban Classic, паста с морепродуктами, "
    "крем-суп из грибов и чизкейк Urban.\n\n"
    "Средний чек — 2500 рублей на человека."
)

INFO_TEXT = (
    "Urban Taste — современный городской ресторан европейской кухни.\n\n"
    "Адрес: ул. Центральная, 15\n"
    "Пн–Пт: 10:00–23:00\n"
    "Сб–Вс: 11:00–00:00"
)


async def _record_exchange(
    session: AsyncSession,
    user: User,
    services: ServiceContainer,
    incoming_text: str,
    response_text: str,
) -> None:
    await services.conversations.add_message(session, user.id, MessageRole.USER, incoming_text)
    await services.conversations.add_message(session, user.id, MessageRole.ASSISTANT, response_text)


def looks_like_reservation(text: str) -> bool:
    normalized = text.casefold()
    return any(
        phrase in normalized
        for phrase in ("заброниров", "брониров", "брон", "столик", "reserve", "reservation")
    )


@router.message(CommandStart())
async def command_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    await state.clear()
    await services.conversations.add_message(session, db_user.id, MessageRole.ASSISTANT, WELCOME_TEXT)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_BUTTON)
async def cancel_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Текущий сценарий отменён. Выберите действие в меню.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(StateFilter(None), F.text == MENU_BUTTON)
async def show_menu(
    message: Message,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    await _record_exchange(session, db_user, services, MENU_BUTTON, MENU_TEXT)
    await message.answer(MENU_TEXT, reply_markup=main_menu_keyboard())


@router.message(StateFilter(None), F.text == INFO_BUTTON)
async def show_info(
    message: Message,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    await _record_exchange(session, db_user, services, INFO_BUTTON, INFO_TEXT)
    await message.answer(INFO_TEXT, reply_markup=main_menu_keyboard())


@router.message(StateFilter(None), F.text == QUESTION_BUTTON)
async def ask_question(
    message: Message,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    prompt = "Напишите ваш вопрос обычным сообщением — я постараюсь помочь."
    await _record_exchange(session, db_user, services, QUESTION_BUTTON, prompt)
    await message.answer(prompt, reply_markup=main_menu_keyboard())


@router.message(StateFilter(None), F.text)
async def handle_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    user_text = (message.text or "").strip()
    if not user_text:
        return
    if user_text.startswith("/"):
        return

    if looks_like_reservation(user_text):
        await begin_booking(
            message,
            state,
            session,
            db_user,
            services,
            source_text=user_text,
        )
        return

    await services.conversations.add_message(session, db_user.id, MessageRole.USER, user_text)
    history = await services.conversations.get_ai_history(
        session,
        db_user.id,
        settings.ai_history_limit,
    )

    try:
        ai_reply = await services.ai.answer(history)
    except AIServiceError:
        logger.exception("AI response failed for user_id=%s", db_user.id)
        fallback = (
            "Сейчас я не могу получить ответ от AI-ассистента. Я передам ваш вопрос "
            "администратору — он свяжется с вами при необходимости."
        )
        request = await services.requests.create_question(session, db_user, question=user_text)
        await services.conversations.add_message(session, db_user.id, MessageRole.ASSISTANT, fallback)
        try:
            await services.notifications.send_request(request)
        except Exception:
            logger.exception("Could not notify admin about question request_id=%s", request.id)
        await answer_in_chunks(message, fallback, reply_markup=main_menu_keyboard())
        return

    if ai_reply.intent == "reservation":
        await state.clear()
        await state.set_state(BookingStates.name)
        await services.conversations.add_message(
            session,
            db_user.id,
            MessageRole.ASSISTANT,
            BOOKING_INITIAL_PROMPT,
        )
        await message.answer(BOOKING_INITIAL_PROMPT, reply_markup=main_menu_keyboard())
        return

    response = ai_reply.answer
    if ai_reply.needs_admin:
        request = await services.requests.create_question(session, db_user, question=user_text)
        notification_sent = True
        try:
            await services.notifications.send_request(request)
        except Exception:
            notification_sent = False
            logger.exception("Could not notify admin about question request_id=%s", request.id)
        if not notification_sent:
            response = (
                "Я сохранил ваш вопрос в CRM, но временно не смог отправить уведомление. "
                "Администратор увидит обращение при следующей проверке."
            )

    await services.conversations.add_message(session, db_user.id, MessageRole.ASSISTANT, response)
    await answer_in_chunks(message, response, reply_markup=main_menu_keyboard())
