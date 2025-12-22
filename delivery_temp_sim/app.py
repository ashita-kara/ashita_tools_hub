import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 設定 ---
API_KEY = "3f080119fc55babcb348d038ac5017c9"
CITIES = {
    "札幌": {"lat": 43.0641, "lon": 141.3469}, "仙台": {"lat": 38.2682, "lon": 140.8694},
    "東京": {"lat": 35.6895, "lon": 139.6917}, "神奈川": {"lat": 35.4437, "lon": 139.6380},
    "名古屋": {"lat": 35.1815, "lon": 136.9066}, "大阪": {"lat": 34.6937, "lon": 135.5023},
    "福岡": {"lat": 33.5904, "lon": 130.4017}, "沖縄": {"lat": 26.2124, "lon": 127.6809},
}

# --- 強力な横スクロール用CSS ---
st.markdown("""
    <style>
    /* グラフの外側コンテナを横スクロール可能にする */
    .scroll-container {
        overflow-x: auto !important;
        white-space: nowrap;
        -webkit-overflow-scrolling: touch;
        padding-bottom: 20px;
    }
    /* グラフ本体の最小幅を強制固定 */
    .scroll-container > div {
        min-width: 1000px !important;
    }
    </style>
    """, unsafe_allow_html=True)

def calc_perceived_temp(t, h, v_kmh, shield_rate, rad_bonus):
    v_ms = (v_kmh * (1 - shield_rate/100)) / 3.6
    v_ms = max(v_ms, 0.1)
    a = 1.76 + 1.4 * (v_ms**0.75)
    tn = 37 - (37 - t) / (0.68 - 0.0014 * h + 1/a) - 0.29 * t * (1 - h/100)
    return tn + rad_bonus

def get_advice(p_temp, rain, wind):
    advice = ""
    if p_temp < 0: advice = "❄️【極寒】超極暖＋電熱＋ハンカバ必須。"
    elif p_temp < 5: advice = "🧥【厳冬】厚手ダウン＋防風パンツ＋冬グローブ。"
    elif p_temp < 12: advice = "🧤【冬】防風ジャケ＋インナーダウン。"
    elif p_temp < 20: advice = "🛵【春秋】3シーズン用。夜間の冷え注意。"
    elif p_temp < 28: advice = "☀️【快適】メッシュや長袖シャツでOK。"
    else: advice = "🔥【猛暑】空調服やクールインナー。水分を！"
    if rain > 0: advice += " ☔【雨】浸水注意。"
    if wind > 8: advice += " 🚩【強風】減速とニーグリップを。"
    return advice

st.set_page_config(page_title="配達員体感温度予報", layout="wide", initial_sidebar_state="auto")
st.title("🛵 配達員向け リアル体感温度予報")

# --- サイドバー ---
st.sidebar.header("🔧 条件設定")
selected_city = st.sidebar.selectbox("都市を選択", list(CITIES.keys()))
speed = st.sidebar.slider("走行速度 (km/h)", 0, 80, 40)
bike_type = st.sidebar.radio("バイクのタイプ", ["ネイキッド (0%)", "小型スクリーン (30%)", "中型スクリーン (60%)", "屋根付き・大型 (90%)", "カスタム設定"])
shield = int(bike_type.split("(")[1].split("%")[0]) if bike_type != "カスタム設定" else st.sidebar.slider("風除け効果 (%)", 0, 100, 50)
is_sunny_mode = st.sidebar.checkbox("日向（直射日光）を考慮する", value=True)

# --- データ取得 ---
@st.cache_data(ttl=3600)
def fetch_weather(city_name):
    lat, lon = CITIES[city_name]["lat"], CITIES[city_name]["lon"]
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=ja"
    return requests.get(url).json()

data = fetch_weather(selected_city)

if data.get("list"):
    st.header(f"📍 {selected_city} エリアの予測")

    rows = []
    monthly_rad = {1:0.5, 2:1, 3:2, 4:3, 5:4, 6:4, 7:6, 8:7, 9:5, 10:3, 11:1.5, 12:0.5}
    now = datetime.now()

    for item in data["list"][:14]: # 約1.5日分
        dt = datetime.fromtimestamp(item["dt"])
        t = item["main"]["temp"]
        h = item["main"]["humidity"]
        w_speed = item["wind"]["speed"]
        rain = item.get("rain", {}).get("3h", 0) / 3 
        
        day_label = "今日" if dt.date() == now.date() else "明日" if dt.date() == (now + timedelta(days=1)).date() else dt.strftime("%m/%d")
        time_str = f"{day_label}<br>{dt.hour}時" # 改行を入れて縦に並べる
        
        rad_bonus = (monthly_rad.get(dt.month, 2) if is_sunny_mode else 0) if 7 <= dt.hour <= 17 else 0
        p_temp = calc_perceived_temp(t, h, speed + (w_speed * 3.6), shield, rad_bonus)
        
        rows.append({"日時": time_str, "気温": t, "体感温度": round(p_temp, 1), "風速": w_speed, "降水量": round(rain, 2)})

    df = pd.DataFrame(rows)

    # --- グラフ作成 ---
    # shared_xaxes=False にして、それぞれに時間軸を表示
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.15, 
                        subplot_titles=("温度推移 (℃)", "天候詳細 (降水・風速)"))

    # 上段
    fig.add_trace(go.Scatter(x=df["日時"], y=df["気温"], name="予報気温", line=dict(color='orange', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["体感温度"], name="走行時体感温度", line=dict(color='cyan', width=4)), row=1, col=1)

    # 下段
    fig.add_trace(go.Bar(x=df["日時"], y=df["降水量"], name="降水量(mm/h)", marker_color='royalblue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["風速"], name="風速(m/s)", line=dict(color='gray', width=1)), row=2, col=1)

    fig.update_layout(
        height=600,
        dragmode=False,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
    )
    
    # ズーム禁止と目盛り設定
    fig.update_xaxes(fixedrange=True, tickangle=0) # 時間軸を回転させず読みやすく
    fig.update_yaxes(fixedrange=True)

    # --- スクロール用コンテナの中にグラフを配置 ---
    st.markdown('<div class="scroll-container">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=False, width=1000, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

    # --- アドバイス ---
    st.subheader("💡 稼働アドバイス")
    for i in range(4):
        with st.container():
            # 日付の<br>を除去して表示
            clean_time = df['日時'].iloc[i].replace('<br>', ' ')
            st.write(f"**{clean_time}** : {df['体感温度'].iloc[i]} ℃")
            st.caption(get_advice(df['体感温度'].iloc[i], df['降水量'].iloc[i], df['風速'].iloc[i]))
            st.divider()
else:
    st.error("データの取得に失敗しました。")
