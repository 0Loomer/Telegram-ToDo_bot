import json
import os
from pathlib import Path
 
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
FILE = "tasks.json"

ADDING, EDITING = range(2)
DEFAULT_LANG = "en"

TEXTS = {
    "fa": {
        "choose_language": "زبان را انتخاب کن 👇",
        "language_set": "✅ زبان تنظیم شد.",
        "welcome": "سلام 👋\nمن بات مدیریت تسک‌هات هستم.",
        "commands": (
            "دستورات:\n"
            "/addtask - افزودن تسک جدید\n"
            "/tasks - نمایش لیست\n"
            "/language - تغییر زبان\n"
            "/cancel - لغو عملیات"
        ),
        "list_empty": "📭 لیست کارها خالیه.",
        "list_title": "📋 لیست کارهای شما",
        "list_count": "انجام‌شده: {done}/{total}",
        "add_prompt": "📝 لطفاً عنوان تسک را بفرست:",
        "add_empty": "عنوان خالیه — لطفاً متن معنادار بفرست.",
        "add_success": "✅ تسک «{title}» اضافه شد.",
        "edit_prompt": "✏️ لطفاً عنوان جدید را بفرست:",
        "edit_done": "✅ ویرایش انجام شد.",
        "cancel_done": "📛 عملیات کنسل شد.",
        "unknown": "❔ دستور ناشناخته — از /tasks یا /addtask استفاده کن.",
        "not_found": "خطا: آیتم پیدا نشد.",
        "lang_fa": "فارسی",
        "lang_en": "English",
        "add_button": "➕ افزودن",
        "language_button": "🌐 زبان",
        "toggle_button": "🔁 تغییر وضعیت",
        "edit_button": "✏️ ویرایش",
        "delete_button": "🗑️ حذف",
        "status_done": "✅",
        "status_todo": "⬜",
    },
    "en": {
        "choose_language": "Choose a language 👇",
        "language_set": "✅ Language set.",
        "welcome": "Hi 👋\nI am your task manager bot.",
        "commands": (
            "Commands:\n"
            "/addtask - add a new task\n"
            "/tasks - show your list\n"
            "/language - change language\n"
            "/cancel - cancel current action"
        ),
        "list_empty": "📭 Your task list is empty.",
        "list_title": "📋 Your tasks",
        "list_count": "Done: {done}/{total}",
        "add_prompt": "📝 Please send the task title:",
        "add_empty": "Title is empty — please send something meaningful.",
        "add_success": "✅ Task “{title}” added.",
        "edit_prompt": "✏️ Please send the new title:",
        "edit_done": "✅ Task updated.",
        "cancel_done": "📛 Action cancelled.",
        "unknown": "❔ Unknown command — use /tasks or /addtask.",
        "not_found": "Error: item not found.",
        "lang_fa": "فارسی",
        "lang_en": "English",
        "add_button": "➕ Add",
        "language_button": "🌐 Language",
        "toggle_button": "🔁 Toggle",
        "edit_button": "✏️ Edit",
        "delete_button": "🗑️ Delete",
        "status_done": "✅",
        "status_todo": "⬜",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else DEFAULT_LANG
    text = TEXTS[lang].get(key, TEXTS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs)


class StorageManager:
    def __init__(self, filename=FILE):
        self.path = Path(filename)
        if not self.path.exists():
            self._save_all({"users": {}})

    def _normalize_task(self, task):
        if not isinstance(task, dict):
            return {"title": str(task), "done": False}
        title = str(task.get("title", "")).strip()
        done = bool(task.get("done", False))
        return {"title": title, "done": done}

    def _normalize_data(self, data):
        if not isinstance(data, dict):
            return {"users": {}}

        if "users" in data and isinstance(data["users"], dict):
            users = {}
            for uid, info in data["users"].items():
                if not isinstance(info, dict):
                    continue
                lang = info.get("lang") if info.get("lang") in TEXTS else None
                tasks = info.get("tasks", [])
                if not isinstance(tasks, list):
                    tasks = []
                users[str(uid)] = {
                    "lang": lang,
                    "tasks": [self._normalize_task(task) for task in tasks],
                }
            return {"users": users}

        users = {}
        for uid, tasks in data.items():
            if isinstance(tasks, list):
                users[str(uid)] = {
                    "lang": None,
                    "tasks": [self._normalize_task(task) for task in tasks],
                }
        return {"users": users}

    def _load_all(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return self._normalize_data(raw)
        except Exception:
            return {"users": {}}

    def _save_all(self, data):
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_user_record(self, user_id):
        data = self._load_all()
        users = data.setdefault("users", {})
        uid = str(user_id)

        if uid not in users or not isinstance(users[uid], dict):
            users[uid] = {"lang": None, "tasks": []}

        users[uid].setdefault("lang", None)
        users[uid].setdefault("tasks", [])
        if not isinstance(users[uid]["tasks"], list):
            users[uid]["tasks"] = []

        return data, users[uid]

    def has_lang(self, user_id):
        _, record = self._get_user_record(user_id)
        return bool(record.get("lang"))

    def get_lang(self, user_id):
        _, record = self._get_user_record(user_id)
        return record.get("lang") or DEFAULT_LANG

    def set_lang(self, user_id, lang):
        data, record = self._get_user_record(user_id)
        record["lang"] = lang if lang in TEXTS else DEFAULT_LANG
        self._save_all(data)

    def get_tasks(self, user_id):
        _, record = self._get_user_record(user_id)
        tasks = record.get("tasks", [])
        if not isinstance(tasks, list):
            return []
        return [self._normalize_task(task) for task in tasks]

    def save_tasks(self, user_id, tasks):
        data, record = self._get_user_record(user_id)
        record["tasks"] = [self._normalize_task(task) for task in tasks]
        self._save_all(data)

    def add_task(self, user_id, task_obj):
        tasks = self.get_tasks(user_id)
        tasks.append(self._normalize_task(task_obj))
        self.save_tasks(user_id, tasks)

    def toggle_task(self, user_id, idx):
        tasks = self.get_tasks(user_id)
        if 0 <= idx < len(tasks):
            tasks[idx]["done"] = not tasks[idx].get("done", False)
            self.save_tasks(user_id, tasks)
            return True
        return False

    def update_task(self, user_id, idx, title):
        tasks = self.get_tasks(user_id)
        if 0 <= idx < len(tasks):
            tasks[idx]["title"] = title.strip()
            self.save_tasks(user_id, tasks)
            return True
        return False

    def delete_task(self, user_id, idx):
        tasks = self.get_tasks(user_id)
        if 0 <= idx < len(tasks):
            removed = tasks.pop(idx)
            self.save_tasks(user_id, tasks)
            return removed
        return None


storage = StorageManager()


def build_language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(TEXTS["fa"]["lang_fa"], callback_data="lang_fa"),
            InlineKeyboardButton(TEXTS["en"]["lang_en"], callback_data="lang_en"),
        ]
    ])


def build_main_keyboard(lang, tasks):
    buttons = []

    if tasks:
        for i, _ in enumerate(tasks):
            buttons.append([
                InlineKeyboardButton(
                    t(lang, "toggle_button"),
                    callback_data=f"toggle_{i}",
                ),
                InlineKeyboardButton(
                    t(lang, "edit_button"),
                    callback_data=f"edit_{i}",
                ),
                InlineKeyboardButton(
                    t(lang, "delete_button"),
                    callback_data=f"delete_{i}",
                ),
            ])

    buttons.append([
        InlineKeyboardButton(t(lang, "add_button"), callback_data="start_add"),
        InlineKeyboardButton(t(lang, "language_button"), callback_data="choose_language"),
    ])

    return InlineKeyboardMarkup(buttons)


async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, edit: bool = False):
    lang = storage.get_lang(user_id)
    tasks = storage.get_tasks(user_id)

    if not tasks:
        text = t(lang, "list_empty")
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(t(lang, "add_button"), callback_data="start_add"),
                InlineKeyboardButton(t(lang, "language_button"), callback_data="choose_language"),
            ]
        ])
    else:
        done_count = sum(1 for task in tasks if task.get("done"))
        total_count = len(tasks)
        lines = []
        for i, task in enumerate(tasks):
            status = t(lang, "status_done") if task.get("done") else t(lang, "status_todo")
            title = task.get("title", "")
            lines.append(f"{i+1}. {status} {title}")

        text = (
            f"{t(lang, 'list_title')}\n"
            f"{t(lang, 'list_count', done=done_count, total=total_count)}\n\n"
            + "\n".join(lines)
        )
        markup = build_main_keyboard(lang, tasks)

    if edit and update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
            return
        except Exception:
            pass

    await update.effective_message.reply_text(text, reply_markup=markup)


async def ask_language(update: Update, lang=DEFAULT_LANG):
    await update.effective_message.reply_text(
        t(lang, "choose_language"),
        reply_markup=build_language_keyboard(),
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not storage.has_lang(user_id):
        await ask_language(update, DEFAULT_LANG)
        return

    lang = storage.get_lang(user_id)
    await update.effective_message.reply_text(
        f"{t(lang, 'welcome')}\n\n{t(lang, 'commands')}",
        reply_markup=build_main_keyboard(lang, storage.get_tasks(user_id)),
    )


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = storage.get_lang(update.effective_user.id)
    await ask_language(update, lang)


async def addtask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = storage.get_lang(user_id)

    if not storage.has_lang(user_id):
        await ask_language(update, DEFAULT_LANG)
        return

    if context.args:
        title = " ".join(context.args).strip()
        if title:
            storage.add_task(user_id, {"title": title, "done": False})
            await update.message.reply_text(t(lang, "add_success", title=title))
            await show_tasks(update, context, user_id)
            return

    context.user_data["expecting_add"] = True
    context.user_data.pop("editing_index", None)
    await update.message.reply_text(t(lang, "add_prompt"))


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = storage.get_lang(user_id)

    context.user_data.pop("expecting_add", None)
    context.user_data.pop("editing_index", None)

    await update.message.reply_text(t(lang, "cancel_done"))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang = storage.get_lang(user_id)
    data = query.data

    if data == "choose_language":
        await query.edit_message_text(
            t(lang, "choose_language"),
            reply_markup=build_language_keyboard(),
        )
        return

    if data in ("lang_fa", "lang_en"):
        new_lang = "fa" if data == "lang_fa" else "en"
        storage.set_lang(user_id, new_lang)
        context.user_data.pop("expecting_add", None)
        context.user_data.pop("editing_index", None)

        await query.edit_message_text(t(new_lang, "language_set"))
        await query.message.reply_text(
            f"{t(new_lang, 'welcome')}\n\n{t(new_lang, 'commands')}",
            reply_markup=build_main_keyboard(new_lang, storage.get_tasks(user_id)),
        )
        return

    if data == "start_add":
        context.user_data["expecting_add"] = True
        context.user_data.pop("editing_index", None)
        await query.edit_message_text(t(lang, "add_prompt"))
        return

    if data.startswith("toggle_"):
        idx = int(data.split("_", 1)[1])
        ok = storage.toggle_task(user_id, idx)
        if ok:
            await show_tasks(update, context, user_id, edit=True)
        else:
            await query.edit_message_text(t(lang, "not_found"))
        return

    if data.startswith("edit_"):
        idx = int(data.split("_", 1)[1])
        tasks = storage.get_tasks(user_id)
        if 0 <= idx < len(tasks):
            context.user_data["editing_index"] = idx
            context.user_data.pop("expecting_add", None)
            await query.edit_message_text(t(lang, "edit_prompt"))
        else:
            await query.edit_message_text(t(lang, "not_found"))
        return

    if data.startswith("delete_"):
        idx = int(data.split("_", 1)[1])
        removed = storage.delete_task(user_id, idx)
        if removed is None:
            await query.edit_message_text(t(lang, "not_found"))
        else:
            await show_tasks(update, context, user_id, edit=True)
        return


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id

    if not storage.has_lang(user_id):
        await ask_language(update, DEFAULT_LANG)
        return

    lang = storage.get_lang(user_id)
    text = (update.message.text or "").strip()

    if context.user_data.pop("expecting_add", False):
        if not text:
            await update.message.reply_text(t(lang, "add_empty"))
            return

        storage.add_task(user_id, {"title": text, "done": False})
        await update.message.reply_text(t(lang, "add_success", title=text))
        await show_tasks(update, context, user_id)
        return

    if "editing_index" in context.user_data:
        idx = context.user_data.pop("editing_index")
        if not text:
            await update.message.reply_text(t(lang, "add_empty"))
            return

        ok = storage.update_task(user_id, idx, text)
        if ok:
            await update.message.reply_text(t(lang, "edit_done"))
            await show_tasks(update, context, user_id)
        else:
            await update.message.reply_text(t(lang, "not_found"))
        return

    return 


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN not found in environment variables.")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("addtask", addtask_cmd))
    app.add_handler(CommandHandler("tasks", lambda update, context: show_tasks(update, context, update.effective_user.id)))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot is running")
    app.run_polling()


if __name__ == "__main__":
    main()
