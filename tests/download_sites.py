import requests
from datetime import datetime

def download_sites():
    # Date format for filenames: YYYYMMDD
    DATE = datetime.now().strftime("%Y%m%d")
    
    # List of websites
    SITES = {
        "nytimes": "https://www.nytimes.com/",
        "wapo": "https://www.washingtonpost.com/",
        "google": "https://www.google.com/",
        "apple": "https://www.apple.com/",
        "baidu": "https://www.baidu.com/",
        "qq": "https://www.qq.com/",
        "yandex": "https://www.yandex.ru/",
        "aljazeera": "https://www.aljazeera.com/"
    }

    for name, url in SITES.items():
        response = requests.get(url)
        if response.status_code == 200:
            with open(f"{name}_{DATE}.html", "w", encoding="utf-8") as f:
                f.write(response.text)
        else:
            print(f"Failed to download {name}. Status Code: {response.status_code}")

if __name__ == "__main__":
    download_sites()
