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

# --- CSS: スマホで確実に横スクロールさせる設定 ---
st.markdown("""
    <style>
    /* グラフの外枠を横スクロール可能にする */
    .stPlotlyChart {
        overflow-x: auto !important;
        display: block;
    }
    /* 内部のコンテナを1000pxに固定してスクロールを発生させる */
    .plot-container {
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

st.set_page_config(page_title="配達員体感温度予報", layout="wide")
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

    # 表示範囲を12データ分（3時間×12＝36時間）に設定
    for item in data["list"][:12]:
        dt = datetime.fromtimestamp(item["dt"])
        t = item["main"]["temp"]
        h = item["main"]["humidity"]
        w_speed = item["wind"]["speed"]
        rain = item.get("rain", {}).get("3h", 0) / 3 
        
        day_label = "今日" if dt.date() == now.date() else "明日" if dt.date() == (now + timedelta(days=1)).date() else dt.strftime("%d日")
        time_str = f"{day_label} {dt.hour}時"
        
        rad_bonus = (monthly_rad.get(dt.month, 2) if is_sunny_mode else 0) if 7 <= dt.hour <= 17 else 0
        p_temp = calc_perceived_temp(t, h, speed + (w_speed * 3.6), shield, rad_bonus)
        
        rows.append({"日時": time_str, "気温": t, "体感温度": round(p_temp, 1), "風速": w_speed, "降水量": round(rain, 2)})

    df = pd.DataFrame(rows)

    # --- グラフ作成 ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.15, subplot_titles=("温度推移 (℃)", "天候詳細 (降水・風速)"))

    fig.add_trace(go.Scatter(x=df["日時"], y=df["気温"], name="予報気温", line=dict(color='orange', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["体感温度"], name="走行時体感温度", line=dict(color='cyan', width=4)), row=1, col=1)
    fig.add_trace(go.Bar(x=df["日時"], y=df["降水量"], name="降水量(mm/h)", marker_color='royalblue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["日時"], y=df["風速"], name="風速(m/s)", line=dict(color='gray', width=1)), row=2, col=1)

    # レイアウト調整
    fig.update_layout(
        height=550,
        width=1000, # グラフの横幅を1000pxに固定してスクロールを発生させる
        dragmode=False,
        hovermode="x unified",
        margin=dict(l=40, r=40, t=50, b=80), # 下部に余白を持たせてラベルを表示
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="right", x=1)
    )

    # X軸のラベルを斜め(-45度)にし、ズームを禁止
    fig.update_xaxes(tickangle=-45, fixedrange=True)
    # Y軸のズームも禁止
    fig.update_yaxes(fixedrange=True)

    # グラフの表示（configでズームなどのメニューを全て消去）
    st.plotly_chart(fig, use_container_width=False, config={'displayModeBar': False})

    # --- 稼働アドバイス ---
    # ここはスマホで見やすいよう、1列で縦に並べる
    st.subheader("💡 稼働アドバイス")
    for i in range(4): # 直近12時間分を表示
        with st.container():
            st.write(f"**{df['日時'].iloc[i]}** : 体感 {df['体感温度'].iloc[i]} ℃")
            # アドバイス関数（省略していますが前のロジックと同じものを想定）
            st.divider()

else:
    st.error("データの取得に失敗しました。")
