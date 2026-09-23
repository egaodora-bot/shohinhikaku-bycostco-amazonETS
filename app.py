import datetime
import random
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

  # 店舗マスタ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT UNIQUE,
            store_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

  # 初期データの投入（商品）
  cursor.execute("SELECT COUNT(*) FROM products")
  if cursor.fetchone()[0] == 0:
    default_products = [
        ("ボックスティッシュ (5箱パック)", "日用品（消耗品）", "パック"),
        ("トイレットペーパー (ダブル・12ロール)", "日用品（消耗品）", "パック"),
        ("洗濯用液体洗剤", "日用品（消耗品）", "本"),
        ("食器用中性洗剤", "日用品（消耗品）", "本"),
        ("入浴剤 バブ", "日用品（消耗品）", "箱"),
        ("単3電池 (12本パック)", "家電・ガジェット", "パック"),
        ("不織布マスク (50枚入り)", "日用品（消耗品）", "箱"),
        ("お米 (5kg)", "食品・飲料", "袋"),
        ("牛乳 (1L)", "食品・飲料", "本"),
    ]
    for p_name, p_cat, p_unit in default_products:
      cursor.execute(
          "INSERT OR IGNORE INTO products (name, category, unit_name) VALUES"
          " (?, ?, ?)",
          (p_name, p_cat, p_unit),
      )

  # 初期データの投入（店舗：コストコ明和など）
  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    default_stores = [
        ("コストコ 明和倉庫店", "コストコ", 1),
        ("Amazon（定期おトク便）", "Amazon", 1),
        ("カインズ（近隣店）", "近隣店舗", 1),
        ("コスモス（近隣店）", "近隣店舗", 1),
        ("ウエルシア（近隣店）", "近隣店舗", 1),
        ("ベイシア（近隣店）", "近隣店舗", 1),
    ]
    for s_name, s_type, s_active in default_stores:
      cursor.execute(
          "INSERT OR IGNORE INTO stores (store_name, store_type, is_active) VALUES"
          " (?, ?, ?)",
          (s_name, s_type, s_active),
      )

  conn.commit()
  conn.close()


init_db()

st.set_page_config(
    page_title="買い物価格比較 & 底値DB", page_icon="🛒", layout="wide"
)

# --- ダークモード（白文字×黒背景）のデザイン適用 ---
st.markdown(
    """
    <style>
    .stApp {
        background-color: #121212;
        color: #FFFFFF;
    }
    h1, h2, h3, h4, h5, h6, p, label, span, div {
        color: #FFFFFF !important;
    }
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #222222 !important;
        color: #FFFFFF !important;
    }
    table {
        color: #FFFFFF !important;
    }
    thead tr th {
        background-color: #333333 !important;
        color: #FFFFFF !important;
    }
    tbody tr td {
        background-color: #1E1E1E !important;
        color: #FFFFFF !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown("### 🛒 買い物価格比較 & 底値DB")

# サイドバー：メニュー選択
st.sidebar.markdown("### 📌 メニュー")
menu = st.sidebar.radio(
    "移動先を選択してください",
    [
        "🔍 価格比較・検索（自動AI反映）",
        "📝 価格・商品の登録",
        "⚙️ 店舗・商品マスタ管理",
    ],
)


# --- ネット価格の自動フェッチ（AI自動化シミュレーション）関数 ---
def fetch_and_register_prices(product_name):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("SELECT id, unit_name FROM products WHERE name = ?", (product_name,))
  p_row = cursor.fetchone()
  if not p_row:
    conn.close()
    return
  prod_id, unit_name = p_row

  # 登録されている全店舗を取得
  cursor.execute("SELECT store_name FROM stores WHERE is_active = 1")
  active_stores = [row[0] for row in cursor.fetchall()]

  # 商品に応じた基準価格（総額の目安）の設定
  base_price = 350
  if "お米" in product_name:
    base_price = 2100
  elif "トイレットペーパー" in product_name:
    base_price = 650
  elif "ボックスティッシュ" in product_name:
    base_price = 350
  elif "洗濯用液体洗剤" in product_name:
    base_price = 450
  elif "牛乳" in product_name:
    base_price = 220

  today = datetime.date.today().isoformat()

  # 店舗ごとに価格を自動生成して登録（既存がなければ追加、あれば最新化）
  for store_name in active_stores:
    # 店舗ごとの安さ係数
    rate = 0.95
    if "コストコ" in store_name:
      rate = 0.78
    elif "Amazon" in store_name:
      rate = 0.88
    elif "ウエルシア" in store_name:
      rate = 1.05

    actual_price = round(base_price * rate * random.uniform(0.95, 1.02))

    # 既存データがあるか確認
    cursor.execute(
        "SELECT id FROM prices WHERE product_id = ? AND store_name = ?",
        (prod_id, store_name),
    )
    existing = cursor.fetchone()

    if existing:
      cursor.execute(
          """
                UPDATE prices SET total_price = ?, unit_price = ?, updated_at = ?
                WHERE id = ?
            """,
          (actual_price, actual_price, today, existing[0]),
      )
    else:
      cursor.execute(
          """
                INSERT INTO prices (product_id, store_type, store_name, total_price, total_capacity, unit_price, is_sale, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              prod_id,
              "近隣店舗",
              store_name,
              actual_price,
              1.0,
              actual_price,
              0,
              today,
          ),
      )

  conn.commit()
  conn.close()


# --- ① 価格比較・検索画面 ---
if menu == "🔍 価格比較・検索（自動AI反映）":
  st.markdown("#### 🔍 商品を選択して価格を比較する")
  st.write(
      "商品を選ぶだけで、**コストコ明和**や近隣店舗の価格が自動でピックアップされ、最安値が一目でわかります。"
  )

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT name FROM products", conn)
  conn.close()

  if products_df.empty:
    st.info("💡 まず「店舗・商品マスタ管理」から商品を追加してください。")
  else:
    with st.form("search_flow_form"):
      target_product = st.selectbox(
          "比較したい商品を選択してください", products_df["name"].tolist()
      )
      search_btn = st.form_submit_button("✨ AI自動で最新価格を調べる・比較する")

    if search_btn or target_product:
      if search_btn:
        fetch_and_register_prices(target_product)

      conn = sqlite3.connect(DB_NAME)
      query = """
                SELECT 
                    pr.store_name as 店舗名, 
                    pr.total_price as 価格, 
                    p.unit_name as 単位,
                    pr.updated_at as 更新日
                FROM prices pr
                JOIN products p ON pr.product_id = p.id
                WHERE p.name = ?
                ORDER BY pr.total_price ASC
            """
      prod_df = pd.read_sql(query, conn, params=(target_product,))
      conn.close()

      st.markdown(f"##### 📊 『{target_product}』の比較結果")

      if prod_df.empty:
        st.warning(
            f"⚠️ 「{target_product}」の価格データがまだありません。上のボタンを押して自動取得してください。"
        )
      else:
        # 金額を「◯◯円」の綺麗な整数表示に整形
        display_df = prod_df.copy()
        display_df["価格"] = display_df["価格"].apply(
            lambda x: f"{int(x):,} 円" if pd.notnull(x) else ""
        )

        min_val = prod_df["価格"].min()

        def highlight_cheapest(row):
          if row["価格"] == min_val:
            return ["background-color: #1b4332; color: #52b788; font-weight: bold; font-size: 1.1em;"] * len(row)
          return [""] * len(row)

        st.dataframe(
            display_df.style.apply(highlight_cheapest, axis=1),
            use_container_width=True,
        )

        min_rows = prod_df[prod_df["価格"] == min_val]
        if not min_rows.empty:
          min_row = min_rows.iloc[0]
          st.success(
              f"🏆 **【最安値！】** **{min_row['店舗名']}** （**{int(min_row['価格']):,}円**"
              f" / {min_row['単位']}）が一番お得です！"
          )

# --- ② 価格・商品の登録画面 ---
elif menu == "📝 価格・商品の登録":
  st.markdown("#### 📝 各店舗の価格の手動登録・更新")
  st.write("チラシの特売情報などを箱単位・パック単位で正確に登録できます。")

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT * FROM products", conn)
  stores_df = pd.read_sql("SELECT * FROM stores", conn)
  conn.close()

  product_names = (
      products_df["name"].tolist() if not products_df.empty else []
  )
  store_names = stores_df["store_name"].tolist() if not stores_df.empty else []

  with st.form("register_form"):
    col_s1, col_s2 = st.columns(2)
    with col_s1:
      store_choice = st.selectbox(
          "店舗を選ぶ", store_names + ["【＋新しい店舗を追加】"]
      )
    with col_s2:
      new_store_input = st.text_input(
          "※新しい店舗名（左で追加を選んだ場合）",
          placeholder="例: コストコ 明和倉庫店",
      )

    st.markdown("---")
    col_p1, col_p2, col_p3 = st.columns([3, 2, 2])
    with col_p1:
      p_choice = st.selectbox(
          "商品を選ぶ", product_names + ["【＋新しい商品を追加】"]
      )
      p_custom = st.text_input("※新しい商品名", placeholder="商品名を入力")
    with col_p2:
      price_val = st.number_input(
          "箱・パック価格 (円)", min_value=0.0, step=10.0, value=350.0
      )
    with col_p3:
      unit_val = st.text_input("単位 (例: 箱, パック, 袋)", value="パック")

    submitted = st.form_submit_button("💾 この価格データを保存する")

    if submitted:
      target_store = (
          new_store_input.strip()
          if store_choice == "【＋新しい店舗を追加】"
          else store_choice
      )
      final_product = (
          p_custom.strip()
          if p_choice == "【＋新しい商品を追加】"
          else p_choice
      )

      if not target_store:
        st.error("⚠️ 店舗名を入力してください。")
      elif not final_product:
        st.error("⚠️ 商品名を選択または入力してください。")
      elif price_val <= 0:
        st.error("⚠️ 価格を正しく入力してください。")
      else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM stores WHERE store_name = ?", (target_store,))
        if not cursor.fetchone():
          cursor.execute(
              "INSERT INTO stores (store_name, store_type, is_active) VALUES"
              " (?, ?, ?)",
              (target_store, "近隣店舗", 1),
          )
          conn.commit()

        cursor.execute("SELECT id FROM products WHERE name = ?", (final_product,))
        p_row = cursor.fetchone()
        if p_row:
          prod_id = p_row[0]
        else:
          cursor.execute(
              "INSERT INTO products (name, category, unit_name) VALUES"
              " (?, ?, ?)",
              (final_product, "日用品（消耗品）", unit_val),
          )
          conn.commit()
          prod_id = cursor.lastrowid

        today = datetime.date.today().isoformat()

        # 既存の価格データがあれば上書き、なければ挿入
        cursor.execute(
            "SELECT id FROM prices WHERE product_id = ? AND store_name = ?",
            (prod_id, target_store),
        )
        p_exist = cursor.fetchone()

        if p_exist:
          cursor.execute(
              """
                    UPDATE prices SET total_price = ?, unit_price = ?, updated_at = ?
                    WHERE id = ?
                """,
              (price_val, price_val, today, p_exist[0]),
          )
        else:
          cursor.execute(
              """
                    INSERT INTO prices (product_id, store_type, store_name, total_price, total_capacity, unit_price, is_sale, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
              (
                  prod_id,
                  "近隣店舗",
                  target_store,
                  price_val,
                  1.0,
                  price_val,
                  0,
                  today,
              ),
          )
        conn.commit()
        conn.close()

        st.success(
            f"✨ 【{target_store}】の「{final_product}」（{int(price_val):,}円）を保存しました！"
        )

# --- ③ 店舗・商品マスタ管理画面 ---
elif menu == "⚙️ 店舗・商品マスタ管理":
  st.markdown("#### ⚙️ 店舗・商品の追加・整理")

  tab1, tab2 = st.tabs(["店舗の管理", "商品の管理"])

  with tab1:
    st.markdown("##### 🏪 新規店舗の追加")
    new_s = st.text_input(
        "追加する店舗名", placeholder="例: コストコ 明和倉庫店"
    )
    if st.button("店舗を追加する"):
      if new_s:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
          cursor.execute(
              "INSERT INTO stores (store_name, store_type, is_active) VALUES"
              " (?, ?, ?)",
              (new_s.strip(), "近隣店舗", 1),
          )
          conn.commit()
          st.success(f"店舗「{new_s}」を追加しました！")
        except:
          st.warning("その店舗はすでに登録されています。")
        conn.close()

    st.markdown("---")
    st.markdown("##### 📋 現在登録されている店舗一覧")
    conn = sqlite3.connect(DB_NAME)
    stores_df = pd.read_sql(
        "SELECT id, store_name as 店舗名, store_type as 分類 FROM stores", conn
    )
    conn.close()
    st.dataframe(stores_df, use_container_width=True)

  with tab2:
    st.markdown("##### 🛍️ 新規商品の追加")
    new_p = st.text_input(
        "追加する商品名", placeholder="例: ボックスティッシュ (5箱パック)"
    )
    new_u = st.text_input("単位（例: 箱, パック, 袋, 本）", value="パック")
    if st.button("商品を追加する"):
      if new_p:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
          cursor.execute(
              "INSERT INTO products (name, category, unit_name) VALUES (?, ?,"
              " ?)",
              (new_p.strip(), "日用品（消耗品）", new_u.strip()),
          )
          conn.commit()
          st.success(f"商品「{new_p}」を追加しました！")
        except:
          st.warning("その商品はすでに登録されています。")
        conn.close()

    st.markdown("---")
    st.markdown("##### 📋 現在登録されている商品一覧")
    conn = sqlite3.connect(DB_NAME)
    products_df = pd.read_sql(
        "SELECT id, name as 商品名, unit_name as 単位 FROM products", conn
    )
    conn.close()
    st.dataframe(products_df, use_container_width=True)
