"use client";

import { useSyncExternalStore } from "react";

import type { Turn } from "@/components/chat/use-chat";

/**
 * Conversation history, stored in the browser.
 *
 * Local-first on purpose. The backend already persists conversations for signed-in users
 * under Row Level Security, but signing in is optional here — the FAQ is public and
 * requiring an account to ask a public question is friction with no security benefit. So
 * history has to work for anonymous visitors too, and the only place to keep it without
 * inventing an identity for them is their own browser.
 *
 * That is also the honest privacy position: an anonymous person's chat log stays on their
 * machine rather than becoming a row we hold against a hashed IP.
 *
 * Reactivity is `useSyncExternalStore` over a single module-level store, which gets
 * cross-tab sync for free: the `storage` event fires in every OTHER tab, so renaming a
 * chat in one updates the sidebar in the rest.
 */

const STORAGE_KEY = "winchat:conversations:v1";
const MAX_CONVERSATIONS = 100;

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  turns: Turn[];
}

type Listener = () => void;

const listeners = new Set<Listener>();

/**
 * `useSyncExternalStore` compares snapshots by reference and re-renders on every change.
 * Re-parsing localStorage on each call would return a fresh array every time and spin
 * forever, so the parsed value is cached and invalidated only on an actual write.
 */
let cache: Conversation[] | null = null;

const EMPTY: Conversation[] = [];

function read(): Conversation[] {
  if (cache) return cache;
  if (typeof window === "undefined") return EMPTY;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    cache = Array.isArray(parsed) ? (parsed as Conversation[]) : EMPTY;
  } catch {
    // Corrupt or unavailable storage (private mode, quota, a hand-edited value) must not
    // take the app down — an empty history is a working app.
    cache = EMPTY;
  }
  return cache;
}

function write(next: Conversation[]): void {
  cache = next.slice(0, MAX_CONVERSATIONS);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch {
    // Over quota or storage disabled. The in-memory cache still holds this session, so
    // the app keeps working; only persistence across reloads is lost.
  }
  for (const listener of listeners) listener();
}

if (typeof window !== "undefined") {
  // Fires in other tabs only — exactly the cross-tab case we want to react to.
  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    cache = null;
    for (const listener of listeners) listener();
  });
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function newConversationId(): string {
  // `crypto.randomUUID` needs a secure context; localhost counts, but a plain-http
  // deployment would not, so there is a fallback rather than a crash.
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function titleFrom(question: string): string {
  const cleaned = question.trim().replace(/\s+/g, " ");
  return cleaned.length > 60 ? `${cleaned.slice(0, 57)}…` : cleaned || "New chat";
}

export function listConversations(): Conversation[] {
  return read();
}

export function getConversation(id: string): Conversation | undefined {
  return read().find((conversation) => conversation.id === id);
}

/** Insert or update, keeping the list ordered most-recent first. */
export function saveConversation(conversation: Conversation): void {
  const others = read().filter((candidate) => candidate.id !== conversation.id);
  write([conversation, ...others].sort((a, b) => b.updatedAt - a.updatedAt));
}

export function removeConversation(id: string): void {
  write(read().filter((conversation) => conversation.id !== id));
}

export function renameConversation(id: string, title: string): void {
  const trimmed = title.trim();
  if (!trimmed) return;
  write(
    read().map((conversation) =>
      conversation.id === id ? { ...conversation, title: trimmed } : conversation,
    ),
  );
}

export function clearConversations(): void {
  write([]);
}

/** Subscribe a component to the conversation list. */
export function useConversations(): Conversation[] {
  return useSyncExternalStore(
    subscribe,
    read,
    // Server snapshot: history lives in the browser, so there is nothing to render on the
    // server. A stable EMPTY reference keeps this from looping during hydration.
    () => EMPTY,
  );
}
