import json
import os
import random

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

TOKEN = os.getenv("BOT_TOKEN")
GAP = 30

with open("questions.json", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

SESSIONS = {}
POLLS = {}

SUBJECTS = {"physics", "chemistry", "maths", "biology"}


def leaderboard(scores):
    if not scores:
        return "Kisi ne answer nahi diya 😅"
    ranked = sorted(scores.values(), key=lambda x: -x[1])
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, pts) in enumerate(ranked[:10]):
        lines.append(f"{medals[i] if i < 3 else str(i + 1) + '.'} {name} — {pts}")
    return "\n".join(lines)


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in SESSIONS:
        await update.message.reply_text("Quiz already chal raha hai. /stop se rok do.")
        return

    subject, count = "all", 10
    for a in context.args:
        if a.isdigit():
            count = min(int(a), 50)
        elif a.lower() in SUBJECTS:
            subject = a.lower()

    pool = [q for q in QUESTIONS if subject == "all" or q["subject"] == subject]
    if not pool:
        await update.message.reply_text("Is subject ke questions nahi mile.")
        return
    random.shuffle(pool)
    SESSIONS[chat_id] = {"queue": pool[:count], "scores": {}}

    await update.message.reply_text(
        f"🔥 Quiz shuru! {min(count, len(pool))} questions, har {GAP}s me ek.\n"
        "Jaldi answer do, leaderboard end me milega."
    )
    context.job_queue.run_repeating(
        tick, interval=GAP, first=2, chat_id=chat_id, name=str(chat_id)
    )


async def tick(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    session = SESSIONS.get(chat_id)
    if not session:
        context.job.schedule_removal()
        return

    if not session["queue"]:
        await context.bot.send_message(
            chat_id, "🏁 Quiz khatam!\n\n" + leaderboard(session["scores"])
        )
        SESSIONS.pop(chat_id, None)
        context.job.schedule_removal()
        return

    q = session["queue"].pop(0)
    msg = await context.bot.send_poll(
        chat_id,
        question=f"[{q['subject'].title()}] {q['question']}"[:300],
        options=q["options"],
        type="quiz",
        correct_option_id=q["answer"],
        explanation=q.get("explanation", "")[:200] or None,
        is_anonymous=False,
        open_period=GAP - 2,
    )
    POLLS[msg.poll.id] = (chat_id, q["answer"])


async def on_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.poll_answer
    info = POLLS.get(ans.poll_id)
    if not info:
        return
    chat_id, correct = info
    session = SESSIONS.get(chat_id)
    if not session:
        return
    user = ans.user
    entry = session["scores"].setdefault(user.id, [user.full_name, 0])
    if ans.option_ids and ans.option_ids[0] == correct:
        entry[1] += 1


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SESSIONS.get(update.effective_chat.id)
    if not session:
        await update.message.reply_text("Abhi koi quiz nahi chal raha.")
        return
    await update.message.reply_text("📊 Abhi tak:\n\n" + leaderboard(session["scores"]))


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = SESSIONS.pop(chat_id, None)
    for job in context.job_queue.get_jobs_by_name(str(chat_id)):
        job.schedule_removal()
    if session:
        await update.message.reply_text(
            "⛔ Quiz roka gaya.\n\n" + leaderboard(session["scores"])
        )
    else:
        await update.message.reply_text("Koi quiz chal hi nahi raha.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NEET/JEE Quiz Bot 🎯\n\n"
        "/quiz — 10 random questions\n"
        "/quiz physics 5 — subject + count\n"
        "/score — current leaderboard\n"
        "/stop — quiz rokna\n\n"
        "Subjects: physics, chemistry, maths, biology"
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(PollAnswerHandler(on_answer))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
