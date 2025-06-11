# Coin Peak Detector

The Coin Peak Detector is a Python-based application designed to analyze YouTube channel view counts, specifically focusing on channels related to cryptocurrency. It aims to identify sudden surges in video views within a short period (1-3 days) as a potential indicator of heightened interest or market activity, which some might interpret as a "peak" or anomaly.

## Features

- **YouTube Data Collection:** Fetches recent video data (views, publish dates) from specified YouTube channels using the YouTube Data API v3.
- **Categorization:** Allows differentiation between Korean and international YouTube channels.
- **Surge Analysis:** Compares view counts of very recent videos (last 1-3 days) against a baseline average of slightly older videos (e.g., last 4-10 days) from the same channel.
- **Configurable Thresholds:** Surge detection parameters (e.g., percentage increase, time windows for "recent" and "baseline") are configurable.
- **Console Alerts:** Reports detected surges with relevant video details directly to the console.
- **Data Persistence:** Saves fetched raw data to JSON files for potential later analysis or debugging.

## How It Works

1.  **Configuration:** The application reads settings from `config/config.yaml`. This includes the YouTube API key, lists of Korean and international channels (by their Channel IDs), and analysis parameters.
2.  **Data Collection (`src/youtube_collector.py`):** It connects to the YouTube API and fetches recent video statistics for each configured channel.
3.  **Data Storage (`src/main.py`):** The collected raw data is saved as a timestamped JSON file in the `data/` directory.
4.  **Analysis (`src/analysis_engine.py`):**
    *   For each channel, videos are categorized as "recent" or "baseline" based on their publication date and the configured time windows.
    *   An average view count is calculated for the "baseline" videos.
    *   Each "recent" video's view count is compared to this baseline average.
    *   If a recent video's views exceed the baseline average by a specified percentage, it's flagged as a "surge."
5.  **Alerting (`src/alerter.py`):** Details of any videos flagged as surges are printed to the console, including the channel name, video title, view count, percentage increase, and a direct link to the video.

## Setup Instructions

### 1. Prerequisites
    - Python 3.7+
    - `pip` (Python package installer)

### 2. Clone the Repository
    ```bash
    git clone <your_repository_url_here> # Replace with your actual repository URL
    cd coin-peak-detector # Or your repository's directory name
    ```

### 3. Create a Virtual Environment (Recommended)
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

### 4. Install Dependencies
    ```bash
    pip install -r requirements.txt
    ```

### 5. Obtain and Configure YouTube Data API v3 Key

    **This is a critical step.** The application will not work without a valid API key.

    a.  **Go to the Google Cloud Console:** [https://console.cloud.google.com/](https://console.cloud.google.com/)
    b.  **Create a new project** (or select an existing one).
    c.  **Enable the "YouTube Data API v3":**
        - In the navigation menu, go to "APIs & Services" -> "Library".
        - Search for "YouTube Data API v3" and enable it for your project.
    d.  **Create API Key Credentials:**
        - Go to "APIs & Services" -> "Credentials".
        - Click "+ CREATE CREDENTIALS" -> "API key".
        - Your API key will be generated. **Copy this key immediately.**
        - It's highly recommended to restrict your API key to only be usable by the "YouTube Data API v3". You can do this by clicking on the newly created key in the console and setting API restrictions. You might also consider IP address restrictions if you have a static IP for running this script.
    e.  **Update `config/config.yaml`:**
        Open the `config/config.yaml` file in the project.
        Replace `"YOUR_API_KEY_HERE"` with the API key you just obtained:
        ```yaml
        youtube_api_key: "AIzaSyYOURACTUALAPIKEYHERE..."
        ```
    f.  **API Quotas:** The YouTube Data API has daily quotas. Default quota is usually 10,000 units per day. Fetching video data consumes quota (typically 1 unit for listing videos, plus more for channel details). If you monitor many channels frequently, you might hit this limit. You can monitor your quota usage in the Google Cloud Console.

### 6. Configure Channels
    a.  **Identify Target Channels:** Decide which Korean and international cryptocurrency-focused YouTube channels you want to monitor.
    b.  **Find their Channel IDs:**
        - Visit the channel's YouTube page.
        - The Channel ID is usually part of the URL (e.g., `https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxx` - the `UC...` string is the ID).
        - If the channel uses a custom URL (e.g., `/ @username`), you might need to view the page source and search for `"channelId"` or use an online tool to find the ID from the custom URL.
    c.  **Update `config/config.yaml`:**
        Edit the `channels` section in `config/config.yaml`. Replace the placeholder entries with your actual channel IDs and descriptive names.
        Example:
        ```yaml
        channels:
          korean:
            - id: "UC1ExampleKoreanChannelID"
              name: "Real Korean Crypto Channel"
            # Add more Korean channels
          international:
            - id: "UC2ExampleIntlChannelID"
              name: "Real International Crypto Channel"
            # Add more international channels
        ```

### 7. Configure Analysis Settings (Optional)
    Review and adjust the `analysis_settings` in `config/config.yaml` if needed:
    ```yaml
    analysis_settings:
      surge_threshold_percentage: 75  # Alert if views are 75% above baseline
      recent_days_for_surge: 3      # Videos from the last 3 days are "recent"
      baseline_days: 7              # Baseline uses videos from 4 to 10 days ago (recent_days + baseline_days)
    ```

## Usage

Once setup is complete, run the main script from the project's root directory:

```bash
python src/main.py
```

The script will:
1.  Fetch data for the configured channels.
2.  Save the data to the `data/` directory.
3.  Analyze the data for view surges.
4.  Print any detected surge alerts to the console.

## Project Structure

```
.
├── config/
│   └── config.yaml         # Configuration file (API key, channels, analysis settings)
├── data/                   # Directory where fetched YouTube data is stored (created automatically)
├── src/
│   ├── __init__.py
│   ├── youtube_collector.py # Module for fetching data from YouTube API
│   ├── analysis_engine.py  # Module for analyzing view data to find surges
│   ├── alerter.py          # Module for reporting detected surges
│   └── main.py             # Main orchestration script
├── .gitignore              # Specifies intentionally untracked files
├── README.md               # This file
└── requirements.txt        # Python dependencies
```

## Future Enhancements (Ideas)

- **Web Interface:** Develop a web service (e.g., using Flask/Django) to display results and manage settings.
- **Database Storage:** Use a proper database (e.g., SQLite, PostgreSQL) for more robust data storage and querying.
- **Advanced Alerting:** Implement email notifications, Telegram/Discord bots, or other alert mechanisms.
- **Historical Analysis & Charting:** Allow users to view trends over time and visualize view counts.
- **User-Managed Channel Lists:** Allow adding/removing channels via an interface instead of just `config.yaml`.
- **More Sophisticated Anomaly Detection:** Explore more advanced statistical methods for defining a "surge."
- **Error Handling & Logging:** Implement more robust error handling and logging to a file.
- **Unit Tests:** Develop a comprehensive suite of unit tests.
```
