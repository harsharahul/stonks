/**
 * useAuth: Stonks-flavoured wrapper around react-oidc-context's useAuth.
 * Returns a stable API regardless of whether OIDC is configured.
 *
 * Admin status is determined by the backend (ADMIN_EMAILS env var) via /auth/me,
 * not by OIDC claims, so the frontend never needs Authentik group configuration.
 */
import { useEffect, useState } from 'react';
import { useAuth as useOidcAuth } from 'react-oidc-context';
import { authApi } from '../api/client';

export interface StonksUser {
  name: string;
  email: string;
  avatarUrl: string | null;
  role: 'user' | 'admin';
  /** Raw OIDC sub claim */
  sub: string;
}

export interface AuthState {
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  user: StonksUser | null;
  accessToken: string | null;
  login: () => void;
  logout: () => void;
  /** True when OIDC is configured (env vars present). */
  isOidcEnabled: boolean;
}

// M6: OIDC_ENABLED is a compile-time constant: Vite inlines the env vars at build.
// This means the conditional hook call below is safe: the branch never changes at runtime.
const OIDC_ENABLED =
  Boolean(import.meta.env.VITE_OIDC_AUTHORITY) &&
  Boolean(import.meta.env.VITE_OIDC_CLIENT_ID);

/** H2: Validate avatar URL is HTTPS to prevent XSS via javascript: or data: URIs. */
const safeAvatarUrl = (url: unknown): string | null => {
  if (typeof url !== 'string') return null;
  try { return new URL(url).protocol === 'https:' ? url : null; }
  catch { return null; }
};

/**
 * Hook that works even if the AuthProvider is not wrapping the component tree
 * (e.g. during local dev without Authentik configured).
 */
export function useAuth(): AuthState {
  // react-oidc-context throws if called outside AuthProvider,
  // so we only call it when OIDC is actually configured.
  const oidc = OIDC_ENABLED ? useOidcAuth() : null; // eslint-disable-line react-hooks/rules-of-hooks
  const [backendRole, setBackendRole] = useState<'user' | 'admin' | null>(null);

  // Fetch the backend role once when the user authenticates
  useEffect(() => {
    if (!oidc?.isAuthenticated || !oidc.user?.access_token) {
      setBackendRole(null);
      return;
    }
    let cancelled = false;
    authApi.getMe().then((me) => {
      if (!cancelled) setBackendRole(me.role);
    }).catch(() => {
      if (!cancelled) setBackendRole(null);
    });
    return () => { cancelled = true; };
  }, [oidc?.isAuthenticated, oidc?.user?.access_token]);

  if (!OIDC_ENABLED || !oidc) {
    return {
      isLoading: false,
      isAuthenticated: false,
      isAdmin: false,
      user: null,
      accessToken: null,
      login: () => {},
      logout: () => {},
      isOidcEnabled: false,
    };
  }

  const profile = oidc.user?.profile;
  const accessToken = oidc.user?.access_token ?? null;
  const isAdmin = backendRole === 'admin';

  const user: StonksUser | null = profile
    ? {
        name: (profile.name as string) || (profile.preferred_username as string) || profile.email as string,
        email: profile.email as string,
        avatarUrl: safeAvatarUrl(profile.picture),
        role: isAdmin ? 'admin' : 'user',
        sub: profile.sub,
      }
    : null;

  return {
    isLoading: oidc.isLoading,
    isAuthenticated: oidc.isAuthenticated,
    isAdmin,
    user,
    accessToken,
    login: () => oidc.signinRedirect(),
    // NOT signoutRedirect(): oidc-client-ts appends id_token_hint +
    // post_logout_redirect_uri, and Authentik 400s ("request is otherwise
    // malformed") when the post-logout URI isn't registered on the provider.
    // Clearing the local session and visiting the bare end-session flow URL
    // logs out reliably on every host the app is served from.
    logout: () => {
      const authority = ((import.meta.env.VITE_OIDC_AUTHORITY as string) || '').replace(/\/?$/, '/');
      void oidc.removeUser().finally(() => {
        if (authority) window.location.href = `${authority}end-session/`;
      });
    },
    isOidcEnabled: true,
  };
}
