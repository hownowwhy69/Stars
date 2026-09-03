# -*- coding: utf-8 -*-
"""
Telegram Unified Bot (Referral + Stars Payment System + Multi-Admin + Notifications) - stars.py
Built with python-telegram-bot v21+ and Motor (MongoDB Async)
"""

import logging
import asyncio
from typing import Dict, Any, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    InputMediaVideo,
    InputMediaPhoto,
    InputMediaDocument
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

# ----------------- CONFIGURATION -----------------
BOT_TOKEN = "8968775484:AAE0QzNvQcXeVei8f6LGaGCXbiq_k7WhaCw"  # Apna Telegram Bot Token yahan dalein
ADMIN_ID = "938899359"            # Apna Telegram Numeric Owner/Admin ID yahan dalein
MONGO_URL = "mongodb+srv://aaravkeshav92_db_user:VYpt1A4TTJvWJynJ@cluster0.3h5mg56.mongodb.net/?appName=Cluster0"  # MongoDB URI
DB_NAME = "telegram_unified_bot"

# Enable logging for debugging and tracking
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Async MongoDB Client
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client[DB_NAME]
users_col = db["users"]
config_col = db["config"]
videos_col = db["videos"]
admins_col = db["admins"]  # Collection to store dynamic admin user IDs

# ----------------- INITIAL SETUP / HELPERS -----------------

async def is_admin(user_id: int) -> bool:
    """Checks if a user is the main owner or an added admin."""
    if user_id == ADMIN_ID:
        return True
    admin_doc = await admins_col.find_one({"user_id": user_id})
    return bool(admin_doc)

async def get_config() -> Dict[str, Any]:
    """Fetches configuration from database, creates default if not exists."""
    config = await config_col.find_one({"_id": "settings"})
    if not config:
        config = {
            "_id": "settings",
            "packages": {
                "1": {"stars": 50, "videos": 5, "link": "https://t.me/+example_channel_1"},
                "2": {"stars": 150, "videos": 20, "link": "https://t.me/+example_channel_2"},
                "3": {"stars": 300, "videos": 50, "link": "https://t.me/+example_channel_3"}
            },
            "button_counts": {"small": 5, "large": 10}
        }
        await config_col.insert_one(config)
    return config

async def get_user(user_id: int, user_name: str = "User") -> tuple[Dict[str, Any], bool]:
    """Fetches user document from DB or initializes a new user profile. Returns (user_doc, is_new)."""
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "referred_by": None,
            "referral_count": 0,
            "unlocked_videos": 0,
            "balance": 0,
            "name": user_name
        }
        await users_col.insert_one(user)
        return user, True
    return user, False

async def notify_all_admins(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Sends notification text to the main owner and all dynamic admins."""
    admin_ids = {ADMIN_ID}
    async for adm in admins_col.find({}):
        admin_ids.add(adm["user_id"])
    
    for adm_id in admin_ids:
        try:
            await context.bot.send_message(chat_id=adm_id, text=text)
        except Exception as e:
            logger.error(f"Failed to send notification to admin {adm_id}: {e}")

# ----------------- COMMAND HANDLERS: START & REFERRAL -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "User"
    args = context.args

    user, is_new = await get_user(user_id, user_name)

    # If new user, broadcast notification to owner/admins matching the requested format
    if is_new:
        total_users = await users_col.count_documents({})
        notif_text = f"🆕 New User!\nTotal: [{total_users}]\nName: {user_name}"
        await notify_all_admins(context, notif_text)

    # Referral Tracking Logic
    if args and not user.get("referred_by") and user["referral_count"] == 0:
        try:
            referrer_id = int(args[0])
            if referrer_id != user_id:
                referrer = await users_col.find_one({"user_id": referrer_id})
                if referrer:
                    # Set referrer for current user
                    await users_col.update_one(
                        {"user_id": user_id},
                        {"$set": {"referred_by": referrer_id}}
                    )
                    # Increment referrer count and unlock sequential video reward
                    new_ref_count = referrer.get("referral_count", 0) + 1
                    new_unlocked = referrer.get("unlocked_videos", 0) + 1
                    
                    await users_col.update_one(
                        {"user_id": referrer_id},
                        {"$set": {"referral_count": new_ref_count, "unlocked_videos": new_unlocked}}
                    )
                    
                    # Notify Referrer & Send Unlocked Video Automatically if available
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 Badhai ho! Aapke referral link se ek naye user ne join kiya hai.\n👥 Total Referrals: {new_ref_count}\n🎬 New video unlocked! Serial #{new_unlocked}"
                        )
                        vid_doc = await videos_col.find_one({"serial_no": new_unlocked})
                        if vid_doc:
                            f_id = vid_doc["file_id"]
                            f_type = vid_doc.get("file_type", "video")
                            if f_type == "document":
                                await context.bot.send_document(chat_id=referrer_id, document=f_id, caption=f"🎁 Referral Reward: Video #{new_unlocked}")
                            elif f_type == "photo":
                                await context.bot.send_photo(chat_id=referrer_id, photo=f_id, caption=f"🎁 Referral Reward: Video #{new_unlocked}")
                            else:
                                await context.bot.send_video(chat_id=referrer_id, video=f_id, caption=f"🎁 Referral Reward: Video #{new_unlocked}")
                    except Exception as e:
                        logger.error(f"Error rewarding referrer: {e}")
        except ValueError:
            pass

    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    keyboard = [
        [InlineKeyboardButton("🎁 Referral Status & Videos", callback_data="menu_referral")],
        [InlineKeyboardButton("⭐ Buy Premium via Telegram Stars", callback_data="menu_packages")],
        [InlineKeyboardButton("🔗 My Invite Link", callback_data="menu_link")]
    ]
    
    # Add Admin Panel button if the user is an admin or owner
    if await is_admin(user_id):
        keyboard.insert(0, [InlineKeyboardButton("🛠️ Admin Panel", callback_data="menu_admin")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"👋 <b>Welcome to the Unified Bot!</b>\n\n"
        f"• Doston ko invite karein aur free sequential videos automatically unlock karein.\n"
        f"• Ya fir Telegram Stars ke zariye instant premium packages purchase karke private channel access payein.\n\n"
        f"🔗 <b>Aapka Referral Link:</b>\n<code>{ref_link}</code>"
    )

    await query.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")

# ----------------- CALLBACK & MENU MANAGEMENT -----------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_admin":
        if not await is_admin(user_id):
            await query.answer("❌ Aap authorized admin nahi hain.", show_alert=True)
            return
        
        text = "🛠️ <b>Admin Control Panel</b>\n\nAap yahan se packages, videos manage kar sakte hain ya naye admins add kar sakte hain."
        keyboard = [
            [InlineKeyboardButton("📋 Admin Help / Commands", callback_data="admin_help")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "admin_help":
        if not await is_admin(user_id):
            return
        text = (
            "🛠️ <b>Admin Commands List:</b>\n\n"
            "• <code>/addadmin [user_id]</code> - Kisi user ko admin banayein\n"
            "• <code>/removeadmin [user_id]</code> - Admin rights hatayein\n"
            "• <code>/setpackage [ID] [Stars] [Videos] [Link]</code> - Package setup karein\n"
            "• <code>/setvideos [small/large] [count]</code> - Button count set karein\n"
            "• <code>/addvid [Serial_No]</code> (Media ke sath bhejein) - Video add karein"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="menu_admin")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_referral":
        user, _ = await get_user(user_id)
        refs = user.get("referral_count", 0)
        unlocked = user.get("unlocked_videos", 0)
        
        text = (
            f"📊 <b>Aapka Referral Dashboard</b>\n\n"
            f"👥 Total Referrals: <b>{refs}</b>\n"
            f"🎬 Unlocked Videos: <b>{unlocked}</b>\n\n"
            f"Har successful referral par aapko agla sequential video automatically mil jata hai!"
        )
        keyboard = [
            [InlineKeyboardButton("📂 View My Unlocked Videos", callback_data="view_my_videos")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "view_my_videos":
        user, _ = await get_user(user_id)
        unlocked = user.get("unlocked_videos", 0)
        if unlocked == 0:
            await query.answer("❌ Aapne abhi tak koi video unlock nahi ki hai. Doston ko invite karein!", show_alert=True)
            return
        
        await query.message.reply_text(f"📥 Aapke unlocked videos (1 se {unlocked} tak) bhej rahe hain...")
        cursor = videos_col.find({"serial_no": {"$lte": unlocked}}).sort("serial_no", 1)
        async for vid in cursor:
            try:
                f_id = vid["file_id"]
                f_type = vid.get("file_type", "video")
                s_no = vid["serial_no"]
                if f_type == "document":
                    await context.bot.send_document(chat_id=user_id, document=f_id, caption=f"🎬 Video #{s_no}")
                elif f_type == "photo":
                    await context.bot.send_photo(chat_id=user_id, photo=f_id, caption=f"🎬 Video #{s_no}")
                else:
                    await context.bot.send_video(chat_id=user_id, video=f_id, caption=f"🎬 Video #{s_no}")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error sending video #{vid.get('serial_no')}: {e}")

    elif data == "menu_packages":
        config = await get_config()
        packages = config.get("packages", {})
        
        keyboard = []
        for pkg_id, pkg_info in packages.items():
            btn_text = f"⭐ {pkg_info['stars']} Stars - {pkg_info['videos']} Videos"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_pkg_{pkg_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_home")])
        
        await query.edit_message_text(
            "⭐ <b>Available Premium Packages</b>\n\nNeeche diye gaye package ko select karein aur Telegram Stars ke zariye instant payment karein:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    elif data == "menu_link":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        text = f"🔗 <b>Aapka Unique Referral Link:</b>\n\n<code>{ref_link}</code>\n\nIse apne doston aur groups ke sath share karein!"
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_home":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        keyboard = [
            [InlineKeyboardButton("🎁 Referral Status & Videos", callback_data="menu_referral")],
            [InlineKeyboardButton("⭐ Buy Premium via Telegram Stars", callback_data="menu_packages")],
            [InlineKeyboardButton("🔗 My Invite Link", callback_data="menu_link")]
        ]
        if await is_admin(user_id):
            keyboard.insert(0, [InlineKeyboardButton("🛠️ Admin Panel", callback_data="menu_admin")])
            
        text = f"👋 <b>Main Menu</b>\n\nAapka Referral Link:\n<code>{ref_link}</code>"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("buy_pkg_"):
        pkg_id = data.split("_")[2]
        config = await get_config()
        pkg = config["packages"].get(pkg_id)
        
        if not pkg:
            await query.edit_message_text("❌ Package not found.")
            return

        title = f"Premium Package {pkg_id} ({pkg['videos']} Videos)"
        description = f"Instant access to exclusive content: {pkg['videos']} videos + private channel invite link."
        payload = f"stars_pkg_{pkg_id}_{user_id}"
        currency = "XTR"  # Native Telegram Stars currency code
        prices = [LabeledPrice("Telegram Stars", pkg["stars"])]

        await context.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Must be left empty string for Telegram Stars invoices
            currency=currency,
            prices=prices
        )

# ----------------- TELEGRAM STARS PAYMENT HANDLERS -----------------

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    user_id = update.message.from_user.id

    if payload.startswith("stars_pkg_"):
        parts = payload.split("_")
        pkg_id = parts[2]
        
        config = await get_config()
        pkg = config["packages"].get(pkg_id)
        
        if pkg:
            channel_link = pkg["link"]
            success_text = (
                f"✅ <b>Payment Successful!</b>\n\n"
                f"Aapne successfully Telegram Stars ke zariye package purchase kar liya hai.\n\n"
                f"📥 <b>Aapka Private Channel Invite Link:</b>\n{channel_link}"
            )
            await update.message.reply_text(success_text, parse_mode="HTML")
        else:
            await update.message.reply_text("✅ Payment successful, par package configuration nahi mili. Kripya admin se contact karein.")

# ----------------- ADMIN COMMAND HANDLERS -----------------

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Sirf main owner hi naye admin add kar sakta hai.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /addadmin [user_id]")
        return

    try:
        new_admin_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ User ID numeric honi chahiye.")
        return

    await admins_col.update_one(
        {"user_id": new_admin_id},
        {"$set": {"user_id": new_admin_id}},
        upsert=True
    )
    await update.message.reply_text(f"✅ User {new_admin_id} ko successfully admin bana diya gaya hai!")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Sirf main owner hi admin remove kar sakta hai.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /removeadmin [user_id]")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ User ID numeric honi chahiye.")
        return

    result = await admins_col.deleteOne({"user_id": target_id}) if hasattr(admins_col, "deleteOne") else await admins_col.delete_one({"user_id": target_id})
    await update.message.reply_text(f"✅ User {target_id} ke admin rights hata diye gaye hain!")

async def set_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Aap authorized admin nahi hain.")
        return

    args = context.args
    if len(args) < 4:
        await update.message.reply_text("⚠️ Usage: /setpackage [Pkg_ID] [Stars] [Videos] [Channel_Link]")
        return

    pkg_id = args[0]
    try:
        stars = int(args[1])
        videos = int(args[2])
        link = args[3]
    except ValueError:
        await update.message.reply_text("❌ Stars aur Videos ki value numeric honi chahiye.")
        return

    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"packages.{pkg_id}": {"stars": stars, "videos": videos, "link": link}}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Package {pkg_id} successfully update kar diya gaya hai!")

async def set_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Aap authorized admin nahi hain.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Usage: /setvideos [small/large] [count]")
        return

    size_type = args[0].lower()
    try:
        count = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Count numeric hona chahiye.")
        return

    if size_type not in ["small", "large"]:
        await update.message.reply_text("❌ Type sirf 'small' ya 'large' ho sakta hai.")
        return

    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"button_counts.{size_type}": count}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Button count for {size_type} updated to {count}!")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Aap authorized admin nahi hain.")
        return

    message = update.message
    if not message.video and not message.document and not message.photo:
        await update.message.reply_text("⚠️ Kripya media file (video/document/photo) ke sath command bhejein:\n/addvid [Serial_No]")
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /addvid [Serial_No]")
        return

    try:
        serial_no = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Count numeric hona chahiye.")
        return

    if size_type not in ["small", "large"]:
        await update.message.reply_text("❌ Type sirf 'small' ya 'large' ho sakta hai.")
        return

    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"button_counts.{size_type}": count}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Button count for {size_type} updated to {count}!")

async def add_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ Aap authorized admin nahi hain.")
        return

    message = update.message
    if not message.video and not message.document and not message.photo:
        await update.message.reply_text("⚠️ Kripya media file (video/document/photo) ke sath command bhejein:\n/addvid [Serial_No]")
        return

    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /addvid [Serial_No]")
        return

    try:
        serial_no = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Serial number numeric hona chahiye.")
        return

    file_id = None
    file_type = "video"
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"

    await videos_col.update_one(
        {"serial_no": serial_no},
        {"$set": {"file_id": file_id, "file_type": file_type}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Video with serial #{serial_no} successfully database mein store ho gayi hai!")

# ----------------- MAIN ENTRYPOINT -----------------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("setpackage", set_package))
    app.add_handler(CommandHandler("setvideos", set_videos))
    app.add_handler(CommandHandler("addvid", add_video))
    
    # Callback Query Handler for Menus & Buttons
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Telegram Stars Payment Handlers
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    logger.info("Bot is starting and polling for updates...")
    app.run_polling()

if __name__ == "__main__":
    main()
