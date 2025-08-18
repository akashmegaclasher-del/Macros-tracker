import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials   # modern replacement

# ---------------- LOAD FOOD DATABASE CSV ---------------- #
@st.cache_data
def load_food_df():
    df = pd.read_csv("food_database.csv")
    df.columns = df.columns.str.strip().str.lower()  # normalize headers
    return df

food_df = load_food_df()

# ---------------- GOOGLE SHEETS SETUP ---------------- #
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

# Load credentials from Streamlit secrets
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
client = gspread.authorize(creds)

# Replace with your Google Sheet name
sheet = client.open("MacroTracker")

def get_or_create_ws(name, headers):
    """Fetch worksheet or create it with headers if missing/empty"""
    try:
        ws = sheet.worksheet(name)
        current_headers = ws.row_values(1)
        if not current_headers:  # if sheet exists but empty
            ws.append_row(headers)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="1000", cols="20")
        ws.append_row(headers)
        return ws

# Initialize tabs with correct headers
food_ws = get_or_create_ws("daily_log", ["Date", "Food", "Amount (g)", "Calories", "Protein", "Carbs", "Fat"])
weight_ws = get_or_create_ws("weight_log", ["Date", "Weight"])
profile_ws = get_or_create_ws("Profile", ["Sex", "Age", "Height", "Weight", "Activity", "ManualTDEE"])

# ---------------- FOOD DATABASE ---------------- #
@st.cache_data
def load_food_database():
    df = pd.read_csv("food_database.csv")

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    required = ["food_name", "calories", "protein", "carbs", "fat"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in food_database.csv")

    food_dict = {}
    for _, row in df.iterrows():
        food_dict[row["food_name"]] = {
            "cal": row["calories"],
            "p": row["protein"],
            "c": row["carbs"],
            "f": row["fat"],
        }
    return food_dict

FOOD_DB = load_food_database()

# ---------------- HELPERS ---------------- #
def get_today():
    return datetime.date.today().strftime("%d/%m/%Y")

# Always have today_str available for logging
today_str = get_today()

# ---------------- INITIALIZE SESSION STATE ---------------- #
if "all_logs" not in st.session_state:
    st.session_state.all_logs = []

if "selected_date" not in st.session_state:
    st.session_state.selected_date = f"{today_str} (Today)"

def save_daily_log(logs):
    """Save today's log entries to Google Sheets (daily_log tab)."""
    import gspread
    from google.oauth2.service_account import Credentials

    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open("MacroTracker").worksheet("daily_log")

    # Convert logs to DataFrame
    if len(logs) > 0:
        df = pd.DataFrame(logs)
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
    else:
        # If no logs, just clear the sheet
        sheet.clear()

def _normalize(s: str) -> str:
    """Return alphanumeric lowercased version of a header for matching."""
    if s is None:
        return ""
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())

def fetch_logs(ws, expected_headers=None):
    """
    Read worksheet and return DataFrame with columns normalized to expected_headers.
    Always returns DataFrame with the expected headers.
    """
    if expected_headers is None:
        expected_headers = ["Date", "Food", "Amount (g)", "Calories", "Protein", "Carbs", "Fat"]

    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=expected_headers)

    df = pd.DataFrame(records)
    actual_cols = list(df.columns)
    actual_norm_map = {_normalize(c): c for c in actual_cols}
    expected_norm_map = {_normalize(h): h for h in expected_headers}

    new_data = {}
    for exp_norm, display_name in expected_norm_map.items():
        if exp_norm in actual_norm_map:
            orig_col = actual_norm_map[exp_norm]
            new_data[display_name] = df[orig_col].astype(object)
        else:
            new_data[display_name] = pd.Series([None] * len(df))

    new_df = pd.DataFrame(new_data)
    for col in new_df.select_dtypes(include=["object"]).columns:
        new_df[col] = new_df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    return new_df

def log_food(food, grams):
    entry = FOOD_DB[food]
    cals = round((grams/100) * entry["cal"], 1)
    p = round((grams/100) * entry["p"], 1)
    c = round((grams/100) * entry["c"], 1)
    f = round((grams/100) * entry["f"], 1)
    food_ws.append_row([get_today(), food, grams, cals, p, c, f])

def log_weight(weight):
    weight_ws.append_row([get_today(), weight])

def calculate_tdee(sex, age, height, weight, activity):
    if sex == "Male":
        bmr = 10*weight + 6.25*height - 5*age + 5
    else:
        bmr = 10*weight + 6.25*height - 5*age - 161
    return round(bmr * activity)

# ---------------- UI ---------------- #
st.title("🥗 Macro & Weight Tracker")

with st.sidebar:
    with st.expander("👤 Profile Settings", expanded=False):
        sex = st.selectbox("Sex", ["Male", "Female"])
        age = st.number_input("Age", 15, 90, 25)
        height = st.number_input("Height (cm)", 100, 220, 175)
        weight = st.number_input("Baseline Weight (kg)", 40, 200, 80)

        col1, col2 = st.columns(2)
        if col1.button("🏋️ Gym Day"):
            activity = 1.55
        elif col2.button("🛌 Rest Day"):
            activity = 1.2
        else:
            activity = 1.55

        manual_tdee = st.number_input("Manual TDEE (kcal, optional)", 0, 10000, 0)

        if st.button("Save Profile"):
            profile_ws.clear()
            profile_ws.append_row(["Sex", "Age", "Height", "Weight", "Activity", "ManualTDEE"])
            profile_ws.append_row([sex, age, height, weight, activity, manual_tdee])
            st.success("Profile saved!")

# ---------------- FOOD LOGGING UI ---------------- #
st.subheader("🥑 Food Database")
search_query = st.text_input("Search for a food item...", key="search_bar")

# Filter food database (loaded from food_database.csv)
filtered_df = food_df[food_df['food_name'].str.contains(search_query, case=False, na=False)] if search_query else food_df
st.markdown("Click on a food to log it.")

for _, row in filtered_df.iterrows():
    food_name = row['food_name'].replace('_', ' ').title()
    
    with st.popover(f"**{food_name}**"):
        with st.form(key=f"form_{row['food_name']}"):
            base_amount_str = row['food_name'].split('_')[-1]
            unit = "unit(s)"
            if '100g' in base_amount_str: 
                unit = "grams (g)"
            elif 'katori' in base_amount_str: 
                unit = "katori(s)"
            elif 'tbsp' in base_amount_str: 
                unit = "tablespoon(s)"
            elif 'scoop' in base_amount_str: 
                unit = "scoop(s)"
            elif 'slice' in base_amount_str: 
                unit = "slice(s)"
            elif 'medium' in base_amount_str: 
                unit = "item(s)"

            amount = st.number_input(f"Amount ({unit})", min_value=0.1, value=1.0, step=0.1)
            submit = st.form_submit_button("Log Food")

        if submit:
            # base amount = 100g if mentioned, otherwise treat as 1 unit
            base_amount = 100.0 if '100g' in base_amount_str else 1.0
            multiplier = amount / base_amount if base_amount != 1.0 else amount

            new_entry = {
                'Date': today_str,
                'Food': food_name,
                'Amount (g)': f"{amount} {unit}",
                'Calories': row['calories'] * multiplier,
                'Protein': row['protein'] * multiplier,
                'Carbs': row['carbs'] * multiplier,
                'Fat': row['fat'] * multiplier,
            }

            # Insert into session and Google Sheets
            st.session_state.all_logs.insert(0, new_entry)
            save_daily_log(st.session_state.all_logs)
            st.session_state.selected_date = f"{today_str} (Today)"
            st.success(f"Logged {amount} {unit} of {food_name}!")
            st.rerun()

# =========================
# 📊 Log History (UPDATED SECTION)
# =========================
st.subheader("📊 Log History")

# Add a date input to select which day to view
selected_date_obj = st.date_input("Select a date to view logs", datetime.date.today())
selected_date_str = selected_date_obj.strftime("%d/%m/%Y")

df_logs = pd.DataFrame(st.session_state.all_logs)

EXPECTED_COLUMNS = ['Date', 'Food', 'Amount (g)', 'Calories', 'Protein', 'Carbs', 'Fat']
if df_logs.empty:
    df_logs = pd.DataFrame(columns=EXPECTED_COLUMNS)

# Filter logs based on the selected date, not just today's date
day_logs = df_logs[df_logs["Date"] == selected_date_str].copy()
item_to_delete_index = None

# IMPORTANT: From here on, replace all instances of 'today_logs' with 'day_logs' in this section.
if not day_logs.empty:
    # ... the rest of your code for displaying the table and totals continues...
    # Just make sure to use 'day_logs' instead of 'today_logs'
    
    # For example:
    for index, row in day_logs.iterrows():
        # ... your column write logic
    
    totals = day_logs[numeric_cols].sum()
    # ... and so on
else:
    st.info(f"No food logged on {selected_date_str}.")

# ... your delete logic continues ...


# ---------------- DAILY SUMMARY ---------------- #
st.subheader("📈 Daily Summary")

calories = today_logs["Calories"].sum() if not today_logs.empty else 0
protein = today_logs["Protein"].sum() if not today_logs.empty else 0
carbs = today_logs["Carbs"].sum() if not today_logs.empty else 0
fat = today_logs["Fat"].sum() if not today_logs.empty else 0

profile_df = fetch_logs(profile_ws, ["Sex", "Age", "Height", "Weight", "Activity", "ManualTDEE"])
if not profile_df.empty:
    prof = profile_df.iloc[-1]
    tdee_auto = calculate_tdee(prof["Sex"], int(prof["Age"]), int(prof["Height"]), float(prof["Weight"]), float(prof["Activity"]))
    tdee_manual = int(prof["ManualTDEE"]) if int(prof["ManualTDEE"]) > 0 else None
else:
    tdee_auto, tdee_manual = 0, None

tdee_used = tdee_manual if tdee_manual else tdee_auto
balance = calories - tdee_used if tdee_used else 0
latest_weight = profile_df.iloc[-1]["Weight"] if not profile_df.empty else weight
ratio = round(protein / latest_weight, 2) if latest_weight else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories Consumed", f"{calories} kcal")
col2.metric("TDEE (Auto)", f"{tdee_auto} kcal")
col3.metric("TDEE (Manual)", f"{tdee_manual if tdee_manual else '—'}")
col4.metric("Balance (vs TDEE)", f"{balance} kcal")

st.markdown(f"**Protein Consumed:** {protein} g")
st.markdown(f"**Latest Weight:** {latest_weight} kg")
st.markdown(f"**Protein to Bodyweight Ratio:** {ratio} g/kg")
st.markdown(f"**Carbs:** {carbs} g")
st.markdown(f"**Fat:** {fat} g")

# ---------------- WEIGHT LOGGING ---------------- #
st.subheader("⚖️ Log Weight")
new_weight = st.number_input("Today's Weight (kg)", 0.0, 300.0, value=float(weight))
if st.button("Log Weight"):
    log_weight(new_weight)
    st.success(f"Logged weight {new_weight} kg")

# ---------------- DOWNLOAD DATA ---------------- #
st.subheader("⬇️ Download Logs")
csv_food = df_logs.to_csv(index=False).encode("utf-8")
st.download_button("Download 30-day Food Logs", csv_food, "food_logs.csv", "text/csv")

df_weights = fetch_logs(weight_ws, ["Date", "Weight"])
csv_weights = df_weights.to_csv(index=False).encode("utf-8")
st.download_button("Download Weight Logs", csv_weights, "weight_logs.csv", "text/csv")

# ---------------- WEIGHT CHART ---------------- #
st.subheader("📉 Weight Trend")

if not df_weights.empty:
    df_weights["Date"] = pd.to_datetime(df_weights["Date"], format="%d/%m/%Y", errors="coerce")
    df_weights = df_weights.dropna(subset=["Date"])
    df_weights = df_weights.sort_values("Date")

    st.line_chart(df_weights.set_index("Date")["Weight"])
else:
    st.info("No weight logs yet.")
