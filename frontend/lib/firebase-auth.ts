// frontend/lib/firebase-auth.ts
// Provide invisible, persistent Firebase Anonymous Authentication for API calls.
'use client';

import { getApp, getApps, initializeApp } from 'firebase/app';
import { browserLocalPersistence, getAuth, setPersistence, signInAnonymously, type User } from 'firebase/auth';

let userPromise: Promise<User> | null = null;

// Create or restore one anonymous visitor and return a current Firebase ID token.
export async function getFirebaseIdToken(): Promise<string> {
    if (!userPromise) userPromise = (async () => {
        try {
            const config = {
                apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
                authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
                projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
            };
            if (!config.apiKey || !config.authDomain || !config.projectId) {
                throw new Error('Firebase authentication is not configured.');
            }
            const app = getApps().length ? getApp() : initializeApp(config);
            const auth = getAuth(app);
            await setPersistence(auth, browserLocalPersistence);
            return auth.currentUser ?? (await signInAnonymously(auth)).user;
        } catch (error) {
            userPromise = null;
            throw error;
        }
    })();
    const user = await userPromise;
    return await user.getIdToken();
}

// Attach a verified-user bearer token to every FastAPI request.
export async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    try {
        const token = await getFirebaseIdToken();
        const headers = new Headers(init.headers);
        headers.set('Authorization', `Bearer ${token}`);
        return await fetch(input, { ...init, headers });
    } catch (error) {
        throw error;
    }
}
