# 🌥️ ダウ雲アラートシステム v3.0 - Renderクラウド + ローカル通知

TradingView Pine Script「ダウ雲_V03」から送信されるJSONデータを**Render無料プラン（クラウド）**で受信し、**ローカルPC**でデスクトップ通知・音声・LINE通知を行う統合システムです。

## 🎯 システム構成

```
🌐 TradingView → 📡 Renderクラウド → 💻 ローカルPC
                        ↓
                   📱 LINE通知
```

- **Renderサーバー（クラウド）**: TradingViewからのWebhook受信・データ保存・LINE通知
- **ローカルクライアント（PC）**: デスクトップ通知・音声再生
- **PCを閉じてもクラウドで24/7受信継続**

## ✅ 主な機能

✅ **クラウド常時受信** - Render無料プランでPCオフでも受信継続  
✅ **LINE Notify通知** - スマホにリアルタイムプッシュ通知  
✅ **デスクトップ通知** - Windows Toast通知で視覚的アラート  
✅ **音声アラート** - VOICEVOX音声を雲種別・GC/DC別に再生  
✅ **PostgreSQL保存** - Render無料DBで発火履歴を永続保存  
✅ **Webダッシュボード** - ブラウザで雲の状態をリアルタイム表示  

---

## 📂 ファイル構成

```
TradingViewWebhook/
├── render_server.py          # 🚀 Renderクラウドサーバー（Webhook受信・LINE通知）
├── local_client.py            # 💻 ローカルPCクライアント（デスクトップ通知・音声）
├── requirements_render.txt    # ☁️ Render用パッケージ（PostgreSQL対応）
├── requirements_local.txt     # 🖥️ ローカル用パッケージ（音声・通知）
├── render.yaml                # ⚙️ Renderデプロイスクリプト
├── voice_config.json          # 🔊 音声設定（音量調整）
├── templates/
│   └── dashboard.html         # 🌐 Webダッシュボード
└── sounds/                    # 🔊 VOICEVOX音声ファイル（9種類）
    ├── short_up.wav          # 短期雲GC
    ├── short_dn.wav          # 短期雲DC
    ├── mid_up.wav            # 中期雲GC
    ├── mid_dn.wav            # 中期雲DC
    ├── long_up.wav           # 長期雲GC
    ├── long_dn.wav           # 長期雲DC
    ├── ultra_up.wav          # 超長期雲GC
    ├── ultra_dn.wav          # 超長期雲DC
    └── max_reached.wav       # 最大発火数到達
```

---

## 🚀 セットアップ手順

### 1️⃣ LINE Notify トークン取得

1. https://notify-bot.line.me/ にアクセス
2. 「マイページ」→「トークンを発行する」
3. トークン名: `TradingView ダウ雲アラート`
4. 通知先グループを選択
5. **トークンをコピー**（後でRender環境変数に設定）

---

### 2️⃣ VOICEVOX音声ファイル作成

1. [VOICEVOX](https://voicevox.hiroshiba.jp/)をダウンロード・インストール
2. 以下の9種類の音声ファイルを作成し、`sounds/`フォルダに保存:

| ファイル名 | テキスト例 |
|-----------|-----------|
| `short_up.wav` | 短期雲、ゴールデンクロス発火 |
| `short_dn.wav` | 短期雲、デッドクロス発火 |
| `mid_up.wav` | 中期雲、ゴールデンクロス発火 |
| `mid_dn.wav` | 中期雲、デッドクロス発火 |
| `long_up.wav` | 長期雲、ゴールデンクロス発火 |
| `long_dn.wav` | 長期雲、デッドクロス発火 |
| `ultra_up.wav` | 超長期雲、ゴールデンクロス発火 |
| `ultra_dn.wav` | 超長期雲、デッドクロス発火 |
| `max_reached.wav` | 最大発火数に到達しました |

---

### 3️⃣ Renderクラウドデプロイ

#### 3-1. GitHubリポジトリ作成

```powershell
cd c:\Users\kanda\Desktop\PythonData\TradingViewWebhook
git init
git add .
git commit -m "Initial commit: Dow Cloud Alert System v3.0"
git remote add origin <your-github-repo-url>
git push -u origin main
```

#### 3-2. Renderでサービス作成

1. https://render.com にサインアップ
2. 「New」→「Web Service」
3. GitHubリポジトリを接続
4. 設定:
   - **Name**: `dow-cloud-alert`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements_render.txt`
   - **Start Command**: `gunicorn render_server:app`
   - **Instance Type**: `Free`

#### 3-3. 環境変数を設定

Renderダッシュボード → Your Service → Environment で以下を追加:

| Key | Value | 説明 |
|-----|-------|------|
| `LINE_NOTIFY_TOKEN` | `取得したLINEトークン` | LINE通知用 |
| `LOCAL_CLIENT_URL` | `http://your-local-ip:5001/alert` | ローカルPC転送用（後で設定） |

---

### 4️⃣ ローカルPC環境セットアップ

```powershell
cd c:\Users\kanda\Desktop\PythonData\TradingViewWebhook

# パッケージインストール
pip install -r requirements_local.txt

# ffmpegインストール（音声再生に必要）
choco install ffmpeg
# または https://ffmpeg.org/download.html から手動インストール

# ローカルクライアント起動
python local_client.py
```

✅ 起動確認: ブラウザで `http://localhost:5001/test` にアクセス

---

### 5️⃣ ローカルPCを公開（ngrok）

Renderからローカルクライアントに通知を転送するため、ngrokでポート公開:

```powershell
# ngrokインストール後
ngrok http 5001
```

表示されるURL（例: `https://1234-abcd.ngrok-free.app`）を  
Renderの環境変数 `LOCAL_CLIENT_URL` に設定:
```
https://1234-abcd.ngrok-free.app/alert
```

---

### 6️⃣ TradingViewアラート設定

1. TradingViewチャートで「ダウ雲_V03」インジケーターを適用
2. 右上「アラート」→「アラートを作成」
3. 設定:
   - **条件**: `ダウ雲_V03` → `alert() function calls only`
   - **Webhook URL**: `https://your-render-app.onrender.com/webhook`
   - **メッセージ**: （Pine Scriptから自動送信されるJSON）
4. 「作成」をクリック

---

## 🧪 動作テスト

### クラウド + ローカル統合テスト

```powershell
# 1. ローカルクライアント起動
python local_client.py

# 2. ngrokで公開
ngrok http 5001
# URLをRenderのLOCAL_CLIENT_URL環境変数に設定

# 3. Renderサーバーにテストデータ送信
$json = @'
{
  "symbol":"USDJPY",
  "tf":"5",
  "time":1760621400000,
  "price":151.219,
  "clouds":[
    {"label":"5m","tf":"5m","gc":true,"fire_count":1,"max_reached":false,"thickness":1.22,"angle":-21.88,"elapsed":80},
    {"label":"15m","tf":"15m","gc":false,"fire_count":0,"max_reached":false,"thickness":0.11,"angle":-24.63,"elapsed":103},
    {"label":"1H","tf":"1H","gc":true,"fire_count":2,"max_reached":false,"thickness":0.28,"angle":1.55,"elapsed":95},
    {"label":"4H","tf":"4H","gc":false,"fire_count":0,"max_reached":false,"thickness":23.06,"angle":-12.85,"elapsed":2540}
  ]
}
'@

curl https://your-render-app.onrender.com/webhook -Method POST -ContentType "application/json" -Body $json
```

### 期待される動作

1. **LINE通知**: スマホに「短期雲 ゴールデンクロス (発火1回)」が届く
2. **デスクトップ通知**: PCにWindows Toast通知が表示
3. **音声再生**: `short_up.wav` が再生される
4. **Webダッシュボード**: https://your-render-app.onrender.com で状態確認

### ローカルクライアント単体テスト

```powershell
# ブラウザで以下にアクセス
http://localhost:5001/test
```

### Webダッシュボード確認

- **Render**: https://your-render-app.onrender.com

---

## 📊 Webダッシュボードの機能

- **リアルタイム更新**: 10秒ごとに自動更新
- **表形式表示**: 4つの雲（短期・中期・長期・超長期）の状態を一覧表示
- **視覚的表現**:
  - GC/DC方向（上昇/下降）
  - 発火回数（🔥マーク）
  - 最大発火数到達（MAXバッジ）
  - 雲厚み・角度
- **レスポンシブデザイン**: スマホ・タブレット対応

---

## 🔧 カスタマイズ

### 音量調整

`voice_config.json` を編集:
```json
{
  "volume": 0
}
```
- `0`: デフォルト
- `+6`: 2倍の音量
- `-6`: 半分の音量

### 通知メッセージのカスタマイズ

`render_server.py` の `analyze_clouds()` 関数を編集してメッセージをカスタマイズできます。

---

## ⚠️ トラブルシューティング

### 音声が再生されない

**原因**: ffmpegがインストールされていない

**解決策**:
```powershell
choco install ffmpeg
```

### LINE通知が届かない

**原因**: `LINE_NOTIFY_TOKEN` が設定されていない

**解決策**: Renderの環境変数を確認

### ローカルクライアントにデータが届かない

**原因**: `LOCAL_CLIENT_URL` が正しくない

**解決策**:
- ngrokが起動しているか確認
- Renderの環境変数のURLを確認
- ファイアウォール設定を確認

### Renderがスリープする

**原因**: 15分間アクセスなしで自動スリープ

**解決策**:
- 有料プラン（$7/月）にアップグレード
- https://cron-job.org/ で `/health` を定期実行

---

## 💰 コスト

- **Render無料枠**: 750時間/月（PostgreSQL込み）
- **LINE Notify**: 完全無料
- **VOICEVOX**: 完全無料
- **ngrok無料枠**: 1アカウント1トンネル

**合計: 完全無料で運用可能** 🎉

---

## 🚀 今後の機能追加予定

- [ ] 複数通貨ペアの並列表示
- [ ] 別インジケーターの統合
- [ ] カスタム発火条件の構築UI
- [ ] モバイルアプリ対応
- [ ] Discord/Slack通知対応
- [ ] バックテスト機能
- [ ] アラート履歴のエクスポート

---

## 📝 ライセンス

MIT License

---

## 🤝 サポート

問題が発生した場合は、以下を確認してください:

1. **Renderログ**: Renderダッシュボード → Your Service → Logs
2. **ローカルログ**: local_client.py 実行中のコンソール出力
3. **データベース確認**: `sqlite3 webhook_data.db "SELECT * FROM alerts LIMIT 10;"`

---

**作成日**: 2025年10月19日  
**バージョン**: 3.0.0  
**作成者**: Kanda
