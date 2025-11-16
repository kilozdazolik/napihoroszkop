import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Navbar from "../landingPage/Navbar";
import Footer from "../landingPage/Footer";
import HoroscopeGenerator from "./HoroscopeGenerator";

export default function Application() {
  const [searchParams] = useSearchParams();
  const [unsubscribeStatus, setUnsubscribeStatus] = useState("");

  useEffect(() => {
    const token = searchParams.get("unsubscribeToken");
    if (!token) return;

    const controller = new AbortController();

    const run = async () => {
      try {
        const res = await fetch(
          `/api/unsubscribe?token=${encodeURIComponent(token)}`,
          {
            method: "POST",
            signal: controller.signal,
          }
        );

        let data = {};
        try {
          data = await res.json();
        } catch {
          data = {};
        }

        if (res.ok && data.success) {
          if (data.already_unsubscribed) {
            setUnsubscribeStatus(
              data.message ||
                "Ez az email cím már korábban leiratkozott a napi horoszkópról."
            );
          } else {
            setUnsubscribeStatus(
              data.message ||
                "Sikeresen leiratkoztál a napi horoszkóp hírlevélről."
            );
          }
        } else {
          setUnsubscribeStatus(
            data.detail ||
              data.message ||
              "A leiratkozás nem sikerült. Kérlek próbáld meg később újra."
          );
        }
      } catch {
        if (!controller.signal.aborted) {
          setUnsubscribeStatus(
            "Hálózati hiba történt a leiratkozás során. Kérlek próbáld meg később újra."
          );
        }
      }
    };

    run();

    return () => {
      controller.abort();
    };
  }, [searchParams]);

  return (
    <>
      <Navbar />
      {unsubscribeStatus && (
        <div className="unsubscribe-banner">
          {unsubscribeStatus}
        </div>
      )}
      <HoroscopeGenerator />
      <Footer />
    </>
  );
}
