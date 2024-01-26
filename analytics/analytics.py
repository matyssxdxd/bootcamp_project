import requests
import pandas as pd
from datetime import datetime
from statsmodels.tsa.arima.model import ARIMA
import matplotlib.pyplot as plt

# Function to fetch data from API for a specific country
def fetch_covid_data(country):
    url = f"http://localhost:5000/api/covid-cases?country={country}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to fetch data")
        return None

# Function to convert fetched data into a DataFrame
def json_to_dataframe(data):
    df = pd.DataFrame(data)
    df['DATE'] = pd.to_datetime(df['DATE'])
    df.set_index('DATE', inplace=True)
    return df

# Function to forecast using ARIMA model
def arima_forecast(data, steps):
    model = ARIMA(data, order=(5,1,0))
    model_fit = model.fit()

    forecast = model_fit.forecast(steps=steps)

    return forecast

country = "Latvia" # Can be changed to any country
covid_data = fetch_covid_data(country)
if covid_data:
    df = json_to_dataframe(covid_data)
    cases_series = df['CASES']

    # Perform ARIMA forecasting for 60 days into the future
    forecast = arima_forecast(cases_series, steps=60)

    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['CASES'], label='Actual Cases')
    plt.plot(pd.date_range(start=df.index[-1], periods=len(forecast)), forecast, label='Forecasted Cases')
    plt.xlabel('Date')
    plt.ylabel('Cases')
    plt.title(f'COVID-19 Forecast for {country}')
    plt.legend()
    plt.grid(True)
    plt.show()
