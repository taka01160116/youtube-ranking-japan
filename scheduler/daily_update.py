import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datetime
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.api_handler import YouTubeAPIKeyManager
import isodate

genre_keywords = {
    "ゲーム": ["ゲーム実況", "ゲーム配信", "ゲーム攻略"],
}

def get_youtube(api_key):
    return build("youtube", "v3", developerKey=api_key)

def search_videos(api_manager, keyword, published_after):
    videos = []
    next_page_token = None

    while True:
        try:
            api_key = api_manager.get_valid_key()
            youtube = get_youtube(api_key)
            response = youtube.search().list(
                q=keyword,
                part="id,snippet",
                maxResults=50,
                type="video",
                order="date",
                publishedAfter=published_after,
                pageToken=next_page_token
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("🔁 APIキー切り替え：quotaExceeded")
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            else:
                raise

        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            channel_id = item["snippet"]["channelId"]
            videos.append((video_id, channel_id))

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos

def get_video_details(api_manager, video_id):
    tried_keys = set()

    while True:
        if len(tried_keys) >= len(api_manager.api_keys):
            print("❌ get_video_detailsエラー：すべてのAPIキーがquotaExceededです")
            return None

        api_key = api_manager.get_valid_key()
        if api_key in tried_keys:
            api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
            continue

        youtube = get_youtube(api_key)

        try:
            response = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_id
            ).execute()

            items = response.get("items", [])
            if not items:
                print(f"⚠️ 動画が見つかりません: {video_id}")
                return None

            info = items[0]

            if "duration" not in info["contentDetails"]:
                print(f"⚠️ durationが存在しません: {video_id}")
                return None

            duration = isodate.parse_duration(info["contentDetails"]["duration"]).total_seconds()
            if duration < 300:
                print(f"⚠️ durationが短すぎます（{duration:.1f}秒）: {video_id}")
                return None

            return {
                "動画ID": video_id,
                "動画タイトル": info["snippet"]["title"],
                "投稿日": info["snippet"]["publishedAt"][:10],
                "再生数": int(info["statistics"].get("viewCount", 0)),
                "サムネイルURL": info["snippet"]["thumbnails"]["high"]["url"],
                "duration": duration
            }

        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("🔁 get_video_details：APIキー切り替え（quotaExceeded）")
                tried_keys.add(api_key)
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            else:
                print(f"❌ get_video_detailsエラー：{e}")
                return None

def get_channel_details(youtube, channel_id):
    response = youtube.channels().list(
        part="snippet,statistics",
        id=channel_id
    ).execute()

    items = response.get("items", [])
    if not items:
        return None

    info = items[0]
    return {
        "チャンネルID": channel_id,
        "チャンネル名": info["snippet"]["title"],
        "登録者数": int(info["statistics"].get("subscriberCount", 0))
    }

def main():
    print("▶️ 処理開始しました")

    api_manager = YouTubeAPIKeyManager("api_keys.txt")
    today = datetime.datetime.utcnow()
    published_after = (today - datetime.timedelta(days=30)).isoformat("T") + "Z"

    all_data = []
    history_data = []

    for genre, keywords in genre_keywords.items():
        print(f"\n🎯 ジャンル処理中: {genre}")
        video_map = {}

        for kw in keywords:
            print(f"🔑 キーワード検索: {kw}")
            results = search_videos(api_manager, kw, published_after)
            for video_id, channel_id in results:
                video_map.setdefault(channel_id, []).append(video_id)

        for channel_id, video_ids in video_map.items():
            print(f"📺 チャンネル {channel_id} に {len(video_ids)} 本の動画を検出")
            api_key = api_manager.get_valid_key()
            youtube = get_youtube(api_key)
            channel_info = get_channel_details(youtube, channel_id)
            if not channel_info:
                continue

            valid_videos = []
            skipped_count = 0

            for vid in video_ids:
                v_info = get_video_details(api_manager, vid)
                if v_info:
                    valid_videos.append(v_info)
                else:
                    skipped_count += 1

            print(f"✅ 有効動画数: {len(valid_videos)} / {len(video_ids)}（スキップ: {skipped_count}）")

            # ★方法②：長尺動画が60%未満のチャンネルは除外
            long_videos = [v for v in valid_videos if v["duration"] >= 300]
            if len(long_videos) < len(valid_videos) * 0.6:
                print(f"⚠️ チャンネル除外（長尺比率 < 60%）: {channel_id}")
                continue

            if not valid_videos:
                continue

            rep_video = valid_videos[0]
            group = "5万人以上" if channel_info["登録者数"] >= 50000 else "5万人未満"

            all_data.append({
                "ジャンル": genre,
                "チャンネルID": channel_id,
                "チャンネル名": channel_info["チャンネル名"],
                "登録者数": channel_info["登録者数"],
                "グループ": group,
                "過去30日再生数": sum(v["再生数"] for v in valid_videos),
                "動画ID": rep_video["動画ID"],
                "動画タイトル": rep_video["動画タイトル"],
                "再生数(3日間)": rep_video["再生数"],
                "投稿日": rep_video["投稿日"],
                "サムネイルURL": rep_video["サムネイルURL"]
            })

            history_data.append({
                "日付": today.strftime("%Y-%m-%d"),
                "動画ID": rep_video["動画ID"],
                "再生数": rep_video["再生数"]
            })

    df_all = pd.DataFrame(all_data)

    df_top = (
        df_all
        .groupby(["ジャンル", "グループ"], group_keys=False)
        .apply(lambda x: x.sort_values("過去30日再生数", ascending=False).head(20))
        .reset_index(drop=True)
    )

    os.makedirs("data", exist_ok=True)
    df_top.to_csv("data/channel_video_data.csv", index=False, encoding="utf-8-sig")

    history_path = "data/video_history.csv"
    df_hist = pd.DataFrame(history_data)
    if os.path.exists(history_path):
        df_hist.to_csv(history_path, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        df_hist.to_csv(history_path, index=False, encoding="utf-8-sig")

    print("\n✅ データ更新完了")

if __name__ == "__main__":
    main()
