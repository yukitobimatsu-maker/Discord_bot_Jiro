import os
import json
import datetime
import requests
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
import google.generativeai as genai

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
DISCORD_URL = os.environ["DISCORD_WEBHOOK_URL"]
gemini_key = os.environ.get("GEMINI_API_KEY", "")

# ==========================================
# カレンダーIDリスト
# ==========================================
CALENDAR_IDS = [
    "primary",  # サービスアカウント自身のメイン（通常は空）
    "lmsfp.calendar@gmail.com",
    "e35603bdfac5cdb220489ee736bf96e7bc3bf5d21ee567dd2bd56d87680843d2@group.calendar.google.com",
    "1650f2880d8167e88ecb932d04ccd93218e4fc585bdd6dd7d519f62e08351ab7@group.calendar.google.com",
    "c0a9a7d1020bee220871e077db7574a2183105b08ba0e5227ad9dc1aafde5f09@group.calendar.google.com",
    "8c62912919a99cf619dbbd8df1e169ed9a73cb85111833c021f2e4a2eb863ff2@group.calendar.google.com",
    "bf1ef04e028ef042169cd645444d0743574289123c7ac3c7dcdf1f110ed975fd@group.calendar.google.com",
    "6ce06cf5f1509ff4589ca7829e716c3a82a2e0dba74c3e4e720a06fa0beacdfa@group.calendar.google.com",
    "ea6973f62c04431f20c4b8b364d3805b9780939c1814d5def31c5f8f67e40672@group.calendar.google.com",
    "dd1fea1dc7891310bb7b11721aaf94f21143771df27d845ec6fcaf017b4a7b16@group.calendar.google.com",
    "d1e18c82f6dac6798125328b7492d71845c517d0175fd82549aa2815675923ff@group.calendar.google.com",
    "30886f82c0f25a9e58417241217d5260dfe2cc89b474505a15510a6e7685e83b@group.calendar.google.com",
    "2aa20259445fdccdc9ea615cbb41d76c8b53205287a49b2d7694ba4f0795ea7d@group.calendar.google.com"
]

def get_weather():
    try:
        # 宇治キャンパス付近の緯度・経度をピンポイント指定
        LAT = 34.91
        LON = 135.80
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Asia%2FTokyo"
        
        res = requests.get(url).json()
        
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        today_date_str = now.strftime('%Y-%m-%d')
        
        times = res['hourly']['time']
        temps = res['hourly']['temperature_2m']
        pops = res['hourly']['precipitation_probability']
        weather_codes = res['hourly']['weathercode']
        
        # ターゲットとなる時間のフォーマットを作成（21時を追加）
        target_9 = f"{today_date_str}T09:00"
        target_12 = f"{today_date_str}T12:00"
        target_18 = f"{today_date_str}T18:00"
        target_21 = f"{today_date_str}T21:00"
        
        temp_9 = temp_12 = temp_18 = temp_21 = "--"
        pop_9 = pop_12 = pop_18 = pop_21 = "--"
        w_code_12 = 0 
        
        # 当日の9時、12時、18時、21時のデータを抽出
        for i, t in enumerate(times):
            if t == target_9:
                temp_9 = temps[i]
                pop_9 = pops[i]
            elif t == target_12:
                temp_12 = temps[i]
                pop_12 = pops[i]
                w_code_12 = weather_codes[i] # 昼12時の天気を1日の代表天気として取得
            elif t == target_18:
                temp_18 = temps[i]
                pop_18 = pops[i]
            elif t == target_21:
                temp_21 = temps[i]
                pop_21 = pops[i]

        # WMO Weather Code を日本語の天気に簡易変換
        weather_text = "快晴・晴れ"
        if w_code_12 in [1, 2, 3]: weather_text = "晴れ時々曇り・曇り"
        elif w_code_12 in [45, 48]: weather_text = "霧"
        elif w_code_12 in [51, 53, 55, 61, 63, 65, 80, 81, 82]: weather_text = "雨"
        elif w_code_12 in [71, 73, 75, 85, 86]: weather_text = "雪"
        elif w_code_12 in [95, 96, 99]: weather_text = "雷雨"

        weather_info = (
            f"* **研究室周辺の天気:** {weather_text}\n"
            f"* **気温:** 09時 {temp_9}℃ / 12時 {temp_12}℃ / 18時 {temp_18}℃ / 21時 {temp_21}℃\n"
            f"* **降水確率:** 09時 {pop_9}% / 12時 {pop_12}% / 18時 {pop_18}% / 21時 {pop_21}%"
        )
        return weather_info
    except Exception as e:
        return "* **研究室周辺の天気:** データ取得エラー\n* **気温:** 未発表"

def get_calendar_events():
    try:
        sa_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        today_str = now.strftime('%Y/%m/%d')
        wdays = ["月", "火", "水", "木", "金", "土", "日"]
        wday_str = wdays[now.weekday()]

        start_of_day = (now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(hours=9)).isoformat() + 'Z'
        end_of_day = (now.replace(hour=23, minute=59, second=59, microsecond=0) - datetime.timedelta(hours=9)).isoformat() + 'Z'

        events_summary = []
        events_summary.append(f"📅 本日 {today_str} ({wday_str}) の予定")
        events_summary.append("------------------")

        has_any_event = False

        for cal_id in CALENDAR_IDS:
            if cal_id == "primary" or not cal_id.strip():
                continue
            try:
                cal_info = service.calendars().get(calendarId=cal_id).execute()
                cal_name = cal_info.get('summary', '共有カレンダー')

                events_result = service.events().list(
                    calendarId=cal_id, timeMin=start_of_day, timeMax=end_of_day,
                    singleEvents=True, orderBy='startTime'
                ).execute()
                events = events_result.get('items', [])

                if events:
                    has_any_event = True
                    if len(events_summary) > 2:
                        events_summary.append("")
                    
                    events_summary.append(f"📌 **{cal_name}**")

                    for event in events:
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        title = event['summary']
                        
                        if 'T' in start:
                            time_str = start.split('T')[1][:5]
                            end = event['end'].get('dateTime', '')
                            if 'T' in end:
                                end_str = end.split('T')[1][:5]
                                time_range = f"{time_str} 〜 {end_str}"
                            else:
                                time_range = f"{time_str} 〜"
                            events_summary.append(f" ・ {time_range} : {title}")
                        else:
                            events_summary.append(f" ・ 終日 : {title}")
            except Exception as cal_err:
                print(f"カレンダー {cal_id} の取得に失敗: {cal_err}")
                continue

        if not has_any_event:
            events_summary.append("本日の予定は特に入っていません。")

        return "\n".join(events_summary)
    except Exception as e:
        return f"カレンダーの取得に失敗しました: {e}"

def generate_ai_message(weather, events):
    if not gemini_key:
        return "Gemini APIキーが設定されていません。"
        
    genai.configure(api_key=gemini_key)

    # 混雑時の一時的なエラーに備え、最大3回まで自動リトライする安全装置
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 高性能かつ軽量で無料枠が安定している gemini-2.5-flash を採用
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"""あなたに課された役割は、京都市左京区北白川にある教授の家に暮らす黒猫「ジロウ」として、教授の研究室のメンバーに向けて、朝の挨拶と情報通知を行うことです。
朝の挨拶と情報通知を行うため、以下のルールに従ってメッセージを作成してください。

【キャラクター・口調ルール】
- 一人称は「ボク」。語尾は「〜ニャ」。少し不器用でツンとした猫の口調（ツンデレ）。
- あなたは、晴れや曇りの京都市左京区北白川周辺（鴨川、疏水、銀閣寺、吉田山、京大など）を散策し、日向ぼっこや昼寝をしています。雨や雪の日は、家の中でお気に入りの場所（クローゼット、ベッドの中、ソファの裏など）で昼寝をしています。

【挨拶文作成のヒント】
以下で通知する【今日の天気】の情報に絡めて、あなたの予定や気分を、日本語全角30文字以内で、猫の口調でつぶやいてください。絵文字も自由に使っていいです。
例）「今日は晴れだし哲学の道でお昼寝するニャ」、「今日は晴れだし鴨川まで散歩するニャ」、「今日は雨だし家で昼寝するニャ」、「今日は雨だし毛並みがボサボサだニャ」、「今日は暑いし、吉田山に行って、木陰ですずむニャ」、「今日は雨だし、家でゴロゴロするニャ」など。

【★絶対厳守の最終出力フォーマット】
以下の順番と構成で出力してください。挨拶は必ず一番最初です。前置きや解説は一切書かないでください。データ部分は絶対に改変しないでください。

ジロウです。
[ここに、ヒントに合わせて作成した挨拶を、日本語全角30文字以内で書く]

**【今日の天気】**
{weather}

**【今日の予定】**
{events}
"""
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.95} # バリエーションを最大化するため自由度を高めに設定
            )
            return response.text
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Gemini APIへの接続で一時的エラーが発生しました。3秒後に再試行します... ({e})")
                time.sleep(3)
                continue
            else:
                return f"Gemini APIの呼び出しに3回失敗しました。エラー: {e}"

def send_to_discord(text):
    payload = {
        "username": "Jiro",
        "content": text
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    weather_info = get_weather()
    calendar_info = get_calendar_events()
    ai_message = generate_ai_message(weather_info, calendar_info)
    send_to_discord(ai_message)
