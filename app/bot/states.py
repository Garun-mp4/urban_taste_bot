from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    reply = State()


class AdminPanelStates(StatesGroup):
    search = State()
    search_results = State()
