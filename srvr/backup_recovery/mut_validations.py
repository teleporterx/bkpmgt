# backup_recovery/mut_validations.py
from typing import Optional, Dict
from srvr.backup_recovery.models import TimeDurationInput
from datetime import datetime, timezone

def validate_scheduler_repeats(scheduler_repeats: Optional[str]) -> Optional[str]:
    if scheduler_repeats is None:
        return None  # No validation needed if not specified
    
    # Handle valid cases: "once", "infinite", or a positive whole number
    if scheduler_repeats == "once" or scheduler_repeats == "infinite":
        return scheduler_repeats
    
    # Handle regular whole number repeats
    try:
        num_repeats = int(scheduler_repeats)
        if num_repeats > 0:
            return str(num_repeats)  # Return as string
        else:
            return "Error: 'scheduler_repeats' must be a positive integer"
    except ValueError:
        return "Error: 'scheduler_repeats' must be either 'once', 'infinite', or a positive integer"

def validate_scheduler_priority(scheduler_priority: Optional[int]) -> Optional[str]:
    if scheduler_priority is None:
        return None  # No validation needed if not specified

    if isinstance(scheduler_priority, int):
        return str(scheduler_priority)  # Return the priority as a string (you can also return it as an int if required)
    else:
        return "Error: 'scheduler_priority' must be a whole number"

def prime_scheduler(
    scheduler: Optional[str], 
    scheduler_repeats: Optional[str], 
    scheduler_priority: Optional[int], 
    interval: Optional[TimeDurationInput], 
    timelapse: Optional[str], 
    task_message: Dict
) -> Optional[str]:
    # Validate scheduler repeats and priority
    if scheduler:
        scheduler_repeats_validation = validate_scheduler_repeats(scheduler_repeats)
        scheduler_priority_validation = validate_scheduler_priority(scheduler_priority)
        
        # If validation fails, return the error message
        if scheduler_repeats_validation and "Error" in scheduler_repeats_validation:
            return "Error: Invalid scheduler_repeats input!"
        
        if scheduler_priority_validation and "Error" in scheduler_priority_validation:
            return "Error: Invalid scheduler_priority input!"

        # Add the validated values to task_message
        task_message["scheduler_repeats"] = scheduler_repeats_validation
        task_message["scheduler_priority"] = scheduler_priority_validation

        # Define scheduling actions based on scheduler type
        scheduling_action = {
            "interval": lambda: task_message.update({
                "interval": {
                    "days": interval.days,
                    "hours": interval.hours,
                    "minutes": interval.minutes,
                    "seconds": interval.seconds,
                }
            }) if interval else None,
            "timelapse": lambda: task_message.update({
                "timelapse": datetime.fromisoformat(timelapse).astimezone(timezone.utc).isoformat() if timelapse else None
            }) if timelapse else None
        }

        try:
            # Apply the scheduling action based on the scheduler type
            action = scheduling_action[scheduler]
            action()
        except KeyError as e:
            return f"Error: Invalid scheduler {e}"

    return None  # No error, meaning scheduling was handled successfully