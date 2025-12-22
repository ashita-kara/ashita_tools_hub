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

# --- CSS: タイトルサイズの調整と全体の最適化 ---
st.markdown("""
    <style>
    /* スマホ（画面幅640px以下）でタイトルを小さくする */
    @media (max-width: 640px) {
        .main-title {
            font-size: 1.5rem !important;
            line-height: 1.2 !important;
        }
    }
    /* PCでは標準サイズ */
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

def calc_perceived_temp(t, h, v_kmh, shield_rate, rad_bonus):
    v_ms = (v_kmh * (1 - shield_rate/100)) / 3.6
    v_ms = max(v_ms, 0.1)
    a = 1.76 + 1.4 * (v_ms**0.75)
    tn = 37 - (37 - t) / (0.68 - 0.0014 * h + 1/a) - 0.29 * t * (1 - h/100)
    return tn + rad_bonus

st.set_page_config(page_title="配達員体感温度予報", layout="wide")

# タイトルをCSSクラス付きのHTMLで描画
st.markdown('<div class="main-title">🛵 配達員向け リアル体感温度予報</div>', unsafe_allow_html=True)

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
    st.header(f"📍 {selected_city} エリアの予測")

    rows = []
    monthly_rad = {1:0.5, 2:1, 3:2, 4:3, 5:4, 6:4, 7:6, 8:7, 9:5, 10:3, 11:1.5, 12:0.5}
    now_jst = datetime.now(JST)
    now_ts = now_jst.timestamp()

    # 日本時間の現在より後の予報を抽出
    filtered_list = [item for item in data["list"] if item["dt"] > now_ts - 5400]

    # 表示範囲を24時間（3時間おき×8データ）に設定
    for item in filtered_list[:8]:
        dt = datetime.fromtimestamp(item["dt"], JST)
        t = item["main"]["temp"]
        h = item["main"]["humidity"]
        w_speed = item["wind"]["speed"]
        rain = item.get("rain", {}).get("3h", 0) / 3 
        
        day_label = "今日" if dt.date() == now_jst.date() else "明日"
        time_str = f"{day_label} {dt.hour}時"
        
        rad_bonus = (monthly_rad.get(dt.month, 2) if is_sunny_mode else 0) if 7 <= dt.hour <= 17 else 0
        p_temp = calc_perceived_temp(t, h, speed + (w_speed * 3.6), shield, rad_bonus)
        
        rows.append({"日時": time_str, "気温": t, "体感温度": round(p_temp, 1), "風速": w_speed, "降水量": round(rain, 2)})

    df = pd.DataFrame(rows)

    # --- グラフ作成 ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.25, 
                        subplot_titles=("温度推移 (℃)", "天候詳細 (降水・風速)"))

    fig.add_trace(go.Scatter(x=df["日時"], y=df["気温"], name="予報気温", line=dict(color='orange', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["体感温度"], name="体感温度", line=dict(color='cyan', width=4)), row=1, col=1)
    fig.add_trace(go.Bar(x=df["日時"], y=df["降水量"], name="雨(mm)", marker_color='royalblue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["風速"], name="風(m/s)", line=dict(color='gray', width=1)), row=2, col=1)

    fig.update_layout(
        height=550,
        dragmode=False,
        hovermode="x unified",
        margin=dict(l=40, r=40, t=50, b=100),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        template="plotly_white"
    )

    fig.update_xaxes(showticklabels=True, tickangle=-45, fixedrange=True, tickfont=dict(size=10))
    fig.update_yaxes(fixedrange=True)

    # グラフを表示
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # --- アドバイス ---
    st.subheader("💡 直近のアドバイス")
    for i in range(min(len(df), 3)):
        st.write(f"**{df['日時'].iloc[i]}** : 体感 **{df['体感温度'].iloc[i]} ℃**")
        st.divider()
else:
    st.error("最新データの取得に失敗しました。")
