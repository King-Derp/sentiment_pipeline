import pandas as pd
import sys
from datetime import timedelta

# Load the data
print("Loading data...")
df = pd.read_csv('data/reddit_finance.csv')
print(f"Total records: {len(df)}")

# Convert timestamps to datetime
df['created_utc'] = pd.to_datetime(df['created_utc'], unit='s')
df = df.sort_values('created_utc')

# Print date range
print(f"Date range: {df.created_utc.min()} to {df.created_utc.max()}")

# Calculate time differences
df['time_diff'] = df['created_utc'].diff().dt.total_seconds()

# Check for gaps larger than 10 minutes
gap_threshold = 600  # 10 minutes in seconds
gaps = df[df['time_diff'] > gap_threshold]
print(f"\nFound {len(gaps)} gaps > 10 minutes out of {len(df)} records")

# Show largest gaps
print("\nTop 10 largest gaps:")
largest_gaps = gaps.sort_values('time_diff', ascending=False).head(10)
for i, row in largest_gaps.iterrows():
    gap_hours = row['time_diff'] / 3600
    print(f"Gap of {gap_hours:.1f} hours between {row['created_utc']} ({row['subreddit']}) and previous record")

# Check recent data (last 24 hours)
last_day = df[df['created_utc'] > (df['created_utc'].max() - timedelta(days=1))]
print(f"\nRecords in last 24 hours: {len(last_day)}")

# Check for gaps in last 24 hours
recent_gaps = last_day[last_day['time_diff'] > gap_threshold]
print(f"Gaps > 10 minutes in last 24 hours: {len(recent_gaps)}")

if len(recent_gaps) > 0:
    print("\nRecent gaps:")
    for i, row in recent_gaps.sort_values('time_diff', ascending=False).head(5).iterrows():
        gap_minutes = row['time_diff'] / 60
        print(f"Gap of {gap_minutes:.1f} minutes at {row['created_utc']} ({row['subreddit']})")

# Check most recent data collection pattern
print("\nMost recent 5 records:")
for i, row in df.sort_values('created_utc', ascending=False).head(5).iterrows():
    print(f"{row['created_utc']} - {row['subreddit']} - {row['title'][:50]}...")
