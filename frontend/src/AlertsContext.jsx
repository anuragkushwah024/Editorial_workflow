import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "./api";

// The overdue-alert count for the badge in the navigation (goal 10).
// It refreshes every minute, and any page can call refreshAlerts() right
// after an action that may change it (publish, unpublish, dismiss...).
const AlertsContext = createContext({ count: 0, refreshAlerts: () => {} });

const REFRESH_EVERY_MS = 60 * 1000;

export function AlertsProvider({ children }) {
  const [count, setCount] = useState(0);

  const refreshAlerts = useCallback(() => {
    api
      .get("/api/alerts/")
      .then((response) => setCount(response.data.count))
      .catch(() => {
        // A failed refresh keeps the last known count; the next one will try again.
      });
  }, []);

  useEffect(() => {
    refreshAlerts();
    const timer = setInterval(refreshAlerts, REFRESH_EVERY_MS);
    return () => clearInterval(timer);
  }, [refreshAlerts]);

  return <AlertsContext.Provider value={{ count: count, refreshAlerts: refreshAlerts }}>{children}</AlertsContext.Provider>;
}

export function useAlerts() {
  return useContext(AlertsContext);
}
