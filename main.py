import os
import requests
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# טעינת משתנים מקובץ .env
load_dotenv()

# הגדרות הבוט ו-API
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# אתחול של הבוט ושל ה-API
bot = Bot(token=TELEGRAM_API_TOKEN)

# כתובת ה-API של Football-Data.org
FOOTBALL_API_URL = "https://api.football-data.org/v4/"

# יצירת אפליקציה של FastAPI
app = FastAPI()

# פונקציה לשליחת הודעה בטלגרם
async def send_telegram_message(message):
    try:
        response = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Error sending message: {e}")  # טיפול בשגיאות

# פונקציה לשליחת משחקים לפי תאריך עבור קבוצה נתונה
def get_matches_for_date(start_date, end_date, team_id):
    headers = {
        "X-Auth-Token": FOOTBALL_API_KEY
    }

    params = {'dateFrom': start_date, 'dateTo': end_date}  # מגביל לפי תאריך

    try:
        response = requests.get(FOOTBALL_API_URL + f"teams/{team_id}/matches", headers=headers, params=params)
        response.raise_for_status()  # יוודא שאין בעיות עם ה-API
        data = response.json()
        print(f"data for team {team_id}:", data)
        return data.get("matches", [])
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return []

# פונקציה לשליחת משחקים לשבוע הקרוב עבור ריאל וברצלונה
async def get_this_week_matches():
    today = datetime.now()
    start_date = today.strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')

    # משחקי ריאל מדריד (ID של ריאל הוא 86)
    real_matches = get_matches_for_date(start_date, end_date, team_id=86)
    # משחקי ברצלונה (ID של ברצלונה הוא 81)
    barca_matches = get_matches_for_date(start_date, end_date, team_id=81)

    all_matches = real_matches + barca_matches
    all_matches_sorted = sorted(all_matches, key=lambda x: x["utcDate"])  # סידור לפי תאריך

    if not all_matches_sorted:
        await send_telegram_message(f"לא נמצאו משחקים לשבוע הקרוב ({start_date} - {end_date}).")
    else:
        message = f"משחקים לשבוע הקרוב ({start_date} - {end_date}):\n"
        for match in all_matches_sorted:
            competition = match["competition"]["name"]
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            utc_date = match["utcDate"]
            match_time = (datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

            # הצגת קו הפרדה מעל המשחק
            message += "-" * 40 + "\n"
            message += f"תחרות: {competition}\n"
            message += f"{home_team} vs {away_team}\n"
            message += f"תאריך: {match_time.split()[0]}\n"  # תאריך
            message += f"שעה: {match_time.split()[1]}\n"    # שעה (שעה ודקה בלבד)

        await send_telegram_message(message)

# פונקציה לשליחת הודעת בדיקה
@app.get("/send_test_message")
async def send_test_message():
    await send_telegram_message("הודעת בדיקה: הבוט פועל בהצלחה!")
    return JSONResponse(content={"message": "Test message sent."})

# הגדרת מערכת המתזמן
scheduler = BackgroundScheduler()

# מתזמן שליחת סיכום משחקים לשבוע הקרוב ב-יום שני בשעה 15:00
scheduler.add_job(lambda: asyncio.run(get_this_week_matches()), 'cron', hour=15, minute=26)

# התחלת המתזמן
scheduler.start()

@app.get("/")
def read_root():
    return JSONResponse(content={"message": "Football Bot API is running."})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
