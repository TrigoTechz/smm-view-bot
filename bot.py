import telebot
import re
import requests
import time
import os
import threading
from flask import Flask
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from functions import insertUser, track_exists, addBalance, cutBalance, getData, addRefCount, isExists, setWelcomeStaus, setReferredStatus

# --- RENDER WEB SERVER SETUP ---
# Render requires a web server to stay active on the free tier
app = Flask('')

@app.route('/')
def home():
    return "Bot is running and healthy!"

def run_web_server():
    # Render automatically provides a PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT CONFIGURATION ---
# We use os.environ.get to pull keys from Render's Environment Settings
bot_token = os.environ.get("BOT_TOKEN") 
SmmPanelApi = os.environ.get("SMM_API_KEY")

bot = telebot.TeleBot(bot_token)
admin_user_id = 5413540878
welcome_bonus = 100
ref_bonus = 200
min_view = 100
max_view = 30000
required_channels = ['@viewsindi']  
payment_channel = "@viewsindi"

# --- HELPER FUNCTIONS ---

def is_member_of_channel(user_id):
    for channel in required_channels:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

# --- MESSAGE HANDLERS ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    ref_by = message.text.split()[1] if len(
        message.text.split()) > 1 and message.text.split()[1].isdigit() else None

    if ref_by and int(ref_by) != int(user_id) and track_exists(ref_by):
        if not isExists(user_id):
            initial_data = {
                "user_id": user_id,
                "balance": 0.00,
                "ref_by": ref_by,
                "referred": 0,
                "welcome_bonus": 0,
                "total_refs": 0,
            }
            insertUser(user_id, initial_data)
            addRefCount(ref_by)

    if not isExists(user_id):
        initial_data = {
            "user_id": user_id,
            "balance": 0.00,
            "ref_by": "none",
            "referred": 0,
            "welcome_bonus": 0,
            "total_refs": 0,
        }
        insertUser(user_id, initial_data)

    if not is_member_of_channel(user_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        button1 = KeyboardButton("/start")
        markup.add(button1)
        bot.send_message(
            user_id,
            "You need to join the following channels before continuing:\n- @viewsindi",
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    userData = getData(user_id)
    wel = userData['welcome_bonus']
    if wel == 0:
        bot.send_message(user_id, f"+{welcome_bonus} coins as welcome bonus.")
        addBalance(user_id, welcome_bonus)
        setWelcomeStaus(user_id)

    data = getData(user_id)
    refby = data['ref_by']
    referred = data['referred']
    if refby != "none" and referred == 0:
        bot.send_message(refby, f"you referred {first_name} +{ref_bonus}")
        addBalance(refby, ref_bonus)
        setReferredStatus(user_id)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = KeyboardButton("👁‍🗨 Order View")
    button2 = KeyboardButton("👤 My Account")
    button3 = KeyboardButton("💳 Pricing")
    button4 = KeyboardButton("🗣 Invite Friends")
    button5 = KeyboardButton("📜 Help")
    markup.add(button1)
    markup.add(button2, button3)
    markup.add(button4, button5)

    bot.reply_to(
        message,
        "With view booster bot there's just a few steps to increase the views of your Telegram posts.\n\n👇🏻 To continue choose an item",
        reply_markup=markup)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_id = message.chat.id
    bot_username = bot.get_me().username

    if message.text == "👤 My Account":
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        data = getData(user_id)
        total_refs = data['total_refs']
        balance = data['balance']
        msg = f"""<b><u>My Account</u></b>\n\n🆔 User id: {user_id}\n👤 Username: @{message.chat.username}\n🗣 Invited users: {total_refs}\n🔗 Referral link: {referral_link}\n\n👁‍🗨 Balance: <code>{balance}</code> Views"""
        bot.reply_to(message, msg, parse_mode='html')

    elif message.text == "🗣 Invite Friends":
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        bot.reply_to(
            message,
            f"<b>Referral link:</b> {referral_link}\n\n<b><u>Share it with friends and get {ref_bonus} coins for each referral</u></b>",
            parse_mode='html')

    elif message.text == "📜 Help":
        msg = f"<b><u>❓ Frequently Asked questions</u></b>\n\nMinimum order: {min_view}\nMaximum order: {max_view}\n\n🆘 Support: @A_with"
        bot.reply_to(message, msg, parse_mode="html")

    elif message.text == "💳 Pricing":
        msg = f"<b><u>💎 Pricing 💎</u></b>\n\nYour ID: <code>{user_id}</code>\nContact @A_with to buy views."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💲 Contact Support", url="https://t.me/A_with"))
        bot.reply_to(message, msg, parse_mode="html", reply_markup=markup)

    elif message.text == "👁‍🗨 Order View":
        data = getData(user_id)
        balance = data['balance']
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton("✘ Cancel"))
        msg = f"👉‍ Enter number of Views ({min_view}-{max_view})\n\n👁‍🗨️ Your balance: {balance}"
        bot.reply_to(message, msg, reply_markup=markup, parse_mode="html")
        bot.register_next_step_handler(message, view_amount)

def view_amount(message):
    user_id = message.from_user.id
    if message.text == "✘ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=main_markup())
        return

    amount = message.text
    if not amount.isdigit():
        bot.send_message(user_id, "📛 Invalid value. Enter numeric value.", reply_markup=main_markup())
        return
    
    data = getData(str(user_id))
    if int(amount) < min_view or float(amount) > float(data['balance']):
        bot.send_message(user_id, "❌ Invalid amount or insufficient balance.", reply_markup=main_markup())
        return

    bot.reply_to(message, "Enter Telegram post link now:")
    bot.register_next_step_handler(message, view_link, amount)

def is_valid_link(link):
    pattern = r'^https?://t\.me/[a-zA-Z0-9_]{5,}/\d+$'
    return re.match(pattern, link) is not None

def view_link(message, amount):
    user_id = message.from_user.id
    link = message.text
    if link == "✘ Cancel":
        bot.reply_to(message, "Operation canceled.", reply_markup=main_markup())
        return

    if not is_valid_link(link):
        bot.send_message(user_id, "❌ Invalid Telegram link.", reply_markup=main_markup())
        return

    try:
        response = requests.post(url="	https://n1panel.com/api/v2",
                                 data={
                                     'key': SmmPanelApi,
                                     'action': 'add',
                                     'service': '3183',
                                     'link': link,
                                     'quantity': amount
                                 })
        result = response.json()
        
        if result and 'order' in result:
            oid = result['order']
            cutBalance(user_id, float(amount))
            bot.send_message(user_id, f"✅ Order Submitted!\nID: {oid}", reply_markup=main_markup())
            bot.send_message(payment_channel, f"✅ New Order: {amount} views\nUser ID: {user_id}")
        else:
            bot.send_message(user_id, "❌ API Error. Try again later.")
    except Exception as e:
        bot.send_message(user_id, "❌ Something went wrong.")

def main_markup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("👁‍🗨 Order View"))
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("💳 Pricing"))
    markup.add(KeyboardButton("🗣 Invite Friends"), KeyboardButton("📜 Help"))
    return markup

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    # Start Web Server thread for Render
    threading.Thread(target=run_web_server, daemon=True).start()
    
    print("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

