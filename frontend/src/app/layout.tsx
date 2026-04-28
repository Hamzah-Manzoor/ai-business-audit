import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI Business Audit',
  description: 'AI-powered business website audit platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
