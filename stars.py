# -*- coding: utf-8 -*-
"""
Single Unified Telegram Bot Script
Runs both Main Bot and Payment Receiver Bot concurrently.
"""

import logging
import asyncio
from typing import Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    LabeledPrice
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters
)
from motor.motor_asyncio import AsyncIOMotorClient

# ==================== CONFIGURATION ====================
MAIN_BOT_TOKEN = "8968775484:AAE0QzNvQcXeVei8f6LGaGCXbiq_k7WhaCw"
PAYMENT_BOT_TOKEN = "8935465779:AAHCiegWcNpLiqSX3bbEMfYSRAl9P8UFagg"
ADMIN_ID = 938899359
MONGO_URL = "mongodb+srv://aaravkeshav92_db_user:VYpt1A4TTJvWJynJ@cluster0.3h5mg56.mongodb.net/?appName=Cluster0"
DB_NAME = "telegram_unified_bot"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB Setup
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client[DB_NAME]
users_col = db["users"]
config_col = db["config"]
videos_col = db["videos"]
admins_col = db["admins"]


# ==================== COMMON HELPERS ====================
async def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    admin_doc = await admins_col.find_one({"user_id": user_id})
    return bool(admin_doc)

async def get_config() -> Dict[str, Any]:
    config = await config_col.find_one({"_id": "settings"})
    if not config:
        config = {
            "_id": "settings",
            "payment_bot_username": "PaymentBotUsername",
            "ref_rewards": {"2": 5, "5": 10, "10": 20},
            "packages": {
                "1": {"stars": 50, "videos": "6", "link": "https://t.me/+example_1"},
                "2": {"stars": 100, "videos": "14", "link": "https://t.me/+example_2"},
                "3": {"stars": 200, "videos": "31", "link": "https://t.me/+example_3"},
                "4": {"stars": 500, "videos": "179", "link": "https://t.me/+example_4"},
                "5": {"stars": 1000, "videos": "349", "link": "https://t.me/+example_5"},
                "6": {"stars": 5000, "videos": "1.5k", "link": "https://t.me/+example_6"},
                "7": {"stars": 10000, "videos": "5k", "link": "https://t.me/+example_7"}
            }
        }
        await config_col.insert_one(config)
    return config

def get_rank_info(ref_count: int) -> tuple[str, int]:
    if ref_count < 2: return "Bronze (0/2)", 2
    elif ref_count < 5: return "Silver (0/5)", 5
    elif ref_count < 10: return "Gold (0/10)", 10
    elif ref_count < 25: return "Diamond (0/25)", 25
    elif ref_count < 50: return "Crystal (0/50)", 50
    elif ref_count < 100: return "Champion (0/100)", 100
    else: return "Legend", 200

def build_main_menu_keyboard(ref_count: int, is_user_admin: bool) -> InlineKeyboardMarkup:
    rank_title, _ = get_rank_info(ref_count)
    
    keyboard = [
        [InlineKeyboardButton(f"🖥️ INVITE FRIENDS | Next: 🥈 {rank_title}", callback_data="menu_link")],
        [InlineKeyboardButton(f"❤️ My Referral Progress ({ref_count})", callback_data="menu_referral")],
        [InlineKeyboardButton("⭐ 50 Stars = 6 Videos", callback_data="buy_pkg_1")],
        [InlineKeyboardButton("⭐ 100 Stars = 14 Videos", callback_data="buy_pkg_2")],
        [InlineKeyboardButton("⭐ 200 Stars = 31 Videos", callback_data="buy_pkg_3")],
        [InlineKeyboardButton("⭐ 500 Stars = 179 Videos", callback_data="buy_pkg_4")],
        [InlineKeyboardButton("⭐ 1k Stars = 349 Videos", callback_data="buy_pkg_5")],
        [InlineKeyboardButton("⭐ 5k Stars = 1.5k Videos", callback_data="buy_pkg_6")],
        [InlineKeyboardButton("⭐ 10k Stars = 5k Videos", callback_data="buy_pkg_7")],
        [InlineKeyboardButton("📊 Referral Leaderboard", callback_data="menu_leaderboard")]
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("🛠️ Admin Control Panel", callback_data="menu_admin")])
        
    return InlineKeyboardMarkup(keyboard)


# ==================== MAIN BOT HANDLERS ====================
async def start_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    args = context.args

    existing_user = await users_col.find_one({"user_id": user_id})

    if not existing_user:
        referrer_id = None
        if args and args[0].isdigit():
            possible_ref = int(args[0])
            if possible_ref != user_id:
                referrer_id = possible_ref

        new_user = {
            "user_id": user_id,
            "first_name": user.first_name,
            "username": user.username,
            "referrals": 0,
            "referred_by": referrer_id,
            "claimed_milestones": []
        }
        await users_col.insert_one(new_user)

        if referrer_id:
            await users_col.update_one({"user_id": referrer_id}, {"$inc": {"referrals": 1}})
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 <b>New Referral!</b> User {user.first_name} joined using your link!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # 🔔 New User Joined Admin Alert
        notify_msg = (
            f"🔔 <b>New User Joined Bot!</b>\n\n"
            f"👤 <b>Name:</b> {user.first_name}\n"
            f"🏷️ <b>Username:</b> @{user.username if user.username else 'N/A'}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>Referred By:</b> <code>{referrer_id if referrer_id else 'Direct'}</code>"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=notify_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    user_data = await users_col.find_one({"user_id": user_id})
    ref_count = user_data.get("referrals", 0) if user_data else 0
    user_is_admin = await is_admin(user_id)

    welcome_text = (
        "❤️ <b>Welcome to the Premium Video Club!</b> 👋\n\n"
        "🔥 <b>Invite friends and earn FREE premium videos!</b>\n\n"
        "⭐ <b>Start inviting and unlock your rewards!</b> ⭐"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=build_main_menu_keyboard(ref_count, user_is_admin),
        parse_mode="HTML"
    )

async def menu_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    text = f"🔗 <b>Your Referral Link:</b>\n\n<code>{ref_link}</code>\n\nShare this link to earn free rewards!"
    keyboard = [[InlineKeyboardButton("🗑️ Close", callback_data="menu_home")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def menu_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_referral_dashboard(update.effective_user.id, update.message.reply_text)

async def show_referral_dashboard(user_id: int, send_func):
    user = await users_col.find_one({"user_id": user_id})
    config = await get_config()
    
    refs = user.get("referrals", 0) if user else 0
    claimed = user.get("claimed_milestones", []) if user else []
    ref_rewards = config.get("ref_rewards", {})

    text = (
        f"🏆 <b>Referral Progress Dashboard</b>\n\n"
        f"👥 Total Invites: <b>{refs}</b>\n\n"
        f"<b>Milestones & Rewards:</b>\n"
    )
    keyboard = []

    for req_invites, vid_count in sorted(ref_rewards.items(), key=lambda x: int(x[0])):
        req_int = int(req_invites)
        if req_invites in claimed:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — ✅ Claimed\n"
        elif refs >= req_int:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — 🎁 READY TO CLAIM\n"
            keyboard.append([InlineKeyboardButton(f"🎁 Claim {vid_count} Videos ({req_invites} Invites)", callback_data=f"claim_ref_{req_invites}")])
        else:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — 🔒 Need {req_int - refs} more\n"

    keyboard.append([InlineKeyboardButton("🗑️ Close", callback_data="menu_home")])
    await send_func(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def main_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_home":
        await query.message.delete()

    elif data == "menu_link":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        user = await users_col.find_one({"user_id": user_id})
        ref_count = user.get("referrals", 0) if user else 0
        rank_title, _ = get_rank_info(ref_count)

        text = (
            f"🔗 <b>Your Referral Link:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 <b>Next:</b> 🥈 {rank_title} — {ref_count} invites\n\n"
            f"Share this link and earn FREE videos when friends join! 🎁"
        )
        keyboard = [[InlineKeyboardButton("🗑️ Close", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_referral":
        await show_referral_dashboard(user_id, query.message.reply_text)

    elif data.startswith("claim_ref_"):
        req_invites = data.split("_")[2]
        user = await users_col.find_one({"user_id": user_id})
        config = await get_config()

        refs = user.get("referrals", 0)
        claimed = user.get("claimed_milestones", [])
        ref_rewards = config.get("ref_rewards", {})
        vid_count = ref_rewards.get(req_invites, 0)

        if refs < int(req_invites):
            return await query.answer("❌ Insufficient invites!", show_alert=True)
        if req_invites in claimed:
            return await query.answer("⚠️ Already claimed!", show_alert=True)

        await users_col.update_one({"user_id": user_id}, {"$push": {"claimed_milestones": req_invites}})
        await query.answer("🎉 Reward Claimed!", show_alert=True)
        await query.message.reply_text(f"🎉 Sending <b>{vid_count} Videos</b> now...", parse_mode="HTML")

        videos = await videos_col.find().limit(vid_count).to_list(length=vid_count)
        for vid in videos:
            try:
                await context.bot.send_video(chat_id=user_id, video=vid["file_id"])
                await asyncio.sleep(0.5)
            except Exception:
                pass

    elif data.startswith("buy_pkg_"):
        pkg_id = data.split("_")[2]
        config = await get_config()
        pkg = config["packages"].get(pkg_id)
        pay_bot = config.get("payment_bot_username", "PaymentBot")

        if not pkg: return

        stars = pkg["stars"]
        videos = pkg["videos"]

        msg_text = (
            f"📦 <b>{videos} Media Pack</b>\n\n"
            f"Get {videos} exclusive media items instantly!\n\n"
            f"💰 <b>Price:</b> {stars} Stars ⭐\n\n"
            f"🔗 Click the button below to complete payment securely via our Payment Bot."
        )
        pay_link = f"https://t.me/{pay_bot}?start=pkg_{pkg_id}"
        keyboard = [
            [InlineKeyboardButton(f"💳 Pay {stars} Stars via Payment Bot", url=pay_link)],
            [InlineKeyboardButton("❌ Cancel", callback_data="menu_home")]
        ]
        await query.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_admin":
        if not await is_admin(user_id): return
        total_users = await users_col.count_documents({})
        total_vids = await videos_col.count_documents({})
        config = await get_config()

        text = (
            f"⚡ <b>SUPER ADMIN CONTROL PANEL</b> ⚡\n\n"
            f"👥 Total Users: <b>{total_users}</b>\n"
            f"🎬 Total Videos: <b>{total_vids}</b>\n"
            f"🤖 Linked Payment Bot: <code>@{config.get('payment_bot_username')}</code>\n\n"
            f"<b>Admin Commands:</b>\n"
            f"• <code>/broadcast [msg]</code> - Broadcast message\n"
            f"• <code>/setpaybot [username]</code> - Set Payment Bot\n"
            f"• <code>/setpackage [ID] [Stars] [Videos] [Link]</code>\n"
            f"• <code>/setrefreward [Invites] [Videos]</code>\n"
            f"• <code>/addadmin [user_id]</code> | <code>/removeadmin [user_id]</code>\n"
            f"• <code>/addvid [Serial_No]</code> (Reply/Send with video)"
        )
        keyboard = [[InlineKeyboardButton("🗑️ Close Panel", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# Admin Commands
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    text_to_send = " ".join(context.args)
    if not text_to_send and not update.message.reply_to_message:
        return await update.message.reply_text("⚠️ Usage: `/broadcast [message]`", parse_mode="Markdown")

    status_msg = await update.message.reply_text("🚀 Broadcasting...")
    success, fail = 0, 0

    async for u in users_col.find({}):
        try:
            if update.message.reply_to_message:
                await context.bot.copy_message(chat_id=u["user_id"], from_chat_id=update.message.chat_id, message_id=update.message.reply_to_message.message_id)
            else:
                await context.bot.send_message(chat_id=u["user_id"], text=text_to_send, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.04)
        except Exception:
            fail += 1

    await status_msg.edit_text(f"✅ <b>Complete!</b>\nSuccessful: {success}\nFailed: {fail}", parse_mode="HTML")

async def set_paybot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    if not context.args: return await update.message.reply_text("⚠️ Usage: `/setpaybot BotUsername`", parse_mode="Markdown")
    bot_user = context.args[0].replace("@", "")
    await config_col.update_one({"_id": "settings"}, {"$set": {"payment_bot_username": bot_user}}, upsert=True)
    await update.message.reply_text(f"✅ Payment bot updated to @{bot_user}")

async def set_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    if len(context.args) < 4: return await update.message.reply_text("⚠️ Usage: `/setpackage [ID] [Stars] [Videos] [Link]`", parse_mode="Markdown")
    
    pkg_id, stars, vids, link = context.args[0], int(context.args[1]), context.args[2], context.args[3]
    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"packages.{pkg_id}": {"stars": stars, "videos": vids, "link": link}}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Package {pkg_id} updated successfully!")

async def set_ref_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    if len(context.args) < 2: return await update.message.reply_text("⚠️ Usage: `/setrefreward [Invites] [Videos]`", parse_mode="Markdown")
    
    invites, vids = context.args[0], int(context.args[1])
    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"ref_rewards.{invites}": vids}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Milestone set: {invites} invites = {vids} videos!")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: return await update.message.reply_text("⚠️ Usage: `/addadmin [user_id]`", parse_mode="Markdown")
    
    new_admin = int(context.args[0])
    await admins_col.update_one({"user_id": new_admin}, {"$set": {"user_id": new_admin}}, upsert=True)
    await update.message.reply_text(f"✅ User {new_admin} added as Admin!")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    msg = update.message
    if not msg.video or not context.args:
        return await update.message.reply_text("⚠️ Send video with `/addvid [Serial_No]`", parse_mode="Markdown")
    
    serial = int(context.args[0])
    await videos_col.update_one(
        {"serial_no": serial},
        {"$set": {"file_id": msg.video.file_id}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Video #{serial} stored!")

async def post_init(application):
    commands = [
        BotCommand("start", "Welcome & referral rewards"),
        BotCommand("invite", "Get your referral link"),
        BotCommand("stats", "Your stats & tier progress")
    ]
    await application.bot.set_my_commands(commands)


# ==================== PAYMENT BOT HANDLERS ====================
async def start_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    
    if args and args[0].startswith("pkg_"):
        pkg_id = args[0].split("_")[1]
        
        config = await config_col.find_one({"_id": "settings"})
        pkg = config["packages"].get(pkg_id) if config else None
        
        if pkg:
            stars = pkg["stars"]
            videos = pkg["videos"]
            
            title = f"📦 {videos} Media Pack"
            description = f"Get {videos} exclusive media items instantly! — Pay with the button below 👇👇"
            payload = f"stars_payload_pkg_{pkg_id}_{update.effective_user.id}"
            prices = [LabeledPrice("Telegram Stars", stars)]
            
            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=title,
                description=description,
                payload=payload,
                provider_token="",  # Blank for Telegram Stars (XTR)
                currency="XTR",
                prices=prices
            )
            return

    await update.message.reply_text("👋 Payment Receiver Bot for Vidmatrixbot.")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    if "stars_payload_pkg_" in payload:
        pkg_id = payload.split("_")[3]
        
        config = await config_col.find_one({"_id": "settings"})
        pkg = config["packages"].get(pkg_id) if config else None
        
        channel_link = pkg.get("link", "https://t.me/your_channel") if pkg else "https://t.me/your_channel"
        
        text = (
            "🎉 <b>Thanks for purchasing our content!</b>\n\n"
            "Join this channel for content using the button below 👇"
        )
        keyboard = [[InlineKeyboardButton("🚀 Join Channel Now", url=channel_link)]]
        
        await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="HTML"
        )


# ==================== MAIN CONCURRENT RUNNER ====================
async def main():
    # 1. Build Main Bot Application
    app_main = ApplicationBuilder().token(MAIN_BOT_TOKEN).post_init(post_init).build()
    app_main.add_handler(CommandHandler("start", start_main))
    app_main.add_handler(CommandHandler("invite", menu_link_command))
    app_main.add_handler(CommandHandler("stats", menu_referral_command))
    app_main.add_handler(CommandHandler("broadcast", broadcast_command))
    app_main.add_handler(CommandHandler("setpaybot", set_paybot))
    app_main.add_handler(CommandHandler("setpackage", set_package))
    app_main.add_handler(CommandHandler("setrefreward", set_ref_reward))
    app_main.add_handler(CommandHandler("addadmin", add_admin))
    app_main.add_handler(CommandHandler("addvid", add_video))
    app_main.add_handler(CallbackQueryHandler(main_button_handler))

    # 2. Build Payment Bot Application
    app_pay = ApplicationBuilder().token(PAYMENT_BOT_TOKEN).build()
    app_pay.add_handler(CommandHandler("start", start_payment))
    app_pay.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_pay.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # 3. Start Both Bots Concurrently
    await app_main.initialize()
    await app_main.start()
    await app_main.updater.start_polling()

    await app_pay.initialize()
    await app_pay.start()
    await app_pay.updater.start_polling()

    logger.info("🚀 Both Main Bot and Payment Bot are now running concurrently!")

    # Keep async loop running
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app_main.updater.stop()
        await app_main.stop()
        await app_main.shutdown()

        await app_pay.updater.stop()
        await app_pay.stop()
        await app_pay.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
