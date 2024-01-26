from flask import Flask, request, abort, jsonify, make_response
import datetime
import re
from flask_caching import Cache

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import snowflake.connector
from snowflake.connector import DictCursor
from config import creds

# Connection to snowflake, got this from their Flask API tutorial.
def connect() -> snowflake.connector.SnowflakeConnection:
    if 'private_key' in creds:
        if not isinstance(creds['private_key'], bytes):
            p_key = serialization.load_pem_private_key(
                    creds['private_key'].encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
            pkb = p_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption())
            creds['private_key'] = pkb
    return snowflake.connector.connect(**creds)

def validate_date_format(date_str):
    try:
        # Attempt to parse the date to see if it is correct.
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False
    
def validate_date_range(str_date, end_date):
    # Check if the date is between 2019-12-31 and 2020-12-14, because there is no data outside of this range.
    return '2019-12-31' <= str_date <= '2020-12-14' and '2019-12-31' <= end_date <= '2020-12-14'

def validate_country_name(country):
    # Allow alphanumeric characters, white spaces, and certain special characters in country names.
    return bool(re.match(r'^[a-zA-Z0-9\s\.,\'-]+$', country))

def validate_year(year):
    try:
        year_int = int(year)
        return 1750 <= year_int <= 2021
    except ValueError:
        return False


conn = connect()

app = Flask(__name__)

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/')
def home():
    return make_response(jsonify(result='Nothing here!'))


# Covid data

@app.route('/api/covid-cases')
def get_cases():
    try:
        country = request.args.get('country')
        deaths_param = request.args.get('deaths')
        str_date = request.args.get('str_date')
        end_date = request.args.get('end_date')
        sum_cases = request.args.get('sum_cases')

        # Validate deaths_param
        if deaths_param is not None and deaths_param not in {'0', '1'}:
            abort(400, "Invalid value for deaths parameter. It should be 0 (false) or 1 (true).")

        if sum_cases is not None and sum_cases not in {'0', '1'}:
            abort(400, "Invalid value for deaths parameter. It should be 0 (false) or 1 (true).")

        # Validate date format
        if str_date and not validate_date_format(str_date):
            abort(400, "Invalid date format for str_date. It should be in 'YYYY-MM-DD' format.")
        if end_date and not validate_date_format(end_date):
            abort(400, "Invalid date format for end_date. It should be in 'YYYY-MM-DD' format.")

        # Validate country name
        if country and not validate_country_name(country):
            abort(400, "Invalid country name. It should consist only of letters.")

        if sum_cases == '1':
        # Base SQL query
            base_sql = 'SELECT COUNTRY_REGION as Country, SUM(CASES) as Cases'
        elif sum_cases == '0' or sum_cases is None:
            base_sql = 'SELECT COUNTRY_REGION as Country, DATE as Date, CASES as Cases'

        if deaths_param:
            if sum_cases == '1':
                base_sql += ', SUM(DEATHS) as Deaths'
            elif sum_cases == '0' or sum_cases is None:
                base_sql += ', DEATHS as Deaths'

        # Add the data table to the basesql and create a where_clause array.
        base_sql += ' FROM COVID19_EPIDEMIOLOGICAL_DATA.PUBLIC.ECDC_GLOBAL'
        where_clause = []

        # Build the WHERE clause based on parameters.
        if country:
            # Use LIKE to match similar country names, even with white spaces or special characters.
            where_clause.append(f'COUNTRY_REGION LIKE \'%{country}%\'')
        if str_date and end_date:
            # Check if the date range is valid before adding it to the WHERE clause.
            if not validate_date_range(str_date, end_date):
                abort(400, "Invalid date range for str_date or end_date. They should be between 2019-12-31 and 2020-12-14.")
            where_clause.append(f'DATE BETWEEN \'{str_date}\' AND \'{end_date}\'')
        elif str_date or end_date:
            # If only one of str_date or end_date is provided, it's invalid.
            abort(400, "Both str_date and end_date are required for date range query.")
        if deaths_param:
            where_clause.append('DEATHS IS NOT NULL')  # To filter out rows where deaths are not available.

        # Combine the base SQL with the WHERE clause.
        if where_clause:
            if sum_cases == '1':
                sql = f'{base_sql} WHERE {" AND ".join(where_clause)} GROUP BY COUNTRY_REGION'
            elif sum_cases == '0' or sum_cases is None:
                sql = f'{base_sql} WHERE {" AND ".join(where_clause)} ORDER BY DATE ASC'
        else:
            if sum_cases == '1':
                sql = f'{base_sql} GROUP BY COUNTRY_REGION'
            elif sum_cases == '0' or sum_cases is None:
                sql = f'{base_sql} ORDER BY DATE ASC'

        # Check if the request URL matches the specific criteria for caching
        cache_time = 300  # Cache for 5 minutes
        cache_key = request.full_path  # Default cache key
        if request.path == '/api/covid-cases' and (request.args.get('deaths') == '1' or request.args.get('sum_cases') == '1'):
            cache_key = request.full_path  # Include query parameters in the cache key
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response

        # Execute SQL query and fetch results
        cursor = conn.cursor(DictCursor)
        cursor.execute(sql)
        results = cursor.fetchall()

        # Create response
        response = make_response(jsonify(results), 200)

        # Cache the response
        cache.set(cache_key, response, timeout=cache_time)  # Cache for 5 minutes

        return response
    except snowflake.connector.errors.ProgrammingError as e:
        abort(500, e)
    except Exception as e:
        abort(500, e)



# Emissions by country data

@app.route('/api/emissions-by-country')
def get_emissions():
    try:
        country = request.args.get('country')
        year = request.args.get('year')

        # Validate country name
        if country and not validate_country_name(country):
            abort(400, "Invalid country name. It should consist only of letters.")

        # Validate year
        if year and not validate_year(year):
            abort(400, "Invalid year. It should be between 1750 and 2021.")

        base_sql = "SELECT Country, Total, Year FROM KAGGLEDATASET.PUBLIC.EMISSIONS_BY_COUNTRY"
        where_clause = []

        if country:
            where_clause.append(f'COUNTRY LIKE \'%{country}%\'')

        if year:
            where_clause.append(f'YEAR = {year}')

        if where_clause:
            sql = f'{base_sql} WHERE {" AND ".join(where_clause)}'

        # Check if the request URL matches the specific criteria for caching
        cache_time = 300  # Cache for 5 minutes
        cache_key = request.full_path  # Default cache key
        if request.path == '/api/emissions-by-country' and request.args.get('year') in ['2019', '2020', '2021']:
            cache_key = request.full_path  # Include query parameters in the cache key
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response

        cursor = conn.cursor(DictCursor)
        cursor.execute(sql)
        results = cursor.fetchall()

        response = make_response(jsonify(results), 200)

        # Cache the response
        cache.set(cache_key, response, timeout=cache_time)  # Cache for 5 minutes

        return response
    except snowflake.connector.errors.ProgrammingError as e:
        abort(500, e)
    except Exception as e:
        abort(500, e)