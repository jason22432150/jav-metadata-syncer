import { useEffect, useState } from "react";
import Lookup from "./pages/Lookup";
import Settings from "./pages/Settings";

type Route = "lookup" | "settings";

function readRoute(): Route {
  return window.location.hash === "#settings" ? "settings" : "lookup";
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute);
  useEffect(() => {
    const onHash = () => setRoute(readRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route === "settings" ? <Settings /> : <Lookup />;
}
