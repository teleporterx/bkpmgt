# auth/routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .tokens import create_access_token

auth_router = APIRouter()

class TokenRequest(BaseModel):
    system_uuid: str
    password: str

@auth_router.post("/token")
async def login(token_request: TokenRequest):
    # Access the data using the model
    system_uuid = token_request.system_uuid
    password = token_request.password

    # Validate user credentials
    if not await validate_user_credentials(system_uuid, password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Create and return the token
    token = create_access_token(data={"sub": system_uuid})
    return {"access_token": token, "token_type": "bearer"}

async def validate_user_credentials(system_uuid: str, password: str) -> bool:
    # Implement logic to validate the user credentials
    # For example, check against a database
    # The following compares password with a hardcoded password and returns bool
    return password == "deepdefend_authpass"  # Replace with actual validation later