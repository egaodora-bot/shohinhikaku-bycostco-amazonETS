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
            maker_name TEXT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            unit_name TEXT,
            spec_detail TEXT
        )
    """)

  # 既存のテーブルに maker_name カラムがない場合に安全に追加する処理
  try:
    cursor.execute("ALTER TABLE products ADD COLUMN maker_name TEXT")
    conn.commit()
  except sqlite3.OperationalError:
    pass

  # 価格データ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            store_name TEXT,
            total_price REAL,
            total_capacity REAL,
            unit_price REAL,
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

  # 初期データの投入
  cursor.execute("SELECT COUNT(*) FROM products")
  if cursor.fetchone()[0] == 0:
    default_products = [
        (
            "大王製紙",
            "トイレットペーパー (ダブル)",
            "日用品",
            "m",
            "1.5倍巻き・総m数で比較",
        ),
        (
            "大王製紙",
            "ボックスティッシュ",
            "日用品",
            "箱",
            "5箱パック・1箱200組(400枚)",
        ),
        ("一般メーカー", "お米 (5kg)", "食品", "kg", "精米 5kg"),
        ("花王", "洗濯用液体洗剤", "日用品", "ml", "詰替用"),
    ]
    for p_maker, p_name, p_cat, p_unit, p_spec in default_products:
      cursor.execute(
          """
                INSERT OR IGNORE INTO products (maker_name, name, category, unit_name, spec_detail) 
                VALUES (?, ?, ?, ?, ?)
            """,
          (p_maker, p_name, p_cat, p_unit, p_spec),
      )

  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    default_stores = [
        ("コストコ", "コストコ"),
        ("Amazon", "Amazon"),
        ("カインズ", "近隣店舗"),
        ("コスモス", "近隣店舗"),
        ("ウエルシア", "近隣店舗"),
        ("ベイシア", "近隣店舗"),
    ]
    for s_name, s_type in default_stores:
      cursor.execute(
          "INSERT OR IGNORE INTO stores (store_name, store_type) VALUES"
          " (?, ?)",
          (s_name, s_type),
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
    .stTextInput input, .stNumberInput input {
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
        "🔍 価格比較・検索",
        "📝 価格・商品の登録",
        "⚙️ 店舗・商品マスタ管理",
    ],
)


# --- ① 価格比較・検索画面 ---
if menu == "🔍 価格比較・検索":
  st.markdown("#### 🔍 商品の価格・実質単価比較")

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, maker_name, name FROM products")
  all_products = cursor.fetchall()
  conn.close()

  # 選択肢用のリストを作成（「メーカー名: 商品名」の形式）
  prod_options = {
      f"[{p[1] if p[1] else 'ノーブランド'}] {p[2]}": p[0] for p in all_products
  }

  selected_label = st.selectbox(
      "登録済み商品から選択して比較",
      list(prod_options.keys()) if prod_options else ["（商品がありません）"],
  )

  if prod_options and selected_label in prod_options:
    target_prod_id = prod_options[selected_label]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT maker_name, name, spec_detail, unit_name FROM products WHERE"
        " id = ?",
        (target_prod_id,),
    )
    maker_name, target_product, spec_detail, unit_name = cursor.fetchone()

    cursor.execute(
        """
            SELECT store_name, total_price, total_capacity, unit_price, updated_at
            FROM prices 
            WHERE product_id = ?
            ORDER BY unit_price ASC
        """,
        (target_prod_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    st.markdown("---")
    st.markdown(
        f"##### 📦 選択中商品: **[{maker_name if maker_name else 'ノーブランド'}]"
        f" {target_product}**"
    )
    st.markdown(
        f"**🏷️ メーカー**: `{maker_name}` | **📝 スペック**: `{spec_detail}` |"
        f" **基準単位**: `{unit_name}`"
    )
    st.markdown("---")
    st.markdown("##### 📊 各店舗の価格・実質単価比較")

    if not rows:
      st.info(
          f"💡 「{target_product}」の価格データがまだ登録されていません。「📝"
          " 価格・商品の登録」メニューから価格と総容量を登録してください。"
      )
    else:
      data_list = []
      raw_unit_prices = []
      for r in rows:
        store_name, t_price, t_cap, u_price, upd_date = r
        data_list.append({
            "店舗名": store_name,
            "支払総額": f"{int(t_price):,} 円",
            "総容量・数量": f"{t_cap:g} {unit_name}",
            f"1{unit_name}あたり単価": f"{u_price:.2f} 円/{unit_name}",
            "更新日": upd_date,
        })
        raw_unit_prices.append(u_price)

      display_df = pd.DataFrame(data_list)
      min_unit_price = min(raw_unit_prices)

      def highlight_cheapest(row):
        u_val = raw_unit_prices[row.name]
        if u_val == min_unit_price:
          return ["background-color: #1b4332; color: #52b788; font-weight: bold; font-size: 1.1em;"] * len(row)
        return [""] * len(row)

      st.dataframe(
          display_df.style.apply(highlight_cheapest, axis=1),
          use_container_width=True,
      )

      min_idx = raw_unit_prices.index(min_unit_price)
      best_row = rows[min_idx]
      st.success(
          f"🏆 **【最安値・お得情報】**\n\n"
          f"一番お得なのは **{best_row[0]}** です！\n"
          f"- **支払総額**: **{int(best_row[1]):,}円** （総容量: {best_row[2]:g}"
          f" {unit_name}）\n"
          f"- **1{unit_name}あたりの単価**: **{best_row[3]:.2f}円**"
      )

# --- ② 価格・商品の登録画面 ---
elif menu == "📝 価格・商品の登録":
  st.markdown("#### 📝 店舗ごとの価格・容量の手動登録")
  st.write(
      "メーカー名や商品名、総m数（トイレットペーパー等）を入力して正確に登録できます。"
  )

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT name FROM products")
  product_names = [row[0] for row in cursor.fetchall()]
  cursor.execute("SELECT store_name FROM stores")
  store_names = [row[0] for row in cursor.fetchall()]
  conn.close()

  with st.form("register_form"):
    col_s1, col_s2 = st.columns(2)
    with col_s1:
      store_choice = st.selectbox(
          "店舗を選択", store_names + ["【＋新しい店舗を追加】"]
      )
    with col_s2:
      new_store_input = st.text_input(
          "※新しい店舗名（左で追加を選んだ場合）", placeholder="例: 近隣のスーパー"
      )

    st.markdown("---")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
      maker_input = st.text_input(
          "メーカー名（ブランド名）", placeholder="例: エリエール, 花王"
      )
    with col_p2:
      p_choice = st.selectbox(
          "商品を選択", product_names + ["【＋新しい商品を追加】"]
      )
    with col_p3:
      p_custom = st.text_input(
          "※新しい商品名", placeholder="商品名を入力（例: 贅沢保湿）"
      )

    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
      price_val = st.number_input(
          "支払総額 (円)", min_value=0.0, step=10.0, value=1280.0
      )
    with col_v2:
      capacity_val = st.number_input(
          "総容量・数量（例: 総m数や個数）",
          min_value=0.1,
          step=1.0,
          value=100.0,
      )
    with col_v3:
      unit_val = st.selectbox(
          "単位（計算の基準）", ["m", "個", "箱", "ロール", "kg", "ml"]
      )

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
      final_maker = maker_input.strip() if maker_input.strip() else "ノーブランド"

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
              "INSERT INTO stores (store_name, store_type) VALUES (?, ?)",
              (target_store, "近隣店舗"),
          )
          conn.commit()

        cursor.execute("SELECT id FROM products WHERE name = ?", (final_product,))
        p_row = cursor.fetchone()
        if p_row:
          prod_id = p_row[0]
          cursor.execute(
              "UPDATE products SET maker_name = ? WHERE id = ?",
              (final_maker, prod_id),
          )
        else:
          cursor.execute(
              """
                    INSERT INTO products (maker_name, name, category, unit_name, spec_detail) 
                    VALUES (?, ?, ?, ?, ?)
                """,
              (final_maker, final_product, "日用品・食品", unit_val, "ユーザー登録商品"),
          )
          conn.commit()
          prod_id = cursor.lastrowid

        unit_price = (
            price_val / capacity_val if capacity_val > 0 else price_val
        )
        today = datetime.date.today().isoformat()

        cursor.execute(
            """
                SELECT id FROM prices WHERE product_id = ? AND store_name = ?
            """,
            (prod_id, target_store),
        )
        existing = cursor.fetchone()

        if existing:
          cursor.execute(
              """
                    UPDATE prices 
                    SET total_price = ?, total_capacity = ?, unit_price = ?, updated_at = ?
                    WHERE id = ?
                """,
              (
                  price_val,
                  capacity_val,
                  unit_price,
                  today,
                  existing[0],
              ),
          )
        else:
          cursor.execute(
              """
                    INSERT INTO prices (product_id, store_name, total_price, total_capacity, unit_price, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
              (
                  prod_id,
                  target_store,
                  price_val,
                  capacity_val,
                  unit_price,
                  today,
              ),
          )

        conn.commit()
        conn.close()

        st.success(
            f"✨ 【{target_store}】の「[{final_maker}]"
            f" {final_product}」（総額 {int(price_val):,}円 / {capacity_val:g}"
            f" {unit_val}）を保存しました！（1{unit_val}あたり"
            f" {unit_price:.2f}円）"
        )

# --- ③ 店舗・商品マスタ管理画面 ---
elif menu == "⚙️ 店舗・商品マスタ管理":
  st.markdown("#### ⚙️ 店舗・商品の管理")

  tab1, tab2 = st.tabs(["店舗一覧", "商品一覧"])

  with tab1:
    st.markdown("##### 📋 登録されている店舗一覧")
    conn = sqlite3.connect(DB_NAME)
    stores_df = pd.read_sql("SELECT store_name as 店舗名, store_type as 分類 FROM stores", conn)
    conn.close()
    st.dataframe(stores_df, use_container_width=True)

  with tab2:
    st.markdown("##### 📋 登録されている商品一覧")
    conn = sqlite3.connect(DB_NAME)
    products_df = pd.read_sql(
        """
            SELECT maker_name as メーカー名, name as 商品名, category as カテゴリ, unit_name as 基準単位, spec_detail as スペック備考 
            FROM products
        """,
        conn,
    )
    conn.close()
    st.dataframe(products_df, use_container_width=True)
