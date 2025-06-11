from datetime import datetime, timedelta

def calculate_average_views(videos):
    """Calculates the average view count for a list of video objects."""
    if not videos:
        return 0
    total_views = sum(video.get('view_count', 0) for video in videos)
    return total_views / len(videos)

def analyze_channel_data(channel_data, analysis_settings):
    """
    Analyzes video data for a single channel to detect view surges.
    Args:
        channel_data: A dictionary containing channel info and a list of its videos.
                      Example: {"channel_id": "xxx", "name": "Channel A", "videos": [...]}
        analysis_settings: A dictionary with settings like surge_threshold_percentage,
                           recent_days_for_surge, and baseline_days.
                           Example: {
                               'surge_threshold_percentage': 50,
                               'recent_days_for_surge': 3,
                               'baseline_days': 7
                           }
    Returns:
        A list of videos that are considered to have surged, with additional analysis info.
        Example: [
            {
                'id': 'video_id', 'title': 'Video Title', 'view_count': 150000,
                'published_at': '...', 'days_since_published': 1,
                'baseline_avg_views': 50000, 'percentage_increase': 200,
                'is_surge': True
            }, ...
        ]
    """
    videos = channel_data.get('videos', [])
    if not videos:
        return []

    surge_threshold_percentage = analysis_settings.get('surge_threshold_percentage', 50)
    recent_days = analysis_settings.get('recent_days_for_surge', 3)
    baseline_days = analysis_settings.get('baseline_days', 7) # Days *before* the recent_days period

    now = datetime.utcnow()

    recent_videos = []
    baseline_videos = []

    for video in videos:
        published_at_str = video.get('published_at')
        if not published_at_str:
            continue

        # Ensure published_at_str is parsed correctly, assuming ISO format with 'Z'
        try:
            if published_at_str.endswith('Z'):
                published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ")
            else: # Fallback if 'Z' is missing, though API usually includes it
                published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError as e:
            print(f"Error parsing date {published_at_str} for video {video.get('id')}: {e}")
            continue

        days_since_published = (now - published_at).days

        if 0 <= days_since_published <= recent_days:
            video['days_since_published'] = days_since_published
            recent_videos.append(video)
        elif recent_days < days_since_published <= recent_days + baseline_days:
            video['days_since_published'] = days_since_published # For context if needed
            baseline_videos.append(video)

    if not recent_videos:
        # No videos in the "recent" period to analyze
        return []

    baseline_avg_views = calculate_average_views(baseline_videos)

    surged_videos_details = []
    for video in recent_videos:
        view_count = video.get('view_count', 0)
        percentage_increase = 0
        is_surge = False

        if baseline_avg_views > 0: # Avoid division by zero if no baseline views
            percentage_increase = ((view_count - baseline_avg_views) / baseline_avg_views) * 100
        elif view_count > 0: # If no baseline, any views on a recent video could be considered significant
            percentage_increase = float('inf') # Represents a very large increase

        if percentage_increase >= surge_threshold_percentage:
            is_surge = True

        # Add analysis details to the video dictionary itself or a new dictionary
        analysis_info = {
            **video, # Spread existing video info
            'baseline_avg_views': round(baseline_avg_views),
            'percentage_increase': round(percentage_increase, 2),
            'is_surge': is_surge
        }
        surged_videos_details.append(analysis_info)

    # Filter out non-surged videos from the detailed list, or return all with 'is_surge' flag
    # For this function, let's return details for all recent videos, including the surge flag
    return surged_videos_details


def run_analysis(all_channels_data, config):
    """
    Runs the analysis for all channels.
    Args:
        all_channels_data: Data fetched by the youtube_collector.
                           Example: {"korean": [...], "international": [...]}
        config: The application's configuration dictionary, expected to contain 'analysis_settings'.
    Returns:
        A dictionary with analysis results, structured similarly to input, but with
        an 'analysis_results' key for each channel.
        Example:
        {
            "korean": [
                {
                    "channel_id": "xxx", "name": "Channel A",
                    "videos": [...], # Original videos
                    "analysis_results": { # Results from analyze_channel_data
                        "surged_videos": [...], # Only videos flagged as surge
                        "all_recent_videos_analysis": [...] # All recent videos with analysis data
                    }
                }, ...
            ],
            "international": [...]
        }
    """
    if 'analysis_settings' not in config:
        print("Error: 'analysis_settings' not found in configuration.")
        return {} # Or raise an error

    analysis_settings = config['analysis_settings']
    results = {"korean": [], "international": []}

    for category, channels in all_channels_data.items():
        if category not in results:
            print(f"Warning: Data category '{category}' not recognized for analysis. Skipping.")
            continue

        for channel_data in channels:
            channel_name = channel_data.get('name', 'Unknown Channel')
            print(f"Analyzing data for {category} channel: {channel_name}")

            # `analyze_channel_data` returns a list of all recent videos with analysis details
            # including the 'is_surge' flag.
            all_recent_videos_with_analysis = analyze_channel_data(channel_data, analysis_settings)

            # Filter to get only those videos that are actual surges
            surged_videos_only = [v for v in all_recent_videos_with_analysis if v['is_surge']]

            channel_result_entry = {
                **channel_data, # Include original channel info and all fetched videos
                "analysis_results": {
                    "surged_videos": surged_videos_only,
                    "all_recent_videos_analysis": all_recent_videos_with_analysis # For context or detailed display
                }
            }
            results[category].append(channel_result_entry)
            print(f"Analysis complete for {channel_name}. Found {len(surged_videos_only)} surged videos.")

    return results

if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    print("Testing Analysis Engine Module...")

    # Dummy config for testing
    test_config = {
        'analysis_settings': {
            'surge_threshold_percentage': 50, # 50% increase
            'recent_days_for_surge': 3,      # Videos in last 3 days
            'baseline_days': 7               # Baseline from day 4 to day 10
        }
    }

    # Dummy channel data for testing
    now_utc = datetime.utcnow()
    test_channel_data = {
        "korean": [
            {
                "channel_id": "korean123",
                "name": "Korean Test Channel",
                "videos": [
                    # Recent videos
                    {'id': 'k_vid1', 'title': 'Recent Korean Surge Video', 'view_count': 150000, 'published_at': (now_utc - timedelta(days=1)).isoformat() + "Z"},
                    {'id': 'k_vid2', 'title': 'Recent Korean Normal Video', 'view_count': 60000, 'published_at': (now_utc - timedelta(days=2)).isoformat() + "Z"},
                    # Baseline videos
                    {'id': 'k_vid3', 'title': 'Baseline Korean Video 1', 'view_count': 50000, 'published_at': (now_utc - timedelta(days=5)).isoformat() + "Z"},
                    {'id': 'k_vid4', 'title': 'Baseline Korean Video 2', 'view_count': 55000, 'published_at': (now_utc - timedelta(days=7)).isoformat() + "Z"},
                    {'id': 'k_vid5', 'title': 'Baseline Korean Video 3 (Older)', 'view_count': 45000, 'published_at': (now_utc - timedelta(days=10)).isoformat() + "Z"},
                     # This one should be too old for baseline
                    {'id': 'k_vid6', 'title': 'Too Old Korean Video', 'view_count': 100000, 'published_at': (now_utc - timedelta(days=15)).isoformat() + "Z"},
                ]
            }
        ],
        "international": [
            {
                "channel_id": "intl456",
                "name": "International Test Channel",
                "videos": [
                     # Recent videos
                    {'id': 'i_vid1', 'title': 'Recent Intl Low View Video', 'view_count': 1000, 'published_at': (now_utc - timedelta(days=1)).isoformat() + "Z"},
                    # Baseline (no baseline videos, to test that case)
                ]
            }
        ]
    }

    analysis_results = run_analysis(test_channel_data, test_config)

    if analysis_results:
        print("\nAnalysis Results Summary:")
        for category, channels in analysis_results.items():
            print(f"Category: {category}")
            for channel in channels:
                print(f"  Channel: {channel['name']} ({channel['channel_id']})")
                surges = channel.get('analysis_results', {}).get('surged_videos', [])
                if surges:
                    for video in surges:
                        print(f"    SURGE: {video['title']} - Views: {video['view_count']}, Increase: {video['percentage_increase']}% over avg {video['baseline_avg_views']}")
                else:
                    print("    No significant surges detected.")
                # Optionally print all_recent_videos_analysis for more detail
                # print("    All recent videos analyzed:")
                # for video_analysis in channel.get('analysis_results', {}).get('all_recent_videos_analysis', []):
                #     print(f"      - {video_analysis['title']}: Views {video_analysis['view_count']}, Surge? {video_analysis['is_surge']}")

    else:
        print("Analysis produced no results (this might be an error or no data).")
