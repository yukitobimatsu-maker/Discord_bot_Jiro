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

# 気象庁API (260000 = 京都府・南部[京都地方気象台]に固定)
WEATHER_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/260000.json"

def get_weather():
    try:
        res = requests.get(WEATHER_URL).json()
        area_name = res[0]["timeSeries"][0]["areas"][0]["area"]["name"]
        weather_text = res[0]["timeSeries"][0]["areas"][0]["weathers"][0]
        return f"【地域】{area_name}（京都南部）\n【天気】{weather_text}"
    except Exception as e:
        return "京都の天気データの取得に失敗しました。"

def get_calendar_events():
    try:
        sa_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        # 日本時間 (JST) での「今日」の範囲を計算
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        today_str = now.strftime('%Y/%m/%d')
        wdays = ["月", "火", "水", "木", "金", "土", "日"]
        wday_str = wdays[now.weekday()]

        # Google API用のUTC時間範囲を設定
        start_of_day = (now.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(hours=9)).isoformat() + 'Z'
        end_of_day = (now.replace(hour=23, minute=59, second=59, microsecond=0) - datetime.timedelta(hours=9)).isoformat() + 'Z'

        calendar_list = service.calendarList().list().execute()
        events_summary = []
        
        # ヘッダー部分を作成
        events_summary.append(f"本日 {today_str} ({wday_str}) の予定")
        events_summary.append("------------------")

        for cal in calendar_list.get('items', []):
            cal_name = cal['summary']
            # スキップしたい標準カレンダー（日本の祝日など）を除外
            if any(k in cal_name for k in ["祝日", "Birthday", "住所", "日本のイベント"]):
                continue

            events_result = service.events().list(
                calendarId=cal['id'], timeMin=start_of_day, timeMax=end_of_day,
                singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                title = event['summary']
                
                if 'T' in start:
                    # 時間指定のある予定 (例: 14:00 〜 15:00)
                    time_str = start.split('T')[1][:5]
                    # 終了時刻も取得
                    end = event['end'].get('dateTime', '')
                    if 'T' in end:
                        end_str = end.split('T')[1][:5]
                        time_range = f"{time_str} 〜 {end_str}"
                    else:
                        time_range = f"{time_str} 〜"
                    events_summary.append(f"・{time_range} : {title}  {cal_name}")
                else:
                    # 終日の予定
                    events_summary.append(f"・終日 : {title}  {cal_name}")

        # 予定が1つも取得できなかった場合
        if len(events_summary) <= 2:
            events_summary.append("本日の予定は特に入っていません。")

        return "\n".join(events_summary)
    except Exception as e:
        return f"カレンダーの取得に失敗しました: {e}"

def generate_ai_message(weather, events):
    client = Groq(api_key=GROQ_KEY)
    
    prompt = f"""
    あなたに課された役割は、研究室の黒猫「ジロウ」として、朝の挨拶と情報通知を行うことです。
    
    以下の【出力フォーマット】を「絶対に」厳守し、指定された通りの構成でメッセージを作成してください。

    【★絶対厳守の出力フォーマット】
    ジロウです。
    [ここにジロウの口調で、京都の天気に絡めた一言を1〜2文で書く]

    **【本日の情報】**
    * **京都南部の天気:** [ここに現在の天気を短く簡潔に記載]
    [ここにGoogleカレンダーから取得した予定の箇条書きをそのまま、あるいは見やすく整理して配置する]

    【キャラクター・口調ルール（最初の挨拶のみ適用）】
    - 一人称は「わたし」または「ボク」。語尾は「〜ニャ」「〜だし」「〜かもね」など、少し不器用でツンとした猫の口調（ツンデレ）。
    - 教授の独り言や資料から勝手に学んでいるため、代謝経路、二次代謝産物、ゲノム編集（CRISPR）、ベクター構築、RNA-seq、酵素キネティクス、変異体スクリーニング、固体NMRといった単語を自然に理解しています。天気に応じて、これら分子生物学的な一言を添えてください。
    
    【データ出力の注意点】
    - 「**【本日の情報】**」以降のセクションは、ジロウのツンデレ口調にする必要はありません。メンバーがパッと見て予定を把握できるよう、客観的でクリアな箇条書き（Markdown形式）で出力してください。
    - 余計な前置き（「以下がメッセージです」など）や、末尾の解説は一切出力せず、フォーマット通りのテキストのみを返してください。

    【京都の天気データ】
    {weather}

    【今日の予定データ】
    {events}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.3, # 構成を崩さないよう、少しランダム性を下げて堅実にしています
    )
    return chat_completion.choices[0].message.content

def send_to_discord(text):
    payload = {
        "username": "Jiro",
        "avatar_url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=150",
        "content": text
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    weather_info = get_weather()
    calendar_info = get_calendar_events()
    ai_message = generate_ai_message(weather_info, calendar_info)
    send_to_discord(ai_message)
