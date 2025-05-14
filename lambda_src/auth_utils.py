import jwt # PyJWT library
from auth0.authentication.token_verifier import JwksFetcher # We can use JwksFetcher directly
from auth0.exceptions import Auth0Error # For JWKS fetching errors

from .config import AUTH0_DOMAIN, AUTH0_AUDIENCE # Relative import
from image_processor.logger import get_logger

logger = get_logger(__name__)

# --- Global variable for JwksFetcher instance for potential reuse within a warm Lambda --- 
_jwks_fetcher_instance = None

def get_jwks_fetcher():
    """Returns a singleton instance of JwksFetcher."""
    global _jwks_fetcher_instance
    if _jwks_fetcher_instance is None:
        if not AUTH0_DOMAIN:
            logger.error("AUTH0_DOMAIN is not configured. Cannot create JwksFetcher.")
            raise ValueError("AUTH0_DOMAIN must be set to initialize JwksFetcher.")
        jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
        logger.info(f"Initializing JwksFetcher with URL: {jwks_url}")
        try:
            _jwks_fetcher_instance = JwksFetcher(jwks_url, cache_ttl=3600) # Cache for 1 hour
        except Exception as e:
            logger.error(f"Failed to initialize JwksFetcher: {e}", exc_info=True)
            _jwks_fetcher_instance = None # Ensure it's reset on failure
            raise # Re-raise the exception to signal failure
    return _jwks_fetcher_instance

def validate_auth0_token(token_string: str) -> dict:
    """
    Validates an Auth0 access token using PyJWT and Auth0's JwksFetcher.
    Returns the decoded token payload (including user_sub).
    Raises an exception if validation fails.
    """
    logger.info("Attempting Auth0 token validation using PyJWT and JwksFetcher.")

    if not AUTH0_DOMAIN:
        logger.error("AUTH0_DOMAIN is not configured. Cannot validate token.")
        raise ValueError("AUTH0_DOMAIN must be set for token validation.")
    if not AUTH0_AUDIENCE:
        logger.error("AUTH0_AUDIENCE is not configured. Cannot validate token.")
        raise ValueError("AUTH0_AUDIENCE must be set for token validation.")
    if not token_string:
        logger.warning("No access token provided for validation.")
        raise ValueError("Access token cannot be empty.")

    try:
        jwks_fetcher = get_jwks_fetcher()
        if not jwks_fetcher:
            # This case should ideally be prevented by get_jwks_fetcher raising an error
            logger.error("JwksFetcher is not initialized. Cannot validate token.")
            raise ValueError("JwksFetcher not initialized.")

        # Get the kid from the token header without verification first
        unverified_header = jwt.get_unverified_header(token_string)
        if 'kid' not in unverified_header:
            logger.warning("Token validation failed: Missing 'kid' in token header.")
            raise jwt.PyJWTError("Token missing 'kid' in header.")
        kid = unverified_header['kid']

        # Get the public key (RSAPublicKey object) from JWKS using the kid
        # JwksFetcher.get_key(kid) can raise Auth0Error if key not found or JWKS fails
        public_key_obj = jwks_fetcher.get_key(kid)
        
        if public_key_obj is None: # Should be caught by Auth0Error from get_key if kid not found
            logger.warning(f"Token validation failed: Public key not found for kid '{kid}'.")
            raise jwt.PyJWTError(f"Public key not found for kid '{kid}'.")

        # Decode and validate the token using PyJWT
        expected_issuer = f'https://{AUTH0_DOMAIN}/'
        
        payload = jwt.decode(
            token_string,
            public_key_obj, # Pass the RSAPublicKey object directly
            algorithms=["RS256"], # Algorithm used to sign
            audience=AUTH0_AUDIENCE, # PyJWT checks if this is IN the token's 'aud' list (or matches if 'aud' is a string)
            issuer=expected_issuer,
            options={
                "verify_exp": True, 
                "verify_iat": True, 
                "verify_nbf": True,
                # "require": ["exp", "iat", "iss", "aud", "sub"] # Optionally enforce presence of claims
            }
        )

        if 'sub' not in payload:
            logger.warning("Validated Auth0 token (PyJWT) does not contain 'sub' claim, but other checks passed.")
            # Depending on strictness, you might raise an error here or allow it.
            # For now, we log a warning. If 'sub' is absolutely essential, add to 'require' options or raise here.

        logger.info(f"Auth0 token (PyJWT) validated successfully. User_sub: {payload.get('sub', 'N/A')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token validation error (PyJWT): Token has expired.")
        raise ValueError("Invalid access token: Token has expired.")
    except jwt.InvalidAudienceError:
        logger.warning(f"Token validation error (PyJWT): Invalid Audience. Expected '{AUTH0_AUDIENCE}' in token's aud claim.")
        raise ValueError("Invalid access token: Invalid audience.")
    except jwt.InvalidIssuerError:
        logger.warning(f"Token validation error (PyJWT): Invalid Issuer. Expected '{expected_issuer}'.")
        raise ValueError("Invalid access token: Invalid issuer.")
    except Auth0Error as e: # Catch errors from JwksFetcher (e.g., key not found, JWKS URL issue)
        logger.error(f"Auth0 SDK error during JWKS fetching/key retrieval: {e}", exc_info=True)
        raise ValueError(f"Invalid access token: JWKS/key retrieval error ({e})")
    except jwt.PyJWTError as e: # Catch other PyJWT specific errors (e.g., malformed token, signature mismatch)
        logger.error(f"Token validation error (PyJWT): {e}", exc_info=True)
        raise ValueError(f"Invalid access token: JWT processing error ({e})")
    except ValueError as ve: # Catch ValueErrors raised from our own checks or get_jwks_fetcher
        logger.error(f"ValueError during token validation: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during PyJWT token validation: {e}", exc_info=True)
        raise ValueError(f"Unexpected token validation error (PyJWT): {e}") 