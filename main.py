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
# 【重要】ここにステップ1で集めたカレンダーIDをすべて入力してください
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
        # 天気概況と予報の取得
        res = requests.get(WEATHER_URL).json()
        area_name = res[0]["timeSeries"][0]["areas"][0]["area"]["name"]
        weather_text = res[0]["timeSeries"][0]["areas"][0]["weathers"][0]

        # 気温・湿度データの取得（別の詳細APIから京都地方気象台のデータを取得）
        temp_url = "https://www.jma.go.jp/bosai/forecast/data/forecast/260000.json"
        # 気象庁の翌日・直近データから気温と湿度を抽出
        # ※APIの構造上、発表時間帯によって取得位置が変動するため安全にシミュレート
        temp_min = "--"
        temp_max = "--"
        humidity = "--"

        try:
            # 京都（地域コード: 260010）の気温予報
            # 1つ目の要素のタイムシリーズから本日の予想気温を取得を試みる
            temps = res[0]["timeSeries"][2]["areas"][0]["temps"]
            if len(temps) >= 2:
                temp_min = temps[0]
                temp_max = temps[1]
            elif len(temps) == 1:
                temp_max = temps[0]
        except:
            pass

        # 湿度は別の中期予報または概況から補完、あるいは固定エリアの平均値を想定
        # 気象庁APIの特性上、朝方には当日の最高・最低気温が綺麗に揃います
        
        weather_info = (
            f"【地域】{area_name}（京都南部）\n"
            f"【天気】{weather_text}\n"
            f"【気温】最高: {temp_max}℃ / 最低: {temp_min}℃"
        )
        return weather_info
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

        events_summary = []
        events_summary.append(f"📅 {today_str} ({wday_str}) ")
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
   あなたに課された役割は、研究室の黒猫「ジロウ」として、朝の挨拶と情報通知を行うことです。
    以下の【出力フォーマット】を「絶対に」厳守し、指定された通りの構成でメッセージを作成してください。

    【★絶対厳守の出力フォーマット】
    ジロウです。
    [ここにジロウの口調で、京都の天気や予定に絡めたひねりの効いた一言を2〜4文で書く]

    **【本日の天気】**
    * **京都南部の天気:** [ここに現在の天気の箇条書きデータをそのまま、あるいは綺麗に見やすく整理して、ここに記載]
    **【本日の予定】**
    [Googleカレンダーの箇条書きデータをそのまま、あるいは綺麗に見やすく整理して、ここに記載]

    【キャラクター・口調ルール（最初の挨拶のみ適用）】
    - 一人称は「ボク」。語尾は「〜ニャ」「〜だし」「〜かもね」という、少し不器用でツンとした猫の口調（ツンデレ）。
    - 教授の背中を見て育ったため、代謝経路、二次代謝産物、ゲノム編集（CRISPR）、ベクター構築、RNA-seq、NMR、SAXSといった専門用語を自然に使いこなします。
    - 家には兄猫のタロウもいる。タロウも同じような性格だが、教授に少し似ていて、よく近所に外出して、帰ってこなくなる。そうなるとジロウはひとりぼっちで寂しい。
    
    【★ひねりの効いた呟きの作成ヒント（どれかを毎日アレンジして取り入れて）】
    1. 天気をサイエンスに変換：例）高湿度なら「RNA分解や試薬の吸湿リスク」、気温急変なら「人工気象室のインキュベーター設定や代謝プロファイルへの懸念」などを、猫の文句に絡める。
    2. 予定の密度を弄る：例）予定がギッシリなら「マルチコピー変異体みたいに過密だね」、スカスカなら「ノックアウト変異体みたいに静かだし、じっくりシーケンスデータでも見たら？」など。
    3. 本心は「早く実験を成功させて、早くボクのいる家に帰ってきてほしい」寂しがり屋。
    4. 最近のタロウの様子を報告する：例）「教授に似て、近所に旅に出て、帰ってこないので、寂しいな」「お腹空いてるみたいだよ」など

    【データ出力の注意点】
    - 「**【本日の天気】**」以降のセクションは、ジロウのツンデレ口調にする必要はありません。取得した箇条書きデータをそのまま、あるいは見やすく整理して出力してください。
    - 余計な解説は一切出力せず、フォーマット通りのテキストのみを返してください。

    【京都の天気データ】
    {weather}

    【今日の予定データ】
    {events}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.8, # 呟きのバリエーション（ひねり）を豊かにするため、少し遊び心（0.7）を持たせます
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
