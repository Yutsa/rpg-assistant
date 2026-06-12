(ns rpg-assistant-web.events
  (:require [cljs.core.async :refer [<! go]]
            [rpg-assistant-web.api :as api]
            [rpg-assistant-web.state :as state]))

(defonce ^:private !render (atom nil))

(defn set-render! [f]
  (reset! !render f))

(defn- render! []
  (when-let [f @!render]
    (f)))

(defn- load-campaigns! []
  (swap! state/store assoc
         :campaigns-loading? true
         :campaigns-error nil)
  (render!)
  (go
    (let [result (<! (api/fetch-json "/campaigns"))]
      (if (:ok result)
        (swap! state/store assoc
               :campaigns (:data result)
               :campaigns-loading? false
               :campaigns-error nil)
        (swap! state/store assoc
               :campaigns-loading? false
               :campaigns-error (or (:error result) "Erreur réseau")))
      (render!))))

(defn dispatch-event! [{:replicant/keys [js-event]} actions]
  (doseq [action actions]
    (case (first action)
      :dom/prevent-default (some-> js-event .preventDefault)
      :navigate (do
                  (state/navigate! (second action))
                  (render!))
      :load-campaigns (load-campaigns!)
      :retry-campaigns (load-campaigns!)
      nil)))

(defn install-popstate! []
  (.addEventListener js/window "popstate"
                     (fn [_]
                       (state/reset-route!)
                       (render!))))
