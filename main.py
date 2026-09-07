import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
import io
import copy

st.set_page_config(page_title="전국 폭염일수 대시보드", page_icon="\u2600\ufe0f", layout="wide")
st.title("\u2600\ufe0f 대한민국 폭염 종합 분석 대시보드")
st.caption("기상청 관측망 데이터를 바탕으로 한 전국 폭염일수 지도 및 연도별 주요 폭염 기록 통계입니다.")

GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

@st.cache_data
def load_geojson(url):
    response = requests.get(url)
    return response.json()

@st.cache_data
def load_all_heatwave_data():
    """하나의 heatwave.csv에서 3개 섹션의 데이터를 각각 읽어옵니다."""
    try:
        with open("heatwave.csv", "r", encoding="cp949") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open("heatwave.csv", "r", encoding="utf-8") as f:
            lines = f.readlines()

    longest_idx = extreme_idx = points_idx = None
    for idx, line in enumerate(lines):
        clean_l = line.strip()
        if clean_l == "가장 긴 폭염":
            longest_idx = idx + 1
        elif clean_l == "가장 빠른/가장 늦은 폭염":
            extreme_idx = idx + 1
        elif clean_l == "전국 폭염일수":
            points_idx = idx + 2

    longest_lines = []
    for l in lines[longest_idx:]:
        if not l.strip() or "가장 빠른" in l:
            break
        longest_lines.append(l)
    df_longest = pd.read_csv(io.StringIO("".join(longest_lines)))
    df_longest.columns = [c.strip() for c in df_longest.columns]

    extreme_lines = []
    for l in lines[extreme_idx:]:
        if not l.strip() or "전국 폭염일수" in l:
            break
        extreme_lines.append(l)
    df_extreme = pd.read_csv(io.StringIO("".join(extreme_lines)))
    df_extreme.columns = [c.strip() for c in df_extreme.columns]

    df_points = pd.read_csv(io.StringIO("".join(lines[points_idx:])))
    df_points.columns = [c.strip() for c in df_points.columns]
    df_points = df_points.dropna(subset=["년도", "지점"])
    df_points["년도"] = df_points["년도"].astype(int)

    return df_longest, df_extreme, df_points

try:
    geojson_raw = load_geojson(GEOJSON_URL)
    df_longest, df_extreme, df_raw = load_all_heatwave_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

STATION_TO_SIGUNGU = {
    "강릉": "강릉시", "강화": "강화군", "거제": "거제시", "거창": "거창군",
    "고흥": "고흥군", "광주": "광주", "구미": "구미시", "군산": "군산시",
    "금산": "금산군", "남원": "남원시", "남해": "남해군", "대관령": "평창군",
    "대구": "대구", "대전": "대전", "목포": "목포시", "문경": "문경시",
    "밀양": "밀양시", "보령": "보령시", "보은": "보은군", "봉화": "봉화군",
    "부산": "부산", "부안": "부안군", "부여": "부여군", "산청": "산청군",
    "서산": "서산시", "서울": "서울", "속초": "속초시", "수원": "수원시",
    "안동": "안동시", "양평": "양평군", "여수": "여수시", "영덕": "영덕군",
    "영주": "영주시", "영천": "영천시", "완도": "완도군", "울산": "울산",
    "울진": "울진군", "원주": "원주시", "의성": "의성군", "이천": "이천시",
    "인제": "인제군", "인천": "인천", "임실": "임실군", "장수": "장수군",
    "장흥": "장흥군", "전주": "전주시", "정읍": "정읍시", "제천": "제천시",
    "진주": "진주시", "창원": "창원시", "천안": "천안시", "철원": "철원군",
    "청주": "청주시", "추풍령": "영동군", "춘천": "춘천시", "충주": "충주시",
    "태백": "태백시", "통영": "통영시", "포항": "포항시", "합천": "합천군",
    "해남": "해남군", "홍천": "홍천군",
}

st.sidebar.header("\U0001f50d 조회 옵션")
years = sorted(df_raw["년도"].unique())
selected_year = st.sidebar.select_slider("\U0001f4c5 지도 조회 연도 선택", options=years, value=years[-1])

df_year = df_raw[df_raw["년도"] == selected_year]
df_counts = df_year.groupby("지점").size().reset_index(name="폭염일수")
df_counts["시군구"] = df_counts["지점"].map(STATION_TO_SIGUNGU)

if not df_counts.empty:
    max_row = df_counts.sort_values(by="폭염일수", ascending=False).iloc[0]
    avg_val = df_counts["폭염일수"].mean()
    m1, m2, m3 = st.columns(3)
    m1.metric("전국 평균 폭염일수", f"{avg_val:.1f}일")
    m2.metric("최다 폭염 관측지", f"{max_row['지점']} ({max_row['폭염일수']}일)")
    m3.metric("관측 지점 수", f"{len(df_counts)}개 지역")

geojson_display = copy.deepcopy(geojson_raw)
heatwave_map = dict(zip(df_counts["시군구"], df_counts["폭염일수"]))
for feature in geojson_display["features"]:
    sigungu = feature["properties"].get("시군구", "")
    val = heatwave_map.get(sigungu)
    feature["properties"]["폭염일수"] = f"{val}일" if val is not None else "관측소 없음"

st.subheader(f"\U0001f5fa\ufe0f {selected_year}년 전국 폭염일수 지도")
m = folium.Map(location=[36.0, 127.8], zoom_start=7, tiles="CartoDB positron")

min_val, max_val = float(df_counts["폭염일수"].min()), float(df_counts["폭염일수"].max())
bins = [min_val - 1.0, min_val, min_val + 1.0] if min_val == max_val else \
    [round(min_val + i * (max_val - min_val) / 5.0, 1) for i in range(6)]

folium.Choropleth(
    geo_data=geojson_display, data=df_counts, columns=["시군구", "폭염일수"],
    key_on="feature.properties.시군구", fill_color="YlOrRd", fill_opacity=0.78,
    line_color="white", line_weight=1.0, legend_name=f"{selected_year}년 폭염일수 (일)",
    bins=bins, nan_fill_color="#f8fafc",
).add_to(m)

folium.GeoJson(
    geojson_display,
    style_function=lambda x: {"fillColor": "#00000000", "color": "#00000000", "weight": 0},
    tooltip=folium.GeoJsonTooltip(fields=["시도", "시군구", "폭염일수"], aliases=["시도:", "시군구:", "폭염일수:"]),
).add_to(m)

st_folium(m, width="100%", height=600, key=f"heatwave_map_{selected_year}", returned_objects=[])

st.divider()
st.subheader(f"\U0001f4ca {selected_year}년 폭염일수 순위")
col1, col2 = st.columns(2)
top10 = df_counts.sort_values("폭염일수", ascending=False).head(10)[["지점", "시군구", "폭염일수"]].reset_index(drop=True)
bottom10 = df_counts.sort_values("폭염일수", ascending=True).head(10)[["지점", "시군구", "폭염일수"]].reset_index(drop=True)
with col1:
    st.markdown("#### \U0001f525 폭염 많은 상위 10곳")
    st.dataframe(top10, use_container_width=True)
with col2:
    st.markdown("#### \U0001f9ca 폭염 적은 하위 10곳")
    st.dataframe(bottom10, use_container_width=True)

st.divider()
st.markdown("#### 가장 긴 폭염")
st.dataframe(df_longest, use_container_width=True, hide_index=True)
st.markdown("#### 가장 빠른/늦은 폭염")
st.dataframe(df_extreme, use_container_width=True, hide_index=True)
