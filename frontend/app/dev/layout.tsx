import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Developer panel",
  robots: { index: false, follow: false },
};

export default function DevLayout({ children }: { children: React.ReactNode }) {
  return children;
}
