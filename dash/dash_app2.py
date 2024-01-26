import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import requests
from pymongo import MongoClient
from datetime import datetime

# Function to fetch COVID-19 data
def fetch_covid_data():
    url = "http://localhost:5000/api/covid-cases?sum_cases=1"
    response = requests.get(url)
    data = response.json()
    df_covid = pd.DataFrame(data)
    return df_covid

# Function to fetch emissions data for a given year
def fetch_emissions_data(year):
    url = f"http://localhost:5000/api/emissions-by-country?year={year}"
    response = requests.get(url)
    data = response.json()
    df_emissions = pd.DataFrame(data)
    return df_emissions

# Function to fetch comments from MongoDB
def fetch_comments():
    client = MongoClient('mongodb://localhost:27017/')
    db = client['comments']
    comments_collection = db['year_comments']
    comments = {}
    for doc in comments_collection.find():
        year = doc['year']
        comment_info = {
            'username': doc['username'],
            'comment': doc['comment'],
            'date': doc['date'].strftime('%Y-%m-%d %H:%M:%S')
        }
        if year not in comments:
            comments[year] = []
        comments[year].append(comment_info)
    return comments

# Function to store comments in MongoDB
def store_comment(username, year, comment):
    client = MongoClient('mongodb://localhost:27017/')
    db = client['comments']
    comments_collection = db['year_comments']
    current_date = datetime.now()
    comments_collection.insert_one({
        'username': username,
        'year': year,
        'comment': comment,
        'date': current_date
    })


# Fetch COVID-19 data
df_covid = fetch_covid_data()

# Fetch emissions data for each year
df_emissions_2019 = fetch_emissions_data(2019)
df_emissions_2020 = fetch_emissions_data(2020)
df_emissions_2021 = fetch_emissions_data(2021)

# Merge COVID-19 and emissions data
df_merged_2019 = pd.merge(df_covid, df_emissions_2019, on='COUNTRY', how='inner')
df_merged_2020 = pd.merge(df_covid, df_emissions_2020, on='COUNTRY', how='inner')
df_merged_2021 = pd.merge(df_covid, df_emissions_2021, on='COUNTRY', how='inner')

# Combine all merged data
df_all = pd.concat([df_merged_2019, df_merged_2020, df_merged_2021])

# Initialize Dash app
app = dash.Dash(__name__)

comments = fetch_comments()

# Define layout
app.layout = html.Div([
    html.H1("COVID-19 Cases vs Total Emissions by Country"),
    dcc.Graph(id='scatter-plot'),
    dcc.Dropdown(
        id='year-dropdown',
        options=[
            {'label': '2019', 'value': 2019},
            {'label': '2020', 'value': 2020},
            {'label': '2021', 'value': 2021}
        ],
        value=2019
    ),
    dcc.Input(
        id='username-input',
        type='text',
        placeholder='Enter your username...',
        style={'width': '50%'}
    ),
    dcc.Textarea(
        id='comment-input',
        placeholder='Enter your comment...',
        style={'width': '50%'}
    ),
    html.Button('Add Comment', id='add-comment-button', n_clicks=0),
    html.Div(id='comments-output')
])

# Define callback to update scatter plot based on selected year
@app.callback(
    [Output('scatter-plot', 'figure'),
     Output('comments-output', 'children'),
     Output('username-input', 'value'),
     Output('comment-input', 'value')],
    [Input('year-dropdown', 'value'),
     Input('add-comment-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('comment-input', 'value')]
)
def update_scatter_plot(selected_year, n_clicks, username, comment):

    trace = go.Scatter(
        x=df_all[df_all['YEAR'] == selected_year]['TOTAL'],
        y=df_all[df_all['YEAR'] == selected_year]['CASES'],
        mode='markers',
        name=str(selected_year),
        text=df_all[df_all['YEAR'] == selected_year]['COUNTRY']
    )

    layout = go.Layout(
        title='COVID-19 Cases vs Total Emissions by Country',
        xaxis=dict(title='Total Emissions'),
        yaxis=dict(title='COVID-19 Cases'),
        hovermode='closest'
    )

    fig = go.Figure(data=[trace], layout=layout)

    if n_clicks > 0 and comment:
        store_comment(username, selected_year, comment)

    year_comments = fetch_comments().get(selected_year, [])

    comments_output = html.Ul([html.Li(f"{info['username']} ({info['date']}): {info['comment']}") for info in year_comments])
    
    return fig, comments_output, '', ''

if __name__ == '__main__':
    app.run_server(debug=True, port="8080")
