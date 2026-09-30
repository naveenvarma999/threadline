import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Customer } from "../types";

/** Demo control: browse as one of the anonymised customers, or as a guest of a chosen age. */
export function ShopperPicker() {
  const { shopper, setShopper } = useStore();
  const [customers, setCustomers] = useState<Customer[]>([]);

  useEffect(() => {
    api.demoCustomers().then(setCustomers).catch(() => setCustomers([]));
  }, []);

  return (
    <div className="picker">
      <label htmlFor="shopper">Viewing as</label>
      <select
        id="shopper"
        value={shopper.customerId ?? "guest"}
        onChange={(e) => setShopper({ customerId: e.target.value === "guest" ? null : e.target.value, age: shopper.age })}
      >
        <option value="guest">Guest shopper</option>
        {customers.map((c) => (
          <option key={c.customer_id} value={c.customer_id}>
            Customer {c.customer_id.slice(0, 6)} · {c.age ?? "?"} · {c.n_purchases} orders
          </option>
        ))}
      </select>
      {shopper.customerId === null && (
        <>
          <label htmlFor="age" className="sr-only">
            Guest age
          </label>
          <select id="age" value={shopper.age ?? 30} onChange={(e) => setShopper({ customerId: null, age: Number(e.target.value) })}>
            {[20, 30, 40, 50, 60].map((a) => (
              <option key={a} value={a}>
                Age {a}s
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  );
}
