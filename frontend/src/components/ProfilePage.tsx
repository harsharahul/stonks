import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi, UserProfile } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useTheme, Theme } from '../hooks/useTheme';
import { Settings, User, Sun, Moon, Monitor, Save, Check } from 'lucide-react';
import { cn } from '../utils/format';

const ProfilePage: React.FC = () => {
  const { isAuthenticated, login, isOidcEnabled } = useAuth();
  const { theme, setTheme } = useTheme();
  const queryClient = useQueryClient();

  const [editName, setEditName] = useState('');
  const [nameSaved, setNameSaved] = useState(false);
  const [themeSaved, setThemeSaved] = useState(false);

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile'],
    queryFn: () => authApi.getMe(),
    enabled: isAuthenticated,
  });

  // Sync edit field when profile loads
  useEffect(() => {
    if (profile?.name) setEditName(profile.name);
  }, [profile?.name]);

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; preferences?: Record<string, any> }) =>
      authApi.updateMe(data),
    onSuccess: (updated) => {
      queryClient.setQueryData(['profile'], updated);
    },
  });

  const handleSaveName = () => {
    if (!editName.trim() || editName === profile?.name) return;
    updateMutation.mutate({ name: editName.trim() }, {
      onSuccess: () => {
        setNameSaved(true);
        setTimeout(() => setNameSaved(false), 2000);
      },
    });
  };

  const handleThemeChange = (t: Theme) => {
    setTheme(t);
    // Persist to backend preferences
    updateMutation.mutate({ preferences: { theme: t } }, {
      onSuccess: () => {
        setThemeSaved(true);
        setTimeout(() => setThemeSaved(false), 2000);
      },
    });
  };

  // Guard: not logged in
  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto mt-20 text-center px-4">
        <User className="w-12 h-12 mx-auto text-neutral-300 dark:text-neutral-600 mb-4" />
        <h2 className="text-xl font-semibold text-neutral-800 dark:text-white mb-2">Profile</h2>
        <p className="text-neutral-500 dark:text-neutral-400 mb-6">Sign in to view your profile.</p>
        {isOidcEnabled && (
          <button onClick={login} className="px-5 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium text-sm">
            Sign In
          </button>
        )}
      </div>
    );
  }

  if (isLoading) {
    return <div className="text-center py-12 text-neutral-500 dark:text-neutral-400">Loading profile...</div>;
  }

  if (error || !profile) {
    return <div className="text-center py-12 text-red-500">Failed to load profile. Try refreshing.</div>;
  }

  const initial = profile.name?.charAt(0)?.toUpperCase() || '?';

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <h1 className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
        <Settings className="w-6 h-6 text-neutral-500" /> Profile
      </h1>

      {/* Profile Card */}
      <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-6">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
            {initial}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-neutral-900 dark:text-white truncate">{profile.name}</h2>
              {profile.role === 'admin' && (
                <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                  ADMIN
                </span>
              )}
            </div>
            <p className="text-sm text-neutral-500 dark:text-neutral-400 truncate">{profile.email}</p>
            {profile.created_at && (
              <p className="text-xs text-neutral-400 dark:text-neutral-500 mt-1">
                Member since {new Date(profile.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Edit Name */}
      <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Display Name</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="flex-1 px-3 py-2 border border-neutral-200 dark:border-neutral-700 rounded-lg bg-white dark:bg-neutral-900 text-sm text-neutral-900 dark:text-white placeholder-neutral-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="Your display name"
          />
          <button
            onClick={handleSaveName}
            disabled={updateMutation.isLoading || !editName.trim() || editName === profile.name}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-1.5 transition-colors',
              nameSaved
                ? 'bg-green-600 text-white'
                : 'bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50'
            )}
          >
            {nameSaved ? <><Check className="w-4 h-4" /> Saved</> : <><Save className="w-4 h-4" /> Save</>}
          </button>
        </div>
      </div>

      {/* Theme Preferences */}
      <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">Preferences</h3>
          {themeSaved && <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1"><Check className="w-3 h-3" /> Saved</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-neutral-600 dark:text-neutral-400 mr-2">Theme</span>
          {([
            { value: 'light' as Theme, label: 'Light', icon: Sun },
            { value: 'dark' as Theme, label: 'Dark', icon: Moon },
            { value: 'system' as Theme, label: 'System', icon: Monitor },
          ]).map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              onClick={() => handleThemeChange(value)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                theme === value
                  ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                  : 'bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-400 border border-transparent hover:bg-neutral-200 dark:hover:bg-neutral-600'
              )}
            >
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>
      </div>

      {/* Account Info */}
      <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">Account</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-neutral-500 dark:text-neutral-400">Provider</dt>
          <dd className="text-neutral-900 dark:text-white">Authentik</dd>

          {profile.last_login_at && (
            <>
              <dt className="text-neutral-500 dark:text-neutral-400">Last login</dt>
              <dd className="text-neutral-900 dark:text-white">
                {new Date(profile.last_login_at).toLocaleString(undefined, {
                  year: 'numeric', month: 'short', day: 'numeric',
                  hour: 'numeric', minute: '2-digit',
                })}
              </dd>
            </>
          )}

          <dt className="text-neutral-500 dark:text-neutral-400">User ID</dt>
          <dd className="text-neutral-500 dark:text-neutral-400 font-mono text-xs truncate">{profile.id}</dd>
        </dl>
      </div>
    </div>
  );
};

export default ProfilePage;
