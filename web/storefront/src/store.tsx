import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { track } from "./api";
import type { Article, EventType } from "./types";

interface Shopper {
  customerId: string | null; // null = guest
  age: number | null; // used for guests
}

interface StoreState {
  sessionId: string;
  shopper: Shopper;
  setShopper: (s: Shopper) => void;
  sessionItems: number[]; // viewed this session, newest first
  noteViewed: (id: number) => void;
  bag: Article[];
  addToBag: (a: Article, placement: string) => void;
  removeFromBag: (id: number) => void;
  clearBag: () => void;
  bagOpen: boolean;
  setBagOpen: (v: boolean) => void;
  modelVersion: string;
  setModelVersion: (v: string) => void;
  log: (type: EventType, articleId: number, placement: string) => void;
}

const Ctx = createContext<StoreState | null>(null);

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage can be unavailable in private windows */
  }
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [sessionId] = useState(() => {
    const existing = load<string | null>("tl.session", null);
    const id = existing ?? crypto.randomUUID();
    save("tl.session", id);
    return id;
  });
  const [shopper, setShopperState] = useState<Shopper>(() => load("tl.shopper", { customerId: null, age: 30 }));
  const [sessionItems, setSessionItems] = useState<number[]>([]);
  const [bag, setBag] = useState<Article[]>(() => load("tl.bag", []));
  const [bagOpen, setBagOpen] = useState(false);
  const [modelVersion, setModelVersion] = useState("");

  useEffect(() => save("tl.bag", bag), [bag]);

  const setShopper = useCallback((s: Shopper) => {
    setShopperState(s);
    save("tl.shopper", s);
    setSessionItems([]); // a new shopper starts a fresh session context
  }, []);

  const log = useCallback(
    (type: EventType, articleId: number, placement: string) =>
      track({
        session_id: sessionId,
        customer_id: shopper.customerId,
        article_id: articleId,
        event_type: type,
        placement,
        model_version: modelVersion,
      }),
    [sessionId, shopper.customerId, modelVersion],
  );

  const noteViewed = useCallback((id: number) => {
    setSessionItems((prev) => [id, ...prev.filter((x) => x !== id)].slice(0, 20));
  }, []);

  const addToBag = useCallback(
    (a: Article, placement: string) => {
      setBag((prev) => (prev.some((x) => x.article_id === a.article_id) ? prev : [...prev, a]));
      log("add_to_cart", a.article_id, placement);
      setBagOpen(true);
    },
    [log],
  );

  const value = useMemo<StoreState>(
    () => ({
      sessionId,
      shopper,
      setShopper,
      sessionItems,
      noteViewed,
      bag,
      addToBag,
      removeFromBag: (id) => setBag((prev) => prev.filter((x) => x.article_id !== id)),
      clearBag: () => setBag([]),
      bagOpen,
      setBagOpen,
      modelVersion,
      setModelVersion,
      log,
    }),
    [sessionId, shopper, setShopper, sessionItems, noteViewed, bag, addToBag, bagOpen, modelVersion, log],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): StoreState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useStore must be used inside StoreProvider");
  return v;
}
