import streamlit as st
import pandas as pd
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Macro Tracker")

# --- File Paths ---
FOOD_DB_FILE = 'food_database.csv'
DAILY_LOG_FILE = 'daily_log.csv' # File to store the current day's log

# --- Data Loading & Management ---
@st.cache_data
def load_food_database():
    """Loads the food database from the CSV file."""
    try:
        df = pd.read_csv(FOOD_DB_FILE)
        df.columns = [col.lower().strip() for col in df.columns]
        # Sort the database alphabetically by food name
        df = df.sort_values(by='food_name').reset_index(drop=True)
        return df
    except FileNotFoundError:
        st.error(f"Error: '{FOOD_DB_FILE}' not found. Please create it in the same folder.")
        return pd.DataFrame(columns=['food_name', 'calories', 'protein', 'carbs', 'fat'])

def load_daily_log():
    """Loads today's log from the CSV file. If the log is from a previous day, it starts fresh."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    try:
        log_df = pd.read_csv(DAILY_LOG_FILE)
        # Check if the log file is actually from today
        if not log_df.empty and log_df['date'].iloc[0] == today_str:
            return log_df.to_dict('records')
    except (FileNotFoundError, pd.errors.EmptyDataError):
        # If file doesn't exist or is empty, no problem, we'll start a new one
        pass
    # Return an empty list if no valid log for today is found
    return []

def save_daily_log(log_data):
    """Saves the current day's log to the CSV file."""
    if not log_data:
        # If the log is empty, create an empty file or clear the existing one
        pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat']).to_csv(DAILY_LOG_FILE, index=False)
    else:
        df = pd.DataFrame(log_data)
        df.to_csv(DAILY_LOG_FILE, index=False)

# --- Main App ---
def main():
    """The main function that runs the Streamlit application."""
    # --- Initialization ---
    food_df = load_food_database()
    
    # Initialize the session state by loading today's log from the file
    if 'daily_log' not in st.session_state:
        st.session_state.daily_log = load_daily_log()

    # --- UI Layout ---
    st.title("🥗 Personal Macro Tracker")
    
    # --- Display Total Macros for the Current Session ---
    st.subheader(f"📊 Totals for Today ({datetime.now().strftime('%B %d, %Y')})")
    if st.session_state.daily_log:
        total_macros = {
            'calories': sum(item['calories'] for item in st.session_state.daily_log),
            'protein': sum(item['protein'] for item in st.session_state.daily_log),
            'carbs': sum(item['carbs'] for item in st.session_state.daily_log),
            'fat': sum(item['fat'] for item in st.session_state.daily_log)
        }
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Calories", f"{total_macros['calories']:.0f} kcal")
        col2.metric("Protein", f"{total_macros['protein']:.1f} g")
        col3.metric("Carbs", f"{total_macros['carbs']:.1f} g")
        col4.metric("Fat", f"{total_macros['fat']:.1f} g")
    else:
        st.info("Log your first item to see today's totals.")

    st.markdown("---")

    # --- Main Interface ---
    col_food, col_log = st.columns([2, 1.5])

    with col_food:
        st.subheader("🥑 Food Database")
        
        # --- Search Bar ---
        search_query = st.text_input("Search for a food item...", key="search_bar")
        
        # Filter the DataFrame based on the search query
        if search_query:
            filtered_df = food_df[food_df['food_name'].str.contains(search_query, case=False, na=False)]
        else:
            filtered_df = food_df
        
        st.markdown("Click on a food to log it.")
        
        # Display food items from the filtered list
        for index, row in filtered_df.iterrows():
            food_name = row['food_name'].replace('_', ' ').title()
            
            with st.expander(f"**{food_name}**", expanded=False):
                base_amount_str = row['food_name'].split('_')[-1]
                unit = "unit(s)"

                if '100g' in base_amount_str: unit = "grams (g)"
                elif 'katori' in base_amount_str: unit = "katori(s)"
                elif 'tbsp' in base_amount_str: unit = "tablespoon(s)"
                elif 'scoop' in base_amount_str: unit = "scoop(s)"
                elif 'slice' in base_amount_str: unit = "slice(s)"
                elif 'medium' in base_amount_str: unit = "item(s)"
                
                amount = st.number_input(f"Amount ({unit})", min_value=0.1, value=1.0, step=0.1, key=f"amount_{row['food_name']}")
                
                if st.button("Log Food", key=f"btn_{row['food_name']}"):
                    base_amount = 100.0 if '100g' in base_amount_str else 1.0
                    multiplier = amount / base_amount if base_amount != 1.0 else amount

                    new_entry = {
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'name': food_name,
                        'amount_logged': f"{amount} {unit}",
                        'calories': row['calories'] * multiplier,
                        'protein': row['protein'] * multiplier,
                        'carbs': row['carbs'] * multiplier,
                        'fat': row['fat'] * multiplier,
                    }
                    
                    st.session_state.daily_log.insert(0, new_entry)
                    save_daily_log(st.session_state.daily_log)
                    st.success(f"Logged {amount} {unit} of {food_name}!")
                    st.rerun()

    with col_log:
        st.subheader("📝 Today's Log")
        if not st.session_state.daily_log:
            st.write("Your logged items for today will appear here.")
        else:
            # Display each logged item
            for i, entry in enumerate(st.session_state.daily_log):
                with st.container(border=True):
                    st.markdown(f"**{entry['name']}** ({entry['amount_logged']})")
                    macros_text = (
                        f"🔥 {entry['calories']:.0f} kcal | "
                        f"💪 {entry['protein']:.1f}g P | "
                        f"🍞 {entry['carbs']:.1f}g C | "
                        f"🥑 {entry['fat']:.1f}g F"
                    )
                    st.text(macros_text)
                    if st.button("Delete", key=f"del_{i}", type="secondary"):
                        st.session_state.daily_log.pop(i)
                        save_daily_log(st.session_state.daily_log)
                        st.rerun()

if __name__ == "__main__":
    main()
