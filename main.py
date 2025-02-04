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
import json

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

# קריאת המילונים מקבצי JSON
def load_json_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

# טעינת תרגומי הליגות והקבוצות
league_translations = load_json_file('leagues.json')
team_translations = load_json_file('teams.json')

# פונקציה לשליחת הודעה בטלגרם
async def send_telegram_message(message):
    try:
        response = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Error sending message: {e}")  # טיפול בשגיאות

# פונקציה לשליחת משחקים לפי תאריך
def get_matches_for_date(start_date, end_date, team_ids):
    headers = {
        "X-Auth-Token": FOOTBALL_API_KEY
    }

    params = {'dateFrom': start_date, 'dateTo': end_date}  # מגביל לפי תאריך

    try:
        all_matches = []
        for team_id in team_ids:
            response = requests.get(f"{FOOTBALL_API_URL}teams/{team_id}/matches", headers=headers, params=params)
            response.raise_for_status()  # יוודא שאין בעיות עם ה-API
            data = response.json()
            all_matches.extend(data.get("matches", []))
        return all_matches
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return []

# פונקציה לשליחת משחקים לשבוע הקרוב
async def get_this_week_matches():
    today = datetime.now()
    start_date = today.strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')

    # IDs של ריאל מדריד וברצלונה ב-API
    team_ids = [86, 81]  # 86: ריאל מדריד, 81: ברצלונה

    matches = get_matches_for_date(start_date, end_date, team_ids)

    if not matches:
        await send_telegram_message(f"לא נמצאו משחקים לשבוע הקרוב ({start_date} - {end_date}).")
    else:
        # מיון המשחקים לפי תאריך ושעה
        matches.sort(key=lambda match: match["utcDate"])

        message = f"משחקים לשבוע הקרוב ({start_date} - {end_date}):\n"
        for match in matches:
            # תרגום הליגה
            competition = league_translations.get(match["competition"]["name"], match["competition"]["name"])

            # תרגום קבוצות
            home_team = team_translations.get(match["homeTeam"]["name"], match["homeTeam"]["name"])
            away_team = team_translations.get(match["awayTeam"]["name"], match["awayTeam"]["name"])

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

# מתזמן שליחת סיכום משחקים לשבוע הקרוב ב-יום ראשון בשעה 9:00
scheduler.add_job(lambda: asyncio.run(get_this_week_matches()), 'cron', day_of_week='sun', hour=9, minute=0)

# התחלת המתזמן
scheduler.start()

@app.get("/")
def read_root():
    return JSONResponse(content={"message": "Football Bot API is running."})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
