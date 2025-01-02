import dash
from dash import Dash, html, dcc, Input, Output, State
from dash.dependencies import ALL
from dash.dash_table import DataTable
import pandas as pd
from datetime import datetime, timedelta
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import psycopg2
from psycopg2.extras import RealDictCursor

# PostgreSQL connection setup
DB_CONFIG = {
    'dbname': 'algdcatsitterdb',
    'user': 'algdcatsitter',
    'password': 'rxehxlXDLxwMTvN7mIUS6yyMZNfZPMpB',
    'host': 'dpg-ctr27n9opnds73fo25ag-a.singapore-postgres.render.com',
    'port': 5432
}

# Initialize PostgreSQL table
def initialize_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cat_sitting_records (
            id SERIAL PRIMARY KEY,
            start_date DATE,
            end_date DATE,
            cat_name TEXT,
            service_type TEXT,
            unit_price NUMERIC,
            days INTEGER,
            total_amount NUMERIC,
            remarks TEXT
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()

initialize_db()

# Load records from PostgreSQL
def load_records():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM cat_sitting_records ORDER BY id;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame(rows)

# Save a new record to PostgreSQL
def save_record(record):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO cat_sitting_records (start_date, end_date, cat_name, service_type, unit_price, days, total_amount, remarks)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (record['Start Date'], record['End Date'], record['Cat Name'], record['Service Type'],
          record['Unit Price'], record['Days'], record['Total Amount'], record['Remarks']))
    conn.commit()
    cur.close()
    conn.close()

# Delete a record from PostgreSQL
def delete_record(record_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute('DELETE FROM cat_sitting_records WHERE id = %s;', (record_id,))
    conn.commit()
    cur.close()
    conn.close()

# Helper function to calculate monthly income for cross-month records by service type
def calculate_monthly_income_by_type(df):
    income_data = []

    for _, row in df.iterrows():
        start_date = pd.to_datetime(row["start_date"])
        end_date = pd.to_datetime(row["end_date"])
        unit_price = row["unit_price"]
        service_type = row["service_type"]

        current_date = start_date
        while current_date <= end_date:
            next_month = (current_date + pd.offsets.MonthEnd(0) + timedelta(days=1)).replace(day=1)
            month_end = min(next_month - timedelta(days=1), end_date)
            days_in_month = (month_end - current_date).days + 1

            income_data.append({
                "YearMonth": current_date.strftime("%Y-%m"),
                "ServiceType": service_type,
                "Income": days_in_month * unit_price
            })

            current_date = month_end + timedelta(days=1)

    income_df = pd.DataFrame(income_data)
    return income_df.groupby(["YearMonth", "ServiceType"])["Income"].sum().reset_index()

# Generate monthly income bar chart with stacked bars
COLORS = {
    "普通寄养": "#d6e9f2",
    "单间寄养": "#f2e6d6",
    "上门喂养": "#e6f2d6"
}

def generate_monthly_income_chart():
    df = load_records()
    if df.empty:
        return go.Figure()

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    df = df.dropna(subset=["start_date", "end_date", "unit_price", "service_type"])

    monthly_income = calculate_monthly_income_by_type(df)

    service_types = ["普通寄养", "单间寄养", "上门喂养"]
    fig = go.Figure()

    for service_type in service_types:
        filtered_data = monthly_income[monthly_income["ServiceType"] == service_type]
        fig.add_trace(go.Bar(
            x=filtered_data["YearMonth"],
            y=filtered_data["Income"],
            name=service_type,
            marker_color=COLORS[service_type]
        ))

    # Add total income on top of the stacked bars
    total_income = monthly_income.groupby("YearMonth")["Income"].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=total_income["YearMonth"],
        y=total_income["Income"],
        mode="text",
        text=total_income["Income"],
        textposition="top center",
        showlegend=False
    ))

    fig.update_layout(
        title="每月总收入（分服务类别）",
        xaxis_title="月份",
        yaxis_title="总收入 (澳币)",
        barmode="stack",
        template="simple_white",
        margin={"t": 40, "b": 30},
    )
    return fig

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
# Add server start 
server = app.server
app.title = "阿里嘎多猫咪寄养"

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("猫咪寄养记账软件", className="text-center mb-4"), width=12)
    ]),

    dbc.Row([
        dbc.Col([
            dcc.Graph(id="monthly_income_chart", config={"displayModeBar": False}, figure=generate_monthly_income_chart())
        ], width=12)
    ], className="mb-3"),

    dbc.Row([
        dbc.Col([
            dbc.Label("开始日期", className="mt-2"),
            dcc.DatePickerSingle(id="start_date", placeholder="选择开始日期", className="mb-2"),

            dbc.Label("结束日期", className="mt-2"),
            dcc.DatePickerSingle(id="end_date", placeholder="选择结束日期", className="mb-2"),

            dbc.Label("猫咪名字", className="mt-2"),
            dbc.Input(id="cat_name", type="text", placeholder="请输入猫咪名字", className="mb-2"),

            dbc.Label("服务类型", className="mt-2"),
            dcc.Dropdown(
                id="service_type",
                options=[
                    {"label": "普通寄养", "value": "普通寄养"},
                    {"label": "单间寄养", "value": "单间寄养"},
                    {"label": "上门喂养", "value": "上门喂养"}
                ],
                placeholder="请选择服务类型",
                className="mb-2"
            ),

            dbc.Label("单价 (澳币/天)", className="mt-2"),
            dbc.Input(id="unit_price", type="number", placeholder="请输入单价", className="mb-2"),

            dbc.Label("天数", className="mt-2"),
            dbc.Input(id="days", type="number", placeholder="请输入天数", className="mb-2", disabled=True),

            dbc.Label("备注", className="mt-2"),
            dbc.Input(id="remarks", type="text", placeholder="请输入备注", className="mb-3"),

            dbc.Button("添加记录", id="add_record", color="primary", className="mb-4 w-100", n_clicks=0)
        ], width=12),
    ], className="mb-3"),

    dbc.Row([
        dbc.Col([
            DataTable(
                id="records_table",
                columns=[
                    {"name": "开始日期", "id": "start_date", "editable": True},
                    {"name": "结束日期", "id": "end_date", "editable": True},
                    {"name": "猫咪名字", "id": "cat_name", "editable": True},
                    {"name": "服务类型", "id": "service_type", "editable": True},
                    {"name": "单价 (澳币/天)", "id": "unit_price", "editable": True},
                    {"name": "天数", "id": "days", "editable": True},
                    {"name": "总金额 (澳币)", "id": "total_amount", "editable": False},
                    {"name": "备注", "id": "remarks", "editable": True}
                ],
                data=load_records().to_dict("records"),
                editable=True,
                row_deletable=True,
                sort_action="native",
                filter_action="native",
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "fontSize": "14px", "padding": "10px"},
                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{service_type} = '普通寄养'"},
                        "backgroundColor": COLORS["普通寄养"],
                        "color": "black"
                    },
                    {
                        "if": {"filter_query": "{service_type} = '单间寄养'"},
                        "backgroundColor": COLORS["单间寄养"],
                        "color": "black"
                    },
                    {
                        "if": {"filter_query": "{service_type} = '上门喂养'"},
                        "backgroundColor": COLORS["上门喂养"],
                        "color": "black"
                    }
                ]
            )
        ], width=12)
    ])
], fluid=True)

@app.callback(
    [Output("days", "disabled"),
     Output("days", "value")],
    [Input("service_type", "value"),
     Input("start_date", "date"),
     Input("end_date", "date")]
)
def toggle_days_input(service_type, start_date, end_date):
    if service_type in ["普通寄养", "单间寄养"]:
        if start_date and end_date:
            days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1
            return True, days
        return True, None
    elif service_type == "上门喂养":
        return False, None
    return True, None

@app.callback(
    [Output("records_table", "data"),
     Output("monthly_income_chart", "figure")],
    [Input("add_record", "n_clicks"), Input("records_table", "data_previous")],
    [State("records_table", "data"),
     State("start_date", "date"),
     State("end_date", "date"),
     State("cat_name", "value"),
     State("service_type", "value"),
     State("unit_price", "value"),
     State("days", "value")],
    prevent_initial_call=True
)
def update_table_and_chart(n_clicks, data_previous, table_data, start_date, end_date, cat_name, service_type, unit_price, days):
    ctx = dash.callback_context

    # Add loading spinner
    from dash import no_update
    from dash.exceptions import PreventUpdate

    if ctx.triggered and ctx.triggered[0]["prop_id"] == "add_record.n_clicks":
        if not (start_date and end_date and cat_name and service_type and unit_price):
            raise PreventUpdate

        total_amount = float(unit_price) * int(days)
        new_record = {
            "Start Date": start_date,
            "End Date": end_date,
            "Cat Name": cat_name,
            "Service Type": service_type,
            "Unit Price": float(unit_price),
            "Days": int(days),
            "Total Amount": total_amount,
            "Remarks": ""
        }
        save_record(new_record)
        table_data.append(new_record)

    if data_previous:
        current_df = pd.DataFrame(table_data)
        previous_df = pd.DataFrame(data_previous)
        deleted_rows = pd.concat([previous_df, current_df]).drop_duplicates(keep=False)
        for _, row in deleted_rows.iterrows():
            delete_record(row["id"])

    updated_data = load_records().to_dict("records")
    return updated_data, generate_monthly_income_chart()

if __name__ == "__main__":
    app.run_server(debug=True)
