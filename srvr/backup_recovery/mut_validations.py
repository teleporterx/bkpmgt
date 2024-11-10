from typing import Optional

def validate_scheduler_repeats(scheduler_repeats: Optional[str]) -> Optional[str]:
    if scheduler_repeats is None:
        return None  # No validation needed if not specified
    
    if scheduler_repeats == "once" or scheduler_repeats == "infinite":
        return scheduler_repeats
    
    try:
        # Check if it's a valid positive integer
        num_repeats = int(scheduler_repeats)
        if num_repeats > 0:
            return str(num_repeats)  # Return the number of repetitions as a string
        else:
            return "Error: 'scheduler_repeats' must be a positive integer or one of 'once' or 'infinite'"
    except ValueError:
        return "Error: 'scheduler_repeats' must be either 'once', 'infinite', or a positive integer"