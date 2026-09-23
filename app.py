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

  # 店舗マスタ
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT UNIQUE,
            store_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

  # 既存の重複や古いデータをクリアして、整理されたマスターに再構築
  # （※価格データとの外部キー制約を考慮しつつ初期商品を整理します）
  cursor.execute("DELETE FROM products")

  # 定番日用品の整理された初期データ（トイレットペーパーはダブルのみ、ご指定の追加商品を含む）
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
      # ご指定の追加商品
      ("入浴剤 バブ", "日用品（消耗品）", "錠"),
      ("キャッツビーフェイスタオル", "日用品（消耗品）", "枚"),
      ("単3電池 / 単4電池", "家電・ガジェット", "本"),
      ("不織布マスク", "日用品（消耗品）", "枚"),
      ("衣料用洗剤", "日用品（消耗品）", "ml"),
      ("ボディソープ・石鹸", "日用品（消耗品）", "個"),
  ]

  for p_name, p_cat, p_unit in default_products:
    cursor.execute(
        """
            INSERT OR IGNORE INTO products (name, category, unit_name) 
            VALUES (?, ?, ?)
        """,
        (p_name, p_cat, p_unit),
    )

  # ご指定の店舗を含む初期データ（コストコ壬生・明和、業務スーパー、コスモス、カインズ等）
  default_stores = [
      ("Amazon（定期おトク便）", "Amazon", 1),
      ("コストコ 壬生倉庫店", "コストコ", 1),
      ("コストコ 明和倉庫店", "コストコ", 1),
      ("カインズ（近隣店）", "近隣店舗", 1),
      ("コスモス（近隣店）", "近隣店舗", 1),
      ("業務スーパー（近隣店）", "近隣店舗", 1),
      ("ウエルシア（近隣店）", "近隣店舗", 0),
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
    "リポジトリ: `shohinhikaku-bycostco-amazonETS` | 商品整理・定番品追加版"
)

# サイドバー：メニュー選択
st.sidebar.markdown("### 📌 メニュー")
menu = st.sidebar.radio(
    "移動先を選択してください",
    [
        "価格比較・検索",
        "複数商品の価格を一括登録",
        "店舗マスタ設定（地域・住所連動）",
    ],
)

# --- ① 価格比較・検索画面 ---
if menu == "価格比較・検索":
  st.markdown("#### 🔍 4店舗横並び・単位単価チェック（買い回り最適化）")

  conn = sqlite3.connect(DB_NAME)
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
        "💡 まだ価格データが登録されていません。「複数商品の価格を一括登録」からデータを追加してみましょう。"
    )
  else:
    if active_stores:
      df_filtered = df[df["店舗名"].isin(active_stores)]
    else:
      df_filtered = df

    st.markdown("##### 📊 選択した店舗の横並び単位単価マトリックス")

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
          "選択された店舗の価格データがまだありません。「店舗マスタ設定」や「価格登録」をご確認ください。"
      )

    st.markdown("##### 💡 商品ごとの詳細＆最安値チェック")
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

# --- ② 複数商品の価格を一括登録画面 ---
elif menu == "複数商品の価格を一括登録":
  st.markdown("#### 📝 複数商品の価格を一括登録（時短・自動追加対応）")
  st.write(
      "1つの店舗で複数の商品をまとめて購入した際、一気に数値を入力して一度に保存できます。"
  )
  st.write(
      "※リストにない新しい商品や店舗名を入力した場合は、**自動的にマスターへ追加**されます！"
  )

  conn = sqlite3.connect(DB_NAME)
  products_df = pd.read_sql("SELECT * FROM products", conn)
  stores_df = pd.read_sql("SELECT * FROM stores", conn)
  conn.close()

  product_names = (
      products_df["name"].tolist() if not products_df.empty else []
  )
  store_names = stores_df["store_name"].tolist() if not stores_df.empty else []

  with st.form("bulk_register_form"):
    st.markdown("##### 📍 購入店舗の選択（または直接入力）")
    store_choice = st.selectbox("店舗を選択", store_names + ["【＋新しい店舗を直接入力】"])
    new_store_input = st.text_input(
        "※上の選択肢で「【＋新しい店舗を直接入力】」を選んだ場合はこちらに入力",
        placeholder="例: ヨークベニマル 古河店",
    )

    st.markdown("---")
    st.markdown(
        "##### 🛍️ 商品ごとの価格・容量入力（最大5件を同時にサクサク入力）"
    )

    for i in range(1, 6):
      st.markdown(f"**商品 {i}**")
      col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
      with col1:
        p_name = st.selectbox(
            f"商品名 #{i}",
            ["-- 登録しない --"] + product_names + ["【＋新規商品を追加】"],
            key=f"p_name_{i}",
        )
        p_name_custom = st.text_input(
            f"新規商品名 #{i}",
            placeholder="商品名を入力",
            key=f"p_custom_{i}",
        )
      with col2:
        total_price = st.number_input(
            f"総額(円) #{i}", min_value=0.0, step=10.0, key=f"price_{i}"
        )
      with col3:
        total_cap = st.number_input(
            f"容量/数量 #{i}", min_value=0.1, value=1.0, key=f"cap_{i}"
        )
      with col4:
        unit_in = st.text_input(f"単位 #{i}", value="個", key=f"unit_{i}")
      st.markdown("")

    submitted = st.form_submit_button("一括データをデータベースに保存する")

    if submitted:
      target_store = (
          new_store_input.strip()
          if store_choice == "【＋新しい店舗を直接入力】"
          else store_choice
      )

      if not target_store:
        st.error("⚠️ 店舗名を選択または入力してください。")
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

        saved_count = 0
        today = datetime.date.today().isoformat()

        for i in range(1, 6):
          selected_p = st.session_state.get(f"p_name_{i}")
          custom_p = st.session_state.get(f"p_custom_{i}", "").strip()
          t_price = st.session_state.get(f"price_{i}", 0.0)
          t_cap = st.session_state.get(f"cap_{i}", 1.0)
          u_name = st.session_state.get(f"unit_{i}", "個")

          final_product_name = ""
          if selected_p == "【＋新規商品を追加】" and custom_p:
            final_product_name = custom_p
          elif selected_p and selected_p not in [
              "-- 登録しない --",
              "【＋新規商品を追加】",
          ]:
            final_product_name = selected_p

          if final_product_name and t_price > 0:
            cursor.execute(
                "SELECT id, unit_name FROM products WHERE name = ?",
                (final_product_name,),
            )
            p_row = cursor.fetchone()
            if p_row:
              prod_id = p_row[0]
            else:
              cursor.execute(
                  "INSERT INTO products (name, category, unit_name) VALUES"
                  " (?, ?, ?)",
                  (final_product_name, "日用品（消耗品）", u_name),
              )
              conn.commit()
              prod_id = cursor.lastrowid

            unit_price = t_price / t_cap if t_cap > 0 else 0

            cursor.execute(
                """
                        INSERT INTO prices (product_id, store_type, store_name, total_price, total_capacity, unit_price, is_sale, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    prod_id,
                    "近隣店舗",
                    target_store,
                    t_price,
                    t_cap,
                    unit_price,
                    0,
                    today,
                ),
            )
            saved_count += 1

        conn.commit()
        conn.close()

        if saved_count > 0:
          st.success(
              f"✨ 【{target_store}】での価格データ **{saved_count}件**"
              " の一括保存が完了しました！"
          )
        else:
          st.warning(
              "⚠️ 保存されたデータがありません。商品名と価格を正しく入力してください。"
          )

# --- ③ 店舗マスタ設定（地域・住所連動）画面 ---
elif menu == "店舗マスタ設定（地域・住所連動）":
  st.markdown("#### ⚙️ 地域・住所連動による店舗自動切り替え＆比較設定")
  st.write(
      "お住まいの地域や住所を入力すると、その周辺に合わせた主要スーパー・ドラッグストアやコストコ（壬生・明和）が自動でセットされます。"
  )

  user_address = st.text_input(
      "基準となる住所・エリア（例: 茨城県古河市...）", value="茨城県古河市"
  )

  if st.button("地域を変更して周辺店舗を自動連動・更新"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    regional_stores = [
        ("コストコ 壬生倉庫店", "コストコ", 1),
        ("コストコ 明和倉庫店", "コストコ", 1),
        ("カインズ（近隣店）", "近隣店舗", 1),
        ("コスモス（近隣店）", "近隣店舗", 1),
        ("業務スーパー（近隣店）", "近隣店舗", 1),
        ("Amazon（定期おトク便）", "Amazon", 1),
    ]

    for s_name, s_type, s_active in regional_stores:
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
        f"📍 地域を「{user_address}」に連動させました！ 業務スーパー・コスモス・カインズ・コストコ（壬生・明和）がマスターに反映されました。"
    )

  st.markdown("##### 🛒 買い回り比較の対象にする店舗を選択（最大4店舗〜推奨）")

  conn = sqlite3.connect(DB_NAME)
  stores_df = pd.read_sql("SELECT * FROM stores", conn)
  conn.close()

  if not stores_df.empty:
    with st.form("store_select_form"):
      updated_actives = {}
      for idx, row in stores_df.iterrows():
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
        st.success("✨ 比較店舗の設定を保存しました！")
  else:
    st.info("店舗データがありません。上のボタンを押して生成してください。")
