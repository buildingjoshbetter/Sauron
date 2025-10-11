"""
Storage monitoring and management for SAURON.
Prevents SD card from filling up by intelligently managing data.
"""
import logging
import shutil
from pathlib import Path
from typing import Tuple


def get_storage_usage(path: Path) -> Tuple[int, int, float]:
    """
    Get storage usage for a given path.
    Returns: (used_gb, total_gb, percent_used)
    """
    try:
        stat = shutil.disk_usage(path)
        used_gb = stat.used / (1024 ** 3)
        total_gb = stat.total / (1024 ** 3)
        percent_used = (stat.used / stat.total) * 100
        return (used_gb, total_gb, percent_used)
    except Exception as e:
        logging.error(f"Failed to get storage usage: {e}")
        return (0, 0, 0)


def check_storage_cap(data_dir: Path, max_usage_percent: float = 70.0) -> bool:
    """
    Check if storage usage exceeds cap.
    Returns True if cleanup needed.
    
    Args:
        data_dir: Directory to monitor
        max_usage_percent: Maximum allowed usage (default 70% of total SD card)
    """
    used_gb, total_gb, percent_used = get_storage_usage(data_dir)
    
    logging.info(f"Storage usage: {used_gb:.2f}GB / {total_gb:.2f}GB ({percent_used:.1f}%)")
    
    if percent_used >= max_usage_percent:
        logging.warning(f"Storage cap reached: {percent_used:.1f}% >= {max_usage_percent}%")
        return True
    
    return False


def emergency_cleanup(data_dir: Path, nas_archive_dir: Path) -> int:
    """
    Emergency cleanup when storage cap is reached.
    Archives oldest files to NAS and deletes them from local storage.
    Returns number of files cleaned up.
    """
    from datetime import datetime, timedelta
    
    logging.warning("Running emergency cleanup due to storage cap")
    
    cleaned_count = 0
    
    # Archive audio files older than 12 hours
    audio_dir = data_dir / "audio"
    if audio_dir.exists():
        archive_dir = nas_archive_dir / "audio_archive" / "emergency"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        cutoff_time = datetime.now() - timedelta(hours=12)
        
        for audio_file in sorted(audio_dir.glob("audio_*.wav"), key=lambda p: p.stat().st_mtime):
            try:
                file_mtime = datetime.fromtimestamp(audio_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    # Move to NAS
                    dest = archive_dir / audio_file.name
                    audio_file.rename(dest)
                    cleaned_count += 1
                    logging.debug(f"Archived: {audio_file.name}")
            except Exception as e:
                logging.warning(f"Failed to archive {audio_file}: {e}")
    
    # Archive images older than 12 hours
    images_dir = data_dir / "images"
    if images_dir.exists():
        archive_dir = nas_archive_dir / "video_archive" / "emergency"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        cutoff_time = datetime.now() - timedelta(hours=12)
        
        for img_file in sorted(images_dir.glob("img_*.jpg"), key=lambda p: p.stat().st_mtime):
            try:
                file_mtime = datetime.fromtimestamp(img_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    # Move to NAS
                    dest = archive_dir / img_file.name
                    img_file.rename(dest)
                    cleaned_count += 1
                    logging.debug(f"Archived: {img_file.name}")
            except Exception as e:
                logging.warning(f"Failed to archive {img_file}: {e}")
    
    # Delete any orphaned video files
    video_dir = data_dir / "video"
    if video_dir.exists():
        for vid_file in video_dir.glob("motion_*.h264"):
            try:
                vid_file.unlink()
                cleaned_count += 1
                logging.debug(f"Deleted orphaned video: {vid_file.name}")
            except Exception as e:
                logging.warning(f"Failed to delete {vid_file}: {e}")
    
    logging.info(f"Emergency cleanup completed: {cleaned_count} files archived/deleted")
    
    return cleaned_count


def storage_monitor_worker(conf, memory_system):
    """
    Background worker that monitors storage and triggers cleanup when needed.
    Runs every 30 minutes.
    """
    import time
    
    while True:
        try:
            # Check storage every 30 minutes
            if check_storage_cap(conf.data_dir, max_usage_percent=70.0):
                # Emergency cleanup
                cleaned = emergency_cleanup(conf.data_dir, conf.nas_archive_dir)
                
                # Notify user via SMS
                try:
                    from .sms import send_sms
                    send_sms(
                        account_sid=conf.twilio_account_sid,
                        auth_token=conf.twilio_auth_token,
                        from_number=conf.twilio_from_number,
                        to_number=conf.twilio_to_number,
                        body=f"Storage cap reached. Archived {cleaned} files to NAS and freed up space.",
                    )
                    logging.info("Sent storage cleanup notification via SMS")
                except Exception as e:
                    logging.warning(f"Failed to send storage notification: {e}")
            
            # Sleep for 30 minutes
            time.sleep(1800)
        
        except Exception:
            logging.exception("Storage monitor error")
            time.sleep(300)  # Sleep 5 min on error

