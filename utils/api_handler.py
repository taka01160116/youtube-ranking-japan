import requests
import random

class YouTubeAPIKeyManager:
    def __init__(self, key_file_path="api_keys.txt"):
        with open(key_file_path, "r") as f:
            self.api_keys = [line.strip() for line in f if line.strip()]
        self.index = 0

    def get_valid_key(self):
        for _ in range(len(self.api_keys)):
            key = self.api_keys[self.index]
            if self._check_quota(key):
                return key
            self.index = (self.index + 1) % len(self.api_keys)
        raise Exception("すべてのAPIキーが使用上限に達しています。")

    def _check_quota(self, key):
        # quota確認用に簡単なAPI呼び出し（例：videoCategories.list）
        url = "https://www.googleapis.com/youtube/v3/videoCategories"
        params = {
            "part": "snippet",
            "regionCode": "JP",
            "key": key
        }
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        return False
