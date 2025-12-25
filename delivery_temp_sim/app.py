import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
import time

# --- 設定 ---
API_KEY = "3f080119fc55babcb348d038ac5017c9"
CITIES = {
    "札幌": {"lat": 43.0641, "lon": 141.3469}, "仙台": {"lat": 38.2682, "lon": 140.8694},
    "東京": {"lat": 35.6895, "lon": 139.6917}, "神奈川": {"lat": 35.4437, "lon": 139.6380},
    "名古屋": {"lat": 35.1815, "lon": 136.9066}, "大阪": {"lat": 34.6937, "lon": 135.5023},
    "福岡": {"lat": 33.5904, "lon": 130.4017}, "沖縄": {"lat": 26.2124, "lon": 127.6809},
}

# 日本時間(JST)の定義
JST = timezone(timedelta(hours=9))

# --- CSS: サイドバーボタンを死守し、不要な要素だけを完全に抹消 ---
st.markdown("""
    <style>
    /* 1. 画面全体の余白調整 */
    .block-container {
        padding-top: 2.5rem !important; 
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* 2. ヘッダー：背景を透明にしつつ、左側のボタン(>> / <<)をタップ可能にする */
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
    }

    /* 3. 右側のツールバー（GitHub/Deploy/メニュー）だけをピンポイントで削除 */
    div[data-testid="stToolbar"], 
    .stAppDeployButton {
        display: none !important;
    }

    /* 4. 右下の赤いフッター（Hosted with Streamlit）を完全に削除 */
    footer {
        display: none !important;
    }

    /* 5. タイトルのスタイル設定 */
    .custom-title {
        font-size: 1.5rem !important;
        font-weight: bold;
        text-align: left;
        margin-bottom: 0.5rem;
        color: #31333F;
    }
    
    /* 右下の小さなステータスウィジェットも削除 */
    div[data-testid="stStatusWidget"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

def calc_perceived_temp(t, h, v_kmh, shield_rate, rad_bonus):
    v_ms = (v_kmh * (1 - shield_rate/100)) / 3.6
    v_ms = max(v_ms, 0.1)
    a = 1.76 + 1.4 * (v_ms**0.75)
    tn = 37 - (37 - t) / (0.68 - 0.0014 * h + 1/a) - 0.29 * t * (1 - h/100)
    return tn + rad_bonus

# タイトルを1段で表示
st.markdown('<div class="custom-title">🛵 配達員向け 体感温度予報</div>', unsafe_allow_html=True)

# --- サイドバー ---
st.sidebar.header("🔧 条件設定")
selected_city = st.sidebar.selectbox("都市を選択", list(CITIES.keys()))
speed = st.sidebar.slider("走行速度 (km/h)", 0, 80, 40)
bike_type = st.sidebar.radio("バイクのタイプ", ["ネイキッド (0%)", "小型スクリーン (30%)", "中型スクリーン (60%)", "屋根付き・大型 (90%)", "カスタム設定"])
shield = int(bike_type.split("(")[1].split("%")[0]) if bike_type != "カスタム設定" else st.sidebar.slider("風除け効果 (%)", 0, 100, 50)
is_sunny_mode = st.sidebar.checkbox("日向（直射日光）を考慮する", value=True)

# --- データ取得 ---
@st.cache_data(ttl=600)
def fetch_weather(city_name):
    lat, lon = CITIES[city_name]["lat"], CITIES[city_name]["lon"]
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=ja"
    return requests.get(url).json()

data = fetch_weather(selected_city)

if data.get("list"):
    st.subheader(f"📍 {selected_city} エリア")

    rows = []
    monthly_rad = {1:0.5, 2:1, 3:2, 4:3, 5:4, 6:4, 7:6, 8:7, 9:5, 10:3, 11:1.5, 12:0.5}
    now_jst = datetime.now(JST)
    now_ts = now_jst.timestamp()

    # 日本時間の現在時刻から先の予報のみ抽出
    filtered_list = [item for item in data["list"] if item["dt"] > now_ts - 5400]

    # スマホで見やすい24時間分（8個）に限定
    for item in filtered_list[:8]:
        dt = datetime.fromtimestamp(item["dt"], JST)
        t = item["main"]["temp"]
        h = item["main"]["humidity"]
        w_speed = item["wind"]["speed"]
        rain = item.get("rain", {}).get("3h", 0) / 3 
        
        day_label = "今日" if dt.date() == now_jst.date() else "明日"
        time_str = f"{day_label}{dt.hour}時"
        
        rad_bonus = (monthly_rad.get(dt.month, 2) if is_sunny_mode else 0) if 7 <= dt.hour <= 17 else 0
        p_temp = calc_perceived_temp(t, h, speed + (w_speed * 3.6), shield, rad_bonus)
        
        rows.append({"日時": time_str, "気温": t, "体感温度": round(p_temp, 1), "風速": w_speed, "雨": round(rain, 2)})

    df = pd.DataFrame(rows)

    # --- グラフ作成 ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.2, 
                        subplot_titles=("温度推移 (℃)", "天候詳細 (雨・風)"))

    fig.add_trace(go.Scatter(x=df["日時"], y=df["気温"], name="予報気温", line=dict(color='orange', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["体感温度"], name="体感温度", line=dict(color='cyan', width=4)), row=1, col=1)
    fig.add_trace(go.Bar(x=df["日時"], y=df["雨"], name="雨(mm)", marker_color='royalblue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["風速"], name="風(m/s)", line=dict(color='gray', width=1)), row=2, col=1)

    fig.update_layout(
        height=500,
        dragmode=False,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        template="plotly_white"
    )

    fig.update_xaxes(showticklabels=True, tickangle=-45, fixedrange=True, tickfont=dict(size=9))
    fig.update_yaxes(fixedrange=True)

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- 直近のアドバイス ---
    st.subheader("💡 直近のアドバイス")
    for i in range(min(len(df), 3)):
        st.write(f"**{df['日時'].iloc[i]}**: 体感 **{df['体感温度'].iloc[i]} ℃**")
        st.divider()
else:
    st.error("データの取得に失敗しました。")
