import os
import yaml
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json # For potentially saving data directly, or for structuring return values

# It's good practice to load configuration within the functions that need it,
# or pass it as an argument, rather than loading globally.

def load_config():
    """Loads the configuration from config/config.yaml."""
    # Construct the path to the config file relative to this script's location
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # This should point to the project root
    config_path = os.path.join(base_dir, 'config', 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        if not config:
            raise ValueError("Config file is empty or malformed.")
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        # Potentially create a dummy config or raise an error
        return None # Or raise
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration: {e}")
        return None # Or raise


def get_youtube_service(api_key):
    """Initializes and returns the YouTube API service client."""
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("API key is missing or is a placeholder. Please update config/config.yaml.")
        # In a real application, you might raise an exception here or handle it more gracefully.
        return None
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        return youtube
    except Exception as e:
        print(f"Error building YouTube service: {e}")
        return None


def get_channel_videos(youtube_service, channel_id, published_after_days=7):
    """
    Fetches video details for a specific channel, published within the last N days.
    Args:
        youtube_service: The initialized YouTube API service.
        channel_id: The ID of the YouTube channel.
        published_after_days: How many days back to fetch videos from.
    Returns:
        A list of video details (id, title, published_at, view_count).
    """
    if not youtube_service:
        print("YouTube service is not available.")
        return []

    videos_data = []
    try:
        # 1. Find the uploads playlist ID for the channel
        channel_response = youtube_service.channels().list(
            id=channel_id,
            part='contentDetails'
        ).execute()

        if not channel_response.get('items'):
            print(f"No items found for channel ID: {channel_id}. Channel might be invalid or have no content details.")
            return []

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # 2. Get videos from the uploads playlist
        # Calculate the date to filter videos
        published_after_date = (datetime.utcnow() - timedelta(days=published_after_days)).isoformat("T") + "Z"

        next_page_token = None
        while True:
            playlist_items_response = youtube_service.playlistItems().list(
                playlistId=uploads_playlist_id,
                part='snippet,contentDetails',
                maxResults=50, # Max allowed by API
                pageToken=next_page_token
            ).execute()

            video_ids = []
            video_publish_dates = {}
            for item in playlist_items_response.get('items', []):
                video_id = item.get('contentDetails', {}).get('videoId')
                # We need to filter by publish date here as playlistItems don't support publishedAfter directly
                # snippet.publishedAt is the date video was added to playlist, not necessarily video publish date.
                # We'll get the actual publish date from the video resource itself later.
                # For now, let's grab all recent playlist additions and then filter.
                # A better approach for very active channels might be to use search.list with channelId and publishedAfter.
                if video_id:
                    video_ids.append(video_id)
                    # Store the playlist add date as a fallback or for reference
                    video_publish_dates[video_id] = item['snippet']['publishedAt']


            if not video_ids:
                break # No videos found in this page

            # 3. Get video details (including view count and actual publish date) for the collected video IDs
            video_details_response = youtube_service.videos().list(
                id=','.join(video_ids),
                part='snippet,statistics'
            ).execute()

            for video in video_details_response.get('items', []):
                video_actual_publish_date_str = video['snippet']['publishedAt']
                video_actual_publish_date = datetime.strptime(video_actual_publish_date_str, "%Y-%m-%dT%H:%M:%SZ")

                # Compare with our desired published_after_date
                # Need to parse published_after_date string back to datetime for comparison
                published_after_datetime = datetime.strptime(published_after_date.split('T')[0], "%Y-%m-%d")

                # Strip time for comparison if published_after_date was just a date
                if video_actual_publish_date.date() >= published_after_datetime.date():
                    videos_data.append({
                        'id': video['id'],
                        'title': video['snippet']['title'],
                        'published_at': video_actual_publish_date_str,
                        'view_count': int(video['statistics'].get('viewCount', 0)), # Ensure view_count is int
                        'like_count': int(video['statistics'].get('likeCount', 0)), # Example of getting more stats
                        'comment_count': int(video['statistics'].get('commentCount', 0)) # Example
                    })

            next_page_token = playlist_items_response.get('nextPageToken')
            if not next_page_token:
                break # No more pages

    except Exception as e:
        print(f"An error occurred while fetching videos for channel {channel_id}: {e}")
        # Potentially log the error to a file or a more sophisticated logging system

    # Sort videos by publish date, most recent first
    videos_data.sort(key=lambda v: v['published_at'], reverse=True)
    return videos_data


def fetch_all_channels_data(config):
    """
    Fetches video data for all channels listed in the configuration.
    Args:
        config: The loaded configuration dictionary.
    Returns:
        A dictionary containing data for all channels, structured by category (korean, international).
        Example:
        {
            "korean": [
                {"channel_id": "xxx", "name": "Channel A", "videos": [...]},
                ...
            ],
            "international": [
                {"channel_id": "yyy", "name": "Channel B", "videos": [...]},
                ...
            ]
        }
    """
    if not config or 'youtube_api_key' not in config or 'channels' not in config:
        print("Configuration is missing API key or channel list.")
        return {}

    api_key = config['youtube_api_key']
    youtube_service = get_youtube_service(api_key)
    if not youtube_service:
        return {} # Error already printed by get_youtube_service

    all_data = {"korean": [], "international": []}

    analysis_settings = config.get('analysis_settings', {})
    fetch_days = analysis_settings.get('baseline_days', 7) # Use baseline_days as a reasonable period to fetch

    for category, channels in config['channels'].items():
        if category not in all_data:
            print(f"Warning: Channel category '{category}' in config is not 'korean' or 'international'. Skipping.")
            continue
        if not channels: # Handle case where a category might be empty
            print(f"No channels listed for category: {category}")
            continue
        for channel_info in channels:
            channel_id = channel_info.get('id') # Changed from 'channel_id' to 'id' to match config.yaml
            channel_name = channel_info.get('name', 'Unknown Channel')
            if not channel_id:
                print(f"Missing 'id' for a channel in '{category}'. Skipping.")
                continue

            print(f"Fetching videos for {category} channel: {channel_name} ({channel_id})")
            videos = get_channel_videos(youtube_service, channel_id, published_after_days=fetch_days)
            all_data[category].append({
                "channel_id": channel_id,
                "name": channel_name,
                "videos": videos,
                "fetched_at": datetime.utcnow().isoformat()
            })
            print(f"Fetched {len(videos)} videos for channel {channel_name}.")

    return all_data

if __name__ == '__main__':
    # Example usage (for testing this module directly)
    # This part will only run when youtube_collector.py is executed as the main script.
    print("Testing YouTube Collector Module...")
    config = load_config()
    if config:
        # Replace with actual channel IDs in your config/config.yaml for testing
        # Ensure 'YOUR_API_KEY_HERE' is also replaced with a real key.
        if config.get('youtube_api_key') == "YOUR_API_KEY_HERE":
            print("Please set your YouTube API key in config/config.yaml")
        else:
            # Create dummy channel entries in config for testing if they don't exist
            if not config['channels']['korean'] and not config['channels']['international']:
                print("Please add some channel IDs to config/config.yaml under 'korean' or 'international' sections for testing.")
                print("Example format for a channel entry:")
                print("  - id: 'UClbR8o_l7swIZVsqrDbV6wA' # Example: Google Developers channel")
                print("    name: 'Google Developers'")

            # Temporarily add a public channel for testing if none are configured
            # This avoids errors if the user hasn't set up channels yet.
            # For actual runs, the user's configured channels will be used.
            test_channel_added = False
            # Corrected check for 'international' channels
            if not config['channels'].get('international'):
                if 'international' not in config['channels']:
                    config['channels']['international'] = []
                config['channels']['international'].append({
                    "id": "UClbR8o_l7swIZVsqrDbV6wA", # Google Developers
                    "name": "Google Developers (Test)"
                })
                test_channel_added = True
                print("Temporarily added 'Google Developers' channel for testing purposes.")

            channel_data = fetch_all_channels_data(config)

            if test_channel_added: # Clean up if we added a test channel
                config['channels']['international'].pop()

            if channel_data:
                print("\nFetched data summary:")
                for category, channels in channel_data.items():
                    print(f"Category: {category}")
                    for channel in channels:
                        print(f"  Channel: {channel['name']} ({channel['channel_id']}) - {len(channel['videos'])} videos")

                # Example: Save to a file (optional, could be done in main.py)
                # data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
                # if not os.path.exists(data_dir):
                #     os.makedirs(data_dir)
                # file_path = os.path.join(data_dir, 'youtube_data_test.json')
                # with open(file_path, 'w') as f:
                #     json.dump(channel_data, f, indent=4)
                # print(f"\nTest data saved to {file_path}")
            else:
                print("No data fetched. Check API key and channel configurations.")
    else:
        print("Could not load configuration. Collector cannot run.")
