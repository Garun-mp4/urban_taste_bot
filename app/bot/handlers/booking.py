import logging
from datetime import datetime, time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import (
    BOOKING_BUTTON,
    PHONE_BUTTON,
    booking_keyboard,
    cancel_keyboard,
    main_menu_keyboard,
)
from app.config import Settings
from app.database.models import MessageRole, User
from app.services.booking import (
    BookingValidationError,
    normalize_phone,
    parse_guests,
    parse_reservation_date,
    parse_reservation_time,
    validate_customer_name,
)
from app.services.container import ServiceContainer

logger = logging.getLogger(__name__)
router = Router(name="booking")

BOOKING_INITIAL_PROMPT = "Отлично, оформим заявку на бронирование. Как вас зовут?"


class BookingStates(StatesGroup):
    name = State()
    guests = State()
    reservation_date = State()
    reservation_time = State()
    phone = State()


async def _record_exchange(
    session: AsyncSession,
    user: User,
    services: ServiceContainer,
    incoming_text: str,
    response_text: str,
) -> None:
    await services.conversations.add_message(session, user.id, MessageRole.USER, incoming_text)
    await services.conversations.add_message(session, user.id, MessageRole.ASSISTANT, response_text)


async def begin_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    *,
    source_text: str | None = None,
) -> None:
    await state.clear()
    prompt = BOOKING_INITIAL_PROMPT
    await state.set_state(BookingStates.name)
    await _record_exchange(
        session,
        db_user,
        services,
        source_text or BOOKING_BUTTON,
        prompt,
    )
    await message.answer(prompt, reply_markup=cancel_keyboard())


@router.message(F.text == BOOKING_BUTTON)
async def booking_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    await begin_booking(message, state, session, db_user, services)


@router.message(BookingStates.name, F.text)
async def booking_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    try:
        customer_name = validate_customer_name(message.text or "")
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.")
        return

    await state.update_data(customer_name=customer_name)
    response = "Сколько будет гостей? Укажите число от 1 до 50."
    await state.set_state(BookingStates.guests)
    await _record_exchange(session, db_user, services, message.text or "", response)
    await message.answer(response, reply_markup=cancel_keyboard())


@router.message(BookingStates.guests, F.text)
async def booking_guests(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    try:
        guests = parse_guests(message.text or "")
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.")
        return

    await state.update_data(guests=guests)
    response = "На какую дату планируете визит? Напишите ДД.ММ.ГГГГ или «сегодня»/«завтра»."
    await state.set_state(BookingStates.reservation_date)
    await _record_exchange(session, db_user, services, message.text or "", response)
    await message.answer(response, reply_markup=cancel_keyboard())


@router.message(BookingStates.reservation_date, F.text)
async def booking_date(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    try:
        reservation_date = parse_reservation_date(message.text or "", settings.timezone)
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.")
        return

    await state.update_data(reservation_date=reservation_date.isoformat())
    response = "На какое время? Например, 19:30."
    await state.set_state(BookingStates.reservation_time)
    await _record_exchange(session, db_user, services, message.text or "", response)
    await message.answer(response, reply_markup=cancel_keyboard())


@router.message(BookingStates.reservation_time, F.text)
async def booking_time(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    try:
        reservation_time = parse_reservation_time(message.text or "")
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.")
        return

    await state.update_data(reservation_time=reservation_time.strftime("%H:%M"))
    response = "Оставьте номер телефона для связи или воспользуйтесь кнопкой ниже."
    await state.set_state(BookingStates.phone)
    await _record_exchange(session, db_user, services, message.text or "", response)
    await message.answer(response, reply_markup=booking_keyboard())


async def _finish_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    phone: str,
) -> None:
    data = await state.get_data()
    request = await services.requests.create_reservation(
        session,
        db_user,
        customer_name=data["customer_name"],
        phone=phone,
        guests=int(data["guests"]),
        reservation_date=datetime.fromisoformat(data["reservation_date"]).date(),
        reservation_time=time.fromisoformat(data["reservation_time"]),
    )
    await services.users.update_phone(session, db_user, phone)

    notification_sent = True
    try:
        await services.notifications.send_request(request)
    except Exception:
        notification_sent = False
        logger.exception("Could not notify admin about reservation request_id=%s", request.id)

    response = (
        "Спасибо! Заявка на бронирование принята. Администратор свяжется с вами для "
        "подтверждения."
    )
    if not notification_sent:
        response += " Заявка сохранена в CRM и будет обработана администратором."
    await _record_exchange(session, db_user, services, phone, response)
    await state.clear()
    await message.answer(response, reply_markup=main_menu_keyboard())


@router.message(BookingStates.phone, F.contact)
async def booking_phone_contact(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    contact = message.contact
    if contact is None or (
        contact.user_id is not None
        and message.from_user is not None
        and contact.user_id != message.from_user.id
    ):
        await message.answer("Пожалуйста, отправьте свой контакт или введите номер вручную.")
        return
    try:
        phone = normalize_phone(contact.phone_number)
    except BookingValidationError as exc:
        await message.answer(str(exc))
        return
    await _finish_booking(message, state, session, db_user, services, phone)


@router.message(BookingStates.phone, F.text)
async def booking_phone_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    if message.text == PHONE_BUTTON:
        await message.answer("Нажмите кнопку отправки контакта или введите номер телефона вручную.")
        return
    try:
        phone = normalize_phone(message.text or "")
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.")
        return
    await _finish_booking(message, state, session, db_user, services, phone)
