import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.booking import (
    booking_calendar_keyboard,
    booking_cancel_keyboard,
    booking_confirmation_keyboard,
    custom_guests_keyboard,
    guests_keyboard,
    time_slots_keyboard,
)
from app.bot.keyboards.main import (
    BOOKING_BUTTON,
    PHONE_BUTTON,
    booking_keyboard,
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
from app.services.requests import ReservationSlotUnavailable

logger = logging.getLogger(__name__)
router = Router(name="booking")

BOOKING_INITIAL_PROMPT = "Отлично, оформим заявку на бронирование. Как вас зовут?"


class BookingStates(StatesGroup):
    name = State()
    guests = State()
    reservation_date = State()
    reservation_time = State()
    phone = State()
    confirmation = State()


async def _record_exchange(
    session: AsyncSession,
    user: User,
    services: ServiceContainer,
    incoming_text: str,
    response_text: str,
) -> None:
    await services.conversations.add_message(session, user.id, MessageRole.USER, incoming_text)
    await services.conversations.add_message(session, user.id, MessageRole.ASSISTANT, response_text)


def _today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def _validate_booking_date(value: date, settings: Settings) -> date:
    today = _today(settings)
    last_bookable_day = today + timedelta(days=settings.reservation_max_days)
    if value > last_bookable_day:
        raise BookingValidationError(
            f"Бронирование доступно максимум на {settings.reservation_max_days} дней вперёд"
        )
    return value


def _format_booking_summary(data: dict[str, object]) -> str:
    reservation_date = date.fromisoformat(str(data["reservation_date"]))
    reservation_time = time.fromisoformat(str(data["reservation_time"]))
    return (
        "Проверьте данные заявки:\n\n"
        f"Имя: {data['customer_name']}\n"
        f"Гостей: {data['guests']}\n"
        f"Дата: {reservation_date.strftime('%d.%m.%Y')}\n"
        f"Время: {reservation_time.strftime('%H:%M')}\n"
        f"Телефон: {data['phone']}\n\n"
        "После подтверждения заявка будет передана администратору."
    )


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
    await message.answer(prompt, reply_markup=booking_cancel_keyboard())


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
    settings: Settings,
) -> None:
    try:
        customer_name = validate_customer_name(message.text or "")
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, message.text or "", str(exc))
        await message.answer(f"{exc}. Попробуйте ещё раз.", reply_markup=booking_cancel_keyboard())
        return

    await state.update_data(customer_name=customer_name, awaiting_custom_guests=False)
    response = (
        "Сколько будет гостей? Выберите вариант или введите число от 1 до "
        f"{settings.reservation_capacity}."
    )
    await state.set_state(BookingStates.guests)
    await _record_exchange(session, db_user, services, message.text or "", response)
    await message.answer(response, reply_markup=guests_keyboard(settings.reservation_capacity))


async def _accept_guests(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    raw_value: str,
    settings: Settings,
) -> None:
    try:
        guests = parse_guests(raw_value, settings.reservation_capacity)
    except BookingValidationError as exc:
        await _record_exchange(session, db_user, services, raw_value, str(exc))
        await message.answer(
            f"{exc}. Попробуйте ещё раз.",
            reply_markup=guests_keyboard(settings.reservation_capacity),
        )
        return

    await state.update_data(guests=guests, awaiting_custom_guests=False)
    response = "Выберите дату визита:"
    await state.set_state(BookingStates.reservation_date)
    await _record_exchange(session, db_user, services, raw_value, response)
    await message.answer(
        response,
        reply_markup=booking_calendar_keyboard(
            timezone=settings.timezone,
            max_days=settings.reservation_max_days,
        ),
    )


@router.callback_query(BookingStates.guests, F.data.startswith("booking:guests:"))
async def booking_guests_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if callback.message is None:
        return
    value = (callback.data or "").split(":", 2)[-1]
    await callback.answer()
    if value == "custom":
        await state.update_data(awaiting_custom_guests=True)
        prompt = (
            "Введите количество гостей целым числом от 1 до "
            f"{settings.reservation_capacity}."
        )
        await services.conversations.add_message(session, db_user.id, MessageRole.ASSISTANT, prompt)
        await callback.message.answer(prompt, reply_markup=custom_guests_keyboard())
        return
    await _accept_guests(callback.message, state, session, db_user, services, value, settings)


@router.message(BookingStates.guests, F.text)
async def booking_guests(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    await _accept_guests(message, state, session, db_user, services, message.text or "", settings)


async def _show_time_step(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
    reservation_date: date,
    incoming_text: str,
) -> None:
    data = await state.get_data()
    guests = int(data.get("guests", 1))
    slots = await services.requests.get_available_slots(
        session,
        reservation_date,
        guests=guests,
    )
    if not slots:
        response = "На эту дату нет подходящих свободных слотов. Выберите другую дату."
        await state.set_state(BookingStates.reservation_date)
        await _record_exchange(session, db_user, services, incoming_text, response)
        await message.answer(
            response,
            reply_markup=booking_calendar_keyboard(
                timezone=settings.timezone,
                max_days=settings.reservation_max_days,
            ),
        )
        return

    response = (
        f"Свободное время на {reservation_date.strftime('%d.%m.%Y')} для {guests} "
        "гостей:"
    )
    await state.set_state(BookingStates.reservation_time)
    await _record_exchange(session, db_user, services, incoming_text, response)
    await message.answer(
        response,
        reply_markup=time_slots_keyboard([slot.strftime("%H:%M") for slot in slots]),
    )


async def _accept_date(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
    raw_value: str,
) -> None:
    try:
        reservation_date = _validate_booking_date(
            parse_reservation_date(raw_value, settings.timezone),
            settings,
        )
    except (BookingValidationError, ValueError) as exc:
        response = str(exc)
        await _record_exchange(session, db_user, services, raw_value, response)
        await message.answer(
            f"{response}. Попробуйте ещё раз.",
            reply_markup=booking_calendar_keyboard(
                timezone=settings.timezone,
                max_days=settings.reservation_max_days,
            ),
        )
        return

    await state.update_data(reservation_date=reservation_date.isoformat())
    await _show_time_step(
        message,
        state,
        session,
        db_user,
        services,
        settings,
        reservation_date,
        raw_value,
    )


@router.callback_query(BookingStates.reservation_date, F.data.startswith("booking:month:"))
async def booking_month_callback(
    callback: CallbackQuery,
    settings: Settings,
) -> None:
    if callback.message is None:
        return
    try:
        reference = date.fromisoformat((callback.data or "").split(":", 2)[-1])
    except ValueError:
        await callback.answer("Некорректный месяц", show_alert=True)
        return
    await callback.message.edit_reply_markup(
        reply_markup=booking_calendar_keyboard(
            timezone=settings.timezone,
            reference=reference,
            max_days=settings.reservation_max_days,
        )
    )
    await callback.answer()


@router.callback_query(BookingStates.reservation_date, F.data.startswith("booking:date:"))
async def booking_date_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if callback.message is None:
        return
    raw_value = (callback.data or "").split(":", 2)[-1]
    await callback.answer()
    await _accept_date(callback.message, state, session, db_user, services, settings, raw_value)


@router.message(BookingStates.reservation_date, F.text)
async def booking_date(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    await _accept_date(message, state, session, db_user, services, settings, message.text or "")


async def _ask_phone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    reservation_time: time,
) -> None:
    await state.update_data(reservation_time=reservation_time.strftime("%H:%M"))
    response = "Оставьте номер телефона для связи или воспользуйтесь кнопкой ниже."
    await state.set_state(BookingStates.phone)
    await _record_exchange(session, db_user, services, reservation_time.strftime("%H:%M"), response)
    await message.answer(response, reply_markup=booking_keyboard())


async def _accept_time(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    raw_value: str,
) -> None:
    try:
        reservation_time = parse_reservation_time(raw_value)
        data = await state.get_data()
        reservation_date = date.fromisoformat(str(data["reservation_date"]))
        if not await services.requests.is_slot_available(
            session,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            guests=int(data["guests"]),
        ):
            raise BookingValidationError("Выбранное время уже занято или недоступно")
    except (BookingValidationError, ValueError, KeyError) as exc:
        response = str(exc)
        await _record_exchange(session, db_user, services, raw_value, response)
        await message.answer(f"{response}. Выберите другое время.")
        return

    await _ask_phone(message, state, session, db_user, services, reservation_time)


@router.callback_query(BookingStates.reservation_time, F.data.startswith("booking:time:"))
async def booking_time_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    if callback.message is None:
        return
    raw_value = (callback.data or "").split(":", 2)[-1]
    await callback.answer()
    await _accept_time(callback.message, state, session, db_user, services, raw_value)


@router.message(BookingStates.reservation_time, F.text)
async def booking_time(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    await _accept_time(message, state, session, db_user, services, message.text or "")


async def _show_confirmation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    phone: str,
) -> None:
    await state.update_data(phone=phone)
    data = await state.get_data()
    response = _format_booking_summary(data)
    await state.set_state(BookingStates.confirmation)
    await _record_exchange(session, db_user, services, "Телефон предоставлен", response)
    await message.answer(response, reply_markup=booking_confirmation_keyboard())


async def _finish_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
) -> None:
    data = await state.get_data()
    request = await services.requests.create_reservation(
        session,
        db_user,
        customer_name=str(data["customer_name"]),
        phone=str(data["phone"]),
        guests=int(data["guests"]),
        reservation_date=date.fromisoformat(str(data["reservation_date"])),
        reservation_time=time.fromisoformat(str(data["reservation_time"])),
    )
    await services.users.update_phone(session, db_user, str(data["phone"]))
    await services.notifications.enqueue_request(session, request)

    response = (
        "Спасибо! Заявка на бронирование принята. Администратор свяжется с вами для "
        "подтверждения."
    )
    await _record_exchange(session, db_user, services, "Заявка подтверждена", response)
    await state.clear()
    await message.answer(response, reply_markup=main_menu_keyboard())


async def _confirm_booking(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    try:
        await _finish_booking(message, state, session, db_user, services)
    except ReservationSlotUnavailable as exc:
        await state.set_state(BookingStates.reservation_date)
        await message.answer(
            f"{exc} Выберите другую дату.",
            reply_markup=booking_calendar_keyboard(
                timezone=settings.timezone,
                max_days=settings.reservation_max_days,
            ),
        )


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
    await _show_confirmation(message, state, session, db_user, services, phone)


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
    await _show_confirmation(message, state, session, db_user, services, phone)


@router.callback_query(BookingStates.confirmation, F.data == "booking:confirm")
async def booking_confirm_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if callback.message is None:
        return
    await callback.answer()
    await _confirm_booking(callback.message, state, session, db_user, services, settings)


@router.message(BookingStates.confirmation, F.text)
async def booking_confirm_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    services: ServiceContainer,
    settings: Settings,
) -> None:
    if (message.text or "").strip().casefold() in {"да", "подтвердить", "подтверждаю"}:
        await _confirm_booking(message, state, session, db_user, services, settings)
        return
    await message.answer(
        "Нажмите «Подтвердить заявку» или отмените бронирование.",
        reply_markup=booking_confirmation_keyboard(),
    )


@router.callback_query(F.data == "booking:cancel")
async def booking_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Бронирование отменено")
    if callback.message is not None:
        await callback.message.answer(
            "Сценарий отменён. Выберите действие в меню.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(BookingStates.reservation_time, F.data == "booking:back:date")
async def booking_back_to_date(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.set_state(BookingStates.reservation_date)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "Выберите дату визита:",
            reply_markup=booking_calendar_keyboard(
                timezone=settings.timezone,
                max_days=settings.reservation_max_days,
            ),
        )


@router.callback_query(BookingStates.confirmation, F.data == "booking:back:phone")
async def booking_back_to_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.phone)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "Введите номер телефона ещё раз или отправьте контакт.",
            reply_markup=booking_keyboard(),
        )


@router.callback_query(BookingStates.guests, F.data == "booking:back:guests")
async def booking_back_to_guests(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    await state.update_data(awaiting_custom_guests=True)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(
            "Введите количество гостей целым числом от 1 до "
            f"{settings.reservation_capacity}.",
            reply_markup=custom_guests_keyboard(),
        )


@router.callback_query(F.data == "booking:noop")
async def booking_noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
