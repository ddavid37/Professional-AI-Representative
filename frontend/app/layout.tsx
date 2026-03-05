import type { Metadata } from "next";
import "./globals.css";
import Nav from "./components/Nav";

export const metadata: Metadata = {
  title: "Daniel David — AI Representative",
  description:
    "Professional AI representative for Daniel David, ML Engineer & Columbia CS '26.",
  openGraph: {
    title: "Daniel David — AI Representative",
    description: "Chat with Daniel's AI representative. Ask about his work, skills, or leave a message.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="min-h-screen bg-background text-text-primary antialiased">
        <Nav />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
