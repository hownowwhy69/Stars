# -*- coding: utf-8 -*-
"""
Unified Telegram Bot Script (stars.py)
Updated with:
- Smart 'Back to Main Menu' navigation (No delete)
- Clean button UI without extra color boxes (🟥, 🟦, 🟪)
- Custom format_k() helper for displaying 1k, 5k, 10k on buttons
- Exact numeric star values passed to Payment Gateway
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

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database Setup
db_client = AsyncIOMotorClient(config.MONGO_URL)
db = db_client[config.DB_NAME]
users_col = db["users"]
config_col = db["config"]
videos_col = db["videos"]
admins_col = db["admins"]

WELCOME_TEXT = (
    "❤️ <b>Welcome to the Premium Video Club!</b> 👋\n\n"
    "🔥 <b>Invite friends and earn FREE premium videos!</b>\n\n"
    "👥 <b>Referral Rewards:</b>\n"
    "└ 🥉 <b>2 invites</b> = 5 free videos\n"
    "└ 🥈 <b>5 invites</b> = 15 free videos\n"
    "└ 🥇 <b>10 invites</b> = 30 free videos\n"
    "└ 💎 <b>25 invites</b> = 100 free videos\n"
    "└ 🔷 <b>50 invites</b> = 250 free videos\n"
    "└ 👑 <b>100 invites</b> = 600 free videos\n"
    "└ 🔥 <b>200 invites</b> = 1400 free videos\n\n"
    "⭐ <b>Start inviting and unlock your rewards!</b> ⭐"
)

# ==================== HELPERS ====================
def format_k(num) -> str:
    """Buttons par 1000 -> 1k, 5000 -> 5k, 10000 -> 10k dikhane ke liye helper"""
    try:
        val = int(num)
        if val >= 1000:
            return f"{val // 1000}k" if val % 1000 == 0 else f"{val / 1000}k"
        return str(val)
    except (ValueError, TypeError):
        return str(num)

async def is_admin(user_id: int) -> bool:
    if user_id == config.ADMIN_ID:
        return True
    admin_doc = await admins_col.find_one({"user_id": user_id})
    return bool(admin_doc)

async def get_config() -> Dict[str, Any]:
    db_settings = await config_col.find_one({"_id": "settings"})
    
    if not db_settings:
        settings_data = {
            "_id": "settings",
            "payment_bot_username": "PaymentBotUsername",
            "ref_rewards": config.REF_REWARDS,
            "packages": config.PACKAGES
        }
        await config_col.insert_one(settings_data)
        return settings_data
    else:
        await config_col.update_one(
            {"_id": "settings"},
            {"$set": {"packages": config.PACKAGES, "ref_rewards": config.REF_REWARDS}}
        )
        db_settings["packages"] = config.PACKAGES
        db_settings["ref_rewards"] = config.REF_REWARDS
        return db_settings

def get_rank_info(ref_count: int) -> tuple[str, int]:
    if ref_count < 2: return "Bronze (0/2)", 2
    elif ref_count < 5: return "Silver (0/5)", 5
    elif ref_count < 10: return "Gold (0/10)", 10
    elif ref_count < 25: return "Diamond (0/25)", 25
    elif ref_count < 50: return "Crystal (0/50)", 50
    elif ref_count < 100: return "Champion (0/100)", 100
    else: return "Legend", 200

def build_main_menu_keyboard(ref_count: int, is_user_admin: bool, pkgs: dict) -> InlineKeyboardMarkup:
    rank_title, _ = get_rank_info(ref_count)
    
    keyboard = [
        # Clean INVITE FRIENDS Button
        [InlineKeyboardButton(f"👥 INVITE FRIENDS | Next: 🥈 {rank_title}", callback_data="menu_link")],
        
        # Clean My Referral Progress Button
        [InlineKeyboardButton(f"❤️ My Referral Progress ({ref_count})", callback_data="menu_referral")],
        
        # Star Packages with format_k (1k, 5k, 10k formatting for display)
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['1']['stars'])} Stars = {pkgs['1']['videos']} Videos", callback_data="buy_pkg_1")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['2']['stars'])} Stars = {pkgs['2']['videos']} Videos", callback_data="buy_pkg_2")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['3']['stars'])} Stars = {pkgs['3']['videos']} Videos", callback_data="buy_pkg_3")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['4']['stars'])} Stars = {pkgs['4']['videos']} Videos", callback_data="buy_pkg_4")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['5']['stars'])} Stars = {pkgs['5']['videos']} Videos", callback_data="buy_pkg_5")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['6']['stars'])} Stars = {pkgs['6']['videos']} Videos", callback_data="buy_pkg_6")],
        [InlineKeyboardButton(f"⭐ {format_k(pkgs['7']['stars'])} Stars = {pkgs['7']['videos']} Videos 💎", callback_data="buy_pkg_7")],
        
        [InlineKeyboardButton("📊 Referral Leaderboard", callback_data="menu_leaderboard")]
    ]
    if is_user_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Control Panel", callback_data="menu_admin")])
        
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
            "claimed_milestones": [],
            "sent_videos": []
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

        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"🔔 <b>New User Joined:</b> {user.first_name} (<code>{user_id}</code>)",
                parse_mode="HTML"
            )
        except Exception:
            pass

    user_data = await users_col.find_one({"user_id": user_id})
    ref_count = user_data.get("referrals", 0) if user_data else 0
    user_is_admin = await is_admin(user_id)
    cfg = await get_config()

    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=build_main_menu_keyboard(ref_count, user_is_admin, cfg["packages"]),
        parse_mode="HTML"
    )

async def menu_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    text = f"🔗 <b>Your Referral Link:</b>\n\n<code>{ref_link}</code>\n\nShare this link to earn free rewards!"
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def menu_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_referral_dashboard(update, context, edit_existing=False)

async def render_referral_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, edit_existing: bool = True):
    user_id = update.effective_user.id
    user = await users_col.find_one({"user_id": user_id})
    cfg = await get_config()
    
    refs = user.get("referrals", 0) if user else 0
    claimed = user.get("claimed_milestones", []) if user else []
    ref_rewards = cfg.get("ref_rewards", config.REF_REWARDS)

    text = f"🏆 <b>Referral Progress Dashboard</b>\n\n👥 Total Invites: <b>{refs}</b>\n\n<b>Milestones & Video Rewards:</b>\n"
    keyboard = []

    for req_invites, vid_count in sorted(ref_rewards.items(), key=lambda x: int(x[0])):
        req_int = int(req_invites)
        if str(req_invites) in claimed:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — ✅ Claimed\n"
        elif refs >= req_int:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — 🎁 <b>READY TO CLAIM</b>\n"
            keyboard.append([InlineKeyboardButton(f"🎁 Claim {vid_count} Videos ({req_invites} Invites)", callback_data=f"claim_ref_{req_invites}")])
        else:
            text += f"• <b>{req_invites} Invites:</b> {vid_count} Videos — 🔒 Need {req_int - refs} more\n"

    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")])
    markup = InlineKeyboardMarkup(keyboard)

    if edit_existing and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=markup, parse_mode="HTML")

async def main_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_home":
        user = await users_col.find_one({"user_id": user_id})
        ref_count = user.get("referrals", 0) if user else 0
        user_is_admin = await is_admin(user_id)
        cfg = await get_config()

        await query.edit_message_text(
            WELCOME_TEXT,
            reply_markup=build_main_menu_keyboard(ref_count, user_is_admin, cfg["packages"]),
            parse_mode="HTML"
        )

    elif data == "menu_link":
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        user = await users_col.find_one({"user_id": user_id})
        ref_count = user.get("referrals", 0) if user else 0
        rank_title, _ = get_rank_info(ref_count)

        text = f"🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>\n\n📊 <b>Next:</b> 🥈 {rank_title} — {ref_count} invites\n\nShare this link to earn free videos! 🎁"
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_referral":
        await render_referral_dashboard(update, context, edit_existing=True)

    elif data == "menu_leaderboard":
        top_users = await users_col.find().sort("referrals", -1).limit(10).to_list(length=10)
        text = "📊 <b>Top Referral Leaderboard</b>\n\n"
        for idx, u in enumerate(top_users, start=1):
            text += f"{idx}. <b>{u.get('first_name', 'User')}</b> — {u.get('referrals', 0)} Invites\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("claim_ref_"):
        req_invites = data.split("_")[2]
        user = await users_col.find_one({"user_id": user_id})
        cfg = await get_config()

        refs = user.get("referrals", 0)
        claimed = user.get("claimed_milestones", [])
        already_sent = user.get("sent_videos", [])
        
        ref_rewards = cfg.get("ref_rewards", {})
        vid_count = ref_rewards.get(req_invites, 0)

        if refs < int(req_invites): return await query.answer("❌ Insufficient invites!", show_alert=True)
        if str(req_invites) in claimed: return await query.answer("⚠️ Already claimed!", show_alert=True)

        available_videos = await videos_col.find(
            {"file_id": {"$nin": already_sent}}
        ).limit(vid_count).to_list(length=vid_count)

        if not available_videos:
            await query.message.reply_text("❌ No new videos available in pool! Admin will upload more soon.")
            return

        await users_col.update_one({"user_id": user_id}, {"$push": {"claimed_milestones": str(req_invites)}})
        await query.answer("🎉 Reward Claimed!", show_alert=True)
        await query.message.reply_text(f"🎉 Sending <b>{len(available_videos)} Unique Videos</b> now...", parse_mode="HTML")

        sent_file_ids = []
        for vid in available_videos:
            try:
                await context.bot.send_video(chat_id=user_id, video=vid["file_id"])
                sent_file_ids.append(vid["file_id"])
                await asyncio.sleep(0.4)
            except Exception as e:
                logger.error(f"Error sending video: {e}")

        if sent_file_ids:
            await users_col.update_one(
                {"user_id": user_id},
                {"$addToSet": {"sent_videos": {"$each": sent_file_ids}}}
            )

    elif data.startswith("buy_pkg_"):
        pkg_id = data.split("_")[2]
        cfg = await get_config()
        pkg = cfg["packages"].get(pkg_id)
        pay_bot = cfg.get("payment_bot_username", "PaymentBot")

        if not pkg: return

        stars, videos = pkg["stars"], pkg["videos"]
        msg_text = (
            f"📦 <b>{videos} Media Pack</b>\n\n"
            f"Get {videos} exclusive media items instantly!\n\n"
            f"💰 <b>Price:</b> {stars} Stars ⭐\n\n"
            f"🔗 Click below to pay securely via Payment Bot."
        )
        pay_link = f"https://t.me/{pay_bot}?start=pkg_{pkg_id}"
        keyboard = [
            [InlineKeyboardButton(f"💳 Pay {stars} Stars via Payment Bot", url=pay_link)],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")]
        ]
        await query.edit_message_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "menu_admin":
        if not await is_admin(user_id): return
        total_users = await users_col.count_documents({})
        total_vids = await videos_col.count_documents({})
        cfg = await get_config()

        text = (
            f"⚡ <b>SUPER ADMIN CONTROL PANEL</b> ⚡\n\n"
            f"👥 Total Users: <b>{total_users}</b>\n"
            f"🎬 Total Videos in Pool: <b>{total_vids}</b>\n"
            f"🤖 Linked Payment Bot: <code>@{cfg.get('payment_bot_username')}</code>\n\n"
            f"<b>Upload Videos:</b>\n"
            f"• Send or forward video with caption <code>/addvid</code>\n\n"
            f"<b>Commands:</b>\n"
            f"• <code>/setlink [Pkg_ID] [Link]</code> - Set Package Link\n"
            f"• <code>/broadcast [msg]</code> - Broadcast Message\n"
            f"• <code>/setpaybot [username]</code> - Set Payment Bot\n"
            f"• <code>/addadmin [user_id]</code> - Add New Admin"
        )
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==================== ADMIN COMMANDS ====================
async def add_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    msg = update.message
    
    video = msg.video or (msg.reply_to_message.video if msg.reply_to_message else None)
    if not video:
        return await update.message.reply_text("⚠️ Send or reply to a Video with <code>/addvid</code>", parse_mode="HTML")

    file_id = video.file_id
    existing = await videos_col.find_one({"file_id": file_id})
    if existing:
        return await update.message.reply_text("⚠️ Video already exists in pool!")

    await videos_col.insert_one({"file_id": file_id})
    total = await videos_col.count_documents({})
    await update.message.reply_text(f"✅ Video added! Total in pool: <b>{total}</b>", parse_mode="HTML")

async def set_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.message.from_user.id): return
    if len(context.args) < 2: 
        return await update.message.reply_text("⚠️ Usage: `/setlink [Pkg_ID (1-7)] [Channel_Link]`", parse_mode="Markdown")
    
    pkg_id, link = context.args[0], context.args[1]
    await config_col.update_one(
        {"_id": "settings"},
        {"$set": {f"packages.{pkg_id}.link": link}},
        upsert=True
    )
    await update.message.reply_text(f"✅ Package {pkg_id} link updated to:\n`{link}`", parse_mode="Markdown")

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

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != config.ADMIN_ID: return
    if not context.args: return await update.message.reply_text("⚠️ Usage: `/addadmin [user_id]`", parse_mode="Markdown")
    
    new_admin = int(context.args[0])
    await admins_col.update_one({"user_id": new_admin}, {"$set": {"user_id": new_admin}}, upsert=True)
    await update.message.reply_text(f"✅ User {new_admin} added as Admin!")

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
        cfg = await get_config()
        pkg = cfg["packages"].get(pkg_id)
        
        if pkg:
            # Passes exact integer star amount (e.g., 1000, 5000, 10000) to Telegram Invoice
            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=f"📦 {pkg['videos']} Media Pack",
                description=f"Get {pkg['videos']} exclusive videos instantly!",
                payload=f"stars_payload_pkg_{pkg_id}_{update.effective_user.id}",
                provider_token="",  # Telegram Stars (XTR)
                currency="XTR",
                prices=[LabeledPrice("Telegram Stars", int(pkg["stars"]))]
            )
            return

    await update.message.reply_text("👋 Payment Receiver Bot.")

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    if "stars_payload_pkg_" in payload:
        pkg_id = payload.split("_")[3]
        cfg = await get_config()
        pkg = cfg["packages"].get(pkg_id, {})
        channel_link = pkg.get("link", "https://t.me/your_channel")
        
        text = "🎉 <b>Thanks for purchasing!</b>\n\nJoin the channel using the button below 👇"
        keyboard = [[InlineKeyboardButton("🚀 Join Channel Now", url=channel_link)]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


# ==================== MAIN RUNNER ====================
async def main():
    app_main = ApplicationBuilder().token(config.MAIN_BOT_TOKEN).post_init(post_init).build()
    
    # User Commands
    app_main.add_handler(CommandHandler("start", start_main))
    app_main.add_handler(CommandHandler("invite", menu_link_command))
    app_main.add_handler(CommandHandler("stats", menu_referral_command))
    
    # Admin Commands
    app_main.add_handler(CommandHandler("addvid", add_video_handler))
    app_main.add_handler(MessageHandler(filters.VIDEO & filters.CaptionRegex(r"^/addvid"), add_video_handler))
    app_main.add_handler(CommandHandler("setlink", set_link_command))
    app_main.add_handler(CommandHandler("broadcast", broadcast_command))
    app_main.add_handler(CommandHandler("setpaybot", set_paybot))
    app_main.add_handler(CommandHandler("addadmin", add_admin))
    
    # Callbacks
    app_main.add_handler(CallbackQueryHandler(main_button_handler))

    # Payment Bot App
    app_pay = ApplicationBuilder().token(config.PAYMENT_BOT_TOKEN).build()
    app_pay.add_handler(CommandHandler("start", start_payment))
    app_pay.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app_pay.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    await app_main.initialize()
    await app_main.start()
    await app_main.updater.start_polling()

    await app_pay.initialize()
    await app_pay.start()
    await app_pay.updater.start_polling()

    logger.info("🚀 Main Bot and Payment Bot are running!")

    stop_event = asyncio.Event()
    await stop_event.wait()

if __name__ == "__main__":
    asyncio.run(main())
