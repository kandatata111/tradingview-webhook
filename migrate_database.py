"""
データベースマイグレーション: topPrice/bottomPrice カラムを追加
"""
import os
import sys

# PostgreSQL用（本番環境）
def migrate_postgresql():
    import psycopg2
    from urllib.parse import urlparse
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL環境変数が設定されていません")
        return False
    
    # URLをパース
    url = urlparse(database_url)
    
    try:
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            user=url.username,
            password=url.password,
            database=url.path[1:]
        )
        c = conn.cursor()
        
        print("🔧 PostgreSQLデータベースを更新中...")
        
        # 各時間足にtopPriceとbottomPriceを追加
        columns_to_add = [
            "cloud_5m_topPrice REAL DEFAULT 0",
            "cloud_5m_bottomPrice REAL DEFAULT 0",
            "cloud_15m_topPrice REAL DEFAULT 0",
            "cloud_15m_bottomPrice REAL DEFAULT 0",
            "cloud_1h_topPrice REAL DEFAULT 0",
            "cloud_1h_bottomPrice REAL DEFAULT 0",
            "cloud_4h_topPrice REAL DEFAULT 0",
            "cloud_4h_bottomPrice REAL DEFAULT 0"
        ]
        
        for column in columns_to_add:
            try:
                c.execute(f"ALTER TABLE current_states ADD COLUMN {column}")
                print(f"✅ 追加: {column.split()[0]}")
            except Exception as e:
                if 'already exists' in str(e) or 'duplicate column' in str(e):
                    print(f"⏭️  既存: {column.split()[0]}")
                else:
                    print(f"❌ エラー: {column.split()[0]} - {e}")
        
        conn.commit()
        conn.close()
        print("✅ PostgreSQLデータベースの更新完了")
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

# SQLite用（ローカル環境）
def migrate_sqlite():
    import sqlite3
    
    try:
        conn = sqlite3.connect('webhook_data.db')
        c = conn.cursor()
        
        print("🔧 SQLiteデータベースを更新中...")
        
        # 各時間足にtopPriceとbottomPriceを追加
        columns_to_add = [
            "cloud_5m_topPrice REAL DEFAULT 0",
            "cloud_5m_bottomPrice REAL DEFAULT 0",
            "cloud_15m_topPrice REAL DEFAULT 0",
            "cloud_15m_bottomPrice REAL DEFAULT 0",
            "cloud_1h_topPrice REAL DEFAULT 0",
            "cloud_1h_bottomPrice REAL DEFAULT 0",
            "cloud_4h_topPrice REAL DEFAULT 0",
            "cloud_4h_bottomPrice REAL DEFAULT 0"
        ]
        
        for column in columns_to_add:
            try:
                c.execute(f"ALTER TABLE current_states ADD COLUMN {column}")
                print(f"✅ 追加: {column.split()[0]}")
            except Exception as e:
                if 'duplicate column' in str(e):
                    print(f"⏭️  既存: {column.split()[0]}")
                else:
                    print(f"❌ エラー: {column.split()[0]} - {e}")
        
        conn.commit()
        conn.close()
        print("✅ SQLiteデータベースの更新完了")
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("データベースマイグレーション")
    print("=" * 60)
    
    if 'DATABASE_URL' in os.environ:
        print("\n本番環境（PostgreSQL）を検出")
        success = migrate_postgresql()
    else:
        print("\nローカル環境（SQLite）を検出")
        success = migrate_sqlite()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ マイグレーション成功")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ マイグレーション失敗")
        print("=" * 60)
        sys.exit(1)
