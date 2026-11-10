# Accounts and verification

Rover uses account sign-up, email verification, and sign-in before enabling account-specific features.

## Account flow

1. Submit the sign-up form with the requested account details.
2. Rover sends a verification code to the supplied email address.
3. Enter the code on the verification page before its expiry, or use the resend flow if needed.
4. Sign in after verification to access the Design Dashboard, Notes, Settings, and AI integrations.

Sign-in and verification endpoints apply request limits. If an account is not verified, protected features remain unavailable until verification is complete.

```mermaid
stateDiagram-v2
    [*] --> Registration
    Registration --> PendingVerification: Verification email sent
    PendingVerification --> PendingVerification: Resend after cooldown
    PendingVerification --> Verified: Valid, unexpired code
    Verified --> SignedIn: Valid credentials
    SignedIn --> DesignDashboard
    SignedIn --> Notes
    SignedIn --> Integrations
    SignedIn --> TripleRover
```

<details>
  <summary>Email delivery troubleshooting</summary>
  <br>

  Check that `RESEND_API_KEY` is configured, the sender address is verified in Resend, and the recipient can receive messages. Keep the API key in private deployment configuration; never put it in the repository or a screenshot.
</details>
