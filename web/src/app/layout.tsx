import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { InitialBootOverlay } from "@/components/InitialBootOverlay";
import { ThemeProvider } from "@/components/ThemeProvider";

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
    <html lang="en" className={jetbrains.variable} suppressHydrationWarning>
      <body className="min-h-screen antialiased nexus-bg">
        <Script
          id="nexus-theme-boot"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(()=>{try{var t=localStorage.getItem('nexus-theme');if(t==='light')document.documentElement.classList.add('light');else document.documentElement.classList.remove('light');}catch(e){}})();`,
          }}
        />
        <InitialBootOverlay />
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
