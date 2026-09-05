import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'ICRA Frontend',
    description: 'AI-powered full-stack starter app',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
