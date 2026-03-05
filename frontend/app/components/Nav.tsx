"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Home, Mail, MessageSquare } from "lucide-react";

const links = [
  { href: "/",        label: "Home",    icon: Home           },
  { href: "/chat",    label: "Chat",    icon: MessageSquare  },
  { href: "/contact", label: "Contact", icon: Mail           },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2 text-accent font-semibold tracking-tight hover:opacity-80 transition-opacity"
        >
          <Bot size={20} strokeWidth={1.75} />
          <span className="text-sm">Daniel<span className="text-text-secondary">.ai</span></span>
        </Link>

        {/* Links */}
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
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
