// frontend/app/layout.tsx
import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { AnalysisProvider } from './providers';

// Apply a restrained interface typeface suitable for a production workspace.
const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
    title: 'MemeDirector | Cultural Reference Director',
    description: 'Turn screenplay moments into actionable cultural-reference opportunities.',
};

// Provide application state once so an uploaded File survives client-side route changes.
export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body className={inter.variable}>
                <AnalysisProvider>{children}</AnalysisProvider>
            </body>
        </html>
    );
}
