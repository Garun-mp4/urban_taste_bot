from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

BOOKING_BUTTON = "📅 Забронировать столик"
MENU_BUTTON = "🍽 Узнать меню"
QUESTION_BUTTON = "💬 Задать вопрос"
INFO_BUTTON = "📍 Адрес и часы работы"
MY_REQUESTS_BUTTON = "📋 Мои заявки"
CANCEL_BUTTON = "❌ Отменить"
PHONE_BUTTON = "📱 Отправить номер телефона"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BOOKING_BUTTON)],
            [KeyboardButton(text=MENU_BUTTON), KeyboardButton(text=QUESTION_BUTTON)],
            [KeyboardButton(text=INFO_BUTTON)],
            [KeyboardButton(text=MY_REQUESTS_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def booking_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=PHONE_BUTTON, request_contact=True)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите номер или отправьте контакт",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Заполните заявку или отмените",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
