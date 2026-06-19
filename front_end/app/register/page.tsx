'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { registerUser } from '@/lib/mtg-client';

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [discord, setDiscord] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);

    try {
      const result = await registerUser(username, password, discord);
      setSuccess(result.message);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md p-8 space-y-6 bg-card rounded-xl border border-border shadow-lg">
        <h1 className="text-2xl font-bold text-center text-foreground">Create Account</h1>
        
        {error && <div className="p-3 text-sm text-red-500 bg-red-500/10 rounded border border-red-500/20">{error}</div>}
        {success && <div className="p-3 text-sm text-green-500 bg-green-500/10 rounded border border-green-500/20">{success}</div>}

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-400">Username</label>
            <Input 
              value={username} 
              onChange={(e) => setUsername(e.target.value)} 
              required 
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-zinc-400">Discord Handle (e.g., username)</label>
            <Input 
              value={discord} 
              onChange={(e) => setDiscord(e.target.value)} 
              required 
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-zinc-400">Password</label>
            <Input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              required 
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-zinc-400">Confirm Password</label>
            <Input 
              type="password" 
              value={confirmPassword} 
              onChange={(e) => setConfirmPassword(e.target.value)} 
              required 
              className="mt-1"
            />
          </div>

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? 'Registering...' : 'Register'}
          </Button>
        </form>

        <p className="text-center text-sm text-zinc-400 mt-4">
          Already have an account? <Link href="/login" className="text-indigo-400 hover:underline">Log in</Link>
        </p>
      </div>
    </div>
  );
}