# 出糧之後：十四日生成

每月生成費用 **HK$0**。稿喺 `content/14-day.md`。每一條只教一件對得到嘅事，題材仍然只係出糧同預算、信用卡、保險概念、ETF 入門、加密貨幣點解會郁、每日用開嘅 AI。冇強積金，冇稅，冇叫人買某一隻，冇保證回報。

```bash
cd ig-pipeline
python3 -m pip install -r requirements.txt
python3 -m ig_pipeline generate
python3 -m ig_pipeline generate --limit 5
python3 -m ig_pipeline publish
```

`generate` 讀十四日稿，出粵語口播、9:16 字卡 Reels、4:5 圖文，同埋一個 `schedule.json`。畫面同稿用繁體中文，口語係廣東話，可以有短英文。單數日香港時間 12:20，雙數日 21:00。預設由聽日開始，`--start-date YYYY-MM-DD` 可以改。唔加 `--limit` 就出全部 14 日。`--limit 5` 只出第 1 至第 5 日，順序、caption、出帖時間都同全日表一樣，唔會寫第 6 至第 14 日。檔案喺 `output/<開始日期>/day-01` 至 `day-05`，同埋嗰個資料夾入面嘅 `schedule.json`。

`publish` 係乾跑，唔會出帖。未有 `IG_ACCESS_TOKEN` 同 `IG_USER_ID` 就停低，講明原因。有呢兩個環境變數都仍然係乾跑，要加 `--live` 先至會打官方 Instagram Graph API。每次 `--live` 最多出一條已經到時間嘅帖，而且距離上一條至少 12 小時。

## 聲

每一條 Reel 用你自己錄嘅聲。把 `day-01.wav` 或者 `day-01.m4a`（`.mp3`、`.aac` 都得）放喺 `ig-pipeline/recordings/`。想一句一檔，就放 `recordings/day-01/01.wav`、`02.wav`，檔數要同畫面卡一樣。程式唔會叫你把聲貼落聊天。

有你嘅檔，就唔會再叫 edge-tts。冇檔先至用 `zh-HK-HiuMaanNeural`，唔使匙，唔使錢。播放清單另一個後備係同一把聲嘅 Azure 官方端點。你自己已經有免費層匙，先至：

```bash
python3 -m ig_pipeline generate --voice azure
```

匙放喺 `AZURE_SPEECH_KEY` 同 `AZURE_SPEECH_REGION`。唔好貼落聊天。

網路連唔到語音，條片仍然會出，音軌係靜音，檔案同 `schedule.json` 都會寫 `SILENT FALLBACK`。未換返把聲，`--live` 會拒絕出帖。

出帖之前自己聽 `voice-check/` 四句：買同賣、冇、七百二、claim。程式唔會話你聽把聲過唔過關。

## 畫面

每一句口播一張卡。卡喺嗰句講出嚟嘅時間出現，唔係等成段聲平均切開。Pillow 畫 1080×1920，字放喺上半安全區一塊深色底上面，白字，一行一個意思，縮到每個字都喺畫面入面。底部留位。ffmpeg 只負責編碼、拼接、配音，唔使用 drawtext，所以 `brew install ffmpeg` 就得。圖文用 Pillow，1080×1350 JPEG。冇音樂，冇第二個人條片，冇浮水印。

第 2、6、10 日喺播放清單係你自己嘅螢幕、一鏡過。呢度用同一段口播同畫面字做成字卡。程式唔會錄你部電腦。你想換自己條片，出帖前換走 `reel.mp4`。口播入面「你用開嗰個」留低，因為程式唔知你當日打開邊個軟件。

## 你要自己做一次嘅嘢

1. 開 Instagram Creator 帳，公開，類別教育，顯示名稱「出糧之後」，簡介用播放清單嗰四行。開同名 Facebook 專頁，喺 Meta Business Suite 駁埋，只出 Instagram。
2. 喺 Meta for Developers 開一個 app，用 Facebook 登入，攞 `instagram_basic` 同 `instagram_content_publish`（如果畫面要求，再加 `pages_read_engagement`）。產生一條長效 Page access token，對住駁咗 Instagram 嗰版專頁。
3. `IG_USER_ID` 係 Instagram 專業帳 id，唔係 Facebook 專頁 id。`IG_ACCESS_TOKEN` 係上面嗰條 token。兩個都放喺你自己部電腦嘅環境變數。唔好貼落聊天，唔好 commit。
4. 聽聲。聲調錯嘅一句，你自己補錄嗰一句。
5. 圖文 `--live` 要 Meta 嘅伺服器攞到 JPEG。將輸出資料夾放到一個 https 網址，設 `IG_MEDIA_PUBLIC_BASE_URL`。Reels 可以由呢部電腦用官方 resumable upload 上傳，唔使公開網址。圖文你亦都可以喺 Business Suite 用 `caption.txt` 自己排。
6. App 問你係咪 AI 生成，如實答。有語音嘅 Reels 會傳 `is_ai_generated=true`。

官方發佈文件：<https://developers.facebook.com/docs/instagram-platform/content-publishing>

呢套程式唔會跟蹤、取消跟蹤、私訊、買粉絲，亦都唔會用非官方 Instagram 客戶端。

生成同官方 API 發佈都係 HK$0。呢個用量唔使訂 MiniMax、CapCut 或者 Canva。
