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
    try:
        df = pd.read_csv(FOOD_DB_FILE)
        df.columns = [col.lower().strip() for col in df.columns]
        df = df.sort_values(by='food_name').reset_index(drop=True)
        return df
    except FileNotFoundError:
        st.error(f"Error: '{FOOD_DB_FILE}' not found. Please create it in the same folder.")
        return pd.DataFrame(columns=['food_name', 'calories', 'protein', 'carbs', 'fat'])

def load_daily_log():
    today = datetime.now().date()
    try:
        log_df = pd.read_csv(DAILY_LOG_FILE, parse_dates=['date'], dayfirst=True)
        cutoff_date = today - timedelta(days=30)
        log_df = log_df[log_df['date'].dt.date >= cutoff_date]
        log_df['date'] = log_df['date'].dt.strftime('%d/%m/%Y')
        return log_df.to_dict('records')
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return []

def save_daily_log(log_data):
    if not log_data:
        pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat']).to_csv(DAILY_LOG_FILE, index=False)
    else:
        df = pd.DataFrame(log_data)
        df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y', dayfirst=True)
        cutoff_date = datetime.now().date() - timedelta(days=30)
        df = df[df['date'].dt.date >= cutoff_date]
        df['date'] = df['date'].dt.strftime('%d/%m/%Y')
        df.to_csv(DAILY_LOG_FILE, index=False)

# --- Main App ---
def main():
    food_df = load_food_database()
    if 'all_logs' not in st.session_state:
        st.session_state.all_logs = load_daily_log()

    st.title("🥗 Personal Macro Tracker")

    # --- Date Selector with Today Button ---
    today_str = datetime.now().strftime('%d/%m/%Y')

    available_dates = sorted(
        {entry['date'] for entry in st.session_state.all_logs},
        key=lambda x: datetime.strptime(x, '%d/%m/%Y'),
        reverse=True
    )
    if today_str not in available_dates:
        available_dates.insert(0, today_str)
    else:
        available_dates.remove(today_str)
        available_dates.insert(0, today_str)

    available_dates_display = [
        f"{d} (Today)" if d == today_str else d for d in available_dates
    ]

    if 'selected_date' not in st.session_state or st.session_state.selected_date not in available_dates_display:
        st.session_state.selected_date = f"{today_str} (Today)"

    col_today, col_dropdown = st.columns([0.3, 1])
    with col_today:
        if st.button("📅 Today"):
            st.session_state.selected_date = f"{today_str} (Today)"

    with col_dropdown:
        # Handle potential index error if selected_date is not in the list
        try:
            current_index = available_dates_display.index(st.session_state.selected_date)
        except ValueError:
            current_index = 0
            st.session_state.selected_date = available_dates_display[0]

        selected_display = st.selectbox(
            "Select date to view log",
            available_dates_display,
            index=current_index
        )

    selected_date = selected_display.replace(" (Today)", "")
    st.session_state.selected_date = selected_display
    selected_date_obj = datetime.strptime(selected_date, '%d/%m/%Y').date()

    daily_log = [entry for entry in st.session_state.all_logs if entry['date'] == selected_date]

    # --- Daily Totals ---
    st.subheader(f"📊 Totals for {selected_date}")
    if daily_log:
        total_macros = {
            'calories': sum(item.get('calories', 0) for item in daily_log),
            'protein': sum(item.get('protein', 0) for item in daily_log),
            'carbs': sum(item.get('carbs', 0) for item in daily_log),
            'fat': sum(item.get('fat', 0) for item in daily_log)
        }
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Calories", f"{total_macros['calories']:.0f} kcal")
        col2.metric("Protein", f"{total_macros['protein']:.1f} g")
        col3.metric("Carbs", f"{total_macros['carbs']:.1f} g")
        col4.metric("Fat", f"{total_macros['fat']:.1f} g")
    else:
        st.info("No items logged for this date.")

    # --- Download CSV ---
    if st.session_state.all_logs:
        df_export = pd.DataFrame(st.session_state.all_logs)
        if not df_export.empty:
            df_export['date'] = pd.to_datetime(df_export['date'], format='%d/%m/%Y', dayfirst=True).dt.strftime('%d/%m/%Y')
            csv_data = df_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Last 30 Days Log (CSV)",
                data=csv_data,
                file_name="macro_log_last_30_days.csv",
                mime="text/csv"
            )

    # --- Trends Chart ---
    st.markdown("### 📈 Macro Trends (Last 30 Days)")
    if st.session_state.all_logs:
        df_all = pd.DataFrame(st.session_state.all_logs)
        df_all['date'] = pd.to_datetime(df_all['date'], format='%d/%m/%Y', dayfirst=True)
        df_trends = df_all.groupby('date', as_index=False).agg({
            'calories': 'sum',
            'protein': 'sum',
            'carbs': 'sum',
            'fat': 'sum'
        }).sort_values('date')

        metrics = ['calories', 'protein', 'carbs', 'fat']
        selected_metrics = st.multiselect(
            "Select metrics to display",
            options=metrics,
            default=metrics
        )
        show_smoothing = st.checkbox("Show 7-day rolling average", value=True)

        colors = {
            'calories': 'orange',
            'protein': 'blue',
            'carbs': 'green',
            'fat': 'red'
        }

        if selected_metrics:
            df_plot = df_trends.copy()
            
            num_days_with_data = df_plot['date'].nunique()
            plot_mode = 'markers' if num_days_with_data == 1 else 'lines+markers'
            
            date_range_days = (df_plot['date'].max() - df_plot['date'].min()).days if num_days_with_data > 1 else 1
            tick_interval = "D1" if date_range_days <= 14 else "M1"

            if show_smoothing and num_days_with_data > 1:
                for metric in metrics:
                    df_plot[f"{metric} (7d avg)"] = df_plot[metric].rolling(window=7, min_periods=1).mean()

            fig = go.Figure()

            def add_trace_to_fig(metric_name, y_axis, plot_mode):
                fig.add_trace(go.Scatter(
                    x=df_plot['date'], y=df_plot[metric_name], mode=plot_mode,
                    name=metric_name, line=dict(color=colors[metric_name]),
                    yaxis=y_axis, connectgaps=False
                ))
                if show_smoothing and num_days_with_data > 1:
                    fig.add_trace(go.Scatter(
                        x=df_plot['date'], y=df_plot[f"{metric_name} (7d avg)"], mode='lines',
                        name=f"{metric_name} (7d avg)", line=dict(color=colors[metric_name], dash='dash'),
                        yaxis=y_axis
                    ))

            if 'calories' in selected_metrics:
                add_trace_to_fig('calories', 'y1', plot_mode)
            for metric in ['protein', 'carbs', 'fat']:
                if metric in selected_metrics:
                    add_trace_to_fig(metric, 'y2', plot_mode)

            fig.update_layout(
                xaxis=dict(title="Date", type='date', range=[df_plot['date'].min() - timedelta(days=1), df_plot['date'].max() + timedelta(days=1)]),
                yaxis=dict(title="Calories", side="left", rangemode="tozero"),
                yaxis2=dict(title="Protein / Carbs / Fat (g)", overlaying="y", side="right", rangemode="tozero"),
                legend=dict(orientation="h", y=-0.25),
                margin=dict(l=40, r=40, t=40, b=80),
                height=500
            )
            fig.update_xaxes(tickformat="%d/%m", tickangle=-45, dtick=tick_interval)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one metric to display.")
    else:
        st.write("No data to display trends.")


    st.markdown("---")

    # --- Dialog for Logging New Food ---
    if "food_to_log" in st.session_state:
        # Define the callback function that saves the input's state
        def update_log_amount():
            st.session_state.log_amount_value = st.session_state.log_amount_input
        
        food_data = st.session_state.food_to_log
        food_name_display = food_data['food_name'].replace('_', ' ').title()

        @st.dialog(f"Log {food_name_display}")
        def log_food_dialog():
            st.subheader(f"Log: {food_name_display}")
            base_amount_str = food_data['food_name'].split('_')[-1]
            unit_match = {'100g': 'grams (g)', 'katori': 'katori(s)', 'tbsp': 'tablespoon(s)', 'scoop': 'scoop(s)', 'slice': 'slice(s)', 'medium': 'item(s)'}
            unit = next((v for k, v in unit_match.items() if k in base_amount_str), "unit(s)")
            
            # This number input now uses on_change for robust state handling
            st.number_input(
                f"Amount ({unit})", 
                min_value=0.1, 
                value=st.session_state.get('log_amount_value', 1.0), # Use the saved value
                step=0.1, 
                key="log_amount_input", # Assign a key for the callback
                on_change=update_log_amount # The callback function
            )
            
            if st.button("Log Food"):
                amount = st.session_state.get('log_amount_value', 1.0) # Get the final value
                base_amount = 100.0 if '100g' in base_amount_str else 1.0
                multiplier = amount / base_amount if base_amount != 1.0 else amount
                new_entry = {
                    'date': datetime.now(),
                    'name': food_name_display,
                    'amount_logged': f"{amount} {unit}",
                    'calories': food_data['calories'] * multiplier,
                    'protein': food_data['protein'] * multiplier,
                    'carbs': food_data['carbs'] * multiplier,
                    'fat': food_data['fat'] * multiplier,
                }
                st.session_state.all_logs.insert(0, new_entry)
                save_daily_log(st.session_state.all_logs)
                
                # Clean up session state keys
                del st.session_state.food_to_log
                if 'log_amount_value' in st.session_state:
                    del st.session_state.log_amount_value
                if 'log_amount_input' in st.session_state:
                    del st.session_state.log_amount_input
                st.rerun()

        log_food_dialog()

    # --- Main Layout (Database and Log) ---
    col_food, col_log = st.columns([2, 1.5])

    with col_food:
        st.subheader("🥑 Food Database")
        search_query = st.text_input("Search for a food item...")
        filtered_df = food_df[food_df['food_name'].str.contains(search_query, case=False, na=False)] if search_query else food_df
        
        st.markdown("Click on a food to log it.")
        for _, row in filtered_df.iterrows():
            food_name_display = row['food_name'].replace('_', ' ').title()
            if st.button(food_name_display, key=f"log_{row['food_name']}", use_container_width=True):
                st.session_state.food_to_log = row.to_dict()
                st.rerun()

    with col_log:
        st.subheader(f"📝 Log for {selected_date}")
        if not daily_log:
            st.write("No items logged.")
        else:
            # Create a list of indices matching the daily_log to find the original index in all_logs
            log_indices = [i for i, entry in enumerate(st.session_state.all_logs) if entry['date'].date() == datetime.strptime(selected_date, '%d/%m/%Y').date()]
            
            for original_log_index in reversed(log_indices): # Reverse to avoid index errors on deletion
                entry = st.session_state.all_logs[original_log_index]
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f"**{entry['name']}** ({entry.get('amount_logged', '')})")
                        macros_text = (
                            f"🔥 {entry.get('calories', 0):.0f} kcal | "
                            f"💪 {entry.get('protein', 0):.1f}g P | "
                            f"🍞 {entry.get('carbs', 0):.1f}g C | "
                            f"🥑 {entry.get('fat', 0):.1f}g F"
                        )
                        st.text(macros_text)
                    with c2:
                        if st.button("Delete", key=f"del_{original_log_index}", use_container_width=True):
                            st.session_state.all_logs.pop(original_log__index)
                            save_daily_log(st.session_state.all_logs)
                            st.rerun()
if __name__ == "__main__":
    main()
