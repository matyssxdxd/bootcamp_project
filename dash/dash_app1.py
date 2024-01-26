import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import requests
import plotly.express as px
from pymongo import MongoClient
from datetime import datetime

# Function to fetch data from the API
def fetch_data():
    url = "http://localhost:5000/api/covid-cases?deaths=1"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses
        data_json = response.json()
        df = pd.DataFrame(data_json)
        return df
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

# Function to fetch comments from MongoDB
def fetch_comments():
    client = MongoClient('mongodb://localhost:27017/')
    db = client['comments']
    comments_collection = db['covid_comments']
    comments = {}
    for doc in comments_collection.find():
        country = doc['country']
        comment_info = {
            'username': doc['username'],
            'comment': doc['comment'],
            'date': doc['date'].strftime('%Y-%m-%d %H:%M:%S')
        }
        if country not in comments:
            comments[country] = []
        comments[country].append(comment_info)
    return comments

# Function to store comments in MongoDB
def store_comment(username, country, comment):
    client = MongoClient('mongodb://localhost:27017/')
    db = client['comments']
    comments_collection = db['covid_comments']
    current_date = datetime.now()
    comments_collection.insert_one({
        'username': username,
        'country': country,
        'comment': comment,
        'date': current_date
    })

app = dash.Dash(__name__)

df = fetch_data()
comments = fetch_comments()

# Create a list of unique countries for the dropdown menu
countries = df['COUNTRY'].unique()

app.layout = html.Div([
    dcc.Dropdown(
        id='country-dropdown',
        options=[{'label': country, 'value': country} for country in countries],
        value=countries[0],
        style={'width': '50%'}
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
    html.Div(id='comments-output'),
    dcc.Graph(id='cases-graph'),
])

# Define callback to update the graph and comments based on user input
@app.callback(
    [Output('cases-graph', 'figure'),
     Output('comments-output', 'children'),
     Output('username-input', 'value'),
     Output('comment-input', 'value')],
    [Input('country-dropdown', 'value'),
     Input('add-comment-button', 'n_clicks')],
    [State('username-input', 'value'),
     State('comment-input', 'value')]
)
def update_graph_and_comments(selected_country, n_clicks, username, comment):
    if df is None:
        return px.line(title='Error fetching data from API'), None, username, comment

    # Filter the data based on the selected country
    filtered_df = df[df['COUNTRY'] == selected_country]

    # Check if a new comment is submitted
    if n_clicks > 0 and comment:
        store_comment(username, selected_country, comment)

    # Fetch updated comments for the selected country
    country_comments = fetch_comments().get(selected_country, [])

    # Create a line chart using Plotly
    fig = px.line(filtered_df, x='DATE', y=['CASES', 'DEATHS'], title=f'Cases and Deaths in {selected_country}')

    # Display comments for the selected country
    comments_output = html.Ul([html.Li(f"{info['username']} ({info['date']}): {info['comment']}") for info in country_comments])

    return fig, comments_output, '', ''  # Clear input fields after submission

if __name__ == '__main__':
    app.run_server(debug=True, port="8080")
