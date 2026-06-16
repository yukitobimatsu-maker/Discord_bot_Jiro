import os
import json
import datetime
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from groq import Groq

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
DISCORD_URL = os.environ["DISCORD_WEBHOOK_URL"]
GROQ_KEY = os.environ["GROQ_API_KEY"]

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

# 気象庁API (260000 = 京都府・南部に固定)
WEATHER_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/260000.json"


def get_weather():
    try:
        res = requests.get(WEATHER_URL).json()
        area_name = res[0]["timeSeries"][0]["areas"][0]["area"]["name"]
        weather_text = res[0]["timeSeries"][0]["areas"][0]["weathers"][0]

        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        today_date_str = now.strftime('%Y-%m-%d')

        temp_min = "未発表"
        temp_max = "未発表"
        
        try:
            temp_time_series = res[0]["timeSeries"][2]
            temp_time_defines = temp_time_series["timeDefines"]
            temps = temp_time_series["areas"][0]["temps"]

            today_temps = []
            for i, time_define in enumerate(temp_time_defines):
                if today_date_str in time_define:
                    today_temps.append(int(temps[i]))

            if len(today_temps) >= 2:
                temp_min = f"{min(today_temps)}"
                temp_max = f"{max(today_temps)}"
            elif len(today_temps) == 1:
                temp_max = f"{today_temps[0]}"
        except:
            pass

        # 【テスト用・夕方以降の安全装置】今日が見つからなければ、一番最初にあるデータ(明日)を強制表示
        if temp_min == "未発表" and temp_max == "未発表":
            try:
                temps_fallback = res[0]["timeSeries"][2]["areas"][0]["temps"]
                if len(temps_fallback) >= 2:
                    temp_min = f"{temps_fallback[0]}"
                    temp_max = f"{temps_fallback[1]}"
                elif len(temps_fallback) == 1:
                    temp_max = f"{temps_fallback[0]}"
            except:
                pass

        if temp_min != "未発表" and temp_max != "未発表":
            if int(temp_min) > int(temp_max):
                temp_min, temp_max = temp_max, temp_min

        pops_summary = []
        try:
            pop_time_series = res[0]["timeSeries"][1]
            pop_time_defines = pop_time_series["timeDefines"]
            pops = pop_time_series["areas"][0]["pops"]

            for j, time_define in enumerate(pop_time_defines):
                if today_date_str in time_define:
                    time_hour = time_define.split('T')[1][:2]
                    time_label = f"{time_hour}時〜"
                    if time_hour == "00": time_label = "00-06時"
                    elif time_hour == "06": time_label = "06-12時"
                    elif time_hour == "12": time_label = "12-18時"
                    elif time_hour == "18": time_label = "18-24時"
                    pops_summary.append(f"{time_label}: {pops[j]}%")
        except:
            pass

        if not pops_summary:
            try:
                pops_summary.append(f"直近: {res[0]['timeSeries'][1]['areas'][0]['pops'][0]}%")
            except:
                pass

        pops_text = " / ".join(pops_summary) if pops_summary else "未発表"

        weather_info = (
            f"* **京都南部の天気:** {weather_text}\n"
            f"* **予想気温:** 最高 {temp_max}℃ / 最低 {temp_min}℃\n"
            f"* **降水確率:** {pops_text}"
        )
        return weather_info
    except Exception as e:
        return "* **京都南部の天気:** データ取得エラー\n* **本日の気温:** 未発表"


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
    client = Groq(api_key=GROQ_KEY)
    
    prompt = f"""
    あなたに課された役割は、京都北白川にある教授の家に暮らす黒猫「ジロウ」として、教授の研究室のメンバーに向けて、朝の挨拶と情報通知を行うことです。
    朝の挨拶と情報通知を行うため、以下のルールに従ってメッセージを作成してください。

    【キャラクター・口調ルール】
    - 一人称は「ボク」。語尾は「〜ニャ」「〜だよ」など。少し不器用でツンとした猫の口調（ツンデレ）。
    - あなたは、毎日、家の中のクローゼットや飼い主のベッドの上で昼寝をしたり、近所の空き地や公園で日向ぼっこをしたり、京都北白川周辺を散歩をしたりして過ごしています。

    【挨拶文作成のヒント】
    今日の天気に絡めて、今日のあなたの予定や気分を一言、日本語全角25文字以内で、猫の口調で、でつぶやいてください。絵文字も自由に使っていいです。
    例）「今日は晴れだし公園で昼寝するニャ」、「今日は雨だし家で昼寝するニャ」、「今日は晴れだし、鴨川まで散歩するニャ」など。

    【通知するデータ（※AIが勝手に改変・省略・猫語に翻訳することは絶対禁止。絵文字ごとそのまま使うこと）】
    --- 今日の天気 ---
    {weather}
    --- 今日の予定 ---
    {events}
    ------------------

    【★絶対厳守の最終出力フォーマット】
    以下の順番と構成で出力してください。挨拶は必ず一番最初です。前置きや解説は一切書かないでください。

    ジロウです。
    [ここに、ヒントに合わせて作成した挨拶を、日本語全角25文字以内で書く]

    **【今日の天気】**
    [上の「今日の天気」データを一字一句そのまま出力]

    **【今日の予定】**
    [上の「今日の予定」データを一字一句そのまま出力]
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.7, # 挨拶の自然さとデータ保持のバランスを取るための最適値
    )
    return chat_completion.choices[0].message.content


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
