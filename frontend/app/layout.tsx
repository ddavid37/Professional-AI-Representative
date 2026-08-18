import type { Metadata } from "next";
import { cookies } from "next/headers";
import { DM_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";
import AppChrome from "./components/AppChrome";
import { ThemeProvider } from "./components/ThemeProvider";
import { THEME_COOKIE } from "../lib/theme";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Daniel David — ML Engineer",
  description:
    "Daniel David — Columbia CS graduate. ML engineer specializing in federated learning, agentic AI, and production ML systems. Open to new opportunities.",
  openGraph: {
    title: "Daniel David — ML Engineer",
    description:
      "Columbia CS graduate open to ML/AI roles. Chat with my AI representative or get in touch.",
    type: "website",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const theme = cookieStore.get(THEME_COOKIE)?.value === "light" ? "light" : "dark";

  return (
    <html
      lang="en"
      className={`scroll-smooth ${dmSans.variable} ${instrumentSerif.variable}${theme === "light" ? " light" : ""}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-background font-sans text-text-primary antialiased">
        <ThemeProvider initialTheme={theme}>
          <AppChrome>{children}</AppChrome>
        </ThemeProvider>
      </body>
    </html>
  );
}
