"use client";

import { usePathname } from "next/navigation";
import Nav from "./Nav";
import ThemeToggle from "./ThemeToggle";

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isDevPanel = pathname === "/dev" || pathname.startsWith("/dev/");

  if (isDevPanel) {
    return (
      <>
        <div className="flex h-12 items-center justify-end px-6 lg:px-12">
          <ThemeToggle />
        </div>
        <main>{children}</main>
      </>
    );
  }

  return (
    <>
      <Nav />
      <main className="pt-16">{children}</main>
    </>
  );
}
