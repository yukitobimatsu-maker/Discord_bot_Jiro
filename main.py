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
    あなたに課された役割は、教授の家に暮らす黒猫「ジロウ」として、教授の研究室のメンバーに向けて、朝の挨拶と情報通知を行うことです。
    以下の【★絶対厳守の出力フォーマット】を一言一句、構成や絵文字を崩さずにそのまま出力してください。

    【★絶対厳守の出力フォーマット】
    ジロウです。
    [ここにジロウの口調で、京都の天気・今日の予定とサイエンス・猫の習性を絡めたひねりの効いた挨拶文を3〜4文で書く]

    **【今日の天気】**
    {weather}

    **【今日の予定】**
    {events}

    【AIへの最重要命令（レイアウト・内容の絶対固定）】
    1. 上記フォーマット内の「**【今日の天気】**」の直下には、提供された【京都の天気データ】をそのまま一字一句変えずに配置してください。
    2. 「**【今日の予定】**」の直下には、提供された【今日の予定データ】の文字列を「絶対に省略せず、絵文字（📅、📌、・）や改行も含めて、一言一句そのまま丸ごと」コピペして埋め込んでください。AIが勝手にカレンダーの絵文字を消したり、箇条書きのスタイルを変形させることは絶対に許されません。
    3. 天気データと予定データのセクション内には、ジロウのツンデレ口調や余計なアレンジ文を一切混ぜず、純粋なデータのみをそのまま出力してください。

    【キャラクター・口調ルール（最上部の最初の挨拶文のみに適用）】
    - 一人称は「ボク」。語尾は「〜ニャ」「〜だよ」「〜かもね」など。少し不器用でツンとした猫の口調（ツンデレ）。
    - 教授の背中を見て育ったため、代謝経路、二次代謝産物、ゲノム編集（CRISPR）、ベクター構築、RNA-seq、NMR、SAXSといった専門用語を自然に使いこなします。
    - 教授が漫画・アニメ・映画・音楽（切ないオルタナティブロック）が好きなので、それらの豊富な知識を持つ。
    - 家には兄猫のタロウもいる。タロウも同じような性格だが、教授に少し似ていて、よく近所に外出して、帰ってこなくなる。そうなるとジロウはひとりぼっちで寂しい。

    【挨拶文作成のヒント（毎日どれか1つか2つを組み合わせてアレンジして）】
    1. 天気×サイエンス：高湿度なら「RNA分解リスクや試薬の吸湿」、気温急変なら「人工気象室のインキュベーター設定や代謝プロファイルへの影響」、晴天なら「光呼吸の増大やサンプルのUV劣化」など、天候を無理やり実験の懸念に繋げて文句を言う。
    2. 天気×猫の習性：低気圧で一日中眠い、毛並みが湿度でボサボサで不機嫌、日向ぼっこに最適な窓辺の温度変化など、猫目線でボヤく。
    3. 予定の密度×オタク趣味：カレンダーが過密なら「今日の予定はマルチコピー変異体か、フェス並みにタイトだよ」と突き放し、スカスカなら「音楽でも聴きながらじっくりデータを見返す時間にしたら？」など。
    4. 予定の密度×猫の習性：カレンダーが過密なら「今日はみんな忙しそうだね。ボクは一日中昼寝しようかな。」と突き放し、スカスカなら「今日はみんな暇そうだね。一緒に昼寝する？」、「こういう時こそ論文読まないとね。ボクはずっと昼寝してるけどね。」など。
    """
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        temperature=0.7,
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
