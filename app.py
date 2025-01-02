import dash
from dash import Dash, html, dcc, Input, Output, State
from dash.dependencies import ALL
from dash.dash_table import DataTable
import pandas as pd
import os
from datetime import datetime, timedelta
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
# Add server start
server = app.server

# File to store records
CSV_FILE = "cat_sitting_records.csv"

# Initialize CSV if it doesn't exist
def initialize_csv():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=["Start Date", "End Date", "Cat Name", "Service Type", "Unit Price", "Days", "Total Amount", "Remarks"])
        df.to_csv(CSV_FILE, index=False)

initialize_csv()

# Load records from CSV
def load_records():
    return pd.read_csv(CSV_FILE)

# Save all records to CSV
def save_all_records(data):
    df = pd.DataFrame(data)
    df.to_csv(CSV_FILE, index=False)

# Helper function to calculate monthly income for cross-month records by service type
def calculate_monthly_income_by_type(df):
    income_data = []

    for _, row in df.iterrows():
        start_date = pd.to_datetime(row["Start Date"])
        end_date = pd.to_datetime(row["End Date"])
        unit_price = row["Unit Price"]
        service_type = row["Service Type"]

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

    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    df = df.dropna(subset=["Start Date", "End Date", "Unit Price", "Service Type"])

    monthly_income = calculate_monthly_income_by_type(df)

    service_types = ["普通寄养", "单间寄养", "上门喂养"]
    fig = go.Figure()

    for service_type in service_types:
        filtered_data = monthly_income[monthly_income["ServiceType"] == service_type]
        fig.add_trace(go.Bar(
            x=filtered_data["YearMonth"],
            y=filtered_data["Income"],
            name=service_type,
            text=filtered_data["Income"],
            textposition="auto",
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
        xaxis=dict(
            tickformat="%Y-%m",  # 使用年份-月份格式
            type="category"      # 确保按照字符串顺序展示
        ),
        title="每月总收入（分服务类别）",
        xaxis_title="月份",
        yaxis_title="总收入 (澳币)",
        barmode="stack",
        template="simple_white",
        margin={"t": 40, "b": 30},
    )
    return fig

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
                    {"name": "开始日期", "id": "Start Date", "editable": True},
                    {"name": "结束日期", "id": "End Date", "editable": True},
                    {"name": "猫咪名字", "id": "Cat Name", "editable": True},
                    {"name": "服务类型", "id": "Service Type", "editable": True},
                    {"name": "单价 (澳币/天)", "id": "Unit Price", "editable": True},
                    {"name": "天数", "id": "Days", "editable": True},
                    {"name": "总金额 (澳币)", "id": "Total Amount", "editable": False},
                    {"name": "备注", "id": "Remarks", "editable": True}
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
                        "if": {"filter_query": "{Service Type} = '普通寄养'"},
                        "backgroundColor": COLORS["普通寄养"],
                        "color": "black"
                    },
                    {
                        "if": {"filter_query": "{Service Type} = '单间寄养'"},
                        "backgroundColor": COLORS["单间寄养"],
                        "color": "black"
                    },
                    {
                        "if": {"filter_query": "{Service Type} = '上门喂养'"},
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

    # Handle adding new record
    if ctx.triggered and ctx.triggered[0]["prop_id"] == "add_record.n_clicks":
        if not (start_date and end_date and cat_name and service_type and unit_price):
            return table_data, generate_monthly_income_chart()

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
        table_data.append(new_record)

    # Handle row deletion
    if data_previous:
        current_df = pd.DataFrame(table_data)
        previous_df = pd.DataFrame(data_previous)
        deleted_rows = pd.concat([previous_df, current_df]).drop_duplicates(keep=False)
        if not deleted_rows.empty:
            df = load_records()
            df = pd.concat([df, deleted_rows]).drop_duplicates(keep=False)
            df.to_csv(CSV_FILE, index=False)

    # Save updated table data to CSV
    save_all_records(table_data)
    return table_data, generate_monthly_income_chart()

if __name__ == "__main__":
    app.run_server(debug=True)
