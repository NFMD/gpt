import os
import json
from datetime import datetime
import yaml # For loading config directly if not using youtube_collector's loader

# Assuming src is the current working directory or in PYTHONPATH
from youtube_collector import load_config as load_collector_config, fetch_all_channels_data
from analysis_engine import run_analysis
from alerter import report_surges

# A more generic config loader for main.py, if preferred
def load_main_config():
    """Loads the configuration from config/config.yaml, relative to project root."""
    # Assumes main.py is in src/, so config is one level up then into config/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Project root
    config_path = os.path.join(base_dir, 'config', 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        if not config:
            print("Warning: Configuration file is empty or malformed.")
            return None # Or a default config / raise error
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration: {e}")
        return None

def save_data_to_file(data, directory="data", filename_prefix="youtube_data"):
    """Saves the given data to a JSON file in the specified directory."""
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"Created data directory: {directory}")
        except OSError as e:
            print(f"Error creating data directory {directory}: {e}")
            return None # Cannot save if directory cannot be created

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    # Construct path relative to project root if main.py is in src/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_directory_path = os.path.join(base_dir, directory)

    # Re-check directory existence using the full path
    if not os.path.exists(full_directory_path):
        try:
            os.makedirs(full_directory_path)
            print(f"Created data directory: {full_directory_path}")
        except OSError as e:
            print(f"Error creating data directory {full_directory_path}: {e}")
            return None

    file_path = os.path.join(full_directory_path, f"{filename_prefix}_{timestamp}.json")

    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Successfully saved data to {file_path}")
        return file_path
    except Exception as e:
        print(f"Error saving data to {file_path}: {e}")
        return None

def main():
    """Main function to run the coin peak detector."""
    print("Starting Coin Peak Detector...")

    # 1. Load Configuration
    # Using the loader from youtube_collector as it's already robust
    # config = load_collector_config()
    # Or use the one defined in main.py:
    config = load_main_config()

    if not config:
        print("Critical: Could not load configuration. Exiting.")
        return

    api_key = config.get('youtube_api_key')
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("Critical: YouTube API key is missing or is a placeholder in config/config.yaml.")
        print("Please obtain an API key and update the configuration file.")
        print("Setup instructions can be found in the README.md (once it's updated with this info).")
        return

    if not config.get('channels') or (not config['channels'].get('korean') and not config['channels'].get('international')):
        print("Warning: No channels configured in config/config.yaml. The application might not produce useful results.")
        # Allow to continue if user wants to test other parts, or return here

    # 2. Fetch Data
    print("\nFetching YouTube data...")
    # The config is passed to fetch_all_channels_data, which then extracts the API key and channel lists.
    raw_youtube_data = fetch_all_channels_data(config)

    if not raw_youtube_data or (not raw_youtube_data.get('korean') and not raw_youtube_data.get('international')):
        # Check if it's empty due to API key issue or no channels actually returning data
        if get_youtube_service_status(api_key): # A helper to check if API key is generally valid
             print("No data fetched for any channels. This could be due to incorrect channel IDs, no recent videos, or API quota issues.")
        else:
             print("Failed to initialize YouTube Service. Check API Key and internet connection.")
        # Decide whether to proceed with empty data or exit
        # For now, let's proceed to allow analysis of any previously stored data if that feature were implemented
        print("Proceeding with potentially empty data for analysis.")


    # 3. Store Data (Optional but Recommended)
    if raw_youtube_data:
        # The save_data_to_file function now correctly calculates path from project root
        save_data_to_file(raw_youtube_data, directory="data", filename_prefix="youtube_channel_views")
    else:
        print("No new data fetched to save.")

    # 4. Analyze Data
    print("\nAnalyzing collected data...")
    # Pass the freshly fetched data and the main config (which includes analysis_settings)
    analysis_results = run_analysis(raw_youtube_data, config)

    if not analysis_results:
        print("Analysis did not produce any results. This might be due to no input data or issues in the analysis engine.")
        # Exiting if no analysis results, as alerter would have nothing to report.
        return

    # 5. Report Alerts
    print("\nReporting surges...")
    report_surges(analysis_results)

    print("\nCoin Peak Detector run finished.")

# Helper function to check API service status (simplified)
def get_youtube_service_status(api_key):
    from googleapiclient.discovery import build
    try:
        build('youtube', 'v3', developerKey=api_key)
        return True
    except Exception:
        return False

if __name__ == '__main__':
    main()
