import os
import jwt # PyJWT library
import time # For potential delays, not strictly used in validation logic here

from auth0.authentication.token_verifier import JwksFetcher # We can use JwksFetcher directly
from auth0.exceptions import Auth0Error # For JWKS fetching errors

# --- Configuration for the local script ---
# Try to get ACCESS_TOKEN from environment variable first, then hardcoded, then prompt.
ACCESS_TOKEN = os.environ.get(
    'ACCESS_TOKEN',
    # Fallback to a hardcoded token (e.g., for quick tests, but be careful with committing real tokens)
    "eyJhbGciOiJSUzI1NiIsInR5cCI6ImF0K2p3dCIsImtpZCI6ImllbUJIdDI5bU16aHNmeE03UTZ3dCJ9.eyJpc3MiOiJodHRwczovL2F1dGguc3BhcmtpcS5haS8iLCJzdWIiOiJnb29nbGUtb2F1dGgyfDEwMTkyMjA0NTA5MzI2Nzc4Mzc1MSIsImF1ZCI6WyJodHRwczovL2FwaS5zcGFya2lxLmFpIiwiaHR0cHM6Ly9kZXYtanRveG5iZG9pc2kyemJoNi51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ3MzcyMDM0LCJleHAiOjE3NDc0NTg0MzQsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJqdGkiOiJyeGdIUjJFSFR6dDRCdGhTQkJoejJRIiwiY2xpZW50X2lkIjoiYkcwVXptM0MxOEpuMDZ3bzJ2TGdKektxTGRCcE5kTGEifQ.TiXwaI3oLeY495f2sAlayK5XSuGBXCWfyzm_4QkpK0BIugqGKYfqvxoCyAEZywUeX0btbssn9aQtSu0vhsW-Jvni8ZP4s8wrLuTZkgbcwX4Fz-a_r-H-6UMK6nAN5vHq9VMvonLLhi9_fzyK6UPkkehHoKBEPIJaL8e2ActzSrRCeiee2CrCz4z1Qtcut1sl8-XofzPTX1CEOkR01tZcR1fSdjOHZERLLengd4qNUwTbnKOPVxftefbyy7dX3cKKIOXrNDmgz5-9K6QhKMQwdztoR8DvpMhEPFSf03-NLggp4x1ZDeegcbqjM3wZVYjow_cQPvTDo69l6MgaZYzhVQ"
)

AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN', "auth.sparkiq.ai")
# Ensure this matches the audience your token is intended for and what's configured in your Auth0 API settings
AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE', "https://api.sparkiq.ai")

_jwks_fetcher_instance_local = None

def get_jwks_fetcher_local():
    global _jwks_fetcher_instance_local
    if _jwks_fetcher_instance_local is None:
        if not AUTH0_DOMAIN:
            print("Error: Local AUTH0_DOMAIN must be set.")
            return None
        jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
        print(f"[Local Script] Initializing JwksFetcher with URL: {jwks_url}")
        try:
            _jwks_fetcher_instance_local = JwksFetcher(jwks_url, cache_ttl=3600)
        except Exception as e:
            print(f"[Local Script] Failed to initialize JwksFetcher: {e}")
            _jwks_fetcher_instance_local = None 
    return _jwks_fetcher_instance_local

def validate_access_token_with_pyjwt_locally(token_string):
    if not AUTH0_DOMAIN:
        print("Error: AUTH0_DOMAIN must be set for this script.")
        return None
    if not AUTH0_AUDIENCE:
        print("Error: AUTH0_AUDIENCE must be set for this script.")
        return None
    if not token_string:
        print("Error: No access token provided to validate_access_token_with_pyjwt_locally.")
        return None

    print(f"[Local Script] Attempting to validate token using PyJWT.")
    try:
        jwks_fetcher = get_jwks_fetcher_local()
        if not jwks_fetcher:
            print("[Local Script] JwksFetcher not initialized. Cannot validate token.")
            return None

        unverified_header = jwt.get_unverified_header(token_string)
        if 'kid' not in unverified_header:
            print("[Local Script] Error: Token missing 'kid' in header.")
            return None
        kid = unverified_header['kid']

        public_key_obj = jwks_fetcher.get_key(kid) 
        if public_key_obj is None:
            print(f"[Local Script] Error: Public key not found for kid '{kid}'.")
            return None
        
        # print(f"[DEBUG][Local Script] Key object fetched for kid '{kid}': {public_key_obj}")
        # print(f"[DEBUG][Local Script] Type of key object fetched: {type(public_key_obj)}")

        expected_issuer = f'https://{AUTH0_DOMAIN}/'
        payload = jwt.decode(
            token_string,
            public_key_obj, # Expects the key object directly
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE, 
            issuer=expected_issuer,
            options={"verify_exp": True, "verify_iat": True, "verify_nbf": True}
        )

        if 'sub' not in payload:
            print("[Local Script] Warning: Validated token does not contain 'sub' (user_sub), but other checks passed.")
        
        print(f"[Local Script] Token validated successfully using PyJWT! User_sub: {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        print("[Local Script] Token validation error (PyJWT): Token has expired.")
    except jwt.InvalidAudienceError:
        print(f"[Local Script] Token validation error (PyJWT): Invalid Audience. Expected '{AUTH0_AUDIENCE}' in token's aud claim.")
    except jwt.InvalidIssuerError:
        print(f"[Local Script] Token validation error (PyJWT): Invalid Issuer. Expected '{expected_issuer}'.")
    except Auth0Error as e: 
        print(f"[Local Script] Auth0 SDK error during JWKS fetching/key retrieval: {e}")
    except jwt.PyJWTError as e: 
        print(f"[Local Script] Token validation error (PyJWT): {e}")
    except Exception as e:
        print(f"[Local Script] An unexpected error occurred: {e}")
    
    return None

if __name__ == "__main__":
    print("--- Local Auth0 Token Validation Script (PyJWT) ---")
    
    # Prompt for token if the default/env var is empty or placeholder-like
    if not ACCESS_TOKEN or ACCESS_TOKEN == "YOUR_ACCESS_TOKEN_HERE" or len(ACCESS_TOKEN) < 20:
        print("ACCESS_TOKEN is not set, is a placeholder, or seems too short.")
        pasted_token = input("Paste your Access Token here: ").strip()
        if pasted_token:
            ACCESS_TOKEN = pasted_token
        else:
            print("No Access Token provided. Exiting.")
            exit(1)
            
    print(f"Using AUTH0_DOMAIN: {AUTH0_DOMAIN}")
    print(f"Using AUTH0_AUDIENCE (expected in token): {AUTH0_AUDIENCE}")
    print(f"Token to validate (first 30 chars): {ACCESS_TOKEN[:30]}...")
    
    decoded_payload = validate_access_token_with_pyjwt_locally(ACCESS_TOKEN)
    
    if decoded_payload:
        print("\n--- Decoded Payload (PyJWT - Local Script) ---")
        for key, value in decoded_payload.items():
            print(f"  {key}: {value}")
        print("---------------------------------------------")
    else:
        print("\nToken validation FAILED (PyJWT - Local Script).") 
    
    print("--- Script Finished ---") 