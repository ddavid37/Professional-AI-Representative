"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, Send, User } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div
      className={`msg-enter flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs
          ${isUser
            ? "bg-accent text-background"
            : "border border-border bg-surface text-accent"
          }`}
      >
        {isUser ? <User size={13} /> : <Bot size={13} />}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap
          ${isUser
            ? "rounded-tr-sm bg-accent text-background"
            : "rounded-tl-sm border border-border bg-surface text-text-primary"
          }`}
      >
        {msg.content}
        {msg.streaming && (
          <span className="cursor-blink ml-0.5 inline-block w-1.5 h-3.5 bg-accent align-middle rounded-sm" />
        )}
      </div>
    </div>
  );
}

const STARTER_PROMPTS = [
  "What are Daniel's main ML skills?",
  "Tell me about his Federated Learning work.",
  "Is Daniel open to new opportunities?",
  "What is Daniel graduating with?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm Daniel's AI representative. Ask me about his background, projects, skills, or graduation plans. If I can't answer something, I'll make sure Daniel follows up with you.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text.trim(),
    };
    const assistantMsgId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantMsgId, role: "assistant", content: "", streaming: true },
    ]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text.trim() }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double-newline
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === "token" && payload.delta) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, content: m.content + payload.delta }
                    : m
                )
              );
            } else if (payload.type === "error") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, content: `⚠️ Error: ${payload.message}` }
                    : m
                )
              );
            }
          } catch {
            // Ignore malformed SSE frames
          }
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                content:
                  "Sorry, I couldn't reach the backend right now. Please try again in a moment.",
                streaming: false,
              }
            : m
        )
      );
    } finally {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId ? { ...m, streaming: false } : m
        )
      );
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">

      {/* Header */}
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-accent/30 bg-accent-muted">
          <Bot size={16} className="text-accent" />
        </div>
        <div>
          <p className="text-sm font-semibold text-text-primary">Daniel's AI Rep</p>
          <p className="text-xs text-text-secondary">Powered by GPT-4o-mini · Azure OpenAI</p>
        </div>
        <span className="ml-auto flex items-center gap-1.5 text-xs text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          Online
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Starter prompts (only when no user messages yet) */}
      {messages.length === 1 && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {STARTER_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-left text-xs text-text-secondary hover:border-accent/40 hover:text-text-primary transition-colors"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <form
        onSubmit={onSubmit}
        className="mt-4 flex items-end gap-2 rounded-xl border border-border bg-surface p-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
          placeholder="Ask about Daniel's background, projects, or skills…"
          rows={1}
          disabled={loading}
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-text-primary placeholder:text-text-muted outline-none disabled:opacity-50 max-h-[120px]"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-background transition-opacity hover:opacity-90 disabled:opacity-40"
          aria-label="Send message"
        >
          <Send size={14} />
        </button>
      </form>
      <p className="mt-2 text-center text-xs text-text-muted">
        Shift + Enter for new line · Enter to send
      </p>
    </div>
  );
}
