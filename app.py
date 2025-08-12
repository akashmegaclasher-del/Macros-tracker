import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Macro Tracker")

# --- File Paths ---
FOOD_DB_FILE = 'food_database.csv'
DAILY_LOG_FILE = 'daily_log.csv'  # Stores up to 30 days of logs

# --- Data Loading & Management ---
@st.cache_data
def load_food_database():
    """Loads and sorts the food database."""
    try:
        df = pd.read_csv(FOOD_DB_FILE)
        df.columns = [col.lower().strip() for col in df.columns]
        return df.sort_values(by='food_name').reset_index(drop=True)
    except FileNotFoundError:
        st.error(f"Error: '{FOOD_DB_FILE}' not found. Please create it in the same folder.")
        return pd.DataFrame()

def load_log_df():
    """Loads the log file into a DataFrame with a proper datetime column."""
    try:
        log_df = pd.read_csv(DAILY_LOG_FILE)
        # Convert date column to datetime objects, trying different formats
        log_df['date'] = pd.to_datetime(log_df['date'], dayfirst=True, errors='coerce')
        log_df.dropna(subset=['date'], inplace=True) # Remove rows that couldn't be parsed
        return log_df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        # Return an empty DataFrame with correct columns if file is missing or empty
        return pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat'])

def save_log_df(df):
    """Saves the log DataFrame, pruning old entries and formatting the date."""
    if df.empty:
        # If the dataframe is empty, write an empty file with headers
        pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat']).to_csv(DAILY_LOG_FILE, index=False)
        return

    df_to_save = df.copy()
    # Ensure date column is datetime before filtering
    df_to_save['date'] = pd.to_datetime(df_to_save['date'])
    
    # Prune entries older than 30 days
    cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=30))
    df_to_save = df_to_save[df_to_save['date'] >= cutoff]
    
    # Save dates in a consistent string format (DD/MM/YYYY)
    df_to_save['date'] = df_to_save['date'].dt.strftime('%d/%m/%Y')
    df_to_save.to_csv(DAILY_LOG_FILE, index=False)


# --- Main App ---
def main():
    food_df = load_food_database()
    
    # Initialize session state with a DataFrame, ensuring it's always fresh
    if 'log_df' not in st.session_state:
        st.session_state.log_df = load_log_df()

    st.title("🥗 Personal Macro Tracker")

    # --- Date Selector ---
    # FIX: Always get the current date inside the main app function
    today = datetime.now().date()
    
    # Get unique dates from the log DataFrame as date objects
    if not st.session_state.log_df.empty:
        available_dates = sorted(st.session_state.log_df['date'].dt.date.unique(), reverse=True)
    else:
        available_dates = []

    # Ensure today is always an option
    if today not in available_dates:
        available_dates.insert(0, today)

    # Format dates for display in the selectbox
    date_display_map = {d: d.strftime('%d/%m/%Y') + (" (Today)" if d == today else "") for d in available_dates}
    
    # Set default selected date to today
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = today

    # If the stored selected date is somehow invalid (e.g., from a past session), reset to today
    if st.session_state.selected_date not in available_dates:
        st.session_state.selected_date = today

    # Create the date selector UI
    col_today, col_dropdown = st.columns([0.3, 1])
    with col_today:
        if st.button("📅 Today"):
            st.session_state.selected_date = today
            st.rerun() 

    with col_dropdown:
        # The key for the selectbox is now just 'date_selector'
        selected_date = st.selectbox(
            "Select date to view log",
            options=available_dates,
            format_func=lambda d: date_display_map[d],
            key='date_selector',
            index=available_dates.index(st.session_state.selected_date) # Set index based on session state
        )
    
    # Update session state if the user changes the date
    st.session_state.selected_date = selected_date

    # Filter logs for the selected date
    daily_log_df = st.session_state.log_df[st.session_state.log_df['date'].dt.date == selected_date]

    # --- Daily Totals ---
    st.subheader(f"📊 Totals for {selected_date.strftime('%d/%m/%Y')}")
    if not daily_log_df.empty:
        total_macros = daily_log_df[['calories', 'protein', 'carbs', 'fat']].sum()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Calories", f"{total_macros['calories']:.0f} kcal")
        col2.metric("Protein", f"{total_macros['protein']:.1f} g")
        col3.metric("Carbs", f"{total_macros['carbs']:.1f} g")
        col4.metric("Fat", f"{total_macros['fat']:.1f} g")
    else:
        st.info("No items logged for this date.")

    # --- Food Logging & Display ---
    st.markdown("---")
    col_food, col_log = st.columns([2, 1.5])
    with col_food:
        st.subheader("🥑 Food Database")
        search_query = st.text_input("Search for a food item...", key="search_bar")
        filtered_df = food_df[food_df['food_name'].str.contains(search_query, case=False, na=False)] if search_query else food_df
        
        for index, row in filtered_df.iterrows():
            food_name = row['food_name'].replace('_', ' ').title()
            with st.popover(f"**{food_name}**"):
                # Use the food name and selected date to create a unique key for the form
                form_key = f"form_{row['food_name']}_{selected_date.strftime('%Y%m%d')}"
                with st.form(key=form_key):
                    base_amount_str = row['food_name'].split('_')[-1]
                    unit = "unit(s)"
                    if '100g' in base_amount_str: unit = "grams (g)"
                    elif 'katori' in base_amount_str: unit = "katori(s)"
                    elif 'tbsp' in base_amount_str: unit = "tablespoon(s)"
                    elif 'scoop' in base_amount_str: unit = "scoop(s)"
                    
                    amount = st.number_input(f"Amount ({unit})", min_value=0.1, value=1.0, step=0.1)
                    submitted = st.form_submit_button("Log Food")

                    if submitted:
                        base_amount = 100.0 if '100g' in base_amount_str else 1.0
                        multiplier = amount / base_amount if base_amount != 1.0 else amount
                        new_entry = {
                            'date': pd.to_datetime(selected_date), # Log to the selected date
                            'name': food_name,
                            'amount_logged': f"{amount} {unit}",
                            'calories': float(row.get('calories', 0)) * multiplier,
                            'protein': float(row.get('protein', 0)) * multiplier,
                            'carbs': float(row.get('carbs', 0)) * multiplier,
                            'fat': float(row.get('fat', 0)) * multiplier,
                        }
                        new_df = pd.DataFrame([new_entry])
                        st.session_state.log_df = pd.concat([st.session_state.log_df, new_df], ignore_index=True)
                        save_log_df(st.session_state.log_df)
                        st.session_state.selected_date = selected_date # Stay on the current date
                        st.success(f"Logged {amount} {unit} of {food_name}!")
                        st.rerun()

    with col_log:
        st.subheader(f"📝 Log for {selected_date.strftime('%d/%m/%Y')}")
        if daily_log_df.empty:
            st.write("No items logged.")
        else:
            for i, entry in daily_log_df.iloc[::-1].iterrows():
                with st.container(border=True):
                    st.markdown(f"**{entry['name']}** ({entry.get('amount_logged','')})")
                    macros_text = f"🔥 {entry.get('calories',0):.0f} kcal | 💪 {entry.get('protein',0):.1f}g P | 🍞 {entry.get('carbs',0):.1f}g C | 🥑 {entry.get('fat',0):.1f}g F"
                    st.text(macros_text)
                    
                    if st.button("Delete", key=f"del_{i}", type="secondary"):
                        st.session_state.log_df.drop(index=i, inplace=True)
                        save_log_df(st.session_state.log_df)
                        st.rerun()

if __name__ == "__main__":
    main()
