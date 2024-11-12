from typing import Optional

def validate_scheduler_repeats(scheduler_repeats: Optional[str]) -> Optional[str]:
    if scheduler_repeats is None:
        return None  # No validation needed if not specified
    
    if scheduler_repeats == "once" or scheduler_repeats == "infinite":
        return scheduler_repeats
    
    # Handle special cases: cycle, random
    if "cycle" in scheduler_repeats or "random" in scheduler_repeats:
        parts = scheduler_repeats.split()  # Split type and number (e.g., "cycle 3")
        if len(parts) == 2 and parts[0] in ["cycle", "random"]:
            try:
                num_repeats = int(parts[1])
                if num_repeats > 0:
                    return parts  # Return the list [type, number]
                else:
                    return "Error: The number after 'cycle' or 'random' must be a positive integer"
            except ValueError:
                return "Error: Invalid number after 'cycle' or 'random'"
        else:
            return "Error: Invalid format for 'cycle' or 'random' repeats"
    
    # Handle regular whole number repeats
    try:
        num_repeats = int(scheduler_repeats)
        if num_repeats > 0:
            return str(num_repeats)  # Return as string
        else:
            return "Error: 'scheduler_repeats' must be a positive integer"
    except ValueError:
        return "Error: 'scheduler_repeats' must be either 'once', 'infinite', a positive integer or some special case"