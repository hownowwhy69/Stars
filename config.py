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
    "1": {"stars": 50, "videos": "50", "link": "https://t.me/+dNbUdp5zVtQ5MjI0"},
    "2": {"stars": 100, "videos": "120", "link": "https://t.me/+Vw7fhycyX8tiMTI0"},
    "3": {"stars": 200, "videos": "250", "link": "https://t.me/+pGC2w_IB1ZYwOTFk"},
    "4": {"stars": 500, "videos": "650", "link": "https://t.me/+xl0V2xGI-fRiMzNk"},
    "5": {"stars": 1000, "videos": "1400", "link": "https://t.me/+oztFMs9w3Wc3NDRk"},
    "6": {"stars": 5000, "videos": "6000", "link": "https://t.me/+FvkmSOYzg5o4NWM8"},
    "7": {"stars": 10000, "videos": "15000", "link": "https://t.me/+kGV5hB6LCmI4NzZk"}
}

# ==================== REFERRAL REWARDS ====================
# "Invites Required": Free Videos Amount
REF_REWARDS = {
    "2": 5,
    "5": 15,
    "10": 30,
    "25": 100,
    "50": 250,
    "100": 600,
    "200": 1400
}
