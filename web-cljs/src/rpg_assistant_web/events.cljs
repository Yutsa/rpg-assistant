(ns rpg-assistant-web.events
  (:require [rpg-assistant-web.api :as api]
            [rpg-assistant-web.state :as state]))

(defonce ^:private !render (atom nil))

(defn set-render! [f]
  (reset! !render f))

(defn- render! []
  (when-let [f @!render]
    (f)))

(defn load-campaigns! []
  (swap! state/store assoc
         :campaigns-loading? true
         :campaigns-error nil)
  (render!)
  (-> (api/fetch-json "/campaigns")
      (.then
       (fn [result]
         (if (:ok result)
           (swap! state/store assoc
                  :campaigns (:data result)
                  :campaigns-loading? false
                  :campaigns-error nil)
           (swap! state/store assoc
                  :campaigns-loading? false
                  :campaigns-error (or (:error result) "Erreur réseau")))
         (render!)))))

(defn dispatch-event! [_replicant-data actions]
  (doseq [action actions]
    (case (first action)
      :load-campaigns (load-campaigns!)
      :retry-campaigns (load-campaigns!)
      nil)))
