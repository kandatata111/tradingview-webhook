# Render永続ストレージ設定ガイド

## 問題
デプロイの度にSQLiteデータベースが消えてしまい、TradingViewから新しいデータが送られるまで表が表示されない。

## 解決策
Render Diskを追加して、データベースを永続化する。

## 手順

### 方法1: render.yamlを使用（推奨）

1. **render.yamlがリポジトリに含まれていることを確認**
   - GitHubにプッシュ済み

2. **Render Dashboardで設定を同期**
   - https://dashboard.render.com/ にアクセス
   - 「tradingview-webhook」サービスを選択
   - 「Settings」→「Build & Deploy」
   - 「Blueprint」セクションで「Sync」をクリック
   
3. **Diskが自動作成される**
   - Name: webhook-data
   - Mount Path: /var/data
   - Size: 1GB

### 方法2: 手動でDiskを追加

1. **Render Dashboardにアクセス**
   - https://dashboard.render.com/
   - 「tradingview-webhook」サービスを選択

2. **Diskを追加**
   - サイドバーの「Disks」をクリック
   - 「New Disk」ボタンをクリック
   - 設定:
     - Name: `webhook-data`
     - Mount Path: `/var/data`
     - Size: `1 GB`（無料プランでは1GBまで）
   - 「Create」をクリック

3. **環境変数を設定**
   - サイドバーの「Environment」をクリック
   - 「Add Environment Variable」をクリック
   - Key: `PERSISTENT_STORAGE_PATH`
   - Value: `/var/data`
   - 「Save Changes」をクリック

4. **サービスを再デプロイ**
   - 「Manual Deploy」→「Deploy latest commit」

## 確認方法

1. **デプロイ後、ダッシュボードを開く**
   - https://tradingview-webhook-s5x1.onrender.com/

2. **データが表示されることを確認**

3. **もう一度デプロイする**
   - GitHubに何か変更をプッシュ
   - または「Manual Deploy」

4. **データが保持されていることを確認**
   - デプロイ後もすぐに表が表示される
   - TradingViewからの新しいデータを待つ必要がない

## トラブルシューティング

### Diskが作成されない
- Renderの無料プランでは1つまでDiskを作成可能
- 既に他のサービスでDiskを使用している場合は削除が必要

### データが保持されない
- 環境変数`PERSISTENT_STORAGE_PATH`が正しく設定されているか確認
- Render Logsで`DB_PATH`の値を確認:
  ```
  print(f"[INFO] Database path: {DB_PATH}")
  ```

### 既存データの移行
- 現在のデータベースは一時的なので、TradingViewから新しいデータが送られれば自動的に新しいDiskに保存される
- 4H足のデータが必要な場合は、4時間待つか、手動でデータを送信

## 料金
- Render Diskは**最初の1GBは無料**
- 1GB以上は有料（月額$0.25/GB）
- webhook_data.dbは通常数MB程度なので、1GBで十分

## 注意事項
- Diskを削除するとデータも消える
- Diskのバックアップは手動で行う必要がある
- 定期的にデータベースをローカルにバックアップすることを推奨
