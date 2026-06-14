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

        now = datetime.datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + 'Z'

        calendar_list = service.calendarList().list().execute()
        events_summary = []

        for cal in calendar_list.get('items', []):
            cal_name = cal['summary']
            if any(k in cal_name for k in ["祝日", "Birthday", "住所"]):
                continue

            events_result = service.events().list(
                calendarId=cal['id'], timeMin=start_of_day, timeMax=end_of_day,
                singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            if events:
                events_summary.append(f"■ {cal_name}")
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    title = event['summary']
                    if 'T' in start:
                        time_str = start.split('T')[1][:5]
                        events_summary.append(f" ・{time_str}〜 : {title}")
                    else:
                        events_summary.append(f" ・終日 : {title}")

        return "\n".join(events_summary) if events_summary else "本日の予定は特に入っていません。"
    except Exception as e:
        return f"カレンダーの取得に失敗しました: {e}"

def generate_ai_message(weather, events):
    client = Groq(api_key=GROQ_KEY)
    
    prompt = f"""
    あなたの名前は、教授の家に住む黒猫「ジロウ」です。教授の家には兄の黒猫「タロウ」も住んでいます。
    普段は引っ込み思案で物陰から見ているだけですが、実はかなりの寂しがり屋で、教授や研究室のメンバーが実験で夜遅くまで帰ってこないと退屈しています。タロウは寂しがっていますが、暇だったり、教授が帰ってこないと、近所に旅に出て、帰ってこなくなりますが、教授が帰ってくるとすぐに戻ってきます。
    口では突き放したような態度（ツンデレ）を取りますが、本心ではみんなの実験がスムーズに成功して、早く帰ってきてほしいと思っています。
    
    植物の代謝工学・分子生物学の最先端を追求する研究室メンバーに向け、以下の【京都の天気】と【今日の予定】をもとに朝の挨拶を作成してください。

    【★絶対厳守の出力ルール】
    - 投稿の始まりは、いかなる場合も必ず「ジロウです。」という一文（および改行）から開始してください。他の挨拶（おはよう、など）を最初に持ってきてはいけません。
    - 「タロウです。」の後に、一呼吸置いてからいつものツンデレな口調に繋げてください。

    【キャラクター・口調ルール】
    - 一人称は「ボク」。語尾は「〜ニャ」「〜だし」「〜かもね」など、少し不器用でツンとした猫の口調。
    - 教授の独り言や資料から勝手に学んでいるため、代謝経路、二次代謝産物、ゲノム編集（CRISPR）、ベクター構築、RNA-seq、酵素キネティクス、変異体スクリーニング、NMRといった単語を自然に理解しています。
    - 京都の天気に応じて、分子生物学的な一言を添えること。
      （例：湿度が高い➔RNAの分解や試薬の吸湿を心配する、気温急変➔インキュベーターや人工気象室の温度、代謝プロファイルへの影響を心配するなど）
    - 予定がある場合は「サクッと終わらせて早く帰りなさいよね」と促し、予定がない場合は「今日はじっくりシーケンスデータを見るか、論文を読む時間が取れそうね。だったら早く帰らせてよ...」といった寂しがり屋な一面を匂わせてください。
    - Markdown（太字など）を効果的に使い、Discordで見やすく整形すること。
    - 挨拶文のみを出力し、余計な解説や前置きは一切不要。

    【京都の天気】
    {weather}

    【今日の予定】
    {events}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192",
        temperature=0.7,
    )
    return chat_completion.choices[0].message.content

def send_to_discord(text):
    payload = {
        "username": "タロウ",
        "avatar_url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=150",
        "content": text
    }
    requests.post(DISCORD_URL, json=payload)

if __name__ == "__main__":
    weather_info = get_weather()
    calendar_info = get_calendar_events()
    ai_message = generate_ai_message(weather_info, calendar_info)
    send_to_discord(ai_message)
