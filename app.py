import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Macro Tracker")

# --- File Paths ---
FOOD_DB_FILE = 'food_database.csv'
DAILY_LOG_FILE = 'daily_log.csv'

# --- Data Loading & Management ---
@st.cache_data
def load_food_database():
    try:
        df = pd.read_csv(FOOD_DB_FILE)
        df.columns = [col.lower().strip() for col in df.columns]
        df = df.sort_values(by='food_name').reset_index(drop=True)
        return df
    except FileNotFoundError:
        st.error(f"Error: '{FOOD_DB_FILE}' not found. Please create it.")
        return pd.DataFrame(columns=['food_name', 'calories', 'protein', 'carbs', 'fat'])

def load_daily_log():
    try:
        log_df = pd.read_csv(DAILY_LOG_FILE, parse_dates=['date'], dayfirst=True)
        return log_df.to_dict('records')
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return []

def save_daily_log(log_data):
    if not log_data:
        pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat']).to_csv(DAILY_LOG_FILE, index=False)
        return
    df = pd.DataFrame(log_data)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d/%m/%Y')
    df.to_csv(DAILY_LOG_FILE, index=False)

# --- Main App ---
def main():
    food_df = load_food_database()
    if 'all_logs' not in st.session_state:
        st.session_state.all_logs = load_daily_log()
        for entry in st.session_state.all_logs:
            if isinstance(entry['date'], str):
                entry['date'] = datetime.strptime(entry['date'], '%d/%m/%Y')

    st.title("🥗 Personal Macro Tracker")

    # --- Date Selector ---
    today = datetime.now().date()
    today_str = today.strftime('%d/%m/%Y')
    all_dates = {entry['date'].strftime('%d/%m/%Y') for entry in st.session_state.all_logs}
    all_dates.add(today_str)
    sorted_dates = sorted(list(all_dates), key=lambda x: datetime.strptime(x, '%d/%m/%Y'), reverse=True)
    
    selected_date_str = st.selectbox("Select date to view log", sorted_dates)
    selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
    daily_log = [e for e in st.session_state.all_logs if e['date'].date() == selected_date]

    # --- Form for Logging New Food ---
    if "food_to_log" in st.session_state:
        food_data = st.session_state.food_to_log
        food_name_display = food_data['food_name'].replace('_', ' ').title()

        with st.expander(f"Log: {food_name_display}", expanded=True):
            with st.form(key="log_food_form"):
                base_amount_str = food_data['food_name'].split('_')[-1]
                units = {'100g': 'grams (g)', 'scoop': 'scoop(s)', 'slice': 'slice(s)'}
                unit = next((u for k, u in units.items() if k in base_amount_str), "unit(s)")

                amount = st.number_input(f"Amount ({unit})", min_value=0.1, value=1.0, step=0.1)
                
                submitted = st.form_submit_button("Log Food")
                if submitted:
                    base_amount = 100.0 if '100g' in base_amount_str else 1.0
                    multiplier = amount / base_amount if base_amount != 1.0 else amount
                    
                    st.session_state.all_logs.insert(0, {
                        'date': datetime.now(), 'name': food_name_display, 'amount_logged': f"{amount} {unit}",
                        'calories': food_data['calories'] * multiplier, 'protein': food_data['protein'] * multiplier,
                        'carbs': food_data['carbs'] * multiplier, 'fat': food_data['fat'] * multiplier,
                    })
                    save_daily_log(st.session_state.all_logs)
                    
                    del st.session_state['food_to_log']
                    st.rerun()

    # --- Daily Totals ---
    st.subheader(f"📊 Totals for {selected_date_str}")
    if daily_log:
        totals = {k: sum(item.get(k, 0) for item in daily_log) for k in ['calories', 'protein', 'carbs', 'fat']}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Calories", f"{totals['calories']:.0f} kcal")
        c2.metric("Protein", f"{totals['protein']:.1f} g")
        c3.metric("Carbs", f"{totals['carbs']:.1f} g")
        c4.metric("Fat", f"{totals['fat']:.1f} g")
    else:
        st.info("No items logged for this date.")

    st.markdown("---")
    
    # --- Main Layout (Database and Log) ---
    col_food, col_log = st.columns([2, 1.5])

    with col_food:
        st.subheader("🥑 Food Database")
        search = st.text_input("Search for a food item...")
        df = food_df[food_df['food_name'].str.contains(search, case=False)] if search else food_df
        for _, row in df.iterrows():
            name = row['food_name'].replace('_', ' ').title()
            if st.button(name, key=f"log_{row['food_name']}", use_container_width=True):
                st.session_state.food_to_log = row.to_dict()
                st.rerun()

    with col_log:
        st.subheader(f"📝 Log for {selected_date_str}")
        if not daily_log:
            st.write("No items logged.")
        else:
            indices = [i for i, e in enumerate(st.session_state.all_logs) if e['date'].date() == selected_date]
            for i in reversed(indices):
                entry = st.session_state.all_logs[i]
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"**{entry['name']}** ({entry.get('amount_logged', '')})")
                    macros = (f"🔥 {entry.get('calories', 0):.0f} kcal | 💪 {entry.get('protein', 0):.1f}g P | "
                              f"🍞 {entry.get('carbs', 0):.1f}g C | 🥑 {entry.get('fat', 0):.1f}g F")
                    c1.text(macros)
                    if c2.button("Del", key=f"del_{i}", use_container_width=True):
                        st.session_state.all_logs.pop(i)
                        save_daily_log(st.session_state.all_logs)
                        st.rerun()

if __name__ == "__main__":
    main()
