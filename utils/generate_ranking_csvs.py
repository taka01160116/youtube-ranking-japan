import pandas as pd
import os

# 読み込み
df = pd.read_csv("data/channel_video_data.csv")

# ランキングCSV保存先
output_dir = "data/ranking"
os.makedirs(output_dir, exist_ok=True)

# ジャンルごとに30件抽出してCSV化
for genre in df["ジャンル"].unique():
    genre_df = df[df["ジャンル"] == genre].copy()
    genre_df = genre_df.sort_values(by="総再生数", ascending=False).head(30)
    genre_df.to_csv(f"{output_dir}/{genre}.csv", index=False, encoding="utf-8-sig")

print("✅ ジャンル別CSVを生成しました。")
