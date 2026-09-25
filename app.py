import datetime
import re
import sqlite3
from bs4 import BeautifulSoup
import pandas as pd
import requests
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
            name TEXT NOT NULL,
            category TEXT,
            unit_name TEXT,
            spec_detail TEXT
        )
    """)

  # 価格データ (店舗ごとの価格)
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

  # 初期データの投入（主要な店舗とサンプル商品）
  cursor.execute("SELECT COUNT(*) FROM stores")
  if cursor.fetchone()[0] == 0:
    default_stores = [
        ("Amazon", "EC・通販"),
        ("コストコ", "大型倉庫店"),
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

  cursor.execute("SELECT COUNT(*) FROM products")
  if cursor.fetchone()[0] == 0:
    default_products = [
        (
            "大王製紙",
            "トイレットペーパー",
            "日用品",
            "ロール",
            "ダブル 30m・72ロール",
        ),
        (
            "大王製紙",
            "ボックスティッシュ",
            "日用品",
            "箱",
            "5箱パック・1箱200組",
        ),
        ("一般メーカー", "お米", "食品", "kg", "精米 5kg"),
        ("花王", "洗濯用液体洗剤", "日用品", "ml", "詰替用 4000ml"),
    ]
    for p_maker, p_name, p_cat, p_unit, p_spec in default_products:
      cursor.execute(
          """
                INSERT INTO products (maker_name, name, category, unit_name, spec_detail) 
                VALUES (?, ?, ?, ?, ?)
            """,
          (p_maker, p_name, p_cat, p_unit, p_spec),
      )

  conn.commit()
  conn.close()


init_db()

st.set_page_config(
    page_title="買い物価格比較 & 底値DB 【完全無料・自動取得対応版】",
    page_icon="🛒",
    layout="wide",
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

st.markdown(
    "### 🛒 買い物価格比較 & 底値DB 【完全無料・Amazon/コストコ対応】"
)

# サイドバー：メニュー選択
st.sidebar.markdown("### 📌 メニュー")
menu = st.sidebar.radio(
    "移動先を選択してください",
    [
        "🔍 価格比較・最安値チェック",
        "📝 価格・商品の登録（Amazon自動読込対応）",
        "⚙️ 店舗・商品マスタ管理",
        "🛠️ データ自動整合性チェック",
    ],
)


# --- ① 価格比較・検索画面 ---
if menu == "🔍 価格比較・最安値チェック":
  st.markdown("#### 🔍 Amazon・コストコを含めた全店舗の価格・実質単価比較")

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, maker_name, name, spec_detail FROM products")
  all_products = cursor.fetchall()
  conn.close()

  prod_options = {}
  for p in all_products:
    p_id, m_name, p_name, spec = p[0], p[1], p[2], p[3]
    maker_str = f"[{m_name}] " if m_name and m_name.strip() else ""
    spec_str = f" ({spec})" if spec and spec.strip() else ""
    label = f"{maker_str}{p_name}{spec_str}"
    prod_options[label] = p_id

  selected_label = st.selectbox(
      "比較したい商品を選択",
      list(prod_options.keys()) if prod_options else ["（商品がありません）"],
  )

  if prod_options and selected_label in prod_options:
    target_prod_id = prod_options[selected_label]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT maker_name, name, spec_detail, unit_name, category FROM products"
        " WHERE id = ?",
        (target_prod_id,),
    )
    maker_name, target_product, spec_detail, unit_name, category = (
        cursor.fetchone()
    )

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

    display_maker = (
        f"[{maker_name}] " if maker_name and maker_name.strip() else ""
    )
    display_spec = f" ({spec_detail})" if spec_detail and spec_detail.strip() else ""

    st.markdown("---")
    st.markdown(
        "##### 📦 選択中商品:"
        f" **{display_maker}{target_product}{display_spec}**"
    )
    st.markdown(
        f"**🏷️ メーカー**: `{maker_name if maker_name and maker_name.strip() else '未設定'}` | "
        f"**📂 カテゴリ**: `{category}` | "
        f"**📝 スペック**: `{spec_detail if spec_detail else 'なし'}` | "
        f"**基準単位**: `{unit_name}`"
    )
    st.markdown("---")
    st.markdown("##### 📊 各店舗（Amazon・コストコ等）の価格・実質単価比較")

    if not rows:
      st.info(
          f"💡 「{target_product}{display_spec}」の価格データがまだ登録されていません。「📝"
          " 価格・商品の登録」から価格を追加してください。"
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
            "最終更新日": upd_date,
        })
        raw_unit_prices.append(u_price)

      display_df = pd.DataFrame(data_list)
      min_unit_price = min(raw_unit_prices)

      def highlight_cheapest(row):
        u_val = raw_unit_prices[row.name]
        if u_val == min_unit_price:
          return [
              (
                  "background-color: #1b4332; color: #52b788; font-weight: bold;"
                  " font-size: 1.1em;"
              )
          ] * len(row)
        return [""] * len(row)

      st.dataframe(
          display_df.style.apply(highlight_cheapest, axis=1),
          use_container_width=True,
      )

      min_idx = raw_unit_prices.index(min_unit_price)
      best_row = rows[min_idx]
      st.success(
          f"🏆 **【最安値・お買い得情報】**\n\n"
          f"現在一番お得な購入先は **{best_row[0]}** です！\n"
          f"- **支払総額**: **{int(best_row[1]):,}円** （総容量: {best_row[2]:g}"
          f" {unit_name}）\n"
          f"- **1{unit_name}あたりの単価**: **{best_row[3]:.2f}円**"
      )


# --- ② 価格・商品の登録画面（Amazon自動読込対応） ---
elif menu == "📝 価格・商品の登録（Amazon自動読込対応）":
  st.markdown("#### 📝 価格・商品の登録 ＆ Amazon自動アシスト")
  st.write(
      "AmazonのURLを貼り付けてボタンを押すと、商品名や価格のヒントを無料で自動取得できます。"
  )

  # セッション状態で自動取得データを保持
  if "scraped_title" not in st.session_state:
    st.session_state.scraped_title = ""
  if "scraped_price" not in st.session_state:
    st.session_state.scraped_price = 0.0

  with st.expander(
      "🔗 【便利機能】AmazonのURLから自動で商品名・価格を読み取る",
      expanded=False,
  ):
    amazon_url = st.text_input(
        "Amazonの商品ページURLを入力",
        placeholder="https://www.amazon.co.jp/dp/B0...",
    )
    if st.button("🔄 Amazonから情報を取得する"):
      if not amazon_url.strip():
        st.warning("⚠️ AmazonのURLを入力してください。")
      else:
        try:
          headers = {
              "User-Agent": (
                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                  " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
              ),
              "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
          }
          res = requests.get(amazon_url, headers=headers, timeout=5)
          if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")

            # 商品名取得
            title_elem = soup.select_one("#productTitle")
            title = (
                title_elem.get_text(strip=True)
                if title_elem
                else "（商品名自動取得できず）"
            )

            # 価格取得の試行
            price_val_scraped = 0.0
            price_elem = soup.select_one(
                ".a-price .a-offscreen, #priceblock_ourprice,"
                " #priceblock_dealprice"
            )
            if price_elem:
              price_text = price_elem.get_text(strip=True)
              # 数字とカンマ以外を削除して数値化
              num_str = re.sub(r"[^\d]", "", price_text)
              if num_str:
                price_val_scraped = float(num_str)

            st.session_state.scraped_title = title
            st.session_state.scraped_price = price_val_scraped
            st.success(
                "✨ 情報を取得しました！ 下記の登録フォームに反映されます。"
            )
          else:
            st.error(
                "⚠️ Amazon側からアクセスがブロックされました（ステータスコード:"
                f" {res.status_code}）。手動で入力してください。"
            )
        except Exception as e:
          st.error(
              "⚠️ 取得中にエラーが発生しました（Amazonのボット対策等の影響）。手動入力をご利用ください。"
          )

  st.markdown("---")

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT id, name, spec_detail FROM products")
  products_raw = cursor.fetchall()
  cursor.execute("SELECT store_name FROM stores")
  store_names = [row[0] for row in cursor.fetchall()]
  conn.close()

  product_labels = [
      f"{p[1]}" + (f" ({p[2]})" if p[2] else "") for p in products_raw
  ]
  product_map = {
      f"{p[1]}"
      + (f" ({p[2]})" if p[2] else ""): p[0]
      for p in products_raw
  }

  with st.form("register_form"):
    col_s1, col_s2 = st.columns(2)
    with col_s1:
      store_choice = st.selectbox(
          "店舗を選択", store_names + ["【＋新しい店舗を追加】"]
      )
    with col_s2:
      new_store_input = st.text_input(
          "※新しい店舗名（左で追加を選んだ場合）", placeholder="例: ヨドバシ.com"
      )

    st.markdown("---")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
      maker_input = st.text_input(
          "メーカー名（※任意）", placeholder="例: エリエール"
      )
    with col_p2:
      p_choice = st.selectbox(
          "商品を選択", product_labels + ["【＋新しい商品を追加】"]
      )
    with col_p3:
      p_custom = st.text_input(
          "※新しい商品名",
          value=st.session_state.scraped_title[:40]
          if st.session_state.scraped_title
          else "",
          placeholder="例: トイレットペーパー",
      )

    col_spec1, col_spec2 = st.columns(2)
    with col_spec1:
      spec_input = st.text_input(
          "スペック・詳細", placeholder="例: ダブル 30m・72ロール"
      )
    with col_spec2:
      category_input = st.selectbox(
          "カテゴリ", ["日用品", "食品", "飲料", "その他"]
      )

    col_v1, col_v2, col_v3 = st.columns(3)
    with col_v1:
      price_val = st.number_input(
          "支払総額 (円)",
          min_value=0.0,
          step=10.0,
          value=st.session_state.scraped_price
          if st.session_state.scraped_price > 0
          else 1280.0,
      )
    with col_v2:
      capacity_val = st.number_input(
          "総容量・数量（計算基準）",
          min_value=0.1,
          step=1.0,
          value=72.0,
      )
    with col_v3:
      unit_val = st.selectbox(
          "単位", ["ロール", "m", "個", "箱", "kg", "ml", "本"]
      )

    submitted = st.form_submit_button("💾 価格データを保存・更新する")

    if submitted:
      target_store = (
          new_store_input.strip()
          if store_choice == "【＋新しい店舗を追加】"
          else store_choice
      )
      final_maker = maker_input.strip() if maker_input.strip() else None
      final_spec = spec_input.strip() if spec_input.strip() else ""

      if p_choice == "【＋新しい商品を追加】":
        final_product = p_custom.strip()
      else:
        selected_p_id = product_map.get(p_choice)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE id = ?", (selected_p_id,))
        res = cursor.fetchone()
        conn.close()
        final_product = res[0] if res else p_choice

      if not target_store:
        st.error("⚠️ 店舗名を入力してください。")
      elif not final_product:
        st.error("⚠️ 商品名を入力してください。")
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

        cursor.execute(
            "SELECT id FROM products WHERE name = ? AND (spec_detail = ? OR"
            " (spec_detail IS NULL AND ? = ''))",
            (final_product, final_spec, final_spec),
        )
        p_row = cursor.fetchone()

        if p_row:
          prod_id = p_row[0]
          cursor.execute(
              "UPDATE products SET maker_name = ?, category = ?, unit_name ="
              " ? WHERE id = ?",
              (final_maker, category_input, unit_val, prod_id),
          )
        else:
          cursor.execute(
              """
                    INSERT INTO products (maker_name, name, category, unit_name, spec_detail) 
                    VALUES (?, ?, ?, ?, ?)
                """,
              (
                  final_maker,
                  final_product,
                  category_input,
                  unit_val,
                  final_spec,
              ),
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

        # 登録成功したらセッションをクリア
        st.session_state.scraped_title = ""
        st.session_state.scraped_price = 0.0

        st.success(
            f"✨ 【{target_store}】の「{final_product} ({final_spec})」を保存しました！"
            f" （1{unit_val}あたり {unit_price:.2f}円）"
        )


# --- ③ 店舗・商品マスタ管理画面 ---
elif menu == "⚙️ 店舗・商品マスタ管理":
  st.markdown("#### ⚙️ 店舗・商品の管理")

  tab1, tab2 = st.tabs(["店舗一覧", "商品一覧"])

  with tab1:
    st.markdown("##### 📋 登録されている店舗一覧")
    conn = sqlite3.connect(DB_NAME)
    stores_df = pd.read_sql(
        "SELECT store_name as 店舗名, store_type as 分類 FROM stores", conn
    )
    conn.close()
    st.dataframe(stores_df, use_container_width=True)

  with tab2:
    st.markdown("##### 📋 登録されている商品一覧")
    conn = sqlite3.connect(DB_NAME)
    products_df = pd.read_sql(
        """
            SELECT maker_name as メーカー名, name as 商品名, category as カテゴリ, unit_name as 基準単位, spec_detail as スペック詳細 
            FROM products
        """,
        conn,
    )
    conn.close()
    st.dataframe(products_df, use_container_width=True)


# --- ④ データ自動チェック機能 ---
elif menu == "🛠️ データ自動整合性チェック":
  st.markdown("#### 🛠️ データの自動診断と整合性チェック")
  st.write("データベース内のデータ状態を自動チェックします。")

  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("SELECT COUNT(*) FROM products")
  total_prods = cursor.fetchone()[0]

  cursor.execute("SELECT COUNT(*) FROM prices")
  total_prices = cursor.fetchone()[0]

  cursor.execute("""
        SELECT p.id, p.name, p.spec_detail FROM products p
        LEFT JOIN prices pr ON p.id = pr.product_id
        WHERE pr.id IS NULL
    """)
  orphaned_products = cursor.fetchall()
  conn.close()

  st.markdown("##### 📊 データベース診断レポート")
  col1, col2, col3 = st.columns(3)
  col1.metric("登録商品数", f"{total_prods} 件")
  col2.metric("価格データ数", f"{total_prices} 件")
  col3.metric("価格未登録の商品", f"{len(orphaned_products)} 件")

  st.markdown("---")
  st.markdown("##### 🧹 自動クレンジング機能")

  if st.button("🚀 データの重複・矛盾を自動修復する"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
            DELETE FROM products 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM products 
                GROUP BY name, spec_detail
            )
        """)
    conn.commit()
    conn.close()
    st.success("✨ データのクレンジングが正常に完了しました！")
    st.rerun()

  if orphaned_products:
    st.markdown("##### ⚠️ 価格データがまだ登録されていない商品")
    for op in orphaned_products:
      st.warning(
          f"商品名: **{op[1]}** （スペック: {op[2] if op[2] else 'なし'}）"
          " -> 価格が未登録です。"
      )
  else:
    st.success(
        "🎉 すべての商品に価格データが紐付いており、完璧な状態です！"
    )
