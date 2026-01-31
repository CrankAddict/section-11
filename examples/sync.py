#!/usr/bin/env python3
"""
Intervals.icu → GitHub/Local JSON Export
Exports training data for LLM access.
Supports both automated GitHub sync and manual local export.
"""

import requests
import json
import os
import argparse
from datetime import datetime, timedelta
from typing import Dict, List
import base64
import math


class IntervalsSync:
    """Sync Intervals.icu data to GitHub repository or local file"""
    
    INTERVALS_BASE_URL = "https://intervals.icu/api/v1"
    GITHUB_API_URL = "https://api.github.com"
    
    def __init__(self, athlete_id: str, intervals_api_key: str, github_token: str = None, 
                 github_repo: str = None, debug: bool = False):
        self.athlete_id = athlete_id
        self.intervals_auth = base64.b64encode(f"API_KEY:{intervals_api_key}".encode()).decode()
        self.github_token = github_token
        self.github_repo = github_repo
        self.debug = debug
    
    def _intervals_get(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch from Intervals.icu API"""
        if endpoint:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}/{endpoint}"
        else:
            url = f"{self.INTERVALS_BASE_URL}/athlete/{self.athlete_id}"
        headers = {
            "Authorization": f"Basic {self.intervals_auth}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def collect_training_data(self, days_back: int = 7, anonymize: bool = False) -> Dict:
        """Collect all training data for LLM analysis"""
        # For "last 7 days", we want today + previous 6 days = 7 days total
        oldest = (datetime.now() - timedelta(days=days_back - 1)).strftime("%Y-%m-%d")
        newest = datetime.now().strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        print("Fetching athlete data...")
        athlete = self._intervals_get("")
        
        cycling_settings = None
        if athlete.get("sportSettings"):
            for sport in athlete["sportSettings"]:
                if "Ride" in sport.get("types", []) or "VirtualRide" in sport.get("types", []):
                    cycling_settings = sport
                    break
        
        print("Fetching activities...")
        activities = self._intervals_get("activities", {"oldest": oldest, "newest": newest})
        
        print("Fetching wellness data...")
        wellness = self._intervals_get("wellness", {"oldest": oldest, "newest": newest})
        
        print("Fetching actual fitness metrics (yesterday + decay)...")
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_wellness = self._intervals_get("wellness", {"oldest": yesterday, "newest": yesterday})
            yesterday_data = yesterday_wellness[0] if yesterday_wellness else {}
            
            # PMC decay constants
            ctl_decay = math.exp(-1/42)  # ~0.9765
            atl_decay = math.exp(-1/7)   # ~0.8668
            
            # Calculate actual current values (after overnight decay, before any workout today)
            yesterday_ctl = yesterday_data.get("ctl")
            yesterday_atl = yesterday_data.get("atl")
            yesterday_ramp = yesterday_data.get("rampRate")
            
            ctl = round(yesterday_ctl * ctl_decay, 2) if yesterday_ctl else None
            atl = round(yesterday_atl * atl_decay, 2) if yesterday_atl else None
            ramp_rate = round(yesterday_ramp * ctl_decay, 2) if yesterday_ramp else None
        except:
            ctl = None
            atl = None
            ramp_rate = None
        
        tsb = round(ctl - atl, 2) if (ctl is not None and atl is not None) else None
        
        latest_wellness = wellness[-1] if wellness else {}
        
        print("Fetching planned workouts...")
        newest_ahead = (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
        events = self._intervals_get("events", {"oldest": datetime.now().strftime("%Y-%m-%d"), "newest": newest_ahead})
        
        data = {
            "READ_THIS_FIRST": {
                "instruction_for_ai": "DO NOT calculate totals from individual activities. Use the pre-calculated values in 'summary' and 'weekly_summary' sections below. These are already computed accurately from the API data.",
                "data_period": f"Last {days_back} days (including today)",
                "quick_stats": {
                    "total_training_hours": round(sum(act.get("moving_time", 0) for act in activities) / 3600, 2),
                    "total_activities": len(activities),
                    "total_tss": round(sum(act.get("icu_training_load", 0) for act in activities if act.get("icu_training_load")), 0)
                }
            },
            "metadata": {
                "athlete_id": "REDACTED" if anonymize else self.athlete_id,
                "last_updated": datetime.now().isoformat(),
                "data_range_days": days_back,
                "version": "1.0.0"
            },
            "summary": self._compute_activity_summary(activities, days_back),
            "current_status": {
                "fitness": {
                    "ctl": ctl,
                    "atl": atl,
                    "tsb": tsb,
                    "ramp_rate": ramp_rate
                },
                "thresholds": {
                    "ftp": cycling_settings.get("ftp") if cycling_settings else None,
                    "ftp_indoor": cycling_settings.get("indoor_ftp") if cycling_settings else None,
                    "lthr": cycling_settings.get("lthr") if cycling_settings else None,
                    "max_hr": cycling_settings.get("max_hr") if cycling_settings else None
                },
                "current_metrics": {
                    "weight_kg": latest_wellness.get("weight") or athlete.get("icu_weight"),
                    "resting_hr": latest_wellness.get("restingHR") or athlete.get("icu_resting_hr"),
                    "hrv": latest_wellness.get("hrv")
                }
            },
            "recent_activities": self._format_activities(activities, anonymize),
            "wellness_data": self._format_wellness(wellness),
            "planned_workouts": self._format_events(events, anonymize),
            "weekly_summary": self._compute_weekly_summary(activities, wellness)
        }
        
        return data
    
    def _format_activities(self, activities: List[Dict], anonymize: bool = False) -> List[Dict]:
        """Format activities for LLM analysis"""
        formatted = []
        for i, act in enumerate(activities):
            if self.debug and i == 0 and "VirtualRide" in act.get("type", ""):
                print("\n🔍 DEBUG: Available fields in VirtualRide activity:")
                print(json.dumps({k: v for k, v in act.items() if "power" in k.lower() or "watts" in k.lower() or "hr" in k.lower()}, indent=2))
            
            avg_power = (act.get("average_watts") or act.get("avg_watts") or 
                        act.get("average_power") or act.get("avgWatts") or
                        act.get("icu_average_watts"))
            norm_power = (act.get("weighted_average_watts") or act.get("np") or 
                         act.get("icu_pm_np") or act.get("normalizedPower") or
                         act.get("icu_weighted_avg_watts"))
            avg_hr = (act.get("average_heartrate") or act.get("avg_hr") or 
                     act.get("average_heart_rate") or act.get("avgHr") or
                     act.get("icu_average_hr"))
            max_hr = (act.get("max_heartrate") or act.get("max_hr") or 
                     act.get("max_heart_rate") or act.get("maxHr") or
                     act.get("icu_max_hr"))
            
            # Additional metrics
            avg_cadence = (act.get("average_cadence") or act.get("avg_cadence") or
                          act.get("icu_average_cadence"))
            avg_temp = (act.get("average_weather_temp") or act.get("average_temp") or 
                       act.get("avg_temp") or act.get("average_temperature"))
            # Convert joules to kilojoules, or use calories
            joules = act.get("icu_joules")
            work_kj = round(joules / 1000, 1) if joules else None
            calories = act.get("calories") or act.get("icu_calories")
            variability_index = act.get("icu_variability_index")
            decoupling = act.get("icu_hr_decoupling") or act.get("decoupling")
            
            # Speed and pace metrics (convert m/s to km/h)
            avg_speed_ms = act.get("average_speed")
            max_speed_ms = act.get("max_speed")
            avg_speed = round(avg_speed_ms * 3.6, 1) if avg_speed_ms else None  # km/h
            max_speed = round(max_speed_ms * 3.6, 1) if max_speed_ms else None  # km/h
            avg_pace = act.get("average_pace") or act.get("icu_pace")  # min/km
            
            # Weather data
            weather = act.get("weather_description") or act.get("weather")
            humidity = act.get("humidity") or act.get("average_humidity")
            wind_speed = act.get("average_wind_speed") or act.get("wind_speed")
            
            # Nutrition/fuel data
            carbs_used = act.get("carbs_used")
            carbs_ingested = act.get("carbs_ingested")
            
            hr_zones = {}
            power_zones = {}
            
            icu_hr_zone_times = act.get("icu_hr_zone_times", [])
            if icu_hr_zone_times and isinstance(icu_hr_zone_times, list):
                zone_labels = ["z1_time", "z2_time", "z3_time", "z4_time", "z5_time", "z6_time", "z7_time"]
                for idx, secs in enumerate(icu_hr_zone_times):
                    if idx < len(zone_labels):
                        hr_zones[zone_labels[idx]] = secs if secs is not None else 0
            
            icu_zone_times = act.get("icu_zone_times", [])
            if icu_zone_times:
                for zone in icu_zone_times:
                    zone_id = zone.get("id", "").lower()
                    secs = zone.get("secs", 0)
                    if zone_id in ["z1", "z2", "z3", "z4", "z5", "z6", "z7"]:
                        power_zones[f"{zone_id}_time"] = secs if secs is not None else 0
            
            zone_dist = {}
            if hr_zones:
                zone_dist["hr_zones"] = hr_zones
            if power_zones:
                zone_dist["power_zones"] = power_zones
            
            if not zone_dist:
                zone_dist = None
            
            activity_name = act.get("name", "")
            if anonymize:
                if "VirtualRide" in act.get("type", "") or "Indoor" in activity_name:
                    activity_name = activity_name
                else:
                    activity_name = "Training Session"
            
            activity = {
                "id": f"activity_{i+1}" if anonymize else act["id"],
                "date": act["start_date_local"],
                "type": act["type"],
                "name": activity_name,
                "duration_hours": round((act.get("moving_time") or 0) / 3600, 2),
                "distance_km": round((act.get("distance") or 0) / 1000, 2),
                "tss": act.get("icu_training_load"),
                "intensity_factor": act.get("icu_intensity"),
                "avg_power": avg_power,
                "normalized_power": norm_power,
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "avg_cadence": avg_cadence,
                "avg_speed": avg_speed,
                "max_speed": max_speed,
                "avg_pace": avg_pace,
                "avg_temp": avg_temp,
                "weather": weather,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "work_kj": work_kj,
                "calories": calories,
                "carbs_used": carbs_used,
                "carbs_ingested": carbs_ingested,
                "variability_index": variability_index,
                "decoupling": decoupling,
                "elevation_m": act.get("total_elevation_gain"),
                "feel": act.get("feel"),
                "rpe": act.get("icu_rpe"),
                "zone_distribution": zone_dist
            }
            
            formatted.append(activity)
        
        return formatted
    
    def _format_wellness(self, wellness: List[Dict]) -> List[Dict]:
        """Format wellness data"""
        formatted = []
        for w in wellness:
            entry = {
                "date": w["id"],
                "weight_kg": w.get("weight"),
                "resting_hr": w.get("restingHR"),
                "hrv_rmssd": w.get("hrv"),
                "hrv_sdnn": w.get("hrvSdnn"),
                "sleep_hours": round(w["sleepSecs"] / 3600, 2) if w.get("sleepSecs") else None,
                "sleep_quality": w.get("sleepQuality"),
                "mental_energy": w.get("mentalEnergy"),
                "fatigue": w.get("fatigue"),
                "soreness": w.get("soreness"),
                "avg_sleeping_hr": w.get("avgSleepingHR")
            }
            
            formatted.append(entry)
        
        return formatted
    
    def _format_events(self, events: List[Dict], anonymize: bool = False) -> List[Dict]:
        """Format planned workouts"""
        return [{
            "id": f"event_{i+1}" if anonymize else evt["id"],
            "date": evt["start_date_local"],
            "name": "Planned Workout" if anonymize else evt.get("name", ""),
            "type": evt.get("category", ""),
            "description": evt.get("description", ""),
            "planned_tss": evt.get("icu_training_load"),
            "duration_hours": round(evt.get("duration", 0) / 3600, 2)
        } for i, evt in enumerate(events)]
    
    def _compute_weekly_summary(self, activities: List[Dict], wellness: List[Dict]) -> Dict:
        """Compute weekly training summary from actual activity data"""
        total_tss = sum(act.get("icu_training_load", 0) for act in activities if act.get("icu_training_load"))
        total_seconds = sum(act.get("moving_time", 0) for act in activities)
        total_hours = total_seconds / 3600
        
        avg_hrv = None
        avg_rhr = None
        if wellness:
            hrv_values = [w.get("hrv") for w in wellness if w.get("hrv")]
            rhr_values = [w.get("restingHR") for w in wellness if w.get("restingHR")]
            avg_hrv = round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None
            avg_rhr = round(sum(rhr_values) / len(rhr_values), 1) if rhr_values else None
        
        return {
            "total_training_hours": round(total_hours, 2),
            "total_tss": round(total_tss, 0),
            "activities_count": len(activities),
            "avg_hrv": avg_hrv,
            "avg_resting_hr": avg_rhr
        }
    
    def _compute_activity_summary(self, activities: List[Dict], days_back: int = 7) -> Dict:
        """Compute summary by activity type with human-readable format"""
        from collections import defaultdict
        
        by_type = defaultdict(lambda: {"count": 0, "seconds": 0, "tss": 0, "distance_km": 0})
        
        for act in activities:
            activity_type = act.get("type", "Unknown")
            by_type[activity_type]["count"] += 1
            
            # Always use moving_time for all activity types
            time_seconds = act.get("moving_time", 0)
            
            by_type[activity_type]["seconds"] += time_seconds
            by_type[activity_type]["tss"] += act.get("icu_training_load", 0) or 0
            by_type[activity_type]["distance_km"] += (act.get("distance", 0) or 0) / 1000
        
        # Convert to readable format
        activity_breakdown = {}
        total_seconds = 0
        
        for activity_type, data in sorted(by_type.items()):
            activity_breakdown[activity_type] = {
                "duration_decimal_hours": round(data["seconds"] / 3600, 2),
                "count": data["count"],
                "tss": round(data["tss"], 0),
                "distance_km": round(data["distance_km"], 1)
            }
            total_seconds += data["seconds"]
        
        return {
            "period_description": f"Last {days_back} days of training (including today)",
            "note": "Duration calculated from API moving_time field. Minor differences (<30s) from Intervals.icu dashboard are normal due to rounding.",
            "total_duration_decimal_hours": round(total_seconds / 3600, 2),
            "total_activities": len(activities),
            "by_activity_type": activity_breakdown
        }
    
    def publish_to_github(self, data: Dict, filepath: str = "latest.json", 
                         commit_message: str = None) -> str:
        """Publish data to GitHub repository"""
        if not self.github_token or not self.github_repo:
            raise ValueError("GitHub token and repo required for publishing")
        
        if not commit_message:
            commit_message = f"Update training data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        url = f"{self.GITHUB_API_URL}/repos/{self.github_repo}/contents/{filepath}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                current_file = response.json()
                current_sha = current_file["sha"]
                
                current_content = base64.b64decode(current_file["content"]).decode()
                new_content = json.dumps(data, indent=2, default=str)
                
                if current_content == new_content:
                    print("⏭️  No changes detected, skipping update")
                    raw_url = f"https://raw.githubusercontent.com/{self.github_repo}/main/{filepath}"
                    return raw_url
            else:
                current_sha = None
        except Exception as e:
            print(f"⚠️  Could not check existing file: {e}")
            current_sha = None
        
        content_json = json.dumps(data, indent=2, default=str)
        content_base64 = base64.b64encode(content_json.encode()).decode()
        
        payload = {
            "message": commit_message,
            "content": content_base64,
            "branch": "main"
        }
        
        if current_sha:
            payload["sha"] = current_sha
        
        response = requests.put(url, headers=headers, json=payload)
        response.raise_for_status()
        
        raw_url = f"https://raw.githubusercontent.com/{self.github_repo}/main/{filepath}"
        return raw_url
    
    def save_to_file(self, data: Dict, filepath: str = "latest.json"):
        """Save data to local JSON file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Data saved to {filepath}")
        return filepath


def main():
    parser = argparse.ArgumentParser(description="Sync Intervals.icu data to GitHub or local file")
    parser.add_argument("--setup", action="store_true", help="Initial setup wizard")
    parser.add_argument("--athlete-id", help="Intervals.icu athlete ID")
    parser.add_argument("--intervals-key", help="Intervals.icu API key")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--github-repo", help="GitHub repo (format: username/repo)")
    parser.add_argument("--days", type=int, default=7, help="Days of data to export (default: 7)")
    parser.add_argument("--output", help="Save to local file instead of GitHub")
    parser.add_argument("--anonymize", action="store_true", default=True, help="Remove identifying information (default: enabled)")
    parser.add_argument("--debug", action="store_true", help="Show debug output for API fields")
    
    args = parser.parse_args()
    
    if args.setup:
        print("=== Intervals.icu Sync Setup ===\n")
        athlete_id = input("Intervals.icu Athlete ID (e.g., i123456): ")
        intervals_key = input("Intervals.icu API Key: ")
        github_token = input("GitHub Personal Access Token (or press Enter to skip): ")
        github_repo = input("GitHub Repository (username/repo, or press Enter to skip): ")
        
        config = {
            "athlete_id": athlete_id,
            "intervals_key": intervals_key,
        }
        if github_token:
            config["github_token"] = github_token
        if github_repo:
            config["github_repo"] = github_repo
            
        with open(".sync_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print("\n✅ Config saved to .sync_config.json")
        print("\nUsage:")
        print("  Export locally:    python sync.py --output latest.json")
        print("  Push to GitHub:    python sync.py")
        print("  Different range:   python sync.py --days 14 --output 14days.json")
        return
    
    config = {}
    if os.path.exists(".sync_config.json"):
        with open(".sync_config.json") as f:
            config = json.load(f)
    
    athlete_id = args.athlete_id or config.get("athlete_id") or os.getenv("ATHLETE_ID")
    intervals_key = args.intervals_key or config.get("intervals_key") or os.getenv("INTERVALS_KEY")
    github_token = args.github_token or config.get("github_token") or os.getenv("GITHUB_TOKEN")
    github_repo = args.github_repo or config.get("github_repo") or os.getenv("GITHUB_REPO")
    
    print(f"📋 Configuration:")
    print(f"   Athlete ID: {athlete_id[:5] + '...' if athlete_id else 'NOT SET'}")
    print(f"   Intervals Key: {intervals_key[:5] + '...' if intervals_key else 'NOT SET'}")
    print(f"   GitHub Repo: {github_repo or 'NOT SET'}")
    print(f"   GitHub Token: {'SET' if github_token else 'NOT SET'}")
    print(f"   Days: {args.days}")
    
    if not athlete_id or not intervals_key:
        print("\n❌ Error: Missing credentials.")
        print("   Run: python sync.py --setup")
        return
    
    if not args.output and (not github_token or not github_repo):
        print("\n❌ Error: Missing GitHub credentials for push.")
        print("   Either use --output to save locally, or configure GitHub in --setup")
        return
    
    print(f"\n🔄 Fetching {args.days} days of data...")
    sync = IntervalsSync(athlete_id, intervals_key, github_token, github_repo, debug=args.debug)
    
    data = sync.collect_training_data(days_back=args.days, anonymize=args.anonymize)
    
    if args.output:
        filepath = sync.save_to_file(data, args.output)
        if args.anonymize:
            print(f"   🔒 Anonymization: ENABLED")
        print(f"\n✅ Data saved to {filepath}")
        print(f"\n💡 Tip: Paste contents to AI, or upload the file directly")
    else:
        raw_url = sync.publish_to_github(data)
        
        print(f"\n✅ Data published to GitHub")
        if args.anonymize:
            print(f"   🔒 Anonymization: ENABLED")
        print(f"\n📊 Static URL for LLMs:")
        print(f"   {raw_url}")
        print(f"\n💬 Example prompt:")
        print(f'   "Analyze my training data from {raw_url}"')


if __name__ == "__main__":
    main()
