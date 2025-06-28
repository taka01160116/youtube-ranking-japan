import streamlit as st
import pandas as pd

# ページ設定
st.set_page_config(page_title="YouTubeジャンル別チャンネルランキング", layout="wide")
st.title("\U0001F4CA YouTubeジャンル別急上昇チャンネルランキング")
st.caption("直近30日間の総再生数で上位チャンネルを表示し、代表トレンド動画も紹介")

# データ読み込み
@st.cache_data
def load_data():
    return pd.read_csv("data/channel_video_data.csv")

df = load_data()

# ジャンルと登録者グループ選択
genres = sorted(df["ジャンル"].unique())
groups = ["5万人未満", "5万人以上"]

col1, col2 = st.columns(2)
with col1:
    selected_genre = st.selectbox("ジャンルを選択", genres)
with col2:
    selected_group = st.radio("登録者数グループ", groups, horizontal=True)

# フィルタリング
filtered_df = df[(df["ジャンル"] == selected_genre) & (df["グループ"] == selected_group)]

# 再生数でソート
filtered_df = filtered_df.sort_values(by="過去30日再生数", ascending=False)

# 表示タイトル
st.markdown(f"### \U0001F3AF ジャンル「{selected_genre}」・登録者数「{selected_group}」の上位チャンネル")

# データ表示
for idx, row in filtered_df.iterrows():
    with st.container():
        # チャンネルURLと動画URLを生成
        channel_url = f"https://www.youtube.com/channel/{row['チャンネルID']}"
        video_url = f"https://www.youtube.com/watch?v={row['動画ID']}"

        # チャンネル名をリンクに
        st.markdown(f"#### [{row['チャンネル名']}]({channel_url})（登録者数：{row['登録者数']:,}人 / 直近30日間の総再生数：{row['過去30日再生数']:,}回）")

        cols = st.columns([1, 4])
        with cols[0]:
            # サムネイルに動画リンクを追加
            st.markdown(
                f'<a href="{video_url}" target="_blank"><img src="{row["サムネイルURL"]}" width="160"></a>',
                unsafe_allow_html=True
            )
        with cols[1]:
            st.markdown(
                f"**\U0001F3A5 トレンド動画**：[ {row['動画タイトル']} ]({video_url})  \n"
                f"\U0001F4C5 投稿日：{row['投稿日']}"
            )
