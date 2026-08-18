"use client";

import { usePathname } from "next/navigation";
import Nav from "./Nav";

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isDevPanel = pathname === "/dev" || pathname.startsWith("/dev/");

  if (isDevPanel) {
    return <main>{children}</main>;
  }

  return (
    <>
      <Nav />
      <main className="pt-16">{children}</main>
    </>
  );
}
