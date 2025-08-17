import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials

# ============================
# Google Sheets Setup
# ============================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
import gspread
import streamlit as st

# Define the necessary scopes
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Authorize the client with the defined scopes
client = gspread.service_account_from_dict(
    st.secrets["gcp_service_account"],
    scopes=scopes
)

SPREADSHEET_NAME = "MacroTracker"
sheet = client.open(SPREADSHEET_NAME)

# ============================
# Load / Save via Sheets
# ============================
def ensure_columns(df: pd.DataFrame, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = [] if c in ["food", "date"] else 0
    return df[cols]

def load_log() -> pd.DataFrame:
    try:
        ws = sheet.worksheet("daily_log")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame(columns=["date", "food", "grams", "calories", "protein", "carbs", "fat"])
    df = ensure_columns(df, ["date", "food", "grams", "calories", "protein", "carbs", "fat"])
    # Coerce numeric types
    for c in ["grams", "calories", "protein", "carbs", "fat"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

def save_log(df: pd.DataFrame):
    ws = sheet.worksheet("daily_log")
    ws.clear()
    if not df.empty:
        ws.update([df.columns.tolist()] + df.astype(object).values.tolist())

def load_weight_log() -> pd.DataFrame:
    try:
        ws = sheet.worksheet("weight_log")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame(columns=["date", "weight"])
    df = ensure_columns(df, ["date", "weight"])
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
    return df

def save_weight_log(df: pd.DataFrame):
    ws = sheet.worksheet("weight_log")
    ws.clear()
    if not df.empty:
        ws.update([df.columns.tolist()] + df.astype(object).values.tolist())

# ============================
# Food database (sample)
# ============================
food_db = {
    "Curd 100G": {"calories": 98, "protein": 11, "carbs": 4, "fat": 5},
    "Roti": {"calories": 100, "protein": 3, "carbs": 20, "fat": 1},
    "Sugar Tbsp": {"calories": 44, "protein": 0, "carbs": 11.3, "fat": 0},
    "Soya Chunks 100G": {"calories": 345, "protein": 52, "carbs": 33, "fat": 0.5},
    "Paneer 100G": {"calories": 296, "protein": 25, "carbs": 6, "fat": 22},
    "Nakpro Plant Protein": {"calories": 138, "protein": 25, "carbs": 4, "fat": 2},
}

# ============================
# TDEE
# ============================
def calculate_tdee(weight, multiplier):
    # Simple heuristic: 22 kcal/kg * multiplier
    return int(weight * 22 * multiplier)

# ============================
# App
# ============================
def main():
    st.set_page_config(page_title="Macro & Weight Tracker", layout="wide")
    st.title("🥗 Macro & Weight Tracker")

    # Load data
    log_df = load_log()
    weight_df = load_weight_log()

    # Today in DD/MM/YYYY
    today = datetime.date.today().strftime("%d/%m/%Y")

    # ----------------------------
    # Sidebar: Profile & Controls
    # ----------------------------
    st.sidebar.header("👤 Profile")

    if "activity_multiplier" not in st.session_state:
        st.session_state["activity_multiplier"] = 1.55  # default Gym Day
    if "manual_tdee" not in st.session_state:
        st.session_state["manual_tdee"] = None

    c1, c2 = st.sidebar.columns(2)
    if c1.button("🏋️ Gym Day"):
        st.session_state["activity_multiplier"] = 1.55
        st.sidebar.success("Set to Gym Day (Moderate)")
    if c2.button("🛌 Rest Day"):
        st.session_state["activity_multiplier"] = 1.2
        st.sidebar.success("Set to Rest Day (Sedentary)")

    st.sidebar.write(f"**Current Activity Multiplier:** {st.session_state['activity_multiplier']}")
    manual_tdee_input = st.sidebar.number_input(
        "Manual TDEE (kcal, optional)", min_value=0, step=50,
        value=st.session_state["manual_tdee"] or 0
    )
    st.session_state["manual_tdee"] = manual_tdee_input if manual_tdee_input > 0 else None

    # ----------------------------
    # Food Search + Logging (with form for Enter submit)
    # ----------------------------
    st.header("🍽️ Food Database")
    search = st.text_input("Search for a food item...").strip().lower()

    def food_matches(q, name):
        return (q == "") or (q in name.lower())

    any_shown = False
    for food, macros in food_db.items():
        if food_matches(search, food):
            any_shown = True
            with st.expander(food, expanded=False):
                with st.form(key=f"form_{food}"):
                    grams = st.number_input("Amount (grams)", min_value=0.0, step=10.0, key=f"{food}_grams")
                    submitted = st.form_submit_button("Log Food")
                    if submitted and grams > 0:
                        cals = macros["calories"] * grams / 100.0
                        prot = macros["protein"] * grams / 100.0
                        carbs = macros["carbs"] * grams / 100.0
                        fat = macros["fat"] * grams / 100.0
                        new_row = pd.DataFrame([{
                            "date": today, "food": food, "grams": grams,
                            "calories": cals, "protein": prot, "carbs": carbs, "fat": fat
                        }])
                        log_df = pd.concat([log_df, new_row], ignore_index=True)
                        save_log(log_df)
                        st.success(f"Logged {grams:.0f} g of {food}")
                        st.experimental_rerun()
    if not any_shown:
        st.info("No matching foods. Try a different search.")

    # ----------------------------
    # Today's Log (table + delete + totals)
    # ----------------------------
    st.header("📅 Today's Log")
    today_log = log_df[log_df["date"] == today].copy()

    if not today_log.empty:
        totals = today_log[["calories", "protein", "carbs", "fat"]].sum(numeric_only=True)
        total_row = pd.DataFrame([{
            "food": "TOTALS", "grams": "",
            "calories": totals["calories"], "protein": totals["protein"],
            "carbs": totals["carbs"], "fat": totals["fat"]
        }])
        display_df = pd.concat([today_log, total_row], ignore_index=True)

        for i, row in display_df.iterrows():
            cols = st.columns([3, 2, 2, 2, 2, 2, 1])
            if row["food"] == "TOTALS":
                cols[0].markdown(f"**{row['food']}**")
                cols[1].markdown(f"**{row['grams']}**")
                cols[2].markdown(f"**{round(row['calories'],1)}**")
                cols[3].markdown(f"**{round(row['protein'],1)}**")
                cols[4].markdown(f"**{round(row['carbs'],1)}**")
                cols[5].markdown(f"**{round(row['fat'],1)}**")
                cols[6].write("")
            else:
                cols[0].write(row["food"])
                cols[1].write(round(float(row["grams"]), 1))
                cols[2].write(round(float(row["calories"]), 1))
                cols[3].write(round(float(row["protein"]), 1))
                cols[4].write(round(float(row["carbs"]), 1))
                cols[5].write(round(float(row["fat"]), 1))
                # Map display index -> original index in today_log
                if cols[6].button("🗑️", key=f"del_{i}"):
                    orig_idx = today_log.index[i]  # safe because totals row is last
                    log_df = log_df.drop(index=orig_idx)
                    save_log(log_df)
                    st.experimental_rerun()
    else:
        st.info("No food logged yet today.")

    # ----------------------------
    # Weight Logging + Chart
    # ----------------------------
    st.header("⚖️ Weight Tracking")
    new_weight = st.number_input("Enter today's weight (kg)", min_value=1.0, step=0.1)
    if st.button("Log Weight"):
        if new_weight > 0:
            new_row = pd.DataFrame([{"date": today, "weight": new_weight}])
            weight_df = pd.concat([weight_df, new_row], ignore_index=True)
            save_weight_log(weight_df)
            st.success(f"Weight {new_weight:.1f} kg logged for {today}")
            st.experimental_rerun()

    latest_weight = weight_df["weight"].iloc[-1] if not weight_df.empty else None

    if not weight_df.empty:
        # Plot with proper datetime x-axis
        plot_df = weight_df.copy()
        plot_df["date_dt"] = pd.to_datetime(plot_df["date"], format="%d/%m/%Y", errors="coerce")
        plot_df = plot_df.dropna(subset=["date_dt"]).sort_values("date_dt")
        plot_df = plot_df.set_index("date_dt")[["weight"]]
        st.line_chart(plot_df)

    # ----------------------------
    # Daily Summary
    # ----------------------------
    st.header("📊 Daily Summary")

    calories_today = today_log["calories"].sum(numeric_only=True) if not today_log.empty else 0
    protein_today  = today_log["protein"].sum(numeric_only=True)  if not today_log.empty else 0
    carbs_today    = today_log["carbs"].sum(numeric_only=True)    if not today_log.empty else 0
    fat_today      = today_log["fat"].sum(numeric_only=True)      if not today_log.empty else 0

    if latest_weight and latest_weight > 0:
        tdee_auto = calculate_tdee(latest_weight, st.session_state["activity_multiplier"])
        tdee_used = st.session_state["manual_tdee"] if st.session_state["manual_tdee"] else tdee_auto
        balance = int(calories_today - tdee_used)
    else:
        tdee_auto, tdee_used, balance = None, None, None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calories Consumed", f"{int(calories_today)} kcal")
    c2.metric("TDEE (Auto)", f"{tdee_auto} kcal" if tdee_auto else "—")
    c3.metric("TDEE (Manual)", f"{st.session_state['manual_tdee']} kcal" if st.session_state["manual_tdee"] else "—")
    c4.metric("Balance (vs TDEE used)", f"{balance} kcal" if balance is not None else "—")

    st.subheader("💪 Protein Consumed")
    st.write(f"**Protein:** {int(protein_today)} g")
    if latest_weight and latest_weight > 0:
        ratio = protein_today / latest_weight
        st.write(f"**Latest Weight:** {latest_weight:.1f} kg")
        st.write(f"**Protein-to-Bodyweight Ratio:** {ratio:.2f} g/kg")
    st.write(f"**Total Carbs:** {int(carbs_today)} g")
    st.write(f"**Total Fat:** {int(fat_today)} g")

    # ----------------------------
    # Export Data (30 days + All)
    # ----------------------------
    with st.expander("📤 Export Data"):
        st.subheader("Food Logs")
        if not log_df.empty:
            # Last 30 Days (Food)
            log_df["date_dt"] = pd.to_datetime(log_df["date"], format="%d/%m/%Y", errors="coerce")
            cutoff = datetime.date.today() - datetime.timedelta(days=30)
            last_30_food = log_df[log_df["date_dt"].dt.date >= cutoff]
            if not last_30_food.empty:
                export_food_30 = last_30_food.drop(columns=["date_dt"])
                csv_food_30 = export_food_30.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Last 30 Days Food Log (CSV)",
                    data=csv_food_30,
                    file_name="last_30_days_food.csv",
                    mime="text/csv"
                )
            else:
                st.info("No food data in the last 30 days.")

            # ALL Food
            export_food_all = log_df.drop(columns=["date_dt"]) if "date_dt" in log_df.columns else log_df
            csv_food_all = export_food_all.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download ALL Food Log (CSV)",
                data=csv_food_all,
                file_name="all_food_log.csv",
                mime="text/csv"
            )

        st.subheader("Weight Logs")
        if not weight_df.empty:
            # Last 30 Days (Weight)
            weight_df["date_dt"] = pd.to_datetime(weight_df["date"], format="%d/%m/%Y", errors="coerce")
            cutoff_w = datetime.date.today() - datetime.timedelta(days=30)
            last_30_weight = weight_df[weight_df["date_dt"].dt.date >= cutoff_w]
            if not last_30_weight.empty:
                export_weight_30 = last_30_weight.drop(columns=["date_dt"])
                csv_weight_30 = export_weight_30.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Last 30 Days Weight Log (CSV)",
                    data=csv_weight_30,
                    file_name="last_30_days_weight.csv",
                    mime="text/csv"
                )
            else:
                st.info("No weight data in the last 30 days.")

            # ALL Weight
            export_weight_all = weight_df.drop(columns=["date_dt"]) if "date_dt" in weight_df.columns else weight_df
            csv_weight_all = export_weight_all.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download ALL Weight Log (CSV)",
                data=csv_weight_all,
                file_name="all_weight_log.csv",
                mime="text/csv"
            )

# ============================
# Run
# ============================
if __name__ == "__main__":
    main()