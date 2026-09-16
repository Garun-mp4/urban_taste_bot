import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge_base import INFO_TEXT, MENU_TEXT
from app.ai.openai_client import AIServiceError
from app.bot.handlers.booking import BOOKING_INITIAL_PROMPT, BookingStates, begin_booking
from app.bot.keyboards.booking import booking_cancel_keyboard
from app.bot.keyboards.client import client_request_keyboard
from app.bot.keyboards.main import (
    CANCEL_BUTTON,
    INFO_BUTTON,
    MENU_BUTTON,
    MY_REQUESTS_BUTTON,
    QUESTION_BUTTON,
    main_menu_keyboard,
)
from app.bot.utils import answer_in_chunks
from app.config import Settings
from app.database.models import MessageRole, User
from app.services.container import ServiceContainer
from app.services.notifications import format_client_request_message

logger = logging.getLogger(__name__)
router = Router(name="common")

WELCOME_TEXT = (
    "Добро пожаловать в Urban Taste!\n\n"
    "Я помогу сориентироваться по ресторану, отвечу на вопросы и приму заявку "
    "на бронирование столика."
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


@router.message(Command("my_bookings"))
@router.message(Command("my_requests"))
@router.message(StateFilter(None), F.text == MY_REQUESTS_BUTTON)
async def show_my_requests(
    message: Message,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    requests = await services.requests.get_for_user(session, db_user.id, limit=10)
    if not requests:
        await message.answer("У вас пока нет заявок.", reply_markup=main_menu_keyboard())
        return
    await message.answer("Ваши последние заявки:")
    for request in requests:
        await message.answer(
            format_client_request_message(request),
            reply_markup=client_request_keyboard(request.id, request.status),
        )


@router.callback_query(F.data.startswith("client_request:cancel:"))
async def cancel_client_request(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    try:
        request_id = int((callback.data or "").split(":", 2)[-1])
    except (TypeError, ValueError):
        await callback.answer("Некорректная заявка", show_alert=True)
        return
    try:
        request = await services.requests.cancel_for_user(session, db_user.id, request_id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if request is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    await services.notifications.enqueue_admin_update(session, request)
    await callback.answer("Заявка отменена")
    if callback.message is not None:
        await callback.message.edit_text(format_client_request_message(request))


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
        max_chars=settings.ai_history_char_limit,
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
        await services.notifications.enqueue_request(session, request)
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
        await message.answer(BOOKING_INITIAL_PROMPT, reply_markup=booking_cancel_keyboard())
        return

    response = ai_reply.answer
    if ai_reply.needs_admin and ai_reply.intent != "off_topic":
        request = await services.requests.create_question(session, db_user, question=user_text)
        await services.notifications.enqueue_request(session, request)

    await services.conversations.add_message(session, db_user.id, MessageRole.ASSISTANT, response)
    await answer_in_chunks(message, response, reply_markup=main_menu_keyboard())
