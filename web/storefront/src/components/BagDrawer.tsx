import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { GarmentArt } from "./GarmentArt";

export function BagDrawer({ onOrdered }: { onOrdered: () => void }) {
  const { bag, bagOpen, setBagOpen, removeFromBag, clearBag, sessionId, shopper } = useStore();
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const total = bag.reduce((s, a) => s + Number(a.price), 0);

  useEffect(() => {
    if (!bagOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setBagOpen(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [bagOpen, setBagOpen]);

  useEffect(() => {
    if (bagOpen && bag.length) setStatus("idle");
  }, [bagOpen, bag.length]);

  async function checkout() {
    setStatus("sending");
    try {
      await api.checkout({ session_id: sessionId, customer_id: shopper.customerId, article_ids: bag.map((a) => a.article_id) });
      clearBag();
      setStatus("done");
      onOrdered();
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className={bagOpen ? "drawer-layer open" : "drawer-layer"} aria-hidden={!bagOpen}>
      <div className="drawer-scrim" onClick={() => setBagOpen(false)} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Shopping bag">
        <header className="drawer-head">
          <h2>Bag {bag.length > 0 && <span className="muted">({bag.length})</span>}</h2>
          <button className="text-btn" onClick={() => setBagOpen(false)}>
            Close
          </button>
        </header>

        {status === "done" && (
          <div className="drawer-note ok">
            <p className="drawer-note-title">Order placed</p>
            <p>Your purchases now feed into your recommendations. Close the bag to see the updated edit.</p>
          </div>
        )}
        {status === "error" && (
          <div className="drawer-note bad">
            <p>Checkout failed. Check that the API is running and try again.</p>
          </div>
        )}
        {bag.length === 0 && status !== "done" && (
          <div className="drawer-empty">
            <p>Your bag is empty.</p>
            <p className="muted">Press + on any item to add it.</p>
          </div>
        )}

        <ul className="bag-list">
          {bag.map((a) => (
            <li key={a.article_id}>
              <GarmentArt article={a} className="bag-art" />
              <div className="bag-info">
                <p className="card-title">{a.prod_name}</p>
                <p className="muted">{a.colour} · Size M</p>
                <p className="price">£{a.price}</p>
              </div>
              <button className="text-btn small" onClick={() => removeFromBag(a.article_id)} aria-label={`Remove ${a.prod_name}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>

        {bag.length > 0 && (
          <footer className="drawer-foot">
            <div className="total-row">
              <span>Total</span>
              <span className="price">£{total.toFixed(2)}</span>
            </div>
            <button className="block-btn" onClick={checkout} disabled={status === "sending"}>
              {status === "sending" ? "Placing order…" : "Place demo order"}
            </button>
            <p className="muted small">No payment is taken. Orders are logged as training events.</p>
          </footer>
        )}
      </aside>
    </div>
  );
}
