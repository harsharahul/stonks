/**
 * OIDC Authentication Provider for Stonks
 * Wraps the app with react-oidc-context configured for Authentik.
 *
 * Required environment variables (set in .env or at build time):
 *   VITE_OIDC_AUTHORITY  — Authentik OIDC issuer URL
 *                          e.g. https://auth.example.com/application/o/stonks/
 *   VITE_OIDC_CLIENT_ID  — OIDC client ID registered in Authentik
 */
import React, { useEffect } from 'react';
import { AuthProvider as OidcAuthProvider, useAuth as useOidcAuth } from 'react-oidc-context';
import { setAccessTokenGetter } from '../api/client';

const oidcConfig = {
  authority: import.meta.env.VITE_OIDC_AUTHORITY as string,
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID as string,
  redirect_uri: `${window.location.origin}/callback`,
  post_logout_redirect_uri: window.location.origin,
  // offline_access: Authentik issues a refresh token so oidc-client-ts can
  // renew expired access tokens in the background. Without it, sessions died
  // ~5-10 min after login (access-token lifetime) with no recovery path.
  scope: 'openid profile email offline_access',
  response_type: 'code',
  automaticSilentRenew: true,
  userStore: undefined as any,
};

const OIDC_ENABLED = Boolean(oidcConfig.authority && oidcConfig.client_id);

/** Inner component that bridges the OIDC token to Axios. */
function TokenBridge({ children }: { children: React.ReactNode }) {
  const auth = useOidcAuth();

  useEffect(() => {
    setAccessTokenGetter(() => auth.user?.access_token ?? null);
  }, [auth.user?.access_token]);

  // Industry-standard failure path: background renewal almost never fails
  // (rotating refresh tokens), but when it does (refresh token revoked, IdP
  // session expired) bounce through the IdP — instant and invisible if the
  // SSO session is alive, otherwise the user correctly lands on login.
  useEffect(() => {
    if (!auth.events) return;
    const onRenewError = () => {
      console.warn('OIDC silent renew failed — redirecting through IdP');
      auth.signinRedirect().catch(() => {/* user stays anonymous */});
    };
    auth.events.addSilentRenewError(onRenewError);
    return () => auth.events.removeSilentRenewError(onRenewError);
  }, [auth.events, auth.signinRedirect]);

  return <>{children}</>;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  if (!OIDC_ENABLED) {
    return <>{children}</>;
  }

  return (
    <OidcAuthProvider {...oidcConfig}>
      <TokenBridge>{children}</TokenBridge>
    </OidcAuthProvider>
  );
}
