import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datetime
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.api_handler import YouTubeAPIKeyManager
import isodate

# ジャンル設定
genre_keywords = {
    "音楽": ["歌ってみた"],
   
    }
CHANNELS_TXT = "data/channels.txt"

def get_youtube(api_key):
    return build("youtube", "v3", developerKey=api_key)

def search_videos(api_manager, keyword, published_after):
    """キーワード検索で動画からチャンネルIDを抽出（動画IDも）"""
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
            idinfo = item.get("id", {})
            if idinfo.get("kind") == "youtube#video" and "videoId" in idinfo:
                video_id = idinfo["videoId"]
                channel_id = item["snippet"]["channelId"]
                videos.append((video_id, channel_id))
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos

def get_uploads_playlist_id(api_manager, channel_id):
    """各チャンネルのuploadsプレイリストID取得"""
    tried_keys = set()
    while True:
        api_key = api_manager.get_valid_key()
        if api_key in tried_keys:
            api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
            continue
        youtube = get_youtube(api_key)
        try:
            res = youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()
            items = res.get('items', [])
            if not items:
                return None
            return items[0]['contentDetails']['relatedPlaylists']['uploads']
        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("🔁 get_uploads_playlist_id：APIキー切り替え（quotaExceeded）")
                tried_keys.add(api_key)
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            else:
                print(f"❌ get_uploads_playlist_idエラー：{e}")
                return None

def get_recent_videos_from_uploads(api_manager, playlist_id, days=30):
    """uploadsプレイリストから過去days日以内の動画IDリスト取得"""
    videos = []
    next_page_token = None
    today = datetime.datetime.utcnow()
    threshold = today - datetime.timedelta(days=days)
    while True:
        api_key = api_manager.get_valid_key()
        youtube = get_youtube(api_key)
        try:
            res = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("🔁 get_recent_videos_from_uploads：APIキー切り替え（quotaExceeded）")
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            else:
                print(f"❌ get_recent_videos_from_uploadsエラー：{e}")
                break

        for item in res.get("items", []):
            vid = item["contentDetails"]["videoId"]
            published_at = item["contentDetails"].get("videoPublishedAt") or item["snippet"].get("publishedAt")
            if not published_at:
                continue
            video_date = datetime.datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
            if video_date < threshold:
                return videos  # 30日より古いものは以降すべて古い
            videos.append((vid, published_at))
        next_page_token = res.get("nextPageToken")
        if not next_page_token:
            break
    return videos

def get_video_details_bulk(api_manager, video_id_list):
    """動画IDリストを一括で詳細取得（最大50件ずつ）"""
    results = []
    failed_ids = []
    import isodate
    for i in range(0, len(video_id_list), 50):
        batch = video_id_list[i:i+50]
        tried_keys = set()
        while True:
            if len(tried_keys) >= len(api_manager.api_keys):
                print("❌ get_video_details_bulk：APIキー全滅")
                failed_ids.extend(batch)
                break
            api_key = api_manager.get_valid_key()
            if api_key in tried_keys:
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            youtube = get_youtube(api_key)
            try:
                response = youtube.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(batch)
                ).execute()
                got_ids = set()
                for info in response.get("items", []):
                    got_ids.add(info["id"])
                    if "duration" not in info["contentDetails"]:
                        continue
                    duration = isodate.parse_duration(info["contentDetails"]["duration"]).total_seconds()
                    if duration < 300:
                        continue  # 5分未満は除外（既存仕様）
                    results.append({
                        "動画ID": info["id"],
                        "動画タイトル": info["snippet"]["title"],
                        "投稿日": info["snippet"]["publishedAt"],
                        "再生数": int(info["statistics"].get("viewCount", 0)),
                        "サムネイルURL": info["snippet"]["thumbnails"]["high"]["url"],
                        "duration": duration
                    })
                # 取得できなかったIDもリスト化
                notfound = set(batch) - got_ids
                if notfound:
                    failed_ids.extend(list(notfound))
                break  # batch成功したら次へ
            except HttpError as e:
                if e.resp.status == 403 and 'quotaExceeded' in str(e):
                    print("🔁 get_video_details_bulk：APIキー切り替え（quotaExceeded）")
                    tried_keys.add(api_key)
                    api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                    continue
                else:
                    print(f"❌ get_video_details_bulkエラー：{e}")
                    failed_ids.extend(batch)
                    break
    return results, failed_ids

def get_channel_details(api_manager, channel_id):
    """チャンネル名・登録者数を取得"""
    tried_keys = set()
    while True:
        api_key = api_manager.get_valid_key()
        if api_key in tried_keys:
            api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
            continue
        youtube = get_youtube(api_key)
        try:
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
        except HttpError as e:
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                print("🔁 get_channel_details：APIキー切り替え（quotaExceeded）")
                tried_keys.add(api_key)
                api_manager.index = (api_manager.index + 1) % len(api_manager.api_keys)
                continue
            else:
                print(f"❌ get_channel_detailsエラー：{e}")
                return None

def main():
    print("▶️ 処理開始しました")

    api_manager = YouTubeAPIKeyManager("api_keys.txt")
    today = datetime.datetime.utcnow()
    published_after = (today - datetime.timedelta(days=30)).isoformat("T") + "Z"

    all_data = []
    history_data = []
    os.makedirs("data", exist_ok=True)

    for genre, keywords in genre_keywords.items():
        print(f"\n🎯 ジャンル処理中: {genre}")

        # ① キーワード検索で対象チャンネルIDを発掘（set型で重複排除）
        channel_id_set = set()
        for kw in keywords:
            print(f"🔑 キーワード検索: {kw}")
            results = search_videos(api_manager, kw, published_after)
            for _, channel_id in results:
                channel_id_set.add(channel_id)
        print(f"🔎 発見チャンネル数: {len(channel_id_set)}")

        # channels.txt保存（毎回作り直し、次回以降流用可）
        with open(CHANNELS_TXT, "w", encoding="utf-8") as f:
            for cid in channel_id_set:
                f.write(f"{cid}\n")

        # ② 各チャンネルIDごとに「過去30日投稿の全動画」集計
        for channel_idx, channel_id in enumerate(channel_id_set, 1):
            print(f"\n📺 [{channel_idx}/{len(channel_id_set)}] チャンネル処理中: {channel_id}")

            channel_info = get_channel_details(api_manager, channel_id)
            if not channel_info:
                continue

            # ここ！登録者数2000人以下を除外
            if channel_info["登録者数"] <= 2000:
                print(f"⏭️ 登録者数2000人以下のため除外: {channel_id} ({channel_info['登録者数']}人)")
                continue

            uploads_id = get_uploads_playlist_id(api_manager, channel_id)
            if not uploads_id:
                continue

            recent_videos = get_recent_videos_from_uploads(api_manager, uploads_id, days=30)
            print(f"▶️  過去30日投稿動画数: {len(recent_videos)}")
            video_ids = [vid for vid, _ in recent_videos]

            # bulkで詳細取得
            video_infos, failed_ids = get_video_details_bulk(api_manager, video_ids)
            if failed_ids:
                print(f"⚠️ {len(failed_ids)}本の動画詳細取得に失敗: {failed_ids}")

            valid_videos = [v for v in video_infos if v]
            long_videos = [v for v in valid_videos if v["duration"] >= 300]
            if len(valid_videos) == 0 or len(long_videos) < len(valid_videos) * 0.6:
                print(f"⚠️ チャンネル除外（長尺比率 < 60%）: {channel_id}")
                continue

            # 【追加】ショート動画（duration < 60秒）はトレンド動画候補から除外
            trend_candidates = [v for v in valid_videos if v["duration"] >= 60]
            if not trend_candidates:
                print(f"⚠️ トレンド候補が存在しないためスキップ: {channel_id}")
                continue

            # 再生数最大の動画をトレンド動画とする
            trend_video = max(trend_candidates, key=lambda v: v["再生数"])

            total_views = sum(v["再生数"] for v in valid_videos)
            group = "5万人以上" if channel_info["登録者数"] >= 50000 else "5万人未満"

            all_data.append({
                "ジャンル": genre,
                "チャンネルID": channel_id,
                "チャンネル名": channel_info["チャンネル名"],
                "登録者数": channel_info["登録者数"],
                "グループ": group,
                "過去30日再生数": total_views,
                "トレンド動画ID": trend_video["動画ID"],
                "トレンド動画タイトル": trend_video["動画タイトル"],
                "トレンド投稿日": trend_video["投稿日"][:10],
                "トレンド動画再生数": trend_video["再生数"],
                "サムネイルURL": trend_video["サムネイルURL"]
            })

            history_data.append({
                "日付": today.strftime("%Y-%m-%d"),
                "動画ID": trend_video["動画ID"],
                "再生数": trend_video["再生数"]
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
