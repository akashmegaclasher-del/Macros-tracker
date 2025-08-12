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
        log_df = pd.read_csv(DAILY_LOG_FILE, parse_dates=['date'])
        cutoff_date = today - timedelta(days=30)
        log_df = log_df[log_df['date'].dt.date >= cutoff_date]
        return log_df.to_dict('records')
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return []

def save_daily_log(log_data):
    if not log_data:
        pd.DataFrame(columns=['date', 'name', 'amount_logged', 'calories', 'protein', 'carbs', 'fat']).to_csv(DAILY_LOG_FILE, index=False)
    else:
        df = pd.DataFrame(log_data)
        df['date'] = pd.to_datetime(df['date'])
        cutoff_date = datetime.now().date() - timedelta(days=30)
        df = df[df['date'].dt.date >= cutoff_date]
        df.to_csv(DAILY_LOG_FILE, index=False)

# --- Main App ---
def main():
    food_df = load_food_database()
    if 'all_logs' not in st.session_state:
        st.session_state.all_logs = load_daily_log()

    st.title("🥗 Personal Macro Tracker")

    # --- Date Selector ---
    available_dates = sorted({entry['date'] for entry in st.session_state.all_logs}, reverse=True)
    if not available_dates:
        available_dates = [datetime.now().strftime('%Y-%m-%d')]

    selected_date = st.selectbox("📅 Select date to view log", available_dates)
    selected_date_obj = pd.to_datetime(selected_date).date()
    daily_log = [entry for entry in st.session_state.all_logs if pd.to_datetime(entry['date']).date() == selected_date_obj]

    # --- Daily Totals ---
    st.subheader(f"📊 Totals for {selected_date_obj.strftime('%B %d, %Y')}")
    if daily_log:
        total_macros = {
            'calories': sum(item['calories'] for item in daily_log),
            'protein': sum(item['protein'] for item in daily_log),
            'carbs': sum(item['carbs'] for item in daily_log),
            'fat': sum(item['fat'] for item in daily_log)
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
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Last 30 Days Log (CSV)",
            data=csv_data,
            file_name="macro_log_last_30_days.csv",
            mime="text/csv"
        )

    # --- Trends Chart with Dual Axis & Fixed Colors ---
    st.markdown("### 📈 Macro Trends (Last 30 Days)")
    if st.session_state.all_logs:
        df_all = pd.DataFrame(st.session_state.all_logs)
        df_all['date'] = pd.to_datetime(df_all['date'])
        df_trends = df_all.groupby('date', as_index=False).agg({
            'calories': 'sum',
            'protein': 'sum',
            'carbs': 'sum',
            'fat': 'sum'
        })
        df_trends = df_trends.sort_values('date')

        metrics = ['calories', 'protein', 'carbs', 'fat']
        selected_metrics = st.multiselect(
            "Select metrics to display",
            options=metrics,
            default=metrics
        )
        show_smoothing = st.checkbox("Show 7-day rolling average", value=True)

        # Fixed colors for consistency
        colors = {
            'calories': 'orange',
            'protein': 'blue',
            'carbs': 'green',
            'fat': 'red'
        }

        if selected_metrics:
            df_plot = df_trends.copy()
            if show_smoothing:
                for metric in metrics:
                    df_plot[f"{metric} (7d avg)"] = df_plot[metric].rolling(window=7, min_periods=1).mean()

            fig = go.Figure()

            # Calories on left axis
            for metric in selected_metrics:
                if metric.startswith("calories"):
                    col_name = f"{metric} (7d avg)" if show_smoothing else metric
                    fig.add_trace(go.Scatter(
                        x=df_plot['date'], y=df_plot[col_name],
                        mode='lines+markers',
                        name=col_name,
                        line=dict(color=colors['calories']),
                        yaxis="y1"
                    ))

            # Other macros on right axis
            for metric in selected_metrics:
                if metric != "calories":
                    col_name = f"{metric} (7d avg)" if show_smoothing else metric
                    fig.add_trace(go.Scatter(
                        x=df_plot['date'], y=df_plot[col_name],
                        mode='lines+markers',
                        name=col_name,
                        line=dict(color=colors[metric]),
                        yaxis="y2"
                    ))

            fig.update_layout(
                xaxis=dict(title="Date"),
                yaxis=dict(title="Calories", side="left"),
                yaxis2=dict(title="Protein / Carbs / Fat (g)", overlaying="y", side="right"),
                legend=dict(orientation="h", y=-0.3),
                margin=dict(l=40, r=40, t=40, b=40),
                height=500
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one metric to display.")
    else:
        st.write("No data to display trends.")

    st.markdown("---")

    # --- Food Logging ---
    col_food, col_log = st.columns([2, 1.5])
    with col_food:
        st.subheader("🥑 Food Database")
        search_query = st.text_input("Search for a food item...", key="search_bar")
        filtered_df = food_df[food_df['food_name'].str.contains(search_query, case=False, na=False)] if search_query else food_df
        st.markdown("Click on a food to log it.")

        for _, row in filtered_df.iterrows():
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
                    st.session_state.all_logs.insert(0, new_entry)
                    save_daily_log(st.session_state.all_logs)
                    st.success(f"Logged {amount} {unit} of {food_name}!")
                    st.rerun()

    # --- Daily Log Display ---
    with col_log:
        st.subheader(f"📝 Log for {selected_date_obj.strftime('%B %d, %Y')}")
        if not daily_log:
            st.write("No items logged.")
        else:
            for i, entry in enumerate(daily_log):
                with st.container(border=True):
                    st.markdown(f"**{entry['name']}** ({entry['amount_logged']})")
                    macros_text = (
                        f"🔥 {entry['calories']:.0f} kcal | "
                        f"💪 {entry['protein']:.1f}g P | "
                        f"🍞 {entry['carbs']:.1f}g C | "
                        f"🥑 {entry['fat']:.1f}g F"
                    )
                    st.text(macros_text)
                    if selected_date_obj == datetime.now().date():
                        idx_in_all = st.session_state.all_logs.index(entry)
                        if st.button("Delete", key=f"del_{i}", type="secondary"):
                            st.session_state.all_logs.pop(idx_in_all)
                            save_daily_log(st.session_state.all_logs)
                            st.rerun()

if __name__ == "__main__":
    main()