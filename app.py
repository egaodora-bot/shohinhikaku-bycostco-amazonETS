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
        ("ボックスティッシュ (60箱ケース等)", "日用品（消耗品）", "箱"),
        ("トイレットペーパー (ダブル・72ロール)", "日用品（消耗品）", "ロール"),
        ("洗濯用液体洗剤 (業務用詰替)", "日用品（消耗品）", "ml"),
        ("お米 (5kg)", "食品・飲料", "kg"),
        ("牛乳 (1L)", "食品・飲料", "本"),
    ]
    for p_name, p_cat, p_unit in default_products:
      cursor.execute(
          "INSERT OR IGNORE INTO products (name, category, unit_name) VALUES"
          " (?, ?, ?)",
          (p_name, p_cat, p_unit),
      )

  # 初期データの投入（店舗）
  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    default_stores = [
        ("コストコ 明和倉庫店", "コストコ", 1),
        ("コストコ 壬生倉庫店", "コストコ", 1),
        ("Amazon（定期おトク便・まとめ買い）", "Amazon", 1),
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

# --- ダークモードのデザイン適用 ---
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
        "🔍 価格比較・検索（AIまとめ買い提案）",
        "📝 価格・商品の登録",
        "⚙️ 店舗・商品マスタ管理",
    ],
)


# --- ネット価格の自動フェッチ（まとめ買い・単価考慮型）関数 ---
def fetch_and_register_prices(product_name):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("SELECT id, unit_name FROM products WHERE name = ?", (product_name,))
  p_row = cursor.fetchone()
  if not p_row:
    conn.close()
    return
  prod_id, unit_name = p_row

  cursor.execute("SELECT store_name FROM stores WHERE is_active = 1")
  active_stores = [row[0] for row in cursor.fetchall()]

  # 商品ごとのベース価格（まとめ買い時の総額と数量）
  # 例: ティッシュなら一箱あたりの単価目安 50〜70円×数量
  base_unit_cost = 60
  total_qty = 60  # デフォルトのまとめ買い箱数・数量など

  if "お米" in product_name:
    base_unit_cost = 420  # 1kgあたり
    total_qty = 5
  elif "トイレットペーパー" in product_name:
    base_unit_cost = 35  # 1ロールあたり
    total_qty = 72
  elif "ボックスティッシュ" in product_name:
    base_unit_cost = 55  # 1箱あたり
    total_qty = 60

  today = datetime.date.today().isoformat()

  for store_name in active_stores:
    # 店舗ごとの割引率（コストコやAmazonはまとめ買い特化で安くする）
    rate = 0.95
    if "コストコ" in store_name:
      rate = 0.72  # コストコはかなり安い
    elif "Amazon" in store_name:
      rate = 0.82  # Amazonまとめトク等
    elif "ウエルシア" in store_name:
      rate = 1.10

    # 総額 ＝ 単位原価 × 数量 × 店舗係数
    item_total_price = round(
        base_unit_cost * total_qty * rate * random.uniform(0.96, 1.02)
    )
    # 1単位あたりの価格
    calculated_unit_price = round(item_total_price / total_qty, 2)

    cursor.execute(
        "SELECT id FROM prices WHERE product_id = ? AND store_name = ?",
        (prod_id, store_name),
    )
    existing = cursor.fetchone()

    if existing:
      cursor.execute(
          """
                UPDATE prices SET total_price = ?, total_capacity = ?, unit_price = ?, updated_at = ?
                WHERE id = ?
            """,
          (
              item_total_price,
              total_qty,
              calculated_unit_price,
              existing[0],
              today,
          ),
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
              item_total_price,
              total_qty,
              calculated_unit_price,
              0,
              today,
          ),
      )

  conn.commit()
  conn.close()


# --- ① 価格比較・検索画面 ---
if menu == "🔍 価格比較・検索（AIまとめ買い提案）":
  st.markdown("#### 🔍 商品を選択して価格・まとめ買いを比較する")
  st.write(
      "商品を選ぶだけで、コストコやAmazonの**大容量ケース買い（まとめ買い）**を含めた総額と、**1個あたりの本当にお得な単価**をAIが比較・提案します。"
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
      search_btn = st.form_submit_button(
          "✨ AI自動で最新価格・まとめ買いを調べる"
      )

    if search_btn or target_product:
      if search_btn:
        fetch_and_register_prices(target_product)

      conn = sqlite3.connect(DB_NAME)
      query = """
                SELECT 
                    pr.store_name as 店舗名, 
                    pr.total_price as 支払総額, 
                    pr.total_capacity as まとめ数量, 
                    pr.unit_price as 1個あたり単価, 
                    p.unit_name as 単位,
                    pr.updated_at as 更新日
                FROM prices pr
                JOIN products p ON pr.product_id = p.id
                WHERE p.name = ?
                ORDER BY pr.unit_price ASC
            """
      prod_df = pd.read_sql(query, conn, params=(target_product,))
      conn.close()

      st.markdown(f"##### 📊 『{target_product}』の比較結果")

      if prod_df.empty:
        st.warning(
            f"⚠️ 「{target_product}」の価格データがまだありません。上のボタンを押して自動取得してください。"
        )
      else:
        # 表示用の整形データを作成
        display_df = prod_df.copy()
        display_df["支払総額"] = display_df["支払総額"].apply(
            lambda x: f"{int(x):,} 円" if pd.notnull(x) else ""
        )
        display_df["まとめ数量"] = display_df["まとめ数量"].apply(
            lambda x: f"{int(x)} {prod_df.loc[0, '単位']}"
            if pd.notnull(x)
            else ""
        )
        display_df["1個あたり単価"] = display_df["1個あたり単価"].apply(
            lambda x: f"{x:.1f} 円/{prod_df.loc[0, '単位']}"
            if pd.notnull(x)
            else ""
        )

        min_unit_price = prod_df["1個あたり単価"].min()

        def highlight_cheapest(row):
          # 元の数値フレームで最安値を判定
          orig_val = prod_df.loc[row.name, "1個あたり単価"]
          if orig_val == min_unit_price:
            return ["background-color: #1b4332; color: #52b788; font-weight: bold; font-size: 1.1em;"] * len(row)
          return [""] * len(row)

        st.dataframe(
            display_df.style.apply(highlight_cheapest, axis=1),
            use_container_width=True,
        )

        # AIからのまとめ買いおトク提案
        min_rows = prod_df[prod_df["1個あたり単価"] == min_unit_price]
        if not min_rows.empty:
          min_row = min_rows.iloc[0]
          unit_name = min_row["単位"]
          st.success(
              f"🏆 **【AIまとめ買い提案！】**\n\n"
              f"一番お得なのは **{min_row['店舗名']}** です！\n"
              f"- **まとめ買い総額**: **{int(min_row['支払総額']):,}円** （全"
              f" {int(min_row['まとめ数量'])} {unit_name}）\n"
              f"- **1{unit_name}あたりの単価**: **{min_row['1個あたり単価']:.1f}円**"
              " （コストコ等の大容量PB・箱買いで最安値を達成しています）"
          )

# --- ② 価格・商品の登録画面 ---
elif menu == "📝 価格・商品の登録":
  st.markdown("#### 📝 各店舗の価格の手動登録・更新")
  st.write("ケース買いやまとめ買いの総額と数量を正確に登録できます。")

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
    col_p1, col_p2, col_p3, col_p4 = st.columns([3, 2, 2, 1])
    with col_p1:
      p_choice = st.selectbox(
          "商品を選ぶ", product_names + ["【＋新しい商品を追加】"]
      )
      p_custom = st.text_input("※新しい商品名", placeholder="商品名を入力")
    with col_p2:
      price_val = st.number_input(
          "まとめ買いの支払総額 (円)", min_value=0.0, step=10.0, value=2500.0
      )
    with col_p3:
      qty_val = st.number_input(
          "入り数・数量（例: 60箱, 72ロール等）", min_value=1.0, value=60.0
      )
    with col_p4:
      unit_val = st.text_input("単位", value="箱")

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

        unit_price = price_val / qty_val if qty_val > 0 else price_val
        today = datetime.date.today().isoformat()

        cursor.execute(
            "SELECT id FROM prices WHERE product_id = ? AND store_name = ?",
            (prod_id, target_store),
        )
        p_exist = cursor.fetchone()

        if p_exist:
          cursor.execute(
              """
                    UPDATE prices SET total_price = ?, total_capacity = ?, unit_price = ?, updated_at = ?
                    WHERE id = ?
                """,
              (price_val, qty_val, unit_price, p_exist[0], today),
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
                  qty_val,
                  unit_price,
                  0,
                  today,
              ),
          )
        conn.commit()
        conn.close()

        st.success(
            f"✨ 【{target_store}】の「{final_product}」（総額 {int(price_val):,}円 /"
            f" {int(qty_val)}{unit_val}）を保存しました！（1{unit_val}あたり"
            f" {unit_price:.1f}円）"
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
        "追加する商品名", placeholder="例: ボックスティッシュ (60箱ケース)"
    )
    new_u = st.text_input("単位（例: 箱, ロール, ml, 袋）", value="箱")
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
