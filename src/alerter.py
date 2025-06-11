from datetime import datetime

def format_alert(channel_info, video_info):
    """Formats a single video surge alert message."""
    message = (
        f"ALERT: Potential Surge Detected!\n"
        f"  Channel: {channel_info.get('name', 'N/A')} ({channel_info.get('channel_id', 'N/A')})\n"
        f"  Video Title: {video_info.get('title', 'N/A')}\n"
        f"  Published: {video_info.get('published_at', 'N/A')}\n"
        f"  Views: {video_info.get('view_count', 'N/A')}\n"
        f"  Days Since Published: {video_info.get('days_since_published', 'N/A')}\n"
        f"  Baseline Avg Views: {video_info.get('baseline_avg_views', 'N/A')}\n"
        f"  Percentage Increase: {video_info.get('percentage_increase', 'N/A')}%\n"
        f"  Video URL: https://www.youtube.com/watch?v={video_info.get('id', '')}\n"
        f"--------------------------------------------------"
    )
    return message

def report_surges(analysis_results):
    """
    Prints surge alerts to the console based on analysis results.
    Args:
        analysis_results: The output from the analysis_engine's run_analysis function.
                          Expected structure:
                          {
                              "korean": [
                                  {
                                      "channel_id": "xxx", "name": "Channel A",
                                      "analysis_results": { "surged_videos": [...] }
                                  }, ...
                              ],
                              "international": [...]
                          }
    """
    print("\n--- Coin Peak Detector Alerts ---")
    print(f"Report generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    has_surges = False
    for category, channels in analysis_results.items():
        if not channels:
            continue

        print(f"--- {category.upper()} CHANNELS ---")
        category_has_surges = False
        for channel_data in channels:
            surged_videos = channel_data.get('analysis_results', {}).get('surged_videos', [])
            if surged_videos:
                has_surges = True
                category_has_surges = True
                # Basic channel info for the alert
                channel_info_for_alert = {
                    'name': channel_data.get('name'),
                    'channel_id': channel_data.get('channel_id')
                }
                for video_info in surged_videos:
                    print(format_alert(channel_info_for_alert, video_info))

        if not category_has_surges:
            print(f"No surges detected for any channels in the {category} category.")
        print("") # Add a blank line after each category section

    if not has_surges:
        print("No significant surges detected across all channels.")

    print("--- End of Report ---")

if __name__ == '__main__':
    # Example Usage (for testing this module directly)
    print("Testing Alerter Module...")

    # Dummy analysis results for testing
    dummy_results = {
        "korean": [
            {
                "channel_id": "korean123",
                "name": "Korean Test Channel",
                "analysis_results": {
                    "surged_videos": [
                        {
                            'id': 'k_vid1', 'title': 'Recent Korean Surge Video',
                            'view_count': 150000, 'published_at': '2023-10-26T12:00:00Z',
                            'days_since_published': 1, 'baseline_avg_views': 50000,
                            'percentage_increase': 200, 'is_surge': True
                        }
                    ]
                }
            },
            {
                "channel_id": "korean456",
                "name": "Quiet Korean Channel",
                "analysis_results": {
                    "surged_videos": [] # No surges
                }
            }
        ],
        "international": [
            {
                "channel_id": "intl789",
                "name": "International Test Channel",
                "analysis_results": {
                    "surged_videos": [
                        {
                            'id': 'i_vid1', 'title': 'Hot International Video',
                            'view_count': 2500000, 'published_at': '2023-10-25T10:00:00Z',
                            'days_since_published': 2, 'baseline_avg_views': 800000,
                            'percentage_increase': 212.5, 'is_surge': True
                        },
                        {
                            'id': 'i_vid2', 'title': 'Another Intl Spike',
                            'view_count': 120000, 'published_at': '2023-10-26T08:00:00Z',
                            'days_since_published': 1, 'baseline_avg_views': 40000,
                            'percentage_increase': 200.0, 'is_surge': True
                        }
                    ]
                }
            }
        ],
        "empty_category": [] # Test empty category
    }

    report_surges(dummy_results)

    print("\nTesting with no surges:")
    no_surge_results = {
        "korean": [
            {
                "channel_id": "korean123",
                "name": "Korean Test Channel",
                "analysis_results": {"surged_videos": []}
            }
        ],
        "international": []
    }
    report_surges(no_surge_results)
