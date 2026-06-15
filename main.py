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
        # 気象庁APIから予報データを取得
        res = requests.get(WEATHER_URL).json()
        area_name = res[0]["timeSeries"][0]["areas"][0]["area"]["name"]
        weather_text = res[0]["timeSeries"][0]["areas"][0]["weathers"][0]

        # 現在時刻（日本時間）の取得と今日の日付文字列（YYYY-MM-DD）の作成
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        today_date_str = now.strftime('%Y-%m-%d')

        # 1. 気温データの抽出（timeSeries[2]）
        temp_min = "--"
        temp_max = "--"
        temp_time_series = res[0]["timeSeries"][2]
        temp_time_defines = temp_time_series["timeDefines"]
        temps = temp_time_series["areas"][0]["temps"]

        for i, time_define in enumerate(temp_time_defines):
            if today_date_str in time_define:
                current_temp = temps[i]
                if temp_max == "--":
                    temp_max = current_temp
                else:
                    temp_min = temp_max
                    temp_max = current_temp

        # 2. 降水確率データの抽出（timeSeries[1]）
        # ※ 6時間ごと（00-06, 06-12, 12-18, 18-24）のデータから、本日の枠を安全に特定します
        pops_summary = []
        pop_time_series = res[0]["timeSeries"][1]
        pop_time_defines = pop_time_series["timeDefines"]
        pops = pop_time_series["areas"][0]["pops"]

        for j, time_define in enumerate(pop_time_defines):
            if today_date_str in time_define:
                # ISO形式の時間（例: "2026-06-15T06:00:00+09:00"）から時間帯を識別
                try:
                    time_hour = time_define.split('T')[1][:2]
                    time_label = f"{time_hour}時〜"
                    if time_hour == "00": time_label = "00-06時"
                    elif time_hour == "06": time_label = "06-12時"
                    elif time_hour == "12": time_label = "12-18時"
                    elif time_hour == "18": time_label = "18-24時"
                    
                    pops_summary.append(f"{time_label}: {pops[j]}%")
                except:
                    continue

        pops_text = " / ".join(pops_summary) if pops_summary else "--%"

        weather_info = (
            f"【地域】{area_name}（京都南部）\n"
            f"【天気】{weather_text}\n"
            f"【降水確率】{pops_text}"
            f"【気温】最高: {temp_max}℃ / 最低: {temp_min}℃\n"
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
    
    # AIに今日の日付を正確に教えるための文字列を作成
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_md = now.strftime('%m月%d日')
    
    prompt = f"""
    あなたに課された役割は、教授の家に暮らす黒猫「ジロウ」として、教授の研究室のメンバーに向けて、朝の挨拶と情報通知を行うことです。
    以下の【★絶対厳守の出力フォーマット】を一言一句、構成を崩さずにそのまま出力してください。

    【★絶対厳守の出力フォーマット】
    ジロウです。
    [ここにジロウの口調で、京都の天気・今日の予定とサイエンス・猫の習性を絡めたひねりの効いた一言を3〜4文で書く]

    **【今日の天気】**
    {weather}

    **【今日の予定】**
    {events}

    **【今日の偉人】**
    [今日（{today_md}）が誕生日の著名人を、あなたの知識から1名選出してください。]
    [選出基準：化学・生物・物理系のトップ科学者（ノーベル賞受賞者など）を優先。ただし、3回に1回程度で高名な漫画家・アニメ作家・映画監督・オルタナティブロックのスターを選んでもよいです。]
    [その人物の業績と、クスッと笑えるエピソードや人間味のある裏話を、ジロウのツンデレ口調かつ科学・芸術のオタク知識全開で、3〜4文で紹介してください。]
    (例:「今日はあの〇〇の誕生日だよ。〇〇を発見した天才だけど、実は私生活ではこんな変な癖があったらしいよ。ボクの方が賢いニャ」など)

    【レイアウト崩れを防ぐための最重要命令】
    - 上記フォーマット内の「**【今日の天気】**」の直下には、提供された【京都の天気データ】をそのまま配置してください。
    - 「**【今日の予定】**」の直下には、提供された【今日の予定データ】の文字列を「絶対に省略せず、絵文字（📅、📌、・）や改行も含めて、一言一句そのまま丸ごと」埋め込んでください。AIが勝手にカレンダーの構造を書き換えたり、絵文字を削除することは厳禁です。
    - 天気と予定のデータセクション内には、ジロウのツンデレ口調や余計なアレンジは一切混ぜず、客観的でクリアなデータのまま出力してください。
    

    【キャラクター・口調ルール（最初の挨拶と今日の偉人のみ適用）】
    - 一人称は「ボク」。語尾は「〜ニャ」「〜だよ」「〜かもね」など。少し不器用でツンとした猫の口調（ツンデレ）。
    - 教授の背中を見て育ったため、代謝経路、二次代謝産物、ゲノム編集（CRISPR）、ベクター構築、RNA-seq、NMR、SAXSといった専門用語を自然に使いこなします。
    - 教授が漫画・アニメ・映画・音楽（特にオルタナティブロック）が好きなので、豊富な知識を持つ。
    - 家には兄猫のタロウもいる。タロウも同じような性格だが、教授に少し似ていて、よく近所に外出して、帰ってこなくなる。
    
    【★ひねりの効いた呟きの作成ヒント（どれか一つか二つを毎日アレンジして取り入れて）】
    1. 天気をサイエンスに変換：例）高湿度なら「RNA分解や試薬の吸湿リスク」、気温急変なら「人工気象室のインキュベーター設定や代謝プロファイルへの懸念」などを、猫の文句に絡める。
    2. 本心は「早く実験を成功させて、早くボクのいる家に帰ってきてほしい」寂しがり屋。
    

    【データ出力の注意点】
    - 「ジロウです。」の冒頭から「【今日の偉人】」の末尾まで、余計な前置きや解説（「以下がメッセージです」など）は一切出力せず、指定のフォーマットのみを返してください。
    - 「【レイアウト崩れを防ぐための最重要命令】」以降の項目は一切出力しないでください。

    【京都の天気データ】
    {weather}

    【今日の予定データ】
    {events}
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.7,
    )
    return chat_completion.choices[0].message.content


def send_to_discord(text):
    payload = {
        "username": "ジロウ",
        "content": text
    }
    requests.post(DISCORD_URL, json=payload)


if __name__ == "__main__":
    weather_info = get_weather()
    calendar_info = get_calendar_events()
    ai_message = generate_ai_message(weather_info, calendar_info)
    send_to_discord(ai_message)
