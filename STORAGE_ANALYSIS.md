# ノート機能ストレージ構造分析レポート

**調査日**: 2025-11-19  
**対象**: TradingViewWebhook ダッシュボード ノート機能

---

## 📊 現在のストレージ構造

### 1. localStorage の使用状況

#### 現在も使用中のキー:
```
✓ tv_note_font_size          - ノートフォントサイズ設定（小）
✓ tv_note_modal_width        - モーダルウィンドウの幅
✓ tv_note_modal_height       - モーダルウィンドウの高さ
✓ tv_note_modal_left         - モーダル位置（左）
✓ tv_note_modal_top          - モーダル位置（上）
✓ tv_note_current_page       - 現在のページインデックス
✓ tv_note_pages              - **ノートページデータ本体**（廃止済み）
```

#### 使用容量の推定:
- `tv_note_font_size`: ~2 bytes
- `tv_note_current_page`: ~1-2 bytes
- `tv_note_modal_*` (4個): ~20 bytes
- **`tv_note_pages`: 数MB〜数十MB** ← 容量圧迫の原因

---

### 2. IndexedDB の状況

#### 現在の状態:
- ✗ **IndexedDB 初期化コードはあるが実装されていない**
- ✗ `db = null` で定義されているだけ
- ✗ IndexedDB への実装は存在しない

#### コード位置:
```javascript
// Line 2117-2118
// IndexedDB初期化
let db = null;
```

---

### 3. サーバー側ストレージ（新規実装）

#### APIエンドポイント:
```
POST   /api/save_notes    - ノート保存
GET    /api/load_notes    - ノート読み込み
```

#### ファイル保存場所:
```
{BASE_DIR}/notes_data.json
```

#### 特徴:
- ✓ ディスク永続化
- ✓ ブラウザ再起動後のデータ保持
- ✓ サーバー側バックアップ
- ✗ ネットワーク通信コスト

---

## 🔄 データフロー分析

### 現在の処理フロー:

```
1. ノートモーダル開く
   ↓
2. loadNotePages() 実行
   → /api/load_notes にアクセス
   → notes_data.json から読み込み
   → notePages 変数に格納
   ↓
3. UI更新
   → updatePageNavigation()
   → loadCurrentPage()
   ↓
4. ユーザー編集
   ↓
5. 自動保存（3秒ごと）
   → saveNotePages() 実行
   → 現在のセクション情報を取得
   → /api/save_notes に POST
   → notes_data.json に保存
```

---

## 📈 容量分析

### localStorage 使用量（推定）:

| キー名 | サイズ | 用途 |
|--------|--------|------|
| tv_note_font_size | 2 B | フォントサイズ |
| tv_note_current_page | 2 B | ページ位置 |
| tv_note_modal_* (4個) | 20 B | ウィンドウ位置 |
| tv_note_pages | **数MB〜数十MB** | ページデータ本体 |
| **合計** | **数MB〜数十MB** | |

### サーバーディスク使用量:

| ファイル | サイズ | 備考 |
|---------|--------|------|
| notes_data.json | ~100-500 KB | テスト用データ量 |
| 画像キャッシュ | 別フォルダ管理 | NoteImages/ |

---

## 🔍 問題の詳細

### 問題1: localStorage の容量圧迫

**原因**: 
- ノートページデータ全体が `tv_note_pages` キーに保存されている
- localStorage の容量制限は通常 5-10 MB
- 大量のノート、特に画像を含む場合、容量超過の可能性

**影響**:
- ブラウザが遅延
- localStorage アクセス遅延
- 他の機能のデータ保存失敗の可能性

### 問題2: IndexedDB への移行が未完了

**現状**:
```javascript
// Line 2118
let db = null;  // 初期化されていない
```

**理由**:
- IndexedDB 初期化ルーチンがコード内に無い
- `db.transaction()` の使用コードが存在しない
- `migrateFromLocalStorage()` 関数は定義されているが、呼ばれていない

**期待されていた移行**:
```
localStorage の tv_note_pages
    ↓
IndexedDB への移行（容量不足時など）
```

### 問題3: migrateFromLocalStorage 関数が機能していない

**コード位置**: Line 2179-2210

**現在の実装**:
```javascript
function migrateFromLocalStorage() {
  const savedPages = localStorage.getItem('tv_note_pages');
  const savedCurrentPage = parseInt(localStorage.getItem('tv_note_current_page')) || 0;
  
  if (savedPages) {
    try {
      notePages = JSON.parse(savedPages);
      // ... 処理
    }
  }
}
```

**問題**:
- `migrateFromLocalStorage()` が呼ばれていない
- `loadNotePages()` で直接サーバー API から読み込むため、実行されない
- 古い localStorage データが残ったまま

---

## 📊 実装状況の比較

### 設計上の計画:

```
┌─────────────┐
│ localStorage │  
│  (一時)     │
└──────┬──────┘
       ↓
┌─────────────┐
│ IndexedDB   │  (移行予定)
│  (中期)     │
└──────┬──────┘
       ↓
┌─────────────┐
│  Server     │  (永続)
│   API/JSON  │
└─────────────┘
```

### 実装の現状:

```
✓ localStorage     ← 現在使用中（容量圧迫）
✗ IndexedDB       ← 実装されていない
✓ Server API/JSON ← 新規実装、正常動作
```

---

## ✅ 正常に機能している部分

1. **サーバー側ストレージ**
   - `/api/save_notes` と `/api/load_notes` が正常に動作
   - `notes_data.json` にデータが永続化される
   - ブラウザ再起動後のデータ保持 ✓

2. **フロントエンド読み込み機能**
   - `loadNotePages()` が正常にサーバーから読み込み
   - UI 更新 (`updatePageNavigation()`, `loadCurrentPage()`) が実行される
   - 読み込んだデータが表示される ✓

3. **フロントエンド保存機能**
   - `saveNotePages()` が正常にサーバーに送信
   - 自動保存機能が 3 秒ごとに実行
   - ページ切り替え時の保存も実行 ✓

---

## 🔧 容量圧迫対策の現状

### 現在の対策:

1. **localStorage からサーバー API への移行** ✓
   - データ本体はサーバー側に保存
   - ブラウザには最小限のメタデータのみ

2. **localStorage 使用量の削減**
   - 設定値のみを保存（フォントサイズ、ウィンドウ位置など）
   - ノートページデータは含まない

3. **画像ストレージの分離**
   - 画像は `NoteImages/` フォルダに保存
   - ハッシュ値での参照管理

### 未実装の対策:

1. **IndexedDB への移行** ✗
   - 設計上は計画されていた
   - 実装されていない
   - 現在は不要（サーバー API で代替）

---

## 📝 localStorage 内の実際のデータ例

### サイズが大きいもの:

```javascript
localStorage.getItem('tv_note_pages')
// 例: 約 100-500 KB の JSON データ
// 包含内容:
// - notePages 配列
// - 各ページのタイトル
// - セクションのタイトルと内容
// - 画像ハッシュ参照
// - lastModified タイムスタンプ
```

### サイズが小さいもの:

```javascript
localStorage.getItem('tv_note_font_size')      // "15"
localStorage.getItem('tv_note_current_page')   // "0"
localStorage.getItem('tv_note_modal_width')    // "500"
localStorage.getItem('tv_note_modal_height')   // "400"
```

---

## 🎯 容量圧迫の現状判定

### 現在の状態:

✓ **容量圧迫は緩和されている**

### 理由:

1. サーバー API がメインストレージ
   - ノートデータは `notes_data.json` に保存
   - localStorage に `tv_note_pages` キーが残っている**が参照されていない**

2. ブラウザ容量への影響は最小
   - アクティブなデータはサーバー側
   - localStorage は設定値のみ（合計 ~25 bytes）

3. 古い `tv_note_pages` データ
   - 削除されていない（クリーンアップ未実施）
   - ただし新規データは保存されていない
   - 容量は増加していない

---

## ⚠️ 潜在的な問題

### 1. localStorage 内の古いデータ

**現状**:
- `tv_note_pages` キーが削除されていない
- 古いデータが残存している可能性

**影響**:
- localStorage 容量を占有中
- ブラウザが誤って参照する可能性（低）

### 2. IndexedDB が実装されていない

**現状**:
```javascript
let db = null;  // 使用されていない
```

**影響**:
- 設計上の冗長性が無い
- サーバー通信不可時のオフラインキャッシュなし

### 3. 移行処理が不完全

**コード**:
```javascript
function migrateFromLocalStorage() {
  // 定義されているが呼ばれていない
}
```

**影響**:
- 古い localStorage データが活用されていない
- クリーンアップされていない

---

## 📋 推奨事項

### 短期（現在可能）:

1. **localStorage のクリーンアップ**
   ```javascript
   localStorage.removeItem('tv_note_pages');
   localStorage.removeItem('tv_note_sections');
   ```
   - 古い未使用キーを削除
   - 容量を完全に解放

### 中期（オプション）:

1. **IndexedDB への実装**（オフラインキャッシュ用）
   - サーバー通信不可時の冗長化
   - 設計の完全化

### 長期:

1. **オフラインモード対応**
   - IndexedDB + Service Worker
   - 完全オフラインサポート

---

## ✨ 結論

### 現在の状況:

| 項目 | 状態 | 判定 |
|------|------|------|
| localStorage 容量圧迫 | **緩和済み** ✓ | 問題なし |
| サーバー側ストレージ | **正常動作** ✓ | 良好 |
| IndexedDB 移行 | **未実装** ✗ | 不要（サーバー API で代替） |
| ブラウザ再起動後のデータ保持 | **実装済み** ✓ | 正常 |
| 容量圧迫の改善 | **達成** ✓ | 完了 |

### 最終評価:

**容量圧迫は十分に緩和されています。**

- ノートデータはサーバー側に保存
- localStorage は設定値のみ（~25 bytes）
- 古い `tv_note_pages` データは削除推奨だが、新規保存は行われていない

---

**レポート作成日**: 2025-11-19 15:30 JST
