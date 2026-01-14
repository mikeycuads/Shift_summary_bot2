
from flask import Flask
from threading import Thread
import re
import html
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

user_shift_data = {}
last_summary = {}

CREATOR_MAP = {
    "Aleksei Cuadra": "Crystal Anne VIP",
    "Gelyn": "Autumn Paid",
    "Jerecho": "Razz Free",
    "Kia Angelica": "Dan Paid",
    "Mark Andrean G. Fernandez": "Bri PAID",
    "Mark Fernandez": "Bri PAID",   
    "Cyrel San Juan": "Alanna PAID",
}

def usd_to_net(amount: float) -> float:
    return amount * 0.8

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Shift started Paste your sale logs one by one Type /done when finished")

# Message handler – splits multi-line messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_shift_data:
        user_shift_data[user_id] = []

    text = (update.message.text or update.message.caption or "").strip()
    if not text:
        return

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        user_shift_data[user_id].append(line)

# /done
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sender_name = update.effective_user.full_name or "Unknown"
    creator_name = CREATOR_MAP.get(sender_name, "ENTER CREATOR NAME")
    date = datetime.now().strftime("%m/%d/%Y")
    logs = user_shift_data.get(user_id, [])

    if not logs:
        await update.message.reply_text("No sales logs found Please paste your logs before using /done")
        return

    shift_time = "5PM to 1AM PST" if "Mark" in sender_name else "12AM to 8AM PST"

    tips = []
    ppvs = []
    gross_total = 0.0
    net_total = 0.0
    current_username = None

    for line in logs:
        # capture a standalone @username line
        user_match = re.search(r"@([A-Za-z0-9_]+)", line)
        if user_match and re.fullmatch(r"@([A-Za-z0-9_]+)", line):
            current_username = user_match.group(1)
            continue

        # $X TIP
        plain_tip = re.fullmatch(r"\$(\d+(?:\.\d{1,2})?)\s*TIP\b", line, re.IGNORECASE)
        if plain_tip:
            amount = float(plain_tip.group(1))
            if current_username:
                tips.append(f"${amount:.2f} TIP from <a href=\"https://onlyfans.com/{html.escape(current_username)}\">@{html.escape(current_username)}</a>")
                current_username = None
            else:
                tips.append(f"${amount:.2f} TIP")
            gross_total += amount
            net_total += usd_to_net(amount)
            continue

        # bare $X treated as PPV
        amt_only = re.fullmatch(r"\$(\d+(?:\.\d{1,2})?)", line)
        if amt_only:
            amount = float(amt_only.group(1))
            if current_username:
                ppvs.append(f"${amount:.2f} PPV from <a href=\"https://onlyfans.com/{html.escape(current_username)}\">@{html.escape(current_username)}</a>")
                current_username = None
            else:
                ppvs.append(f"${amount:.2f} PPV")
            gross_total += amount
            net_total += usd_to_net(amount)
            continue

        # $X TIP https://onlyfans.com/username
        tip_combo = re.search(r"\$(\d+(?:\.\d{1,2})?)\s*TIP\s*(https?://onlyfans\.com/[^?\s]+)", line, re.IGNORECASE)
        if tip_combo:
            amount = float(tip_combo.group(1))
            link = tip_combo.group(2)
            uname_m = re.search(r"onlyfans\.com/([^?\s]+)", link)
            if uname_m:
                uname = uname_m.group(1)
                tips.append(f"${amount:.2f} TIP from <a href=\"https://onlyfans.com/{html.escape(uname)}\">@{html.escape(uname)}</a>")
            else:
                tips.append(f"${amount:.2f} TIP")
            gross_total += amount
            net_total += usd_to_net(amount)
            continue

        # $X https://onlyfans.com/username
        ppv_combo = re.search(r"\$(\d+(?:\.\d{1,2})?)\s+(https?://onlyfans\.com/[^?\s]+)", line)
        if ppv_combo:
            amount = float(ppv_combo.group(1))
            link = ppv_combo.group(2)
            uname_m = re.search(r"onlyfans\.com/([^?\s]+)", link)
            if uname_m:
                uname = uname_m.group(1)
                ppvs.append(f"${amount:.2f} PPV from <a href=\"https://onlyfans.com/{html.escape(uname)}\">@{html.escape(uname)}</a>")
            else:
                ppvs.append(f"${amount:.2f} PPV")
            gross_total += amount
            net_total += usd_to_net(amount)
            continue

        # tip $X
        tip_line = re.search(r"tip\s*\$?(\d+(?:\.\d{1,2})?)", line, re.IGNORECASE)
        if tip_line:
            amount = float(tip_line.group(1))
            if current_username:
                tips.append(f"${amount:.2f} TIP from <a href=\"https://onlyfans.com/{html.escape(current_username)}\">@{html.escape(current_username)}</a>")
                current_username = None
            else:
                tips.append(f"${amount:.2f} TIP")
            gross_total += amount
            net_total += usd_to_net(amount)
            continue

        # if a line had @user and amount together, fall back:
        if user_match and current_username is None:
            current_username = user_match.group(1)

    tips_output = "\n".join(tips) if tips else "$0"
    ppvs_output = "\n".join(ppvs) if ppvs else "$0"

    # HTML parse mode avoids Telegram Markdown pitfalls
    summary = (
        f"Summary of Tips and VIPs for <b>{html.escape(sender_name)}</b>\n"
        f"{html.escape(date)}\n"
        f"{html.escape(shift_time)}\n"
        f"Shift 8 Hours\n"
        f"Creator {html.escape(creator_name)}\n\n"
        f"Tips\n{tips_output}\n\n"
        f"PPVs\n{ppvs_output}\n\n"
        f"———\n"
        f"<b>TOTAL GROSS SALE</b> ${gross_total:.2f}\n"
        f"<b>TOTAL NET SALE</b> ${net_total:.2f}\n"
        f"<b>TOTAL BONUS</b> $0"
    )

    last_summary[user_id] = gross_total
    await update.message.reply_text(summary, parse_mode="HTML")
    user_shift_data[user_id] = []

# /dayslip
async def dayslip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    gross = last_summary.get(user_id, 0.0)

    if gross == 0:
        await update.message.reply_text("No data available Please complete a /done shift first")
        return

    usd_to_php = 55
    net = gross * 0.8
    bonus = round(net * 0.05, 2)
    final = round(bonus + 32, 2)
    final_php = round(final * usd_to_php, 2)

    response = (
        f"TOTAL GROSS {gross:.2f} x 0.8 = {net:.2f}\n"
        f"{net:.2f} x 0.05 = {bonus:.2f}\n"
        f"{bonus:.2f} + 32 = {final:.2f}\n"
        f"———\n"
        f"<b>Your Salary Today is ${final:.2f} / ₱{final_php:,.2f}</b>"
    )
    await update.message.reply_text(response, parse_mode="HTML")

# Flask keep-alive
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running."

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    # replace with a fresh token from BotFather immediately
    BOT_TOKEN = "7638654177:AAEMk6WVuH7ePaDEIYCz68Y04_rqQDYnpdo"
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("dayslip", dayslip))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

    Thread(target=run_flask, daemon=True).start()
    print("Bot running...")
    app.run_polling()
