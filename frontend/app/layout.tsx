import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Microsoft Support Agent",
  description: "Enterprise support agent powered by GitHub Copilot SDK, Azure AI Foundry, and Work IQ",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
