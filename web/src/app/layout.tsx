import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { InitialBootOverlay } from "@/components/InitialBootOverlay";

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Market Maker — Agentic Nexus",
  description: "Agent thought-chain transparency for OpenClaw.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={jetbrains.variable}>
      <body className="min-h-screen antialiased nexus-bg">
        <InitialBootOverlay />
        {children}
      </body>
    </html>
  );
}
