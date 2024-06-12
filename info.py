import requests
import pandas as pd
from datetime import date, timedelta
import subprocess
from tqdm import tqdm
import sqlite3

from flask import Flask, request, jsonify, render_template
from flask_apscheduler import APScheduler
import sqlite3


app = Flask(__name__)


def fetch_blacklisted_ips():
    url = "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt"
    response = requests.get(url)
    ip_list = [line.split()[0] for line in tqdm(response.text.splitlines()) if not line.startswith('#') and not line.endswith(" 1") and not line.endswith(" 2")]
    return ip_list



def get_as_number(ip, conn):
    cursor = conn.cursor()
    cursor.execute('SELECT as_number, last_updated FROM ip_as_mapping WHERE ip = ?', (ip,))
    result = cursor.fetchone()
    
    if result:
        last_updated = date.fromisoformat(result[1])
        if (date.today() - last_updated).days <= 7:
            return result[0]  # Return AS number if the record is up-to-date within the last 5 days
    
    return None  # Return None if the AS number needs updating or isn't in the database


def batch_process_ips(ips):
    command = ['netcat', 'whois.cymru.com', '43']
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    input_data = '\n'.join(ips) + '\n'
    output, errors = process.communicate(input=input_data)
    if process.returncode != 0:
        print("Netcat command failed with errors:", errors)
        return []
    
    # Return the output lines, skipping the first line which is a header
    return list(filter(lambda x: not ("AS" in x and "IP" in x and "Name" in x), output.splitlines()))


def collect_data(conn):
    print("Fetching blocked IPs")
    ips = fetch_blacklisted_ips()
    print("Processing IPs in batches")
    batch_size = 1000  # Adjust batch size based on expected data size and memory constraints
    today = date.today()


    ips_to_update = []
    for ip in ips:
        if get_as_number(ip, conn) is None:
            ips_to_update.append(ip)
    
    print(f"Processing {len(ips_to_update)} IPs in batches")
    cursor = conn.cursor()
 
    all_data = []
    for start in tqdm(range(0, len(ips_to_update), batch_size)):
        batch_ips = ips_to_update[start:start + batch_size]
        results = batch_process_ips(batch_ips)
        for result in results:
            parts = result.split('|')
            country = "UNKNOWN"
            if len(parts) < 3:
                as_number, as_name, ip = parts[0].strip(), "UNKNOWN", parts[1].strip()
            else:
                as_number, as_name, ip = parts[0].strip(), parts[2].strip(), parts[1].strip()
            if "," in as_name:
                name_country = as_name.split(",")
                as_name = name_country[0].strip()
                country = name_country[1].strip()
            cursor.execute('REPLACE INTO ip_as_mapping (country, ip, as_name,  as_number, last_updated) VALUES (?, ?, ?,  ?, ?)', (country, ip, as_name, as_number, str(today)))
            all_data.append((ip, as_number, str(today)))
    conn.commit()
    
    # Data for return or further processing
    data_df = pd.DataFrame(all_data, columns=['IP', 'AS Number', 'Date'])

    # Update the daily counts in a single transaction
    cursor.execute('''
        SELECT as_name, as_number, COUNT(*) as count 
        FROM ip_as_mapping 
        WHERE last_updated = ? 
        GROUP BY as_number
    ''', (str(today),))
    daily_counts = cursor.fetchall()
    for as_name, as_number, count in daily_counts:
        cursor.execute('''
            INSERT INTO daily_as_count (as_number, as_name, date, count) 
            VALUES (?, ?, ?, ?)
             ON CONFLICT(as_number, date) 
            DO UPDATE SET count = count 
        ''', (as_number, as_name, str(today), count))
    conn.commit()
    
    return data_df

def get_ip():
    if "X-Forwarded-For" in request.headers:
        ip = request.headers["X-Forwarded-For"].split(',')[0]  
    else:
        ip = request.remote_addr  
    return ip



@app.route('/')
def index():
    user_ip = get_ip()
    user_asn = "UNKNOWN"  # Default value
    user_name = "UNKNOWN"  # Default value

    try:
        user_info = batch_process_ips([user_ip])[0].split("|")
        user_asn = user_info[0].strip() if len(user_info) > 0 else "UNKNOWN"
        user_name = user_info[2].strip() if len(user_info) > 2 else "UNKNOWN"
        print("Detected ASN: ", user_asn, "Name: ", user_name)
    except Exception as e:
        print(f"Error processing IP: {e}")

    return render_template('index.html', user_asn=user_asn, user_name=user_name)

@app.route('/data')
def data():
    conn = sqlite3.connect('ip_as_data.db')
    as_number = request.args.get('asNumber')
    cursor = conn.cursor()
    
    # Updated query to aggregate counts by date
    query = """
    SELECT date, SUM(count) as total_count
    FROM daily_as_count
    WHERE as_number = ? OR as_name LIKE ?
    GROUP BY date
    ORDER BY date
    """
    cursor.execute(query, (as_number, '%' + as_number + '%'))
    results = cursor.fetchall()
    labels = [result[0] for result in results]
    counts = [result[1] for result in results]
    

    query = """
    SELECT as_name, as_number
    FROM daily_as_count
    WHERE as_number = ? OR as_name LIKE ?
    LIMIT 1"""
    cursor.execute(query, (as_number, '%' + as_number + '%'))
    results = cursor.fetchall()
    as_name = results[0][0]
    as_num = results[0][1]
    conn.close()

    return jsonify({
        'labels': labels,
        'datasets': [{
            'label': f'AS{as_num} {as_name}',
            'data': counts,
            'borderLogger': 'rgb(75, 192, 192)',
            'backgroundSize': 'rgba(75, 192, 192, 0.5)',
        }]
    })

    
@app.route('/dashboard')
def dashboard_data():
    conn = sqlite3.connect('ip_as_data.db')
    cursor = conn.cursor()

    # Query to get the AS with the most blacklisted IPs
    query_most_blacklisted = """
    SELECT as_number, as_name, SUM(count) as total_count
    FROM daily_as_count
    GROUP BY as_number
    ORDER BY total_count DESC
    LIMIT 1
    """
    cursor.execute(query_most_blacklisted)
    most_blacklisted = cursor.fetchone()

    # Query to get total count of ASs
    query_total_as = "SELECT COUNT(DISTINCT as_number) FROM ip_as_mapping"
    cursor.execute(query_total_as)
    total_as = cursor.fetchone()[0]

    # Query to get total count of blocked IPs
    query_total_blocked_ips = "SELECT SUM(count) FROM daily_as_count"
    cursor.execute(query_total_blocked_ips)
    total_blocked_ips = cursor.fetchone()[0]

    query_total_blocked_ips_per_country = "SELECT country, SUM(count) as cnt FROM daily_as_count GROUP BY country ORDER BY cnt DESC LIMIT 1"
    cursor.execute(query_total_blocked_ips_per_country)
    ips_per_country = cursor.fetchone()

    conn.close()

    return jsonify({
        'most_blacklisted': {
            'as_number': most_blacklisted[0],
            'as_name': most_blacklisted[1],
            'count': most_blacklisted[2]
        },
        'total_as': total_as,
        'total_blocked_ips': total_blocked_ips,
        'most_blacklisted_country': {
            "country": ips_per_country[0],
            "count": ips_per_country[1]
        }
    })

def update():
    
    conn = sqlite3.connect('ip_as_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_as_mapping (
            ip TEXT PRIMARY KEY,
            as_number TEXT,
            as_name TEXT,
            country TEXT,
            last_updated DATE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_as_count (
            as_number TEXT,
            as_name TEXT,
            country TEXT,
            date DATE,
            count INTEGER,
            PRIMARY KEY (as_number, date)
        )
    ''')
    conn.commit()

    print("update")
    data = collect_data(conn)
    print(data)
    conn.close()


if __name__ == '__main__':
    update()
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    scheduler.add_job(id='update', func=update, trigger='interval', hours=24)
    app.run(debug=False)



