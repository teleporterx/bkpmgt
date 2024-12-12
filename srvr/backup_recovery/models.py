import strawberry
# Granular time duration model
@strawberry.input
class TimeDurationInput:
    # Include relevant time denominations, rule out un-realistic ones {months, years, ...}
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0