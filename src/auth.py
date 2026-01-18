"""
Authentication using Clerk.
Handles JWT verification and user management.
"""

import os
from functools import wraps
from typing import Optional
import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Clerk configuration
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
CLERK_PUBLISHABLE_KEY = os.environ.get("CLERK_PUBLISHABLE_KEY")
CLERK_JWT_KEY = os.environ.get("CLERK_JWT_KEY")  # PEM format public key


security = HTTPBearer(auto_error=False)


class ClerkUser:
    """Represents an authenticated Clerk user"""
    
    def __init__(self, clerk_id: str, email: str, name: str = "", image_url: str = ""):
        self.clerk_id = clerk_id
        self.email = email
        self.name = name
        self.image_url = image_url
    
    def __repr__(self):
        return f"ClerkUser(id={self.clerk_id}, email={self.email})"


def verify_clerk_token(token: str) -> Optional[ClerkUser]:
    """
    Verify a Clerk JWT token and extract user info.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        ClerkUser if valid, None otherwise
    """
    if not CLERK_JWT_KEY:
        # Development mode - accept any token with mock user
        print("⚠️  CLERK_JWT_KEY not set - running in development mode")
        return ClerkUser(
            clerk_id="dev_user_123",
            email="dev@example.com",
            name="Development User"
        )
    
    try:
        # Clerk uses RS256 algorithm
        payload = jwt.decode(
            token,
            CLERK_JWT_KEY,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Clerk doesn't always set audience
        )
        
        # Extract user info from Clerk JWT claims
        return ClerkUser(
            clerk_id=payload.get("sub", ""),
            email=payload.get("email", payload.get("primary_email_address", "")),
            name=payload.get("name", payload.get("first_name", "") + " " + payload.get("last_name", "")).strip(),
            image_url=payload.get("image_url", payload.get("profile_image_url", ""))
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> ClerkUser:
    """
    FastAPI dependency to get the current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: ClerkUser = Depends(get_current_user)):
            return {"user_id": user.clerk_id}
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = verify_clerk_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[ClerkUser]:
    """
    FastAPI dependency for optional authentication.
    Returns None if not authenticated instead of raising an error.
    """
    if not credentials:
        return None
    
    try:
        return verify_clerk_token(credentials.credentials)
    except HTTPException:
        return None


# Clerk webhook verification
def verify_clerk_webhook(payload: bytes, signature: str) -> bool:
    """
    Verify a webhook request from Clerk.
    
    Args:
        payload: Raw request body
        signature: Svix-Signature header value
        
    Returns:
        True if valid
    """
    # Clerk uses Svix for webhooks
    # In production, you'd verify the signature using the webhook secret
    # For now, we'll skip verification in development
    
    if not CLERK_SECRET_KEY:
        print("⚠️  Skipping webhook verification in development mode")
        return True
    
    try:
        from svix.webhooks import Webhook
        
        webhook_secret = os.environ.get("CLERK_WEBHOOK_SECRET", "")
        if not webhook_secret:
            return False
        
        wh = Webhook(webhook_secret)
        wh.verify(payload, {
            "svix-signature": signature
        })
        return True
        
    except Exception as e:
        print(f"Webhook verification failed: {e}")
        return False


# React component for frontend auth
CLERK_REACT_SETUP = """
// Install: npm install @clerk/clerk-react

// In your main App.jsx or index.jsx:
import { ClerkProvider, SignIn, SignUp, SignedIn, SignedOut, UserButton } from '@clerk/clerk-react';

const clerkPubKey = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

function App() {
  return (
    <ClerkProvider publishableKey={clerkPubKey}>
      <SignedOut>
        <SignIn />
      </SignedOut>
      <SignedIn>
        <UserButton />
        {/* Your app content */}
      </SignedIn>
    </ClerkProvider>
  );
}

// To get the token for API calls:
import { useAuth } from '@clerk/clerk-react';

function MyComponent() {
  const { getToken } = useAuth();
  
  const callAPI = async () => {
    const token = await getToken();
    const response = await fetch('/api/loans', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  };
}
"""


# HTML snippet for non-React apps
CLERK_SCRIPT_SETUP = """
<!-- Add to your HTML head -->
<script 
  async 
  crossorigin="anonymous"
  data-clerk-publishable-key="YOUR_PUBLISHABLE_KEY"
  src="https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js"
></script>

<script>
  window.addEventListener('load', async () => {
    await Clerk.load();
    
    if (!Clerk.user) {
      // Show sign-in
      Clerk.openSignIn();
    } else {
      // User is signed in
      console.log('User:', Clerk.user);
      
      // Get token for API calls
      const token = await Clerk.session.getToken();
      // Use token in Authorization header
    }
  });
</script>
"""
