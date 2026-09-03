# -*- coding: utf-8 -*-
"""
Configuration File
Yahan se aap Tokens, Stars, Video Amounts, aur Channel Links change kar sakte hain.
"""

# ==================== TOKENS & DB CONFIG ====================
MAIN_BOT_TOKEN = "8968775484:AAE0QzNvQcXeVei8f6LGaGCXbiq_k7WhaCw"
PAYMENT_BOT_TOKEN = "8935465779:AAHCiegWcNpLiqSX3bbEMfYSRAl9P8UFagg"
ADMIN_ID = 938899359
MONGO_URL = "mongodb+srv://aaravkeshav92_db_user:VYpt1A4TTJvWJynJ@cluster0.3h5mg56.mongodb.net/?appName=Cluster0"
DB_NAME = "telegram_unified_bot"

# ==================== PACKAGES CONFIG ====================
# Pkg ID: Stars Amount, Videos Amount, Private Channel Link
PACKAGES = {
    "1": {"stars": 50, "videos": "50", "link": "https://t.me/+your_channel_link_1"},
    "2": {"stars": 100, "videos": "120", "link": "https://t.me/+your_channel_link_2"},
    "3": {"stars": 200, "videos": "250", "link": "https://t.me/+your_channel_link_3"},
    "4": {"stars": 500, "videos": "650", "link": "https://t.me/+your_channel_link_4"},
    "5": {"stars": 1000, "videos": "1400", "link": "https://t.me/+your_channel_link_5"},
    "6": {"stars": 5000, "videos": "6000", "link": "https://t.me/+your_channel_link_6"},
    "7": {"stars": 10000, "videos": "15000", "link": "https://t.me/+your_channel_link_7"}
}

# ==================== REFERRAL REWARDS ====================
# "Invites Required": Free Videos Amount
REF_REWARDS = {
    "2": 10,
    "5": 25,
    "10": 50,
    "25": 125,
    "50": 250,
    "100": 500,
    "200": 1000
}
