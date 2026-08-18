"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Home, Mail, MessageSquare } from "lucide-react";

import ThemeToggle from "./ThemeToggle";

const links = [
  { href: "/",        label: "Home",    icon: Home           },
  { href: "/chat",    label: "Chat",    icon: MessageSquare  },
  { href: "/resume",  label: "Resume",  icon: FileText       },
  { href: "/contact", label: "Contact", icon: Mail           },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/80 bg-background/90 backdrop-blur-md">
      <nav className="flex h-16 w-full items-center justify-between px-6 lg:px-12 xl:px-20">
        <Link
          href="/"
          className="font-display text-lg tracking-tight text-text-primary hover:text-accent transition-colors"
        >
          Daniel David
        </Link>

        <div className="flex items-center gap-1">
          <ul className="flex items-center gap-1">
            {links.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || (href !== "/" && pathname.startsWith(href));
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                      active
                        ? "bg-accent-muted text-accent"
                        : "text-text-secondary hover:text-text-primary hover:bg-surface"
                    }`}
                  >
                    <Icon size={14} strokeWidth={1.75} />
                    <span className="hidden sm:inline">{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
