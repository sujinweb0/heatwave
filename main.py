import streamlit as st
import pandas as pd
import numpy as np
import folium
import json
import requests
from streamlit_folium import st_folium

# 1. 페이지 설정
st.set_page_config(
    page_title="전국 폭염일수 현황 지도",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 전국 폭염일수 현황 및 분석")
st.markdown("기상청 폭염 관측 데이터와 행정구역(시군구) 경계를 결합한 시각화 대시보드입니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 세 섹션 분리 함수
# -----------------------------------------------------------------------------
@st.cache_data
def load_heatwave_data(file_path="heatwave.csv"):
    """
    하나의 CSV 파일 내 3개 섹션("가장 긴 폭염", "가장 빠른/가장 늦은 폭염", "전국 폭염일수")을
    구분하여 3개의 데이터프레임으로 반환합니다.
    """
    # 2-1. 파일 인코딩 처리 (utf-8 실패 시 cp949 시도)
    lines = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, FileNotFoundError):
        try:
            with open(file_path, "r", encoding="cp949") as f:
                lines = f.readlines()
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
            return None, None, None

    # 2-2. 섹션별 줄 번호 찾기
    sec1_idx, sec2_idx, sec3_idx = -1, -1, -1
    for i, line in enumerate(lines):
        if "가장 긴 폭염" in line:
            sec1_idx = i
        elif "가장 빠른/가장 늦은 폭염" in line:
            sec2_idx = i
        elif "전국 폭염일수" in line:
            sec3_idx = i

    # 2-3. 각 섹션 파싱 함수
    def parse_section(start_idx, end_idx):
        if start_idx == -1:
            return pd.DataFrame()
        
        section_lines = lines[start_idx:end_idx] if end_idx else lines[start_idx:]
        # 헤더 선언 전 빈 줄이나 제목 줄 제거
        cleaned_lines = [l.strip() for l in section_lines if l.strip()]
        
        if len(cleaned_lines) < 2:
            return pd.DataFrame()

        # 데이터 변환 (첫 번째 유효한 줄을 헤더로 사용)
        header = [c.strip() for c in cleaned_lines[1].split(",")]
        data = []
        for line in cleaned_lines[2:]:
            row = [c.strip() for c in line.split(",")]
            if len(row) == len(header):
                data.append(row)
        return pd.DataFrame(data, columns=header)

    # 2-4. 섹션 추출 실행
    df_longest = parse_section(sec1_idx, sec2_idx if sec2_idx != -1 else len(lines))
    df_earliest_latest = parse_section(sec2_idx, sec3_idx if sec3_idx != -1 else len(lines))
    df_raw = parse_section(sec3_idx, None)

    return df_longest, df_earliest_latest, df_raw


# GeoJSON 경계 데이터 로드 함수
@st.cache_data
def load_geojson():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()

# 데이터 로딩
df_longest, df_earliest_latest, df_raw = load_heatwave_data("heatwave.csv")
geojson_data = load_geojson()

if df_raw.empty:
    st.error("데이터를 불러오지 못했습니다. 'heatwave.csv' 파일이 올바른 위치에 있는지 확인해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 관측지점 - 시군구 이름 매핑 딕셔너리
# -----------------------------------------------------------------------------
# 기상청 주요 관측지점 이름을 GeoJSON 속성('시군구') 매칭용 이름으로 변환
station_to_sigungu = {
    "서울": "종로구", "강릉": "강릉시", "대관령": "평창군", "추풍령": "영동군",
    "춘천": "춘천시", "원주": "원주시", "속초": "속초시", "동해": "동해시",
    "태백": "태백시", "대전": "유성구", "청주": "청주시", "충주": "충주시",
    "천안": "천안시", "전주": "전주시", "군산": "군산시", "목포": "목포시",
    "여수": "여수시", "광주": "북구", "대구": "중구", "포항": "포항시",
    "안동": "안동시", "창원": "창원시", "울산": "남구", "부산": "중구",
    "제주": "제주시", "서귀포": "서귀포시", "인천": "중구", "수원": "수원시"
}

# -----------------------------------------------------------------------------
# 4. 사이드바 구성 (연도 선택)
# -----------------------------------------------------------------------------
# 년도 컬럼 정제 및 연도 목록 생성
if "년도" in df_raw.columns:
    df_raw["년도"] = pd.to_numeric(df_raw["년도"], errors="coerce")
    year_list = sorted(df_raw["년도"].dropna().unique().astype(int))
else:
    # 컬럼명이 다른 경우 처리
    year_col = [col for col for col in df_raw.columns if "년" in col or "year" in col.lower()][0]
    df_raw["년도"] = pd.to_numeric(df_raw[year_col], errors="coerce")
    year_list = sorted(df_raw["년도"].dropna().unique().astype(int))

st.sidebar.header("⚙️ 옵션 설정")
selected_year = st.sidebar.slider(
    "조회할 연도를 선택하세요",
    min_value=int(min(year_list)),
    max_value=int(max(year_list)),
    value=int(max(year_list)),
    step=1
)

# -----------------------------------------------------------------------------
# 5. 선택된 연도 데이터 가공
# -----------------------------------------------------------------------------
df_year = df_raw[df_raw["년도"] == selected_year].copy()

# 지점별 폭염일수 집계
station_col = "지점" if "지점" in df_year.columns else df_year.columns[2]
df_counts = df_year.groupby(station_col).size().reset_index(name="폭염일수")

# 관측지점을 시군구 이름으로 매핑
df_counts["시군구"] = df_counts[station_col].map(station_to_sigungu).fillna(df_counts[station_col])

# -----------------------------------------------------------------------------
# 6. 상단 지표 카드 (Metrics)
# -----------------------------------------------------------------------------
avg_days = round(df_counts["폭염일수"].mean(), 1) if not df_counts.empty else 0
max_row = df_counts.loc[df_counts["폭염일수"].idxmax()] if not df_counts.empty else None
max_station = f"{max_row[station_col]} ({max_row['폭염일수']}일)" if max_row is not None else "-"
total_stations = len(df_counts)

col1, col2, col3 = st.columns(3)
col1.metric("📊 전국 평균 폭염일수", f"{avg_days} 일")
col2.metric("🔥 최다 폭염 발생지", max_station)
col3.metric("📍 총 관측지점 수", f"{total_stations} 곳")

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. 단계구분도(Choropleth) 지도 시각화
# -----------------------------------------------------------------------------
st.subheader(f"🗺️ {selected_year}년 전국 폭염일수 분포 지도")

# Folium 기본 지도 생성 (대한민국 중심 좌표)
m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="cartodbpositron")

# 단계구분도 레이어 추가
folium.Choropleth(
    geo_data=geojson_data,
    name="choropleth",
    data=df_counts,
    columns=["시군구", "폭염일수"],
    key_on="feature.properties.시군구",
    fill_color="YlOrRd",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name=f"{selected_year}년 폭염일수(일)",
    nan_fill_color="white"
).add_to(m)

# 지도 출력
st_folium(m, width=1200, height=500, returned_objects=[])

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. 하단 데이터 표 구성
# -----------------------------------------------------------------------------
# 8-1. 상위/하위 10개 지점 표
col_top, col_bottom = st.columns(2)

with col_top:
    st.subheader(f"🔝 {selected_year}년 폭염일수 상위 10곳")
    top_10 = df_counts.sort_values(by="폭염일수", ascending=False).head(10)
    st.dataframe(top_10[[station_col, "폭염일수"]].reset_index(drop=True), use_container_width=True)

with col_bottom:
    st.subheader(f"🧊 {selected_year}년 폭염일수 하위 10곳")
    bottom_10 = df_counts.sort_values(by="폭염일수", ascending=True).head(10)
    st.dataframe(bottom_10[[station_col, "폭염일수"]].reset_index(drop=True), use_container_width=True)

st.markdown("---")

# 8-2. 추가 통계 섹션 표 출력
col_sec1, col_sec2 = st.columns(2)

with col_sec1:
    st.subheader("📜 가장 긴 폭염 기록")
    if not df_longest.empty:
        st.dataframe(df_longest, use_container_width=True)
    else:
        st.info("해당 섹션 데이터가 없습니다.")

with col_sec2:
    st.subheader("🗓️ 가장 빠른 / 가장 늦은 폭염 기록")
    if not df_earliest_latest.empty:
        st.dataframe(df_earliest_latest, use_container_width=True)
    else:
        st.info("해당 섹션 데이터가 없습니다.")
