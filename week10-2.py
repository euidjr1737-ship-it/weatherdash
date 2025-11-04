# app.py
import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="🌦️ Open-Meteo Weather Dashboard", layout="wide", page_icon="🌤️")
st.title("🌦️ Open-Meteo Interactive Weather Dashboard")
st.markdown("위치 검색 → 현재/시간별/일별 예보를 확인하세요. (Open-Meteo 기반, API 키 불필요)")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

@st.cache_data(ttl=60*60)
def geocode(query, limit=5):
    params = {"name": query, "count": limit}
    r = requests.get(GEOCODE_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("results", [])

@st.cache_data(ttl=60*10)
def fetch_forecast(lat, lon, timezone_str, hourly_vars, daily_vars, days=7):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(hourly_vars) if hourly_vars else None,
        "daily": ",".join(daily_vars) if daily_vars else None,
        "current_weather": "true",
        "forecast_days": days,
        "timezone": timezone_str
    }
    # remove None values
    params = {k: v for k, v in params.items() if v is not None}
    r = requests.get(FORECAST_URL, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# --- UI: 검색 패널 ---
with st.sidebar:
    st.header("검색")
    q = st.text_input("도시 또는 장소 입력 (예: Seoul, Gangnam, Incheon Airport)", value="Seoul")
    max_results = st.number_input("검색 결과 수", min_value=1, max_value=10, value=5)
    days = st.slider("예보 일수 (max 16)", min_value=1, max_value=16, value=7)
    hourly_options = st.multiselect("Hourly 변수 (차트 표시)", 
                                   options=["temperature_2m","apparent_temperature","relativehumidity_2m","precipitation","windspeed_10m","winddirection_10m","weathercode"],
                                   default=["temperature_2m","precipitation"])
    daily_options = st.multiselect("Daily 변수", 
                                  options=["temperature_2m_max","temperature_2m_min","precipitation_sum","weathercode"],
                                  default=["temperature_2m_max","temperature_2m_min","precipitation_sum"])
    search_btn = st.button("검색")

col1, col2 = st.columns([2,1])

if search_btn and q.strip():
    with st.spinner("위치 검색 중..."):
        results = geocode(q, limit=max_results)
    if not results:
        st.warning("검색 결과 없음 — 다른 키워드로 시도해")
    else:
        # 선택 UI
        rows = []
        for r in results:
            display_name = f"{r.get('name')}, {r.get('country')} ({r.get('admin1') or ''})"
            rows.append({"name": display_name, "lat": r["latitude"], "lon": r["longitude"], "timezone": r.get("timezone")})
        df = pd.DataFrame(rows)
        st.subheader("검색 결과")
        sel = st.radio("지역 선택", df["name"].tolist())
        idx = df["name"].tolist().index(sel)
        sel_row = df.iloc[idx]

        lat, lon, tz = float(sel_row["lat"]), float(sel_row["lon"]), sel_row["timezone"] or "UTC"
        st.markdown(f"**선택:** {sel} — 위도: {lat:.4f}, 경도: {lon:.4f}, timezone: {tz}")

        # 데이터 불러오기
        with st.spinner("예보 불러오는 중..."):
            data = fetch_forecast(lat, lon, tz, hourly_options, daily_options, days=days)

        # 현재 날씨
        current = data.get("current_weather", {})
        if current:
            with col1:
                st.metric("현재 기온 (°C)", f"{current.get('temperature')} °C", delta=None)
                st.write(f"풍속: {current.get('windspeed')} m/s, 바람방향: {current.get('winddirection')}°")
                st.write(f"관측 시간: {current.get('time')}")
        else:
            st.write("현재 날씨 데이터 없음")

        # hourly 차트 (matplotlib 사용)
        hourly = data.get("hourly", {})
        if hourly and hourly_options:
            df_hour = pd.DataFrame(hourly)
            # 시간 컬럼이 문자열이면 판다스 datetime으로
            df_hour['time'] = pd.to_datetime(df_hour['time'])
            st.subheader("시간별 데이터")
            for var in hourly_options:
                if var in df_hour.columns:
                    fig, ax = plt.subplots(figsize=(10, 3))
                    ax.plot(df_hour['time'], df_hour[var])
                    ax.set_title(var)
                    ax.set_xlabel("Time")
                    ax.set_ylabel(var)
                    ax.grid(True)
                    st.pyplot(fig)
                    plt.close(fig)

        # daily summary
        daily = data.get("daily", {})
        if daily and daily_options:
            st.subheader("일별 요약")
            df_daily = pd.DataFrame(daily)
            df_daily['time'] = pd.to_datetime(df_daily['time'])
            st.dataframe(df_daily[['time'] + [c for c in df_daily.columns if c in daily_options]])

        # 지도
        st.subheader("지도")
        map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
        st.map(map_df, zoom=10)

        # 원본 JSON (디버그용, 접기)
        with st.expander("원본 API 응답 보기 (JSON)"):
            st.json(data)
else:
    st.info("왼쪽 패널에서 장소를 검색하고 '검색' 버튼을 눌러 시작하세요.")
