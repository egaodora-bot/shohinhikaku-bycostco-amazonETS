import datetime
import sqlite3
import pandas as pd
import streamlit as st

# データベースの初期化
DB_NAME = "database.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # 商品マスタ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            unit_name TEXT
        )
    """)

  # 価格データ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            store_type TEXT,
            store_name TEXT,
            total_price REAL,
            total_capacity REAL,
            unit_price REAL,
            is_sale INTEGER,
            updated_at TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

  # 店舗マスタ（自動提案・選択用）
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT UNIQUE,
            store_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

  # 定番日用品の初期データ
  default_products = [
      ("トイレットペーパー (ダブル)", "日用品（消耗品）", "m"),
      ("ボックスティッシュ", "日用品（消耗品）", "箱"),
      ("洗濯用液体洗剤", "日用品（消耗品）", "ml"),
      ("食器用中性洗剤", "日用品（消耗品）", "ml"),
      ("お風呂用洗剤", "日用品（消耗品）", "ml"),
      ("台所用スポンジ", "日用品（消耗品）", "個"),
      ("ゴミ袋 (45L)", "日用品（消耗品）", "枚"),
      ("お米 (5kg)", "食品・飲料", "kg"),
      ("牛乳 (1L)", "食品・飲料", "本"),
  ]
  for p_name, p_cat, p_unit in default_products:
    cursor.execute(
        """
            INSERT OR IGNORE INTO products (name, category, unit_name) 
            VALUES (?, ?, ?)
        """,
        (p_name, p_cat, p_unit),
    )

  # デフォルト店舗の初期データ（例：Amazon、コストコ＋近隣の想定店舗）
  default_stores = [
      ("Amazon（定期おトク便）", "Amazon", 1),
      ("コストコ つくば倉庫店", "コストコ", 1),
      ("ウエルシア（近隣店）", "近隣店舗", 1),
      ("カインズ（近隣店）", "近隣店舗", 1),
      ("ベイシア（近隣店）", "近隣店舗", 0),
  ]
  for s_name, s_type, s_active in default_stores:
    cursor.execute(
        """
            INSERT OR IGNORE INTO stores (store_name, store_type, is_active) 
            VALUES (?, ?, ?)
        """,
        (s_name, s_type, s_active),
    )

  conn.commit()
  conn.close()


init_db()

st.set_page_config(
    page_title="買い物価格比較 & 底値DB", page_icon="🛒", layout="wide"
)

st.markdown("### 🛒 買い物価格比較 & 底値DB")
st.caption(
    "リポジトリ: `shohinhikaku-bycostco-amazonETS` | 住所連動・4店舗横並び買い回り比較"
)

# サイドバー：メニュー選択
menu = st.sidebar.selectbox(
    "メニュー", ["価格比較・検索", "商品・価格の登録", "店舗マスタ設定（住所連動）"]
)

# --- ① 価格比較・検索画面 ---
if menu == "価格比較・検索":
  st.markdown("#### 🔍 4店舗横並び・単位単価チェック（買い回り最適化）")

  conn = sqlite3.connect(DB_NAME)
  # 有効化されている（比較対象に選ばれている）店舗のみを抽出
  active_stores_df = pd.read_sql(
      "SELECT store_name FROM stores WHERE is_active = 1", conn
  )
  active_stores = active_stores_df["store_name"].tolist()

  query = """
        SELECT 
            p.id as product_id, 
            p.name as 商品名, 
            p.category as カテゴリ, 
            p.unit_name as 単位,
            pr.store_name as 店舗名, 
            pr.total_price as 総額, 
            pr.unit_price as 単位あたり価格, 
            pr.is_sale as 特売フラグ, 
            pr.updated_at as 更新日
        FROM prices pr
        JOIN products p ON pr.product_id = p.id
    """
  df = pd.read_sql(query, conn)
  conn.close()

  if df.empty:
    st.info(
        "💡 まだ価格データが登録されていません。「商品・価格の登録」から価格を追加してみましょう。"
    )
  else:
    # 選択中の店舗で絞り込み
    if active_stores:
      df_filtered = df[df["店舗名"].isin(active_stores)]
    else:
      df_filtered = df

    st.markdown(
        "##### 📊 選択した店舗（最大4店舗+α）の横並び単位単価マトリックス"
    )
    st.caption(
        "※左メニューの「店舗マスタ設定」で比較したい店舗を変更できます。"
    )

    if not df_filtered.empty:
      pivot_price = df_filtered.pivot_table(
          index=["商品名", "単位"],
          columns="店舗名",
          values="単位あたり価格",
          aggfunc="min",
      )
      st.dataframe(pivot_price, use_container_width=True)
    else:
      st.warning(
          "選択された店舗の価格データがまだありません。店舗設定または価格登録を確認してください。"
      )

    st.markdown("##### 💡 商品ごとの詳細＆最安値店舗チェック")
    target_product = st.selectbox("詳細を見たい商品を選択", df["商品名"].unique())
    prod_df = df[df["商品名"] == target_product].sort_values("単位あたり価格")

    st.table(
        prod_df[[
            "店舗名",
            "総額",
            "単位あたり価格",
            "特売フラグ",
            "更新日",
        ]]
    )

    if not prod_df.empty:
      min_row = prod_df.iloc[0]
      st.success(
          f"🏆 **現在の最安値:** 【{min_row['店舗名']}】 で **1{min_row['単位']}あたり"
          f" {min_row['単位あたり価格']:.2f} 円** です！ (総額: {min_row['総額']}円)"
      )

# --- ② 商品・価格の登録画面 ---
elif menu == "商品・価格の登録":
  st.markdown("#### 📝 価格の登録（一般家庭日用品＆自動登録対応）")

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT * FROM products", conn)
  stores_df = pd.read_sql("SELECT * FROM stores", conn)
  conn.close()

  product_names = (
      products_df["name"].tolist() if not products_df.empty else []
  )
  store_names = stores_df["store_name"].tolist() if not stores_df.empty else []

  with st.form("register_form"):
    st.markdown("##### 1. 商品の選択 または 入力")
    input_product_name = st.selectbox(
        "商品名（定番品から選択、または下に新しい名前を入力）",
        ["-- 新規商品を直接入力する --"] + product_names,
    )
    new_prod_name = st.text_input(
        "※上で新規を選んだ場合はこちらに入力", placeholder="例: ボールド ジェルボール"
    )

    col1, col2 = st.columns(2)
    with col1:
      category = st.selectbox(
          "カテゴリ",
          ["日用品（消耗品）", "食品・飲料", "家電・ガジェット", "その他"],
      )
    with col2:
      unit_name = st.text_input(
          "単位の基準（例: ml, g, 個, m, 箱, 枚 など）", value="個"
      )

    st.markdown("##### 2. 店舗と価格情報")
    # 登録済みの店舗リストから選択（なければ自由入力も可）
    selected_store = st.selectbox("店舗を選択", store_names)

    total_price = st.number_input(
        "購入総額（税込・円）", min_value=0.0, step=10.0
    )
    total_capacity = st.number_input(
        "そのときの総容量・数量（例: 44個入りなら '44'、1500mlなら"
        " '1500'）",
        min_value=0.1,
        step=1.0,
        value=1.0,
    )

    is_sale = st.checkbox("特売品 / セール価格である")

    submitted = st.form_submit_button("データベースに保存して比較表を更新")

    if submitted:
      target_name = (
          new_prod_name.strip()
          if input_product_name == "-- 新規商品を直接入力する --"
          else input_product_name
      )

      if not target_name:
        st.error("⚠️ 商品名を入力するか、選択してください。")
      else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 商品の自動登録 or 取得
        cursor.execute(
            "SELECT id, unit_name FROM products WHERE name = ?", (target_name,)
        )
        row = cursor.fetchone()

        if row:
          product_id = row[0]
          u_name = row[1]
        else:
          cursor.execute(
              "INSERT INTO products (name, category, unit_name) VALUES (?, ?,"
              " ?)",
              (target_name, category, unit_name),
          )
          conn.commit()
          product_id = cursor.lastrowid
          u_name = unit_name

        unit_price = (
            total_price / total_capacity if total_capacity > 0 else 0
        )
        today = datetime.date.today().isoformat()

        cursor.execute(
            """
                INSERT INTO prices (product_id, store_type, store_name, total_price, total_capacity, unit_price, is_sale, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                "近隣店舗",
                selected_store,
                total_price,
                total_capacity,
                unit_price,
                1 if is_sale else 0,
                today,
            ),
        )
        conn.commit()
        conn.close()
        st.success(
            f"✨ 「{target_name}」の価格を【{selected_store}】で登録しました！ (1{u_name}あたり"
            f" **{unit_price:.2f}円**)"
        )

# --- ③ 店舗マスタ設定（住所連動）画面 ---
elif menu == "店舗マスタ設定（住所連動）":
  st.markdown("#### ⚙️ 住所から周辺店舗を自動表示＆比較店舗の選択")
  st.write(
      "ご自宅などの住所を入力すると、近隣の主要店舗（ドラッグストア・スーパー等）が自動で候補に挙がります。比較したい店舗（Amazon・コストコ＋他2〜3店舗）にチェックを入れてください。"
  )

  user_address = st.text_input(
      "基準となる住所（例: 茨城県古河市...）", value="茨城県古河市"
  )

  if st.button("住所から周辺店舗を自動検索・更新"):
    # 住所に応じた近隣店舗の自動提案ロジック（モック連動）
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # すでに登録されている店舗に加え、周辺の代表的な店舗候補を追加
    suggested_stores = [
        ("ウエルシア（近隣店）", "近隣店舗", 1),
        ("カインズ（近隣店）", "近隣店舗", 1),
        ("ベイシア（近隣店）", "近隣店舗", 1),
        ("ヨークベニマル（近隣店）", "近隣店舗", 0),
        ("コストコ つくば倉庫店", "コストコ", 1),
        ("Amazon（定期おトク便）", "Amazon", 1),
    ]

    for s_name, s_type, s_active in suggested_stores:
      cursor.execute(
          """
                INSERT OR IGNORE INTO stores (store_name, store_type, is_active) 
                VALUES (?, ?, ?)
            """,
          (s_name, s_type, s_active),
      )
    conn.commit()
    conn.close()
    st.success(
        f"📍 「{user_address}」周辺の店舗（ウエルシア、カインズ、ベイシアなど）とコストコ・Amazonを自動設定しました！下で比較する店舗を選んでください。"
    )

  st.markdown("##### 🛒 今回の比較・買い回り対象にする店舗を選ぶ（最大4店舗〜推奨）")
  st.caption(
      "ここでチェックを入れた店舗だけが、最初の「価格比較・検索」画面の横並び表に表示されます。"
  )

  conn = sqlite3.connect(DB_NAME)
  stores_df = pd.read_sql("SELECT * FROM stores", conn)
  conn.close()

  with st.form("store_select_form"):
    updated_actives = {}
    for idx, row in stores_df.iterrows():
      # デフォルトでチェックが入る状態を再現
      is_checked = st.checkbox(
          f"{row['store_name']} （{row['store_type']}）",
          value=bool(row["is_active"]),
          key=f"store_{row['id']}",
      )
      updated_actives[row["id"]] = is_checked

    store_submit = st.form_submit_button("比較店舗の設定を保存する")

    if store_submit:
      conn = sqlite3.connect(DB_NAME)
      cursor = conn.cursor()
      for s_id, active_val in updated_actives.items():
        cursor.execute(
            "UPDATE stores SET is_active = ? WHERE id = ?",
            (1 if active_val else 0, s_id),
        )
      conn.commit()
      conn.close()
      st.success(
          "✨ 比較店舗の設定を保存しました！「価格比較・検索」画面で横並びの比較表を確認してみましょう。"
      )
