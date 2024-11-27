# backup_recovery/mut_validations.py
from typing import Optional

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